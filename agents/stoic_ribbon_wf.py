"""
stoic_ribbon_wf.py — Walk-forward du système ruban STOIC 1-2-3.

Port fidèle de `pine_scripts/strategies/stoic_123_ribbon.pine` en Python, pour
faire tourner les garde-fous de `agents/validation.py` (walk-forward, deflated
Sharpe, Monte Carlo) — impossible à faire depuis TradingView, dont le Strategy
Tester ne sait pas séparer in-sample et out-of-sample.

Logique reproduite à l'identique :
  tendance : SMA50 > SMA200 et close > SMA200
  1 · structure : plus-haut des `brk_look` barres précédentes
  2 · pullback  : le prix a touché le ruban (SMA20) dans les `pb_bars` dernières
  3 · entrée    : clôture qui casse la structure ET repasse au-dessus du SMA10
  stop  : sous le ruban (SMA20) − buffer ATR
  cible : T1 2R (50 %), T2 3R (50 %), T3 5R (reste)
  sortie: cassure du SMA200

Usage :
    python agents/stoic_ribbon_wf.py                    # BTC seul
    python agents/stoic_ribbon_wf.py --full             # panier complet
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import validation

COMMISSION = 0.0004  # 0,04 % — même valeur que le script Pine
SLIPPAGE_BPS = 2

DEFAULTS = {
    "len1": 10, "len2": 20, "len50": 50, "len200": 200,
    "pb_bars": 6, "brk_look": 5,
    "sl_buf_atr": 0.5, "atr_len": 14,
    "t1_r": 2.0, "t2_r": 3.0, "t3_r": 5.0,
    "risk_pct": 0.75,          # moyenne golden 1 % / standard 0,5 %
    "use_shorts": 1,
}


# ── Indicateurs ─────────────────────────────────────────────────────────────

def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(int(n)).mean()


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / int(n), adjust=False).mean()


# ── Backtest ────────────────────────────────────────────────────────────────

def run_backtest(df: pd.DataFrame, params: dict) -> dict:
    """Signature compatible validation.py : (df, params) -> dict de métriques."""
    p = {**DEFAULTS, **params}
    if len(df) < int(p["len200"]) + 50:
        return {"error": "Pas assez de données"}

    c, h, l = df["Close"], df["High"], df["Low"]
    o = df["Open"]
    s10 = _sma(c, p["len1"])
    s20 = _sma(c, p["len2"])
    s50 = _sma(c, p["len50"])
    s200 = _sma(c, p["len200"])
    atr = _atr(df, p["atr_len"])

    up_trend = (s50 > s200) & (c > s200)
    down_trend = (s50 < s200) & (c < s200)

    brk = int(p["brk_look"])
    pb = int(p["pb_bars"])
    hi_n = h.rolling(brk).max().shift(1)
    lo_n = l.rolling(brk).min().shift(1)
    tagged_long = l.rolling(pb).min() <= s20
    tagged_short = h.rolling(pb).max() >= s20

    sig_long = up_trend & tagged_long & (c > hi_n) & (c > s10) & (c > o)
    sig_short = down_trend & tagged_short & (c < lo_n) & (c < s10) & (c < o)
    if not p["use_shorts"]:
        sig_short = sig_short & False

    sl_long = np.minimum(s20, l) - p["sl_buf_atr"] * atr
    sl_short = np.maximum(s20, h) + p["sl_buf_atr"] * atr

    equity = 10000.0
    curve = [equity]
    trades: list[dict] = []
    pos = None  # dict en cours

    idx = df.index
    n = len(df)
    slip = SLIPPAGE_BPS / 10000.0

    for i in range(int(p["len200"]) + 1, n):
        px = c.iloc[i]

        # ── gestion de la position ouverte ──
        if pos is not None:
            hit = None
            if pos["side"] == "L":
                if l.iloc[i] <= pos["sl"]:
                    hit, exit_px = "SL", pos["sl"]
                elif h.iloc[i] >= pos["t3"]:
                    hit, exit_px = "T3", pos["t3"]
                elif h.iloc[i] >= pos["t2"]:
                    hit, exit_px = "T2", pos["t2"]
                elif h.iloc[i] >= pos["t1"]:
                    hit, exit_px = "T1", pos["t1"]
                elif px < s200.iloc[i]:
                    hit, exit_px = "EXIT200", px
            else:
                if h.iloc[i] >= pos["sl"]:
                    hit, exit_px = "SL", pos["sl"]
                elif l.iloc[i] <= pos["t3"]:
                    hit, exit_px = "T3", pos["t3"]
                elif l.iloc[i] <= pos["t2"]:
                    hit, exit_px = "T2", pos["t2"]
                elif l.iloc[i] <= pos["t1"]:
                    hit, exit_px = "T1", pos["t1"]
                elif px > s200.iloc[i]:
                    hit, exit_px = "EXIT200", px

            if hit:
                direction = 1 if pos["side"] == "L" else -1
                fill = exit_px * (1 - direction * slip)
                gross = (fill - pos["entry"]) * direction * pos["qty"]
                cost = (abs(pos["entry"]) + abs(fill)) * pos["qty"] * COMMISSION
                pnl = gross - cost
                equity += pnl
                trades.append({
                    "side": pos["side"], "pnl": pnl,
                    "pct": pnl / max(equity - pnl, 1e-9),
                    "exit": hit, "date": str(idx[i]),
                })
                pos = None

        # ── nouvelle entrée ──
        if pos is None and equity > 0:
            long_ok = bool(sig_long.iloc[i]) if not pd.isna(sig_long.iloc[i]) else False
            short_ok = bool(sig_short.iloc[i]) if not pd.isna(sig_short.iloc[i]) else False

            if long_ok:
                sl = sl_long.iloc[i]
                risk = px - sl
                if risk > 0 and not pd.isna(risk):
                    qty = equity * p["risk_pct"] / 100 / risk
                    entry = px * (1 + slip)
                    pos = {"side": "L", "entry": entry, "qty": qty, "sl": sl,
                           "t1": px + p["t1_r"] * risk,
                           "t2": px + p["t2_r"] * risk,
                           "t3": px + p["t3_r"] * risk}
            elif short_ok:
                sl = sl_short.iloc[i]
                risk = sl - px
                if risk > 0 and not pd.isna(risk):
                    qty = equity * p["risk_pct"] / 100 / risk
                    entry = px * (1 - slip)
                    pos = {"side": "S", "entry": entry, "qty": qty, "sl": sl,
                           "t1": px - p["t1_r"] * risk,
                           "t2": px - p["t2_r"] * risk,
                           "t3": px - p["t3_r"] * risk}

        curve.append(equity)

    if not trades:
        return {"error": "Aucun trade"}

    return _metrics(trades, curve, df)


def _metrics(trades: list[dict], curve: list[float], df: pd.DataFrame) -> dict:
    eq = pd.Series(curve)
    final = eq.iloc[-1]
    total_return = (final / 10000 - 1) * 100

    span_days = max((df.index[-1] - df.index[0]).days, 1)
    n_months = span_days / 30
    monthly = ((final / 10000) ** (1 / n_months) - 1) * 100 if final > 0 else -100.0

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    gross_w = sum(t["pnl"] for t in wins)
    gross_l = abs(sum(t["pnl"] for t in losses))

    roll_max = eq.cummax()
    dd = ((eq - roll_max) / roll_max * 100).min()

    rets = pd.Series([t["pct"] for t in trades])
    sharpe_trade = rets.mean() / rets.std() if rets.std() > 0 else 0.0

    return {
        "total_trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1),
        "total_return_pct": round(total_return, 2),
        "monthly_return_pct": round(monthly, 2),
        "profit_factor": round(gross_w / gross_l, 2) if gross_l > 0 else 999,
        "max_drawdown_pct": round(float(dd), 2),
        "sharpe_per_trade": round(float(sharpe_trade), 4),
        "skew": round(float(rets.skew()), 3) if len(rets) > 2 else 0.0,
        "kurtosis": round(float(rets.kurtosis()) + 3, 3) if len(rets) > 3 else 3.0,
        "final_capital": round(final, 2),
    }


# ── Données ─────────────────────────────────────────────────────────────────

def fetch(symbol: str, interval: str = "1h", period_days: int = 720) -> pd.DataFrame | None:
    """`interval` accepte les intervalles yfinance, plus "4h"/"8h" (rééchantillonnés
    depuis le 1h — yfinance ne les sert pas nativement)."""
    import warnings
    warnings.filterwarnings("ignore")
    import yfinance as yf
    from datetime import datetime, timedelta

    resample_to = None
    if interval in ("4h", "8h"):
        resample_to, interval = interval, "1h"

    start = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")
    df = yf.download(symbol, start=start, interval=interval, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if resample_to:
        df = df.resample(resample_to).agg({
            "Open": "first", "High": "max", "Low": "min",
            "Close": "last", "Volume": "sum",
        }).dropna()

    return df if len(df) >= 300 else None


# ── Runner ──────────────────────────────────────────────────────────────────

def walk_forward_report(symbol: str, interval: str = "1h", period_days: int = 720) -> dict | None:
    df = fetch(symbol, interval, period_days)
    if df is None:
        print(f"  {symbol:<12} données indisponibles")
        return None

    wf = validation.walk_forward_split(run_backtest, df, DEFAULTS, holdout_frac=0.3)
    is_r, oos_r = wf["is"], wf["oos"]

    if "error" in is_r:
        print(f"  {symbol:<12} IS: {is_r['error']}")
        return None

    degr = validation.oos_degradation_pct(is_r, oos_r)
    oos_txt = (f"{oos_r['monthly_return_pct']:+6.2f}%/m  PF {oos_r['profit_factor']:>5.2f}"
               f"  {oos_r['total_trades']:>3} tr" if "error" not in oos_r else f"{oos_r['error']}")

    print(f"  {symbol:<12} IS {is_r['monthly_return_pct']:+6.2f}%/m PF {is_r['profit_factor']:>5.2f} "
          f"{is_r['total_trades']:>3} tr  │  OOS {oos_txt}  │  dégr "
          f"{(f'{degr:+.0f}%' if degr is not None else 'n/a'):>7}")

    return {"symbol": symbol, "is": is_r, "oos": oos_r, "degradation_pct": degr}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="panier complet")
    ap.add_argument("--interval", default="1h")
    ap.add_argument("--days", type=int, default=720)
    args = ap.parse_args()

    symbols = (["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
                "ADA-USD", "AVAX-USD", "LINK-USD", "DOT-USD", "DOGE-USD"]
               if args.full else ["BTC-USD"])

    print(f"\nWALK-FORWARD — ruban STOIC 1-2-3  ({args.interval}, {args.days}j, "
          f"70 % in-sample / 30 % out-of-sample)\n")

    results = [r for s in symbols if (r := walk_forward_report(s, args.interval, args.days))]
    if not results:
        print("\nAucun résultat exploitable.\n")
        return

    # ── Deflated Sharpe sur le meilleur candidat ──
    print()
    trial_sharpes = [r["is"]["sharpe_per_trade"] for r in results]
    best = max(results, key=lambda r: r["is"]["sharpe_per_trade"])
    dsr = validation.deflated_sharpe_ratio(
        best["is"]["sharpe_per_trade"], trial_sharpes,
        n_obs=best["is"]["total_trades"],
        skew=best["is"]["skew"], kurtosis=best["is"]["kurtosis"],
    )
    print(f"Deflated Sharpe — meilleur candidat {best['symbol']} "
          f"(Sharpe/trade {best['is']['sharpe_per_trade']:.4f}, "
          f"{len(trial_sharpes)} essais) : "
          f"{dsr if dsr is not None else 'n/a'}   "
          f"{'FIABLE' if dsr and dsr >= 0.95 else 'NON FIABLE (< 0.95)'}")

    # ── Monte Carlo sur le meilleur ──
    df_best = fetch(best["symbol"], args.interval, args.days)
    if df_best is not None:
        mc = validation.monte_carlo_stability(run_backtest, df_best, DEFAULTS, n_sims=12)
        if "error" not in mc:
            print(f"Monte Carlo {best['symbol']} — {mc['mc_stability_pct']}% des perturbations "
                  f"±10 % tiennent la perf  (moy {mc['mc_mean_pct']:+.2f}%/m, "
                  f"σ {mc['mc_std_pct']:.2f}, {mc['n_sims']} sims)")

    # ── Verdict ──
    valid = [r for r in results if r["degradation_pct"] is not None]
    survivors = [r for r in valid
                 if "error" not in r["oos"] and r["oos"]["monthly_return_pct"] > 0]
    print(f"\nOOS positif : {len(survivors)}/{len(valid)} symboles")
    if valid:
        med = float(np.median([r["degradation_pct"] for r in valid]))
        print(f"Dégradation médiane IS → OOS : {med:+.0f}%")
    print()


if __name__ == "__main__":
    main()
