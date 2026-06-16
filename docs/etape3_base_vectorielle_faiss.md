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
- [ ] Module `rag/chunking.py` : `RecursiveCharacterTextSplitter` (LangChain), `CHUNK_SIZE` / `CHUNK_OVERLAP` (`.env`)
- [ ] Conversion des événements en `Document` LangChain : `page_content` (texte) + `metadata` (date, lieu, catégorie, URL, id)
- [ ] Stratégie : 1 événement = 1+ chunks selon la longueur de la description (garder l'id événement en métadonnée)

### 3.2 Embeddings
- [ ] Module `rag/embeddings.py` : `HuggingFaceEmbeddings` (modèle multilingue `EMBEDDING_MODEL`, exécuté en local)
- [ ] Modèle d'embeddings **chargé une seule fois** (réutilisé par l'indexation et l'API)
- [ ] (Note) embeddings HuggingFace privilégiés pour rester local/gratuit ; alternative Mistral embeddings documentée

### 3.3 Indexation FAISS
- [ ] Module `rag/vectorstore.py` : construction `FAISS.from_documents(...)` + `save_local(VECTORSTORE_DIR)`
- [ ] Script CLI `scripts/build_index.py` : (re)construit l'index depuis `data/processed/` → `vectorstore/index/`
- [ ] Persistance de l'index + métadonnées (`index.faiss` + `index.pkl`)
- [ ] Choix de l'index FAISS adapté (Flat L2 / cosine pour un POC ; documenter le choix vs IVF pour le passage à l'échelle)

### 3.4 Tests de recherche & unitaires (énoncé)
- [ ] `tests/test_vectorstore.py` : l'index se charge et contient le nombre attendu de vecteurs
- [ ] Test de **recherche sémantique** : une requête connue renvoie l'événement pertinent dans le top-k
- [ ] Vérifier que **tous les événements** ont bien été indexés (comptage chunks vs documents)
- [ ] Vérifier la **présence des métadonnées** dans les résultats de recherche

## Points de vigilance (énoncé)
- **Optimiser** l'index pour des recherches rapides (bon algorithme FAISS).
- Vérifier que **tous les événements** sont indexés.
- Stocker non seulement les vecteurs mais aussi les **métadonnées** (dates, lieux, descriptions).
- Faire des **tests de recherche** pour valider l'efficacité.

## Outils & ressources
- FAISS (indexation vectorielle), LangChain (interface FAISS), HuggingFace embeddings.
- [Faiss Index Guide](https://github.com/facebookresearch/faiss/wiki).

## Statut : À FAIRE
