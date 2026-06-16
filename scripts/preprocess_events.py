"""Nettoyage / structuration des événements Open Agenda (étape 2.2).

Lit le JSON brut (``data/raw/events.json``), produit un jeu structuré et nettoyé
(``data/processed/events.parquet``) avec une colonne ``document`` prête pour la vectorisation.

Usage :
    uv run python scripts/preprocess_events.py
"""

from __future__ import annotations

import argparse
import sys

from rag.config import settings
from rag.preprocessing import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pré-processing des événements (étape 2.2).")
    parser.add_argument("--raw", default=str(settings.raw_data_path))
    parser.add_argument("--out", default=str(settings.processed_data_path))
    args = parser.parse_args(argv)

    try:
        df = run(args.raw, args.out)
    except FileNotFoundError:
        print(f"Fichier brut introuvable : {args.raw}. Lancez d'abord scripts/fetch_events.py.",
              file=sys.stderr)
        return 1

    print("=== Pré-processing terminé ===")
    print(f"  événements structurés : {len(df)}")
    if not df.empty:
        print(f"  villes (top 3)        : {df['city'].value_counts().head(3).to_dict()}")
        print(f"  longueur doc (médiane): {int(df['document'].str.len().median())} caractères")
        print(f"  sans description      : {(df['description'].str.len() == 0).sum()}")
    print(f"  -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
