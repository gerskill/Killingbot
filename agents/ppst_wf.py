"""
ppst_wf.py — Walk-forward de `pp_st_btc_4h_final.pine`.

Port fidèle de la seule stratégie confirmée en direct dans le Strategy Tester
(+2947 % sur BTCUSDT 4H). Elle n'avait jamais été soumise au walk-forward.

Logique reproduite ligne à ligne depuis le Pine :
  centre    : moyenne pondérée des pivots  center = (center*2 + lastpp) / 3
  bandes    : Up = center − Factor*ATR ; Dn = center + Factor*ATR
  trend     : TUp/TDown à cliquet, flip quand close casse la bande opposée
  entrée    : flip trend −1 → +1  ET  close > EMA200  ET  ADX ≥ 20
  sortie    : flip trend +1 → −1  OU  close repasse sous l'EMA200
  sizing    : 100 % de l'équité (comme l'original), commission 0,1 %, slippage 1

Ajoute une comparaison **buy & hold** sur la même période : sur un actif qui a
fait ×9, un système long-only peut afficher un gros chiffre sans rien apporter.

Usage :
    python agents/ppst_wf.py                       # BTC 4h
    python agents/ppst_wf.py --full                # panier crypto
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
from stoic_ribbon_wf import fetch as _fetch_yf


def fetch(symbol: str, interval: str = "4h", days: int = 720) -> pd.DataFrame | None:
    """Paire nue (BTCUSDT) → API Binance : même source que le test Pine et historique
    intraday complet, là où yfinance plafonne à 730 jours. Sinon repli yfinance.
    Note : le préfixe `BINANCE:` route vers le cache TradingView, pas vers l'API —
    voir `core.data_source.resolve_source`. On passe donc la paire sans préfixe."""
    if ":" not in symbol and symbol.upper().endswith(("USDT", "USDC", "BUSD")):
        from datetime import datetime, timedelta
        from core.data_source import load, DataSourceError
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        try:
            df = load(symbol, interval, start=start)
        except DataSourceError as e:
            print(f"  {symbol:<16} source indisponible : {e}")
            return None
        if df is None or df.empty:
            return None
        df = df.rename(columns=str.capitalize)
        need = {"Open", "High", "Low", "Close"}
        if not need.issubset(df.columns):
            return None
        return df if len(df) >= 300 else None
    return _fetch_yf(symbol, interval, days)

COMMISSION = 0.001   # 0,1 % — valeur du script Pine
SLIP = 1 / 10000.0   # slippage 1

DEFAULTS = {"prd": 2, "factor": 5.0, "pd_atr": 14, "adx_min": 20, "ema_len": 200}


# ── Indicateurs ─────────────────────────────────────────────────────────────

def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / int(n), adjust=False).mean()


def _adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l = df["High"], df["Low"]
    up, dn = h.diff(), -l.diff()
    pdm = up.where((up > dn) & (up > 0), 0.0)
    ndm = dn.where((dn > up) & (dn > 0), 0.0)
    at = _atr(df, n).replace(0, 1e-10)
    pdi = 100 * pdm.ewm(alpha=1 / n, adjust=False).mean() / at
    ndi = 100 * ndm.ewm(alpha=1 / n, adjust=False).mean() / at
    dx = (pdi - ndi).abs() / (pdi + ndi).replace(0, 1e-10) * 100
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def _pivots(df: pd.DataFrame, prd: int):
    """ta.pivothigh/pivotlow : confirmés `prd` barres après, donc décalés."""
    h, l = df["High"], df["Low"]
    n = len(df)
    ph = pd.Series(np.nan, index=df.index)
    pl = pd.Series(np.nan, index=df.index)
    hv, lv = h.values, l.values
    for i in range(prd, n - prd):
        w_h, w_l = hv[i - prd:i + prd + 1], lv[i - prd:i + prd + 1]
        if hv[i] == w_h.max() and (w_h == hv[i]).sum() == 1:
            ph.iloc[i + prd] = hv[i]          # disponible seulement à i+prd
        if lv[i] == w_l.min() and (w_l == lv[i]).sum() == 1:
            pl.iloc[i + prd] = lv[i]
    return ph, pl


# ── Backtest ────────────────────────────────────────────────────────────────

def run_backtest(df: pd.DataFrame, params: dict) -> dict:
    p = {**DEFAULTS, **params}
    if len(df) < int(p["ema_len"]) + 60:
        return {"error": "Pas assez de données"}

    c = df["Close"]
    atr = _atr(df, int(p["pd_atr"]))
    ema200 = c.ewm(span=int(p["ema_len"]), adjust=False).mean()
    adx = _adx(df, 14)
    ph, pl = _pivots(df, int(p["prd"]))

    n = len(df)
    center = np.full(n, np.nan)
    cur = np.nan
    for i in range(n):
        lastpp = ph.iloc[i] if not pd.isna(ph.iloc[i]) else (pl.iloc[i] if not pd.isna(pl.iloc[i]) else np.nan)
        if not pd.isna(lastpp):
            cur = lastpp if pd.isna(cur) else (cur * 2 + lastpp) / 3
        center[i] = cur

    up_band = center - p["factor"] * atr.values
    dn_band = center + p["factor"] * atr.values

    trend = np.ones(n, dtype=int)
    tup = np.full(n, np.nan)
    tdn = np.full(n, np.nan)
    cv = c.values
    for i in range(1, n):
        tup[i] = max(up_band[i], tup[i - 1]) if (not np.isnan(tup[i - 1]) and cv[i - 1] > tup[i - 1]) else up_band[i]
        tdn[i] = min(dn_band[i], tdn[i - 1]) if (not np.isnan(tdn[i - 1]) and cv[i - 1] < tdn[i - 1]) else dn_band[i]
        if not np.isnan(tdn[i - 1]) and cv[i] > tdn[i - 1]:
            trend[i] = 1
        elif not np.isnan(tup[i - 1]) and cv[i] < tup[i - 1]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]

    bull = (c > ema200).values
    trending = (adx >= p["adx_min"]).values

    equity = 10000.0
    curve = [equity]
    trades: list[dict] = []
    in_pos = False
    entry_px = 0.0
    qty = 0.0

    start = max(int(p["ema_len"]) + 1, int(p["prd"]) * 2 + 2)
    for i in range(start, n):
        px = cv[i]
        flip_up = trend[i] == 1 and trend[i - 1] == -1
        flip_dn = trend[i] == -1 and trend[i - 1] == 1

        if in_pos and (flip_dn or not bull[i]):
            fill = px * (1 - SLIP)
            gross = (fill - entry_px) * qty
            cost = (entry_px + fill) * qty * COMMISSION
            pnl = gross - cost
            prev = equity
            equity += pnl
            trades.append({"pnl": pnl, "pct": pnl / max(prev, 1e-9), "date": str(df.index[i])})
            in_pos = False

        elif not in_pos and flip_up and bull[i] and trending[i]:
            entry_px = px * (1 + SLIP)
            qty = equity / entry_px          # 100 % de l'équité, comme l'original
            in_pos = True

        curve.append(equity)

    if in_pos:  # clôture de la position ouverte en fin de série
        fill = cv[-1] * (1 - SLIP)
        gross = (fill - entry_px) * qty
        cost = (entry_px + fill) * qty * COMMISSION
        pnl = gross - cost
        prev = equity
        equity += pnl
        trades.append({"pnl": pnl, "pct": pnl / max(prev, 1e-9), "date": str(df.index[-1])})
        curve.append(equity)

    if not trades:
        return {"error": "Aucun trade"}

    eq = pd.Series(curve)
    final = eq.iloc[-1]
    span_days = max((df.index[-1] - df.index[0]).days, 1)
    n_months = span_days / 30
    monthly = ((final / 10000) ** (1 / n_months) - 1) * 100 if final > 0 else -100.0

    wins = [t for t in trades if t["pnl"] > 0]
    gw = sum(t["pnl"] for t in wins)
    gl = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    roll = eq.cummax()
    dd = ((eq - roll) / roll * 100).min()
    rets = pd.Series([t["pct"] for t in trades])
    sharpe = rets.mean() / rets.std() if rets.std() > 0 else 0.0

    bh = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100

    return {
        "total_trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1),
        "total_return_pct": round((final / 10000 - 1) * 100, 2),
        "monthly_return_pct": round(monthly, 2),
        "profit_factor": round(gw / gl, 2) if gl > 0 else 999,
        "max_drawdown_pct": round(float(dd), 2),
        "sharpe_per_trade": round(float(sharpe), 4),
        "skew": round(float(rets.skew()), 3) if len(rets) > 2 else 0.0,
        "kurtosis": round(float(rets.kurtosis()) + 3, 3) if len(rets) > 3 else 3.0,
        "buy_hold_pct": round(float(bh), 2),
        "vs_buy_hold_pct": round((final / 10000 - 1) * 100 - float(bh), 2),
        "final_capital": round(final, 2),
    }


# ── Runner ──────────────────────────────────────────────────────────────────

def report(symbol: str, interval: str, days: int):
    df = fetch(symbol, interval, days)
    if df is None:
        print(f"  {symbol:<12} données indisponibles")
        return None

    full = run_backtest(df, DEFAULTS)
    wf = validation.walk_forward_split(run_backtest, df, DEFAULTS, holdout_frac=0.3)
    is_r, oos_r = wf["is"], wf["oos"]
    if "error" in is_r:
        print(f"  {symbol:<12} IS : {is_r['error']}")
        return None

    degr = validation.oos_degradation_pct(is_r, oos_r)
    oos_txt = (f"{oos_r['monthly_return_pct']:+6.2f}%/m PF {oos_r['profit_factor']:>5.2f} "
               f"{oos_r['total_trades']:>3} tr" if "error" not in oos_r else oos_r["error"][:22])

    print(f"  {symbol:<12} IS {is_r['monthly_return_pct']:+6.2f}%/m PF {is_r['profit_factor']:>5.2f} "
          f"{is_r['total_trades']:>3} tr │ OOS {oos_txt} │ dégr "
          f"{(f'{degr:+.0f}%' if degr is not None else 'n/a'):>7}")

    if "error" not in full:
        verdict = "BAT B&H" if full["vs_buy_hold_pct"] > 0 else "SOUS B&H"
        print(f"  {'':<12}   total {full['total_return_pct']:+9.1f}%  vs buy&hold "
              f"{full['buy_hold_pct']:+9.1f}%  →  {full['vs_buy_hold_pct']:+9.1f}%  {verdict}")

    return {"symbol": symbol, "full": full, "is": is_r, "oos": oos_r, "degradation_pct": degr}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--interval", default="4h")
    ap.add_argument("--days", type=int, default=720)
    a = ap.parse_args()

    # Paires Binance sans préfixe → API publique, historique intraday complet.
    symbols = (["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
                "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "DOGEUSDT"]
               if a.full else ["BTCUSDT"])

    print(f"\nWALK-FORWARD — PP-ST + EMA200 + ADX (long only)  "
          f"({a.interval}, {a.days}j, 70 % IS / 30 % OOS)\n")

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
    print(f"Deflated Sharpe — {best['symbol']} (Sharpe/trade {best['is']['sharpe_per_trade']:.4f}, "
          f"{len(trials)} essais) : {dsr if dsr is not None else 'n/a'}   "
          f"{'FIABLE' if dsr and dsr >= 0.95 else 'NON FIABLE (< 0.95)'}")

    df_b = fetch(best["symbol"], a.interval, a.days)
    if df_b is not None:
        mc = validation.monte_carlo_stability(run_backtest, df_b, DEFAULTS, n_sims=10)
        if "error" not in mc:
            print(f"Monte Carlo {best['symbol']} — {mc['mc_stability_pct']}% des perturbations "
                  f"±10 % tiennent  (moy {mc['mc_mean_pct']:+.2f}%/m, σ {mc['mc_std_pct']:.2f})")

    valid = [r for r in res if r["degradation_pct"] is not None]
    surv = [r for r in valid if "error" not in r["oos"] and r["oos"]["monthly_return_pct"] > 0]
    beats = [r for r in res if "error" not in r["full"] and r["full"]["vs_buy_hold_pct"] > 0]
    print(f"\nOOS positif      : {len(surv)}/{len(valid)} symboles")
    print(f"Bat le buy & hold: {len(beats)}/{len(res)} symboles")
    if valid:
        print(f"Dégradation médiane IS → OOS : "
              f"{float(np.median([r['degradation_pct'] for r in valid])):+.0f}%")

    # Niveau panier : la vraie question pour un système appliqué uniformément
    # n'est pas « le meilleur symbole tient-il ? » mais « la moyenne tient-elle ? ».
    oos_m = [r["oos"]["monthly_return_pct"] for r in res if "error" not in r["oos"]]
    if oos_m:
        arr = np.array(oos_m)
        print(f"\nPANIER — OOS moyen {arr.mean():+.2f}%/mois · médian "
              f"{float(np.median(arr)):+.2f}%/mois · σ {arr.std():.2f}")
        print(f"         pire symbole {arr.min():+.2f}%/mois · meilleur {arr.max():+.2f}%/mois")
    print()


if __name__ == "__main__":
    main()
