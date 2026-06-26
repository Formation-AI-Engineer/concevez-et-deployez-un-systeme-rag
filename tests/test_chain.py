"""Tests de la chaîne RAG et de sa robustesse (étapes 4.1 / 4.2).

Ces tests sont **hermétiques** : ils n'appellent ni l'API Mistral ni le réseau. On injecte
dans ``RAGAssistant`` :
- une **doublure de vectorstore** qui renvoie des couples (document, distance) contrôlés,
  pour piloter la pertinence et tester le seuil ;
- un **LLM factice** (``FakeListChatModel``) qui rejoue des réponses prédéfinies, pour
  vérifier l'orchestration LCEL sans génération réelle.

Couvre la robustesse 4.2 : cas « aucun document pertinent » (réponse honnête), présence des
infos clés (titre/date/lieu) dans le contexte, et plusieurs scénarios d'interaction.
"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from rag.chain import (
    NO_MATCH_MESSAGE,
    RAGAssistant,
    _format_event,
)


def _event(uid: int, title: str, **meta) -> Document:
    """Construit un Document-événement avec des métadonnées par défaut plausibles."""
    base = {
        "uid": uid,
        "title": title,
        "date_range": "du 1 au 5 juillet 2026",
        "location_name": "Le Sunset",
        "city": "Paris",
        "url": "https://example.org/e",
    }
    base.update(meta)
    return Document(page_content=f"Description de {title}.", metadata=base)


class FakeVectorStore:
    """Doublure de FAISS : renvoie des (document, distance) prédéfinis, triés par distance.

    Implémente le minimum utilisé par ``RAGAssistant`` : ``similarity_search_with_score``
    (filtrage par seuil) et ``as_retriever`` (interface publique 4.1).
    """

    def __init__(self, scored: list[tuple[Document, float]]):
        self._scored = sorted(scored, key=lambda ds: ds[1])

    def similarity_search_with_score(self, query: str, k: int = 4):
        return self._scored[:k]

    def as_retriever(self, **kwargs):
        return object()  # non utilisé dans ces tests, présent pour l'init


def _assistant(scored, responses, threshold=0.9, top_k=4):
    """Fabrique un RAGAssistant entièrement doublé (vectorstore + LLM factices)."""
    return RAGAssistant(
        vectorstore=FakeVectorStore(scored),
        llm=FakeListChatModel(responses=responses),
        top_k=top_k,
        relevance_threshold=threshold,
    )


# --- Récupération & seuil de pertinence ----------------------------------------

def test_retrieve_ecarte_les_documents_au_dela_du_seuil():
    """Seuls les documents sous le seuil de distance sont conservés."""
    scored = [
        (_event(1, "Concert de jazz"), 0.40),  # pertinent
        (_event(2, "Exposition"), 0.85),        # pertinent (sous 0.9)
        (_event(3, "Atelier poterie"), 1.30),   # hors seuil -> écarté
    ]
    assistant = _assistant(scored, responses=["peu importe"])
    docs = assistant.retrieve("jazz à Paris")
    uids = [d.metadata["uid"] for d in docs]
    assert uids == [1, 2]


def test_answer_repond_honnetement_sans_document_pertinent():
    """Requête hors-périmètre : tous les voisins dépassent le seuil -> réponse honnête, sans LLM."""
    scored = [
        (_event(1, "Concert"), 1.40),
        (_event(2, "Théâtre"), 1.55),
    ]
    # Le LLM factice lèverait/insérerait une réponse si appelé ; il ne doit PAS l'être.
    assistant = _assistant(scored, responses=["NE DEVRAIT PAS APPARAITRE"])
    res = assistant.answer("comment réparer un moteur diesel ?")
    assert res.answer == NO_MATCH_MESSAGE
    assert res.sources == []


# --- Génération augmentée (scénarios d'interaction) ----------------------------

def test_answer_genere_et_trace_les_sources():
    """Avec des documents pertinents : la réponse du LLM est renvoyée + les sources tracées."""
    scored = [
        (_event(1, "Festival de jazz au Sunset"), 0.42),
        (_event(2, "Concert piano-voix"), 0.60),
    ]
    assistant = _assistant(scored, responses=["Voici deux concerts de jazz à Paris..."])
    res = assistant.answer("Quels concerts de jazz à Paris cette semaine ?")
    assert "jazz" in res.answer.lower()
    assert [d.metadata["uid"] for d in res.sources] == [1, 2]


def test_plusieurs_scenarios_dinteraction():
    """Plusieurs questions enchaînées : chacune renvoie sa réponse (questions indépendantes)."""
    scored = [(_event(1, "Exposition photo"), 0.55)]
    reponses = ["Réponse expo", "Réponse concert", "Réponse théâtre"]
    assistant = _assistant(scored, responses=reponses)
    questions = [
        "Une exposition photo ce week-end ?",
        "Un concert ce soir ?",
        "Du théâtre demain ?",
    ]
    obtenues = [assistant.answer(q).answer for q in questions]
    assert obtenues == reponses  # FakeListChatModel rejoue les réponses dans l'ordre


# --- Infos clés dans le contexte transmis au LLM -------------------------------

def test_format_event_contient_titre_date_lieu():
    """Le contexte transmis au LLM expose les infos clés issues des métadonnées."""
    rendu = _format_event(
        _event(1, "Concert de jazz", date_range="le 3 juillet 2026", location_name="Le Sunset")
    )
    assert "Concert de jazz" in rendu
    assert "le 3 juillet 2026" in rendu
    assert "Le Sunset" in rendu
    assert "Paris" in rendu
