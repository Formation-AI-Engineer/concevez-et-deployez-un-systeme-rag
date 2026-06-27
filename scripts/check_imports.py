"""Vérification des imports clés du système RAG (étape 1.2).

Reprend les imports demandés par l'énoncé, mais avec les chemins **modernes** valides
(LangChain 1.x, SDK Mistral 2.x). Échoue avec un code de sortie non nul si un import manque
— utilisable tel quel en local ou dans une étape de CI.

Usage :
    uv run python scripts/check_imports.py
"""

from __future__ import annotations

import importlib
import sys

# (instruction d'import, étiquette, équivalent de l'énoncé corrigé)
CHECKS: list[tuple[str, str, str]] = [
    ("faiss", "faiss", "import faiss  (inchangé)"),
    (
        "langchain_community.vectorstores:FAISS",
        "FAISS (vectorstore)",
        "énoncé: from langchain.vectorstores import FAISS  (obsolète)",
    ),
    (
        "langchain_huggingface:HuggingFaceEmbeddings",
        "HuggingFaceEmbeddings",
        "énoncé: from langchain.embeddings import HuggingFaceEmbeddings  (déplacé)",
    ),
    (
        "langchain_mistralai:ChatMistralAI",
        "ChatMistralAI (LLM Mistral)",
        "énoncé: from mistral import MistralClient  (paquet inexistant)",
    ),
]


def _try_import(spec: str) -> None:
    """spec = 'module' ou 'module:attribut'."""
    module, _, attr = spec.partition(":")
    mod = importlib.import_module(module)
    if attr:
        getattr(mod, attr)


def main() -> int:
    print("Vérification des imports clés (étape 1.2)\n")
    ok = True
    for spec, label, note in CHECKS:
        try:
            _try_import(spec)
            print(f"  [OK]   {label:28s} <- {spec}")
            print(f"         {note}")
        except Exception as exc:  # noqa: BLE001 — on veut rapporter tout échec d'import
            ok = False
            print(f"  [FAIL] {label:28s} <- {spec}  ({type(exc).__name__}: {exc})")
    print()
    if ok:
        print("Tous les imports clés sont disponibles. Environnement prêt.")
        return 0
    print("Au moins un import a échoué — vérifier `uv sync`.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
