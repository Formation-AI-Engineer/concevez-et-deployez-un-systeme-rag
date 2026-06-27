"""Validation du jeu de test annoté (étape 4.3).

Vérifie que ``eval/qa_dataset.json`` est bien formé et **réellement ancré** sur les données
indexées : schéma de chaque paire, couverture des catégories, invariants des cas hors-périmètre,
et existence effective des ``expected_event_uids`` dans l'index FAISS (si construit).
"""

from __future__ import annotations

import json

import pytest

from rag.config import ROOT_DIR, settings

QA_PATH = ROOT_DIR / "eval" / "qa_dataset.json"
INDEX_FILE = settings.vectorstore_dir / "index.faiss"

REQUIRED_FIELDS = {
    "id": str,
    "category": str,
    "question": str,
    "reference_answer": str,
    "expected_event_uids": list,
    "expects_no_match": bool,
    "expects_refusal": bool,
}
CATEGORIES = {"type_evenement", "lieu", "periode", "hors_perimetre"}

real_index = pytest.mark.skipif(
    not INDEX_FILE.exists(),
    reason=f"{INDEX_FILE} absent (lancer scripts/build_index.py)",
)


@pytest.fixture(scope="module")
def data():
    with open(QA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def pairs(data):
    return data["pairs"]


def test_au_moins_15_paires(pairs):
    """L'énoncé exige au moins 15 à 20 paires annotées."""
    assert len(pairs) >= 15


def test_schema_de_chaque_paire(pairs):
    """Chaque paire porte tous les champs attendus, bien typés, et une catégorie connue."""
    for p in pairs:
        for champ, typ in REQUIRED_FIELDS.items():
            assert champ in p, f"{p.get('id')}: champ manquant '{champ}'"
            assert isinstance(p[champ], typ), f"{p.get('id')}: '{champ}' mal typé"
        assert p["category"] in CATEGORIES
        assert p["question"].strip()
        assert p["reference_answer"].strip()


def test_identifiants_uniques(pairs):
    """Les identifiants de paires sont uniques (pas de doublon)."""
    ids = [p["id"] for p in pairs]
    assert len(ids) == len(set(ids))


def test_categories_variees_couvertes(pairs):
    """Le jeu couvre bien les quatre familles de cas (dont hors-périmètre)."""
    presentes = {p["category"] for p in pairs}
    assert presentes == CATEGORIES


def test_invariants_hors_perimetre(pairs):
    """Cas hors-périmètre : aucun uid attendu, et refus annoncé."""
    for p in pairs:
        if p["expects_no_match"]:
            assert p["expected_event_uids"] == [], f"{p['id']}: no_match doit n'avoir aucun uid"
            assert p["expects_refusal"], f"{p['id']}: no_match implique un refus"
        if p["category"] == "hors_perimetre":
            assert p["expected_event_uids"] == []


def test_paires_dans_le_perimetre_ont_des_sources(pairs):
    """Les questions du périmètre référencent au moins un événement (traçabilité)."""
    for p in pairs:
        if p["category"] != "hors_perimetre":
            assert p["expected_event_uids"], f"{p['id']}: aucune source annotée"


@real_index
def test_uids_attendus_existent_dans_lindex(pairs):
    """Tous les ``expected_event_uids`` correspondent à des événements réellement indexés."""
    from rag.vectorstore import load_vectorstore

    vs = load_vectorstore()
    uids_index = {doc.metadata["uid"] for doc in vs.docstore._dict.values()}
    attendus = {uid for p in pairs for uid in p["expected_event_uids"]}
    manquants = attendus - uids_index
    assert not manquants, f"uid annotés absents de l'index : {sorted(manquants)}"


@real_index
def test_chaque_reponse_est_ancree_sur_ce_que_la_question_recupere(pairs):
    """Invariant d'ancrage fort : chaque ``uid`` annoté est réellement récupéré par sa question.

    Garantit que les réponses de référence sont fondées sur ce que le système renvoie vraiment
    pour la question stockée (et non sur une formulation antérieure) : ``expected ⊆ retrieved``.
    Vérifie aussi que les cas ``no_match`` ne récupèrent effectivement aucun document.
    """
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    from rag.chain import RAGAssistant

    assistant = RAGAssistant(llm=FakeListChatModel(responses=["(non utilisé)"]))
    erreurs = []
    for p in pairs:
        recus = {d.metadata["uid"] for d in assistant.retrieve(p["question"])}
        absents = set(p["expected_event_uids"]) - recus
        if absents:
            erreurs.append(f"{p['id']}: uid annotés non récupérés {sorted(absents)}")
        if p["expects_no_match"] and recus:
            erreurs.append(f"{p['id']}: no_match attendu mais {len(recus)} doc(s) récupéré(s)")
    assert not erreurs, "ancrage incohérent :\n" + "\n".join(erreurs)
