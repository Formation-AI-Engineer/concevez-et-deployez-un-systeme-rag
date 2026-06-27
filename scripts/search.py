"""Recherche sémantique en ligne de commande (outil de test / démo, étape 3).

Interroge l'index FAISS persistant et affiche les événements les plus proches d'une requête,
avec leur score (distance cosinus : plus bas = plus pertinent) et leurs métadonnées.

Usage :
    uv run python scripts/search.py "concert de jazz"
    uv run python scripts/search.py "exposition de peinture" -k 5
"""

from __future__ import annotations

import argparse
import sys

from rag.vectorstore import load_vectorstore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recherche sémantique dans l'index FAISS.")
    parser.add_argument("query", help="Requête en langage naturel.")
    parser.add_argument("-k", type=int, default=5, help="Nombre de résultats (défaut : 5).")
    args = parser.parse_args(argv)

    try:
        vectorstore = load_vectorstore()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    results = vectorstore.similarity_search_with_score(args.query, k=args.k)
    print(f"🔎 {args.query!r} — top {len(results)} :\n")
    for doc, score in results:
        m = doc.metadata
        date = (m.get("date_start") or "")[:10]
        print(f"[{score:.2f}] {m.get('title', '')}")
        print(f"       {m.get('location_name', '')} {m.get('city', '')} {date}".rstrip())
        if m.get("url"):
            print(f"       {m['url']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
