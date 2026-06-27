"""API REST exposant le système RAG (étape 5).

Encapsule l'assistant RAG (`rag.RAGAssistant`, étape 4) derrière une API **FastAPI** : les clients
posent une question via `POST /ask` et reçoivent une réponse augmentée + ses sources. L'index FAISS
et le modèle sont chargés **une seule fois au démarrage** (`lifespan`) puis réutilisés à chaque
requête (exigence de performance). La logique métier reste dans `rag/` ; ce module ne fait que
l'exposer en HTTP.

Lancement local :
    uvicorn api.main:app --reload
    # Swagger interactif : http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from api.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    RebuildResponse,
    SourceEvent,
)
from rag.config import settings

logger = logging.getLogger("api")


def _document_to_source(doc) -> SourceEvent:
    """Projette un `Document` LangChain (métadonnées) en source publique (sans champ sensible)."""
    m = doc.metadata
    # `dict.fromkeys` concatène lieu + ville sans doublon (ex. "Paris Paris" → "Paris").
    parts = dict.fromkeys(x for x in (m.get("location_name"), m.get("city")) if x)
    lieu = " ".join(parts) or None
    return SourceEvent(
        uid=m.get("uid"),
        title=m.get("title"),
        date=m.get("date_range"),
        location=lieu,
        url=m.get("url"),
    )


def _dedupe_sources(docs) -> list[SourceEvent]:
    """Convertit et dédoublonne les sources par `uid` (le chunking peut renvoyer 2 chunks)."""
    sources: list[SourceEvent] = []
    vus: set[int] = set()
    for doc in docs:
        uid = doc.metadata.get("uid")
        if uid is not None and uid in vus:
            continue
        if uid is not None:
            vus.add(uid)
        sources.append(_document_to_source(doc))
    return sources


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Charge l'assistant RAG **une fois** au démarrage et le range dans `app.state`.

    Si l'index est absent ou le modèle indisponible, l'app démarre quand même (Swagger reste
    accessible) mais `/health` signale `degraded` et `/ask` renvoie 503 jusqu'à reconstruction.
    """
    app.state.assistant = None
    try:
        from rag.chain import RAGAssistant

        app.state.assistant = RAGAssistant()
        logger.info("Assistant RAG chargé au démarrage.")
    except Exception as exc:  # index manquant, modèle indisponible…
        logger.warning("Assistant RAG non chargé au démarrage : %s", exc)
    yield
    app.state.assistant = None


app = FastAPI(
    title="Assistant RAG — Événements culturels",
    description=(
        "API de recommandation d'événements culturels parisiens par RAG "
        "(LangChain + FAISS + Mistral). Posez une question à `POST /ask`."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# --- Dépendances ---------------------------------------------------------------

def get_assistant(request: Request):
    """Fournit l'assistant chargé ; 503 s'il n'est pas disponible (index non construit)."""
    assistant = getattr(request.app.state, "assistant", None)
    if assistant is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Assistant indisponible : index non chargé. Lancez /rebuild ou build_index.",
        )
    return assistant


def require_rebuild_token(x_api_token: str | None = Header(default=None)) -> None:
    """Protège l'endpoint sensible `/rebuild` par un jeton (en-tête `X-API-Token`).

    Refuse si aucun jeton n'est configuré côté serveur (on n'expose jamais une reconstruction
    ouverte) ou si le jeton fourni ne correspond pas. Comparaison à temps constant.
    """
    expected = settings.api_rebuild_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Endpoint /rebuild désactivé : aucun jeton configuré (API_REBUILD_TOKEN).",
        )
    if not x_api_token or not secrets.compare_digest(x_api_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton invalide ou manquant (en-tête X-API-Token).",
        )


# --- Endpoints -----------------------------------------------------------------

@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Redirige la racine vers la documentation Swagger."""
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthResponse, tags=["service"])
def health(request: Request) -> HealthResponse:
    """État du service : indique si l'assistant est chargé et combien d'événements sont indexés."""
    assistant = getattr(request.app.state, "assistant", None)
    indexed = None
    if assistant is not None:
        try:
            indexed = assistant.vectorstore.index.ntotal
        except Exception:  # pragma: no cover - défensif
            indexed = None
    return HealthResponse(
        status="ok" if assistant is not None else "degraded",
        assistant_ready=assistant is not None,
        indexed_events=indexed,
    )


@app.post("/ask", response_model=AskResponse, tags=["rag"])
def ask(payload: AskRequest, assistant=Depends(get_assistant)) -> AskResponse:
    """Répond à une question via le système RAG et renvoie la réponse + ses sources."""
    try:
        result = assistant.answer(payload.question)
    except Exception as exc:  # échec d'inférence / LLM indisponible
        # On journalise le détail côté serveur mais on ne l'expose pas (pas de fuite de clé/URL).
        logger.exception("Échec de génération pour la question.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la génération de la réponse.",
        ) from exc
    return AskResponse(
        question=result.question,
        answer=result.answer,
        sources=_dedupe_sources(result.sources),
    )


@app.post(
    "/rebuild",
    response_model=RebuildResponse,
    tags=["service"],
    dependencies=[Depends(require_rebuild_token)],
)
def rebuild(request: Request) -> RebuildResponse:
    """Reconstruit l'index FAISS depuis `data/processed/` et recharge l'assistant (protégé)."""
    try:
        from rag.chain import RAGAssistant
        from rag.vectorstore import build_and_save, vector_count

        vectorstore = build_and_save()
        request.app.state.assistant = RAGAssistant(vectorstore=vectorstore)
        n = vector_count(vectorstore)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jeu de données structuré introuvable : lancez d'abord le preprocessing.",
        ) from exc
    except Exception as exc:
        logger.exception("Échec de la reconstruction de l'index.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la reconstruction de l'index.",
        ) from exc
    logger.info("Index reconstruit : %d vecteurs.", n)
    return RebuildResponse(status="ok", indexed_events=n)
