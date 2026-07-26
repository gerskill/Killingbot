"""
Market Regime Detector — filtre de régime en amont de toute décision de trade.

Principe : avant de chercher une confluence, déterminer l'état du marché.
    TRENDING  → stratégies breakout/momentum (KB_15m, KB_SVWAP, PP-ST)
    RANGING   → mean reversion uniquement (ou rien si non implémentée)
    UNDECIDED → NE PAS TRADER (l'abstention est une position)

Trois mesures indépendantes, vote majoritaire (2/3) :
    1. ADX             — force directionnelle (leçon PP-ST : ADX>=20 change tout)
    2. BB Width slope  — expansion/contraction de la volatilité
    3. Efficiency Ratio (Kaufman) — déplacement net / chemin parcouru

Usage :
    from core.market_regime import detect_market_regime
    regime = detect_market_regime(df)          # df: colonnes open/high/low/close
    if regime["regime"] == "UNDECIDED":
        skip_trade()

CLI (test rapide sur data Binance publique) :
    python3 core/market_regime.py BTCUSDT 15m
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

# Seuils — mutables par journal_agent (1-2 par itération, comme le reste)
ADX_TREND_MIN = 22        # au-dessus : directionnel
ADX_RANGE_MAX = 17        # en dessous : range
ER_TREND_MIN = 0.30       # Efficiency Ratio : > 0.30 = déplacement efficace
ER_RANGE_MAX = 0.15
BBW_SLOPE_LOOKBACK = 10   # barres pour la pente de largeur des bandes
ADX_LEN = 14
ER_LEN = 20
BB_LEN = 20


def _adx(df: pd.DataFrame, length: int = ADX_LEN) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm = (high.diff()).clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    # DM directionnel : ne garder que le dominant
    plus_dm[plus_dm < minus_dm] = 0.0
    minus_dm[minus_dm <= plus_dm] = 0.0
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / length, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / length, adjust=False).mean()


def _efficiency_ratio(close: pd.Series, length: int = ER_LEN) -> pd.Series:
    """Kaufman ER : |déplacement net| / somme des |déplacements barre à barre|.
    1.0 = ligne droite (trend parfait), ~0 = bruit pur (range)."""
    net = (close - close.shift(length)).abs()
    path = close.diff().abs().rolling(length).sum()
    return net / path.replace(0, np.nan)


def _bbw_slope(close: pd.Series, length: int = BB_LEN,
               lookback: int = BBW_SLOPE_LOOKBACK) -> pd.Series:
    """Pente de la largeur des Bollinger Bands. >0 = expansion (breakout/trend),
    <0 = contraction (compression/range)."""
    ma = close.rolling(length).mean()
    sd = close.rolling(length).std()
    bbw = (4 * sd) / ma  # largeur normalisée (±2σ)
    return bbw - bbw.shift(lookback)


def detect_market_regime(df: pd.DataFrame) -> dict:
    """Retourne le régime du marché sur la dernière barre close.

    df : DataFrame avec colonnes open, high, low, close (index chronologique).
         Minimum ~60 barres pour des mesures stables.

    Retour :
        {"regime": "TRENDING"|"RANGING"|"UNDECIDED",
         "direction": "UP"|"DOWN"|None,
         "votes": {...}, "metrics": {...}, "tradeable": bool}
    """
    if len(df) < max(ADX_LEN, ER_LEN, BB_LEN) * 3:
        return {"regime": "UNDECIDED", "direction": None, "votes": {},
                "metrics": {"error": f"besoin >= {max(ADX_LEN, ER_LEN, BB_LEN) * 3} barres, reçu {len(df)}"},
                "tradeable": False}

    close = df["close"]
    adx_val = float(_adx(df).iloc[-1])
    er_val = float(_efficiency_ratio(close).iloc[-1])
    bbw_val = float(_bbw_slope(close).iloc[-1])

    # Vote de chaque mesure : TREND / RANGE / abstention
    votes = {
        "adx": "TREND" if adx_val >= ADX_TREND_MIN else "RANGE" if adx_val <= ADX_RANGE_MAX else "NEUTRAL",
        "efficiency_ratio": "TREND" if er_val >= ER_TREND_MIN else "RANGE" if er_val <= ER_RANGE_MAX else "NEUTRAL",
        "bbw_slope": "TREND" if bbw_val > 0 else "RANGE",
    }
    trend_votes = sum(1 for v in votes.values() if v == "TREND")
    range_votes = sum(1 for v in votes.values() if v == "RANGE")

    if trend_votes >= 2:
        regime = "TRENDING"
    elif range_votes >= 2:
        regime = "RANGING"
    else:
        regime = "UNDECIDED"

    # Direction du trend : pente du prix sur la fenêtre ER
    direction = None
    if regime == "TRENDING":
        direction = "UP" if close.iloc[-1] > close.iloc[-ER_LEN] else "DOWN"

    return {
        "regime": regime,
        "direction": direction,
        "votes": votes,
        "metrics": {
            "adx": round(adx_val, 2),
            "efficiency_ratio": round(er_val, 3),
            "bbw_slope": round(bbw_val, 5),
        },
        # Condition stricte : UNDECIDED = pas de trade, point.
        "tradeable": regime != "UNDECIDED",
    }


# ── Data helper + CLI ────────────────────────────────────────────────────────

def fetch_binance_klines(symbol: str = "BTCUSDT", interval: str = "15m",
                         limit: int = 200) -> pd.DataFrame:
    """Klines Binance publiques (pas d'API key). Pour test/CLI uniquement."""
    import urllib.request
    url = (f"https://api.binance.com/api/v3/klines"
           f"?symbol={symbol}&interval={interval}&limit={limit}")
    with urllib.request.urlopen(url, timeout=15) as r:
        raw = json.load(r)
    df = pd.DataFrame(raw, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "qav", "trades", "tbb", "tbq", "ignore"])
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms")
    return df[["ts", "open", "high", "low", "close", "volume"]]


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    interval = sys.argv[2] if len(sys.argv) > 2 else "15m"
    frame = fetch_binance_klines(symbol, interval)
    result = detect_market_regime(frame)
    result["symbol"] = symbol
    result["interval"] = interval
    result["last_close"] = float(frame["close"].iloc[-1])
    result["last_bar"] = str(frame["ts"].iloc[-1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
