# syntax=docker/dockerfile:1
#
# Étape 6.1 — Conteneurisation de l'API RAG.
#
# Stratégie d'index : l'index FAISS pré-construit (vectorstore/index/) ET le modèle
# d'embeddings HuggingFace sont EMBARQUÉS dans l'image. Le conteneur fait donc tourner
# la démo complète SANS dépendance réseau au démarrage ; seule la génération Mistral
# (POST /ask) appelle l'API externe au moment de la requête. Cela répond à l'exigence de
# l'énoncé : « éviter de dépendre d'une connexion instable → version locale prête ».
#
# Build :  docker build -t assistant-rag-evenements .
# Run   :  docker run --rm -p 8000:8000 --env-file .env.local assistant-rag-evenements

FROM python:3.11-slim

# uv : gestionnaire de dépendances (installé via pip pour ne dépendre d'aucun tag d'image tiers).
RUN pip install --no-cache-dir uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    # Cache HuggingFace fixé dans l'image : le modèle d'embeddings pré-téléchargé (cf. plus bas)
    # est retrouvé à l'exécution sans nouvel appel réseau.
    HF_HOME=/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/huggingface

# Exécution sous un utilisateur non privilégié (bonne pratique sécurité). On bascule sur ce
# compte AVANT d'installer le venv et de télécharger le modèle : les volumineux artefacts
# (venv, cache HuggingFace) sont ainsi créés directement avec les bons droits — on évite un
# `chown -R` récursif coûteux (plusieurs minutes sur un FS overlay).
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
RUN chown appuser:appuser /app
USER appuser

# 1. Dépendances seules (couche mise en cache tant que pyproject.toml / uv.lock ne changent pas).
#    --no-dev : on exclut pytest/ruff/jupyter et l'extra eval (Ragas) — inutiles pour servir l'API.
COPY --chown=appuser:appuser pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# 2. Code applicatif + artefacts embarqués (index FAISS pré-construit + données structurées).
COPY --chown=appuser:appuser rag/ rag/
COPY --chown=appuser:appuser api/ api/
COPY --chown=appuser:appuser scripts/ scripts/
COPY --chown=appuser:appuser vectorstore/index/ vectorstore/index/
COPY --chown=appuser:appuser data/processed/ data/processed/

# Installe le projet lui-même (packages rag/ et api/) dans le venv.
RUN uv sync --frozen --no-dev

# 3. Pré-télécharge le modèle d'embeddings DANS l'image (démo hors-ligne, démarrage rapide).
RUN python -c "from rag.embeddings import get_embeddings; get_embeddings()"

EXPOSE 8000

# Sonde de vivacité : /health répond 200 dès que l'app est levée (ok ou degraded).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

# L'assistant (index + modèle) est chargé une seule fois au démarrage via le lifespan FastAPI.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
