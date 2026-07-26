"""
Logique de signal — pp_st_btc_4h

Portage Python de strategy.pine (Pine v6). Le Pine reste la référence : c'est
lui qui tourne en production et qui a passé G6. Ce portage sert à la boucle de
recherche — optimisation, portes G1→G5, variantes — sans dépendre de TradingView.

Architecture (identique au Pine) :
    SIGNAL   Pivot Point SuperTrend, retournement de tendance
    FILTRE 1 EMA200 — long uniquement au-dessus
    FILTRE 2 ADX ≥ seuil — écarte les phases de range
    SORTIE   retournement PP-ST OU passage sous l'EMA200

Anti-look-ahead : un pivot situé en barre i n'est confirmé qu'en barre i+prd,
puisqu'il faut prd barres à droite pour savoir que c'en était un. Le code
respecte ce décalage — c'est le point le plus facile à rater dans un portage
de Pine, et celui qui gonfle silencieusement un backtest.
"""
import numpy as np
import pandas as pd


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    """ATR de Wilder — ta.atr() de Pine lisse en RMA, pas en SMA."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift()
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()],
                   axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ADX — équivalent de la 3ᵉ valeur de ta.dmi(period, period)."""
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
                        index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
                         index=df.index)

    prev_close = close.shift()
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()],
                   axis=1).max(axis=1)

    atr_w = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_w.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_w.replace(0, np.nan)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def _pivot_center(df: pd.DataFrame, prd: int) -> pd.Series:
    """Centre pondéré des pivots — `center := (center * 2 + lastpp) / 3` en Pine.

    Un pivot en position p n'est visible qu'à partir de p+prd. La valeur n'est
    donc écrite qu'à cet instant, jamais rétroactivement.
    """
    high, low = df["high"].values, df["low"].values
    n = len(df)
    center = np.full(n, np.nan)
    current = np.nan

    for i in range(prd, n):
        p = i - prd  # barre candidate, confirmée à l'instant i
        if p - prd >= 0:
            window = slice(p - prd, min(p + prd + 1, n))
            last_pp = np.nan
            if high[p] == np.max(high[window]):
                last_pp = high[p]
            elif low[p] == np.min(low[window]):
                last_pp = low[p]

            if not np.isnan(last_pp):
                current = last_pp if np.isnan(current) else (current * 2 + last_pp) / 3
        center[i] = current

    return pd.Series(center, index=df.index)


def pp_supertrend(df: pd.DataFrame, prd: int, factor: float, atr_len: int) -> pd.Series:
    """Tendance PP-SuperTrend : +1 haussière, −1 baissière."""
    center = _pivot_center(df, prd)
    atr = _atr(df, atr_len)

    up_band = (center - factor * atr).values
    dn_band = (center + factor * atr).values
    close = df["close"].values
    n = len(df)

    t_up = np.full(n, np.nan)
    t_down = np.full(n, np.nan)
    trend = np.ones(n, dtype=int)

    for i in range(1, n):
        prev_up = t_up[i - 1] if not np.isnan(t_up[i - 1]) else 0.0
        prev_dn = t_down[i - 1] if not np.isnan(t_down[i - 1]) else 0.0
        prev_close = close[i - 1]

        u, d = up_band[i], dn_band[i]
        if np.isnan(u) or np.isnan(d):
            trend[i] = trend[i - 1]
            continue

        t_up[i] = max(u, prev_up) if prev_close > prev_up else u
        t_down[i] = min(d, prev_dn) if prev_close < prev_dn else d

        if prev_dn != 0.0 and close[i] > prev_dn:
            trend[i] = 1
        elif prev_up != 0.0 and close[i] < prev_up:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]

    return pd.Series(trend, index=df.index)


def signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Renvoie entry_long / exit_long. Ne lit que des données closes."""
    prd = int(params.get("pivot_period", 2))
    factor = float(params.get("atr_factor", 5.0))
    atr_len = int(params.get("pp_atr_period", 14))
    adx_min = float(params.get("adx_min", 20))
    ema_len = int(params.get("ema_len", 200))

    trend = pp_supertrend(df, prd, factor, atr_len)
    ema = df["close"].ewm(span=ema_len, adjust=False).mean()
    adx = _adx(df, 14)

    bull_macro = df["close"] > ema
    trending = adx >= adx_min

    flip_up = (trend == 1) & (trend.shift() == -1)
    flip_dn = (trend == -1) & (trend.shift() == 1)

    entry_long = flip_up & bull_macro & trending
    exit_long = flip_dn | (~bull_macro)

    return pd.DataFrame({
        "entry_long": entry_long.fillna(False),
        "exit_long": exit_long.fillna(False),
    }, index=df.index)
