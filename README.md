# Assistant RAG — Recommandation d'événements culturels (Puls-Events)

POC d'un système **RAG (Retrieval-Augmented Generation)** capable de répondre en langage naturel à des
questions d'utilisateurs sur les **événements culturels à venir**, en combinant **recherche vectorielle**
(FAISS) et **génération** (Mistral), orchestrées avec **LangChain**. Les données proviennent de l'API
**Open Agenda**. Le système est exposé via une **API REST FastAPI** et conteneurisé avec **Docker**.

> Contexte : mission freelance pour **Puls-Events** (OpenClassrooms — « Concevez et déployez un système RAG »).

## Architecture

```
Open Agenda API ──► pré-processing (pandas) ──► chunks ──► embeddings (HuggingFace)
                                                              │
                                                              ▼
   question ──► API FastAPI ──► LangChain RAG ──► FAISS (recherche sémantique) ──► Mistral (LLM) ──► réponse
```

| Composant            | Technologie                                              |
|----------------------|----------------------------------------------------------|
| Source de données    | API Open Agenda                                          |
| Embeddings           | `sentence-transformers` (multilingue) via HuggingFace    |
| Base vectorielle     | FAISS (`faiss-cpu`)                                      |
| Orchestration        | LangChain                                                |
| Génération (LLM)     | Mistral (API)                                            |
| API REST             | FastAPI + Uvicorn                                        |
| Évaluation           | Ragas + jeu de test annoté                               |
| Conteneurisation     | Docker                                                   |

## Structure du dépôt

```
.
├── rag/             # Logique métier RAG (chargement, pré-processing, vectorstore, chaîne)
├── api/             # API REST FastAPI exposant le système
├── scripts/         # Scripts CLI (récupération données, build index, évaluation)
├── tests/           # Tests unitaires
├── eval/            # Jeu de test annoté + rapports d'évaluation
├── data/            # Données Open Agenda (brutes / nettoyées) — non versionnées
├── vectorstore/     # Index FAISS — reconstructible, non versionné
├── docs/            # Fiches d'étape (une par étape de la mission)
└── notebooks/       # Explorations
```

## Installation & reproduction

Prérequis : **Python 3.10–3.12** et [`uv`](https://docs.astral.sh/uv/).

```bash
# 1. Installer les dépendances dans un environnement isolé
uv sync --extra dev --extra eval

# 2. Configurer les secrets (clés API Mistral et Open Agenda)
cp .env.example .env   # puis éditer .env

# 3. Vérifier les imports clés
uv run python -c "import faiss; from langchain_community.vectorstores import FAISS; print('OK')"
```

> ⚠️ Ne jamais versionner le fichier `.env` ni les clés d'API.

## Utilisation (vue d'ensemble — voir `docs/` pour le détail)

```bash
# Récupérer les événements Open Agenda (étape 2)
uv run python scripts/fetch_events.py

# Construire l'index vectoriel FAISS (étape 3)
uv run python scripts/build_index.py

# Lancer l'API (étape 5)
uv run uvicorn api.main:app --reload
# → Swagger : http://localhost:8000/docs

# Évaluer la qualité des réponses (étape 4/5)
uv run python scripts/evaluate_rag.py
```

## Documentation

Le déroulé du projet est découpé en fiches d'étape dans [`docs/`](docs/) :

| Étape | Fiche |
|-------|-------|
| Contexte | [`contexte_general.md`](docs/contexte_general.md) |
| Suivi | [`fiche_taches_projet7.md`](docs/fiche_taches_projet7.md) |
| 1 | [`etape1_configuration_environnement.md`](docs/etape1_configuration_environnement.md) |
| 2 | [`etape2_preprocessing_openagenda.md`](docs/etape2_preprocessing_openagenda.md) |
| 3 | [`etape3_base_vectorielle_faiss.md`](docs/etape3_base_vectorielle_faiss.md) |
| 4 | [`etape4_integration_langchain_rag.md`](docs/etape4_integration_langchain_rag.md) |
| 5 | [`etape5_api_rest.md`](docs/etape5_api_rest.md) |
| 6 | [`etape6_conteneurisation_demo.md`](docs/etape6_conteneurisation_demo.md) |

## Statut

🚧 POC en cours d'initialisation.
