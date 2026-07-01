# Étape 6 — Conteneurisez, déployez localement et préparez votre démonstration

## Objectif
Rendre l'ensemble du système **exécutable localement via Docker** et **présentable** lors de la soutenance :
endpoint API exposé dans un conteneur + démo live + présentation structurée pour les parties prenantes métier.

## Prérequis (énoncé)
- Tous les scripts (pré-processing, vectorisation, API) **fonctionnels**.
- Environnement bien configuré (`README`, dépendances).
- Système RAG **testé de bout en bout**.

## Résultats attendus (énoncé)
- Un **script de build** de l'index vectoriel (`scripts/build_index.py` — étape 3).
- Un **Dockerfile** permettant de **builder et run l'API en local**.
- Une **démo live fluide** : question posée → réponse retournée.
- Une **présentation PowerPoint (10–15 slides)** : objectif/contexte, architecture (conteneurisation + API),
  données & modèles, résultats & évaluation, perspectives.

## Tâches

### 6.1 Conteneurisation
- [x] `Dockerfile` (`python:3.11-slim`, deps API via `uv sync --no-dev`, copie code + index, `uvicorn`)
- [x] `.dockerignore` (exclut `.venv`, `data/raw`, notebooks, PDF/docx, caches, secrets `.env*`…)
- [x] Stratégie d'**index** retenue : **index pré-construit copié dans l'image** (+ modèle d'embeddings
      pré-téléchargé au build) → démarrage **hors-ligne**, seul `POST /ask` appelle Mistral à la requête.
      Justification : exigence « éviter de dépendre d'une connexion instable » + démo rapide/déterministe.
- [x] `docker build` + `docker run` testés en local : `/health` → `ok` (4076 événements indexés),
      `/ask` retourne une réponse cohérente + sources, Swagger accessible sur le port exposé.
- [x] (Optionnel) `docker-compose.yml` (service `api`, port 8000, `env_file: .env.local`).

### 6.2 Exécution de bout en bout
- [x] Pipeline rejouable : `fetch_events` → `preprocess_events` → `build_index` → API → `/ask` cohérent
      (validé en local ; l'index ainsi produit est celui embarqué dans l'image).
- [x] **Reproductibilité** : build depuis zéro OK (deps `uv` figées via `uv.lock`, secrets injectés au
      run via `--env-file .env.local`, jamais copiés dans l'image).
- [x] **Version locale robuste** : index + modèle d'embeddings embarqués → aucune dépendance réseau au
      démarrage (seule la génération Mistral nécessite une connexion).

> **Notes build / optimisations** :
> - 1re construction : téléchargement de `torch` (CPU) + modèle d'embeddings (~5 min).
> - **PyTorch CPU épinglé** (`torch ... +cpu`, index PyTorch dans `pyproject.toml`) : le projet étant
>   100 % CPU, on n'embarque pas le runtime CUDA → image **3,5 Go** (vs ~11,6 Go avec torch CUDA), build accéléré.
> - Compte non-root `appuser` créé **avant** l'install du venv et du cache HuggingFace : évite un
>   `chown -R` récursif coûteux (plusieurs minutes sur FS overlay) sur ces volumineux artefacts.

### 6.3 Préparation de la démo
- [x] Scénarios validés dans le conteneur :
      - « Quels concerts de jazz puis-je voir à Paris ? » → Jazzycolors, Café Maa…
      - « Une expo de peinture à voir à Paris ? » → Mai-Thu Perret, Akosua V. Adu-Sanyah…
- [ ] (Optionnel) ajouter un 3e scénario (théâtre / hors-périmètre pour illustrer le gating) pour la soutenance.

### 6.4 Rapport technique (livrable)
- [x] Rapport rédigé : [`docs/rapport_technique.md`](rapport_technique.md), suivant le plan en 10
      sections du template `Template+de+rapport+technique.docx` (objectifs, architecture, données &
      vectorisation, modèle NLP, base vectorielle, API, évaluation chiffrée, perspectives, dépôt, annexes).
      → À exporter en PDF / reverser dans le `.docx` pour le rendu final si exigé.

### 6.5 Présentation (soutenance)
- [x] PowerPoint **16 slides** ([`docs/presentation.pptx`](presentation.pptx)), structuré selon le
      cadrage de soutenance : déroulé → système RAG → **démo de l'API** → rapport & résultats →
      **structure du dépôt & scripts** → reproductibilité → perspectives → discussion. ~15 min (fenêtre
      10–20). Généré de façon reproductible par
      [`scripts/build_presentation.py`](../scripts/build_presentation.py) (charte reprise du Projet 8).
      Régénération : `uv run --extra dev python scripts/build_presentation.py`.
- [x] Slide dédiée « Qu'est-ce qu'un RAG ? » en **explication métier** simple (sans jargon).
- [x] Notes orateur sur les slides clés ; perspectives/limites anticipant les **questions**
      (choix modèle/archi, évaluation, industrialisation).

## Points de vigilance (énoncé)
- Tester l'**exécution complète**.
- Éviter de dépendre d'une **connexion instable** → version locale prête.
- Vérifier que toutes les **dépendances** sont installées et compatibles.
- Présentation **sans jargon inutile**, compréhensible par profils techniques **et** non techniques.

## Outils & ressources
- Docker (+ Docker Compose facultatif), FastAPI (Swagger UI), Postman/curl/navigateur.
- PowerPoint / Google Slides, GitHub pour le versioning.

## Statut : QUASI TERMINÉE
- ✅ 6.1 Conteneurisation (Dockerfile + `.dockerignore` + `docker-compose.yml`), build & run validés.
- ✅ 6.2 Exécution de bout en bout reproductible, version locale hors-ligne.
- ✅ 6.3 Démo : 2 scénarios validés dans le conteneur (3e optionnel pour la soutenance).
- ✅ 6.4 Rapport technique rédigé ([`rapport_technique.md`](rapport_technique.md)).
- ✅ 6.5 Présentation de soutenance générée ([`presentation.pptx`](presentation.pptx), 16 slides,
  alignée sur le cadrage de soutenance : livrables 15 min + axes de discussion).
