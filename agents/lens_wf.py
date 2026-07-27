"""
lens_wf.py — Walk-forward de `stoic_lens_pure_v2.pine` (G1c).

Dernier candidat non testé. En in-sample il affichait la meilleure généralisation
du projet : 17/20 symboles positifs en Daily, aucun drawdown au-dessus de 8,8 %.
La question ouverte : est-ce que ça tient hors de la période d'ajustement ?

Port fidèle du Pine — protocole Stoic à 4 piliers :
  P1  extrême mensuel : plus haut / plus bas CLOSE journalier du mois courant
  P2  biais SMA20/200 : prix > SMA20 > SMA200 (long) ou l'inverse (short)
  P3  niveau daily    : proximité de PDH / PDL / PDC (tolérance × ATR)
  P4  zone Fib        : retracement 50-61,8 % du dernier swing

  Entrée si score >= 3/4 ET setup présent (Break & Retest ou SFP/sweep)
  Sortie : T1 2R (50 %), T2 3R (50 %), T3 5R, stop derrière la structure
  No Edge Zone : milieu de range, volatilité trop faible, SMA entrelacées
  Circuit breaker : 2 pertes consécutives → journée bloquée

Usage :
    python agents/lens_wf.py                  # BTC Daily
    python agents/lens_wf.py --full           # panier crypto
    python agents/lens_wf.py --full --interval 15m
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
from ppst_wf import fetch          # Binance pour les paires nues, repli yfinance

COMMISSION = 0.0004   # 0,04 % — valeur du script Pine
SLIP = 2 / 10000.0

DEFAULTS = {
    "min_score": 3, "lvl_tol_atr": 0.5, "fib_lo": 0.50, "fib_hi": 0.618,
    "swing_len": 10, "no_edge_pct": 0.35, "min_atr_pct": 0.05,
    "risk_golden": 1.0, "risk_std": 0.5, "atr_len": 14, "sl_buf_atr": 0.3,
    "t1r": 2.0, "t2r": 3.0, "t3r": 5.0, "max_loss_day": 2,
}


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / int(n), adjust=False).mean()


def _daily_levels(df: pd.DataFrame):
    """PDH / PDL / PDC + HCOM / LCOM.

    HCOM/LCOM = plus haut / plus bas CLOSE **journalier** du mois courant,
    remis à zéro au changement de mois. C'est le point que la v1 du Pine avait
    faux (elle testait « bougie verte »). `.shift(1)` partout : on n'utilise que
    de l'information disponible à la clôture de la veille.
    """
    d = df.resample("1D").agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
    pdh, pdl, pdc = d["High"].shift(1), d["Low"].shift(1), d["Close"].shift(1)

    month = d.index.to_period("M")
    hcom = d["Close"].groupby(month).cummax().shift(1)
    lcom = d["Close"].groupby(month).cummin().shift(1)

    out = pd.DataFrame({"pdh": pdh, "pdl": pdl, "pdc": pdc, "hcom": hcom, "lcom": lcom})
    return out.reindex(df.index, method="ffill")


def _pivots(df: pd.DataFrame, n: int):
    h, l = df["High"].values, df["Low"].values
    N = len(df)
    last_ph = np.full(N, np.nan)
    last_pl = np.full(N, np.nan)
    cph = cpl = np.nan
    for i in range(N):
        j = i - n                      # pivot confirmé n barres plus tard
        if n <= j < N - n:
            wh, wl = h[j - n:j + n + 1], l[j - n:j + n + 1]
            if h[j] == wh.max():
                cph = h[j]
            if l[j] == wl.min():
                cpl = l[j]
        last_ph[i], last_pl[i] = cph, cpl
    return last_ph, last_pl


def run_backtest(df: pd.DataFrame, params: dict) -> dict:
    p = {**DEFAULTS, **params}
    if len(df) < 260:
        return {"error": "Pas assez de données"}

    c, h, l, o = df["Close"], df["High"], df["Low"], df["Open"]
    atr = _atr(df, int(p["atr_len"]))
    sma20 = c.rolling(20).mean()
    sma200 = c.rolling(200).mean()
    lv = _daily_levels(df)
    last_ph, last_pl = _pivots(df, int(p["swing_len"]))

    cv, hv, lv_, ov = c.values, h.values, l.values, o.values
    av = atr.values
    s20, s200 = sma20.values, sma200.values
    pdh, pdl, pdc = lv["pdh"].values, lv["pdl"].values, lv["pdc"].values
    hcom, lcom = lv["hcom"].values, lv["lcom"].values

    equity = 10000.0
    curve, trades = [equity], []
    pos = None
    loss_streak = 0
    cur_day = None

    N = len(df)
    for i in range(205, N):
        if np.isnan(s200[i]) or np.isnan(av[i]) or av[i] <= 0:
            curve.append(equity)
            continue

        day = df.index[i].date()
        if day != cur_day:
            cur_day, loss_streak = day, 0

        px, tol = cv[i], p["lvl_tol_atr"] * av[i]

        # ── gestion de la position ouverte ──
        if pos:
            exited = False
            if pos["side"] == "L":
                if lv_[i] <= pos["sl"]:
                    fill, exited = pos["sl"], True
                elif hv[i] >= pos["t3"]:
                    fill, exited = pos["t3"], True
                elif hv[i] >= pos["t1"] and not pos["t1_hit"]:
                    pos["t1_hit"], pos["sl"] = True, pos["entry"]   # breakeven après T1
            else:
                if hv[i] >= pos["sl"]:
                    fill, exited = pos["sl"], True
                elif lv_[i] <= pos["t3"]:
                    fill, exited = pos["t3"], True
                elif lv_[i] <= pos["t1"] and not pos["t1_hit"]:
                    pos["t1_hit"], pos["sl"] = True, pos["entry"]

            if exited:
                sign = 1 if pos["side"] == "L" else -1
                fill_adj = fill * (1 - sign * SLIP)
                gross = (fill_adj - pos["entry"]) * pos["qty"] * sign
                cost = (pos["entry"] + fill_adj) * pos["qty"] * COMMISSION
                pnl = gross - cost
                prev = equity
                equity += pnl
                trades.append({"pnl": pnl, "pct": pnl / max(prev, 1e-9)})
                loss_streak = loss_streak + 1 if pnl < 0 else 0
                pos = None

        # ── recherche d'un nouveau setup ──
        if pos is None and loss_streak < p["max_loss_day"]:
            bias_long = px > s20[i] > s200[i]
            bias_short = px < s20[i] < s200[i]

            day_range = pdh[i] - pdl[i]
            mid_range = (day_range > 0 and
                         abs(px - (pdh[i] + pdl[i]) / 2) < day_range * p["no_edge_pct"] / 2)
            too_quiet = (av[i] / px * 100) < p["min_atr_pct"]
            no_edge = mid_range or too_quiet or not (bias_long or bias_short)

            if not no_edge:
                p1l = not np.isnan(lcom[i]) and abs(px - lcom[i]) <= tol * 2
                p1s = not np.isnan(hcom[i]) and abs(px - hcom[i]) <= tol * 2
                p3l = abs(px - pdl[i]) <= tol or abs(px - pdc[i]) <= tol
                p3s = abs(px - pdh[i]) <= tol or abs(px - pdc[i]) <= tol

                p4l = p4s = False
                if not np.isnan(last_ph[i]) and not np.isnan(last_pl[i]):
                    rng = last_ph[i] - last_pl[i]
                    if rng > 0:
                        p4l = last_ph[i] - rng * p["fib_hi"] <= px <= last_ph[i] - rng * p["fib_lo"]
                        p4s = last_pl[i] + rng * p["fib_lo"] <= px <= last_pl[i] + rng * p["fib_hi"]

                # int() obligatoire : sous NumPy 2.x, `+` entre np.bool_ est un OU
                # logique, pas une addition. Sans cast, le score vaut True et
                # `score >= 3` est toujours faux — aucun trade n'est jamais pris.
                score_l = int(p1l) + int(bias_long) + int(p3l) + int(p4l)
                score_s = int(p1s) + int(bias_short) + int(p3s) + int(p4s)

                prev_c = cv[i - 1]
                bnr_l = ((prev_c < pdc[i] <= px and lv_[i] <= pdc[i] + tol) or
                         (prev_c < pdh[i] <= px and lv_[i] <= pdh[i] + tol))
                bnr_s = ((prev_c > pdc[i] >= px and hv[i] >= pdc[i] - tol) or
                         (prev_c > pdl[i] >= px and hv[i] >= pdl[i] - tol))
                sfp_l = ((lv_[i] < pdl[i] and px > pdl[i] and px > ov[i]) or
                         (not np.isnan(lcom[i]) and lv_[i] < lcom[i] and px > lcom[i] and px > ov[i]))
                sfp_s = ((hv[i] > pdh[i] and px < pdh[i] and px < ov[i]) or
                         (not np.isnan(hcom[i]) and hv[i] > hcom[i] and px < hcom[i] and px < ov[i]))

                go_l = (bnr_l or sfp_l) and score_l >= p["min_score"]
                go_s = (bnr_s or sfp_s) and score_s >= p["min_score"]

                if go_l or go_s:
                    side = "L" if go_l else "S"
                    score = score_l if go_l else score_s
                    buf = p["sl_buf_atr"] * av[i]
                    if side == "L":
                        sl = min(lv_[i], last_pl[i] if not np.isnan(last_pl[i]) else lv_[i]) - buf
                        risk = px - sl
                    else:
                        sl = max(hv[i], last_ph[i] if not np.isnan(last_ph[i]) else hv[i]) + buf
                        risk = sl - px

                    if risk > 0:
                        rpct = p["risk_golden"] if score >= 4 else p["risk_std"]
                        qty = equity * rpct / 100 / risk
                        sign = 1 if side == "L" else -1
                        entry = px * (1 + sign * SLIP)
                        pos = {
                            "side": side, "entry": entry, "qty": qty, "sl": sl,
                            "t1": entry + sign * p["t1r"] * risk,
                            "t3": entry + sign * p["t3r"] * risk,
                            "t1_hit": False,
                        }

        curve.append(equity)

    if not trades:
        return {"error": "Aucun trade"}

    eq = pd.Series(curve)
    final = eq.iloc[-1]
    span_days = max((df.index[-1] - df.index[0]).days, 1)
    monthly = ((final / 10000) ** (1 / (span_days / 30)) - 1) * 100 if final > 0 else -100.0

    wins = [t for t in trades if t["pnl"] > 0]
    gw = sum(t["pnl"] for t in wins)
    gl = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    roll = eq.cummax()
    dd = ((eq - roll) / roll * 100).min()
    rets = pd.Series([t["pct"] for t in trades])
    bh = (cv[-1] / cv[0] - 1) * 100

    return {
        "total_trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1),
        "total_return_pct": round((final / 10000 - 1) * 100, 2),
        "monthly_return_pct": round(monthly, 2),
        "profit_factor": round(gw / gl, 2) if gl > 0 else 999,
        "max_drawdown_pct": round(float(dd), 2),
        "sharpe_per_trade": round(float(rets.mean() / rets.std()), 4) if rets.std() > 0 else 0.0,
        "skew": round(float(rets.skew()), 3) if len(rets) > 2 else 0.0,
        "kurtosis": round(float(rets.kurtosis()) + 3, 3) if len(rets) > 3 else 3.0,
        "buy_hold_pct": round(float(bh), 2),
        "vs_buy_hold_pct": round((final / 10000 - 1) * 100 - float(bh), 2),
        "final_capital": round(final, 2),
    }


def report(symbol: str, interval: str, days: int):
    df = fetch(symbol, interval, days)
    if df is None:
        print(f"  {symbol:<10} données indisponibles")
        return None

    full = run_backtest(df, DEFAULTS)
    wf = validation.walk_forward_split(run_backtest, df, DEFAULTS, holdout_frac=0.3)
    is_r, oos_r = wf["is"], wf["oos"]
    if "error" in is_r:
        print(f"  {symbol:<10} IS : {is_r['error']}")
        return None

    degr = validation.oos_degradation_pct(is_r, oos_r)
    oos_txt = (f"{oos_r['monthly_return_pct']:+6.2f}%/m PF {oos_r['profit_factor']:>5.2f} "
               f"{oos_r['total_trades']:>3} tr" if "error" not in oos_r else oos_r["error"][:22])
    print(f"  {symbol:<10} IS {is_r['monthly_return_pct']:+6.2f}%/m PF {is_r['profit_factor']:>5.2f} "
          f"{is_r['total_trades']:>3} tr │ OOS {oos_txt} │ dégr "
          f"{(f'{degr:+.0f}%' if degr is not None else 'n/a'):>7}")
    if "error" not in full:
        print(f"  {'':<10}   total {full['total_return_pct']:+8.1f}%  vs B&H "
              f"{full['buy_hold_pct']:+9.1f}%  →  {full['vs_buy_hold_pct']:+9.1f}%  "
              f"{'BAT' if full['vs_buy_hold_pct'] > 0 else 'SOUS'} B&H  DD {full['max_drawdown_pct']:.1f}%")
    return {"symbol": symbol, "full": full, "is": is_r, "oos": oos_r, "degradation_pct": degr}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--days", type=int, default=3200)
    a = ap.parse_args()

    symbols = (["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
                "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "DOGEUSDT"]
               if a.full else ["BTCUSDT"])

    print(f"\nWALK-FORWARD — STOIC LENS (4 piliers)  ({a.interval}, {a.days}j, 70 % IS / 30 % OOS)\n")
    res = [r for s in symbols if (r := report(s, a.interval, a.days))]
    if not res:
        print("\nAucun résultat exploitable.\n")
        return

    print()
    trials = [r["is"]["sharpe_per_trade"] for r in res]
    best = max(res, key=lambda r: r["is"]["sharpe_per_trade"])
    dsr = validation.deflated_sharpe_ratio(
        best["is"]["sharpe_per_trade"], trials, n_obs=best["is"]["total_trades"],
        skew=best["is"]["skew"], kurtosis=best["is"]["kurtosis"])
    print(f"Deflated Sharpe — {best['symbol']} ({len(trials)} essais) : "
          f"{dsr if dsr is not None else 'n/a'}   "
          f"{'FIABLE' if dsr and dsr >= 0.95 else 'NON FIABLE (< 0.95)'}")

    df_b = fetch(best["symbol"], a.interval, a.days)
    if df_b is not None:
        mc = validation.monte_carlo_stability(run_backtest, df_b, DEFAULTS, n_sims=10)
        if "error" not in mc:
            print(f"Monte Carlo {best['symbol']} — {mc['mc_stability_pct']}% des perturbations "
                  f"±10 % tiennent  (moy {mc['mc_mean_pct']:+.2f}%/m)")

    valid = [r for r in res if r["degradation_pct"] is not None]
    surv = [r for r in valid if "error" not in r["oos"] and r["oos"]["monthly_return_pct"] > 0]
    beats = [r for r in res if "error" not in r["full"] and r["full"]["vs_buy_hold_pct"] > 0]
    print(f"\nOOS positif      : {len(surv)}/{len(valid)} symboles")
    print(f"Bat le buy & hold: {len(beats)}/{len(res)} symboles")
    if valid:
        print(f"Dégradation médiane IS → OOS : "
              f"{float(np.median([r['degradation_pct'] for r in valid])):+.0f}%")

    oos_m = [r["oos"]["monthly_return_pct"] for r in res if "error" not in r["oos"]]
    if oos_m:
        arr = np.array(oos_m)
        print(f"\nPANIER — OOS moyen {arr.mean():+.2f}%/mois · médian "
              f"{float(np.median(arr)):+.2f}%/mois · σ {arr.std():.2f}")
        print(f"         pire {arr.min():+.2f} · meilleur {arr.max():+.2f}")
    print()


if __name__ == "__main__":
    main()
