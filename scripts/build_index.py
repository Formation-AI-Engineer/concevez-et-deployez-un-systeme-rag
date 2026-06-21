"""(Re)construction de l'index vectoriel FAISS (étape 3.3).

Lit le jeu structuré (``data/processed/events.parquet``), découpe les événements en chunks,
les vectorise avec le modèle d'embeddings local, puis persiste l'index FAISS
(``vectorstore/index/`` : ``index.faiss`` + ``index.pkl``).

Usage :
    uv run python scripts/build_index.py
    uv run python scripts/build_index.py --processed data/processed/events.parquet
"""

from __future__ import annotations

import argparse
import sys

from rag.chunking import build_chunks, load_events
from rag.config import settings
from rag.embeddings import get_embeddings
from rag.vectorstore import build_vectorstore, save_vectorstore, vector_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Construction de l'index FAISS (étape 3.3).")
    parser.add_argument("--processed", default=str(settings.processed_data_path),
                        help="Parquet structuré en entrée (étape 2).")
    parser.add_argument("--out", default=str(settings.vectorstore_dir),
                        help="Répertoire de sortie de l'index FAISS.")
    args = parser.parse_args(argv)

    try:
        df = load_events(args.processed)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"Découpage de {len(df)} événements en chunks…")
    chunks = build_chunks(df)
    print(f"  -> {len(chunks)} chunks")

    print(f"Chargement du modèle d'embeddings ({settings.embedding_model})…")
    embeddings = get_embeddings()

    print("Vectorisation + indexation FAISS…")
    vectorstore = build_vectorstore(chunks, embeddings=embeddings)

    out = save_vectorstore(vectorstore, args.out)

    print("=== Index FAISS construit ===")
    print(f"  événements indexés : {df['uid'].nunique()}")
    print(f"  vecteurs (chunks)  : {vector_count(vectorstore)}")
    print(f"  dimension          : {vectorstore.index.d}")
    print(f"  -> {out}/ (index.faiss + index.pkl)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
