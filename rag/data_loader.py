"""Client de l'API Open Agenda v2 (étape 2 — récupération des données).

Encapsule les appels à l'API derrière une classe réutilisable :
- recherche d'agendas par mot-clé (``search_agendas``) ;
- récupération paginée des événements d'un agenda, filtrés par date (``iter_events``).

La recherche globale d'événements (``/v2/events``) étant restreinte (403) sur la clé du projet,
la stratégie retenue est : cibler des agendas puis parcourir leurs événements (cf. docs/etape2).
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import requests

API_BASE = "https://api.openagenda.com/v2"


class OpenAgendaError(RuntimeError):
    """Erreur renvoyée par l'API Open Agenda."""


class OpenAgendaClient:
    """Client minimal et poli (retries) pour l'API Open Agenda v2."""

    def __init__(self, api_key: str, *, timeout: int = 25, max_retries: int = 3,
                 base_url: str = API_BASE) -> None:
        if not api_key:
            raise ValueError("Clé API Open Agenda manquante.")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_url = base_url
        self.session = requests.Session()

    def _get(self, path: str, params: dict) -> dict:
        """GET avec clé injectée + retries sur 429 / 5xx."""
        params = {"key": self.api_key, **params}
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
                if r.status_code == 429 or r.status_code >= 500:
                    time.sleep(1.5 * (attempt + 1))  # back-off simple
                    last_exc = OpenAgendaError(f"HTTP {r.status_code} sur {path}")
                    continue
                if not r.ok:
                    raise OpenAgendaError(f"HTTP {r.status_code} sur {path} : {r.text[:200]}")
                return r.json()
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(1.5 * (attempt + 1))
        raise OpenAgendaError(f"Échec après {self.max_retries} tentatives sur {path}") from last_exc

    def search_agendas(self, query: str, *, limit: int = 40, page_size: int = 20) -> list[dict]:
        """Recherche d'agendas contenant ``query`` (titre/description).

        Pagine via le cursor ``after`` (l'``offset`` est ignoré par ``/agendas``) et
        dédoublonne par ``uid`` (les pages se chevauchent d'un élément).
        """
        agendas: list[dict] = []
        seen: set = set()
        after: list[str] | None = None
        while len(agendas) < limit:
            params: dict = {"search": query, "size": page_size}
            if after:
                params["after[]"] = after
            data = self._get("/agendas", params)
            batch = data.get("agendas", [])
            if not batch:
                break
            new = 0
            for a in batch:
                if a["uid"] in seen:
                    continue
                seen.add(a["uid"])
                agendas.append(a)
                new += 1
                if len(agendas) >= limit:
                    break
            after = data.get("after")
            if not after or new == 0:
                break
        return agendas[:limit]

    def iter_events(self, agenda_uid: int, *, since: str | None = None,
                    until: str | None = None, page_size: int = 100,
                    max_events: int | None = None) -> Iterator[dict]:
        """Itère sur les événements d'un agenda, paginés via le cursor ``after``.

        ``since`` / ``until`` : bornes ISO 8601 sur les *timings* (``timings[gte]`` / ``[lte]``).
        """
        params: dict = {"size": page_size, "detailed": 1}
        if since:
            params["timings[gte]"] = since
        if until:
            params["timings[lte]"] = until

        after: list[str] | None = None
        yielded = 0
        while True:
            page_params = dict(params)
            if after:
                page_params["after[]"] = after
            data = self._get(f"/agendas/{agenda_uid}/events", page_params)
            events = data.get("events", [])
            if not events:
                break
            for ev in events:
                ev["_agenda_uid"] = agenda_uid  # traçabilité de la source
                yield ev
                yielded += 1
                if max_events is not None and yielded >= max_events:
                    return
            after = data.get("after")
            if not after or len(events) < page_size:
                break

    def count_upcoming(self, agenda_uid: int, *, since: str | None = None) -> int:
        """Nombre d'événements (à partir de ``since``) — pour classer les agendas par volume."""
        params: dict = {"size": 1}
        if since:
            params["timings[gte]"] = since
        return self._get(f"/agendas/{agenda_uid}/events", params).get("total", 0)
