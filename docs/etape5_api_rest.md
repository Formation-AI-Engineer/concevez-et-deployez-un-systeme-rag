# Étape 5 — Créez une API pour exposer le système RAG

## Objectif
Rendre le système RAG accessible via une **API REST** : les équipes métier posent une question via un appel
HTTP et reçoivent une **réponse augmentée** générée par le système. Possibilité de **reconstruire** la base
vectorielle.

## Prérequis (énoncé)
- Système RAG opérationnel sous forme de **classe / fonction** (étape 4, `RAGAssistant`).
- Maîtrise d'un framework d'API Python (FastAPI ou Flask) + bases des routes HTTP (GET/POST).

## Résultats attendus (énoncé)
- Une **API REST locale** exposant le système RAG.
- Endpoint **`/ask` (POST)** : prend une question → renvoie une réponse générée.
- Endpoint **`/rebuild` (GET ou POST)** : reconstruit la base vectorielle à la demande.
- **Documentation Swagger** générée automatiquement (FastAPI).
- Un **test fonctionnel** de l'API (`tests/api_test.py` ou équivalent).

## Tâches

### 5.1 Application FastAPI ✅
- [x] Module `api/main.py` : instance FastAPI + métadonnées (titre, description, version 1.0.0)
- [x] **Chargement au démarrage** (`lifespan`) de l'index FAISS + assistant RAG **une seule fois**, rangé dans `app.state` (démarrage gracieux si index absent → `/health` `degraded`)
- [x] Logique métier (`rag/`) séparée du code d'API (`api/`) ; schémas Pydantic isolés dans `api/schemas.py` ; l'API importe `RAGAssistant`

### 5.2 Endpoints ✅
- [x] `GET /` → redirection vers Swagger (`/docs`) ; `GET /health` → état du service + nb d'événements indexés
- [x] `POST /ask` : corps `{ "question": "..." }` → `{ "question", "answer", "sources": [...] }`
  - [x] Schémas **Pydantic** `AskRequest` / `AskResponse` (+ `SourceEvent`) dans `api/schemas.py`
  - [x] **Sources** (uid, titre, date, lieu, URL) incluses ; **dédoublonnées par uid** (chunking) et lieu nettoyé ("Paris Paris" → "Paris")
- [x] `POST /rebuild` : reconstruit l'index FAISS (`build_and_save`) depuis `data/processed/` et recharge l'assistant dans `app.state`
  - [x] **Protégé** par jeton `API_REBUILD_TOKEN` (en-tête `X-API-Token`, comparaison à temps constant) ; désactivé si non configuré

### 5.3 Gestion des erreurs ✅
- [x] Question **vide** / champ manquant → `422` (validation Pydantic + `field_validator`)
- [x] Erreur d'inférence / LLM indisponible → `500` avec message **générique** (détail journalisé côté serveur uniquement)
- [x] Aucune info sensible exposée ; assistant non chargé → `503` ; jeton invalide → `401`

### 5.4 Tests fonctionnels (énoncé) ✅
- [x] `tests/test_api.py` (via `TestClient`, assistant **mocké** → rapide et déterministe) :
  - [x] `/health` `200` (ok / degraded) ; `/` redirige vers `/docs`
  - [x] `/ask` question valide → `200` + `answer` non vide + sources dédoublonnées
  - [x] `/ask` question vide / champ manquant → `422` ; sans assistant → `503` ; erreur LLM → `500` sans fuite
  - [x] `/rebuild` : désactivé sans jeton → `503` ; jeton manquant → `401` ; jeton valide → `200`

### 5.5 Évaluation automatisée (énoncé — Ragas en CI) ✅
- [x] Workflow `.github/workflows/ci.yml` — job **`quality`** (push/PR) : `ruff check .` + `pytest` via `uv`, avec cache des modèles HuggingFace
- [x] `scripts/evaluate_rag.py` intégré dans un job **`evaluate`** (déclenchement manuel `workflow_dispatch`) : **pipeline complet** `fetch_events` → `preprocess_events` → `build_index` → évaluation sur échantillon, secrets `OPENAGENDA_API_KEY` + `MISTRAL_API_KEY`, rapport publié en artefact
- [x] Job `evaluate` **non bloquant** (`continue-on-error`) + garde si les secrets sont absents — le job `quality` reste le cœur exécuté à chaque commit
- ⚠️ Le job récupère un **instantané frais réduit** (≈300 événements) : distinct de l'index local sur lequel `qa_dataset.json` est ancré → les métriques de couverture/ancrage peuvent différer du run local (le job valide surtout l'exécution **de bout en bout** + métriques sémantiques/Ragas)
- 💡 `workflow_dispatch` n'est disponible **que depuis la branche par défaut** (`main`) : le workflow doit y être présent pour que le bouton « Run workflow » apparaisse
- ℹ️ Prérequis CI vérifié : aucun test n'exige de clé Mistral (assistant mocké / `FakeListChatModel`) ni l'index réel (tests `skipif` index absent) → la CI passe sans secret

## Points de vigilance (énoncé)
- **Séparer** logique métier et code d'API ; **documenter** chaque route (entrées/sorties).
- Tirer parti de **Swagger** (`/docs`) auto-généré par FastAPI.
- **Réutilisabilité** : système encapsulé dans une classe/fonction centrale importée par l'API.
- Gérer les **erreurs** (questions vides, mauvaise requête).
- Ne pas laisser de **clé d'API** exposée ; **protéger** `/rebuild`.
- **Performances** : ne pas relancer toute la chaîne (chargement index/modèle) à chaque appel.

## Outils & ressources
- FastAPI + Uvicorn (Swagger UI auto), Pydantic, `httpx` (tests), Ragas (évaluation).
- [FastAPI Quickstart](https://fastapi.tiangolo.com/), [Ragas](https://docs.ragas.io/).

## Statut : FAIT (5.1 API, 5.2 endpoints, 5.3 erreurs, 5.4 tests, 5.5 CI lint+tests+éval)
