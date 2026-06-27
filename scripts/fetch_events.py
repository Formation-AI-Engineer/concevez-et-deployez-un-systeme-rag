"""Récupération des événements Open Agenda (étape 2.1).

Stratégie (cf. docs/etape2), multi-agendas :
  1. rechercher les agendas correspondant à la ville cible ;
  2. les classer par volume d'événements (sur la fenêtre de dates) ;
  3. parcourir leurs événements filtrés par date (1 an d'historique + à venir) ;
  4. ne garder que ceux réellement localisés dans la ville (``location.city``) ;
  5. dédoublonner par ``uid`` et sauvegarder le JSON brut dans ``data/raw/events.json``.

Le nettoyage / la structuration (pandas → parquet) relèvent de l'étape 2.2 (``preprocessing.py``).

Usage :
    uv run python scripts/fetch_events.py
    uv run python scripts/fetch_events.py --city Lyon --target-events 1000
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from rag.config import settings
from rag.data_loader import OpenAgendaClient


def _normalize(text: str) -> str:
    """Minuscule + sans accents, pour comparer des noms de villes."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.strip().lower()


def _city_matches(event_city: str | None, target: str) -> bool:
    """Vrai si la ville de l'événement correspond à la ville cible.

    Accepte les arrondissements (« Paris 11e ») : on exige un préfixe suivi d'une
    frontière (fin de chaîne, espace, chiffre ou tiret) pour éviter « Parisot ».
    """
    if not event_city:
        return False
    city = _normalize(event_city)
    tgt = _normalize(target)
    if city == tgt:
        return True
    if city.startswith(tgt):
        rest = city[len(tgt):]
        return rest[0] in " -0123456789" if rest else True
    return False


def fetch(client: OpenAgendaClient, *, city: str, since: str,
          max_agendas: int, target_events: int, per_agenda_max: int) -> list[dict]:
    print(f"Recherche d'agendas pour {city!r}…")
    agendas = client.search_agendas(city, limit=max_agendas)
    print(f"  {len(agendas)} agendas candidats récupérés.")

    print("Classement des agendas par volume d'événements…")
    ranked: list[tuple[dict, int]] = []
    for a in agendas:
        try:
            total = client.count_upcoming(a["uid"], since=since)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! agenda {a.get('uid')} ignoré ({exc})")
            continue
        if total:
            ranked.append((a, total))
    ranked.sort(key=lambda t: t[1], reverse=True)
    print(f"  {len(ranked)} agendas avec des événements sur la fenêtre.")

    seen: set = set()
    kept: list[dict] = []
    for a, total in ranked:
        if len(kept) >= target_events:
            break
        uid = a["uid"]
        matched = 0
        # On borne aussi le parcours (scan_cap) pour ne pas dérouler un énorme agenda
        # dont peu d'événements seraient dans la ville cible.
        scan_cap = per_agenda_max * 4
        for ev in client.iter_events(uid, since=since, max_events=scan_cap):
            ev_uid = ev.get("uid")
            if ev_uid in seen:
                continue
            location = ev.get("location") or {}
            if not _city_matches(location.get("city"), city):
                continue
            seen.add(ev_uid)
            kept.append(ev)
            matched += 1
            if matched >= per_agenda_max or len(kept) >= target_events:
                break
        print(f"  agenda {uid:>10} {a.get('title', '')[:40]:40.40} | "
              f"total={total:>5} | gardés({city})={matched}")
    return kept


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Récupère les événements Open Agenda (étape 2.1).")
    parser.add_argument("--city", default=settings.events_city)
    parser.add_argument("--months-back", type=int, default=settings.events_months_back,
                        help="Profondeur d'historique en mois (énoncé : 1 an).")
    parser.add_argument("--max-agendas", type=int, default=60,
                        help="Nombre max d'agendas candidats à scanner.")
    parser.add_argument("--target-events", type=int, default=1500,
                        help="Nombre cible d'événements à collecter (borne l'indexation).")
    parser.add_argument("--per-agenda-max", type=int, default=300,
                        help="Plafond d'événements gardés par agenda (favorise la diversité).")
    parser.add_argument("--out", default=str(settings.raw_data_path))
    args = parser.parse_args(argv)

    if not settings.openagenda_api_key:
        print("OPENAGENDA_API_KEY manquante (.env.local).", file=sys.stderr)
        return 1

    since_dt = datetime.now() - timedelta(days=round(args.months_back * 30.44))
    since = since_dt.strftime("%Y-%m-%dT00:00:00")
    print(f"=== Récupération Open Agenda — ville={args.city} | depuis {since} (+ à venir) ===")

    client = OpenAgendaClient(settings.openagenda_api_key)
    events = fetch(client, city=args.city, since=since, max_agendas=args.max_agendas,
                   target_events=args.target_events, per_agenda_max=args.per_agenda_max)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {
            "city": args.city,
            "since": since,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "count": len(events),
            "source": "openagenda_v2",
        },
        "events": events,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(events)} événements sauvegardés -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
