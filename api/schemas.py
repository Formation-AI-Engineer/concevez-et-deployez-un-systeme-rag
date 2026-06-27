"""Schémas d'entrée/sortie de l'API REST (étape 5.2).

Contrats **Pydantic** échangés avec les clients HTTP : ils valident les requêtes (question non
vide → 422 automatique) et documentent les réponses dans Swagger. Aucun secret n'y transite.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AskRequest(BaseModel):
    """Corps de `POST /ask` : la question de l'utilisateur."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Question en langage naturel sur les événements culturels.",
        examples=["Quels concerts de jazz puis-je voir à Paris ?"],
    )

    @field_validator("question")
    @classmethod
    def _non_vide(cls, v: str) -> str:
        """Rejette une question vide ou composée uniquement d'espaces (→ 422)."""
        v = v.strip()
        if not v:
            raise ValueError("La question ne peut pas être vide.")
        return v


class SourceEvent(BaseModel):
    """Événement source ayant servi à construire la réponse (traçabilité)."""

    uid: int | None = None
    title: str | None = None
    date: str | None = None
    location: str | None = None
    url: str | None = None


class AskResponse(BaseModel):
    """Réponse de `POST /ask` : texte généré + événements sources."""

    question: str
    answer: str
    sources: list[SourceEvent]


class HealthResponse(BaseModel):
    """État du service (`GET /health`)."""

    status: str = Field(description="`ok` si l'assistant est chargé, sinon `degraded`.")
    assistant_ready: bool
    indexed_events: int | None = Field(
        default=None, description="Nombre de vecteurs dans l'index (si chargé)."
    )


class RebuildResponse(BaseModel):
    """Résultat de `POST /rebuild` : statut de la reconstruction de l'index."""

    status: str
    indexed_events: int
