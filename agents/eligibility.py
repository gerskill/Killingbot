"""
eligibility.py — Filtre d'éligibilité par symbole (G8).

Le walk-forward de PP-ST a montré un trou : **DOTUSDT affichait un profit factor
in-sample de 0,03** — la stratégie y perd presque tout ce qu'elle engage — et
rien ne l'écartait automatiquement. Il a fallu un test manuel pour le voir.

Ce module décide, à partir des seules données **in-sample**, si un symbole mérite
d'être tradé. Il ne regarde jamais l'out-of-sample : sinon on choisirait les
symboles en connaissant la réponse, ce qui vide le walk-forward de son sens.

Critères (tous doivent passer) :
  1. profit factor    >= pf_min          — refuse les symboles franchement perdants
  2. nombre de trades >= min_trades      — refuse les échantillons non concluants
  3. rendement mensuel > 0               — refuse ce qui perd déjà en in-sample
  4. drawdown         <= max_dd_pct      — refuse ce qui gagne au prix d'un risque excessif

Usage :
    from eligibility import screen, DEFAULT_RULES
    verdict = screen(is_result, DEFAULT_RULES)
    if verdict.eligible:
        ...
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rules:
    """Seuils calibrés sur PP-ST 4h, 10 paires, 2017-2026 (mesuré le 2026-07-26).

    `max_dd_pct` est volontairement désactivé par défaut. Testé à 35 %, il
    rejetait SOL, XRP, ADA et LINK — dont trois se sont révélés **positifs**
    en out-of-sample (ADA +1,49 %/m, LINK +1,61 %/m, XRP +3,22 %/m). Le panier
    filtré perdait alors 0,20 point par rapport au panier complet.

    Un drawdown élevé en in-sample signale de la volatilité, pas un défaut de la
    stratégie. Filtrer dessus revient à écarter les actifs volatils — ce qui, en
    crypto, écarte surtout ceux qui rapportent.

    Effet mesuré des seuils retenus (PF + trades + rendement positif) :
        panier OOS  +0,562 → +0,792 %/mois  (+0,230 point)
        médian      +0,350 → +0,500 %/mois
        seul rejet  DOTUSDT (PF 0,03)
    """
    pf_min: float = 1.20          # sous 1,2 l'edge ne couvre pas les coûts réels
    min_trades: int = 12          # sous 12 trades, un PF élevé ne veut rien dire
    max_dd_pct: float = 999.0     # désactivé — voir docstring
    require_positive: bool = True


DEFAULT_RULES = Rules()


@dataclass(frozen=True)
class Verdict:
    symbol: str
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def __str__(self) -> str:
        mark = "OK  " if self.eligible else "REJET"
        why = "" if self.eligible else "  — " + " · ".join(self.reasons)
        return f"{mark} {self.symbol:<10}{why}"


def screen(is_result: dict, rules: Rules = DEFAULT_RULES, symbol: str = "?") -> Verdict:
    """Juge un symbole sur son seul résultat in-sample."""
    if not is_result or "error" in is_result:
        return Verdict(symbol, False, [is_result.get("error", "pas de résultat")
                                       if is_result else "pas de résultat"])

    pf = is_result.get("profit_factor", 0.0)
    n = is_result.get("total_trades", 0)
    monthly = is_result.get("monthly_return_pct", 0.0)
    dd = abs(is_result.get("max_drawdown_pct", 0.0))

    reasons: list[str] = []
    if pf < rules.pf_min:
        reasons.append(f"PF {pf:.2f} < {rules.pf_min}")
    if n < rules.min_trades:
        reasons.append(f"{n} trades < {rules.min_trades}")
    if rules.require_positive and monthly <= 0:
        reasons.append(f"rendement {monthly:+.2f}%/m <= 0")
    if dd > rules.max_dd_pct:
        reasons.append(f"DD {dd:.1f}% > {rules.max_dd_pct}%")

    return Verdict(symbol, not reasons, reasons,
                   {"pf": pf, "trades": n, "monthly_pct": monthly, "dd_pct": dd})


def screen_all(results: list[dict], rules: Rules = DEFAULT_RULES) -> list[Verdict]:
    """`results` = liste de dicts {symbol, is, oos, ...} produits par un runner WF."""
    return [screen(r.get("is", {}), rules, r.get("symbol", "?")) for r in results]


def portfolio_impact(results: list[dict], verdicts: list[Verdict]) -> dict:
    """Compare le panier complet au panier filtré, mesuré sur l'**out-of-sample**.

    C'est le seul usage légitime de l'OOS ici : on ne s'en sert pas pour choisir
    les symboles (le filtre ne lit que l'in-sample), mais pour vérifier après coup
    si le filtre aurait aidé.
    """
    import numpy as np

    keep = {v.symbol for v in verdicts if v.eligible}

    def oos_returns(subset: set[str] | None):
        out = []
        for r in results:
            if subset is not None and r.get("symbol") not in subset:
                continue
            o = r.get("oos", {})
            if o and "error" not in o:
                out.append(o.get("monthly_return_pct", 0.0))
        return np.array(out) if out else np.array([])

    allr, filt = oos_returns(None), oos_returns(keep)
    if allr.size == 0:
        return {"error": "pas de données OOS"}

    res = {
        "n_total": len(results),
        "n_retenus": len(keep),
        "retenus": sorted(keep),
        "rejetes": sorted({v.symbol for v in verdicts if not v.eligible}),
        "oos_moyen_avant": round(float(allr.mean()), 3),
        "oos_median_avant": round(float(np.median(allr)), 3),
        "positifs_avant": f"{int((allr > 0).sum())}/{allr.size}",
    }
    if filt.size:
        res.update({
            "oos_moyen_apres": round(float(filt.mean()), 3),
            "oos_median_apres": round(float(np.median(filt)), 3),
            "positifs_apres": f"{int((filt > 0).sum())}/{filt.size}",
            "gain_moyen": round(float(filt.mean() - allr.mean()), 3),
        })
    else:
        res["oos_moyen_apres"] = None
    return res


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent))
    sys.path.insert(0, str(Path(__file__).parent.parent))

    ap = argparse.ArgumentParser(description="Filtre d'éligibilité — applique et mesure le gain")
    ap.add_argument("--strategy", default="ppst", choices=["ppst", "lens"])
    ap.add_argument("--interval", default="4h")
    ap.add_argument("--days", type=int, default=3200)
    ap.add_argument("--pf-min", type=float, default=DEFAULT_RULES.pf_min)
    ap.add_argument("--min-trades", type=int, default=DEFAULT_RULES.min_trades)
    ap.add_argument("--max-dd", type=float, default=DEFAULT_RULES.max_dd_pct,
                    help="drawdown in-sample toléré (mettre 999 pour désactiver)")
    a = ap.parse_args()

    if a.strategy == "ppst":
        from ppst_wf import fetch, run_backtest, DEFAULTS
    else:
        from lens_wf import fetch, run_backtest, DEFAULTS
    import validation

    rules = Rules(pf_min=a.pf_min, min_trades=a.min_trades, max_dd_pct=a.max_dd)
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
               "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "DOGEUSDT"]

    print(f"\nFILTRE D'ÉLIGIBILITÉ — {a.strategy} ({a.interval})")
    print(f"Règles : PF >= {rules.pf_min} · trades >= {rules.min_trades} · "
          f"rendement > 0 · DD <= {rules.max_dd_pct}%\n")

    results = []
    for s in symbols:
        df = fetch(s, a.interval, a.days)
        if df is None:
            continue
        wf = validation.walk_forward_split(run_backtest, df, DEFAULTS, holdout_frac=0.3)
        results.append({"symbol": s, "is": wf["is"], "oos": wf["oos"]})

    verdicts = screen_all(results, rules)
    for v in verdicts:
        m = v.metrics
        extra = (f"  [PF {m.get('pf', 0):.2f} · {m.get('trades', 0)} tr · "
                 f"{m.get('monthly_pct', 0):+.2f}%/m]") if m else ""
        print(f"  {v}{extra}")

    imp = portfolio_impact(results, verdicts)
    if "error" in imp:
        print(f"\n{imp['error']}\n")
        raise SystemExit

    print(f"\nRetenus : {imp['n_retenus']}/{imp['n_total']} — {', '.join(imp['retenus'])}")
    if imp["rejetes"]:
        print(f"Rejetés : {', '.join(imp['rejetes'])}")
    print(f"\nEffet mesuré sur l'OOS (le filtre ne lit que l'in-sample) :")
    print(f"  avant  moyen {imp['oos_moyen_avant']:+.3f}%/m · médian "
          f"{imp['oos_median_avant']:+.3f}%/m · positifs {imp['positifs_avant']}")
    if imp.get("oos_moyen_apres") is not None:
        print(f"  après  moyen {imp['oos_moyen_apres']:+.3f}%/m · médian "
              f"{imp['oos_median_apres']:+.3f}%/m · positifs {imp['positifs_apres']}")
        print(f"  gain   {imp['gain_moyen']:+.3f} point de %/mois")
    print()
