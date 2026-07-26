"""
strategy_bot.py — Le bot standard livré avec chaque stratégie.

Idée directrice : on n'écrit qu'une logique de signal. Tout le reste — données,
backtest, portes de validation, optimisation, journal des essais, rapport —
arrive automatiquement et à l'identique pour chaque stratégie. Deux stratégies
sont donc comparables : mêmes données, mêmes coûts, mêmes portes.

Ce que le bot apporte, et pourquoi :

  · Portes G1→G5 obligatoires. On ne peut pas « oublier » la validation :
    c'est exactement l'oubli qui a produit les 10 fausses stratégies du sweep
    KB_* (validation.py existait, personne ne l'appelait).

  · trials.jsonl enregistre TOUS les essais, y compris les ratés. Le Deflated
    Sharpe a besoin de la liste complète : jeter les échecs casse la correction
    du biais de sélection et fait remonter le bruit au rang de découverte.

  · G6 (test live TradingView) reste manuelle et bloque le statut. Aucun statut
    ne peut passer VALIDATED sans elle.

Arborescence créée par `new` :

    strategies/<id>/
        config.json     symbole, intervalle, params, grille, portes
        logic.py        signals(df, params) — la seule chose à écrire
        hypotheses.md   pourquoi chaque composant existe (à remplir AVANT le backtest)
        trials.jsonl    tous les essais, succès et échecs
        strategy.pine   source Pine pour G6 (à déposer)

CLI :
    python3 core/strategy_bot.py new ma_strat --symbol BTCUSDT --interval 4h
    python3 core/strategy_bot.py backtest ma_strat
    python3 core/strategy_bot.py validate ma_strat
    python3 core/strategy_bot.py optimize ma_strat
    python3 core/strategy_bot.py list
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

STRATEGIES_DIR = ROOT / "strategies"

from core.strategy_engine import BARS_PER_YEAR

# Portes de la spec §1.4. Un candidat doit toutes les passer.
#
# G1 — pourquoi deux seuils plutôt qu'un.
#   Un seuil unique de 30 trades appliqué au seul hold-out est arithmétiquement
#   inatteignable pour les stratégies sélectives : le hold-out vaut 30 % de
#   l'historique, soit ~2,7 ans sur 9 ans de données, ce qui exige plus de
#   11 trades/an. Une stratégie à 6 trades/an échouait donc quelle que soit sa
#   qualité, tandis qu'une stratégie à 65 trades/an passait sans difficulté —
#   y compris KB_15m, dont on sait qu'elle perd (PF 0.465 en live).
#   La porte sélectionnait la fréquence, pas la qualité : exactement le biais
#   qui a produit les 10 fausses stratégies du sweep KB_*.
#   Correctif : significativité mesurée sur l'échantillon total, et minimum
#   hors-échantillon abaissé à 10 — assez pour détecter un effondrement, pas
#   assez pour prétendre à la précision statistique.
GATES = {
    "G1_min_trades_total": 30,
    "G1_min_trades_oos": 10,
    "G2_pf_oos_min": 1.2,
    "G3_max_oos_degradation_pct": 30.0,
    "G4_deflated_sharpe_min": 0.95,
    "G5_mc_stability_min_pct": 80.0,
    "G6_live_test": "manuel — Strategy Tester TradingView",
    "max_dd_pct": 25.0,
}

LOGIC_TEMPLATE = '''"""
Logique de signal — {sid}

Seule chose à écrire. Le bot fournit données, coûts, risque, portes, rapport.

RÈGLE : n'utiliser que des données disponibles à la CLÔTURE de chaque barre.
Le moteur décale l'exécution à l'ouverture suivante — ne pas le refaire ici.
"""
import pandas as pd


def signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """df : OHLCV, index UTC. Renvoie entry_long / exit_long (bool)."""
    fast = int(params.get("ema_fast", 20))
    slow = int(params.get("ema_slow", 50))

    ema_f = df["close"].ewm(span=fast, adjust=False).mean()
    ema_s = df["close"].ewm(span=slow, adjust=False).mean()

    cross_up = (ema_f > ema_s) & (ema_f.shift() <= ema_s.shift())
    cross_dn = (ema_f < ema_s) & (ema_f.shift() >= ema_s.shift())

    return pd.DataFrame({"entry_long": cross_up, "exit_long": cross_dn}, index=df.index)
'''

HYPOTHESES_TEMPLATE = """# Hypothèses — {sid}

> À remplir **avant** tout backtest. Une hypothèse écrite après coup n'est pas
> une hypothèse, c'est du data mining habillé.

## Hypothèse économique

Pourquoi ce marché devrait-il se comporter ainsi ? Décrire le mécanisme, pas la
courbe d'équité.

## Composants

| Composant | Hypothèse | Effet attendu sur le nombre de trades |
|-----------|-----------|----------------------------------------|
| (ex. EMA200) | filtre de tendance macro | ↓ (un bon filtre retire des trades) |

## Conditions d'invalidation

Qu'est-ce qui prouverait que cette stratégie ne marche pas ? Écrire maintenant,
pendant que c'est encore honnête.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Squelette
# ─────────────────────────────────────────────────────────────────────────────

def cmd_new(sid: str, symbol: str, interval: str) -> Path:
    d = STRATEGIES_DIR / sid
    if d.exists():
        raise SystemExit(f"existe déjà : {d}")
    d.mkdir(parents=True)

    config = {
        "id": sid,
        "symbol": symbol,
        "interval": interval,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "DRAFT",
        "setup_key": sid[:8].upper(),  # clé de routage webhook (dédup symbol+setup)
        "params": {
            "ema_fast": 20, "ema_slow": 50,
            "atr_len": 14, "sl_atr_mult": 1.5,
            "risk_per_trade_pct": 1.0, "tp_rr": None,
        },
        # Grille grossière volontairement : 3-5 valeurs, 2 params max (spec §2.1).
        "param_grid": {"ema_fast": [10, 20, 30], "ema_slow": [40, 50, 60]},
        "gates": GATES,
        "gate_results": {},
        "deploy_state": "paper",
    }
    (d / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False))
    # replace() et non format() : les templates contiennent des accolades Python.
    (d / "logic.py").write_text(LOGIC_TEMPLATE.replace("{sid}", sid))
    (d / "hypotheses.md").write_text(HYPOTHESES_TEMPLATE.replace("{sid}", sid))
    (d / "trials.jsonl").touch()

    print(f"✅ {d}")
    print("   1. remplir hypotheses.md AVANT tout backtest")
    print("   2. écrire logic.py")
    print(f"   3. python3 core/strategy_bot.py backtest {sid}")
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Chargement
# ─────────────────────────────────────────────────────────────────────────────

def load_strategy(sid: str):
    d = STRATEGIES_DIR / sid
    if not d.exists():
        raise SystemExit(f"stratégie inconnue : {sid}")
    config = json.loads((d / "config.json").read_text())

    spec = importlib.util.spec_from_file_location(f"strategies.{sid}.logic", d / "logic.py")
    logic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(logic)
    return d, config, logic


def _backtest_fn(logic, interval):
    """(df, params) -> dict, signature attendue par agents/validation.py."""
    from core.strategy_engine import backtest_from_logic

    def fn(df, params):
        try:
            return backtest_from_logic(logic, df, {**params, "interval": interval})
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
    return fn


def log_trial(d: Path, entry: dict):
    """Tous les essais, succès ET échecs — le DSR a besoin de la liste complète."""
    entry = {**entry, "ts": datetime.now(timezone.utc).isoformat()}
    with open(d / "trials.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_trials(d: Path) -> list[dict]:
    p = d / "trials.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Backtest simple
# ─────────────────────────────────────────────────────────────────────────────

def cmd_backtest(sid: str, verbose: bool = True) -> dict:
    from core.data_source import load

    d, config, logic = load_strategy(sid)
    df = load(config["symbol"], config["interval"])
    res = _backtest_fn(logic, config["interval"])(df, config["params"])

    log_trial(d, {"kind": "backtest", "params": config["params"],
                  **{k: v for k, v in res.items() if k != "trades"}})

    if verbose:
        if "error" in res:
            print(f"❌ {res['error']}")
        else:
            print(json.dumps({k: v for k, v in res.items() if k != "trades"},
                             indent=2, ensure_ascii=False))
    return res


# ─────────────────────────────────────────────────────────────────────────────
# Portes G1 → G5
# ─────────────────────────────────────────────────────────────────────────────

def cmd_validate(sid: str) -> dict:
    from agents.validation import (deflated_sharpe_ratio, monte_carlo_stability,
                                   oos_degradation_pct, walk_forward_split)
    from core.data_source import load

    d, config, logic = load_strategy(sid)
    fn = _backtest_fn(logic, config["interval"])
    df = load(config["symbol"], config["interval"])
    params, g = config["params"], config["gates"]
    verdicts: list[dict] = []

    def gate(name, passed, detail):
        verdicts.append({"gate": name, "pass": bool(passed), "detail": detail})
        print(f"  {'✅' if passed else '❌'} {name}: {detail}")

    print(f"\n🔍 {sid} — {config['symbol']} {config['interval']} ({len(df)} barres)\n")

    split = walk_forward_split(fn, df, params, holdout_frac=0.3)
    is_r, oos_r = split["is"], split["oos"]
    if "error" in oos_r:
        gate("G1_min_trades", False, oos_r["error"])
        return _finish(d, config, verdicts)

    n_oos = oos_r.get("n_trades", 0)
    n_total = n_oos + is_r.get("n_trades", 0)
    min_total = g.get("G1_min_trades_total", g.get("G1_min_trades", 30))
    min_oos = g.get("G1_min_trades_oos", 10)
    gate("G1_min_trades", n_total >= min_total and n_oos >= min_oos,
         f"{n_total} trades total (min {min_total}), {n_oos} OOS (min {min_oos})")

    pf = oos_r.get("pf", 0)
    gate("G2_pf_oos", pf > g["G2_pf_oos_min"], f"PF OOS {pf} (min {g['G2_pf_oos_min']})")

    deg = oos_degradation_pct(is_r, oos_r)
    gate("G3_oos_degradation",
         deg is not None and deg > -g["G3_max_oos_degradation_pct"],
         f"{deg}% IS→OOS (max -{g['G3_max_oos_degradation_pct']}%)" if deg is not None
         else "non comparable")

    # Le DSR a besoin de TOUS les Sharpe déjà observés sur cette stratégie :
    # c'est le nombre d'essais qui crée le biais, pas le meilleur essai.
    #
    # Unités : le moteur renvoie un Sharpe annualisé, le DSR attend un Sharpe
    # par barre cohérent avec n_obs. On dé-annualise des deux côtés (observé et
    # essais) pour rester homogène — mélanger les deux sature le z-score et rend
    # la porte inopérante.
    ann = math.sqrt(BARS_PER_YEAR.get(config["interval"], 2190))
    trial_sharpes = [t["sharpe"] / ann for t in read_trials(d)
                     if isinstance(t.get("sharpe"), (int, float))]
    obs_sharpe = oos_r.get("sharpe", 0) / ann
    trial_sharpes.append(obs_sharpe)

    n_obs_oos = max(len(df) - int(len(df) * 0.7), 2)
    dsr_val = deflated_sharpe_ratio(obs_sharpe, trial_sharpes, n_obs_oos)
    gate("G4_deflated_sharpe",
         isinstance(dsr_val, (int, float)) and dsr_val >= g["G4_deflated_sharpe_min"],
         f"DSR {dsr_val} sur {len(trial_sharpes)} essais, {n_obs_oos} barres OOS "
         f"(min {g['G4_deflated_sharpe_min']})")

    mc = monte_carlo_stability(fn, df, params, n_sims=15, perturb_pct=0.1)
    if "error" in mc:
        gate("G5_mc_stability", False, mc["error"])
    else:
        stable_pct = mc["mc_stability_pct"]
        gate("G5_mc_stability", stable_pct >= g["G5_mc_stability_min_pct"],
             f"{stable_pct}% des perturbations ±10% tiennent "
             f"(min {g['G5_mc_stability_min_pct']}%, {mc['n_sims']} sims)")

    dd = oos_r.get("max_dd_pct", 999)
    gate("max_drawdown", dd < g["max_dd_pct"], f"DD {dd}% (max {g['max_dd_pct']}%)")

    log_trial(d, {"kind": "validate", "params": params,
                  "oos": {k: v for k, v in oos_r.items() if k != "trades"},
                  "sharpe": oos_r.get("sharpe", 0),
                  "gates": {v["gate"]: v["pass"] for v in verdicts}})
    return _finish(d, config, verdicts)


def _finish(d: Path, config: dict, verdicts: list[dict]) -> dict:
    all_pass = all(v["pass"] for v in verdicts)
    config["gate_results"] = {v["gate"]: v["pass"] for v in verdicts}
    config["status"] = "PENDING_G6" if all_pass else "REJECTED"
    config["validated_at"] = datetime.now(timezone.utc).isoformat()
    (d / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False))

    if all_pass:
        print("\n✅ G1→G5 franchies → statut PENDING_G6")
        print("   G6 (obligatoire, manuelle) : compiler strategy.pine, lancer le")
        print("   Strategy Tester TradingView, comparer à ±20%.")
        print("   Seule cette étape a démasqué KB_15m. Aucun statut VALIDATED sans elle.")
    else:
        failed = [v["gate"] for v in verdicts if not v["pass"]]
        print(f"\n❌ REJETÉE — portes échouées : {', '.join(failed)}")
        print("   Un rejet est le résultat attendu la plupart du temps.")
    return {"status": config["status"], "verdicts": verdicts}


# ─────────────────────────────────────────────────────────────────────────────
# Optimisation
# ─────────────────────────────────────────────────────────────────────────────

def cmd_optimize(sid: str) -> dict:
    """Grille grossière. Chaque essai est journalisé — y compris les mauvais."""
    from core.data_source import load

    d, config, logic = load_strategy(sid)
    grid = config.get("param_grid", {})
    if not grid:
        raise SystemExit("param_grid vide dans config.json")
    if len(grid) > 2:
        raise SystemExit(
            f"param_grid contient {len(grid)} paramètres. Maximum 2 par itération "
            "(spec §2.1) — au-delà, l'espace de recherche dépasse ce que les "
            "données peuvent valider."
        )

    fn = _backtest_fn(logic, config["interval"])
    df = load(config["symbol"], config["interval"])

    # Optimiser sur l'in-sample uniquement. L'OOS reste vierge pour la validation.
    df_is = df.iloc[:int(len(df) * 0.7)]

    keys = list(grid)
    combos = list(itertools.product(*(grid[k] for k in keys)))
    print(f"🔬 {len(combos)} combinaisons sur l'in-sample ({len(df_is)} barres)\n")

    results = []
    for combo in combos:
        p = {**config["params"], **dict(zip(keys, combo))}
        r = fn(df_is, p)
        row = {"kind": "optimize", "params": dict(zip(keys, combo)),
               **{k: v for k, v in r.items() if k != "trades"}}
        log_trial(d, row)
        if "error" not in r:
            results.append((p, r))
            print(f"  {dict(zip(keys, combo))} → PF {r['pf']}  n={r['n_trades']}  "
                  f"DD {r['max_dd_pct']}%  exp {r['expectancy_r']}R")

    if not results:
        print("\n❌ aucune combinaison exploitable")
        return {}

    # Sélection sur le Profit Factor, jamais sur le Sharpe ni le win rate
    # (spec §1.2 : les deux se manipulent trop facilement).
    best_p, best_r = max(results, key=lambda x: x[1]["pf"])
    print(f"\n🏆 in-sample : {best_p} → PF {best_r['pf']}")
    print(f"   {len(combos)} essais journalisés → le DSR en tiendra compte.")

    config["params"] = best_p
    (d / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False))
    print(f"\n➡️  python3 core/strategy_bot.py validate {sid}")
    return {"best_params": best_p, "n_trials": len(combos)}


# ─────────────────────────────────────────────────────────────────────────────
# Inventaire
# ─────────────────────────────────────────────────────────────────────────────

def cmd_list():
    if not STRATEGIES_DIR.exists():
        print("aucune stratégie. `new <id>` pour commencer.")
        return
    rows = []
    for d in sorted(STRATEGIES_DIR.iterdir()):
        cfg_file = d / "config.json"
        if not d.is_dir() or not cfg_file.exists():
            continue
        c = json.loads(cfg_file.read_text())
        rows.append((c["id"], c["symbol"], c["interval"], c.get("status", "?"),
                     len(read_trials(d)), c.get("deploy_state", "-")))

    if not rows:
        print("aucune stratégie.")
        return
    print(f"\n{'ID':<20} {'SYMBOLE':<14} {'TF':<6} {'STATUT':<14} {'ESSAIS':<8} {'DEPLOY'}")
    print("─" * 76)
    for r in rows:
        print(f"{r[0]:<20} {r[1]:<14} {r[2]:<6} {r[3]:<14} {r[4]:<8} {r[5]}")
    print(f"\n{len(rows)} stratégie(s). VALIDATED exige G6 (test live TradingView).\n")


def main():
    ap = argparse.ArgumentParser(description="Bot standard par stratégie")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="créer le squelette d'une stratégie")
    p_new.add_argument("id")
    p_new.add_argument("--symbol", default="BTCUSDT")
    p_new.add_argument("--interval", default="4h")

    for name, helptext in [("backtest", "run unique"), ("validate", "portes G1→G5"),
                           ("optimize", "grille in-sample")]:
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("id")

    sub.add_parser("list", help="inventaire des stratégies")

    a = ap.parse_args()
    if a.cmd == "new":
        cmd_new(a.id, a.symbol, a.interval)
    elif a.cmd == "backtest":
        cmd_backtest(a.id)
    elif a.cmd == "validate":
        cmd_validate(a.id)
    elif a.cmd == "optimize":
        cmd_optimize(a.id)
    elif a.cmd == "list":
        cmd_list()


if __name__ == "__main__":
    main()
