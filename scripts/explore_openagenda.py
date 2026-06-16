"""Script d'exploration de l'API Open Agenda (étape 2 — préparation).

But : démontrer que la connexion à l'API fonctionne et valider la stratégie de récupération
des données retenue pour le POC. Ce script est exploratoire (diagnostic), il ne produit pas
le jeu de données final — c'est le rôle de ``scripts/fetch_events.py`` (à venir).

Stratégie validée par ce script :
  - la recherche GLOBALE d'événements (``/v2/events``) renvoie **403** (accès restreint) ;
  - on passe donc par les **agendas** : recherche d'agendas (``/v2/agendas``) puis récupération
    des événements d'un agenda (``/v2/agendas/{uid}/events``) filtrés par date.

Usage :
    uv run python scripts/explore_openagenda.py
"""

from __future__ import annotations

import sys

import requests

from rag.config import settings

API = "https://api.openagenda.com/v2"
TIMEOUT = 25


def _localized(value, lang: str = "fr"):
    """Open Agenda renvoie souvent des champs multilingues {fr: ..., en: ...}."""
    if isinstance(value, dict):
        return value.get(lang) or next(iter(value.values()), None)
    return value


def check_key() -> None:
    print("1) Validation de la clé Open Agenda")
    r = requests.get(f"{API}/agendas", params={"key": settings.openagenda_api_key, "size": 1},
                     timeout=TIMEOUT)
    r.raise_for_status()
    print(f"   OK — clé valide, {r.json().get('total', '?')} agendas accessibles.\n")


def check_global_search_restricted() -> None:
    print("2) Recherche globale d'événements /v2/events (attendu : 403 restreint)")
    r = requests.get(f"{API}/events",
                     params={"key": settings.openagenda_api_key, "size": 1, "search": settings.events_city},
                     timeout=TIMEOUT)
    print(f"   HTTP {r.status_code} -> on ne peut pas requêter tous les événements d'un coup."
          " Stratégie : passer par les agendas.\n")


def search_agendas(query: str, size: int = 8) -> list[dict]:
    print(f"3) Recherche d'agendas correspondant à {query!r}")
    r = requests.get(f"{API}/agendas",
                     params={"key": settings.openagenda_api_key, "search": query, "size": size},
                     timeout=TIMEOUT)
    r.raise_for_status()
    agendas = r.json().get("agendas", [])
    print(f"   {r.json().get('total', '?')} agendas trouvés (top {len(agendas)}) :")
    for a in agendas:
        print(f"     uid={a.get('uid')} | {a.get('title')!r}")
    print()
    return agendas


def sample_events(agenda_uid: int, since: str = "2025-06-16T00:00:00", size: int = 2) -> None:
    print(f"4) Événements à venir de l'agenda {agenda_uid} (filtre date timings[gte]={since})")
    r = requests.get(f"{API}/agendas/{agenda_uid}/events",
                     params={"key": settings.openagenda_api_key, "size": size,
                             "timings[gte]": since, "detailed": 1},
                     timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    print(f"   total à venir : {data.get('total')}")
    for ev in data.get("events", []):
        loc = ev.get("location") or {}
        print(f"     • {_localized(ev.get('title'))}")
        print(f"       lieu  : {loc.get('name')} — {loc.get('city')}")
        print(f"       quand : {_localized(ev.get('dateRange'))}")
        desc = str(_localized(ev.get("description")) or "")[:120]
        print(f"       desc  : {desc}")
    print()


def main() -> int:
    if not settings.openagenda_api_key:
        print("OPENAGENDA_API_KEY manquante (définir dans .env.local).", file=sys.stderr)
        return 1
    print(f"=== Exploration API Open Agenda — ville cible : {settings.events_city} ===\n")
    check_key()
    check_global_search_restricted()
    agendas = search_agendas(settings.events_city)
    if agendas:
        sample_events(agendas[0]["uid"])
    print("=== Connexion API fonctionnelle — stratégie par agendas validée. ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
