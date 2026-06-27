"""Tests unitaires du filtrage localisation (étape 2.3).

Valide la logique de ciblage par ville de ``scripts/fetch_events.py`` : normalisation
(casse/accents) et correspondance ville, y compris les arrondissements parisiens.
"""

from __future__ import annotations

from scripts.fetch_events import _city_matches, _normalize

# --- _normalize() --------------------------------------------------------------

def test_normalize_minuscule_et_sans_accents():
    assert _normalize("Orléans") == "orleans"
    assert _normalize("  PARIS  ") == "paris"


def test_normalize_none():
    assert _normalize(None) == ""


# --- _city_matches() -----------------------------------------------------------

def test_city_matches_egalite_insensible_casse_accents():
    assert _city_matches("Paris", "Paris")
    assert _city_matches("paris", "Paris")
    assert _city_matches("PARIS", "paris")


def test_city_matches_accepte_arrondissements():
    assert _city_matches("Paris 14", "Paris")
    assert _city_matches("Paris 11e", "Paris")
    assert _city_matches("Paris-15", "Paris")


def test_city_matches_rejette_autres_communes():
    assert not _city_matches("Parisot", "Paris")     # préfixe sans frontière
    assert not _city_matches("Lyon", "Paris")
    assert not _city_matches("Neuilly-sur-Seine", "Paris")


def test_city_matches_ville_absente():
    assert not _city_matches(None, "Paris")
    assert not _city_matches("", "Paris")
