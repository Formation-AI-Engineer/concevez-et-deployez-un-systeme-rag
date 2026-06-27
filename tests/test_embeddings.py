"""Tests du modèle d'embeddings local (étape 3.2).

Ces tests chargent le vrai modèle HuggingFace (≈ une fois, fixture de module). Ils sont
ignorés automatiquement si le modèle ne peut pas être chargé (environnement hors-ligne).
"""

from __future__ import annotations

import math

import pytest

from rag.embeddings import get_embeddings


@pytest.fixture(scope="module")
def embeddings():
    try:
        model = get_embeddings()
        model.embed_query("warmup")  # force le chargement réel
    except Exception as exc:  # pragma: no cover - dépend de l'accès réseau/cache HF
        pytest.skip(f"Modèle d'embeddings indisponible : {exc}")
    return model


def _norm(vector) -> float:
    return math.sqrt(sum(x * x for x in vector))


def test_dimension_constante(embeddings):
    a = embeddings.embed_query("concert de jazz")
    b = embeddings.embed_query("exposition de peinture")
    assert len(a) == len(b) > 0


def test_vecteurs_normalises(embeddings):
    vector = embeddings.embed_query("un spectacle de danse contemporaine")
    assert _norm(vector) == pytest.approx(1.0, abs=1e-3)


def test_modele_charge_une_seule_fois(embeddings):
    # même configuration -> même instance (cache lru), pas de rechargement.
    assert get_embeddings() is embeddings


def test_proximite_semantique(embeddings):
    """Un couple proche doit être plus similaire qu'un couple éloigné (cosinus = produit
    scalaire sur des vecteurs normalisés)."""
    concert = embeddings.embed_query("un concert de musique classique")
    symphonie = embeddings.embed_query("une symphonie jouée par un orchestre")
    cuisine = embeddings.embed_query("un cours de cuisine végétarienne")

    sim_proche = sum(x * y for x, y in zip(concert, symphonie, strict=True))
    sim_loin = sum(x * y for x, y in zip(concert, cuisine, strict=True))
    assert sim_proche > sim_loin
