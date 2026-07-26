"""
Macro Kill Switch — bloque les nouvelles entrées autour des events macro à fort impact.

Principe : un FOMC/CPI/NFP annule n'importe quelle analyse technique. Dans la
fenêtre [-2h, +1h] autour d'un event high-impact, aucun nouveau trade.

Source : calendrier ForexFactory (feed public JSON, pas de clé API).
Cache disque 4h — le calendrier hebdo ne change presque jamais en intraday.
Fail-open : feed injoignable → on log, on ne bloque pas (même philosophie que
le regime filter : protéger, pas tuer le flux).

Usage :
    from core.macro_calendar import macro_block
    verdict = macro_block()
    if verdict["blocked"]:
        reject_signal(verdict["reason"])

CLI :
    python3 core/macro_calendar.py
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CACHE_FILE = Path(__file__).parent.parent / "vault" / ".macro_cache.json"
CACHE_TTL_S = 4 * 3600

# Fenêtre de blocage autour de l'event
BLOCK_BEFORE_H = 2.0   # pas de nouveau trade 2h avant
BLOCK_AFTER_H = 1.0    # ni 1h après (spike + spread élargi)

# Devises surveillées : USD pilote le crypto ; EUR pour la macro globale
WATCH_CURRENCIES = {"USD", "EUR"}
WATCH_IMPACT = {"High"}


def _fetch_calendar() -> list[dict]:
    """Feed hebdo, avec cache disque. Lève en cas d'échec réseau ET cache vide."""
    if CACHE_FILE.exists():
        age = time.time() - CACHE_FILE.stat().st_mtime
        if age < CACHE_TTL_S:
            return json.loads(CACHE_FILE.read_text())

    try:
        req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            events = json.load(r)
        CACHE_FILE.parent.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(events))
        return events
    except Exception:
        # Réseau KO : cache périmé accepté plutôt que rien
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text())
        raise


def upcoming_high_impact(within_hours: float = BLOCK_BEFORE_H) -> list[dict]:
    """Events high-impact dans la fenêtre [now - BLOCK_AFTER_H, now + within_hours]."""
    now = datetime.now(timezone.utc)
    lo = now - timedelta(hours=BLOCK_AFTER_H)
    hi = now + timedelta(hours=within_hours)
    hits = []
    for ev in _fetch_calendar():
        if ev.get("impact") not in WATCH_IMPACT:
            continue
        if ev.get("country") not in WATCH_CURRENCIES:
            continue
        try:
            ev_time = datetime.fromisoformat(ev["date"])
        except (KeyError, ValueError):
            continue
        if lo <= ev_time <= hi:
            hits.append({
                "title": ev.get("title", "?"),
                "currency": ev.get("country"),
                "time_utc": ev_time.astimezone(timezone.utc).isoformat(),
                "minutes_away": round((ev_time - now).total_seconds() / 60),
            })
    return hits


def macro_block() -> dict:
    """Verdict kill switch. Fail-open : erreur feed = pas de blocage, flag dans la réponse."""
    try:
        events = upcoming_high_impact()
        return {
            "blocked": len(events) > 0,
            "reason": f"{len(events)} event(s) macro high-impact dans la fenêtre" if events else None,
            "events": events,
            "feed_ok": True,
        }
    except Exception as e:
        return {"blocked": False, "reason": None, "events": [],
                "feed_ok": False, "error": str(e)[:200]}


if __name__ == "__main__":
    print(json.dumps(macro_block(), indent=2, ensure_ascii=False))
