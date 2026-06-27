"""Tests de la base vectorielle FAISS et de la recherche sémantique (étape 3.4).

Deux familles de tests :
- sur l'**index réellement persisté** (``vectorstore/index/``) : chargement, comptage des
  vecteurs, couverture de tous les événements, présence des métadonnées, pertinence d'une
  requête connue. Ignorés si l'index n'a pas été construit (``scripts/build_index.py``).
- un **round-trip** build → save → load sur un mini-corpus synthétique, indépendant des
  données réelles, pour valider le pipeline et la persistance. Ignoré si le modèle
  d'embeddings ne peut pas être chargé (environnement hors-ligne).
"""

from __future__ import annotations

import pandas as pd
import pytest
from langchain_core.documents import Document

from rag.chunking import build_chunks
from rag.config import settings
from rag.embeddings import get_embeddings
from rag.vectorstore import (
    build_vectorstore,
    load_vectorstore,
    save_vectorstore,
    vector_count,
)

PARQUET = settings.processed_data_path
INDEX_FILE = settings.vectorstore_dir / "index.faiss"

real_index = pytest.mark.skipif(
    not INDEX_FILE.exists(),
    reason=f"{INDEX_FILE} absent (lancer scripts/build_index.py)",
)


def _embeddings_or_skip():
    try:
        model = get_embeddings()
        model.embed_query("warmup")
    except Exception as exc:  # pragma: no cover - dépend de l'accès réseau/cache HF
        pytest.skip(f"Modèle d'embeddings indisponible : {exc}")
    return model


# --- Index réel persisté -------------------------------------------------------

@pytest.fixture(scope="module")
def embeddings():
    return _embeddings_or_skip()


@pytest.fixture(scope="module")
def vs(embeddings):
    return load_vectorstore(embeddings=embeddings)


@pytest.fixture(scope="module")
def df():
    return pd.read_parquet(PARQUET)


@real_index
def test_index_se_charge_et_compte_les_vecteurs(vs, df):
    """L'index se charge et contient autant de vecteurs que de chunks attendus."""
    attendu = len(build_chunks(df))
    assert vector_count(vs) == attendu > 0


@real_index
def test_tous_les_evenements_sont_indexes(vs, df):
    """Chaque événement du parquet est présent dans l'index (via son ``uid``)."""
    uids_index = {doc.metadata["uid"] for doc in vs.docstore._dict.values()}
    uids_parquet = set(df["uid"].tolist())
    assert uids_index == uids_parquet


@real_index
def test_metadonnees_presentes_dans_les_resultats(vs):
    """Les résultats de recherche portent bien les métadonnées (date, lieu, id, url)."""
    docs = vs.similarity_search("exposition d'art contemporain", k=3)
    assert docs
    for doc in docs:
        meta = doc.metadata
        for champ in ("uid", "title", "city", "date_start", "url"):
            assert champ in meta
        assert isinstance(meta["uid"], int)


@real_index
def test_recherche_renvoie_un_top_k_ordonne(vs):
    """``similarity_search_with_score`` renvoie k résultats triés par distance croissante."""
    results = vs.similarity_search_with_score("concert de musique", k=5)
    assert len(results) == 5
    scores = [score for _, score in results]
    assert scores == sorted(scores)  # distance cosinus : plus petit = plus pertinent


@real_index
def test_requete_connue_retrouve_son_evenement(vs, df):
    """Une requête construite depuis le titre d'un événement le retrouve dans le top-k."""
    # événement de référence : un titre distinctif et suffisamment long
    cible = df[df["title"].str.len() > 25].iloc[0]
    resultats = vs.similarity_search(cible["title"], k=5)
    uids_top_k = [doc.metadata["uid"] for doc in resultats]
    assert cible["uid"] in uids_top_k


# --- Round-trip build / save / load (corpus synthétique) -----------------------

def test_build_save_load_roundtrip(tmp_path):
    """Construit un petit index, le persiste, le recharge et l'interroge."""
    embeddings = _embeddings_or_skip()
    docs = [
        Document(page_content="Concert de jazz au Sunset, trio piano-basse-batterie.",
                 metadata={"uid": 1, "city": "Paris"}),
        Document(page_content="Exposition de peinture impressionniste au musée d'Orsay.",
                 metadata={"uid": 2, "city": "Paris"}),
        Document(page_content="Atelier de poterie pour enfants le mercredi.",
                 metadata={"uid": 3, "city": "Paris"}),
    ]

    vectorstore = build_vectorstore(docs, embeddings=embeddings)
    save_vectorstore(vectorstore, tmp_path)
    assert (tmp_path / "index.faiss").exists()
    assert (tmp_path / "index.pkl").exists()

    reloaded = load_vectorstore(tmp_path, embeddings=embeddings)
    assert vector_count(reloaded) == 3

    # la requête la plus proche thématiquement doit ramener l'événement attendu en tête
    top = reloaded.similarity_search("spectacle de musique", k=1)[0]
    assert top.metadata["uid"] == 1
