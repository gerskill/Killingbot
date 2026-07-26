"""
sovereign/context.py — Context loader (équivalent source de données de Sovereign)
Polls vault/memory.json + backtest results -> contexte pour templates Pine.
"""
import json
from pathlib import Path
from typing import Any

BASE  = Path(__file__).parent.parent
VAULT = BASE / "vault"
BACKTEST_DIR = BASE / "backtest" / "results"


def load() -> dict[str, Any]:
    """
    Agrège toutes les sources de contexte :
      - vault/memory.json      → meilleures stratégies connues
      - backtest/results/*.json → résultats récents
      - CLAUDE.md header       → paramètres communs top stratégies
    Retourne dict utilisé par le template engine.
    """
    ctx: dict[str, Any] = {
        "best_strategies": [],
        "common_params":   _default_params(),
        "backtest_results": [],
    }

    # Source 1 — vault memory
    mem_file = VAULT / "memory.json"
    if mem_file.exists():
        try:
            mem = json.loads(mem_file.read_text())
            results = mem.get("results", [])
            ctx["best_strategies"] = sorted(
                results, key=lambda r: r.get("metrics", {}).get("monthly_return_pct", 0), reverse=True
            )[:5]
            # Paramètres du meilleur
            if ctx["best_strategies"]:
                best = ctx["best_strategies"][0]
                ctx["common_params"].update(best.get("params", {}))
        except (json.JSONDecodeError, KeyError):
            pass

    # Source 2 — backtest results JSON
    if BACKTEST_DIR.exists():
        for f in sorted(BACKTEST_DIR.glob("*.json"))[-10:]:
            try:
                ctx["backtest_results"].append(json.loads(f.read_text()))
            except (json.JSONDecodeError, OSError):
                pass

    return ctx


def _default_params() -> dict:
    """Paramètres communs top stratégies (depuis CLAUDE.md)."""
    return {
        "ema_fast":     7,
        "ema_slow":     21,
        "kijun":        26,
        "atr_length":   14,
        "atr_mult":     1.5,
        "ema_sep_min":  0.15,
        "cooldown":     3,
        "atr_min_pct":  0.3,
        "rr_ratio":     2.5,
        "adx_min":      20,
    }
