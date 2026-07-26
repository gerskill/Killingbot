"""
sidecars/signal_filter.py — Validation signal (5 étapes TraderMorin)
Sidecar indépendant : reçoit payload webhook, retourne verdict + raison.
"""
from dataclasses import dataclass, field
from typing import Literal

VALID_SETUPS = {"A*", "B"}
VALID_DIRS   = {"LONG", "SHORT"}
VALID_TFS    = {"15", "60", "240", "1D", "4H", "1H", "15M"}
MIN_PRICE    = 0.0001

# Paires autorisées (whitelist)
ALLOWED_TICKERS = {
    "BTCUSD", "BTCUSDT", "ETHUSD", "ETHUSDT",
    "SOLUSD", "SOLUSDT", "XAUUSD", "NVDA",
    "AAPL", "SPX", "NQ1!", "ES1!",
}


@dataclass
class FilterResult:
    passed: bool
    setup: str
    rejection_reason: str = ""
    warnings: list[str] = field(default_factory=list)
    step_results: dict = field(default_factory=dict)


def validate(payload: dict) -> FilterResult:
    """
    5 étapes TraderMorin :
      1. Setup valide (A* ou B)
      2. Direction valide (LONG/SHORT)
      3. Ticker autorisé
      4. Timeframe reconnu
      5. Prix cohérent (> 0)
    """
    steps = {}
    warnings = []
    setup = str(payload.get("setup", "")).upper().strip()
    direction = str(payload.get("dir", "")).upper().strip()
    ticker = str(payload.get("ticker", "")).upper().strip()
    tf = str(payload.get("tf", "")).strip()
    price_raw = payload.get("price", "0")

    # Étape 1 — Setup
    steps["1_setup"] = setup in VALID_SETUPS
    if not steps["1_setup"]:
        return FilterResult(False, setup, f"Setup inconnu: '{setup}'. Attendu: {VALID_SETUPS}", warnings, steps)

    # Étape 2 — Direction
    steps["2_direction"] = direction in VALID_DIRS
    if not steps["2_direction"]:
        return FilterResult(False, setup, f"Direction invalide: '{direction}'", warnings, steps)

    # Étape 3 — Ticker
    steps["3_ticker"] = ticker in ALLOWED_TICKERS
    if not steps["3_ticker"]:
        warnings.append(f"Ticker '{ticker}' hors whitelist — signal accepté mais non prioritaire")

    # Étape 4 — Timeframe
    steps["4_timeframe"] = tf in VALID_TFS
    if not steps["4_timeframe"]:
        warnings.append(f"TF '{tf}' non standard")

    # Étape 5 — Prix
    try:
        price = float(price_raw)
        steps["5_price"] = price > MIN_PRICE
    except (ValueError, TypeError):
        steps["5_price"] = False

    if not steps["5_price"]:
        return FilterResult(False, setup, f"Prix invalide: '{price_raw}'", warnings, steps)

    return FilterResult(True, setup, warnings=warnings, step_results=steps)
