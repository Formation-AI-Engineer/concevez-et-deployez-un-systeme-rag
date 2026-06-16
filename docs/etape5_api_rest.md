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

### 5.1 Application FastAPI
- [ ] Module `api/main.py` : instance FastAPI + métadonnées (titre, description, version)
- [ ] **Chargement au démarrage** (`lifespan`) de l'index FAISS + assistant RAG **une seule fois** (pas par requête)
- [ ] Séparer **logique métier** (`rag/`) du **code d'API** (`api/`) — l'API importe `RAGAssistant`

### 5.2 Endpoints
- [ ] `GET /` → redirection vers Swagger (`/docs`) ; `GET /health` → état du service
- [ ] `POST /ask` : corps `{ "question": "..." }` → `{ "answer": "...", "sources": [...] }`
  - [ ] Schéma d'entrée/sortie **Pydantic** (`AskRequest` / `AskResponse`)
  - [ ] Inclure les **sources** (titre, date, lieu, URL) dans la réponse
- [ ] `POST /rebuild` : reconstruit l'index FAISS depuis `data/processed/` et recharge l'assistant
  - [ ] **Protéger** l'endpoint sensible (clé/token simple, même pour un POC)

### 5.3 Gestion des erreurs
- [ ] Question **vide** / champ manquant → `422` (validation Pydantic)
- [ ] Erreur d'inférence / LLM indisponible → `500` avec message clair
- [ ] Ne **jamais exposer** d'informations sensibles (clés d'API) dans les réponses/erreurs

### 5.4 Tests fonctionnels (énoncé)
- [ ] `tests/test_api.py` (via `httpx` / `TestClient`) :
  - [ ] `/health` répond `200`
  - [ ] `/ask` avec question valide → `200` + champ `answer` non vide
  - [ ] `/ask` avec question vide → `422`
  - [ ] (mock LLM/retriever pour des tests rapides et déterministes)

### 5.5 Évaluation automatisée (énoncé — Ragas en CI)
- [ ] `scripts/evaluate_rag.py` (étape 4.4) intégrable dans un pipeline (script / GitHub Actions)
- [ ] (Optionnel) workflow `.github/workflows/ci.yml` : `pytest` + lint `ruff` + évaluation Ragas

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

## Statut : À FAIRE
