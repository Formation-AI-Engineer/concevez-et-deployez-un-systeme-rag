# Étape 3 — Implémentez la base de données vectorielle avec Faiss

## Objectif
Indexer les descriptions des événements sous forme de **vecteurs** dans une base **FAISS**, permettant une
**recherche sémantique rapide** par similarité.

## Prérequis (énoncé)
- Avoir nettoyé les données Open Agenda (étape 2).
- Avoir **découpé les textes en chunks** avant la vectorisation.

## Résultat attendu (énoncé)
- Une base **FAISS** contenant les événements indexés en fonction de leurs vecteurs sémantiques.
- Les **métadonnées** des événements (dates, lieux, descriptions) stockées avec les vecteurs.

## Tâches

### 3.1 Découpage en chunks
- [x] Module `rag/chunking.py` : `RecursiveCharacterTextSplitter` (LangChain), `CHUNK_SIZE` / `CHUNK_OVERLAP` (`.env`)
- [x] Conversion des événements en `Document` LangChain : `page_content` (texte) + `metadata` (date, lieu, catégorie, URL, id)
- [x] Stratégie : 1 événement = 1+ chunks selon la longueur de la description (`uid` + `chunk`/`n_chunks` en métadonnée)
- [x] **Résultat** : 1500 événements → **4076 chunks** (~2.72/événement) ; 100 % des `uid` couverts

### 3.2 Embeddings
- [x] Module `rag/embeddings.py` : `HuggingFaceEmbeddings` (modèle multilingue `EMBEDDING_MODEL`, exécuté en local, CPU)
- [x] Modèle d'embeddings **chargé une seule fois** (`@functools.cache`, réutilisé par l'indexation et l'API)
- [x] Vecteurs **normalisés** (norme 1, dim 384) → distance L2 ≈ cosinus
- [x] (Note) embeddings HuggingFace privilégiés pour rester local/gratuit ; alternative `mistral-embed` documentée

### 3.3 Indexation FAISS
- [x] Module `rag/vectorstore.py` : `FAISS.from_documents(...)` (`DistanceStrategy.COSINE`) + `save_local`/`load_local`
- [x] Script CLI `scripts/build_index.py` : (re)construit l'index depuis `data/processed/` → `vectorstore/index/`
- [x] Persistance de l'index + métadonnées (`index.faiss` 6.4 Mo + `index.pkl` 3.2 Mo)
- [x] Choix `IndexFlatL2` (exact, rappel 100 % pour le POC) ; bascule IVF/HNSW documentée pour le passage à l'échelle

### 3.4 Tests de recherche & unitaires (énoncé)
- [x] `tests/test_vectorstore.py` : l'index se charge et contient le nombre attendu de vecteurs (4076)
- [x] Test de **recherche sémantique** : une requête connue renvoie l'événement pertinent dans le top-k
- [x] Vérifier que **tous les événements** ont bien été indexés (1500 `uid` index == parquet)
- [x] Vérifier la **présence des métadonnées** dans les résultats de recherche
- [x] + round-trip build → save → load sur corpus synthétique ; **44 tests passent** au total (`uv run pytest`)

## Points de vigilance (énoncé)
- **Optimiser** l'index pour des recherches rapides (bon algorithme FAISS).
- Vérifier que **tous les événements** sont indexés.
- Stocker non seulement les vecteurs mais aussi les **métadonnées** (dates, lieux, descriptions).
- Faire des **tests de recherche** pour valider l'efficacité.

## Outils & ressources
- FAISS (indexation vectorielle), LangChain (interface FAISS), HuggingFace embeddings.
- [Faiss Index Guide](https://github.com/facebookresearch/faiss/wiki).

## Statut : TERMINÉ
