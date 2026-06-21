"""Découpage des événements en chunks LangChain (étape 3.1).

Transforme le jeu structuré (``data/processed/events.parquet``) en une liste de
``Document`` LangChain prêts à être vectorisés :
- 1 événement → 1 ``Document`` dont ``page_content`` est le texte consolidé (colonne
  ``document``) et ``metadata`` porte les champs utiles (id, dates, lieu, catégorie, url) ;
- découpage des textes longs via ``RecursiveCharacterTextSplitter`` (``CHUNK_SIZE`` /
  ``CHUNK_OVERLAP`` issus de la configuration) ; chaque chunk conserve l'``uid`` de son
  événement plus son rang (``chunk``) et le nombre total de chunks (``n_chunks``).

Le découpage est nécessaire car le modèle d'embeddings tronque les textes trop longs :
sans chunking, la fin des descriptions volumineuses ne serait jamais vectorisée.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config import settings

# Champs conservés comme métadonnées du Document (énoncé : dates, lieu, catégorie, url, id).
# L'id (``uid``) relie chaque chunk à son événement d'origine.
_METADATA_FIELDS = (
    "uid",
    "title",
    "date_start",
    "date_end",
    "next_date",
    "date_range",
    "location_name",
    "address",
    "city",
    "postal_code",
    "latitude",
    "longitude",
    "keywords",
    "agenda_title",
    "slug",
    "url",
)


def load_events(path: str | Path | None = None) -> pd.DataFrame:
    """Charge le jeu structuré (parquet) produit à l'étape 2."""
    path = Path(path) if path is not None else settings.processed_data_path
    if not path.exists():
        raise FileNotFoundError(
            f"Jeu structuré introuvable : {path}. Lancez d'abord scripts/preprocess_events.py."
        )
    return pd.read_parquet(path)


def _event_metadata(row: pd.Series) -> dict:
    """Extrait les métadonnées d'un événement (valeurs ``NaN`` normalisées en ``None``)."""
    meta: dict = {}
    for field in _METADATA_FIELDS:
        value = row.get(field)
        # ``pd.isna`` gère les flottants manquants (latitude/longitude) sans casser les chaînes.
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            meta[field] = None
        elif field == "uid":
            meta[field] = int(value)
        else:
            meta[field] = value
    return meta


def events_to_documents(df: pd.DataFrame) -> list[Document]:
    """Convertit chaque ligne d'événement en un ``Document`` LangChain (avant découpage)."""
    documents: list[Document] = []
    for _, row in df.iterrows():
        text = row["document"]
        if not text:  # garde-fou : aucun événement sans texte ne devrait passer l'étape 2
            continue
        documents.append(Document(page_content=text, metadata=_event_metadata(row)))
    return documents


def make_splitter(
    chunk_size: int | None = None, chunk_overlap: int | None = None
) -> RecursiveCharacterTextSplitter:
    """Construit le splitter récursif paramétré par la configuration (``.env``)."""
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size if chunk_size is not None else settings.chunk_size,
        chunk_overlap=chunk_overlap if chunk_overlap is not None else settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=True,
    )


def split_events(
    documents: list[Document], splitter: RecursiveCharacterTextSplitter | None = None
) -> list[Document]:
    """Découpe les documents-événements en chunks en traçant ``chunk`` / ``n_chunks``.

    Le découpage se fait événement par événement afin de numéroter les chunks au sein de
    chaque événement et d'enregistrer leur nombre total (utile pour vérifier en test que
    tous les événements ont bien été indexés).
    """
    splitter = splitter or make_splitter()
    chunks: list[Document] = []
    for doc in documents:
        parts = splitter.split_documents([doc])
        n = len(parts)
        for i, part in enumerate(parts):
            part.metadata = {**part.metadata, "chunk": i, "n_chunks": n}
            chunks.append(part)
    return chunks


def build_chunks(df: pd.DataFrame | None = None) -> list[Document]:
    """Pipeline complet : parquet → documents-événements → chunks prêts pour l'embedding."""
    if df is None:
        df = load_events()
    return split_events(events_to_documents(df))
