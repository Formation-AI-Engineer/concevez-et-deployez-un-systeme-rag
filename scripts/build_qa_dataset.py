"""(Ré)annotation du jeu de test à partir des données indexées (étape 4.3).

Reprend les **questions** existantes de ``eval/qa_dataset.json`` et, pour chaque question du
périmètre, régénère :
- les ``expected_event_uids`` = événements **réellement récupérés** par le retriever sur l'index
  courant (méthode d'annotation de l'étape 4.3, automatisée) ;
- une ``reference_answer`` **ancrée sur les faits réels** de ces événements (titre, date, lieu).

Les questions **hors-périmètre** (refus attendu) sont conservées telles quelles. Le filtrage
temporel est **désactivé** ici : l'annotation et l'évaluation se font sur l'instantané indexé
(reproductible, indépendant de la date du jour). À relancer après tout rafraîchissement des
données pour réaligner le jeu sur le nouvel index.

Usage :
    python scripts/build_qa_dataset.py            # réécrit eval/qa_dataset.json
    python scripts/build_qa_dataset.py --dry-run  # affiche sans écrire
"""

from __future__ import annotations

import argparse
import json
from datetime import date

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from rag.chain import RAGAssistant
from rag.config import ROOT_DIR

QA_PATH = ROOT_DIR / "eval" / "qa_dataset.json"

REFUSAL = (
    "Je n'ai pas trouvé d'événement correspondant à votre demande. "
    "Je peux seulement vous recommander des événements culturels à Paris."
)


def _distinct_events(docs):
    """Événements distincts (par uid) récupérés, dans l'ordre de pertinence."""
    vus: set[int] = set()
    events = []
    for d in docs:
        uid = d.metadata.get("uid")
        if uid is None or uid in vus:
            continue
        vus.add(uid)
        # Dédoublonne les composantes du lieu (évite « Paris Paris »), comme l'API.
        lieu = " ".join(
            dict.fromkeys(x for x in (d.metadata.get("location_name"), d.metadata.get("city")) if x)
        )
        events.append(
            {"uid": int(uid), "title": d.metadata.get("title") or "Événement",
             "date": d.metadata.get("date_range"), "lieu": lieu or None}
        )
    return events


def _reference_answer(events) -> str:
    """Rédige une réponse de référence factuelle à partir des événements récupérés."""
    def _details(e):
        bits = [b for b in (e["date"], e["lieu"]) if b]
        return f" ({', '.join(bits)})" if bits else ""

    if len(events) == 1:
        e = events[0]
        return f"Je vous recommande « {e['title']} »{_details(e)}."
    items = [f"« {e['title']} »{_details(e)}" for e in events]
    return "Voici des événements correspondants : " + " ; ".join(items) + "."


def rebuild(pairs, assistant) -> list[dict]:
    """Reconstruit chaque paire : questions inchangées, ancrage régénéré sur l'index courant."""
    out = []
    for p in pairs:
        base = {"id": p["id"], "category": p["category"], "question": p["question"]}
        if p["category"] == "hors_perimetre":
            # Refus attendu dans tous les cas ; no_match=True seulement si le seuil écarte tout.
            docs = assistant.retrieve(p["question"])
            out.append({**base, "reference_answer": p.get("reference_answer", REFUSAL),
                        "expected_event_uids": [],
                        "expects_no_match": not docs, "expects_refusal": True})
            continue
        events = _distinct_events(assistant.retrieve(p["question"]))
        if not events:  # plus aucun événement pertinent -> refus honnête
            out.append({**base, "reference_answer": REFUSAL, "expected_event_uids": [],
                        "expects_no_match": True, "expects_refusal": True})
        else:
            out.append({**base, "reference_answer": _reference_answer(events),
                        "expected_event_uids": [e["uid"] for e in events],
                        "expects_no_match": False, "expects_refusal": False})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="(Ré)annote le jeu de test sur l'index courant.")
    parser.add_argument("--dry-run", action="store_true", help="Afficher sans écrire le fichier.")
    args = parser.parse_args()

    data = json.loads(QA_PATH.read_text(encoding="utf-8"))
    # Filtrage temporel OFF : annotation/éval reproductibles sur l'instantané indexé.
    assistant = RAGAssistant(
        llm=FakeListChatModel(responses=["(non utilisé)"]), filter_past_events=False
    )
    pairs = rebuild(data["pairs"], assistant)

    meta = data.get("metadata", {})
    meta.update({
        "annotated_on": date.today().isoformat(),
        "note": "Réannoté sur l'index courant via scripts/build_qa_dataset.py (références ancrées "
                "sur les événements réellement récupérés ; filtrage temporel OFF).",
    })
    payload = {"metadata": meta, "pairs": pairs}

    n_match = sum(not p["expects_no_match"] for p in pairs)
    print(f"Paires : {len(pairs)} | dans le périmètre : {n_match} | refus : {len(pairs) - n_match}")
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    QA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {QA_PATH.relative_to(ROOT_DIR)} réécrit.")


if __name__ == "__main__":
    main()
