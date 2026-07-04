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
from datetime import datetime, timezone

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
    "Nous sommes le {today}. Propose en priorité des événements à venir ; si l'utilisateur "
    "cible une période précise (une année, un mois, une saison), limite-toi aux événements de "
    "cette période et, si aucun ne correspond, dis-le clairement.\n"
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


def _parse_event_datetime(value) -> datetime | None:
    """Parse une date ISO d'événement (ex. ``2026-06-20T08:00:00+02:00``) -> ``datetime`` *aware*."""  # noqa: E501
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _event_end_datetime(meta: dict) -> datetime | None:
    """Date la plus tardive pertinente pour juger qu'un événement est encore à venir.

    On privilégie la date de **fin** (une expo s'étale sur des semaines), puis la prochaine
    occurrence, puis la date de début. ``None`` si aucune date n'est exploitable (l'événement
    est alors conservé : on préfère ne pas écarter par excès de prudence).
    """
    for field in ("date_end", "next_date", "date_start"):
        dt = _parse_event_datetime(meta.get(field))
        if dt:
            return dt
    return None


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
        filter_past_events: bool | None = None,
        filter_fetch_k: int | None = None,
        reference_date: datetime | None = None,
    ) -> None:
        self.vectorstore = vectorstore or load_vectorstore()
        self.top_k = top_k or settings.top_k
        # Seuil de distance au-delà duquel un document est jugé non pertinent (cf. config).
        self.relevance_threshold = (
            settings.relevance_threshold if relevance_threshold is None else relevance_threshold
        )
        # Filtrage temporel : n'exposer que les événements à venir (cf. config). ``reference_date``
        # permet de figer « aujourd'hui » en test ; sinon on prend l'heure courante à la requête.
        self.filter_past_events = (
            settings.filter_past_events if filter_past_events is None else filter_past_events
        )
        # Fenêtre de récupération élargie AVANT filtrage temporel (cf. config) : garantit que les
        # événements à venir les plus proches ne sont pas noyés sous des voisins passés.
        self.filter_fetch_k = (
            settings.filter_fetch_k if filter_fetch_k is None else filter_fetch_k
        )
        self.reference_date = reference_date
        # Retriever LangChain « brut » (interface publique réutilisable par l'API étape 5).
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": self.top_k})
        self.llm = llm or _build_llm()
        # Chaîne LCEL : prompt -> LLM -> texte brut. Le contexte est injecté dans answer().
        self.chain = _build_prompt() | self.llm | StrOutputParser()

    def _today(self) -> datetime:
        return self.reference_date or datetime.now(timezone.utc)

    def _keep_upcoming(self, docs: list[Document]) -> list[Document]:
        """Écarte les événements déjà passés (date de fin < aujourd'hui) ; garde ceux sans date."""
        today = self._today().date()
        kept = []
        for doc in docs:
            end = _event_end_datetime(doc.metadata)
            if end is None or end.date() >= today:
                kept.append(doc)
        return kept

    def retrieve(self, question: str) -> list[Document]:
        """Récupère les événements proches, écarte les non pertinents (seuil) puis les passés.

        ``similarity_search_with_score`` renvoie la distance cosinus (plus petite = plus proche) ;
        on ne conserve que les documents sous ``relevance_threshold``. Quand le filtrage temporel
        est actif, on élargit fortement la recherche (``filter_fetch_k``) car le corpus est
        majoritairement passé : sans cela, les voisins immédiats sont surtout des événements
        terminés, et les événements à venir pertinents — plus loin dans le classement — seraient
        écartés à tort. On ne garde ensuite que les à-venir, avant de tronquer à ``top_k``. Une
        requête hors-périmètre renvoie une liste vide -> réponse honnête dans ``answer()``.
        """
        fetch_k = self.filter_fetch_k if self.filter_past_events else self.top_k
        scored = self.vectorstore.similarity_search_with_score(question, k=fetch_k)
        docs = [doc for doc, distance in scored if distance <= self.relevance_threshold]
        if self.filter_past_events:
            docs = self._keep_upcoming(docs)
        return docs[: self.top_k]

    def answer(self, question: str) -> RAGAnswer:
        """Répond à une question : recherche les événements pertinents puis génère la réponse."""
        docs = self.retrieve(question)
        # Aucun document pertinent : réponse honnête, sans appeler le LLM (anti-hallucination).
        if not docs:
            return RAGAnswer(question=question, answer=NO_MATCH_MESSAGE, sources=[])
        context = _format_context(docs)
        answer = self.chain.invoke(
            {"question": question, "context": context, "today": self._today().strftime("%d/%m/%Y")}
        )
        return RAGAnswer(question=question, answer=answer, sources=docs)
