"""
ptb_wf.py — Entrée PTB (Pullback To Buy) de @StoicTA, testée en walk-forward.

Source : tweet du 27 juillet 2026 + schéma annoté.

    « Step 3 confirms direction and sets the Step 3 High or Low. Price pulls back.
      The PTB is the last pullback candle.
      Bullish: buy stop above the PTB high.
      Bearish: sell stop below the PTB low.
      When price trades through it, the Entry triggers. »

Ce que ça change par rapport au ruban 1-2-3 déjà testé (`stoic_ribbon_wf.py`),
qui entrait **au marché sur la cassure** :

    ruban  : entrée à la cassure       → stop large (sous SMA20) → R:R médiocre
    PTB    : entrée sur ordre stop     → stop serré (sous PTB)   → R:R meilleur
             au-dessus du plus haut de
             la dernière bougie de repli

À win rate égal, un stop plus serré améliore l'espérance. C'est l'hypothèse que
ce module teste — il ne l'affirme pas.

Séquence implémentée (cas haussier, le baissier est le miroir exact) :
  1. Step 1  : bougie d'impulsion qui inscrit un plus haut sur `impulse_look` barres
  2. Step 2  : plus bas du repli qui suit
  3. Step 3  : clôture au-dessus du plus haut de Step 1 → direction confirmée,
               on mémorise le « Step 3 High »
  4. Repli   : les bougies dont le plus haut est inférieur au précédent
     PTB     : la dernière de ces bougies
  5. Entrée  : ordre stop au-dessus du plus haut du PTB, déclenché quand le prix
               le traverse (remplissage au niveau du stop, pas à la clôture)
  6. Stop    : sous le plus bas du PTB · Cibles : 2R puis extension Fib 261,8 %

Usage :
    python agents/ptb_wf.py --interval 4h
    python agents/ptb_wf.py --full --interval 4h
    python agents/ptb_wf.py --full --compare      # PTB contre entrée à la cassure
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
import validation
from ppst_wf import fetch

COMMISSION = 0.0004
SLIP = 2 / 10000.0

DEFAULTS = {
    "len_fast": 10, "len_slow": 20, "len50": 50, "len200": 200,
    "impulse_look": 5,        # barres pour qualifier l'impulsion de Step 1
    "max_wait": 20,           # barres d'attente max entre Step 3 et l'entrée
    "atr_len": 14,
    "risk_pct": 1.0,
    "t1r": 2.0,               # il annote « +2R » sur son chart
    "fib_ext": 2.618,         # cible finale : extension 261,8 %
    "use_shorts": True,
    "entry_mode": "ptb",      # "ptb" (le sien) ou "break" (l'ancien, pour comparer)
}


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / int(n), adjust=False).mean()


def run_backtest(df: pd.DataFrame, params: dict) -> dict:
    p = {**DEFAULTS, **params}
    if len(df) < int(p["len200"]) + 60:
        return {"error": "Pas assez de données"}

    c = df["Close"]
    s10 = c.rolling(int(p["len_fast"])).mean().values
    s20 = c.rolling(int(p["len_slow"])).mean().values
    s50 = c.rolling(int(p["len50"])).mean().values
    s200 = c.rolling(int(p["len200"])).mean().values
    atr = _atr(df, int(p["atr_len"])).values
    cv, hv, lo, ov = c.values, df["High"].values, df["Low"].values, df["Open"].values
    n = len(df)

    look = int(p["impulse_look"])
    hi_prev = pd.Series(hv).rolling(look).max().shift(1).values
    lo_prev = pd.Series(lo).rolling(look).min().shift(1).values

    equity = 10000.0
    curve, trades = [equity], []
    pos = None

    # État de la séquence, par direction.
    # 0 = rien · 1 = Step 3 confirmé, on suit le repli · l'entrée est un ordre stop
    stL = {"on": False, "s1_hi": np.nan, "s2_lo": np.nan, "s3_hi": np.nan,
           "ptb_hi": np.nan, "ptb_lo": np.nan, "bar": 0}
    stS = {"on": False, "s1_lo": np.nan, "s2_hi": np.nan, "s3_lo": np.nan,
           "ptb_lo": np.nan, "ptb_hi": np.nan, "bar": 0}

    start = int(p["len200"]) + 2
    tf = p.get("trade_from")
    if tf is not None:
        start = max(start, int(df.index.searchsorted(tf)))
        if start >= n - 2:
            return {"error": "Fenêtre trop courte"}

    for i in range(start, n):
        if np.isnan(s200[i]) or np.isnan(atr[i]) or atr[i] <= 0:
            curve.append(equity)
            continue

        bull = s50[i] > s200[i] and cv[i] > s200[i]
        bear = s50[i] < s200[i] and cv[i] < s200[i]

        # ── sortie ──────────────────────────────────────────────────────────
        if pos:
            sign = 1 if pos["side"] == "L" else -1
            hit = None
            if pos["side"] == "L":
                if lo[i] <= pos["sl"]:
                    hit = pos["sl"]
                elif hv[i] >= pos["t2"]:
                    hit = pos["t2"]
                elif hv[i] >= pos["t1"] and not pos["t1_hit"]:
                    pos["t1_hit"], pos["sl"] = True, pos["entry"]
            else:
                if hv[i] >= pos["sl"]:
                    hit = pos["sl"]
                elif lo[i] <= pos["t2"]:
                    hit = pos["t2"]
                elif lo[i] <= pos["t1"] and not pos["t1_hit"]:
                    pos["t1_hit"], pos["sl"] = True, pos["entry"]

            if hit is not None:
                fill = hit * (1 - sign * SLIP)
                pnl = (fill - pos["entry"]) * pos["qty"] * sign \
                      - (pos["entry"] + fill) * pos["qty"] * COMMISSION
                prev = equity
                equity += pnl
                trades.append({"pnl": pnl, "pct": pnl / max(prev, 1e-9)})
                pos = None

        # ── séquence 1-2-3 haussière ────────────────────────────────────────
        if bull:
            if not stL["on"]:
                # Step 1 puis Step 3 : clôture au-dessus du plus haut récent,
                # ruban orienté à la hausse.
                if (not np.isnan(hi_prev[i]) and cv[i] > hi_prev[i]
                        and s10[i] > s20[i] and cv[i] > ov[i]):
                    if p["entry_mode"] == "break" and pos is None:
                        # Ancien comportement : entrée au marché dès Step 3,
                        # stop sous le plus bas de Step 2 (donc bien plus large).
                        entry = cv[i] * (1 + SLIP)
                        s2 = lo_prev[i] if not np.isnan(lo_prev[i]) else lo[i]
                        sl = s2 - 0.05 * atr[i]
                        risk = entry - sl
                        if risk > 0:
                            qty = equity * p["risk_pct"] / 100 / risk
                            pos = {"side": "L", "entry": entry, "qty": qty, "sl": sl,
                                   "t1": entry + p["t1r"] * risk,
                                   "t2": s2 + (hv[i] - s2) * p["fib_ext"],
                                   "t1_hit": False}
                    else:
                        stL.update({"on": True, "s1_hi": hi_prev[i], "s3_hi": hv[i],
                                    "s2_lo": lo_prev[i] if not np.isnan(lo_prev[i]) else lo[i],
                                    "ptb_hi": np.nan, "ptb_lo": np.nan, "bar": i})
            else:
                if i - stL["bar"] > p["max_wait"]:
                    stL["on"] = False
                elif not np.isnan(stL["ptb_hi"]) and hv[i] > stL["ptb_hi"] and pos is None:
                    # l'ordre stop est traversé → entrée au niveau du stop
                    entry = stL["ptb_hi"] * (1 + SLIP)
                    sl = stL["ptb_lo"] - 0.05 * atr[i]
                    risk = entry - sl
                    if risk > 0:
                        qty = equity * p["risk_pct"] / 100 / risk
                        leg = max(stL["s3_hi"] - stL["s2_lo"], risk)
                        pos = {"side": "L", "entry": entry, "qty": qty, "sl": sl,
                               "t1": entry + p["t1r"] * risk,
                               "t2": stL["s2_lo"] + leg * p["fib_ext"],
                               "t1_hit": False}
                    stL["on"] = False
                elif hv[i] < hv[i - 1]:
                    # le repli continue → ce PTB remplace le précédent
                    stL["ptb_hi"], stL["ptb_lo"] = hv[i], lo[i]
                if lo[i] < stL["s2_lo"]:
                    stL["on"] = False        # repli trop profond → séquence morte
        else:
            stL["on"] = False

        # ── séquence baissière (miroir) ─────────────────────────────────────
        if p["use_shorts"] and bear:
            if not stS["on"]:
                if (not np.isnan(lo_prev[i]) and cv[i] < lo_prev[i]
                        and s10[i] < s20[i] and cv[i] < ov[i]):
                    if p["entry_mode"] == "break" and pos is None:
                        entry = cv[i] * (1 - SLIP)
                        s2 = hi_prev[i] if not np.isnan(hi_prev[i]) else hv[i]
                        sl = s2 + 0.05 * atr[i]
                        risk = sl - entry
                        if risk > 0:
                            qty = equity * p["risk_pct"] / 100 / risk
                            pos = {"side": "S", "entry": entry, "qty": qty, "sl": sl,
                                   "t1": entry - p["t1r"] * risk,
                                   "t2": s2 - (s2 - lo[i]) * p["fib_ext"],
                                   "t1_hit": False}
                    else:
                        stS.update({"on": True, "s1_lo": lo_prev[i], "s3_lo": lo[i],
                                    "s2_hi": hi_prev[i] if not np.isnan(hi_prev[i]) else hv[i],
                                    "ptb_lo": np.nan, "ptb_hi": np.nan, "bar": i})
            else:
                if i - stS["bar"] > p["max_wait"]:
                    stS["on"] = False
                elif not np.isnan(stS["ptb_lo"]) and lo[i] < stS["ptb_lo"] and pos is None:
                    entry = stS["ptb_lo"] * (1 - SLIP)
                    sl = stS["ptb_hi"] + 0.05 * atr[i]
                    risk = sl - entry
                    if risk > 0:
                        qty = equity * p["risk_pct"] / 100 / risk
                        leg = max(stS["s2_hi"] - stS["s3_lo"], risk)
                        pos = {"side": "S", "entry": entry, "qty": qty, "sl": sl,
                               "t1": entry - p["t1r"] * risk,
                               "t2": stS["s2_hi"] - leg * p["fib_ext"],
                               "t1_hit": False}
                    stS["on"] = False
                elif lo[i] > lo[i - 1]:
                    stS["ptb_lo"], stS["ptb_hi"] = lo[i], hv[i]
                if hv[i] > stS["s2_hi"]:
                    stS["on"] = False
        else:
            stS["on"] = False

        curve.append(equity)

    if not trades:
        return {"error": "Aucun trade"}

    eq = pd.Series(curve)
    final = eq.iloc[-1]
    span = max((df.index[-1] - df.index[start]).days, 1)
    monthly = ((final / 10000) ** (1 / (span / 30)) - 1) * 100 if final > 0 else -100.0
    wins = [t for t in trades if t["pnl"] > 0]
    gw = sum(t["pnl"] for t in wins)
    gl = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    roll = eq.cummax()
    rets = pd.Series([t["pct"] for t in trades])

    return {
        "total_trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1),
        "total_return_pct": round((final / 10000 - 1) * 100, 2),
        "monthly_return_pct": round(monthly, 2),
        "profit_factor": round(gw / gl, 2) if gl > 0 else 999,
        "max_drawdown_pct": round(float(((eq - roll) / roll * 100).min()), 2),
        "sharpe_per_trade": round(float(rets.mean() / rets.std()), 4) if rets.std() > 0 else 0.0,
        "skew": round(float(rets.skew()), 3) if len(rets) > 2 else 0.0,
        "kurtosis": round(float(rets.kurtosis()) + 3, 3) if len(rets) > 3 else 3.0,
        "buy_hold_pct": round(float((cv[-1] / cv[start] - 1) * 100), 2),
        "vs_buy_hold_pct": round((final / 10000 - 1) * 100 - float((cv[-1] / cv[start] - 1) * 100), 2),
    }


def report(symbol: str, interval: str, days: int, mode: str = "ptb"):
    df = fetch(symbol, interval, days)
    if df is None:
        return None
    prm = {**DEFAULTS, "entry_mode": mode}
    wf = validation.walk_forward_split(run_backtest, df, prm, holdout_frac=0.3)
    is_r, oos_r = wf["is"], wf["oos"]
    if "error" in is_r:
        print(f"  {symbol:<10} IS : {is_r['error']}")
        return None
    degr = validation.oos_degradation_pct(is_r, oos_r)
    oos_txt = (f"{oos_r['monthly_return_pct']:+6.2f}%/m PF {oos_r['profit_factor']:>5.2f} "
               f"{oos_r['total_trades']:>3} tr" if "error" not in oos_r else oos_r["error"][:20])
    print(f"  {symbol:<10} IS {is_r['monthly_return_pct']:+6.2f}%/m PF {is_r['profit_factor']:>5.2f} "
          f"WR {is_r['win_rate_pct']:>4.1f}% {is_r['total_trades']:>3} tr │ OOS {oos_txt} │ "
          f"dégr {(f'{degr:+.0f}%' if degr is not None else 'n/a'):>7}")
    return {"symbol": symbol, "is": is_r, "oos": oos_r, "degradation_pct": degr}


def summarize(res: list, label: str):
    if not res:
        print(f"  {label} : aucun résultat\n")
        return None
    oos = [r["oos"]["monthly_return_pct"] for r in res if "error" not in r["oos"]]
    if not oos:
        return None
    arr = np.array(oos)
    pos = int((arr > 0).sum())
    wr = np.mean([r["is"]["win_rate_pct"] for r in res])
    print(f"\n  {label}")
    print(f"    OOS positif {pos}/{arr.size} · moyen {arr.mean():+.2f}%/m · "
          f"médian {float(np.median(arr)):+.2f}%/m · WR moyen {wr:.1f}%")
    return {"pos": pos, "n": arr.size, "mean": arr.mean(), "median": float(np.median(arr))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--interval", default="4h")
    ap.add_argument("--days", type=int, default=3200)
    ap.add_argument("--compare", action="store_true",
                    help="compare l'entrée PTB à l'entrée à la cassure")
    a = ap.parse_args()

    symbols = (["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
                "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "DOGEUSDT"]
               if a.full else ["BTCUSDT"])

    print(f"\nWALK-FORWARD — ENTRÉE PTB (@StoicTA)  ({a.interval}, 70 % IS / 30 % OOS)\n")
    res_ptb = [r for s in symbols if (r := report(s, a.interval, a.days, "ptb"))]
    s_ptb = summarize(res_ptb, "ENTRÉE PTB (ordre stop au-dessus du repli)")

    if a.compare:
        print(f"\n  — comparaison : entrée au marché sur la cassure —\n")
        res_brk = [r for s in symbols if (r := report(s, a.interval, a.days, "break"))]
        s_brk = summarize(res_brk, "ENTRÉE À LA CASSURE")
        if s_ptb and s_brk:
            d = s_ptb["median"] - s_brk["median"]
            print(f"\n  Écart médian : {d:+.2f} point de %/mois en faveur de "
                  f"{'PTB' if d > 0 else 'la cassure'}")

    if res_ptb:
        trials = [r["is"]["sharpe_per_trade"] for r in res_ptb]
        best = max(res_ptb, key=lambda r: r["is"]["sharpe_per_trade"])
        dsr = validation.deflated_sharpe_ratio(
            best["is"]["sharpe_per_trade"], trials, n_obs=best["is"]["total_trades"],
            skew=best["is"]["skew"], kurtosis=best["is"]["kurtosis"])
        print(f"\n  Deflated Sharpe — {best['symbol']} : {dsr if dsr is not None else 'n/a'}")
    print()


if __name__ == "__main__":
    main()
