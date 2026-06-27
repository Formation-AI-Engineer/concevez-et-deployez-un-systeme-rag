# Problèmes, contraintes & questions pour le mentor

Journal des difficultés, contraintes et décisions rencontrées pendant le projet, à présenter en
session de mentorat. Classé par nature. Les **questions ouvertes** (à trancher avec le mentor) sont
regroupées en fin de document.

---

## 1. Contraintes externes (API / plateformes)

### 1.1 Open Agenda — recherche globale d'événements bloquée (HTTP 403)
- **Constat** : l'endpoint `GET /v2/events` (recherche transverse de tous les événements, ex. par ville)
  renvoie `403 — "Not authorized, contact support@openagenda.com to request access."`.
- **Nature** : **contrainte Open Agenda** (niveau d'accès de la clé publique), **pas** un choix de projet.
  L'accès transverse nécessite une autorisation spécifique à demander au support.
- **Contournement** : stratégie **par agenda** — `GET /v2/agendas` (recherche d'agendas) puis
  `GET /v2/agendas/{uid}/events` (accessibles avec la clé publique), filtrés par date.
- **Impact** : on ne couvre pas « tous les événements de Paris » mais un sous-ensemble issu des agendas
  ciblés (voir §4 qualité des données).

### 1.2 Open Agenda — la recherche d'agendas matche le titre, pas la localisation
- **Constat** : `GET /v2/agendas?search=Paris` renvoie les agendas dont le **titre/description** contient
  « Paris » (ex. « Université Paris-Saclay », dont les événements sont à Orsay/Sèvres), pas les agendas
  dont les **événements** sont à Paris.
- **Contournement** : **re-filtrage** des événements sur `location.city` (Paris) après récupération.

### 1.3 Open Agenda — pagination des agendas non standard (bug rencontré)
- **Constat** : le paramètre `offset` est **ignoré** par `/v2/agendas` → chaque page renvoyait les
  **mêmes 20 agendas** (doublons), réduisant la diversité réelle des sources.
- **Résolu** : pagination via le **cursor `after`** (comme pour les événements) + dédoublonnage par `uid`.
  (Détecté car chaque agenda apparaissait 3× dans les logs ; corrigé puis re-récupération.)

---

## 2. Écarts par rapport à l'énoncé (à justifier)

### 2.1 Imports de l'énoncé obsolètes / erronés
Le snippet d'imports de l'énoncé ne fonctionne pas avec les versions actuelles :
| Import de l'énoncé | Problème | Correction utilisée |
|---|---|---|
| `from langchain.vectorstores import FAISS` | chemin obsolète | `from langchain_community.vectorstores import FAISS` |
| `from langchain.embeddings import HuggingFaceEmbeddings` | déplacé | `from langchain_huggingface import HuggingFaceEmbeddings` |
| `from mistral import MistralClient` | paquet inexistant | `from langchain_mistralai import ChatMistralAI` |
- Détail dans `docs/etape1` (§1.2). Vérif reproductible : `scripts/check_imports.py`.

### 2.2 SDK Mistral — packaging inattendu
- `from mistralai import Mistral` échoue (`mistralai` 2.4.9 est un *namespace package*) ; le bon chemin est
  `from mistralai.client import Mistral`. Sans impact projet : on passe par `ChatMistralAI` (LangChain).

### 2.3 Embeddings : HuggingFace plutôt que Mistral
- **Énoncé** : « Convertir les descriptions en format vectoriel avec un modèle de NLP **comme Mistral** ».
- **Choix** : embeddings **HuggingFace** (`sentence-transformers` multilingue) exécutés **en local**.
- **Justification** : gratuit, reproductible hors-ligne, pas de quota/coût API pour vectoriser 1500+ chunks,
  bon support du français. Mistral reste utilisé pour la **génération** (le LLM du RAG).
- ⚠️ À valider avec le mentor (cf. question Q2).

### 2.4 `langchain-community` en voie de dépréciation
- Avertissement à l'import : `langchain-community` « is being sunset ». `FAISS` y vit encore et fonctionne ;
  à surveiller pour une éventuelle migration vers un paquet d'intégration dédié.

---

## 3. Outillage / environnement

- **Extraction des PDF de l'énoncé** : pas de `pdftotext`/poppler sur la machine ; texte extrait via
  `uvx --with pypdf` (sans impact projet).
- **Secrets** : clés mises dans `.env.local` (et non `.env`) → `rag/config.py` charge `.env.local` en
  priorité puis `.env`. Les deux sont ignorés par Git.

---

## 4. Qualité des données récupérées

- **Volume** : 1500 événements uniques, 100 % localisés à Paris, issus de 16 agendas.
- **Biais thématique** : la recherche « Paris » fait remonter beaucoup d'agendas religieux (Diocèse de Paris,
  paroisses, musique sacrée…) → ~1/3 du jeu. Atténué par un **plafond par agenda** (`--per-agenda-max 300`)
  pour diversifier (Vie parisienne, instituts culturels FICEP, jazz, agenda littéraire, cinéma…).
- **Données manquantes** : 7 événements sans aucune description (à filtrer/gérer au pré-processing 2.2).
- **Normalisation** : la ville apparaît sous plusieurs formes (`Paris`, `paris`, `Paris 14`) → filtrage
  insensible à la casse/accents + gestion des arrondissements.

---

## 5. Questions ouvertes pour le mentor

- **Q1 — Accès API** : faut-il demander à Open Agenda l'accès à la recherche globale `/v2/events`, ou la
  stratégie par agendas est-elle suffisante et acceptable pour un POC ?
- **Q2 — Embeddings** : HuggingFace local (choisi) vs embeddings Mistral (suggéré par l'énoncé) — le choix
  est-il validé ? Faut-il au moins benchmarker les deux ?
- **Q3 — Représentativité** : le biais thématique (forte part d'événements religieux) est-il gênant pour la
  démo « assistant culturel » ? Faut-il curer manuellement une liste d'agendas plus culturels ?
- **Q4 — Volume** : 1500 événements est-il un bon ordre de grandeur pour le POC (indexation, démo) ?
- **Q5 — Périmètre** : Paris uniquement est-il suffisant, ou faut-il prévoir plusieurs villes ?
- **Q6 — Fenêtre temporelle** : on prend 12 mois d'historique + tous les événements à venir ; faut-il borner
  le futur (ex. 3 mois) pour rester pertinent ?
