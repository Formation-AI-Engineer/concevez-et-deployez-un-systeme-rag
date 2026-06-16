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
cp .env.example .env.local   # puis renseigner MISTRAL_API_KEY et OPENAGENDA_API_KEY

# 3. Vérifier les imports clés (faiss, FAISS, HuggingFaceEmbeddings, ChatMistralAI)
uv run python scripts/check_imports.py
```

> Les secrets sont lus depuis `.env.local` (prioritaire) puis `.env`. Les deux sont ignorés par
> Git : ⚠️ **ne jamais versionner** une clé d'API.

## Utilisation (vue d'ensemble — voir `docs/` pour le détail)

```bash
# (diagnostic) explorer l'API Open Agenda et valider la connexion       [disponible]
uv run python scripts/explore_openagenda.py

# Récupérer les événements Open Agenda -> data/raw/events.json (étape 2) [disponible]
uv run python scripts/fetch_events.py            # options : --city, --target-events, --per-agenda-max

# Construire l'index vectoriel FAISS (étape 3)                           [à venir]
uv run python scripts/build_index.py

# Lancer l'API (étape 5)                                                 [à venir]
uv run uvicorn api.main:app --reload             # → Swagger : http://localhost:8000/docs

# Évaluer la qualité des réponses (étape 4/5)                            [à venir]
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

🚧 POC en cours.
- ✅ Étape 1 — environnement uv, imports clés vérifiés, clés API validées
- ✅ Étape 2.1 — récupération Open Agenda (1500 événements Paris, multi-agendas)
- ⏳ Étape 2.2/2.3 — nettoyage/structuration + tests unitaires
- ⏳ Étapes 3 à 6 — index FAISS, chaîne RAG, API, conteneurisation
