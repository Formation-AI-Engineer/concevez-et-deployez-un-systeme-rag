# Contexte général — Projet 7

## Sujet
**Concevez et déployez un système RAG** — *Développez un assistant pour la recommandation d'évènements
culturels* (OpenClassrooms, parcours AI Engineer).

## Mission (résumé de l'énoncé)
Vous êtes **data scientist freelance**, spécialisé en NLP et systèmes intelligents. Vous intervenez pour
**Puls-Events**, une entreprise tech qui développe une plateforme de **recommandations culturelles
personnalisées**.

Message de **Jérémy** (responsable technique) :
> « On a besoin que tu finalises une version fonctionnelle du POC pour notre assistant intelligent.
> L'objectif est de démontrer aux équipes produit et marketing que notre plateforme peut intégrer un
> chatbot capable de répondre aux questions des utilisateurs en s'appuyant sur les données d'événements
> disponibles via l'API Open Agenda. »

Livrable : un **POC complet** démontrant la **faisabilité technique**, la **pertinence métier** et la
**performance** du système, avec une **API exploitable** par les équipes produit et marketing.

## Périmètre du POC
- **Zone géographique** : libre (au choix) → **Paris** retenu par défaut (modifiable via `.env`).
- **Période** : événements **récents (< 1 an)** et **à venir** (1 an d'historique + futur).
- **Pas d'historique de conversation** nécessaire dans le POC (chaque question est indépendante).

## Stack technique imposée / pressentie (à justifier en soutenance)
- **Orchestration** : **LangChain**.
- **LLM (génération)** : **Mistral** (API, modèle choisi sur la plateforme Mistral).
- **Base vectorielle** : **FAISS** (`faiss-cpu` privilégié pour la portabilité).
- **Embeddings** : modèle NLP via **HuggingFace** (`sentence-transformers`, multilingue) exécuté en local.
- **Source de données** : **API Open Agenda**.
- **Manipulation des données** : **pandas**.
- **API REST** : **FastAPI** (recommandé pour Swagger) ou Flask.
- **Évaluation** : **Ragas** + jeu de test annoté (questions/réponses de référence).
- **Conteneurisation** : **Docker** (exécution locale pour la démo).

## Livrables attendus (énoncé)
1. **Système RAG fonctionnel** intégrant LangChain + Mistral + FAISS, avec **scripts de reconstruction de
   l'index** à partir des données.
2. **API REST** (FastAPI/Flask) : envoyer une question → recevoir une réponse augmentée. Endpoints `/ask`
   (POST) et `/rebuild` (reconstruction de la base à la demande).
3. **Rapport technique** (PDF ou README) : architecture, choix technologiques, modèles, résultats,
   pistes d'amélioration (template fourni : `Template+de+rapport+technique.docx`).
4. **Jeu de test annoté** (questions/réponses de référence) pour mesurer la qualité.
5. **Tests unitaires** : indexation des données + performances + automatisation des métriques d'évaluation.
6. **Dockerfile** : image exécutable en local pour la démo.
7. **Présentation PowerPoint** (10–15 slides) + **démo live** de l'API pour la soutenance.

## Critère de qualité d'une réponse (énoncé)
> Une réponse IA est correcte si elle a **le même sens** et contient **les mêmes informations** que la
> réponse annotée par l'humain.

Métriques possibles : score de **similarité**, **Exact Match**, classification manuelle
(*correcte / partiellement correcte / incorrecte*), et métriques **Ragas** (pertinence, fidélité au
contexte, couverture documentaire) intégrables en CI.

## Points de vigilance transverses
- **Ne jamais versionner la clé d'API** Mistral / Open Agenda → variable d'environnement / `.env` ignoré.
- Vérifier la **compatibilité des versions** (notamment FAISS ⇄ LangChain).
- **Séparer** la logique métier (RAG) du code d'API.
- **Charger les ressources lourdes une seule fois** (index FAISS, modèle d'embeddings) au démarrage de l'API.
- Soigner les **métadonnées** des événements indexés (dates, lieux, descriptions).
- Gérer les **erreurs** (questions vides, mauvaise requête) et **protéger** les endpoints sensibles (`/rebuild`).
- Préparer une **version locale** pour la démo (pas de dépendance à une connexion instable).
- Soigner les **données manquantes / incorrectes** d'Open Agenda lors du pré-processing.

## Soutenance (rappel)
30 min : présentation des livrables (15 min, dont démo live de l'API), discussion (10 min, l'évaluateur
joue Jérémy), débrief (5 min). Challenge attendu sur : choix de modèle/architecture, qualité des
embeddings, évaluation des performances, limites, reproductibilité / industrialisation / usage métier.
