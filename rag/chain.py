"""Chaîne RAG — orchestration LangChain (étape 4.1).

Assemble en une **chaîne RAG** réutilisable :
1. le **retriever** FAISS (étape 3) qui retrouve les chunks d'événements les plus proches
   sémantiquement de la question ;
2. le **LLM Mistral** (``ChatMistralAI``) qui rédige une réponse en langage naturel **à partir
   du seul contexte récupéré** (les événements réellement indexés), pour éviter les hallucinations.

La classe ``RAGAssistant`` expose ``answer(question) -> RAGAnswer`` (réponse **+ documents
sources**, pour la traçabilité). Elle est importée telle quelle par l'API REST (étape 5) et par
le script d'évaluation (étape 4.4). Aucun historique de conversation : chaque question est
traitée indépendamment, conformément au périmètre du POC.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai import ChatMistralAI

from rag.config import settings
from rag.vectorstore import load_vectorstore

# Consigne système : cadre le rôle de l'assistant et impose de s'appuyer UNIQUEMENT sur le
# contexte fourni (anti-hallucination), avec une réponse honnête en l'absence de résultat.
SYSTEM_PROMPT = (
    "Tu es un assistant culturel qui recommande des événements à Paris. "
    "Réponds en français, de façon claire et chaleureuse.\n"
    "Appuie-toi EXCLUSIVEMENT sur les événements fournis dans le CONTEXTE ci-dessous : "
    "n'invente jamais d'événement, de date ni de lieu. "
    "Si le contexte ne contient aucun événement pertinent pour la question, dis-le "
    "honnêtement (par exemple : « Je n'ai pas trouvé d'événement correspondant. ») "
    "sans rien inventer.\n"
    "Pour chaque événement recommandé, indique son titre, sa date et son lieu."
)

_HUMAN_PROMPT = "CONTEXTE :\n{context}\n\nQUESTION : {question}"

# Réponse renvoyée lorsqu'aucun événement récupéré n'est pertinent (court-circuit avant LLM) :
# garantit une réponse honnête et déterministe, et économise un appel API inutile.
NO_MATCH_MESSAGE = (
    "Je n'ai pas trouvé d'événement correspondant à votre demande. "
    "Essayez de reformuler ou d'élargir vos critères (type d'événement, période, lieu)."
)


def _build_prompt() -> ChatPromptTemplate:
    """Construit le template de prompt (consigne système + contexte + question)."""
    return ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT), ("human", _HUMAN_PROMPT)]
    )


def _build_llm(temperature: float = 0.2) -> ChatMistralAI:
    """Instancie le LLM Mistral (clé et modèle issus de la configuration).

    Température basse : on privilégie des réponses factuelles et reproductibles, fidèles au
    contexte récupéré, plutôt que de la créativité.
    """
    return ChatMistralAI(
        model=settings.mistral_model,
        mistral_api_key=settings.require_mistral_key(),
        temperature=temperature,
    )


def _format_event(doc: Document) -> str:
    """Rend un chunk d'événement sous une forme lisible par le LLM (métadonnées + description)."""
    m = doc.metadata
    lignes = [f"Titre : {m.get('title') or 'sans titre'}"]
    if m.get("date_range"):
        lignes.append(f"Date : {m['date_range']}")
    lieu = " ".join(x for x in (m.get("location_name"), m.get("city")) if x)
    if lieu:
        lignes.append(f"Lieu : {lieu}")
    if m.get("keywords"):
        lignes.append(f"Mots-clés : {m['keywords']}")
    if m.get("url"):
        lignes.append(f"Lien : {m['url']}")
    lignes.append(f"Description : {doc.page_content}")
    return "\n".join(lignes)


def _format_context(docs: list[Document]) -> str:
    """Concatène les événements récupérés en un bloc de contexte numéroté."""
    if not docs:
        return "(aucun événement trouvé)"
    return "\n\n---\n\n".join(
        f"[Événement {i}]\n{_format_event(doc)}" for i, doc in enumerate(docs, start=1)
    )


@dataclass
class RAGAnswer:
    """Réponse du système RAG : texte généré + documents sources (traçabilité)."""

    question: str
    answer: str
    sources: list[Document]


class RAGAssistant:
    """Assistant RAG réutilisable : retriever FAISS + LLM Mistral orchestrés via LangChain."""

    def __init__(
        self,
        vectorstore=None,
        llm=None,
        top_k: int | None = None,
        relevance_threshold: float | None = None,
    ) -> None:
        self.vectorstore = vectorstore or load_vectorstore()
        self.top_k = top_k or settings.top_k
        # Seuil de distance au-delà duquel un document est jugé non pertinent (cf. config).
        self.relevance_threshold = (
            settings.relevance_threshold if relevance_threshold is None else relevance_threshold
        )
        # Retriever LangChain « brut » (interface publique réutilisable par l'API étape 5).
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": self.top_k})
        self.llm = llm or _build_llm()
        # Chaîne LCEL : prompt -> LLM -> texte brut. Le contexte est injecté dans answer().
        self.chain = _build_prompt() | self.llm | StrOutputParser()

    def retrieve(self, question: str) -> list[Document]:
        """Récupère les événements proches puis **écarte les non pertinents** par seuil de distance.

        ``similarity_search_with_score`` renvoie la distance cosinus (plus petite = plus proche) ;
        on ne conserve que les documents sous ``relevance_threshold``. Une requête hors-périmètre
        (dont tous les voisins sont lointains) renvoie alors une liste vide, ce qui déclenche la
        réponse honnête dans ``answer()``.
        """
        scored = self.vectorstore.similarity_search_with_score(question, k=self.top_k)
        return [doc for doc, distance in scored if distance <= self.relevance_threshold]

    def answer(self, question: str) -> RAGAnswer:
        """Répond à une question : recherche les événements pertinents, puis génère la réponse augmentée."""
        docs = self.retrieve(question)
        # Aucun document pertinent : réponse honnête, sans appeler le LLM (anti-hallucination).
        if not docs:
            return RAGAnswer(question=question, answer=NO_MATCH_MESSAGE, sources=[])
        context = _format_context(docs)
        answer = self.chain.invoke({"question": question, "context": context})
        return RAGAnswer(question=question, answer=answer, sources=docs)
