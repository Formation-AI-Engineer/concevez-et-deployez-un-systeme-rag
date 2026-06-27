# Fiche de suivi — Projet 7

**Sujet** : Concevez et déployez un système RAG — Assistant de recommandation d'événements culturels
**Finalité** : POC d'un système **RAG** (LangChain + Mistral + FAISS) exposé via une **API REST**, conteneurisé
avec Docker, pour **Puls-Events**.
**Structure officielle** : 6 étapes de l'énoncé OpenClassrooms.
**Source de données** : API **Open Agenda** (zone au choix — Paris par défaut ; événements < 1 an + à venir).

## Documents du projet

| Document | Description |
|----------|-------------|
| [`contexte_general.md`](contexte_general.md) | Contexte métier, mission Jérémy, stack, livrables, vigilance |
| [`points_mentor.md`](points_mentor.md) | Problèmes, contraintes & questions rencontrés (à présenter au mentor) |
| [`etape1_configuration_environnement.md`](etape1_configuration_environnement.md) | Environnement uv reproductible + imports clés + secrets + structure |
| [`etape2_preprocessing_openagenda.md`](etape2_preprocessing_openagenda.md) | Récupération + filtrage + nettoyage des données Open Agenda |
| [`etape3_base_vectorielle_faiss.md`](etape3_base_vectorielle_faiss.md) | Chunking + embeddings + index FAISS + recherche sémantique |
| [`etape4_integration_langchain_rag.md`](etape4_integration_langchain_rag.md) | Chaîne RAG LangChain + Mistral + jeu de test annoté + évaluation |
| [`etape5_api_rest.md`](etape5_api_rest.md) | API FastAPI (`/ask`, `/rebuild`) + Swagger + tests fonctionnels |
| [`etape6_conteneurisation_demo.md`](etape6_conteneurisation_demo.md) | Dockerfile + run local + rapport + présentation + démo |

## Livrables (énoncé)

| Livrable | Étape | Statut |
|----------|-------|--------|
| Environnement reproductible (uv / `pyproject.toml` + lock) | 1 | [x] |
| `README.md` (objectifs, structure, reproduction) | 1 | [x] |
| Imports clés vérifiés (faiss, langchain, embeddings, Mistral) | 1 | [x] |
| Données Open Agenda récupérées + filtrées (zone + < 1 an) | 2 | [ ] |
| Jeu de données propre et structuré (pandas) | 2 | [ ] |
| Tests unitaires de la récupération / pré-processing | 2 | [ ] |
| Découpage en chunks + embeddings (HuggingFace) | 3 | [ ] |
| Index FAISS persistant + métadonnées (date/lieu/desc.) | 3 | [ ] |
| Script de (re)construction de l'index `build_index.py` | 3 | [ ] |
| Tests de recherche sémantique | 3 | [ ] |
| Chaîne RAG LangChain + Mistral (classe réutilisable) | 4 | [ ] |
| Jeu de test annoté (questions/réponses de référence) | 4 | [ ] |
| Script d'évaluation (similarité / Exact Match / Ragas) | 4 | [ ] |
| API REST FastAPI : `/ask` (POST) + `/rebuild` | 5 | [ ] |
| Swagger auto + gestion des erreurs (question vide…) | 5 | [ ] |
| Test fonctionnel de l'API | 5 | [ ] |
| Automatisation des métriques d'évaluation (script/CI) | 5 | [ ] |
| Dockerfile + image qui build et run en local | 6 | [ ] |
| Démo live fluide (question → réponse) | 6 | [ ] |
| Rapport technique (PDF/README, template fourni) | 6 | [ ] |
| Présentation PowerPoint (10–15 slides) | 6 | [ ] |

## Vision d'ensemble

```
Étape 1 ──► Étape 2 ──────► Étape 3 ──────► Étape 4 ──────────► Étape 5 ──────► Étape 6
   │           │               │               │                    │              │
 env uv +   données          chunks +        chaîne RAG          API REST       Docker +
 imports +  Open Agenda      embeddings +    LangChain +         FastAPI        run local +
 secrets    nettoyées        index FAISS     Mistral + éval.     /ask /rebuild  rapport + démo
```

## Points de vigilance transverses (énoncé)

- **Ne jamais versionner** la clé d'API (Mistral / Open Agenda) → `.env` ignoré par Git.
- **Compatibilité des versions** (FAISS ⇄ LangChain) ; `faiss-cpu` pour la portabilité.
- **Séparer** logique métier (RAG) et code d'API.
- **Charger une seule fois** au démarrage : index FAISS + modèle d'embeddings (perf).
- Stocker les **métadonnées** des événements avec les vecteurs (date, lieu, description).
- Gérer les **données manquantes / incorrectes** d'Open Agenda.
- Gérer les **erreurs** de l'API + **protéger** `/rebuild`.
- Préparer une **version locale** robuste pour la démo.
- Critère qualité réponse : *même sens + mêmes informations* que la référence annotée.

## Stack retenue (à justifier en soutenance)

| Brique | Choix |
|--------|-------|
| Orchestration | LangChain |
| LLM | Mistral (API) |
| Embeddings | `sentence-transformers` multilingue (HuggingFace, local) |
| Base vectorielle | FAISS (`faiss-cpu`) |
| Données | API Open Agenda + pandas |
| API | FastAPI + Uvicorn |
| Évaluation | Ragas + jeu de test annoté |
| Conteneur | Docker |
| Gestion d'env | uv |
