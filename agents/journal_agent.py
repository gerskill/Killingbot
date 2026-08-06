"""
JournalAgent — Clôture de la boucle d'apprentissage hebdomadaire.

Loop closure : trades de la semaine → analyse Claude → mutation incrémentale
des règles → auto-append loop_history.jsonl → update killingbot_config.json.

Les guardrails sont VALIDÉS EN CODE après la réponse de Claude — le prompt
seul ne suffit pas (un LLM peut halluciner un levier 10x, le code le bloque).

Usage :
    python3 agents/journal_agent.py            # run complet (écrit les fichiers)
    python3 agents/journal_agent.py --dry-run  # analyse sans écrire
"""
import csv
import json
import subprocess
import sys
from datetime import datetime, timedelta, UTC
from pathlib import Path

ROOT = Path(__file__).parent.parent
VAULT = ROOT / "vault"
TRADES_CSV = ROOT / "trades.csv"
CONFIG_FILE = ROOT / "killingbot_config.json"
LOOP_HISTORY = VAULT / "loop_history.jsonl"
LOG_FILE = VAULT / "AGENT_LOG.md"
SIGNALS_LOG = ROOT / "signals_log.jsonl"

SYSTEM_PROMPT = """# RÔLE ET OBJECTIF
Tu es le "Journal & Loop Closure Agent" de Killingbot, un système de trading algorithmique autonome en boucle fermée (TradingView MCP + IBKR).
Ton rôle unique est de clôturer la boucle d'apprentissage : analyser les trades de la semaine, confronter cette analyse à l'historique d'itérations précédentes, mettre à jour les règles, et formater l'entrée de journal pour l'auto-append.

# TON PROCESSUS OBLIGATOIRE (THE LOOP CLOSURE)
Tu reçois 3 éléments en input : [CURRENT_RULES], [LOOP_HISTORY], et [WEEKLY_TRADE_LOGS].

1. ANALYSE DE PERFORMANCE :
- Évalue le PnL, le Win Rate, et le slippage IBKR vs signaux TradingView.
- Identifie précisément quelle règle a causé les pertes ou manqué les gains.
- Analyse [UPSTREAM_FILTER_STATS] : le regime filter et le macro kill switch tournent EN AMONT des trades. Si beaucoup de signaux ont été bloqués, évalue si les filtres ont eu raison (les trades pris pendant les fenêtres autorisées étaient-ils meilleurs ?). Un filtre trop strict qui bloque de bons signaux est aussi un défaut à signaler.

2. PROTECTION ANTI FLIP-FLOP (CRITIQUE) :
- Lis le [LOOP_HISTORY].
- Tu n'as pas le droit de proposer un retour en arrière vers une règle utilisée dans les 3 dernières itérations, SAUF changement structurel de marché clair (ex: range → trend fort). L'instabilité de règles est ton pire ennemi.

3. MUTATION INCRÉMENTALE :
- Ne modifie qu'UN SEUL ou DEUX paramètres maximum par itération. Ne réécris pas toute la stratégie.
- Si la semaine est bonne et qu'aucun défaut clair n'émerge : NE CHANGE RIEN (param_to_change: "none").

# CONTRAINTES DE SÉCURITÉ (GUARDRAILS)
- Si le Drawdown de la semaine dépasse -5%, ta modification doit obligatoirement réduire le risque (size ou stop-loss).
- Ne jamais proposer de levier supérieur à 5.
- Toujours prendre en compte les frais de transaction dans l'analyse de l'échec d'un trade.

# FORMAT DE SORTIE (STRICTEMENT JSON)
Ta réponse DOIT être un objet JSON valide. Aucun texte avant ou après. Pas de markdown. Schéma exact :
{
  "loop_status": "LOOP_CLOSED",
  "performance_analysis": {
    "win_rate": "X%",
    "pnl": "X R",
    "main_failure_cause": "Description concise",
    "main_success_cause": "Description concise"
  },
  "anti_flip_flop_check": "Confirmation que la nouvelle règle ne répète pas N-1, N-2 ou N-3.",
  "rules_update": {
    "param_to_change": "nom_du_parametre ou 'none'",
    "old_value": "ancienne_valeur",
    "new_value": "nouvelle_valeur",
    "justification": "Justification basée sur les logs de la semaine"
  },
  "append_to_loop_history": {
    "week": "YYYY-MM-DD",
    "version": "vX.X",
    "changes": "param_to_change de old_value vers new_value",
    "reason": "Résumé court de la justification"
  },
  "next_run_config": {
    "action": "RE_RUN_NEXT_WEEK",
    "new_strategy_json": {
      "indicators": "...",
      "entry_conditions": "...",
      "exit_conditions": "...",
      "risk_params": {}
    }
  }
}"""


# ── Inputs ──────────────────────────────────────────────────────────────────

def get_weekly_trades() -> list[dict]:
    """Trades des 7 derniers jours depuis trades.csv (rempli par webhook_server / IBKR)."""
    if not TRADES_CSV.exists():
        return []
    # Naive UTC : les dates du CSV sont naive, la comparaison doit l'être aussi
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)
    trades = []
    with open(TRADES_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                if datetime.strptime(row["date"], "%Y-%m-%d") >= cutoff:
                    trades.append(row)
            except (ValueError, KeyError):
                continue
    return trades


def read_config() -> dict:
    with open(CONFIG_FILE) as f:
        return json.load(f)


def read_loop_history(n: int = 5) -> list[dict]:
    if not LOOP_HISTORY.exists():
        return []
    lines = LOOP_HISTORY.read_text().strip().splitlines()
    return [json.loads(line) for line in lines[-n:]]


def get_weekly_filter_stats() -> dict:
    """Bilan des filtres amont sur 7 jours : signaux reçus / bloqués et pourquoi.
    Un filtre qui bloque tout n'est visible que si on le compte."""
    stats = {"signals_total": 0, "blocked_regime": 0, "blocked_macro": 0,
             "passed": 0, "regimes_seen": {}}
    if not SIGNALS_LOG.exists():
        return stats
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)
    for line in SIGNALS_LOG.read_text().splitlines():
        try:
            sig = json.loads(line)
            ts = datetime.fromisoformat(sig.get("received_at", "").rstrip("Z"))
        except (ValueError, json.JSONDecodeError):
            continue
        if ts < cutoff:
            continue
        stats["signals_total"] += 1
        regime = sig.get("regime", "UNKNOWN")
        stats["regimes_seen"][regime] = stats["regimes_seen"].get(regime, 0) + 1
        if sig.get("macro_blocked"):
            stats["blocked_macro"] += 1
        elif regime == "UNDECIDED":
            stats["blocked_regime"] += 1
        else:
            stats["passed"] += 1
    return stats


def weekly_drawdown_pct(trades: list[dict], account_size: float = 25000) -> float:
    """DD intra-semaine sur la courbe de PnL cumulée."""
    equity, peak, max_dd = 0.0, 0.0, 0.0
    for t in trades:
        try:
            equity += float(t.get("pnl_usd") or 0)
        except ValueError:
            continue
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    return round(max_dd / account_size * 100, 2)


# ── Appel Claude : SDK (API key) d'abord, CLI en fallback ───────────────────
# SDK  : stateless, parfait pour cron, facturé au token (console.anthropic.com).
# CLI  : utilise l'abonnement Claude, mais exige `claude /login` interactif.

DEFAULT_MODEL = "claude-sonnet-5"  # override : KILLINGBOT_MODEL dans .env


def _parse_response(text: str) -> dict:
    text = text.strip()
    # Tolère un éventuel bloc markdown malgré la consigne
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    return json.loads(text)


def _call_via_sdk(user_message: str) -> dict:
    import os
    import anthropic
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key.startswith("sk-ant-"):
        raise RuntimeError("ANTHROPIC_API_KEY absente ou invalide dans .env")
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=os.environ.get("KILLINGBOT_MODEL", DEFAULT_MODEL),
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return _parse_response(msg.content[0].text)


def _call_via_cli(user_message: str) -> dict:
    import os
    # Env propre : un run cron n'hérite pas des variables de session Claude Code,
    # et une session imbriquée avec ANTHROPIC_BASE_URL hérité provoque un 401.
    clean_env = {k: v for k, v in os.environ.items()
                 if not k.startswith(("ANTHROPIC", "CLAUDE", "BAGGAGE", "AI_AGENT"))}
    result = subprocess.run(
        ["claude", "-p", user_message,
         "--append-system-prompt", SYSTEM_PROMPT,
         "--output-format", "json",
         "--max-turns", "1",
         # Pas d'outils ni de MCP : analyse pure, démarrage rapide
         "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
         "--disallowed-tools", "*"],
        capture_output=True, text=True, timeout=300,
        cwd=str(ROOT), env=clean_env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI a échoué : {result.stderr[:500]}")
    wrapper = json.loads(result.stdout)
    if wrapper.get("is_error"):
        raise RuntimeError(f"claude CLI en erreur : {wrapper.get('result', '')[:300]}")
    return _parse_response(wrapper.get("result", ""))


def call_claude(user_message: str) -> dict:
    try:
        return _call_via_sdk(user_message)
    except Exception as sdk_err:
        print(f"[SDK] indisponible ({str(sdk_err)[:120]}) → fallback CLI")
        return _call_via_cli(user_message)


# ── Guardrails code-enforced ────────────────────────────────────────────────

class GuardrailViolation(Exception):
    pass


def validate(response: dict, config: dict, history: list[dict], week_dd: float):
    g = config["guardrails"]
    update = response.get("rules_update", {})
    param = update.get("param_to_change", "none")

    # Levier plafonné, où qu'il apparaisse
    risk = response.get("next_run_config", {}).get("new_strategy_json", {}).get("risk_params", {})
    lev = risk.get("leverage")
    if lev is not None and float(lev) > g["max_leverage"]:
        raise GuardrailViolation(f"Levier {lev} > max {g['max_leverage']}")
    if param == "leverage" and float(update.get("new_value", 0)) > g["max_leverage"]:
        raise GuardrailViolation(f"rules_update propose levier {update['new_value']} > max")

    # DD hebdo < -5% → la mutation doit réduire le risque
    if week_dd <= g["weekly_dd_force_risk_reduction_pct"]:
        risk_reducing = {"sl_atr_mult", "risk_per_trade_pct", "leverage", "position_size", "atr_mult"}
        if param not in risk_reducing:
            raise GuardrailViolation(
                f"DD semaine {week_dd}% ≤ {g['weekly_dd_force_risk_reduction_pct']}% : "
                f"la mutation doit réduire le risque, reçu '{param}'")

    # Anti flip-flop : pas de retour à une valeur des N dernières itérations
    if param != "none":
        recent = " ".join(h.get("changes", "") for h in history[-g["flip_flop_lookback_iterations"]:])
        if f"{param} de {update.get('new_value')}" in recent:
            raise GuardrailViolation(f"Flip-flop détecté : {param}={update.get('new_value')} déjà utilisé récemment")


# ── Écritures (la clôture effective) ────────────────────────────────────────

def append_history(entry: dict):
    with open(LOOP_HISTORY, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def update_config(config: dict, response: dict):
    update = response["rules_update"]
    param = update.get("param_to_change", "none")
    if param != "none" and param in config["strategy"]["params"]:
        config["strategy"]["params"][param] = update["new_value"]
    if param != "none" and param in config["strategy"]["risk_params"]:
        config["strategy"]["risk_params"][param] = update["new_value"]
    # Version bump + horodatage
    ver_parts = config["version"].lstrip("v").split(".", 1)
    major = ver_parts[0]
    try:
        minor = int(ver_parts[1]) + 1 if len(ver_parts) > 1 else 1
    except ValueError:
        minor = 1
    config["version"] = f"v{major}.{minor}"
    config["updated_at"] = datetime.now(UTC).isoformat()
    # Atomic write: write to temp then replace — crash mid-write can't corrupt config
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CONFIG_FILE)


def log(msg: str):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')} **JournalAgent** — {msg}\n")


# ── Main ────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False):
    trades = get_weekly_trades()
    config = read_config()
    history = read_loop_history()
    filters = get_weekly_filter_stats()

    if not trades:
        # Semaine plate ≠ semaine vide : si les filtres ont bloqué des signaux,
        # c'est une information — on la journalise sans appeler Claude.
        if filters["signals_total"] > 0:
            entry = {
                "week": datetime.now(UTC).replace(tzinfo=None).strftime("%Y-%m-%d"),
                "version": config["version"],
                "changes": "none (semaine plate)",
                "reason": (f"{filters['signals_total']} signaux reçus, "
                           f"{filters['blocked_regime']} bloqués par regime filter, "
                           f"{filters['blocked_macro']} par macro kill switch. "
                           f"0 trade = 0 perte en marché injouable."),
                "filter_stats": filters,
            }
            if not dry_run:
                append_history(entry)
            print(f"Semaine plate journalisée : {entry['reason']}")
            log(f"semaine plate : {entry['reason']}")
        else:
            print("Aucun signal ni trade cette semaine — boucle non exécutée.")
            log("skip : 0 signal, 0 trade sur 7 jours")
        return

    week_dd = weekly_drawdown_pct(trades)
    user_message = (
        f"[CURRENT_RULES]: {json.dumps(config, ensure_ascii=False)}\n"
        f"[LOOP_HISTORY]: {json.dumps(history, ensure_ascii=False)}\n"
        f"[WEEKLY_TRADE_LOGS]: {json.dumps(trades, ensure_ascii=False)}\n"
        f"[UPSTREAM_FILTER_STATS]: {json.dumps(filters, ensure_ascii=False)}\n"
        f"[COMPUTED_WEEKLY_DD_PCT]: {week_dd}"
    )

    print(f"→ {len(trades)} trades, DD semaine {week_dd}%. Appel Claude…")
    response = call_claude(user_message)

    try:
        validate(response, config, history, week_dd)
    except GuardrailViolation as e:
        print(f"⛔ GUARDRAIL : {e}\nAucune écriture. Mutation rejetée, config inchangée.")
        log(f"REJET guardrail : {e}")
        append_history({
            "week": datetime.now(UTC).strftime("%Y-%m-%d"),
            "version": config["version"],
            "changes": "none (mutation rejetée par guardrail)",
            "reason": str(e),
        })
        return

    print(json.dumps(response, indent=2, ensure_ascii=False))
    if dry_run:
        print("\n[dry-run] Aucune écriture.")
        return

    append_history(response["append_to_loop_history"])
    update_config(config, response)
    log(f"LOOP_CLOSED : {response['append_to_loop_history']['changes']}")
    print(f"\n✅ Boucle fermée. Config → {config['version']}, historique appendé.")


if __name__ == "__main__":
    run(dry_run="--dry-run" in sys.argv)
