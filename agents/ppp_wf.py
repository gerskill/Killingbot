"""
ppp_wf.py — Walk-forward de PP-ST + EMA200 + ADX avec filtre PPP (actions).

Pendant Python de `pine_scripts/strategies/pp_st_ppp_stocks.pine`. Chaque couple
actif × timeframe est testé deux fois, filtre PPP ON et OFF, sur les mêmes
données : la seule question est « le filtre améliore-t-il l'OOS ? ».

PPP (Potential Payback Period) — n tel que PER = (qⁿ − 1)/(q − 1), q = (1+g)/(1+r)
    n = ln[PER·(q−1) + 1] / ln q
    g = r                         → PPP = PER
    g < r et PER ≥ (1+r)/(r−g)    → jamais remboursé (inf)

Fondamentaux point-in-time : SEC EDGAR (companyfacts), chaque valeur n'est
utilisable qu'à partir du lendemain de son dépôt. EPS dilué TTM reconstruit
depuis les 10-Q (FY précédent + YTD courant − YTD de l'an passé). EPS ramené à
la base d'actions actuelle via l'historique des splits (prix yfinance ajustés).

Prérequis réseau : sec.gov, data.sec.gov, Yahoo Finance.
SEC exige un User-Agent avec contact :  export SEC_USER_AGENT="Nom email@domaine"

Usage :
    python agents/ppp_wf.py                                  # panier par défaut, 1d/4h/1h
    python agents/ppp_wf.py --symbols NVDA,MSFT --intervals 1d
    python agents/ppp_wf.py --ppp-max 12 --r 0.08 --report    # écrit backtest/PPP_WF_<date>.md
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
import validation
from ppst_wf import DEFAULTS, fetch, run_backtest

ROOT = Path(__file__).parent.parent
SEC_CACHE = ROOT / "data" / "cache" / "sec"

DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "JPM", "KO", "XOM"]
# yfinance : 1h (et 4h rééchantillonné) plafonné à 730 jours
DEFAULT_DAYS = {"1d": 3650, "4h": 729, "1h": 729}


# ── PPP ─────────────────────────────────────────────────────────────────────

def ppp(per: float, g: float, r: float) -> float:
    """Années de bénéfices actualisés pour rembourser le prix. inf = jamais, nan = non calculable."""
    if per is None or g is None or not np.isfinite(per) or not np.isfinite(g) or per <= 0:
        return float("nan")
    q = (1 + g) / (1 + r)
    if abs(q - 1) < 1e-9:
        return float(per)
    arg = per * (q - 1) + 1
    if arg <= 0:
        return float("inf")
    return math.log(arg) / math.log(q)


# ── SEC EDGAR ───────────────────────────────────────────────────────────────

def _sec_get(url: str, cache_name: str, max_age_days: int = 7) -> dict:
    SEC_CACHE.mkdir(parents=True, exist_ok=True)
    path = SEC_CACHE / cache_name
    if path.exists() and time.time() - path.stat().st_mtime < max_age_days * 86400:
        return json.loads(path.read_text())
    ua = os.environ.get("SEC_USER_AGENT")
    if not ua:
        raise RuntimeError('SEC exige un contact : export SEC_USER_AGENT="Nom email@domaine"')
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    path.write_text(json.dumps(data))
    time.sleep(0.15)  # SEC : 10 requêtes/s max
    return data


def sec_cik(ticker: str) -> str:
    table = _sec_get("https://www.sec.gov/files/company_tickers.json", "company_tickers.json", 30)
    for row in table.values():
        if row["ticker"].upper() == ticker.upper():
            return f"{int(row['cik_str']):010d}"
    raise KeyError(f"{ticker} absent de la table SEC")


def sec_eps_facts(ticker: str) -> list[dict]:
    cik = sec_cik(ticker)
    facts = _sec_get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", f"facts_{cik}.json")
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for concept in ("EarningsPerShareDiluted", "EarningsPerShareBasic"):
        units = gaap.get(concept, {}).get("units", {})
        if "USD/shares" in units:
            return units["USD/shares"]
    raise KeyError(f"{ticker} : pas d'EPS us-gaap")


def yf_splits(ticker: str) -> pd.Series:
    import yfinance as yf
    s = yf.Ticker(ticker).splits
    if s is None or s.empty:
        return pd.Series(dtype=float)
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s[s > 0]


# ── Fondamentaux point-in-time ──────────────────────────────────────────────

def _split_factor_after(d: pd.Timestamp, splits: pd.Series) -> float:
    if splits.empty:
        return 1.0
    after = splits[splits.index > d]
    return float(after.prod()) if len(after) else 1.0


def eps_point_in_time(facts: list[dict], splits: pd.Series | None = None,
                      g_years: int = 3, g_cap: float = 0.25) -> pd.DataFrame:
    """Une ligne par date de dépôt : EPS TTM et g (CAGR de l'EPS annuel), en base
    d'actions actuelle. Index = date à partir de laquelle la valeur est connue
    (dépôt + 1 jour, les dépôts tombent souvent après la clôture)."""
    splits = splits if splits is not None else pd.Series(dtype=float)
    rows = []
    for f in facts:
        if f.get("form") not in ("10-K", "10-Q") or "start" not in f:
            continue
        start, end, filed = pd.Timestamp(f["start"]), pd.Timestamp(f["end"]), pd.Timestamp(f["filed"])
        rows.append({"start": start, "end": end, "dur": (end - start).days,
                     "filed": filed, "val": f["val"] / _split_factor_after(filed, splits)})
    if not rows:
        return pd.DataFrame(columns=["eps_ttm", "g"])

    # Première publication de chaque période : c'est ce que le marché connaissait.
    df = (pd.DataFrame(rows).sort_values("filed")
          .drop_duplicates(subset=["start", "end"], keep="first").reset_index(drop=True))
    annual = df["dur"].between(330, 380)
    tol = pd.Timedelta(days=10)

    out = []
    for F in sorted(df["filed"].unique()):
        av = df[df["filed"] <= F]
        E = av["end"].max()
        cur = av[av["end"] == E]
        ttm = np.nan
        cur_annual = cur[annual.loc[cur.index]]
        if len(cur_annual):
            ttm = cur_annual["val"].iloc[0]
        else:
            ytd = cur.loc[cur["dur"].idxmax()]
            S = ytd["start"]
            prev_fy = av[annual.loc[av.index] & ((av["end"] - (S - pd.Timedelta(days=1))).abs() <= tol)]
            prev_ytd = av[((av["end"] - (E - pd.Timedelta(days=365))).abs() <= tol)
                          & ((av["dur"] - ytd["dur"]).abs() <= 15)]
            if len(prev_fy) and len(prev_ytd):
                ttm = prev_fy["val"].iloc[-1] + ytd["val"] - prev_ytd["val"].iloc[-1]

        fy = av[annual.loc[av.index]].sort_values("end").drop_duplicates("end", keep="last")["val"].values
        g = np.nan
        if len(fy) >= 2:
            k = min(g_years, len(fy) - 1)
            first, last = fy[-1 - k], fy[-1]
            if first > 0 and last > 0:
                g = min((last / first) ** (1 / k) - 1, g_cap)
        out.append({"known_from": F + pd.Timedelta(days=1), "eps_ttm": ttm, "g": g})

    return pd.DataFrame(out).set_index("known_from")


def ppp_mask(df: pd.DataFrame, fund: pd.DataFrame, r: float, ppp_max: float) -> tuple[pd.Series, pd.Series]:
    """Masque d'entrée aligné sur les barres de prix + série PPP (pour diagnostic)."""
    idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
    days = pd.DatetimeIndex(idx).normalize()
    pos = fund.index.searchsorted(days, side="right") - 1
    eps = np.where(pos >= 0, fund["eps_ttm"].values[np.clip(pos, 0, None)], np.nan)
    g = np.where(pos >= 0, fund["g"].values[np.clip(pos, 0, None)], np.nan)
    close = df["Close"].values
    per = np.where(eps > 0, close / np.where(eps > 0, eps, 1), np.nan)
    p = np.array([ppp(a, b, r) for a, b in zip(per, g)])
    p_series = pd.Series(p, index=df.index)
    return pd.Series(np.isfinite(p) & (p <= ppp_max), index=df.index), p_series


# ── Runner ──────────────────────────────────────────────────────────────────

def _fmt(res: dict) -> str:
    if "error" in res:
        return f"{res['error'][:20]:<28}"
    return f"{res['monthly_return_pct']:+6.2f}%/m PF {res['profit_factor']:>5.2f} {res['total_trades']:>3}tr"


def evaluate(symbol: str, interval: str, days: int, fund: pd.DataFrame, r: float, ppp_max: float) -> dict | None:
    df = fetch(symbol, interval, days)
    if df is None:
        print(f"  {symbol:<6} {interval:<3} prix indisponibles")
        return None
    mask, p = ppp_mask(df, fund, r, ppp_max)
    base_p = dict(DEFAULTS)
    filt_p = {**DEFAULTS, "_entry_mask": mask}

    out = {"symbol": symbol, "interval": interval,
           "pct_bars_ok": round(float(mask.mean()) * 100, 1),
           "ppp_last": float(p.iloc[-1]) if len(p) else float("nan")}
    for name, params in (("off", base_p), ("on", filt_p)):
        wf = validation.walk_forward_split(run_backtest, df, params, holdout_frac=0.3)
        out[name] = {"is": wf["is"], "oos": wf["oos"], "full": run_backtest(df, params)}

    print(f"  {symbol:<6} {interval:<3} PPP≤{ppp_max:g} {out['pct_bars_ok']:5.1f}% des barres │ "
          f"OOS OFF {_fmt(out['off']['oos'])} │ OOS ON {_fmt(out['on']['oos'])}")
    return out


def _oos_m(r: dict, key: str):
    o = r[key]["oos"]
    return None if "error" in o else o["monthly_return_pct"]


def summarize(results: list[dict], intervals: list[str]) -> list[str]:
    lines = []
    for itv in intervals:
        rs = [r for r in results if r["interval"] == itv]
        pairs = [(_oos_m(r, "off"), _oos_m(r, "on")) for r in rs]
        both = [(a, b) for a, b in pairs if a is not None and b is not None]
        on_only = [b for a, b in pairs if b is not None]
        off_only = [a for a, b in pairs if a is not None]
        if not rs:
            continue
        better = sum(1 for a, b in both if b > a)
        med = lambda xs: f"{np.median(xs):+.2f}%/m" if xs else "n/a"
        lines.append(
            f"{itv:<3} │ OOS médian OFF {med(off_only)} · ON {med(on_only)} │ "
            f"OOS>0 OFF {sum(1 for x in off_only if x > 0)}/{len(off_only)} "
            f"· ON {sum(1 for x in on_only if x > 0)}/{len(on_only)} │ "
            f"filtre meilleur sur {better}/{len(both)}")

    trials = [r["on"]["is"]["sharpe_per_trade"] for r in results if "error" not in r["on"]["is"]]
    cands = [r for r in results if "error" not in r["on"]["is"]]
    if trials and cands:
        best = max(cands, key=lambda r: r["on"]["is"]["sharpe_per_trade"])
        b = best["on"]["is"]
        dsr = validation.deflated_sharpe_ratio(b["sharpe_per_trade"], trials, n_obs=b["total_trades"],
                                               skew=b["skew"], kurtosis=b["kurtosis"])
        lines.append(f"Deflated Sharpe (filtre ON, meilleur = {best['symbol']} {best['interval']}, "
                     f"{len(trials)} essais) : {dsr if dsr is not None else 'n/a'} "
                     f"→ {'FIABLE' if dsr and dsr >= 0.95 else 'NON FIABLE (< 0.95)'}")
    return lines


def write_report(results: list[dict], summary: list[str], a) -> Path:
    path = ROOT / "backtest" / f"PPP_WF_{date.today().isoformat()}.md"
    L = [f"# Walk-forward PP-ST + filtre PPP — {date.today().isoformat()}", "",
         f"_`agents/ppp_wf.py` · PPP ≤ {a.ppp_max:g} ans · r = {a.r:.1%} · g = CAGR EPS {a.g_years} ans "
         f"plafonné {a.g_cap:.0%} · 70 % IS / 30 % OOS · EPS SEC point-in-time_", "",
         "| Actif | TF | % barres PPP ok | PPP actuel | OOS OFF | OOS ON | PF OOS OFF | PF OOS ON | Trades OOS OFF/ON |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        def cell(k, f):
            o = r[k]["oos"]
            return "—" if "error" in o else f.format(**o)
        pl = r["ppp_last"]
        L.append(f"| {r['symbol']} | {r['interval']} | {r['pct_bars_ok']} | "
                 f"{'jamais' if pl == float('inf') else ('n/a' if not np.isfinite(pl) else f'{pl:.1f}')} | "
                 f"{cell('off', '{monthly_return_pct:+.2f} %/m')} | {cell('on', '{monthly_return_pct:+.2f} %/m')} | "
                 f"{cell('off', '{profit_factor}')} | {cell('on', '{profit_factor}')} | "
                 f"{cell('off', '{total_trades}')}/{cell('on', '{total_trades}')} |")
    L += ["", "## Synthèse", "", "```", *summary, "```", "",
          "Statut : `non-verifie` tant que ce n'est pas relu au Strategy Tester.", ""]
    path.write_text("\n".join(L))
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    ap.add_argument("--intervals", default="1d,4h,1h")
    ap.add_argument("--ppp-max", type=float, default=10.0)
    ap.add_argument("--r", type=float, default=0.08)
    ap.add_argument("--g-years", type=int, default=3)
    ap.add_argument("--g-cap", type=float, default=0.25)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    symbols = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    intervals = [i.strip() for i in a.intervals.split(",") if i.strip()]

    print(f"\nWALK-FORWARD — PP-ST + EMA200 + ADX, filtre PPP ≤ {a.ppp_max:g} ans "
          f"(r {a.r:.1%}, g CAGR {a.g_years} ans plafonné {a.g_cap:.0%})\n")

    results = []
    for sym in symbols:
        try:
            fund = eps_point_in_time(sec_eps_facts(sym), yf_splits(sym), a.g_years, a.g_cap)
        except Exception as e:
            print(f"  {sym:<6} fondamentaux indisponibles : {e}")
            continue
        for itv in intervals:
            res = evaluate(sym, itv, DEFAULT_DAYS.get(itv, 729), fund, a.r, a.ppp_max)
            if res:
                results.append(res)

    if not results:
        print("\nAucun résultat exploitable.\n")
        return
    print()
    summary = summarize(results, intervals)
    for line in summary:
        print(line)
    if a.report:
        print(f"\nRapport : {write_report(results, summary, a).relative_to(ROOT)}")
    print()


if __name__ == "__main__":
    main()
