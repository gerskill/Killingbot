"""
registry.py — Registre des stratégies. Aucune stratégie privilégiée.

Le système est agnostique : il n'existe pas de stratégie « principale », « par
défaut » ni « de tête ». Toute stratégie déposée dans strategies/ est découverte
et traitée exactement comme les autres. `pp_st_btc_4h` est la première du
registre, pas sa référence.

Ce qui est par défaut, c'est la MACHINE : données, backtest, portes de
validation, boucle d'apprentissage, routage, rapport. Chaque stratégie ajoutée
en hérite sans configuration supplémentaire.

Trois rôles :

  1. Découverte     — inventaire de strategies/*/config.json
  2. Routage        — setup_key du webhook → stratégie concernée
  3. Isolation      — chaque stratégie a ses params, ses guardrails, son
                      historique de boucle. Une mutation sur l'une n'affecte
                      jamais les autres (corrige le défaut « config globale
                      unique » relevé à l'audit du 2026-07-15).

Usage :
    from core.registry import all_strategies, by_setup_key, deployed

    for s in all_strategies():          # toutes, sans ordre privilégié
        print(s.id, s.status)

    s = by_setup_key("B")               # routage d'un signal entrant
    if s and s.is_live:
        ...

CLI :
    python3 core/registry.py            # inventaire
    python3 core/registry.py --routes   # table de routage
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent.parent
STRATEGIES_DIR = ROOT / "strategies"

# Clés réservées au pipeline historique (alerte TradingView en cours de
# collecte OOS). Aucune stratégie ne peut les revendiquer tant que la collecte
# n'est pas terminée : casser le routage détruirait la seule donnée
# hors-échantillon du projet.
LEGACY_SETUP_KEYS = {"A*", "B"}

# Statuts. Seul VALIDATED autorise un déploiement, et VALIDATED exige G6
# (test live TradingView) — voir core/strategy_bot.py.
STATUS_ORDER = ["DRAFT", "REJECTED", "PENDING_G6", "VALIDATED"]


@dataclass
class Strategy:
    """Une stratégie et son bot. Vue immuable de son config.json."""
    id: str
    path: Path
    config: dict = field(repr=False)

    @property
    def symbol(self) -> str:
        return self.config.get("symbol", "?")

    @property
    def interval(self) -> str:
        return self.config.get("interval", "?")

    @property
    def status(self) -> str:
        return self.config.get("status", "DRAFT")

    @property
    def setup_key(self) -> str:
        return self.config.get("setup_key", self.id[:8].upper())

    @property
    def deploy_state(self) -> str:
        return self.config.get("deploy_state", "paper")

    @property
    def params(self) -> dict:
        return self.config.get("params", {})

    @property
    def guardrails(self) -> dict:
        """Guardrails propres à la stratégie, jamais partagés."""
        return self.config.get("guardrails", {})

    @property
    def is_live(self) -> bool:
        """Une stratégie ne reçoit des signaux que validée ET déployée.

        PENDING_G6 ne suffit pas : G6 est la seule porte qui a démasqué KB_15m.
        """
        return self.status == "VALIDATED" and self.deploy_state in ("paper", "live")

    def has_logic(self) -> bool:
        return (self.path / "logic.py").exists()

    def has_pine(self) -> bool:
        return (self.path / "strategy.pine").exists()

    def n_trials(self) -> int:
        p = self.path / "trials.jsonl"
        if not p.exists():
            return 0
        return sum(1 for line in p.read_text().splitlines() if line.strip())

    def save(self):
        (self.path / "config.json").write_text(
            json.dumps(self.config, indent=2, ensure_ascii=False))


# ─────────────────────────────────────────────────────────────────────────────
# Découverte
# ─────────────────────────────────────────────────────────────────────────────

def all_strategies() -> list[Strategy]:
    """Toutes les stratégies, triées par identifiant.

    Tri alphabétique délibéré : aucun classement par performance, qui
    réintroduirait implicitement une stratégie « de tête ».
    """
    if not STRATEGIES_DIR.exists():
        return []
    out = []
    for d in sorted(STRATEGIES_DIR.iterdir()):
        cfg = d / "config.json"
        if not d.is_dir() or d.name.startswith((".", "_")) or not cfg.exists():
            continue
        try:
            out.append(Strategy(id=d.name, path=d, config=json.loads(cfg.read_text())))
        except json.JSONDecodeError as e:
            print(f"[REGISTRY] config.json illisible pour {d.name}: {e}", file=sys.stderr)
    return out


def get(strategy_id: str) -> Strategy | None:
    return next((s for s in all_strategies() if s.id == strategy_id), None)


def deployed() -> list[Strategy]:
    """Stratégies habilitées à recevoir des signaux."""
    return [s for s in all_strategies() if s.is_live]


def by_setup_key(setup_key: str) -> Strategy | None:
    """Routage d'un signal entrant. None = clé inconnue ou legacy."""
    key = (setup_key or "").strip().upper()
    return next((s for s in deployed() if s.setup_key.upper() == key), None)


# ─────────────────────────────────────────────────────────────────────────────
# Intégrité du routage
# ─────────────────────────────────────────────────────────────────────────────

def check_routing() -> dict:
    """Détecte les collisions de clés avant qu'elles ne détournent un signal.

    Deux stratégies partageant une setup_key rendent le routage ambigu : le
    signal irait à la première trouvée, silencieusement. Détecté ici plutôt
    qu'en production.
    """
    strategies = all_strategies()
    seen: dict[str, list[str]] = {}
    for s in strategies:
        seen.setdefault(s.setup_key.upper(), []).append(s.id)

    collisions = {k: v for k, v in seen.items() if len(v) > 1}
    legacy_conflicts = {k: v for k, v in seen.items() if k in LEGACY_SETUP_KEYS}

    return {
        "ok": not collisions and not legacy_conflicts,
        "n_strategies": len(strategies),
        "n_deployed": len(deployed()),
        "collisions": collisions,
        "legacy_conflicts": legacy_conflicts,
    }


def routing_table() -> list[dict]:
    return [{
        "setup_key": s.setup_key, "id": s.id, "symbol": s.symbol,
        "interval": s.interval, "status": s.status,
        "deploy_state": s.deploy_state, "routes": s.is_live,
    } for s in all_strategies()]


if __name__ == "__main__":
    if "--routes" in sys.argv:
        check = check_routing()
        print(json.dumps({"routing_check": check, "table": routing_table()},
                         indent=2, ensure_ascii=False))
        if not check["ok"]:
            print("\n⚠️  Routage ambigu — corriger les setup_key avant déploiement.",
                  file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    strategies = all_strategies()
    if not strategies:
        print("Registre vide. `python3 core/strategy_bot.py new <id>` pour commencer.")
        sys.exit(0)

    print(f"\n{'ID':<22} {'SYMBOLE':<14} {'TF':<6} {'STATUT':<13} {'KEY':<10} {'ESSAIS':<8} {'ROUTE'}")
    print("─" * 88)
    for s in strategies:
        print(f"{s.id:<22} {s.symbol:<14} {s.interval:<6} {s.status:<13} "
              f"{s.setup_key:<10} {s.n_trials():<8} {'oui' if s.is_live else '—'}")

    chk = check_routing()
    print(f"\n{chk['n_strategies']} stratégie(s), {chk['n_deployed']} routée(s).")
    if chk["collisions"]:
        print(f"⚠️  collisions de setup_key : {chk['collisions']}")
    if chk["legacy_conflicts"]:
        print(f"⚠️  conflit avec les clés legacy (OOS en cours) : {chk['legacy_conflicts']}")
    print()
