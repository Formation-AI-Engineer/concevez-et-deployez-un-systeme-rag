"""Nettoyage et structuration des événements Open Agenda (étape 2.2).

Transforme le JSON brut (``data/raw/events.json``) en un jeu de données **propre et structuré**
(``data/processed/events.parquet``), prêt à être découpé puis indexé (étape 3) :
- résolution des champs multilingues (français prioritaire) ;
- nettoyage du texte (HTML, espaces, entités) ;
- extraction des métadonnées (lieu, dates, coordonnées, agenda source) ;
- construction d'un **texte consolidé** par événement (titre + description + lieu + dates) destiné
  à la vectorisation ;
- suppression des événements sans contenu textuel exploitable.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def localized(value: Any, lang: str = "fr") -> str:
    """Résout un champ Open Agenda multilingue ``{fr: ..., en: ...}`` en chaîne.

    Préfère ``lang`` puis l'anglais, sinon la première valeur non vide. Renvoie "" si rien.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in (lang, "en"):
            if value.get(key):
                return str(value[key])
        for v in value.values():
            if v:
                return str(v)
    return str(value)


def clean_text(text: str) -> str:
    """Retire le HTML, décode les entités et normalise les espaces."""
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _timing(ev: dict, key: str, bound: str) -> str | None:
    """Extrait une borne ISO (``begin``/``end``) d'un timing (firstTiming/lastTiming/nextTiming)."""
    timing = ev.get(key) or {}
    return timing.get(bound) if isinstance(timing, dict) else None


def event_to_record(ev: dict) -> dict:
    """Aplatit un événement brut en un enregistrement plat et nettoyé."""
    location = ev.get("location") or {}
    origin = ev.get("originAgenda") or {}

    title = clean_text(localized(ev.get("title")))
    description = clean_text(localized(ev.get("description")))
    long_description = clean_text(localized(ev.get("longDescription")))
    keywords = localized(ev.get("keywords"))
    date_range = clean_text(localized(ev.get("dateRange")))

    return {
        "uid": ev.get("uid"),
        "title": title,
        "description": description,
        "long_description": long_description,
        "keywords": keywords,
        "date_range": date_range,
        "date_start": _timing(ev, "firstTiming", "begin"),
        "date_end": _timing(ev, "lastTiming", "end"),
        "next_date": _timing(ev, "nextTiming", "begin"),
        "location_name": location.get("name") or "",
        "address": location.get("address") or "",
        "city": location.get("city") or "",
        "postal_code": location.get("postalCode") or "",
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "agenda_uid": ev.get("_agenda_uid"),
        "agenda_title": clean_text(localized(origin.get("title"))),
        "slug": ev.get("slug") or "",
        "url": origin.get("url") or "",
    }


def build_document_text(record: dict) -> str:
    """Construit le texte consolidé d'un événement, destiné à l'embedding.

    Concatène les éléments porteurs de sens en sections lisibles (le LLM et le retriever
    profitent d'un contexte structuré : quoi, quand, où).
    """
    parts: list[str] = []
    if record["title"]:
        parts.append(record["title"])
    # description courte puis longue (en évitant la redondance si identiques)
    desc = record["description"]
    long_desc = record["long_description"]
    if desc:
        parts.append(desc)
    if long_desc and long_desc != desc:
        parts.append(long_desc)
    if record["date_range"]:
        parts.append(f"Quand : {record['date_range']}.")
    lieu = " ".join(p for p in (record["location_name"], record["address"], record["city"]) if p)
    if lieu:
        parts.append(f"Lieu : {lieu}.")
    if record["keywords"]:
        parts.append(f"Mots-clés : {record['keywords']}.")
    return "\n".join(parts)


def load_raw(path: str | Path) -> list[dict]:
    """Charge la liste d'événements depuis le JSON brut produit par fetch_events."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload.get("events", payload if isinstance(payload, list) else [])


def build_dataframe(raw_events: list[dict]) -> pd.DataFrame:
    """Construit le DataFrame propre + colonne ``document`` (texte consolidé).

    Filtre les événements sans contenu textuel exploitable (ni titre ni description)
    et dédoublonne par ``uid``.
    """
    records = [event_to_record(ev) for ev in raw_events]
    df = pd.DataFrame.from_records(records)
    if df.empty:
        return df

    df["document"] = df.apply(build_document_text, axis=1)

    # Qualité : on retire les événements sans aucun contenu utile.
    has_content = (df["title"].str.len() > 0) | (df["description"].str.len() > 0) | (
        df["long_description"].str.len() > 0
    )
    df = df[has_content].copy()
    df = df.drop_duplicates(subset="uid").reset_index(drop=True)
    return df


def run(raw_path: str | Path, out_path: str | Path) -> pd.DataFrame:
    """Pipeline complet : charge le brut, structure, exporte en parquet."""
    raw = load_raw(raw_path)
    df = build_dataframe(raw)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    return df
