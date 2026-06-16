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

### 4.1 Chaîne RAG (LangChain)
- [ ] Module `rag/chain.py` : assemble retriever FAISS + LLM Mistral en une chaîne RAG
- [ ] **Retriever** : `vectorstore.as_retriever(search_kwargs={"k": TOP_K})`
- [ ] **LLM** : `ChatMistralAI` (modèle `MISTRAL_MODEL`, clé `MISTRAL_API_KEY`)
- [ ] **Prompt template** : consigne de recommander des événements en s'appuyant **uniquement** sur le contexte récupéré
- [ ] Chaîne `create_retrieval_chain` / RAG via LCEL ; retour réponse **+ documents sources** (traçabilité)
- [ ] Pas d'historique de conversation (non requis dans le POC — chaque question indépendante)
- [ ] Classe / fonction centrale `RAGAssistant.answer(question)` **réutilisable** (importée par l'API étape 5)

### 4.2 Robustesse & qualité des réponses
- [ ] Gérer le cas **aucun document pertinent** (réponse honnête « je n'ai pas d'événement correspondant »)
- [ ] Inclure dans la réponse les **infos clés** (titre, date, lieu) issues des métadonnées
- [ ] Tester plusieurs **scénarios d'interaction** (ex. « Quels concerts de jazz à Paris cette semaine ? »)

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

## Statut : À FAIRE
