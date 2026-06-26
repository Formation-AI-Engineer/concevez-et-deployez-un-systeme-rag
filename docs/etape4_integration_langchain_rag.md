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

### 4.3 Jeu de test annoté (livrable)
- [ ] `eval/qa_dataset.json` : questions/réponses de référence **annotées par l'humain** (≥ 15–20 paires)
- [ ] Couvrir des cas variés : type d'événement, lieu, période, question hors-périmètre
- [ ] Documenter la **méthode d'annotation** (réponses fondées sur les données réellement indexées)

### 4.4 Évaluation de la qualité (énoncé)
- [ ] Script `scripts/evaluate_rag.py` : compare les réponses générées au jeu annoté
- [ ] Métriques : **similarité sémantique**, **Exact Match**, et/ou classification *correcte / partielle / incorrecte*
- [ ] Métriques **Ragas** : *answer relevancy*, *faithfulness*, *context recall/precision*
- [ ] Export d'un **rapport d'évaluation** (`eval/reports/`) + synthèse des résultats

## Points de vigilance (énoncé)
- S'assurer que les réponses sont **pertinentes et bien formulées**.
- **Tester plusieurs scénarios** pour vérifier la robustesse du chatbot.
- Critère de correction : *même sens + mêmes informations* que la réponse annotée.

## Outils & ressources
- LangChain (orchestration), Mistral (génération), Ragas (évaluation automatique).
- [LangChain Documentation](https://python.langchain.com/), Mistral Model docs.

## Statut : EN COURS (4.1 + 4.2 faites ; restent 4.3 jeu de test, 4.4 évaluation)
