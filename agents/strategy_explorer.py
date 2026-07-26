"""
StrategyExplorer — Teste des variations de KB-v2.1 sur les 6 paires crypto.
Demande contexte à MemoryAgent → backteste → rapporte.

⚠️ SOURCE DE DONNÉES — changement du 2026-07-25
   Cet explorateur utilisait yfinance. Deux conséquences mesurées :

   1. Désalignement backtest/exécution : backtest sur données Yahoo, exécution
      sur Binance. Un backtest sur une source A déployé sur une source B n'est
      pas interprétable.
   2. Historique intraday tronqué : yfinance plafonne le 15m à 60 jours. La
      variante KB_15m a donc été « validée » sur 60 jours de données, puis
      s'est révélée perdante en live (PF 0.465).

   Ces deux défauts, combinés à l'absence de validation.py dans la boucle,
   expliquent les 10 fausses stratégies du sweep de mai 2026.

   Source unique désormais : core/data_source.py (Binance + cache TradingView).
   Yahoo Finance est retiré et ne doit pas être réintroduit.
"""
import sys
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
import validation
from core.data_source import DataSourceError, load

VAULT = Path(__file__).parent.parent / "vault"

# Symboles Binance directs — plus de table de correspondance vers Yahoo :
# la source du backtest est désormais celle de l'exécution.
PAIRS = {
    "BTCUSDT": "BTCUSDT",
    "ETHUSDT": "ETHUSDT",
    "SOLUSDT": "SOLUSDT",
    "LINKUSDT": "LINKUSDT",
    "NEARUSDT": "NEARUSDT",
    "ATOMUSDT": "ATOMUSDT",
}
INTERVAL = "1h"
PERIOD_DAYS = 365  # borne par défaut ; Binance fournit l'historique complet


# ── Variations à explorer (ordre priorisé) ─────────────────────────────────────
BASE = {
    "ema_fast": 7, "ema_slow": 21, "kijun_len": 26,
    "atr_len": 14, "atr_mult": 1.5, "rr": 2.0,
    "ema_sep_pct": 0.3, "cooldown_bars": 5, "atr_min_pct": 0.5,
    "use_rsi": False, "use_adx": False, "use_macd": False,
    "use_volume": False, "use_supertrend": False, "rsi_ob": 65, "rsi_os": 35,
    "_parent": "KB-v2.1",
}

# Base optimisé (résultat Round 0)
BEST = {**BASE,
    "ema_sep_pct": 0.15, "cooldown_bars": 3, "atr_min_pct": 0.3, "rr": 3.0,
    "_parent": "KB_LOOSE_RR2.5_RR3.0",
}

PREDEFINED_VARIATIONS = [
    # ── Round 0 (déjà testées — skippées si mémoire présente) ─────────────────
    {**BASE, "_name": "KB_BASE",       "_desc": "Baseline EMA7/21+Kijun"},
    {**BASE, "_name": "KB_RSI",        "_desc": "+Filtre RSI 35/65",          "use_rsi": True},
    {**BASE, "_name": "KB_ADX",        "_desc": "+Filtre ADX>25",             "use_adx": True},
    {**BASE, "_name": "KB_MACD",       "_desc": "+Confirm MACD direction",    "use_macd": True},
    {**BASE, "_name": "KB_VOL",        "_desc": "+Volume >1.5x MA20",         "use_volume": True},
    {**BASE, "_name": "KB_RR3",        "_desc": "RR=3.0",                     "rr": 3.0},
    {**BASE, "_name": "KB_EMA5_13",    "_desc": "EMA5/13 plus rapide",        "ema_fast": 5, "ema_slow": 13, "cooldown_bars": 3},
    {**BASE, "_name": "KB_EMA10_30",   "_desc": "EMA10/30 plus lent",         "ema_fast": 10, "ema_slow": 30, "cooldown_bars": 7},
    {**BASE, "_name": "KB_ST",         "_desc": "SuperTrend(10,3) replace EMA","use_supertrend": True},
    {**BASE, "_name": "KB_RSI_RR3",    "_desc": "+RSI +RR3",                  "use_rsi": True, "rr": 3.0},
    {**BASE, "_name": "KB_ADX_MACD",   "_desc": "+ADX+MACD double confirm",   "use_adx": True, "use_macd": True},
    {**BASE, "_name": "KB_COMPOSITE",  "_desc": "RSI+ADX+MACD+VOL",
     "use_rsi": True, "use_adx": True, "use_macd": True, "use_volume": True},
    {**BASE, "_name": "KB_TIGHT",      "_desc": "Filtres serrés",
     "ema_sep_pct": 0.6, "cooldown_bars": 8, "atr_min_pct": 0.8},
    {**BASE, "_name": "KB_LOOSE",      "_desc": "Filtres souples",
     "ema_sep_pct": 0.15, "cooldown_bars": 3, "atr_min_pct": 0.3},
    {**BASE, "_name": "KB_KIJUN52",    "_desc": "Kijun 52 (biais long terme)", "kijun_len": 52},

    # ── Round 1 : Session filter ───────────────────────────────────────────────
    # Crypto actif 8-22 UTC (London+NY). Évite dead zone asiatique 0-8 UTC.
    {**BEST, "_name": "KB_SESSION",    "_desc": "Session 8-22 UTC seulement", "use_session": True},
    {**BEST, "_name": "KB_SESSION_RSI","_desc": "Session+RSI",                "use_session": True, "use_rsi": True},

    # ── Round 1 : Bollinger Band squeeze ──────────────────────────────────────
    # Squeeze = BB étroites (compression) → attendre breakout EMA
    {**BEST, "_name": "KB_BB_SQ",      "_desc": "BB squeeze avant entrée",    "use_bb_squeeze": True},
    {**BEST, "_name": "KB_BB_SQ_RSI",  "_desc": "BB squeeze + RSI",           "use_bb_squeeze": True, "use_rsi": True},

    # ── Round 1 : Stochastic RSI ───────────────────────────────────────────────
    {**BEST, "_name": "KB_STOCH",      "_desc": "Stoch RSI filtre entrée",    "use_stoch": True},
    {**BEST, "_name": "KB_STOCH_ADX",  "_desc": "Stoch RSI + ADX>25",        "use_stoch": True, "use_adx": True},

    # ── Round 1 : VWAP hebdomadaire ───────────────────────────────────────────
    {**BEST, "_name": "KB_VWAP",       "_desc": "VWAP hebdo comme Kijun alt", "use_vwap": True},

    # ── Round 1 : RR agressif ─────────────────────────────────────────────────
    {**BEST, "_name": "KB_RR4",        "_desc": "RR=4.0 (TP plus loin)",      "rr": 4.0},
    {**BEST, "_name": "KB_RR4_SESSION","_desc": "RR4 + Session 8-22",         "rr": 4.0, "use_session": True},
    {**BEST, "_name": "KB_RR5",        "_desc": "RR=5.0 (pyramiding mindset)","rr": 5.0, "cooldown_bars": 2},

    # ── Round 1 : SL serré ────────────────────────────────────────────────────
    {**BEST, "_name": "KB_SL1_RR4",   "_desc": "SL=1xATR TP=4xATR",          "atr_mult": 1.0, "rr": 4.0},
    {**BEST, "_name": "KB_SL2_RR4",   "_desc": "SL=2xATR TP=4xATR plus large","atr_mult": 2.0, "rr": 4.0},

    # ── Round 1 : 15m TF ──────────────────────────────────────────────────────
    # Historique complet depuis le passage à Binance (yfinance plafonnait à 60j,
    # ce qui avait « validé » KB_15m sur un échantillon minuscule — PF 0.465 en live).
    {**BEST, "_name": "KB_15m",        "_desc": "TF 15m",                     "tf_resample": "15min", "cooldown_bars": 6},
    {**BEST, "_name": "KB_1h",         "_desc": "TF 1H (compromis 4H/15m)",   "tf_resample": "1h",    "cooldown_bars": 4},

    # ── Round 1 : Multi-TF confluence ─────────────────────────────────────────
    # Signal 4H MAIS seulement si 1D dans même direction
    {**BEST, "_name": "KB_MTF",        "_desc": "Confluence 4H+1D direction", "use_mtf_filter": True},
    {**BEST, "_name": "KB_MTF_SESSION","_desc": "MTF + Session 8-22",         "use_mtf_filter": True, "use_session": True},

    # ── Round 1 : Composite avancé ────────────────────────────────────────────
    {**BEST, "_name": "KB_ULTRA",      "_desc": "Session+BB+Stoch+RR4",
     "use_session": True, "use_bb_squeeze": True, "use_stoch": True, "rr": 4.0},
    {**BEST, "_name": "KB_ULTRA_MTF",  "_desc": "Session+MTF+BB+RR4",
     "use_session": True, "use_mtf_filter": True, "use_bb_squeeze": True, "rr": 4.0},
]


# ── Indicateurs ────────────────────────────────────────────────────────────────

def ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))

def atr(df, period=14):
    hi, lo, cl = df["High"], df["Low"], df["Close"]
    tr = pd.concat([hi - lo, (hi - cl.shift()).abs(), (lo - cl.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()

def macd(close, fast=12, slow=26, sig=9):
    m = ema(close, fast) - ema(close, slow)
    s = ema(m, sig)
    return m, s

def adx(df, period=14):
    hi, lo, cl = df["High"], df["Low"], df["Close"]
    up = hi.diff()
    dn = -lo.diff()
    pdm = up.where((up > dn) & (up > 0), 0.0)
    ndm = dn.where((dn > up) & (dn > 0), 0.0)
    at = atr(df, period)
    pdi = 100 * pdm.ewm(alpha=1 / period, adjust=False).mean() / at.replace(0, 1e-10)
    ndi = 100 * ndm.ewm(alpha=1 / period, adjust=False).mean() / at.replace(0, 1e-10)
    dx = (pdi - ndi).abs() / (pdi + ndi).replace(0, 1e-10) * 100
    return dx.ewm(alpha=1 / period, adjust=False).mean()

def stoch_rsi(close, rsi_period=14, stoch_period=14, smooth=3):
    r = rsi(close, rsi_period)
    r_min = r.rolling(stoch_period).min()
    r_max = r.rolling(stoch_period).max()
    k = (r - r_min) / (r_max - r_min + 1e-10) * 100
    return k.rolling(smooth).mean()  # %K smoothed

def bb_width(close, period=20, mult=2.0):
    ma = close.rolling(period).mean()
    std = close.rolling(period).std()
    return (std * 2 * mult) / ma * 100  # BB width % of price

def vwap_weekly(df):
    # Approximation VWAP hebdo : rolling 35 bars × 4H = ~140h = ~6 jours
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    vol = df["Volume"]
    return (tp * vol).rolling(35).sum() / vol.rolling(35).sum()

def supertrend(df, period=10, mult=3.0):
    hi, lo, cl = df["High"], df["Low"], df["Close"]
    at_ = atr(df, period)
    mid = (hi + lo) / 2
    up = mid + mult * at_
    dn = mid - mult * at_

    direction = pd.Series(1, index=df.index)
    for i in range(1, len(df)):
        if cl.iloc[i] > up.iloc[i - 1]:
            direction.iloc[i] = 1
        elif cl.iloc[i] < dn.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
    return direction  # 1=bull, -1=bear


# ── Backtest ───────────────────────────────────────────────────────────────────

def run_backtest(df_1h: pd.DataFrame, params: dict) -> dict:
    tf = params.get("tf_resample", "4h")
    df = (
        df_1h.resample(tf)
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        .dropna()
    )
    if len(df) < 50:
        return {"error": "Pas assez de données"}

    cl = df["Close"]
    p = params

    # Indicateurs de base
    e_fast = ema(cl, p["ema_fast"])
    e_slow = ema(cl, p["ema_slow"])
    kijun = (df["High"].rolling(p["kijun_len"]).max() + df["Low"].rolling(p["kijun_len"]).min()) / 2
    at_ = atr(df, p["atr_len"])
    ema_sep = (e_fast - e_slow).abs() / cl * 100
    atr_pct = at_ / cl * 100

    # Filtres optionnels
    rsi_v = rsi(cl, 14) if p.get("use_rsi") else None
    adx_v = adx(df, 14) if p.get("use_adx") else None
    macd_l, macd_s = macd(cl) if p.get("use_macd") else (None, None)
    vol_ma = df["Volume"].rolling(20).mean() if p.get("use_volume") else None
    st_dir = supertrend(df) if p.get("use_supertrend") else None
    stoch_v = stoch_rsi(cl) if p.get("use_stoch") else None
    bb_w = bb_width(cl) if p.get("use_bb_squeeze") else None
    vwap_v = vwap_weekly(df) if p.get("use_vwap") else None
    # Session filter: heure UTC de la bougie
    if p.get("use_session"):
        session_ok = pd.Series(df.index.hour, index=df.index).isin(range(8, 22))
    else:
        session_ok = None
    # MTF filter: biais journalier (EMA20 vs EMA50 sur le df 1h agrégé en 1D)
    if p.get("use_mtf_filter"):
        df_1d = df_1h.resample("1D").agg({"Close": "last"}).dropna()
        ema20_1d = ema(df_1d["Close"], 20).reindex(df.index, method="ffill")
        ema50_1d = ema(df_1d["Close"], 50).reindex(df.index, method="ffill")
        mtf_bull = ema20_1d > ema50_1d
        mtf_bear = ema20_1d < ema50_1d
    else:
        mtf_bull = mtf_bear = None

    # Signaux
    if p.get("use_supertrend"):
        cross_up = (st_dir == 1) & (st_dir.shift(1) == -1)
        cross_down = (st_dir == -1) & (st_dir.shift(1) == 1)
        bull = st_dir == 1
        bear = st_dir == -1
    else:
        cross_up = (e_fast > e_slow) & (e_fast.shift(1) <= e_slow.shift(1))
        cross_down = (e_fast < e_slow) & (e_fast.shift(1) >= e_slow.shift(1))
        bull = cl > kijun
        bear = cl < kijun

    # Filtres qualité
    qual = (ema_sep >= p["ema_sep_pct"]) & (atr_pct >= p["atr_min_pct"])
    if rsi_v is not None:
        qual_long = qual & (rsi_v < p.get("rsi_ob", 65))
        qual_short = qual & (rsi_v > p.get("rsi_os", 35))
    else:
        qual_long = qual_short = qual
    if adx_v is not None:
        adx_ok = adx_v > 25
        qual_long &= adx_ok
        qual_short &= adx_ok
    if macd_l is not None:
        qual_long &= (macd_l > macd_s)
        qual_short &= (macd_l < macd_s)
    if vol_ma is not None:
        vol_ok = df["Volume"] > vol_ma * 1.5
        qual_long &= vol_ok
        qual_short &= vol_ok
    if stoch_v is not None:
        qual_long  &= (stoch_v < 80)   # pas en zone overbought
        qual_short &= (stoch_v > 20)   # pas en zone oversold
    if bb_w is not None:
        bb_squeeze_ok = bb_w < bb_w.rolling(50).mean()  # compression actuelle
        qual_long  &= bb_squeeze_ok
        qual_short &= bb_squeeze_ok
    if vwap_v is not None:
        qual_long  &= (cl > vwap_v)
        qual_short &= (cl < vwap_v)
    if session_ok is not None:
        qual_long  &= session_ok
        qual_short &= session_ok
    if mtf_bull is not None:
        qual_long  &= mtf_bull
        qual_short &= mtf_bear

    long_sig = cross_up & bull & qual_long
    short_sig = cross_down & bear & qual_short

    # Simulation trades
    capital = 10000.0
    equity = [capital]
    trades = []
    cooldown = 0
    i = 0
    idx = df.index.tolist()

    while i < len(df) - 1:
        if cooldown > 0:
            cooldown -= 1
            equity.append(equity[-1])
            i += 1
            continue

        entry_price = cl.iloc[i]
        sl_dist = at_.iloc[i] * p["atr_mult"]
        in_trade = False

        if long_sig.iloc[i]:
            sl = entry_price - sl_dist
            tp = entry_price + sl_dist * p["rr"]
            for j in range(i + 1, min(i + 100, len(df))):
                if df["High"].iloc[j] >= tp:
                    pct = (tp / entry_price - 1) - 0.002
                    trades.append({"type": "L", "pct": pct, "date": str(idx[j])})
                    capital *= (1 + pct)
                    cooldown = p["cooldown_bars"]
                    i = j
                    in_trade = True
                    break
                elif df["Low"].iloc[j] <= sl:
                    pct = (sl / entry_price - 1) - 0.002
                    trades.append({"type": "L", "pct": pct, "date": str(idx[j])})
                    capital *= (1 + pct)
                    cooldown = p["cooldown_bars"]
                    i = j
                    in_trade = True
                    break

        elif short_sig.iloc[i]:
            sl = entry_price + sl_dist
            tp = entry_price - sl_dist * p["rr"]
            for j in range(i + 1, min(i + 100, len(df))):
                if df["Low"].iloc[j] <= tp:
                    pct = (entry_price / tp - 1) - 0.002
                    trades.append({"type": "S", "pct": pct, "date": str(idx[j])})
                    capital *= (1 + pct)
                    cooldown = p["cooldown_bars"]
                    i = j
                    in_trade = True
                    break
                elif df["High"].iloc[j] >= sl:
                    pct = -(entry_price / sl - 1) - 0.002
                    trades.append({"type": "S", "pct": pct, "date": str(idx[j])})
                    capital *= (1 + pct)
                    cooldown = p["cooldown_bars"]
                    i = j
                    in_trade = True
                    break

        if not in_trade:
            equity.append(capital)
        else:
            equity.append(capital)
        i += 1

    # Métriques
    if not trades:
        return {"error": "Aucun trade"}

    total_return = (capital / 10000 - 1) * 100
    span_days = max((df.index[-1] - df.index[0]).days, 1)
    n_months = span_days / 30
    monthly_return = ((capital / 10000) ** (1 / n_months) - 1) * 100
    wins = [t for t in trades if t["pct"] > 0]
    losses = [t for t in trades if t["pct"] <= 0]
    win_rate = len(wins) / len(trades) * 100
    avg_win = np.mean([t["pct"] for t in wins]) * 100 if wins else 0
    avg_loss = np.mean([t["pct"] for t in losses]) * 100 if losses else 0
    gross_win = sum(t["pct"] for t in wins)
    gross_loss = abs(sum(t["pct"] for t in losses))
    profit_factor = gross_win / gross_loss if gross_loss > 0 else 999

    # Drawdown
    eq = pd.Series(equity)
    roll_max = eq.cummax()
    dd = (eq - roll_max) / roll_max * 100
    max_dd = dd.min()

    # Sharpe (approx)
    rets = pd.Series([t["pct"] for t in trades])
    sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0

    return {
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": round(win_rate, 1),
        "total_return_pct": round(total_return, 2),
        "monthly_return_pct": round(monthly_return, 2),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio": round(float(sharpe), 2),
        "final_capital": round(capital, 2),
    }


# ── StrategyExplorer ──────────────────────────────────────────────────────────

class StrategyExplorer:
    def __init__(self, memory_agent):
        self.name = "StrategyExplorer"
        self.mem = memory_agent
        self._log(f"**{self.name}** — prêt. {len(PREDEFINED_VARIATIONS)} variations prédéfinies.")

    def _log(self, msg: str):
        with open(VAULT / "AGENT_LOG.md", "a") as f:
            f.write(msg + "\n")

    def _fetch_data(self, symbol: str) -> pd.DataFrame | None:
        """Données via core.data_source — même source que l'exécution.

        Colonnes capitalisées en sortie : le moteur de backtest historique de
        ce fichier attend le format yfinance (Open/High/Low/Close/Volume). La
        source change, le contrat interne reste.
        """
        start = (datetime.now() - timedelta(days=PERIOD_DAYS + 30)).strftime("%Y-%m-%d")
        try:
            df = load(symbol, INTERVAL, start=start)
        except DataSourceError as e:
            self._log(f"**{self.name}** → ⚠️ données indisponibles {symbol} : {e}")
            return None
        if len(df) < 100:
            return None
        return df.rename(columns=str.capitalize)

    def explore_one(self, variation: dict) -> dict:
        """Backteste une variation sur toutes les paires, retourne métriques agrégées."""
        name = variation.get("_name", "UNKNOWN")
        desc = variation.get("_desc", "")
        self._log(f"**{self.name}** → 🔍 test `{name}` — {desc}")

        if self.mem.already_explored(name):
            self._log(f"**{self.name}** → ⏩ `{name}` déjà exploré, skip")
            return {}

        all_results = []
        oos_results = []
        for tv_sym, sym in PAIRS.items():
            df = self._fetch_data(sym)
            if df is None:
                self._log(f"**{self.name}** → ⚠️ pas de data pour {sym}")
                continue
            # Walk-forward : IS/OOS jamais mélangés. On score sur IS, l'OOS
            # sert uniquement à détecter l'overfitting (jamais utilisé pour choisir).
            wf = validation.walk_forward_split(run_backtest, df, variation)
            result, oos = wf["is"], wf["oos"]
            if "error" not in result:
                result["symbol"] = tv_sym
                all_results.append(result)
                degr = validation.oos_degradation_pct(result, oos)
                oos["symbol"] = tv_sym
                oos["degradation_pct"] = degr
                oos_results.append(oos)
                degr_str = f"{degr:+.0f}%" if degr is not None else "N/A"
                self._log(
                    f"**{self.name}** → {tv_sym}: {result['monthly_return_pct']:.1f}%/mois IS "
                    f"| WR {result['win_rate_pct']:.0f}% | {result['total_trades']} trades "
                    f"| OOS degr {degr_str}"
                )

        if not all_results:
            return {}

        # Agrégation (moyenne pondérée par nombre de trades)
        def wavg(key):
            total_w = sum(r["total_trades"] for r in all_results)
            if total_w == 0:
                return 0
            return sum(r[key] * r["total_trades"] for r in all_results) / total_w

        valid_degr = [o["degradation_pct"] for o in oos_results if o["degradation_pct"] is not None]
        oos_valid = [o for o in oos_results if "error" not in o and o.get("total_trades", 0) > 0]

        agg = {
            "total_trades": sum(r["total_trades"] for r in all_results),
            "winning_trades": sum(r["winning_trades"] for r in all_results),
            "losing_trades": sum(r["losing_trades"] for r in all_results),
            "win_rate_pct": round(wavg("win_rate_pct"), 1),
            "monthly_return_pct": round(wavg("monthly_return_pct"), 2),
            "total_return_pct": round(wavg("total_return_pct"), 2),
            "profit_factor": round(wavg("profit_factor"), 2),
            "max_drawdown_pct": round(wavg("max_drawdown_pct"), 2),
            "sharpe_ratio": round(wavg("sharpe_ratio"), 2),
            "pairs_tested": len(all_results),
            "per_pair": {r["symbol"]: {k: v for k, v in r.items() if k != "symbol"} for r in all_results},
            # ── Out-of-sample (garde-fou anti-overfitting) ──────────────────
            "oos_monthly_return_pct": round(
                sum(o["monthly_return_pct"] for o in oos_valid) / len(oos_valid), 2
            ) if oos_valid else None,
            "oos_degradation_pct": round(sum(valid_degr) / len(valid_degr), 1) if valid_degr else None,
            "oos_pairs_with_trades": len(oos_valid),
        }

        # Reporting vers MemoryAgent
        clean_params = {k: v for k, v in variation.items() if not k.startswith("_")}
        clean_params["_parent"] = variation.get("_parent", "KB-v2.1")
        self.mem.receive_result(name, clean_params, agg)
        return agg

    def stability_check(self, params: dict, n_sims: int = 15) -> dict:
        """
        Monte Carlo sur le gagnant final : perturbe les params ±10%, revérifie
        que la perf tient. Appelé une seule fois sur le candidat final, pas sur
        chaque variation testée (coûteux, utile seulement pour la décision finale).
        """
        stabilities = []
        for tv_sym, sym in PAIRS.items():
            df = self._fetch_data(sym)
            if df is None:
                continue
            r = validation.monte_carlo_stability(run_backtest, df, params, n_sims=n_sims)
            if "error" not in r:
                r["symbol"] = tv_sym
                stabilities.append(r)

        if not stabilities:
            return {"error": "Aucune simulation valide"}

        return {
            "mc_stability_pct_avg": round(
                sum(s["mc_stability_pct"] for s in stabilities) / len(stabilities), 1
            ),
            "per_pair": stabilities,
        }

    def explore_all_predefined(self):
        """Parcourt toutes les variations prédéfinies."""
        self._log(f"\n**{self.name}** → 🚀 démarrage exploration {len(PREDEFINED_VARIATIONS)} variations\n")
        for var in PREDEFINED_VARIATIONS:
            self.explore_one(var)

    def explore_suggested(self):
        """Demande des suggestions à MemoryAgent et les explore."""
        suggestions = self.mem.suggest_next({})
        if not suggestions:
            self._log(f"**{self.name}** → pas de nouvelles suggestions de MemoryAgent")
            return
        self._log(f"**{self.name}** → 🤝 {len(suggestions)} suggestions reçues de MemoryAgent")
        for s in suggestions:
            name = s.get("_name_hint", f"KB_SUGGESTED_{len(self.mem.memory['explored'])}")
            s["_name"] = name
            s["_parent"] = self.mem.memory.get("best", {}).get("name", "KB-v2.1")
            self.explore_one(s)

    def explore_suggested_llm(self, n: int = 3):
        """Demande à Claude n nouvelles combinaisons créatives et les explore."""
        suggestions = self.mem.suggest_next_llm(n=n)
        if not suggestions:
            self._log(f"**{self.name}** → pas de suggestions LLM (clé API absente ou erreur)")
            return
        self._log(f"**{self.name}** → 🧠 {len(suggestions)} suggestions LLM reçues")
        for s in suggestions:
            name = s.get("_name_hint", f"KB_LLM_{len(self.mem.memory['explored'])}")
            s["_name"] = name
            s["_parent"] = self.mem.memory.get("best", {}).get("name", "KB-v2.1")
            self.explore_one(s)
