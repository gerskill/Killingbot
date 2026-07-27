"""
rolling_wf.py — Walk-forward glissant (G9).

Le split unique 70/30 donne **une** mesure hors échantillon. Elle peut être
chanceuse : si la fenêtre OOS tombe sur un régime favorable, le résultat flatte
la stratégie. Un seul point ne dit pas si l'edge persiste.

Ce module découpe l'historique en fenêtres successives — entraînement puis test,
puis on avance — et mesure l'OOS sur chacune. La question n'est plus « le
résultat hors échantillon est-il positif ? » mais **« combien de fenêtres sur N
le sont ? »**.

    |──── train ────|─ test ─|
              |──── train ────|─ test ─|
                        |──── train ────|─ test ─|

Aucune optimisation n'a lieu sur les fenêtres d'entraînement : les paramètres
sont fixés d'avance. L'entraînement sert seulement à respecter la chronologie
(chaque test porte sur des données postérieures au warm-up des indicateurs).

Usage :
    python agents/rolling_wf.py --strategy ppst --interval 4h
    python agents/rolling_wf.py --strategy ppst --interval 4h --windows 8
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))


def rolling_walk_forward(backtest_fn, df: pd.DataFrame, params: dict,
                         n_windows: int = 6, train_frac: float = 0.5,
                         warmup: int = 250) -> list[dict]:
    """Découpe en `n_windows` fenêtres test successives.

    `train_frac` fixe la part d'historique antérieur servant de contexte
    (warm-up des moyennes mobiles). `warmup` est un plancher en barres.
    """
    n = len(df)
    usable = n - warmup
    if usable < n_windows * 60:
        return []

    test_len = usable // n_windows
    out = []
    for k in range(n_windows):
        test_start = warmup + k * test_len
        test_end = test_start + test_len if k < n_windows - 1 else n

        ctx = max(warmup, int((test_start - warmup) * train_frac))
        slice_start = max(0, test_start - ctx)
        sub = df.iloc[slice_start:test_end]
        if len(sub) < warmup + 40:
            continue

        # `trade_from` isole la fenêtre : le contexte sert au warm-up des
        # indicateurs, mais aucun de ses trades n'entre dans le résultat.
        # Sans ça, les fenêtres se recouvrent et le score est gonflé.
        r = backtest_fn(sub, {**params, "trade_from": df.index[test_start]})
        out.append({
            "fenetre": k + 1,
            "debut": str(df.index[test_start].date()),
            "fin": str(df.index[min(test_end, n) - 1].date()),
            "resultat": r,
        })
    return out


def main():
    ap = argparse.ArgumentParser(description="Walk-forward glissant")
    ap.add_argument("--strategy", default="ppst",
                    choices=["ppst", "lens", "ptb", "break"])
    ap.add_argument("--interval", default="4h")
    ap.add_argument("--days", type=int, default=3200)
    ap.add_argument("--windows", type=int, default=6)
    ap.add_argument("--eligible-only", action="store_true",
                    help="n'utiliser que les symboles retenus par le filtre G8")
    a = ap.parse_args()

    if a.strategy == "ppst":
        from ppst_wf import fetch, run_backtest, DEFAULTS
    elif a.strategy == "lens":
        from lens_wf import fetch, run_backtest, DEFAULTS
    else:
        # "ptb" et "break" partagent le même moteur, seul `entry_mode` change
        from ptb_wf import fetch, run_backtest, DEFAULTS as _D
        DEFAULTS = {**_D, "entry_mode": a.strategy}

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
               "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "DOGEUSDT"]
    if a.eligible_only:
        symbols = [s for s in symbols if s != "DOTUSDT"]   # rejeté par G8 (PF 0,03)

    print(f"\nWALK-FORWARD GLISSANT — {a.strategy} ({a.interval}, "
          f"{a.windows} fenêtres){' · symboles éligibles' if a.eligible_only else ''}\n")

    per_window: dict[int, list[float]] = {}
    dates: dict[int, str] = {}
    per_symbol = []

    for s in symbols:
        df = fetch(s, a.interval, a.days)
        if df is None:
            continue
        wins = rolling_walk_forward(run_backtest, df, DEFAULTS, n_windows=a.windows)
        vals = []
        for w in wins:
            r = w["resultat"]
            if "error" in r:
                continue
            m = r["monthly_return_pct"]
            per_window.setdefault(w["fenetre"], []).append(m)
            dates.setdefault(w["fenetre"], f"{w['debut']} → {w['fin']}")
            vals.append(m)
        if vals:
            arr = np.array(vals)
            pos = int((arr > 0).sum())
            per_symbol.append((s, arr.mean(), pos, len(arr)))
            print(f"  {s:<10} moyenne {arr.mean():+6.2f}%/m sur {len(arr)} fenêtres · "
                  f"positives {pos}/{len(arr)}")

    if not per_window:
        print("\nAucune fenêtre exploitable.\n")
        return

    print(f"\n  {'Fenêtre':<9} {'Période':<26} {'Moyenne':>9}  {'Médiane':>9}  Symboles +")
    win_means = []
    for k in sorted(per_window):
        arr = np.array(per_window[k])
        win_means.append(arr.mean())
        print(f"  {k:<9} {dates[k]:<26} {arr.mean():+8.2f}%  {float(np.median(arr)):+8.2f}%  "
              f"{int((arr > 0).sum())}/{arr.size}")

    wm = np.array(win_means)
    pos_windows = int((wm > 0).sum())
    print(f"\n  Fenêtres positives : {pos_windows}/{wm.size}")
    print(f"  Moyenne des fenêtres : {wm.mean():+.2f}%/mois · écart-type {wm.std():.2f}")

    if per_symbol:
        cons = sum(1 for _, mean, pos, tot in per_symbol if pos >= tot * 0.6)
        print(f"  Symboles positifs sur >= 60 % des fenêtres : {cons}/{len(per_symbol)}")

    verdict = ("PERSISTE" if pos_windows >= wm.size * 0.6 and wm.mean() > 0
               else "NE PERSISTE PAS")
    print(f"\n  Verdict : l'edge {verdict} à travers les régimes.\n")


if __name__ == "__main__":
    main()
