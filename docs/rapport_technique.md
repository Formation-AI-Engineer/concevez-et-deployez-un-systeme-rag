# Rapport technique — Assistant intelligent de recommandation d'événements culturels

> POC d'un système **RAG** (Retrieval-Augmented Generation) pour **Puls-Events**, réalisé dans le
> cadre de la mission OpenClassrooms « Concevez et déployez un système RAG ».
> Ce document suit le plan du template de rapport technique fourni.

---

## 1. Objectifs du projet

**Contexte.** Puls-Events, plateforme de recommandation d'événements culturels, souhaite offrir à ses
utilisateurs un **assistant conversationnel** capable de répondre en langage naturel à des questions
sur les événements à venir (« Quels concerts de jazz à Paris ? », « Une expo près de la Cité des
sciences ? »). La mission, confiée en freelance, consiste à livrer un **POC** démontrant la faisabilité
technique et la valeur métier de l'approche.

**Problématique — pourquoi un système RAG ?** Les événements culturels constituent un domaine
**volatil** (l'offre change en permanence) et **factuel** (dates, lieux, titres doivent être exacts).
Un LLM seul, interrogé sur sa mémoire d'entraînement, **hallucinerait** des événements ou donnerait des
informations périmées. Le RAG résout ces deux problèmes : la réponse est **générée à partir d'événements
réels récupérés à la volée** dans une base à jour, ce qui garantit l'ancrage factuel (*grounding*) tout
en conservant la fluidité d'un LLM.

**Objectif du POC.**
- Démontrer la **faisabilité technique** : pipeline complet, de l'API Open Agenda à une réponse en
  langage naturel sourcée.
- Démontrer la **valeur métier** : réponses pertinentes, honnêtes (pas d'invention) et exploitables.
- Valider la **performance** et la **reproductibilité** (chargement unique des modèles, conteneurisation).

**Périmètre.**
- **Zone géographique** : Paris (paramétrable).
- **Période** : événements de moins d'un an et à venir (fenêtre glissante de 12 mois).
- **Données** : ~**1500 événements** culturels parisiens issus de l'**API Open Agenda**, découpés en
  **4076 chunks** indexés.

---

## 2. Architecture du système

### Schéma global

```
                       ┌─────────────────────── INDEXATION (hors-ligne) ───────────────────────┐
   API Open Agenda ──► fetch_events.py ──► preprocessing (pandas) ──► chunking ──► embeddings ──► FAISS
   (événements bruts)   data/raw/*.json     data/processed/*.parquet   (RecursiveChar.)  (HF, CPU)   index/
                                                                                                        │
                       ┌─────────────────────── INTERROGATION (temps réel) ─────────────────────┐      │
   Utilisateur ──► POST /ask (FastAPI) ──► RAGAssistant (LangChain) ──► recherche sémantique ◄──────────┘
                                                   │                         (FAISS, top-k)
                                                   ├─ gating de pertinence (seuil cosinus)
                                                   ▼
                                          Mistral (LLM, génération) ──► réponse + sources (JSON)
```

Deux phases distinctes : une **indexation** menée hors-ligne (scripts), et une **interrogation** en
temps réel servie par l'API. L'index FAISS et le modèle d'embeddings sont **chargés une seule fois au
démarrage** de l'API (et réutilisés à chaque requête), conformément à l'exigence de performance.

### Séparation des responsabilités

- `rag/` — **logique métier** réutilisable (chargement, pré-traitement, chunking, embeddings,
  vectorstore, chaîne RAG). Indépendante du transport HTTP.
- `api/` — **exposition HTTP** (FastAPI) : ne fait qu'encapsuler `rag/`.
- `scripts/` — **outils CLI** (récupération, indexation, recherche, évaluation).

### Technologies utilisées

| Couche | Technologie | Justification courte |
|---|---|---|
| Source de données | API Open Agenda + `requests` | Source officielle d'événements, accès par agendas |
| Manipulation données | `pandas` (+ `pyarrow` pour Parquet) | Standard, format colonne compact pour `data/processed/` |
| Découpage | LangChain `RecursiveCharacterTextSplitter` | Chunks sémantiquement cohérents |
| Embeddings | `sentence-transformers` multilingue (HuggingFace, **CPU**) | Gratuit, local, données qui ne sortent pas |
| Base vectorielle | **FAISS** (`faiss-cpu`, `IndexFlatL2`) | Recherche exacte, portable, sans serveur |
| Orchestration | **LangChain** | Standardise retrieval + prompt + LLM |
| Génération (LLM) | **Mistral** (`mistral-small-latest`, API) | Bonne qualité en français, coût maîtrisé |
| API REST | **FastAPI** + Uvicorn | Async, validation Pydantic, Swagger auto |
| Évaluation | métriques locales + **Ragas** | Quantification de la qualité des réponses |
| Conteneurisation | **Docker** (+ Compose) | Démo locale reproductible |
| Gestion d'environnement | **uv** + `pyproject.toml`/`uv.lock` | Installs déterministes |

---

## 3. Préparation et vectorisation des données

**Source de données.** API Open Agenda, interrogée par **agendas** publics filtrés sur la zone (Paris).
Paramètres clés : ville cible, nombre d'événements visé, nombre maximal d'agendas, plafond par agenda.
Les événements sont récupérés en JSON brut dans `data/raw/events.json`.

**Nettoyage et structuration** (`rag/preprocessing.py`). Les données Open Agenda sont hétérogènes :
- **Champs multilingues** : on privilégie le français (`fr`) avec repli sur les autres langues.
- **Données manquantes / incomplètes** : événements sans titre, sans date ou sans description **écartés** ;
  champs optionnels (lieu, URL, catégorie) normalisés avec valeurs de repli.
- **Dates** : normalisation des plages (`date_range` lisible) et **filtrage temporel** (fenêtre de 12
  mois, événements à venir) pour respecter le périmètre.
- **Périmètre géographique** : filtrage sur la ville cible.
- Résultat : un jeu **propre et structuré** persisté en **Parquet** (`data/processed/events.parquet`),
  format colonne compact et typé.

**Chunking** (`rag/chunking.py`). Chaque événement est transformé en un texte synthétique
(titre + description + date + lieu + catégorie) puis découpé via `RecursiveCharacterTextSplitter` :
- **taille de chunk : 800 caractères**, **chevauchement : 100** — compromis entre granularité (un chunk
  cible un événement et son contexte) et préservation du sens aux frontières.
- Les **métadonnées** de l'événement (uid, titre, date, lieu, ville, url, catégorie) sont attachées à
  **chaque chunk** (essentiel pour restituer les sources). Total : **4076 chunks**.

**Embedding** (`rag/embeddings.py`).
- Modèle : **`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`** (HuggingFace), exécuté
  **en local sur CPU**.
- **Dimensionnalité : 384**. Vecteurs **normalisés** (norme 1) → la distance L2 de FAISS devient
  **monotone à la similarité cosinus**.
- Choix d'embeddings **locaux** (vs API payante type `mistral-embed`) : gratuité, reproductibilité,
  et les données **ne sortent pas** du système. Le modèle est **chargé une seule fois** (cache mémoire).

---

## 4. Choix du modèle NLP

**Modèle sélectionné : Mistral `mistral-small-latest`** (API), via `langchain-mistralai`.

**Pourquoi ce modèle ?**
- **Qualité en français** : le cas d'usage est francophone (événements parisiens) ; Mistral y est
  particulièrement à l'aise.
- **Coût maîtrisé** : la variante *small* offre un bon rapport qualité/prix pour un POC.
- **Compatibilité LangChain** : intégration native (`ChatMistralAI`), interchangeable avec d'autres LLM.
- **Souveraineté** : fournisseur européen, cohérent avec une approche locale/maîtrisée pour les
  embeddings.

**Prompting** (`rag/chain.py`). Un **prompt système** impose l'ancrage factuel :

> *« Tu es un assistant culturel qui recommande des événements à Paris. Réponds en français […]
> Appuie-toi EXCLUSIVEMENT sur les événements fournis dans le CONTEXTE […] n'invente jamais
> d'événement, de date ni de lieu. Si le contexte ne contient aucun événement pertinent, dis-le
> honnêtement […]. Pour chaque événement recommandé, indique son titre, sa date et son lieu. »*

Le contexte (chunks récupérés) et la question sont injectés dans un *human prompt* structuré
(`CONTEXTE : … QUESTION : …`).

**Garde-fou de pertinence (gating).** Avant tout appel au LLM, un **seuil de distance cosinus (0.9)**
écarte les documents non pertinents. Si **aucun** document ne passe le seuil, le système renvoie une
réponse **honnête et déterministe** (« Je n'ai pas trouvé d'événement correspondant »)
**sans appeler le LLM** — gain de robustesse et d'économie d'API.

**Filtrage temporel (événements à venir).** Après le gating, un filtre par **métadonnées de date**
ne conserve que les événements dont la date de fin est **≥ aujourd'hui** (les événements sans date
exploitable sont conservés). La recherche élargit d'abord le nombre de candidats puis tronque à
`top_k`, et la **date du jour est injectée dans le prompt** pour que le modèle privilégie les
événements à venir et respecte une période demandée. On évite ainsi de recommander des événements
**passés** (réglable via `FILTER_PAST_EVENTS`).

**Limites du modèle.**
- Dépendance à une **API externe** (coût, latence, disponibilité réseau au moment de la requête).
- Le LLM peut **reformuler** au-delà du strict contexte malgré le prompt (atténué par le gating et
  l'évaluation).
- Raisonnement temporel relatif fin (« ce week-end ») non géré ; le filtrage ci-dessus traite en
  revanche le cas « événements à venir / d'une année donnée ».

---

## 5. Construction de la base vectorielle

**FAISS utilisé** (`rag/vectorstore.py`).
- Index **`IndexFlatL2`** : recherche **exacte et exhaustive**. Pour un POC de quelques milliers de
  vecteurs, c'est **instantané** et garantit un **rappel de 100 %** (aucune approximation).
- Stratégie de distance déclarée **`COSINE`** : cohérente avec les vecteurs normalisés (L2 ≈ cosinus).
- À l'échelle (centaines de milliers / millions de vecteurs), on basculerait vers un index approximatif
  **IVF / HNSW** (recherche sous-linéaire au prix d'un rappel approché) — hors périmètre du POC.

**Stratégie de persistance.**
- Sauvegarde via `FAISS.save_local` dans `vectorstore/index/`.
- **Format / nommage** : `index.faiss` (les vecteurs) + `index.pkl` (le *docstore* : textes **et**
  métadonnées). Rechargement via `load_local` (un seul chargement au démarrage de l'API).
- L'index est **reconstructible** (`scripts/build_index.py`) et donc **non versionné**.

**Métadonnées associées.** Pour chaque document/chunk sont conservés : **uid, titre, plage de dates
(`date_range`), lieu (`location_name`), ville, url, catégorie**. Elles permettent de restituer les
**sources** dans la réponse de l'API (titre, date, lieu, lien) sans ré-interroger la source.

---

## 6. API et endpoints exposés

**Framework : FastAPI** + Uvicorn (async, validation **Pydantic**, **Swagger** auto sur `/docs`).
L'assistant RAG est chargé **une fois** au démarrage (`lifespan`) et rangé dans `app.state`.

**Endpoints clés.**

| Méthode & route | Description |
|---|---|
| `GET /health` | État du service + nombre d'événements indexés |
| `POST /ask` | `{ "question": "…" }` → `{ "question", "answer", "sources": [...] }` |
| `POST /rebuild` | Reconstruit l'index FAISS depuis `data/processed/` (protégé par jeton `X-API-Token`) |

**Exemple d'appel.**
```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Quels concerts de jazz puis-je voir à Paris ?"}'
```

**Tests effectués et documentés.** **81 tests** automatisés (pytest) couvrant pré-traitement,
chunking, embeddings, vectorstore, et l'API (réponses, codes d'erreur, protection `/rebuild`).
Intégration continue (GitHub Actions) : **lint (ruff) + tests** à chaque push/PR.

**Gestion des erreurs / limitations.**
- `422` — question vide ou champ manquant (validation Pydantic).
- `503` — assistant non chargé (index absent) : `/health` signale alors `degraded`.
- `401` — jeton `/rebuild` invalide ou manquant ; endpoint **désactivé** si aucun jeton configuré.
- `500` — échec de génération : le détail est **journalisé côté serveur**, jamais renvoyé au client
  (pas de fuite de clé/URL).

---

## 7. Évaluation du système

**Jeu de test annoté** (`eval/qa_dataset.json`).
- **20 paires** question / réponse de référence (jeu initial annoté à la main, étape 4.3), **réannotées
  sur l'index courant** via `scripts/build_qa_dataset.py` après rafraîchissement des données.
- **Méthode d'annotation** (inchangée) : pour chaque question, on interroge le *retriever*, on lit les
  événements **réellement récupérés** (titre, date, lieu) et on construit une réponse de référence
  **n'utilisant que ces faits réels**. Chaque paire indique les `expected_event_uids` pertinents, et des
  drapeaux `expects_no_match` / `expects_refusal` pour les cas hors-périmètre.
- **Évaluation sur instantané figé.** Les chiffres ci-dessous correspondent à l'**instantané de
  données** sur lequel le jeu a été annoté. L'index servant la démo peut être **rafraîchi** (cf.
  `fetch_events` + filtrage des événements à venir) ; pour rejouer l'évaluation à l'identique, on se
  place sur cet instantané (ou on réannote `eval/qa_dataset.json` sur les données courantes). Les
  tests d'ancrage du jeu se neutralisent automatiquement si l'index a divergé de l'instantané annoté.
- **Catégories** : `type_evenement` (10), `lieu` (5), `periode` (2), `hors_perimetre` (3).

**Métriques.**
- **Similarité sémantique** (embedding réponse vs référence) — mesure le sens.
- **Couverture des informations clés** (titres/dates attendus présents) — mesure l'exactitude factuelle.
- **Classification** correcte / partielle / incorrecte (seuils combinés).
- **Ragas** (faithfulness, context recall/precision) — sur échantillon (appels LLM coûteux).

**Résultats obtenus** (run complet 20 questions sur l'index **rafraîchi**, jeu réannoté via
`scripts/build_qa_dataset.py` ; filtrage temporel désactivé pour la reproductibilité).

| Indicateur | Valeur |
|---|---|
| Similarité sémantique moyenne | **0.77** |
| Couverture des infos clés | **0.71** |
| Correctes / partielles / incorrectes | **14 / 3 / 3** (70 % correctes) |

| Catégorie | n | Sim. moy. | Taux correctes |
|---|---|---|---|
| `lieu` | 5 | 0.82 | **80 %** |
| `periode` | 2 | 0.84 | 50 % (n=2) |
| `type_evenement` | 10 | 0.78 | 80 % |
| `hors_perimetre` | 3 | 0.63 | 33 % |

**Analyse qualitative.**
- **Points forts** : bonnes performances par **lieu** (80 %) et par **type d'événement** (80 %), avec
  une **similarité sémantique élevée** (0.77 en moyenne). Les réponses citent systématiquement titre,
  date et lieu réels.
- **Sensibilité d'échantillon** : `periode` ne compte que **2 questions** ; une seule réponse partielle
  fait chuter le taux à 50 % — à lire avec prudence vu la taille.
- **Cas faible identifié** : `type-dedicace-litterature` (sim 0.28, couverture 0) — le retriever n'a pas
  remonté l'événement attendu : piste d'amélioration côté recherche (cf. §8).
- **Artefact de métrique sur le hors-périmètre** : les questions hors-périmètre où le système **refuse
  honnêtement** (« je n'ai pas trouvé… ») obtiennent une **faible similarité** à une référence pourtant
  de refus, et sont comptées « incorrectes ». **Le comportement est en réalité correct** — la métrique
  pénalise à tort ces refus, à interpréter avec recul.
- **Ragas** (optionnel, coûteux) : non recalculé sur l'instantané rafraîchi ; sur l'instantané
  précédent, *faithfulness* ~0.53 et *context precision* ~0.71 — cohérent avec un ancrage factuel
  correct. Rejouable via `uv run --extra eval python scripts/evaluate_rag.py`.

---

## 8. Recommandations et perspectives

**Ce qui fonctionne bien.**
- **Ancrage factuel** : réponses fondées sur des événements réels, avec sources citées.
- **Honnêteté** : gating de pertinence → pas d'invention, refus assumé hors-périmètre (sans appel LLM).
- **Performance** : index + modèle chargés une seule fois ; recherche exacte instantanée.
- **Démo robuste** : conteneur autonome, **hors-ligne au démarrage** (index + embeddings embarqués).

**Limites du POC.**
- **Volumétrie** : ~1500 événements, une seule ville, un **instantané** de données (péremption possible).
- **Coût / latence** : dépendance à l'API Mistral pour chaque génération.
- **Couverture thématique** : quelques manques de rappel (ex. dédicace littéraire).
- **Évaluation** : Ragas calculé sur échantillon (coût des appels LLM-juges).

**Améliorations possibles.**
- **Fraîcheur des données** : ingestion **planifiée** (cron) + `/rebuild` automatisé.
- **Qualité de recherche** : **recherche hybride** (lexicale + vectorielle) et **reranking** pour les
  cas de faible rappel ; filtrage **temporel/géographique** structuré en plus du sémantique.
- **Modèle** : tester un LLM plus capable ou un *embedding* de meilleure qualité ; raisonnement
  temporel (« ce week-end »).
- **Passage à l'échelle** : index **IVF/HNSW**, base vectorielle managée si volumétrie importante.

**Passage en production.**
- Ingestion continue + base vectorielle managée, **authentification** et quotas sur l'API,
  **observabilité** (logs, métriques, traçage des coûts LLM), évaluation continue en CI, et
  **CI/CD** de l'image Docker.

---

## 9. Organisation du dépôt GitHub

```
.
├── rag/             # Logique métier RAG (chargement, pré-processing, chunking, embeddings, vectorstore, chaîne)
├── api/             # API REST FastAPI (main.py, schemas.py)
├── scripts/         # CLI : fetch_events, preprocess_events, build_index, search, evaluate_rag
├── tests/           # 81 tests unitaires/fonctionnels (pytest)
├── eval/            # Jeu de test annoté (qa_dataset.json) + rapports d'évaluation
├── data/            # Données Open Agenda (raw/ + processed/) — non versionnées
├── vectorstore/     # Index FAISS — reconstructible, non versionné
├── docs/            # Fiches d'étape + ce rapport technique
├── notebooks/       # Explorations
├── Dockerfile       # Conteneurisation de l'API (index + modèle embarqués, torch CPU)
├── docker-compose.yml
├── pyproject.toml / uv.lock   # Environnement reproductible (uv)
└── README.md        # Démarrage, reproduction, usage de l'API
```

| Répertoire | Rôle |
|---|---|
| `rag/` | Cœur du système, indépendant du transport HTTP |
| `api/` | Exposition HTTP (encapsule `rag/`) |
| `scripts/` | Pipeline reproductible en ligne de commande |
| `tests/` | Garantie de non-régression (lancés en CI) |
| `eval/` | Mesure objective de la qualité des réponses |
| `docs/` | Documentation pas-à-pas (une fiche par étape) |

---

## 10. Annexes

**A. Extrait du jeu de test annoté** (`eval/qa_dataset.json`)
```json
{
  "id": "type-jazz",
  "category": "type_evenement",
  "question": "Quels concerts de jazz puis-je voir à Paris ?",
  "reference_answer": "… (rédigée à partir des événements réellement indexés) …",
  "expected_event_uids": [ … ],
  "expects_no_match": false,
  "expects_refusal": false
}
```

**B. Prompt système** — voir §4 (ancrage factuel + honnêteté + format titre/date/lieu).

**C. Exemple de réponse JSON** (`POST /ask`)
```json
{
  "question": "Quels concerts de jazz puis-je voir à Paris ?",
  "answer": "Voici une sélection de concerts de jazz à Paris : 1. Jazzycolors — Festival … (27 oct. – 9 déc. 2025) …",
  "sources": [
    { "uid": 47475785, "title": "Jazzycolors - Festival de jazz international",
      "date": "27 octobre - 9 décembre 2025", "location": "Paris", "url": "https://www.ficep.info" }
  ]
}
```

**D. Démarrage de la démo conteneurisée**
```bash
docker build -t assistant-rag-evenements .
docker run --rm -p 8000:8000 --env-file .env.local assistant-rag-evenements
# → Swagger : http://127.0.0.1:8000/docs   |   GET /health → {"status":"ok","indexed_events":4076}
```
