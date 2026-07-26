"""
Orchestrateur — Coordonne MemoryAgent + StrategyExplorer.
Lance les rounds d'exploration jusqu'à trouver ≥10%/mois ou épuiser les idées.
"""
import sys
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from memory_agent import MemoryAgent, VAULT, LOG_FILE
from strategy_explorer import StrategyExplorer

MAX_ROUNDS = 5  # rounds de suggestions après les prédéfinies
TARGET_MONTHLY = 10.0


def print_banner():
    print("\n" + "═" * 60)
    print("  KB Multi-Agent Backtester")
    print("  MemoryAgent ↔ StrategyExplorer")
    print(f"  Objectif : {TARGET_MONTHLY}%/mois | TF : 4H | 6 paires")
    print("═" * 60 + "\n")


def log_comm(msg: str):
    """Log orchestrateur visible dans le terminal ET dans le vault."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] 🤖 ORCHESTRATEUR — {msg}")
    with open(LOG_FILE, "a") as f:
        f.write(f"\n**ORCHESTRATEUR** [{ts}] — {msg}\n")


def run():
    print_banner()

    # Initialisation des agents
    log_comm("Démarrage MemoryAgent")
    mem = MemoryAgent()

    log_comm("Démarrage StrategyExplorer")
    explorer = StrategyExplorer(mem)

    # ── Round 0 : exploration prédéfinie ──────────────────────────────────────
    log_comm(f"Round 0 — exploration des {len(__import__('strategy_explorer').PREDEFINED_VARIATIONS)} variations prédéfinies")
    explorer.explore_all_predefined()

    # Rapport intermédiaire
    mem.write_best_report()
    best = mem.get_best(1)
    if best:
        top = best[0]
        monthly = top["metrics"].get("monthly_return_pct", 0)
        log_comm(f"Round 0 terminé. Meilleur : {top['name']} = {monthly:.1f}%/mois")

        if monthly >= TARGET_MONTHLY:
            log_comm(f"🎯 OBJECTIF ATTEINT dès Round 0 ! {top['name']} = {monthly:.1f}%/mois")
            _final_report(mem)
            return

    # ── Rounds suivants : suggestions heuristiques + génération LLM ───────────
    # Les deux tournent chaque round : l'heuristique couvre les ajustements
    # connus (RR, filtres), le LLM cherche des combinaisons jamais codées.
    for round_n in range(1, MAX_ROUNDS + 1):
        log_comm(f"Round {round_n} — suggestions MemoryAgent (heuristique)")
        explorer.explore_suggested()

        log_comm(f"Round {round_n} — génération LLM (Claude)")
        explorer.explore_suggested_llm(n=3)

        mem.write_best_report()
        best = mem.get_best(1)
        if best:
            top = best[0]
            monthly = top["metrics"].get("monthly_return_pct", 0)
            log_comm(f"Round {round_n} terminé. Meilleur : {top['name']} = {monthly:.1f}%/mois")

            if monthly >= TARGET_MONTHLY:
                log_comm(f"🎯 OBJECTIF ATTEINT au Round {round_n} ! {top['name']} = {monthly:.1f}%/mois")
                break
        else:
            log_comm(f"Round {round_n} — aucun résultat")

    _stability_check(mem, explorer)
    _final_report(mem)


def _stability_check(mem: MemoryAgent, explorer: StrategyExplorer):
    """Monte Carlo sur le gagnant final avant de le déclarer fiable."""
    best = mem.get_best(1)
    if not best:
        return
    top = best[0]
    log_comm(f"Vérification stabilité (Monte Carlo) sur {top['name']}...")
    clean_params = {k: v for k, v in top["params"].items() if not k.startswith("_")}
    result = explorer.stability_check(clean_params)
    if "error" in result:
        log_comm(f"Stability check échoué : {result['error']}")
        return
    stab = result["mc_stability_pct_avg"]
    verdict = "✅ ROBUSTE" if stab >= 70 else ("⚠️ FRAGILE" if stab >= 40 else "❌ OVERFIT PROBABLE")
    log_comm(f"Stabilité {top['name']} : {stab:.0f}% des perturbations tiennent la perf → {verdict}")
    with open(VAULT / "AGENT_LOG.md", "a") as f:
        f.write(f"\n**Stability check** `{top['name']}` : {stab:.0f}% stable → {verdict}\n")


def _final_report(mem: MemoryAgent):
    mem.write_best_report()
    best = mem.get_best(5)

    print("\n" + "═" * 60)
    print("  RÉSULTATS FINAUX")
    print("═" * 60)

    targets = [s for s in best if s["metrics"].get("monthly_return_pct", 0) >= TARGET_MONTHLY]
    if targets:
        print(f"\n✅ {len(targets)} stratégie(s) atteignent {TARGET_MONTHLY}%/mois :\n")
        for s in targets:
            m = s["metrics"]
            print(f"  🎯 {s['name']}")
            print(f"     {m['monthly_return_pct']:.1f}%/mois | WR {m['win_rate_pct']:.0f}% | "
                  f"{m['total_trades']} trades | DD {m['max_drawdown_pct']:.1f}% | Sharpe {m['sharpe_ratio']:.2f}")
    else:
        print(f"\n⚠️  Aucune stratégie n'atteint {TARGET_MONTHLY}%/mois. Top 5 :")

    print("\n  TOP 5 TOUTES STRATÉGIES:")
    for i, s in enumerate(best, 1):
        m = s["metrics"]
        target_flag = " 🎯" if m.get("monthly_return_pct", 0) >= TARGET_MONTHLY else ""
        print(f"  {i}. {s['name']}{target_flag}: {m['monthly_return_pct']:.1f}%/mois | "
              f"WR {m['win_rate_pct']:.0f}% | DD {m['max_drawdown_pct']:.1f}%")

    print(f"\n  📂 Vault Obsidian : {VAULT}")
    print(f"  📊 Graphe         : {Path(__file__).parent}/graph_view.html")
    print("═" * 60 + "\n")

    with open(VAULT / "AGENT_LOG.md", "a") as f:
        f.write(f"\n---\n## Rapport final — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Stratégies testées : {len(mem.memory['explored'])}\n")
        if targets:
            f.write(f"**Objectif atteint** : {', '.join(t['name'] for t in targets)}\n")
        else:
            f.write(f"Objectif non atteint. Meilleur : {best[0]['name']} = "
                    f"{best[0]['metrics']['monthly_return_pct']:.1f}%/mois\n")


if __name__ == "__main__":
    run()
