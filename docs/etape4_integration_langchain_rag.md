# Étape 4 — Intégrez LangChain pour le système RAG

## Objectif
Développer le **chatbot intelligent** capable de fournir des **recommandations personnalisées** d'événements
et de générer des **réponses augmentées** à partir des données indexées dans FAISS, en orchestrant via
**LangChain** la recherche vectorielle et le LLM **Mistral**.

## Prérequis (énoncé)
- Les événements sont **indexés dans FAISS** (étape 3).
- Accès à l'**API Mistral** pour générer des réponses naturelles (LLM choisi sur la plateforme Mistral).

## Résultat attendu (énoncé)
- Un **chatbot** capable de fournir des recommandations d'événements et d'interagir avec l'utilisateur.
- Réponses à la fois **pertinentes** et **bien formulées**.

## Tâches

### 4.1 Chaîne RAG (LangChain) ✅
- [x] Module `rag/chain.py` : assemble retriever FAISS + LLM Mistral en une chaîne RAG
- [x] **Retriever** : `vectorstore.as_retriever(search_kwargs={"k": TOP_K})`
- [x] **LLM** : `ChatMistralAI` (modèle `MISTRAL_MODEL`, clé `MISTRAL_API_KEY`)
- [x] **Prompt template** : consigne de recommander des événements en s'appuyant **uniquement** sur le contexte récupéré
- [x] Chaîne RAG via LCEL (`prompt | llm | StrOutputParser`) ; retour réponse **+ documents sources** (`RAGAnswer`, traçabilité)
- [x] Pas d'historique de conversation (non requis dans le POC — chaque question indépendante)
- [x] Classe / fonction centrale `RAGAssistant.answer(question)` **réutilisable** (importée par l'API étape 5)

### 4.2 Robustesse & qualité des réponses ✅
- [x] Gérer le cas **aucun document pertinent** : seuil de distance `RELEVANCE_THRESHOLD` (cosinus, défaut 0.9, calibré empiriquement) ; `RAGAssistant.retrieve()` écarte les voisins lointains, et `answer()` court-circuite avec `NO_MATCH_MESSAGE` **sans appeler le LLM** (réponse honnête déterministe + économie d'appel API)
- [x] Inclure dans la réponse les **infos clés** (titre, date, lieu, mots-clés, lien) via `_format_event` (métadonnées injectées dans le contexte du LLM)
- [x] Tester plusieurs **scénarios d'interaction** : `tests/test_chain.py` (hermétique, doublures vectorstore + `FakeListChatModel`) couvre seuil, réponse honnête, traçabilité des sources, scénarios enchaînés

### 4.3 Jeu de test annoté (livrable) ✅
- [x] `eval/qa_dataset.json` : **20 paires** question/réponse annotées, chaque réponse fondée sur les événements réellement récupérés via `RAGAssistant.retrieve()` (uid tracés dans `expected_event_uids`)
- [x] Cas variés : `type_evenement` (×10), `lieu` (×5), `periode` (×2), `hors_perimetre` (×3, dont un refus malgré récupération)
- [x] **Méthode d'annotation documentée** dans `eval/README.md` ; validation automatique `tests/test_qa_dataset.py` (schéma, couverture, ancrage réel des uid dans l'index)

### 4.4 Évaluation de la qualité (énoncé) ✅
- [x] Script `scripts/evaluate_rag.py` : génère une réponse par question (`RAGAssistant.answer`) et la compare à la référence annotée
- [x] Métriques **locales** (sans LLM juge) : similarité sémantique (cosinus via nos embeddings), Exact Match, couverture des infos clés, classification *correcte / partielle / incorrecte*
- [x] Métriques **Ragas** câblées sur Mistral + embeddings HF (*faithfulness, answer relevancy, context recall/precision*) — **optionnelles et protégées** : dégradation gracieuse si `ragas` indisponible
- [x] Export d'un **rapport** dans `eval/reports/` (JSON détaillé + synthèse Markdown : global, par catégorie, distribution des classes)
- [x] Tests `tests/test_evaluate_rag.py` (fonctions pures hors-ligne) ; drapeaux `--sample N` / `--no-ragas` pour maîtriser le coût
- ✅ **Ragas opérationnel** via un *shim* de compatibilité : `ragas 0.4.3` importe `langchain_community.chat_models.vertexai.ChatVertexAI`, chemin supprimé de `langchain_community ≥ 0.4` ; le script réenregistre ce module avec un stub (jamais instancié — on évalue avec Mistral). Appels Mistral sérialisés (`RunConfig(max_workers=1, …)`) pour éviter le rate-limit. Scores réels obtenus : *faithfulness* 0.53, *context precision* 0.71, *context recall* 0.17.
- ⚠ **`answer_relevancy`** : la métrique legacy bute sur un bug interne de `ragas 0.4.3` (`TypeError: dict += dict`) avec les wrappers langchain 1.x ; le script la rend en `null` (« n/a » dans le rapport) sans interrompre les autres. La variante recommandée `ragas.metrics.collections.AnswerRelevancy` existe mais utilise une interface v2 non compatible avec le `evaluate()` legacy.

## Points de vigilance (énoncé)
- S'assurer que les réponses sont **pertinentes et bien formulées**.
- **Tester plusieurs scénarios** pour vérifier la robustesse du chatbot.
- Critère de correction : *même sens + mêmes informations* que la réponse annotée.

## Outils & ressources
- LangChain (orchestration), Mistral (génération), Ragas (évaluation automatique).
- [LangChain Documentation](https://python.langchain.com/), Mistral Model docs.

## Statut : FAIT (4.1 chaîne RAG, 4.2 robustesse, 4.3 jeu annoté, 4.4 évaluation)

> **Note Ragas / environnement** : `ragas 0.4.3` importe `ChatVertexAI` depuis un chemin supprimé
> de `langchain_community ≥ 0.4`. Plutôt que d'épingler d'anciennes versions, `evaluate_rag.py`
> installe un *shim* (`_install_vertexai_shim`) qui réenregistre le module manquant avec un stub :
> Ragas devient importable et exécutable tel quel. Les appels juge passent par Mistral (sérialisés
> pour éviter le rate-limit). Seule `answer_relevancy` reste indisponible (bug interne de cette
> version) et est rendue en `null`. Lancement : `python scripts/evaluate_rag.py [--sample N]`.
