"""Tests unitaires du nettoyage / structuration (étape 2.3).

Tests *purs* (aucun réseau, aucun fichier) : ils valident la logique de
``rag/preprocessing.py`` à partir d'événements bruts factices imitant l'API Open Agenda.
"""

from __future__ import annotations

from rag.preprocessing import (
    build_dataframe,
    build_document_text,
    clean_text,
    event_to_record,
    localized,
)

# Colonnes attendues en sortie (19 champs structurés + le texte consolidé ``document``).
EXPECTED_COLUMNS = {
    "uid", "title", "description", "long_description", "keywords", "date_range",
    "date_start", "date_end", "next_date", "location_name", "address", "city",
    "postal_code", "latitude", "longitude", "agenda_uid", "agenda_title", "slug",
    "url", "document",
}


def make_raw(**overrides) -> dict:
    """Construit un événement brut Open Agenda complet, surchargeable champ par champ."""
    raw = {
        "uid": 1,
        "title": {"fr": "Concert &amp; <b>Jazz</b>", "en": "Jazz Concert"},
        "description": {"fr": "<p>Une  soirée   jazz.</p>"},
        "longDescription": {"fr": "Programme détaillé du concert."},
        "keywords": {"fr": "jazz, musique"},
        "dateRange": {"fr": "le 1 juin 2026"},
        "firstTiming": {"begin": "2026-06-01T20:00:00+02:00", "end": "2026-06-01T22:00:00+02:00"},
        "lastTiming": {"begin": "2026-06-01T20:00:00+02:00", "end": "2026-06-01T22:00:00+02:00"},
        "nextTiming": {"begin": "2026-06-01T20:00:00+02:00"},
        "location": {
            "name": "Salle Pleyel", "address": "252 rue du Faubourg",
            "city": "Paris", "postalCode": "75008", "latitude": 48.87, "longitude": 2.30,
        },
        "originAgenda": {"title": {"fr": "Agenda Test"}, "url": "https://example.org/a"},
        "slug": "concert-jazz",
        "_agenda_uid": 999,
    }
    raw.update(overrides)
    return raw


# --- localized() ---------------------------------------------------------------

def test_localized_prefere_le_francais():
    assert localized({"fr": "Bonjour", "en": "Hello"}) == "Bonjour"


def test_localized_repli_anglais_puis_premiere_valeur():
    assert localized({"en": "Hello"}) == "Hello"
    assert localized({"de": "Hallo"}) == "Hallo"  # ni fr ni en → première valeur non vide


def test_localized_cas_limites():
    assert localized(None) == ""
    assert localized("déjà une chaîne") == "déjà une chaîne"
    assert localized({}) == ""


# --- clean_text() --------------------------------------------------------------

def test_clean_text_retire_html_et_normalise_espaces():
    assert clean_text("<p>Une  soirée   jazz.</p>") == "Une soirée jazz."


def test_clean_text_decode_entites():
    assert clean_text("Concert &amp; f&ecirc;te") == "Concert & fête"


def test_clean_text_vide():
    assert clean_text("") == ""
    assert clean_text(None) == ""


# --- event_to_record() ---------------------------------------------------------

def test_event_to_record_schema_et_types():
    rec = event_to_record(make_raw())
    assert set(rec) == EXPECTED_COLUMNS - {"document"}  # document ajouté plus tard
    assert rec["uid"] == 1
    assert rec["title"] == "Concert & Jazz"            # multilingue + HTML nettoyés
    assert rec["city"] == "Paris"
    assert rec["date_start"] == "2026-06-01T20:00:00+02:00"
    assert rec["date_end"] == "2026-06-01T22:00:00+02:00"
    assert rec["agenda_uid"] == 999                    # traçabilité conservée
    assert rec["agenda_title"] == "Agenda Test"
    assert rec["latitude"] == 48.87


def test_event_to_record_champs_manquants_donnent_chaine_vide():
    rec = event_to_record({"uid": 2})  # événement quasi vide
    assert rec["title"] == ""
    assert rec["city"] == ""
    assert rec["date_start"] is None   # pas de timing → None (pas "")
    assert rec["latitude"] is None


# --- build_document_text() -----------------------------------------------------

def test_build_document_text_contient_les_sections():
    doc = build_document_text(event_to_record(make_raw()))
    assert "Concert & Jazz" in doc
    assert "Quand :" in doc
    assert "Lieu : Salle Pleyel" in doc
    assert "Mots-clés : jazz, musique" in doc


def test_build_document_text_evite_la_redondance_desc():
    rec = event_to_record(make_raw(
        description={"fr": "Même texte."}, longDescription={"fr": "Même texte."},
    ))
    doc = build_document_text(rec)
    assert doc.count("Même texte.") == 1  # description longue identique → non dupliquée


# --- build_dataframe() ---------------------------------------------------------

def test_build_dataframe_colonnes_et_document():
    df = build_dataframe([make_raw()])
    assert set(df.columns) >= EXPECTED_COLUMNS
    assert len(df) == 1
    assert df.loc[0, "document"]  # texte consolidé non vide


def test_build_dataframe_supprime_evenements_sans_contenu():
    sans_contenu = make_raw(uid=2, title={}, description=None, longDescription=None)
    df = build_dataframe([make_raw(uid=1), sans_contenu])
    assert df["uid"].tolist() == [1]  # l'événement sans titre/description est retiré


def test_build_dataframe_dedoublonne_par_uid():
    df = build_dataframe([make_raw(uid=7), make_raw(uid=7)])
    assert len(df) == 1


def test_build_dataframe_entree_vide():
    assert build_dataframe([]).empty
