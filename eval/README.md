# Jeu de test annoté — évaluation du RAG (étape 4.3)

Ce dossier contient le **jeu de test de référence** (`qa_dataset.json`) qui sert à évaluer la
qualité du chatbot RAG (étape 4.4). Les réponses de référence sont **annotées par l'humain** et
**fondées sur les données réellement indexées** dans FAISS (`vectorstore/index/`), et non sur des
connaissances générales — c'est la condition d'une évaluation juste : on mesure si le système
restitue fidèlement *ce qui est dans le corpus*.

## Corpus de référence

- Source : `data/processed/events.parquet` — **1500 événements** culturels parisiens (Open Agenda).
- Agendas dominants : JASS CLUB Paris (jazz), Cité des sciences, Collège des Bernardins,
  centres culturels étrangers (Wallonie-Bruxelles, coréen, tchèque, taïwanais), Théâtre Mandapa,
  paroisses parisiennes, agendas littéraires et cinéma.

## Méthode d'annotation

L'annotation s'appuie sur le script **`eval/build_qa_dataset.py`**, qui *réimprime les faits
bruts* d'ancrage (il **ne rédige pas** les réponses : celles-ci sont écrites à la main).
Pour **chaque question**, la réponse de référence a été construite ainsi :

1. **Interroger le système réel** : la question est passée à `RAGAssistant.retrieve()` (même
   retriever FAISS + même seuil de pertinence `RELEVANCE_THRESHOLD = 0.9` que la production),
   via `build_qa_dataset.py`.
2. **Lire les événements réellement récupérés** : `uid`, titre, date (`date_range`), lieu
   (`location_name`), agenda.
3. **Rédiger à la main** une réponse n'utilisant **que ces faits** (aucun événement inventé,
   aucune date/lieu ajouté de mémoire). Les doublons dus au *chunking* (un même événement
   découpé en plusieurs morceaux) sont dédoublonnés par `uid`.
4. **Renseigner la traçabilité** : `expected_event_uids` liste les `uid` des événements pertinents
   retenus à la main parmi ceux récupérés (vide pour les questions hors-périmètre).

**Invariant d'ancrage** : `expected_event_uids ⊆ événements récupérés par la question`. Autrement
dit, chaque `uid` annoté doit réellement être renvoyé par le retriever pour la question telle
qu'elle est stockée. Le top-k peut contenir des voisins supplémentaires non retenus (moins
pertinents) : c'est normal, le sous-ensemble pertinent est choisi par l'annotateur humain.

Le script sert aussi à **revérifier** cet invariant : relancé sur le dataset, il signale tout
`uid` annoté qui ne serait **plus récupéré** (« ANCRAGE CASSÉ »), utile si l'index ou le seuil
évolue. ⚠ Reformuler une question change son embedding et donc le top-k : il faut alors
re-vérifier l'ancrage (c'est ce contrôle qui l'attrape).

```bash
python eval/build_qa_dataset.py            # rejoue les 20 questions + contrôle d'écart
python eval/build_qa_dataset.py -q "jazz"  # sonde une requête ponctuelle
```

La preuve d'ancrage est par ailleurs **automatisée** dans
`tests/test_qa_dataset.py::test_uids_attendus_existent_dans_lindex` (tout `uid` annoté doit
exister dans l'index).

## Couverture (20 paires)

| Catégorie | Couvre | Nb |
|---|---|---|
| `type_evenement` | jazz, exposition, orgue/sacrée, cinéma, danse, conférence, sciences, littérature, classique, jeux vidéo | 10 |
| `lieu` | Cité des sciences, Collège des Bernardins, Théâtre Mandapa, Centre Wallonie-Bruxelles, paroisses | 5 |
| `periode` | Fête de la musique, Noël | 2 |
| `hors_perimetre` | moteur diesel, recette, météo (hors sujet) | 3 |

## Schéma d'une paire

```json
{
  "id": "type-jazz",
  "category": "type_evenement",
  "question": "Quels concerts de jazz puis-je voir à Paris ?",
  "reference_answer": "Réponse de référence fondée sur les événements indexés…",
  "expected_event_uids": [47475785, 90172283, 93449035],
  "expects_no_match": false,
  "expects_refusal": false
}
```

| Champ | Sens |
|---|---|
| `reference_answer` | Réponse attendue (sens + infos clés : titre, date, lieu). |
| `expected_event_uids` | `uid` des événements pertinents retenus parmi ceux récupérés (⊆ top-k ; traçabilité / *context recall*). |
| `expects_no_match` | `true` si le seuil de pertinence écarte **tout** document → réponse honnête déterministe (`NO_MATCH_MESSAGE`), **sans appel LLM**. |
| `expects_refusal` | `true` si l'assistant **doit refuser / dire qu'il n'a rien** — soit parce qu'aucun document n'est pertinent (`no_match`), soit parce que des documents remontent mais qu'aucun ne répond réellement (ex. « météo à Lyon » qui ramène des événements « climat » parisiens). |

## Critère de correction (rappel énoncé)

Une réponse générée est jugée correcte si elle a le **même sens** et les **mêmes informations**
(événements, dates, lieux) que la réponse de référence. La quantification (similarité sémantique,
Exact Match, métriques Ragas) est faite par `scripts/evaluate_rag.py` (étape 4.4).
