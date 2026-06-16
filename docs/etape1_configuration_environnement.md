# Étape 1 — Configurez l'environnement

## Objectif
Mettre en place un environnement Python **isolé et reproductible** permettant d'exécuter tous les composants
du POC (récupération des données, pré-processing, vectorisation, API). L'environnement doit être stable et
réinstallable sur n'importe quelle machine à partir d'un fichier de dépendances.

## Prérequis (énoncé)
- Python ≥ 3.8 installé (ici **3.10–3.12**, résolu en 3.11 via `uv`).
- Bases de la gestion d'environnement virtuel (venv / conda / poetry → ici **uv**).
- Bonne connexion internet pour télécharger les packages.

## Résultats attendus (énoncé)
- Un environnement virtuel fonctionnel.
- Un fichier de dépendances (`requirements.txt` ou `environment.yml` → ici **`pyproject.toml` + `uv.lock`**).
- Un `README.md` : objectifs, structure du projet, instructions de reproduction.

## Tâches

### 1.1 Initialisation de l'environnement (uv)
- [x] `uv init` → `pyproject.toml`, Python `>=3.10,<3.13` (`.python-version` = 3.11)
- [x] Dépendances RAG : `langchain`, `langchain-community`, `langchain-mistralai`, `langchain-huggingface`
- [x] Dépendances modèle/embeddings : `mistralai`, `sentence-transformers`
- [x] Base vectorielle : `faiss-cpu` (privilégié à `faiss-gpu` pour la portabilité — cf. énoncé)
- [x] Données : `requests` (Open Agenda), `pandas`, `python-dotenv`
- [x] API : `fastapi`, `uvicorn[standard]`, `pydantic`
- [x] Extra `eval` : `ragas`, `datasets`
- [x] Extra `dev` : `pytest`, `httpx`, `ruff`, `jupyter`, `ipykernel`
- [x] `uv sync --extra dev --extra eval` exécuté avec succès

### 1.2 Vérification des imports clés (énoncé)

#### Incohérences des imports de l'énoncé et corrections
Le snippet de l'énoncé utilise des chemins d'import **obsolètes ou erronés** avec les versions actuelles
(LangChain 1.x, SDK Mistral 2.x). Correspondance énoncé → équivalent moderne **réellement validé** :

| Import de l'énoncé | État | Équivalent moderne utilisé | Paquet |
|---|---|---|---|
| `import faiss` | ✅ valide | inchangé | `faiss-cpu` |
| `from langchain.vectorstores import FAISS` | ❌ `ModuleNotFoundError` | `from langchain_community.vectorstores import FAISS` | `langchain-community` |
| `from langchain.embeddings import HuggingFaceEmbeddings` | ❌ déplacé | `from langchain_huggingface import HuggingFaceEmbeddings` | `langchain-huggingface` |
| `from mistral import MistralClient` | ❌ paquet `mistral` inexistant | `from langchain_mistralai import ChatMistralAI` | `langchain-mistralai` |

Note sur le SDK Mistral brut : le projet n'appelle pas Mistral en direct (il passe par
`ChatMistralAI`), mais pour information, dans `mistralai==2.4.9` le client n'est **pas** exposé à la racine
(`from mistralai import Mistral` échoue — `mistralai` est un *namespace package*). Le bon chemin est
`from mistralai.client import Mistral`.

Imports effectivement utilisés et vérifiés (`uv run python -c "..."`) :
```python
import faiss
from langchain_community.vectorstores import FAISS          # énoncé: langchain.vectorstores (obsolète)
from langchain_huggingface import HuggingFaceEmbeddings      # énoncé: langchain.embeddings (déplacé)
from langchain_mistralai import ChatMistralAI                # énoncé: from mistral import MistralClient (inexistant)
```
- [x] Imports vérifiés OK — script reproductible `scripts/check_imports.py` (`uv run python scripts/check_imports.py`, exit 0)
- [x] **Compatibilité des versions** FAISS ⇄ LangChain validée : `faiss-cpu==1.14.3`, `langchain==1.3.9`,
      `langchain-community==0.4.2` (FAISS accédé via `langchain_community.vectorstores.FAISS`),
      `langchain-mistralai==1.1.5`, `langchain-huggingface==1.2.2`, `sentence-transformers==5.5.1`,
      `fastapi==0.137.1`, `pydantic==2.13.4`, `ragas==0.4.3`

### 1.3 Gestion des secrets
- [x] `.env.example` versionné (clés `MISTRAL_API_KEY`, `OPENAGENDA_API_KEY`, modèles, périmètre, chemins)
- [x] `.env` / `*.local` ignorés par Git (jamais de clé versionnée — cf. `.gitignore`)
- [x] Secrets locaux renseignés dans **`.env.local`** ; module `rag/config.py` charge `.env.local` (prioritaire) puis `.env`
- [x] **Clés validées en ligne** : Mistral OK (`mistral-small-latest` disponible), Open Agenda OK (API répond)

### 1.4 Structure de dossiers
- [x] `rag/` — logique métier RAG (importable)
- [x] `api/` — API REST FastAPI
- [x] `scripts/` — scripts CLI (fetch, build index, évaluation)
- [x] `tests/` — tests unitaires
- [x] `eval/` — jeu de test annoté + rapports d'évaluation
- [x] `data/raw` + `data/processed` — données Open Agenda (non versionnées)
- [x] `vectorstore/` — index FAISS (reconstructible, non versionné)
- [x] `docs/` — fiches d'étape
- [x] `notebooks/` — explorations

### 1.5 Fichiers de configuration
- [x] `.gitignore` (venv, `.env`, `*.local`, données, index FAISS, caches modèles)
- [x] `README.md` initial (objectifs, architecture, structure, reproduction)
- [x] `requirements.txt` exporté depuis uv pour les évaluateurs sans uv (`uv export --no-hashes --no-dev`)

### 1.6 Vérification "installation propre"
- [x] Environnement reconstruit par `uv sync` depuis `uv.lock` (install reproductible depuis le fichier de dépendances)
- [x] Procédure de reproduction documentée dans le `README.md`
- [ ] (Optionnel) rejouer sur une machine neuve / cache vidé pour confirmer la portabilité

## Points de vigilance (énoncé)
- Ne **pas** ajouter l'environnement virtuel au dépôt → fichier de dépendances pour la reproduction.
- Privilégier **`faiss-cpu`** pour la portabilité.
- **Ne jamais versionner** la clé d'API → `.env` ignoré par Git.
- Vérifier la **compatibilité des versions** (FAISS ⇄ LangChain notamment).
- Tester l'install **propre** (cache vidé) pour valider la reproductibilité.

## Outils & ressources
- `uv`, `pyproject.toml`, FAISS, LangChain, Mistral, HuggingFace.

## Statut : TERMINÉ (env uv synchronisé, imports + versions compatibles vérifiés, clés Mistral/Open Agenda validées)
