"""Aide à l'annotation du jeu de test RAG (étape 4.3) — reproductibilité.

Ce script **ne génère pas** les réponses de référence (elles sont rédigées à la main) : il
**réimprime les faits bruts** sur lesquels l'annotation s'appuie. Pour chaque question de
``eval/qa_dataset.json``, il interroge le **vrai retriever** (``RAGAssistant.retrieve()``, même
index FAISS et même seuil de pertinence qu'en production) et affiche les événements réellement
récupérés : ``uid``, titre, date, lieu, agenda — tous hérités du fichier ``events.parquet`` via
les métadonnées de l'index.

C'est la **preuve de traçabilité** demandée : on démontre que chaque ``uid`` et chaque fait du
jeu de test provient des données réellement indexées, et que la démarche est rejouable.

Pour chaque question, le script signale aussi l'écart éventuel entre les ``uid`` réellement
récupérés et les ``expected_event_uids`` annotés (utile si l'index ou le seuil change).

Usage :
    python eval/build_qa_dataset.py            # toutes les questions du dataset
    python eval/build_qa_dataset.py -q "jazz"  # une requête ponctuelle hors dataset

Aucune clé d'API Mistral n'est requise : seul le retriever est sollicité (pas de génération).
"""

from __future__ import annotations

import argparse
import json

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from rag.chain import RAGAssistant
from rag.config import ROOT_DIR

QA_PATH = ROOT_DIR / "eval" / "qa_dataset.json"


def _build_assistant(top_k: int) -> RAGAssistant:
    """Assistant limité au retriever (LLM factice : aucune génération, aucune clé requise)."""
    return RAGAssistant(llm=FakeListChatModel(responses=["(non utilisé)"]), top_k=top_k)


def _show(assistant: RAGAssistant, question: str, expected: list[int] | None = None) -> None:
    """Affiche les événements récupérés pour une question, dédoublonnés par uid."""
    docs = assistant.retrieve(question)
    print("=" * 100)
    print(f"Q : {question}  ({len(docs)} doc(s) récupéré(s))")

    vus: set[int] = set()
    uids_recus: list[int] = []
    for d in docs:
        m = d.metadata
        uid = m.get("uid")
        if uid in vus:  # le chunking peut faire remonter le même événement plusieurs fois
            continue
        vus.add(uid)
        uids_recus.append(uid)
        print(f"   [{uid}] {m.get('title')}")
        print(f"         {m.get('date_range')} | {m.get('location_name')} "
              f"| {m.get('agenda_title')}")

    if expected is not None:
        # Invariant d'ancrage : chaque uid annoté DOIT être récupéré par la question.
        # Les voisins récupérés mais non annotés (top-k plus large que le sous-ensemble
        # pertinent retenu à la main) sont normaux : on les affiche à titre indicatif.
        manquants = [u for u in expected if u not in uids_recus]
        extras = [u for u in uids_recus if u not in expected]
        if manquants:
            print(f"   ⚠ ANCRAGE CASSÉ : uid annotés absents du top-k = {manquants}")
        else:
            print("   ✓ tous les uid annotés sont bien récupérés"
                  + (f"  (+ non annotés : {extras})" if extras else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="Réimprime les faits du jeu de test (4.3).")
    parser.add_argument("-q", "--question", help="Interroge une requête ponctuelle hors dataset.")
    parser.add_argument("-k", "--top-k", type=int, default=4, help="Nombre de voisins (défaut 4).")
    args = parser.parse_args()

    assistant = _build_assistant(args.top_k)

    if args.question:
        _show(assistant, args.question)
        return

    with open(QA_PATH, encoding="utf-8") as f:
        pairs = json.load(f)["pairs"]
    for p in pairs:
        _show(assistant, p["question"], p.get("expected_event_uids"))


if __name__ == "__main__":
    main()
