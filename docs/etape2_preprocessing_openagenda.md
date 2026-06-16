# Étape 2 — Effectuez le pré-processing des données Open Agenda

## Objectif
Récupérer les données d'événements depuis l'**API Open Agenda**, les **filtrer** par localisation et période,
et les **structurer** (nettoyage + format propre) pour une indexation future dans la base vectorielle.

## Prérequis (énoncé)
- Avoir un accès à l'**API Open Agenda** (clé publique).
- Avoir défini les **paramètres de filtrage** : ville, période, type d'événement.

## Résultat attendu (énoncé)
- Un jeu de données d'événements **propre et structuré**, prêt à être indexé.
- Des **tests unitaires** assurant que les données attendues ont bien été récupérées.

## Tâches

### 2.1 Récupération des données (API Open Agenda)
- [ ] Module `rag/data_loader.py` : client de l'API Open Agenda (auth par `OPENAGENDA_API_KEY`)
- [ ] Script CLI `scripts/fetch_events.py` : télécharge les événements → `data/raw/events.json`
- [ ] Gérer la **pagination** de l'API (récupérer l'ensemble des événements de la zone)
- [ ] Filtrer par **localisation** (`EVENTS_CITY`, ex. Paris) et **période** (1 an d'historique + à venir, `< 1 an`)
- [ ] (Optionnel) filtrer par **type d'événement** si pertinent pour la démo

### 2.2 Nettoyage et structuration (pandas)
- [ ] Module `rag/preprocessing.py` : nettoyage + normalisation → DataFrame structuré
- [ ] Sélection des **champs utiles** : titre, description, **date(s)**, **lieu**, ville, catégorie, URL
- [ ] Gestion des **données manquantes / incorrectes** (descriptions vides, dates invalides → filtrées/imputées)
- [ ] Construction d'un **texte d'événement** consolidé (titre + description + lieu + dates) pour la vectorisation
- [ ] Conservation des **métadonnées** (date, lieu, catégorie, URL) à attacher à chaque document
- [ ] Export propre → `data/processed/events.parquet` (+ aperçu CSV éventuel)

### 2.3 Tests unitaires (énoncé)
- [ ] `tests/test_preprocessing.py` : schéma de sortie attendu (colonnes présentes, types corrects)
- [ ] Test du **filtrage période** (aucun événement > 1 an d'ancienneté)
- [ ] Test du **filtrage localisation** (tous les événements dans la zone ciblée)
- [ ] Test de la **gestion des valeurs manquantes** (pas de description/date nulle dans la sortie)

## Points de vigilance (énoncé)
- Attention aux **données manquantes ou incorrectes**.
- Vérifier la **pertinence des filtres** (événements bien ciblés sur zone + période).
- La **conversion en vecteurs** (Mistral / embeddings) intervient à l'étape 3 — ici on prépare le texte propre.

## Outils & ressources
- API Open Agenda ([documentation](https://developers.openagenda.com/)), `requests`, `pandas`.
- Modèle NLP (embeddings) pour la vectorisation → étape 3.

## Statut : À FAIRE
