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

## Stratégie de récupération (validée par exploration API — `scripts/explore_openagenda.py`)
Exploration réelle de l'API v2 avec la clé du projet :
- ❌ **Recherche globale d'événements** `/v2/events` → **HTTP 403** (accès restreint sur cette clé) : on ne
  peut pas requêter d'un coup tous les événements d'une ville.
- ✅ **Recherche d'agendas** `/v2/agendas?search=Paris` → OK (4755 agendas ; le terme matche le *titre* de
  l'agenda, ex. « Diocèse de Paris », pas la localisation des événements).
- ✅ **Événements d'un agenda** `/v2/agendas/{uid}/events` → OK, filtrable par date (`timings[gte]` /
  `timings[lte]`), `detailed=1`, pagination ; champs riches : `title`, `description`, `longDescription`,
  `location` (name, city, latitude, longitude), `timings`, `dateRange`, `categories`, `keywords`, `links`…

**Décision** : récupération **par agenda(s)** ciblé(s) sur la zone (Paris) + filtre par date, puis
**re-filtrage par `location.city`** au pré-processing pour ne garder que les événements réellement parisiens.
Choix de l'agenda/des agendas source(s) → cf. tâche 2.1 (à confirmer).

## Tâches

### 2.1 Récupération des données (API Open Agenda)
- [x] Exploration API + validation de la stratégie par agendas (`scripts/explore_openagenda.py`)
- [x] Module `rag/data_loader.py` : client `OpenAgendaClient` (auth `OPENAGENDA_API_KEY`, retries 429/5xx)
- [x] Script CLI `scripts/fetch_events.py` : multi-agendas Paris → `data/raw/events.json` (paramétrable : `--city`, `--target-events`, `--per-agenda-max`…)
- [x] **Pagination** via cursor `after` pour les événements **et** les agendas (l'`offset` est ignoré par `/agendas` — corrigé)
- [x] Filtrage **localisation** (`location.city`, arrondissements « Paris 14 » captés) + **période** (`timings[gte]` = aujourd'hui − 12 mois, + à venir)
- [x] Dédoublonnage par `uid` + plafond par agenda (`--per-agenda-max 300`) pour la diversité thématique
- [N/A] Filtrage par **type d'événement** : non appliqué (on garde toutes les catégories pour un assistant culturel généraliste)
- [x] **Résultat** : 1500 événements uniques, 16 agendas sources, 100 % localisés à Paris (`data/raw/events.json`)

### 2.2 Nettoyage et structuration (pandas)
- [x] Module `rag/preprocessing.py` : résolution multilingue (fr) + nettoyage HTML/entités/espaces → DataFrame
- [x] Sélection des **champs utiles** (20 colonnes) : `title`, `description`, `long_description`, `keywords`, `date_range`, `date_start/end/next`, `location_name`, `address`, `city`, `postal_code`, `latitude/longitude`, `agenda_uid/title`, `slug`, `url`
- [x] Gestion des **données manquantes** : champs vides → `""`, suppression des événements sans contenu (ni titre ni description), dédoublonnage par `uid`
- [x] Construction d'un **texte consolidé** (`document`) : titre + description + long. desc. + « Quand » + « Lieu » + mots-clés (médiane ~1028 caractères)
- [x] Métadonnées (date, lieu, coordonnées, agenda) conservées comme colonnes → attachables au `Document` LangChain (étape 3)
- [x] Export → `data/processed/events.parquet` (1500 × 20) via `scripts/preprocess_events.py`

### 2.3 Tests unitaires (énoncé)
- [x] `tests/test_preprocessing.py` : tests **purs** (fixtures) — résolution multilingue, nettoyage HTML/entités/espaces, schéma de sortie, texte consolidé, dédoublonnage, suppression des événements sans contenu
- [x] `tests/test_fetch_events.py` : **filtrage localisation** — normalisation casse/accents, correspondance ville + arrondissements (« Paris 14 »), rejet des communes proches (« Parisot »)
- [x] `tests/test_dataset.py` : validation du **parquet réellement produit** (ignoré si absent) — schéma/types, **période** (`date_end` ≥ borne `since`, ancrée sur la méta du JSON brut), **localisation** (toutes les villes dans la zone), **valeurs manquantes** (document non vide, `date_start`/`uid` présents, `uid` unique)
- [x] **Bug corrigé** au passage : `localized({})` renvoyait `"{}"` (dict multilingue vide) → injectait du bruit dans 642 documents ; corrigé en `""`, parquet régénéré (médiane doc 1028 → 983 car.)
- [x] Outillage : `conftest.py` (racine importable) + `scripts/__init__.py` ; **27 tests passent** (`uv run pytest`)

## Points de vigilance (énoncé)
- Attention aux **données manquantes ou incorrectes**.
- Vérifier la **pertinence des filtres** (événements bien ciblés sur zone + période).
- La **conversion en vecteurs** (Mistral / embeddings) intervient à l'étape 3 — ici on prépare le texte propre.

## Outils & ressources
- API Open Agenda ([documentation](https://developers.openagenda.com/)), `requests`, `pandas`.
- Modèle NLP (embeddings) pour la vectorisation → étape 3.

## Statut : TERMINÉ
