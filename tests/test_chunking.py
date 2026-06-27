"""Tests du découpage en chunks (étape 3.1).

Tests purs (fixtures synthétiques, aucun modèle chargé) : conversion événement → Document,
préservation des métadonnées, et découpage des textes longs en plusieurs chunks traçables.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from rag.chunking import (
    build_chunks,
    events_to_documents,
    make_splitter,
    split_events,
)


@pytest.fixture
def df() -> pd.DataFrame:
    """Deux événements : un court (1 chunk) et un long (plusieurs chunks)."""
    long_text = "\n\n".join(f"Paragraphe {i} de la description détaillée. " * 5 for i in range(8))
    return pd.DataFrame(
        [
            {
                "uid": 101,
                "title": "Concert de jazz",
                "date_start": "2026-07-01T20:00:00+02:00",
                "date_end": "2026-07-01T22:00:00+02:00",
                "next_date": "2026-07-01T20:00:00+02:00",
                "date_range": "1 juillet 2026",
                "location_name": "Le Sunset",
                "address": "60 rue des Lombards",
                "city": "Paris",
                "postal_code": "75001",
                "latitude": 48.86,
                "longitude": 2.34,
                "keywords": "jazz, concert",
                "agenda_title": "Agenda Musique",
                "slug": "concert-de-jazz",
                "url": "https://example.org/jazz",
                "document": "Concert de jazz\nUn trio au Sunset.",
            },
            {
                "uid": 202,
                "title": "Exposition",
                "date_start": "2026-08-10T10:00:00+02:00",
                "date_end": "2026-09-10T18:00:00+02:00",
                "next_date": "2026-08-10T10:00:00+02:00",
                "date_range": "août 2026",
                "location_name": "Galerie",
                "address": "1 rue de Rivoli",
                "city": "Paris",
                "postal_code": "75004",
                "latitude": np.nan,  # coordonnées manquantes
                "longitude": np.nan,
                "keywords": "art",
                "agenda_title": "Agenda Expo",
                "slug": "exposition",
                "url": "https://example.org/expo",
                "document": f"Exposition\n{long_text}",
            },
        ]
    )


# --- Conversion événement → Document -------------------------------------------

def test_un_document_par_evenement(df):
    docs = events_to_documents(df)
    assert len(docs) == 2
    assert docs[0].page_content == "Concert de jazz\nUn trio au Sunset."


def test_metadonnees_presentes_et_typees(df):
    meta = events_to_documents(df)[0].metadata
    assert meta["uid"] == 101 and isinstance(meta["uid"], int)
    assert meta["city"] == "Paris"
    assert meta["url"] == "https://example.org/jazz"
    assert meta["date_start"].startswith("2026-07-01")


def test_coordonnees_manquantes_normalisees_en_none(df):
    meta = events_to_documents(df)[1].metadata
    assert meta["latitude"] is None
    assert meta["longitude"] is None


# --- Découpage -----------------------------------------------------------------

def test_texte_court_reste_un_seul_chunk(df):
    docs = events_to_documents(df)
    chunks = split_events([docs[0]], make_splitter(chunk_size=800, chunk_overlap=100))
    assert len(chunks) == 1
    assert chunks[0].metadata["chunk"] == 0
    assert chunks[0].metadata["n_chunks"] == 1


def test_texte_long_decoupe_en_plusieurs_chunks(df):
    docs = events_to_documents(df)
    chunks = split_events([docs[1]], make_splitter(chunk_size=200, chunk_overlap=20))
    assert len(chunks) > 1
    # chunks numérotés en continu, tous porteurs du même nombre total et du même uid
    assert [c.metadata["chunk"] for c in chunks] == list(range(len(chunks)))
    assert all(c.metadata["n_chunks"] == len(chunks) for c in chunks)
    assert all(c.metadata["uid"] == 202 for c in chunks)


def test_chunk_respecte_la_taille_max(df):
    docs = events_to_documents(df)
    size = 200
    chunks = split_events([docs[1]], make_splitter(chunk_size=size, chunk_overlap=20))
    # tolérance : le splitter peut légèrement dépasser sur un séparateur, mais pas massivement
    assert all(len(c.page_content) <= size * 1.5 for c in chunks)


def test_build_chunks_couvre_tous_les_evenements(df):
    chunks = build_chunks(df)
    assert {c.metadata["uid"] for c in chunks} == {101, 202}
