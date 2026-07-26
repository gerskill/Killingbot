"""
strategy_engine.py — Moteur de backtest générique, partagé par toutes les stratégies.

Une stratégie ne fournit que sa logique de signal. Le moteur fournit tout le
reste : exécution, coûts, risque, métriques. Deux stratégies deviennent ainsi
comparables — leurs chiffres sortent du même moteur, pas de deux backtests
écrits séparément.

DEUX INVARIANTS, non négociables :

1. Pas de look-ahead. Un signal calculé sur la barre t (fermée) s'exécute à
   l'OUVERTURE de t+1. Le moteur applique ce décalage lui-même : la logique de
   stratégie ne peut pas l'oublier.

2. Coûts identiques à l'exécution réelle. Slippage et commissions sont importés
   de core.paper_executor. Un backtest moins cher que la production produit des
   stratégies rentables sur le papier uniquement.

Contrat d'une logique de stratégie — fichier strategies/<id>/logic.py :

    def signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
        '''Renvoie un DataFrame indexé comme df, colonnes :
             entry_long  (bool)  — ouvrir une position longue
             exit_long   (bool)  — fermer la position longue
           Optionnel : entry_short / exit_short.
           N'utiliser QUE des données disponibles à la clôture de chaque barre.
        '''
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.paper_executor import COMMISSION_BPS, SLIPPAGE_BPS

BARS_PER_YEAR = {
    "1m": 525_600, "5m": 105_120, "15m": 35_040, "30m": 17_520,
    "1h": 8_760, "2h": 4_380, "4h": 2_190, "6h": 1_460,
    "8h": 1_095, "12h": 730, "1d": 365, "1w": 52,
}


def _apply_costs(price: float, side: str, entering: bool) -> float:
    """Slippage toujours défavorable, même convention que le paper executor."""
    adverse_up = (side == "long") == entering
    return price * (1 + SLIPPAGE_BPS / 10_000 * (1 if adverse_up else -1))


def run_backtest(df: pd.DataFrame, signals: pd.DataFrame, params: dict) -> dict:
    """Simule la stratégie et renvoie métriques + journal des trades.

    params attendus (avec valeurs par défaut alignées sur killingbot_config.json) :
        sl_atr_mult        1.5   — distance du stop, en ATR
        atr_len            14
        risk_per_trade_pct 1.0   — % du capital risqué par trade
        account_size       25000
        tp_rr              None  — take-profit en R ; None = sortie sur signal seul
    """
    sl_mult = float(params.get("sl_atr_mult", 1.5))
    atr_len = int(params.get("atr_len", 14))
    risk_pct = float(params.get("risk_per_trade_pct", 1.0))
    account = float(params.get("account_size", 25_000))
    tp_rr = params.get("tp_rr")

    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift()
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(atr_len).mean()

    entry_long = signals.get("entry_long", pd.Series(False, index=df.index)).fillna(False)
    exit_long = signals.get("exit_long", pd.Series(False, index=df.index)).fillna(False)

    equity = account
    trades: list[dict] = []
    curve: list[tuple] = []
    pos: dict | None = None

    idx = df.index
    o, h, l = df["open"].values, high.values, low.values
    el, xl = entry_long.values, exit_long.values
    atr_v = atr.values

    # i-1 porte le signal, i porte l'exécution : le décalage est structurel.
    for i in range(1, len(df)):
        bar_open, bar_high, bar_low = o[i], h[i], l[i]

        if pos is not None:
            exit_px = exit_reason = None

            if bar_low <= pos["sl"]:
                exit_px, exit_reason = pos["sl"], "SL"
            elif pos["tp"] is not None and bar_high >= pos["tp"]:
                exit_px, exit_reason = pos["tp"], "TP"
            elif xl[i - 1]:
                exit_px, exit_reason = bar_open, "signal"

            if exit_px is not None:
                fill = _apply_costs(exit_px, "long", entering=False)
                gross = (fill - pos["entry"]) * pos["qty"]
                fees = (pos["entry"] + fill) * pos["qty"] * COMMISSION_BPS / 10_000
                pnl = gross - fees
                equity += pnl
                trades.append({
                    "entry_time": str(pos["time"]), "exit_time": str(idx[i]),
                    "entry": round(pos["entry"], 2), "exit": round(fill, 2),
                    "qty": round(pos["qty"], 6), "pnl": round(pnl, 2),
                    "r_multiple": round(pnl / pos["risk_usd"], 3) if pos["risk_usd"] else 0.0,
                    "reason": exit_reason, "bars_held": i - pos["bar"],
                })
                pos = None

        if pos is None and el[i - 1]:
            a = atr_v[i - 1]
            if not np.isnan(a) and a > 0:
                entry = _apply_costs(bar_open, "long", entering=True)
                sl_dist = a * sl_mult
                risk_usd = equity * risk_pct / 100
                qty = risk_usd / sl_dist
                pos = {
                    "entry": entry, "qty": qty, "sl": entry - sl_dist,
                    "tp": entry + sl_dist * float(tp_rr) if tp_rr else None,
                    "risk_usd": risk_usd, "time": idx[i], "bar": i,
                }

        curve.append((idx[i], equity))

    return _metrics(trades, curve, account, df, params)


def _metrics(trades: list[dict], curve: list[tuple], account: float,
             df: pd.DataFrame, params: dict) -> dict:
    """Métriques dans l'ordre de fiabilité de la spec (PF d'abord, WR informatif)."""
    if not trades:
        return {"error": "aucun trade", "n_trades": 0, "pf": 0.0,
                "max_dd_pct": 0.0, "expectancy_r": 0.0, "sharpe": 0.0,
                "win_rate": 0.0, "total_return_pct": 0.0, "trades": []}

    pnls = np.array([t["pnl"] for t in trades])
    wins, losses = pnls[pnls > 0], pnls[pnls <= 0]

    gross_win = float(wins.sum())
    gross_loss = float(abs(losses.sum()))
    # Sans perte, le PF est infini : borné pour rester comparable et ne pas
    # laisser un échantillon minuscule remporter tous les classements.
    pf = round(gross_win / gross_loss, 3) if gross_loss > 0 else 99.0

    eq = pd.Series([e for _, e in curve], index=[t for t, _ in curve])
    dd = (eq / eq.cummax() - 1) * 100
    max_dd = abs(float(dd.min()))

    rets = eq.pct_change().dropna()
    interval = params.get("interval", "4h")
    ann = BARS_PER_YEAR.get(interval, 2190)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(ann)) if len(rets) > 1 and rets.std() > 0 else 0.0

    r_mults = [t["r_multiple"] for t in trades]
    years = max((df.index[-1] - df.index[0]).days / 365.25, 1e-9)
    total_ret = (eq.iloc[-1] / account - 1) * 100

    return {
        "n_trades": len(trades),
        "pf": pf,
        "max_dd_pct": round(max_dd, 2),
        "expectancy_r": round(float(np.mean(r_mults)), 4),
        "sharpe": round(sharpe, 3),
        "win_rate": round(len(wins) / len(trades) * 100, 2),
        "total_return_pct": round(float(total_ret), 2),
        "monthly_return_pct": round(float(total_ret / (years * 12)), 3),
        "final_equity": round(float(eq.iloc[-1]), 2),
        "avg_bars_held": round(float(np.mean([t["bars_held"] for t in trades])), 1),
        "period": f"{df.index[0].date()} → {df.index[-1].date()}",
        "trades": trades,
    }


def backtest_from_logic(logic_module, df: pd.DataFrame, params: dict) -> dict:
    """Adaptateur : logic.signals(df, params) → run_backtest.

    Signature compatible avec agents/validation.py, qui attend une fonction
    (df, params) -> dict.
    """
    sig = logic_module.signals(df, params)
    if not isinstance(sig, pd.DataFrame):
        raise TypeError("signals() doit renvoyer un DataFrame (entry_long / exit_long)")
    if "entry_long" not in sig.columns:
        raise ValueError("signals() doit fournir au moins la colonne entry_long")
    return run_backtest(df, sig, params)
