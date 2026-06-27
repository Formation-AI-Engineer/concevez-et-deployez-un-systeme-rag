"""Évaluation de la qualité du système RAG (étape 4.4).

Compare les réponses **générées** par ``RAGAssistant`` aux réponses de **référence** annotées
(``eval/qa_dataset.json``, étape 4.3) et produit un rapport chiffré dans ``eval/reports/``.

Deux familles de métriques :

1. **Locales** (aucun LLM juge, aucun coût) :
   - *similarité sémantique* : cosinus entre l'embedding de la réponse générée et celui de la
     référence (mêmes embeddings normalisés que l'index → cosinus = produit scalaire) ;
   - *Exact Match* : égalité stricte après normalisation (casse, accents, ponctuation, espaces) ;
   - *couverture des infos clés* : part des événements attendus dont le titre apparaît dans la
     réponse (critère « mêmes informations ») ;
   - *classification* correcte / partielle / incorrecte, dérivée des deux signaux ci-dessus.
   Les cas hors-périmètre (refus attendu) sont évalués de la même façon : la référence étant
   elle-même un refus, une similarité élevée = refus correct.

2. **Ragas** (optionnelles, nécessitent un LLM juge) : *faithfulness*, *answer relevancy*,
   *context recall*, *context precision*, câblées sur **Mistral** + nos embeddings HF. Cette
   partie est **protégée** : si ``ragas`` est absent ou incompatible avec l'environnement, le
   script l'ignore proprement et poursuit avec les métriques locales.

Usage :
    python scripts/evaluate_rag.py                 # tout le jeu, local (+ Ragas si dispo)
    python scripts/evaluate_rag.py --sample 5      # 5 premières questions (maîtrise du coût)
    python scripts/evaluate_rag.py --no-ragas      # métriques locales seulement
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from rag.config import ROOT_DIR
from rag.embeddings import get_embeddings

QA_PATH = ROOT_DIR / "eval" / "qa_dataset.json"
REPORTS_DIR = ROOT_DIR / "eval" / "reports"

# Seuils de classification (sur la similarité sémantique et la couverture des infos clés).
# Calibrés pour le critère de l'énoncé : « même sens + mêmes informations ».
SIM_OK = 0.70       # au-dessus : sens jugé fidèle à la référence
SIM_PARTIAL = 0.50  # entre les deux : partiellement correct
COVERAGE_OK = 0.50  # part minimale d'événements attendus cités pour une réponse « correcte »


# --- Normalisation & métriques locales -----------------------------------------

def _normalize(text: str) -> str:
    """Minuscule, sans accents ni ponctuation, espaces normalisés (pour l'Exact Match)."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def semantic_similarity(generated: str, reference: str, embeddings=None) -> float:
    """Cosinus entre les embeddings (normalisés) des deux textes : 1 = identique sémantiquement."""
    embeddings = embeddings or get_embeddings()
    a, b = embeddings.embed_documents([generated, reference])
    # Embeddings de norme 1 : le cosinus se réduit au produit scalaire.
    return float(np.dot(a, b))


def exact_match(generated: str, reference: str) -> bool:
    """Égalité stricte après normalisation (rare en texte libre, mais demandé par l'énoncé)."""
    return _normalize(generated) == _normalize(reference)


def key_info_coverage(generated: str, expected_titles: list[str]) -> float:
    """Part des événements attendus dont le titre est cité dans la réponse (0..1).

    Un titre est jugé « cité » si une part suffisante de ses mots significatifs apparaît dans
    la réponse (robuste aux reformulations partielles, ponctuation, casse).
    """
    if not expected_titles:
        return 1.0  # rien à couvrir (questions hors-périmètre) -> non pénalisant
    rep = _normalize(generated)
    rep_mots = set(rep.split())
    cites = 0
    for titre in expected_titles:
        mots = [m for m in _normalize(titre).split() if len(m) > 3]
        if not mots:
            continue
        recouvrement = sum(m in rep_mots for m in mots) / len(mots)
        if recouvrement >= 0.5:
            cites += 1
    return cites / len(expected_titles)


def classify(similarity: float, coverage: float, has_expected: bool) -> str:
    """Classe une réponse en correcte / partielle / incorrecte (sens + infos)."""
    if has_expected:
        if similarity >= SIM_OK and coverage >= COVERAGE_OK:
            return "correcte"
        if similarity >= SIM_PARTIAL or coverage >= 0.30:
            return "partielle"
        return "incorrecte"
    # Cas refus / hors-périmètre : seul le sens (vs la référence de refus) compte.
    if similarity >= SIM_OK:
        return "correcte"
    if similarity >= SIM_PARTIAL:
        return "partielle"
    return "incorrecte"


# --- Structures de résultat ----------------------------------------------------

@dataclass
class PairResult:
    id: str
    category: str
    question: str
    reference_answer: str
    generated_answer: str
    retrieved_uids: list[int]
    semantic_similarity: float
    exact_match: bool
    key_info_coverage: float
    classification: str
    ragas: dict = field(default_factory=dict)


# --- Génération + évaluation locale --------------------------------------------

def _expected_titles(pair: dict, uid_to_title: dict[int, str]) -> list[str]:
    return [uid_to_title[u] for u in pair["expected_event_uids"] if u in uid_to_title]


def evaluate_pairs(pairs, assistant, embeddings, uid_to_title) -> list[PairResult]:
    """Génère une réponse par question et calcule les métriques locales."""
    results: list[PairResult] = []
    for i, p in enumerate(pairs, start=1):
        ans = assistant.answer(p["question"])
        titres = _expected_titles(p, uid_to_title)
        sim = semantic_similarity(ans.answer, p["reference_answer"], embeddings)
        cov = key_info_coverage(ans.answer, titres)
        has_expected = bool(p["expected_event_uids"])
        results.append(
            PairResult(
                id=p["id"],
                category=p["category"],
                question=p["question"],
                reference_answer=p["reference_answer"],
                generated_answer=ans.answer,
                retrieved_uids=[d.metadata.get("uid") for d in ans.sources],
                semantic_similarity=round(sim, 4),
                exact_match=exact_match(ans.answer, p["reference_answer"]),
                key_info_coverage=round(cov, 4),
                classification=classify(sim, cov, has_expected),
            )
        )
        print(f"  [{i}/{len(pairs)}] {p['id']:32} sim={sim:.2f} cov={cov:.2f} -> {results[-1].classification}")
    return results


# --- Métriques Ragas (optionnelles, protégées) ---------------------------------

def _install_vertexai_shim() -> None:
    """Contourne une incompatibilité de ``ragas 0.4.3`` avec ``langchain_community >= 0.4``.

    ``ragas/llms/base.py`` importe ``langchain_community.chat_models.vertexai.ChatVertexAI``,
    chemin supprimé de ``langchain_community 0.4`` (déplacé vers ``langchain_google_vertexai``).
    On enregistre un module de remplacement avec un ``ChatVertexAI`` factice : ragas a seulement
    besoin que l'import réussisse — le symbole n'est jamais instancié ici (on évalue avec Mistral).
    """
    import sys
    import types

    name = "langchain_community.chat_models.vertexai"
    if name in sys.modules:
        return
    try:  # privilégier le vrai symbole s'il est disponible
        from langchain_google_vertexai import ChatVertexAI  # type: ignore
    except Exception:
        class ChatVertexAI:  # stub non instancié
            pass
    module = types.ModuleType(name)
    module.ChatVertexAI = ChatVertexAI
    sys.modules[name] = module


def compute_ragas(pairs, results, assistant) -> dict:
    """Calcule les métriques Ragas si la bibliothèque est disponible et compatible.

    Retourne ``{"available": False, "reason": ...}`` si Ragas ne peut pas être chargé/exécuté,
    afin que le rapport reste produit avec les seules métriques locales.
    """
    try:
        _install_vertexai_shim()
        from ragas import EvaluationDataset, evaluate
        from ragas.run_config import RunConfig
        from ragas.dataset_schema import SingleTurnSample
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (
            Faithfulness,
            LLMContextPrecisionWithReference,
            LLMContextRecall,
            ResponseRelevancy,
        )
    except Exception as exc:  # import cassé (ex. conflit langchain_community) ou absent
        return {"available": False, "reason": f"import ragas impossible : {exc}"}

    try:
        by_id = {p["id"]: p for p in pairs}
        samples = []
        for r in results:
            p = by_id[r.id]
            # Métriques de contexte non définies sans contexte : on saute les cas sans source.
            if not r.retrieved_uids:
                continue
            ans = assistant.answer(p["question"])  # régénère pour récupérer les contextes
            samples.append(
                SingleTurnSample(
                    user_input=p["question"],
                    response=ans.answer,
                    retrieved_contexts=[d.page_content for d in ans.sources],
                    reference=p["reference_answer"],
                )
            )
        if not samples:
            return {"available": False, "reason": "aucun échantillon avec contexte"}

        llm = LangchainLLMWrapper(assistant.llm)
        emb = LangchainEmbeddingsWrapper(get_embeddings())
        # Mistral applique un rate-limit strict : on sérialise les appels (1 worker) et on laisse
        # de la marge (timeout + retries) pour éviter les ConnectError/TimeoutError qui sinon
        # produisent des scores NaN. C'est plus lent mais fiable sur un petit jeu de test.
        run_config = RunConfig(max_workers=1, timeout=180, max_retries=10, max_wait=60)
        scores = evaluate(
            dataset=EvaluationDataset(samples=samples),
            metrics=[
                Faithfulness(),
                ResponseRelevancy(),
                LLMContextRecall(),
                LLMContextPrecisionWithReference(),
            ],
            llm=llm,
            embeddings=emb,
            run_config=run_config,
        )
        df = scores.to_pandas()
        # ``mean()`` ignore les NaN ; une colonne entièrement NaN reste NaN -> on la rend en null
        # (JSON valide) plutôt que d'écrire le littéral non standard ``NaN``.
        means = {}
        for c in df.select_dtypes("number").columns:
            m = df[c].mean()
            means[c] = None if np.isnan(m) else round(float(m), 4)
        return {"available": True, "n_samples": len(samples), "means": means}
    except Exception as exc:  # pragma: no cover - dépend de l'API/réseau Mistral
        return {"available": False, "reason": f"exécution ragas échouée : {exc}"}


# --- Agrégation & rapport ------------------------------------------------------

def build_summary(results: list[PairResult]) -> dict:
    """Agrège les métriques locales (global + par catégorie + distribution des classes)."""
    n = len(results) or 1
    classes = ["correcte", "partielle", "incorrecte"]
    distrib = {c: sum(r.classification == c for r in results) for c in classes}
    par_cat: dict[str, dict] = {}
    for r in results:
        d = par_cat.setdefault(r.category, {"n": 0, "sim": 0.0, "correctes": 0})
        d["n"] += 1
        d["sim"] += r.semantic_similarity
        d["correctes"] += r.classification == "correcte"
    for d in par_cat.values():
        d["similarite_moyenne"] = round(d.pop("sim") / d["n"], 4)
        d["taux_correctes"] = round(d.pop("correctes") / d["n"], 4)
    return {
        "n_questions": len(results),
        "similarite_semantique_moyenne": round(sum(r.semantic_similarity for r in results) / n, 4),
        "exact_match_taux": round(sum(r.exact_match for r in results) / n, 4),
        "couverture_infos_moyenne": round(sum(r.key_info_coverage for r in results) / n, 4),
        "classification": distrib,
        "classification_taux": {c: round(v / n, 4) for c, v in distrib.items()},
        "par_categorie": par_cat,
    }


def write_reports(summary, results, ragas, out_dir: Path, stamp: str) -> tuple[Path, Path]:
    """Écrit le rapport détaillé (JSON) et la synthèse lisible (Markdown)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"report_{stamp}.json"
    md_path = out_dir / f"report_{stamp}.md"

    payload = {
        "generated_at": stamp,
        "summary": summary,
        "ragas": ragas,
        "results": [asdict(r) for r in results],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lignes = [
        f"# Rapport d'évaluation RAG — {stamp}",
        "",
        f"- Questions évaluées : **{summary['n_questions']}**",
        f"- Similarité sémantique moyenne : **{summary['similarite_semantique_moyenne']}**",
        f"- Exact Match : **{summary['exact_match_taux']}**",
        f"- Couverture des infos clés : **{summary['couverture_infos_moyenne']}**",
        "",
        "## Classification",
        "",
        "| Classe | Nombre | Taux |",
        "|---|---|---|",
    ]
    for c in ("correcte", "partielle", "incorrecte"):
        lignes.append(f"| {c} | {summary['classification'][c]} | {summary['classification_taux'][c]} |")
    lignes += ["", "## Par catégorie", "", "| Catégorie | n | Sim. moy. | Taux correctes |", "|---|---|---|---|"]
    for cat, d in summary["par_categorie"].items():
        lignes.append(f"| {cat} | {d['n']} | {d['similarite_moyenne']} | {d['taux_correctes']} |")

    lignes += ["", "## Ragas"]
    if ragas.get("available"):
        lignes += ["", f"_Sur {ragas['n_samples']} échantillon(s) avec contexte._", "",
                   "| Métrique | Score moyen |", "|---|---|"]
        for k, v in ragas["means"].items():
            lignes.append(f"| {k} | {'n/a' if v is None else v} |")
    else:
        lignes += ["", f"⚠ Non calculé : {ragas.get('reason', 'indisponible')}"]

    lignes += ["", "## Détail par question", "",
               "| id | catégorie | sim | couv | classe |", "|---|---|---|---|---|"]
    for r in results:
        lignes.append(
            f"| {r.id} | {r.category} | {r.semantic_similarity} | {r.key_info_coverage} | {r.classification} |"
        )
    md_path.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Évalue le RAG sur le jeu de test annoté (4.4).")
    parser.add_argument("--sample", type=int, help="N'évaluer que les N premières questions.")
    parser.add_argument("--no-ragas", action="store_true", help="Désactiver les métriques Ragas.")
    args = parser.parse_args()

    from langchain_core.documents import Document  # noqa: F401  (typage implicite des sources)

    from rag.chain import RAGAssistant
    from rag.chunking import load_events

    with open(QA_PATH, encoding="utf-8") as f:
        pairs = json.load(f)["pairs"]
    if args.sample:
        pairs = pairs[: args.sample]

    # Table uid -> titre, pour mesurer la couverture des infos clés.
    df = load_events()
    uid_to_title = dict(zip(df["uid"].astype(int), df["title"], strict=False))

    print(f"→ Évaluation de {len(pairs)} question(s)…")
    assistant = RAGAssistant()
    embeddings = get_embeddings()
    results = evaluate_pairs(pairs, assistant, embeddings, uid_to_title)

    summary = build_summary(results)
    ragas = {"available": False, "reason": "désactivé (--no-ragas)"}
    if not args.no_ragas:
        print("→ Calcul des métriques Ragas (si disponibles)…")
        ragas = compute_ragas(pairs, results, assistant)
        if not ragas["available"]:
            print(f"  Ragas ignoré : {ragas['reason']}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path, md_path = write_reports(summary, results, ragas, REPORTS_DIR, stamp)

    print("\n=== Synthèse ===")
    print(f"  Similarité moyenne : {summary['similarite_semantique_moyenne']}")
    print(f"  Classification     : {summary['classification']}")
    print(f"  Rapport JSON       : {json_path.relative_to(ROOT_DIR)}")
    print(f"  Rapport Markdown   : {md_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
