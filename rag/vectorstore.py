"""Base vectorielle FAISS (étape 3.3).

Construit, persiste et recharge l'index **FAISS** des événements à partir des chunks
(étape 3.1) et du modèle d'embeddings (étape 3.2).

Choix d'index — ``IndexFlatL2`` (recherche **exacte et exhaustive**) :
- pour un POC de quelques milliers de vecteurs, la recherche exacte est instantanée et
  garantit un rappel de 100 % (aucune approximation) ;
- les vecteurs étant **normalisés** (norme 1, cf. ``rag/embeddings.py``), la distance L2
  ordonne les résultats exactement comme la **similarité cosinus** — d'où la stratégie
  ``COSINE`` déclarée explicitement ;
- pour un passage à l'échelle (centaines de milliers / millions de vecteurs), on basculerait
  vers un index approximatif type ``IVF``/``HNSW`` (recherche sous-linéaire au prix d'un
  rappel approché et d'une phase d'entraînement) — hors périmètre de ce POC.

Persistance via ``save_local`` : ``index.faiss`` (vecteurs) + ``index.pkl`` (docstore =
textes **et métadonnées** : dates, lieu, catégorie, url, id), répondant à l'exigence de
stocker les métadonnées avec les vecteurs.
"""

from __future__ import annotations

from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.documents import Document

from rag.chunking import build_chunks
from rag.config import settings
from rag.embeddings import get_embeddings


def build_vectorstore(documents: list[Document], embeddings=None) -> FAISS:
    """Indexe une liste de chunks dans un index FAISS exact (cosinus)."""
    if not documents:
        raise ValueError("Aucun document à indexer : vérifiez le jeu structuré (étape 2).")
    embeddings = embeddings or get_embeddings()
    return FAISS.from_documents(
        documents,
        embeddings,
        distance_strategy=DistanceStrategy.COSINE,
    )


def save_vectorstore(vectorstore: FAISS, path: str | Path | None = None) -> Path:
    """Persiste l'index sur disque (``index.faiss`` + ``index.pkl``)."""
    path = Path(path) if path is not None else settings.vectorstore_dir
    path.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(path))
    return path


def load_vectorstore(path: str | Path | None = None, embeddings=None) -> FAISS:
    """Recharge l'index persistant depuis le disque.

    ``allow_dangerous_deserialization=True`` est requis car le docstore est un pickle ;
    c'est sans risque ici, l'index étant généré localement par ``build_index.py``.
    """
    path = Path(path) if path is not None else settings.vectorstore_dir
    if not (path / "index.faiss").exists():
        raise FileNotFoundError(
            f"Index FAISS introuvable dans {path}. Lancez d'abord scripts/build_index.py."
        )
    embeddings = embeddings or get_embeddings()
    return FAISS.load_local(str(path), embeddings, allow_dangerous_deserialization=True)


def vector_count(vectorstore: FAISS) -> int:
    """Nombre de vecteurs effectivement présents dans l'index."""
    return vectorstore.index.ntotal


def build_and_save(
    df=None, path: str | Path | None = None, embeddings=None
) -> FAISS:
    """Pipeline complet : parquet → chunks → index FAISS → disque."""
    chunks = build_chunks(df)
    vectorstore = build_vectorstore(chunks, embeddings=embeddings)
    save_vectorstore(vectorstore, path)
    return vectorstore
