"""Modèle d'embeddings local (étape 3.2).

Expose le modèle d'embeddings **multilingue** (HuggingFace / sentence-transformers) utilisé
pour vectoriser les chunks à l'indexation (étape 3) **et** la question de l'utilisateur à
l'interrogation (étape 5). Le modèle est **chargé une seule fois** puis réutilisé (cache),
conformément à l'énoncé : un rechargement à chaque requête serait coûteux.

Choix : embeddings HuggingFace exécutés **en local** (gratuits, sans appel réseau, données
qui ne sortent pas). Alternative possible — ``MistralAIEmbeddings`` (``mistral-embed``, API
payante) — non retenue ici pour rester local et reproductible en démo / CI.

Les vecteurs sont **normalisés** (``normalize_embeddings=True``) : sur des vecteurs de norme 1,
la distance L2 utilisée par FAISS est monotone au cosinus, ce qui donne une recherche par
similarité sémantique correcte (cf. ``rag/vectorstore.py``).
"""

from __future__ import annotations

from functools import cache

from langchain_huggingface import HuggingFaceEmbeddings

from rag.config import settings


@cache
def get_embeddings(model_name: str | None = None) -> HuggingFaceEmbeddings:
    """Renvoie le modèle d'embeddings (instancié une seule fois par nom de modèle).

    Le décorateur ``cache`` garantit qu'une même configuration ne charge le modèle
    qu'une fois : l'indexation et l'API partagent ainsi la même instance en mémoire.
    """
    return HuggingFaceEmbeddings(
        model_name=model_name or settings.embedding_model,
        model_kwargs={"device": "cpu"},  # faiss-cpu : portabilité (Docker, CI, démo locale)
        encode_kwargs={"normalize_embeddings": True},  # norme 1 -> L2 ≈ cosinus
    )
