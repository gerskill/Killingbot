#!/usr/bin/env python3
"""
webhook_server.py — Serveur webhook local pour alertes TradingView
===================================================================
Reçoit les alertes JSON de TradingView directement (sans 3Commas).
Loggue les signaux A*/B, appelle les agents Claude Code.

Démarrage :
    pip install flask --break-system-packages
    python webhook_server.py

Exposer via ngrok (port 5001) :
    ngrok http 5001
    → Coller l'URL https://xxxx.ngrok.io/webhook dans TradingView Alerts

Format attendu depuis HybridAI_TraderMorin.pine :
    {"setup":"A*","dir":"LONG","ticker":"BTCUSD","tf":"60","price":"68500.00","exchange":"BINANCE"}
"""

import hmac
import json
import csv
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, request, jsonify

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
PORT          = 5001
TRADES_CSV    = Path(__file__).parent / "trades.csv"
SIGNALS_LOG   = Path(__file__).parent / "signals_log.jsonl"
PINE_FILE     = Path(__file__).parent / "HybridAI_TraderMorin.pine"
CURRENT_PINE  = Path(__file__).parent / "scripts" / "current.pine"

# Seuil d'action : seulement les A* déclenchent un log actif (B = log passif)
ACTION_SETUPS = {"A*"}
LOG_SETUPS    = {"A*", "B"}

load_dotenv(Path(__file__).parent / ".env")

# Jeton d'URL. TradingView ne permet pas d'ajouter d'en-tête à une alerte, donc
# ni signature HMAC ni Authorization : le secret doit voyager dans l'URL.
# Une liste blanche d'IP ne conviendrait pas non plus — le tunnel se connecte à
# localhost, donc Flask voit 127.0.0.1 pour toute requête et l'IP d'origine
# n'est lisible que dans X-Forwarded-For, en-tête forgeable.
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")

app = Flask(__name__)


def require_token(token: str):
    """Refuse la requête si le jeton d'URL ne correspond pas.

    404 plutôt que 403 : une route inexistante et une route protégée doivent
    être indiscernables pour qui sonde le tunnel.
    """
    if not hmac.compare_digest(token, WEBHOOK_TOKEN):
        print(f"[AUTH]   jeton invalide sur {request.path}")
        abort(404)

# ─────────────────────────────────────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────────────────────────────────────
def log_signal(payload: dict):
    """Ajoute le signal au fichier JSONL de log.

    Best-effort : un échec d'écriture (ex. OSError errno 11 "Resource deadlock
    avoided" observé le 2026-07-19, collision probable avec le cron 5 min) ne
    doit jamais faire échouer le traitement du signal — le 500 renvoyé à
    TradingView ferait perdre l'alerte définitivement.
    """
    entry = {**payload, "received_at": datetime.utcnow().isoformat() + "Z"}
    try:
        with open(SIGNALS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        print(f"[SIGNAL] échec écriture log ({e}) — signal traité quand même")
    print(f"[SIGNAL] {entry['received_at']} | {entry.get('setup')} {entry.get('dir')} {entry.get('ticker')} @ {entry.get('price')}")


def append_trade_csv(payload: dict):
    """Ajoute une ligne dans trades.csv pour le journal de performance."""
    fieldnames = ["date", "time", "symbol", "side", "entry_price",
                  "exit_price", "shares", "pnl_usd", "pnl_pct",
                  "setup_type", "notes"]
    now = datetime.utcnow()
    row = {
        "date":        now.strftime("%Y-%m-%d"),
        "time":        now.strftime("%H:%M"),
        "symbol":      payload.get("ticker", ""),
        "side":        payload.get("dir", "").lower(),
        "entry_price": payload.get("price", ""),
        "exit_price":  "",
        "shares":      "",
        "pnl_usd":     "",
        "pnl_pct":     "",
        "setup_type":  payload.get("setup", ""),
        "notes":       f"tf:{payload.get('tf','')} ex:{payload.get('exchange','')} auto-webhook",
    }
    write_header = not TRADES_CSV.exists()
    with open(TRADES_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    print(f"[CSV]    Trade loggué → {TRADES_CSV.name}")


def call_claude_agent(agent_name: str, context: str):
    """Appelle un sous-agent Claude Code en CLI.

    Best-effort : le signal a déjà été loggé avant cet appel. Une erreur ici
    ne doit jamais faire échouer la réponse HTTP au webhook — TOUTE exception
    est capturée (pas seulement FileNotFoundError/TimeoutExpired) pour éviter
    la 500 intermittente observée le 2026-07-18/19.
    """
    cmd = ["claude", "--agent", agent_name, "--print", context]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        print(f"[AGENT]  {agent_name} → {result.stdout[:120]}")
        return result.stdout
    except FileNotFoundError:
        print(f"[AGENT]  claude CLI non trouvé — agent {agent_name} ignoré")
    except subprocess.TimeoutExpired:
        print(f"[AGENT]  {agent_name} timeout")
    except Exception as e:
        print(f"[AGENT]  erreur inattendue ({type(e).__name__}: {e}) — agent {agent_name} ignoré, signal déjà loggé")
    return None

# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/webhook/<token>", methods=["GET", "HEAD", "POST"])
def webhook(token):
    """Point d'entrée principal — reçoit les alertes TradingView.

    GET/HEAD acceptés en plus de POST : TradingView sonde l'URL webhook avec
    une requête de vérification avant d'accepter de l'enregistrer dans
    l'alerte — sans ça, le champ est rejeté en silence côté UI (405 vu comme
    URL invalide). Ces méthodes ne font rien d'autre que confirmer le jeton.
    """
    require_token(token)
    if request.method in ("GET", "HEAD"):
        return jsonify({"status": "ok"}), 200
    try:
        payload = request.get_json(force=True)
    except Exception:
        payload = {"raw": request.data.decode("utf-8", errors="replace")}

    if not payload:
        return jsonify({"status": "error", "msg": "empty payload"}), 400

    setup = payload.get("setup", "").upper()

    # ─── ROUTAGE PAR STRATÉGIE ───
    # Le registre (strategies/*/config.json) associe une setup_key à une
    # stratégie déployée. Aucune stratégie n'est privilégiée : le routage est
    # une simple correspondance de clé.
    #
    # Repli sur le pipeline historique si la clé est inconnue : l'alerte en
    # cours de collecte OOS émet setup:"B", qui n'appartient à aucune stratégie
    # du registre. Casser ce chemin détruirait la seule donnée hors-échantillon
    # du projet.
    routed = None
    try:
        from core.registry import by_setup_key
        routed = by_setup_key(setup)
        if routed is not None:
            payload["strategy_id"] = routed.id
            print(f"[ROUTE]  {setup} → {routed.id} ({routed.symbol} {routed.interval})")
    except Exception as e:
        print(f"[ROUTE]  registre indisponible ({e}) — repli sur le pipeline historique")

    # Ignorer les setups C et inconnus
    if routed is None and setup not in LOG_SETUPS:
        return jsonify({"status": "ignored", "setup": setup}), 200

    # ─── EXIT DE STRATÉGIE (avant les filtres — une sortie ne se filtre pas) ───
    # Stratégie long-only : "sell" ({{strategy.order.action}} du fill de close)
    # ou "flat" ({{strategy.market_position}} après close) = clôture, jamais
    # une entrée short. Le régime/macro ne doit JAMAIS bloquer une sortie.
    dir_raw = str(payload.get("dir", "")).lower()
    if dir_raw in ("sell", "flat", "close"):
        log_signal(payload)
        try:
            from core.paper_executor import close_from_signal
            result = close_from_signal(payload)
            print(f"[PAPER]  exit sync : {result['reason']}")
            return jsonify({"status": "ok", "action": "exit_sync",
                            "closed": result["closed"], "detail": result["reason"]}), 200
        except Exception as e:
            print(f"[PAPER]  erreur exit sync ({e}) — signal loggé seulement")
            return jsonify({"status": "executor_error", "action": "exit_sync_failed",
                            "detail": str(e)}), 200

    # ─── FILTRE DE RÉGIME (condition stricte, en amont de tout) ───
    # UNDECIDED → signal rejeté avant même la validation confluence.
    # L'abstention est une position. Voir core/market_regime.py.
    try:
        from core.market_regime import detect_market_regime, fetch_binance_klines
        tf_map = {"1": "1m", "5": "5m", "15": "15m", "60": "1h", "240": "4h", "D": "1d"}
        interval = tf_map.get(str(payload.get("tf", "15")), "15m")
        symbol = str(payload.get("ticker", "BTCUSDT")).replace("/", "").replace("PERP", "")
        regime = detect_market_regime(fetch_binance_klines(symbol, interval))
        payload["regime"] = regime["regime"]
        payload["regime_metrics"] = regime["metrics"]
        if not regime["tradeable"]:
            log_signal(payload)  # trace du rejet, jamais silencieux
            print(f"[REGIME] REJET {symbol} {interval} : {regime['regime']} {regime['metrics']}")
            return jsonify({"status": "rejected", "reason": "regime_undecided",
                            "regime": regime}), 200
        print(f"[REGIME] OK {symbol} {interval} : {regime['regime']} {regime['metrics']}")
    except Exception as e:
        # Data indisponible ≠ marché fermé : on log et on laisse passer
        # (fail-open assumé — le filtre protège, il ne doit pas tuer le flux)
        print(f"[REGIME] indisponible ({e}) — signal traité sans filtre")
        payload["regime"] = "UNKNOWN"

    # ─── MACRO KILL SWITCH (FOMC/CPI/NFP dans la fenêtre = pas d'entrée) ───
    try:
        from core.macro_calendar import macro_block
        macro = macro_block()
        payload["macro_feed_ok"] = macro["feed_ok"]
        if macro["blocked"]:
            payload["macro_blocked"] = True
            log_signal(payload)
            print(f"[MACRO]  REJET : {macro['reason']} — {macro['events']}")
            return jsonify({"status": "rejected", "reason": "macro_event_window",
                            "macro": macro}), 200
    except Exception as e:
        print(f"[MACRO]  indisponible ({e}) — signal traité sans kill switch")

    # Log dans JSONL
    log_signal(payload)

    # ─── PAPER EXECUTOR : signal validé → position simulée (prix réels) ───
    # trades.csv est rempli à la CLÔTURE des positions par paper_executor.check
    # (cron 5 min), pas à l'entrée — le journal analyse des trades complets.
    try:
        from core.paper_executor import open_from_signal
        result = open_from_signal(payload)
        if not result["opened"]:
            print(f"[PAPER]  non ouvert : {result['reason']}")
    except Exception as e:
        print(f"[PAPER]  erreur executor ({e}) — signal loggé seulement, position non ouverte",
              file=sys.stderr)

    # Sync dashboard Vercel
    try:
        sync_script = Path(__file__).parent / "scripts" / "sync_dashboard.py"
        subprocess.Popen(["python3", str(sync_script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[SYNC]   Erreur sync dashboard : {e}")

    # Déclencher l'agent signal si A*
    if setup in ACTION_SETUPS:
        context = (
            f"Nouveau signal A* reçu :\n"
            f"  Ticker    : {payload.get('ticker')}\n"
            f"  Direction : {payload.get('dir')}\n"
            f"  Timeframe : {payload.get('tf')}\n"
            f"  Prix      : {payload.get('price')}\n"
            f"  Exchange  : {payload.get('exchange')}\n"
            f"Valide le signal selon le processus TraderMorin 5 étapes."
        )
        call_claude_agent("signal_agent", context)

    return jsonify({"status": "ok", "setup": setup, "action": "logged"}), 200


@app.route("/health", methods=["GET"])
def health():
    """Vérification que le serveur tourne."""
    signals_logged = 0
    if SIGNALS_LOG.exists():
        # Fichier fermé proprement via context manager (l'ancienne version
        # laissait le descripteur ouvert — fuite mineure sur serveur long-lived).
        with open(SIGNALS_LOG) as f:
            signals_logged = sum(1 for _ in f)
    return jsonify({
        "status": "running",
        "port": PORT,
        "signals_logged": signals_logged,
        "trades_csv": str(TRADES_CSV),
    }), 200


@app.route("/signals/<token>", methods=["GET"])
def signals(token):
    """Liste les 20 derniers signaux reçus.

    Protégé : le tunnel expose toutes les routes du port, et cet endpoint
    divulgue l'historique des signaux de trading.

    Robuste : une ligne JSONL corrompue (écriture concurrente interrompue,
    coupure disque, etc.) est ignorée plutôt que de faire planter tout
    l'endpoint — le comportement normal (20 derniers signaux, plus récent
    en premier) est inchangé pour toutes les lignes valides.
    """
    require_token(token)
    if not SIGNALS_LOG.exists():
        return jsonify([]), 200
    lines = SIGNALS_LOG.read_text().strip().split("\n")
    last20 = []
    for l in lines[-20:]:
        if not l:
            continue
        try:
            last20.append(json.loads(l))
        except json.JSONDecodeError as e:
            print(f"[SIGNALS] ligne JSONL corrompue ignorée ({e})")
    return jsonify(last20[::-1]), 200


@app.route("/push-pine/<token>", methods=["POST"])
def push_pine(token):
    """Copie HybridAI_TraderMorin.pine → scripts/current.pine et push via MCP.

    Protégé en priorité : cette route lance `node scripts/pine_push.js`. Sans
    jeton et derrière un tunnel public, elle offrait une exécution de code à
    distance à quiconque connaissait l'URL.
    """
    require_token(token)
    if not PINE_FILE.exists():
        return jsonify({"status": "error", "msg": "HybridAI_TraderMorin.pine introuvable"}), 404
    CURRENT_PINE.write_text(PINE_FILE.read_text())
    try:
        result = subprocess.run(
            ["node", "scripts/pine_push.js"],
            cwd=str(PINE_FILE.parent),
            capture_output=True, text=True, timeout=30
        )
        return jsonify({"status": "ok", "output": result.stdout, "errors": result.stderr}), 200
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Échec fermé : sans jeton, toutes les routes protégées seraient ouvertes.
    # Mieux vaut refuser de démarrer que servir un webhook sans authentification.
    if not WEBHOOK_TOKEN:
        raise SystemExit(
            "WEBHOOK_TOKEN absent de .env — démarrage refusé.\n"
            "  Générer : openssl rand -hex 24\n"
            "  Ajouter : WEBHOOK_TOKEN=<valeur> dans .env"
        )

    masked = f"{WEBHOOK_TOKEN[:4]}…{WEBHOOK_TOKEN[-4:]}"
    print(f"""
╔══════════════════════════════════════════════════════╗
║   WEBHOOK SERVER — Hybrid AI System (sans 3Commas)  ║
╠══════════════════════════════════════════════════════╣
║  POST  /webhook/<token>     ← alerte TradingView     ║
║  GET   /signals/<token>                              ║
║  POST  /push-pine/<token>                            ║
║  GET   /health              ← libre (monitoring)     ║
╠══════════════════════════════════════════════════════╣
║  Jeton   : {masked:<41}║
║  Écoute  : 127.0.0.1:{PORT} (pas d'exposition LAN)     ║
║  Tunnel  : ngrok/cloudflared se connecte en local    ║
╚══════════════════════════════════════════════════════╝
""")
    # 127.0.0.1 et non 0.0.0.0 : le tunnel tourne sur cette machine et se
    # connecte à localhost. Écouter sur toutes les interfaces exposait le
    # serveur à l'ensemble du réseau local sans aucune raison fonctionnelle.
    app.run(host="127.0.0.1", port=PORT, debug=False)
