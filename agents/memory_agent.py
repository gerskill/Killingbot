"""
MemoryAgent — Retient les meilleures stratégies, guide l'Explorateur.
Rôle : assistant de contexte. Reçoit résultats → classe → suggère suivant.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import validation

VAULT = Path(__file__).parent.parent / "vault"
MEMORY_FILE = VAULT / "memory.json"
LOG_FILE = VAULT / "AGENT_LOG.md"


class MemoryAgent:
    def __init__(self):
        self.name = "MemoryAgent"
        VAULT.mkdir(exist_ok=True)
        (VAULT / "strategies").mkdir(exist_ok=True)
        (VAULT / "sessions").mkdir(exist_ok=True)
        self.memory = self._load()
        self._log(f"## Session {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        self._log(f"**{self.name}** — démarrage. {len(self.memory['results'])} stratégies en mémoire.\n")

    # ── Persistance ────────────────────────────────────────────────────────────

    def _load(self):
        if MEMORY_FILE.exists():
            try:
                with open(MEMORY_FILE) as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                corrupt = MEMORY_FILE.with_suffix(".json.corrupt")
                MEMORY_FILE.rename(corrupt)
                print(f"[MEMORY] Fichier corrompu → {corrupt} ({e})", file=sys.stderr)
        return {"results": [], "best": None, "explored": [], "session": 0}

    def _save(self):
        tmp = MEMORY_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.memory, indent=2), encoding="utf-8")
        tmp.replace(MEMORY_FILE)

    def _log(self, msg: str):
        with open(LOG_FILE, "a") as f:
            f.write(msg + "\n")

    # ── API publique ───────────────────────────────────────────────────────────

    def receive_result(self, strategy_name: str, params: dict, metrics: dict):
        """Reçoit un résultat de l'Explorateur, met à jour la mémoire."""
        # Deflated Sharpe : corrige le biais de sélection (on a déjà testé N
        # variantes avant celle-ci, le meilleur des N gagne un peu par hasard).
        # Calculé sur l'historique AVANT d'ajouter l'entrée courante.
        prior_sharpes = [r["metrics"].get("sharpe_ratio", 0) for r in self.memory["results"]]
        trial_sharpes = prior_sharpes + [metrics.get("sharpe_ratio", 0)]
        n_obs = max(metrics.get("total_trades", 1), 2)
        dsr = validation.deflated_sharpe_ratio(metrics.get("sharpe_ratio", 0), trial_sharpes, n_obs)
        if dsr is not None:
            metrics["deflated_sharpe"] = dsr

        entry = {
            "name": strategy_name,
            "params": params,
            "metrics": metrics,
            "ts": datetime.now().isoformat(),
        }
        self.memory["results"].append(entry)
        self.memory["explored"].append(strategy_name)

        monthly = metrics.get("monthly_return_pct", 0)
        wr = metrics.get("win_rate_pct", 0)
        trades = metrics.get("total_trades", 0)
        oos_degr = metrics.get("oos_degradation_pct")

        status = "🎯 TARGET" if monthly >= 10 else ("✅" if monthly >= 5 else ("⚠️" if monthly >= 0 else "❌"))
        flags = []
        if oos_degr is not None and oos_degr < -50:
            flags.append(f"⚠️ OOS s'effondre ({oos_degr:+.0f}%)")
        if dsr is not None and dsr < 0.95:
            flags.append(f"⚠️ deflated_sharpe bas ({dsr:.2f} < 0.95)")
        flag_str = " " + " ".join(flags) if flags else ""
        self._log(
            f"**{self.name}** → reçu `{strategy_name}` "
            f"| {status} {monthly:.1f}%/mois | WR {wr:.0f}% | {trades} trades{flag_str}"
        )

        # Mise à jour du best
        best = self.memory.get("best")
        if best is None or monthly > best.get("metrics", {}).get("monthly_return_pct", -999):
            self.memory["best"] = entry
            self._log(f"**{self.name}** → 🏆 nouveau meilleur : `{strategy_name}` ({monthly:.1f}%/mois)")

        self._save()
        self._write_strategy_note(entry)
        return status

    def get_best(self, n: int = 5) -> list:
        """Retourne les N meilleures stratégies."""
        sorted_r = sorted(
            self.memory["results"],
            key=lambda x: x["metrics"].get("monthly_return_pct", -999),
            reverse=True,
        )
        return sorted_r[:n]

    def suggest_next(self, current_params: dict) -> list[dict]:
        """
        Analyse les résultats précédents et suggère des variations prometteuses.
        L'Explorateur appelle ça pour décider quoi tester ensuite.
        """
        best = self.get_best(3)
        suggestions = []

        if not best:
            return []

        top = best[0]
        top_params = top["params"]
        top_monthly = top["metrics"].get("monthly_return_pct", 0)

        self._log(
            f"**{self.name}** → analyse top 3 pour suggestions. "
            f"Meilleur actuel : `{top['name']}` ({top_monthly:.1f}%/mois)"
        )

        # Si le meilleur a un bon WR mais mauvais RR → augmenter RR
        if top["metrics"].get("win_rate_pct", 0) > 50 and top_params.get("rr", 2.0) < 3.0:
            v = dict(top_params)
            v["rr"] = round(v["rr"] + 0.5, 1)
            v["_name_hint"] = f"{top['name']}_RR{v['rr']}"
            v["_reason"] = f"WR élevé ({top['metrics']['win_rate_pct']:.0f}%) → hausser RR"
            suggestions.append(v)

        # Si le meilleur a peu de trades → assouplir filtres
        if top["metrics"].get("total_trades", 0) < 15:
            v = dict(top_params)
            v["ema_sep_pct"] = max(0.1, v.get("ema_sep_pct", 0.3) - 0.1)
            v["cooldown_bars"] = max(2, v.get("cooldown_bars", 5) - 2)
            v["_name_hint"] = f"{top['name']}_LOOSE"
            v["_reason"] = "Peu de trades → assouplir filtres"
            suggestions.append(v)

        # Si le meilleur a trop de trades (whipsaw) → renforcer filtres
        if top["metrics"].get("total_trades", 0) > 60:
            v = dict(top_params)
            v["ema_sep_pct"] = min(1.0, v.get("ema_sep_pct", 0.3) + 0.15)
            v["cooldown_bars"] = v.get("cooldown_bars", 5) + 3
            v["_name_hint"] = f"{top['name']}_TIGHT"
            v["_reason"] = "Trop de trades → renforcer filtres"
            suggestions.append(v)

        # Si aucun filtre RSI/ADX actif sur le top → essayer
        if not top_params.get("use_rsi") and not top_params.get("use_adx"):
            v = dict(top_params)
            v["use_rsi"] = True
            v["_name_hint"] = f"{top['name']}_RSI"
            v["_reason"] = "Ajouter filtre RSI"
            suggestions.append(v)

        for s in suggestions:
            self._log(f"**{self.name}** → 💡 suggestion `{s.get('_name_hint', '?')}` — {s.get('_reason', '')}")

        return suggestions

    def suggest_next_llm(self, n: int = 3) -> list[dict]:
        """
        Génération créative via Claude (option A) — complète suggest_next().
        Contrairement aux règles if/else fixes, propose des combinaisons de
        params jamais codées à l'avance. Retourne [] si pas de clé API ou erreur,
        jamais d'exception qui casse la boucle.
        """
        from llm_generator import generate_variations

        top = self.get_best(5)
        if not top:
            return []

        variations = generate_variations(top, self.memory["explored"], n=n)
        for v in variations:
            self._log(f"**{self.name}** → 🧠 LLM suggestion `{v.get('_name_hint', '?')}` — {v.get('_reason', '')}")
        return variations

    def already_explored(self, name: str) -> bool:
        return name in self.memory["explored"]

    def write_best_report(self):
        """Génère vault/BEST_STRATEGIES.md"""
        best = self.get_best(10)
        lines = [
            "# 🏆 Meilleures Stratégies KB\n",
            f"_Mise à jour : {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n",
            "_%/mois = in-sample. OOS = perf out-of-sample (jamais utilisée pour classer). "
            "DSR = deflated Sharpe (probabilité que ce ne soit pas juste le meilleur tirage parmi les essais faits ; <0.95 = pas fiable)._\n",
            "| Rang | Stratégie | %/mois IS | OOS | Dégr. OOS | WR | Trades | Drawdown | Sharpe | DSR |",
            "|------|-----------|-----------|-----|-----------|-----|--------|----------|--------|-----|",
        ]
        for i, r in enumerate(best, 1):
            m = r["metrics"]
            target = " 🎯" if m.get("monthly_return_pct", 0) >= 10 else ""
            oos = m.get("oos_monthly_return_pct")
            degr = m.get("oos_degradation_pct")
            dsr = m.get("deflated_sharpe")
            oos_str = f"{oos:.1f}%" if oos is not None else "N/A"
            degr_str = f"{degr:+.0f}%" if degr is not None else "N/A"
            dsr_str = f"{dsr:.2f}" if dsr is not None else "N/A"
            warn = ""
            if degr is not None and degr < -50:
                warn += "⚠️"
            if dsr is not None and dsr < 0.95:
                warn += "⚠️"
            lines.append(
                f"| {i} | [[{r['name']}]]{target}{warn} "
                f"| {m.get('monthly_return_pct', 0):.1f}% "
                f"| {oos_str} "
                f"| {degr_str} "
                f"| {m.get('win_rate_pct', 0):.0f}% "
                f"| {m.get('total_trades', 0)} "
                f"| {m.get('max_drawdown_pct', 0):.1f}% "
                f"| {m.get('sharpe_ratio', 0):.2f} "
                f"| {dsr_str} |"
            )
        lines.append("\n## Détail")
        for r in best:
            m = r["metrics"]
            oos = m.get("oos_monthly_return_pct")
            degr = m.get("oos_degradation_pct")
            dsr = m.get("deflated_sharpe")
            oos_line = f"- **Retour mensuel (OOS)** : {oos:.2f}% (dégradation {degr:+.0f}%)" \
                if oos is not None and degr is not None else "- **OOS** : N/A"
            sharpe_line = f"- **Sharpe** : {m.get('sharpe_ratio', 0):.2f} (deflated: {dsr:.2f})" \
                if dsr is not None else f"- **Sharpe** : {m.get('sharpe_ratio', 0):.2f}"

            lines.append(
                f"\n### [[{r['name']}]]\n"
                f"- **Retour mensuel (IS)** : {m.get('monthly_return_pct', 0):.2f}%\n"
                f"{oos_line}\n"
                f"- **Win Rate** : {m.get('win_rate_pct', 0):.1f}%\n"
                f"- **Trades** : {m.get('total_trades', 0)}\n"
                f"- **Drawdown max** : {m.get('max_drawdown_pct', 0):.1f}%\n"
                f"{sharpe_line}\n"
                f"- **Paramètres** : `{json.dumps({k: v for k, v in r['params'].items() if not k.startswith('_')})}`\n"
            )
        with open(VAULT / "BEST_STRATEGIES.md", "w") as f:
            f.write("\n".join(lines))
        self._log(f"**{self.name}** → 📄 BEST_STRATEGIES.md mis à jour")

    def _write_strategy_note(self, entry: dict):
        """Crée une note Obsidian pour chaque stratégie."""
        name = entry["name"]
        m = entry["metrics"]
        p = entry["params"]
        target = "🎯 OBJECTIF ATTEINT" if m.get("monthly_return_pct", 0) >= 10 else ""
        parent = p.get("_parent", "KB-v2.1")
        note = (
            f"# {name} {target}\n\n"
            f"**Parent** : [[{parent}]]\n"
            f"**Date** : {entry['ts'][:10]}\n\n"
            f"## Performance\n"
            f"- Retour mensuel : **{m.get('monthly_return_pct', 0):.2f}%**\n"
            f"- Win Rate : {m.get('win_rate_pct', 0):.1f}%\n"
            f"- Trades : {m.get('total_trades', 0)}\n"
            f"- Drawdown max : {m.get('max_drawdown_pct', 0):.1f}%\n"
            f"- Profit Factor : {m.get('profit_factor', 0):.2f}\n"
            f"- Sharpe : {m.get('sharpe_ratio', 0):.2f}\n\n"
            f"## Paramètres\n"
            f"```json\n{json.dumps({k: v for k, v in p.items() if not k.startswith('_')}, indent=2)}\n```\n\n"
            f"## Liens\n"
            f"- [[BEST_STRATEGIES]]\n"
            f"- [[AGENT_LOG]]\n"
        )
        with open(VAULT / "strategies" / f"{name}.md", "w") as f:
            f.write(note)
