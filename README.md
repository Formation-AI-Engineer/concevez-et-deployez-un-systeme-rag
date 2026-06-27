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

# Construire l'index vectoriel FAISS (étape 3)                          [disponible]
uv run python scripts/build_index.py

# Recherche sémantique en CLI dans l'index FAISS (test / démo)          [disponible]
uv run python scripts/search.py "concert de jazz" -k 5

# Lancer l'API REST (étape 5) — voir section dédiée ci-dessous          [disponible]
uv run uvicorn api.main:app --reload             # → Swagger : http://localhost:8000/docs

# Évaluer la qualité des réponses (étape 4/5)                            [disponible]
uv run python scripts/evaluate_rag.py            # options : --sample N, --no-ragas
```

## Lancer l'API REST

L'API expose le système RAG en HTTP. Elle peut être lancée **seule**, à condition que l'index
FAISS existe et que la clé Mistral soit configurée.

**Prérequis**
1. Dépendances installées : `uv sync` (cf. *Installation*).
2. Secrets dans `.env.local` : au minimum `MISTRAL_API_KEY` (génération des réponses).
   Optionnel : `API_REBUILD_TOKEN` pour activer l'endpoint `/rebuild`.
3. **Index FAISS construit** (sinon `/health` répond `degraded` et `/ask` renvoie `503`) :
   ```bash
   uv run python scripts/build_index.py        # crée vectorstore/index/
   ```

**Démarrage**
```bash
uv run uvicorn api.main:app --reload           # http://127.0.0.1:8000
```
La documentation interactive **Swagger** est servie sur <http://127.0.0.1:8000/docs>
(la racine `/` y redirige automatiquement).

**Endpoints**

| Méthode & route | Description |
|---|---|
| `GET /health`   | État du service + nombre d'événements indexés |
| `POST /ask`     | `{ "question": "..." }` → `{ "question", "answer", "sources": [...] }` |
| `POST /rebuild` | Reconstruit l'index FAISS (protégé par jeton `X-API-Token`) |

**Exemples**
```bash
# État du service
curl http://127.0.0.1:8000/health

# Poser une question
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Quels concerts de jazz puis-je voir à Paris ?"}'

# Reconstruire l'index (nécessite API_REBUILD_TOKEN dans .env.local)
curl -X POST http://127.0.0.1:8000/rebuild -H "X-API-Token: <votre-jeton>"
```

> **Codes d'erreur** : `422` question vide ou champ manquant · `503` assistant non chargé
> (index absent) · `401` jeton `/rebuild` invalide · `500` erreur de génération (le détail est
> journalisé côté serveur, jamais renvoyé au client).

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
- ✅ Étape 2 — récupération Open Agenda (1500 événements Paris, multi-agendas), nettoyage/structuration + tests unitaires
- ✅ Étape 3 — chunking (4146 chunks), embeddings HuggingFace locaux, index FAISS persistant + tests de recherche
- ✅ Étape 4 — chaîne RAG LangChain (FAISS + Mistral), gating de pertinence, jeu de test annoté, évaluation (métriques locales + Ragas)
- ✅ Étape 5 — API REST FastAPI (`/ask`, `/rebuild` protégé, `/health`, Swagger) + tests fonctionnels (78 tests OK)
- ⏳ Étape 6 — conteneurisation Docker & démo
