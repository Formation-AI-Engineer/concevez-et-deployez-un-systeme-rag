"""Tests de validation du jeu de données produit (étape 2.3).

Contrôlent que le parquet réellement généré (``data/processed/events.parquet``) respecte
les garanties attendues : schéma/types, fenêtre temporelle, localisation, complétude.
Ces tests sont ignorés si le fichier n'a pas encore été généré (CI sans données).
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from rag.config import settings
from scripts.fetch_events import _city_matches

PARQUET = settings.processed_data_path
RAW = settings.raw_data_path

pytestmark = pytest.mark.skipif(
    not PARQUET.exists(), reason=f"{PARQUET} non généré (lancer scripts/preprocess_events.py)"
)

EXPECTED_COLUMNS = {
    "uid", "title", "description", "long_description", "keywords", "date_range",
    "date_start", "date_end", "next_date", "location_name", "address", "city",
    "postal_code", "latitude", "longitude", "agenda_uid", "agenda_title", "slug",
    "url", "document",
}


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return pd.read_parquet(PARQUET)


# --- Schéma & types ------------------------------------------------------------

def test_schema_colonnes_presentes(df):
    assert set(df.columns) >= EXPECTED_COLUMNS


def test_schema_types(df):
    assert pd.api.types.is_integer_dtype(df["uid"])
    assert pd.api.types.is_integer_dtype(df["agenda_uid"])
    assert pd.api.types.is_float_dtype(df["latitude"])
    assert pd.api.types.is_float_dtype(df["longitude"])
    for col in ("title", "description", "city", "document"):
        assert pd.api.types.is_string_dtype(df[col])


# --- Filtrage localisation -----------------------------------------------------

def test_tous_les_evenements_dans_la_zone(df):
    hors_zone = df.loc[~df["city"].apply(lambda c: _city_matches(c, settings.events_city)), "city"]
    assert hors_zone.empty, f"villes hors zone : {hors_zone.unique().tolist()}"


# --- Filtrage période ----------------------------------------------------------

def test_aucun_evenement_anterieur_a_la_fenetre(df):
    """La dernière occurrence (``date_end``) ne doit pas précéder la borne ``since``.

    On s'ancre sur le ``since`` réellement utilisé à la collecte (méta du JSON brut)
    plutôt que sur la date du jour, pour un test stable dans le temps.
    """
    if not RAW.exists():
        pytest.skip("data/raw/events.json absent : borne 'since' inconnue")
    since = json.loads(RAW.read_text(encoding="utf-8"))["meta"]["since"]
    window_start = pd.Timestamp(since).tz_localize("Europe/Paris") - pd.Timedelta(days=2)

    ends = pd.to_datetime(df["date_end"], utc=True, errors="coerce").dropna()
    assert (ends >= window_start.tz_convert("UTC")).all()


# --- Valeurs manquantes / complétude -------------------------------------------

def test_pas_de_document_vide(df):
    assert (df["document"].str.len() > 0).all()


def test_pas_de_date_de_debut_manquante(df):
    assert df["date_start"].notna().all()
    assert (df["date_start"].str.len() > 0).all()


def test_uid_present_et_unique(df):
    assert df["uid"].notna().all()
    assert df["uid"].is_unique
