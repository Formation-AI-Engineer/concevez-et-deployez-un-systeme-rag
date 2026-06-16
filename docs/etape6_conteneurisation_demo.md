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
- [ ] `Dockerfile` (`python:3.11-slim`, install des deps API, copie code + index, lancement `uvicorn`)
- [ ] `.dockerignore` (exclut `.venv`, `data/raw`, notebooks, PDF, caches…)
- [ ] Décider de la stratégie d'**index** : index pré-construit copié dans l'image **ou** build au démarrage
- [ ] `docker build` + `docker run` testés en local (Swagger + `/ask` accessibles sur le port exposé)
- [ ] (Optionnel) `docker-compose.yml` pour simplifier le lancement

### 6.2 Exécution de bout en bout
- [ ] Pipeline complet rejoué : `fetch_events` → `build_index` → API → `/ask` retourne une réponse cohérente
- [ ] Vérifier la **reproductibilité** (install propre + clés `.env`)
- [ ] Préparer une **version locale** robuste (pas de dépendance à une connexion instable pour la démo)

### 6.3 Préparation de la démo
- [ ] Préparer **2–3 scénarios d'usage réalistes** (ex. « Quels événements jazz à Paris cette semaine ? »)
- [ ] Vérifier que les réponses sont fluides et pertinentes sur ces scénarios

### 6.4 Rapport technique (livrable)
- [ ] Rapport (PDF/README) à partir du template `Template+de+rapport+technique.docx` :
      architecture, choix technologiques, modèles utilisés, résultats observés, pistes d'amélioration

### 6.5 Présentation (soutenance)
- [ ] PowerPoint 10–15 slides : problème → solution → résultats → perspectives
- [ ] Préparer une **explication métier** simple de ce qu'est un système RAG
- [ ] Anticiper les **questions** : choix modèle/archi, qualité embeddings, évaluation, limites, industrialisation

## Points de vigilance (énoncé)
- Tester l'**exécution complète**.
- Éviter de dépendre d'une **connexion instable** → version locale prête.
- Vérifier que toutes les **dépendances** sont installées et compatibles.
- Présentation **sans jargon inutile**, compréhensible par profils techniques **et** non techniques.

## Outils & ressources
- Docker (+ Docker Compose facultatif), FastAPI (Swagger UI), Postman/curl/navigateur.
- PowerPoint / Google Slides, GitHub pour le versioning.

## Statut : À FAIRE
