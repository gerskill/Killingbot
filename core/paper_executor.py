"""
Paper Executor — exécution simulée des signaux validés, prix réels Binance.

Rôle : dernière brique de la boucle. Les signaux qui passent les 2 filtres
(regime + macro) deviennent des positions papier avec SL/TP calculés comme
en réel (ATR × mult, RR de la config). Un check périodique (cron 5 min)
mark-to-market les positions ouvertes et écrit les trades clôturés dans
trades.csv — la matière que journal_agent analyse chaque dimanche.

Argent réel : JAMAIS ici. deploy_state "paper" → simulation. Le passage à
"live" est une décision humaine, hors de portée de tout agent.

Réalisme :
    - slippage adverse 5 bps à l'entrée ET à la sortie
    - commission 10 bps par côté (config Binance spot standard)
    - sizing : risque 1% du capital sur la distance entrée→SL
    - une seule position par symbole à la fois

Usage :
    python3 core/paper_executor.py check    # mark-to-market (cron 5 min)
    python3 core/paper_executor.py status   # positions ouvertes
"""
from __future__ import annotations

import csv
import fcntl
import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
CONFIG_FILE = ROOT / "killingbot_config.json"
POSITIONS_FILE = ROOT / "vault" / "paper_positions.json"
TRADES_CSV = ROOT / "trades.csv"

SLIPPAGE_BPS = 5      # adverse, par côté
COMMISSION_BPS = 10   # par côté
ACCOUNT_SIZE = 25000.0

# Plafond global : risque de portefeuille, toutes stratégies confondues.
MAX_OPEN_POSITIONS = 3
# Plafond par stratégie : une stratégie ne peut pas monopoliser le portefeuille
# ni empiler plusieurs positions sur le même symbole.
MAX_POSITIONS_PER_STRATEGY = 1

# Identité des signaux non routés (alerte historique setup A*/B, collecte OOS
# en cours). Les positions legacy sont isolées comme celles d'une stratégie
# nommée : un signal legacy ne peut toucher qu'une position legacy.
LEGACY_STRATEGY_ID = "legacy"


def _strategy_of(obj: dict) -> str:
    """Identité de stratégie d'une position ou d'un payload.

    Le webhook renseigne strategy_id quand le registre a routé le signal. Son
    absence signifie pipeline historique, pas « n'importe quelle stratégie » :
    c'est cette distinction qui empêche un signal d'en toucher un autre.
    """
    return str(obj.get("strategy_id") or LEGACY_STRATEGY_ID)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return json.load(f)


@contextmanager
def positions_lock():
    """Sérialise le cycle lecture-modification-écriture des positions.

    Deux écrivains coexistent : le serveur Flask (threaded=True par défaut, donc
    plusieurs requêtes en parallèle) et le cron `check` toutes les 5 minutes,
    qui est un processus distinct. Sans verrou, les deux lisent le même état,
    modifient chacun leur copie, et le dernier à écrire écrase l'autre — une
    position ouverte peut disparaître sans qu'aucun trade ne soit journalisé.

    flock() couvre les deux cas (threads et processus) puisque le verrou porte
    sur le descripteur de fichier au niveau noyau. POSIX uniquement : sous
    Windows il faudrait msvcrt.locking ou portalocker.
    """
    lock_path = POSITIONS_FILE.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _load_positions() -> list[dict]:
    if POSITIONS_FILE.exists():
        return json.loads(POSITIONS_FILE.read_text())
    return []


def _save_positions(positions: list[dict]):
    POSITIONS_FILE.parent.mkdir(exist_ok=True)
    POSITIONS_FILE.write_text(json.dumps(positions, indent=2, ensure_ascii=False))


def _last_price_and_atr(symbol: str, interval: str = "15m") -> tuple[float, float]:
    from core.market_regime import fetch_binance_klines
    df = fetch_binance_klines(symbol, interval, limit=50)
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift()
    tr = (high - low).combine((high - prev_close).abs(), max).combine(
        (low - prev_close).abs(), max)
    atr = float(tr.rolling(14).mean().iloc[-1])
    return float(close.iloc[-1]), atr


def _slip(price: float, side: str, entering: bool) -> float:
    """Slippage toujours défavorable : long paie plus cher, vend moins cher."""
    adverse_up = (side == "long") == entering
    factor = 1 + SLIPPAGE_BPS / 10_000 * (1 if adverse_up else -1)
    return price * factor


# ── Ouverture (appelé par webhook_server après les 2 filtres) ────────────────

def open_from_signal(payload: dict) -> dict:
    """Ouvre une position papier depuis un signal validé.

    Idempotent par (symbole, stratégie) et non par symbole seul : deux
    stratégies visant le même actif sont des positions distinctes, pas un
    doublon. Dédupliquer sur le seul symbole ferait rejeter silencieusement
    la seconde stratégie.
    """
    config = _load_config()
    if config.get("deploy_state") != "paper":
        return {"opened": False, "reason": f"deploy_state={config.get('deploy_state')} (pas 'paper')"}

    symbol = str(payload.get("ticker", "")).replace("/", "").replace("PERP", "")
    side = str(payload.get("dir", "")).lower()
    # TradingView envoie "buy" ({{strategy.order.action}}) ou "long"
    # ({{strategy.market_position}}) selon le placeholder utilisé dans l'alerte.
    side = {"buy": "long"}.get(side, side)
    if side not in ("long", "short"):
        return {"opened": False, "reason": f"direction inconnue: {side!r}"}

    strategy_id = _strategy_of(payload)
    with positions_lock():
        return _open_locked(payload, symbol, side, strategy_id, config)


def _open_locked(payload: dict, symbol: str, side: str, strategy_id: str, config: dict) -> dict:
    """Corps de l'ouverture, exécuté sous verrou."""
    positions = _load_positions()

    same_pair = [p for p in positions
                 if p["symbol"] == symbol and _strategy_of(p) == strategy_id]
    if same_pair:
        return {"opened": False,
                "reason": f"position déjà ouverte sur {symbol} pour {strategy_id}"}

    mine = [p for p in positions if _strategy_of(p) == strategy_id]
    if len(mine) >= MAX_POSITIONS_PER_STRATEGY:
        return {"opened": False,
                "reason": f"{strategy_id} a atteint son plafond "
                          f"({MAX_POSITIONS_PER_STRATEGY} position)"}

    if len(positions) >= MAX_OPEN_POSITIONS:
        return {"opened": False,
                "reason": f"plafond portefeuille atteint ({MAX_OPEN_POSITIONS} positions)"}

    price, atr = _last_price_and_atr(symbol)
    risk = config["strategy"]["risk_params"]
    sl_dist = atr * float(risk.get("sl_atr_mult", 1.5))
    entry = _slip(price, side, entering=True)

    if side == "long":
        sl = entry - sl_dist
        tp1 = entry + sl_dist * float(risk.get("tp1_rr", 1.5))
        tp2 = entry + sl_dist * float(risk.get("tp2_rr", 3.0))
    else:
        sl = entry + sl_dist
        tp1 = entry - sl_dist * float(risk.get("tp1_rr", 1.5))
        tp2 = entry - sl_dist * float(risk.get("tp2_rr", 3.0))

    risk_usd = ACCOUNT_SIZE * float(risk.get("risk_per_trade_pct", 1.0)) / 100
    qty = round(risk_usd / sl_dist, 6)

    pos = {
        "symbol": symbol, "strategy_id": strategy_id, "side": side, "qty": qty,
        "entry_price": round(entry, 2), "sl": round(sl, 2),
        "tp1": round(tp1, 2), "tp2": round(tp2, 2),
        "tp1_done": False,
        "setup": payload.get("setup", "?"), "tf": payload.get("tf", "?"),
        "opened_at": _now().isoformat(),
        "regime_at_entry": payload.get("regime", "UNKNOWN"),
    }
    positions.append(pos)
    _save_positions(positions)
    print(f"[PAPER]  OUVERT [{strategy_id}] {side.upper()} {symbol} qty={qty} @ {entry:.2f} "
          f"SL={sl:.2f} TP1={tp1:.2f} TP2={tp2:.2f}")
    return {"opened": True, "position": pos}


# ── Clôture ──────────────────────────────────────────────────────────────────

def close_from_signal(payload: dict) -> dict:
    """Clôture la position d'UNE stratégie — exit reçu via webhook.

    Un exit ne ferme que la position de la stratégie qui l'a émis. La version
    précédente filtrait sur le seul symbole et retirait donc toutes les
    positions de cet actif tout en n'écrivant qu'un seul trade : avec deux
    stratégies sur le même symbole, la seconde disparaissait sans que son PnL
    soit jamais enregistré.

    Les stratégies actives sont long-only : un fill "sell" ou un
    market_position "flat" signifie sortie, jamais entrée short.
    """
    symbol = str(payload.get("ticker", "")).replace("/", "").replace("PERP", "")
    strategy_id = _strategy_of(payload)
    with positions_lock():
        return _close_locked(payload, symbol, strategy_id)


def _close_locked(payload: dict, symbol: str, strategy_id: str) -> dict:
    """Corps de la clôture, exécuté sous verrou."""
    positions = _load_positions()

    pos = next((p for p in positions
                if p["symbol"] == symbol and _strategy_of(p) == strategy_id), None)
    if pos is None:
        others = [_strategy_of(p) for p in positions if p["symbol"] == symbol]
        detail = f" (ouvertes sur {symbol} : {', '.join(others)})" if others else ""
        return {"closed": False,
                "reason": f"aucune position {strategy_id} sur {symbol}{detail}"}

    try:
        price, _ = _last_price_and_atr(symbol)
    except Exception:
        # Binance KO : prix de l'alerte, sinon entrée (PnL 0 plutôt que blocage)
        try:
            price = float(payload.get("price") or pos["entry_price"])
        except (TypeError, ValueError):
            price = pos["entry_price"]

    qty = pos["qty"] / 2 if pos["tp1_done"] else pos["qty"]
    _write_trade(pos, price, qty, "strategy_exit")

    # Retrait par identité de l'objet : une position au même symbole et à la
    # même stratégie ne peut pas exister en double (garanti à l'ouverture),
    # mais comparer l'objet évite toute ambiguïté résiduelle.
    _save_positions([p for p in positions if p is not pos])
    return {"closed": True,
            "reason": f"{symbol} [{strategy_id}] clôturé @ {price:.2f} (strategy_exit)"}

def _write_trade(pos: dict, exit_price: float, exited_qty: float, label: str):
    """Ligne trades.csv au format que journal_agent lit."""
    exit_px = _slip(exit_price, pos["side"], entering=False)
    direction = 1 if pos["side"] == "long" else -1
    gross = (exit_px - pos["entry_price"]) * direction * exited_qty
    fees = (pos["entry_price"] + exit_px) * exited_qty * COMMISSION_BPS / 10_000
    pnl = round(gross - fees, 2)
    pnl_pct = round(pnl / ACCOUNT_SIZE * 100, 3)

    # strategy_id en dernière colonne : journal_agent lit en DictReader, donc
    # l'ajout n'affecte pas les colonnes existantes. Sans elle, l'analyse
    # hebdomadaire mélangerait les trades de toutes les stratégies dans un seul
    # bloc — le défaut « config globale unique » relevé à l'audit du 2026-07-15.
    fieldnames = ["date", "time", "symbol", "side", "entry_price", "exit_price",
                  "shares", "pnl_usd", "pnl_pct", "setup_type", "notes", "strategy_id"]
    now = _now()
    strategy_id = _strategy_of(pos)
    row = {
        "date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M"),
        "symbol": pos["symbol"], "side": pos["side"],
        "entry_price": pos["entry_price"], "exit_price": round(exit_px, 2),
        "shares": exited_qty, "pnl_usd": pnl, "pnl_pct": pnl_pct,
        "setup_type": pos["setup"],
        "notes": f"paper {label} tf:{pos['tf']} regime:{pos['regime_at_entry']} fees:{fees:.2f}",
        "strategy_id": strategy_id,
    }
    write_header = not TRADES_CSV.exists() or TRADES_CSV.stat().st_size == 0
    with open(TRADES_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    print(f"[PAPER]  CLÔTURE [{strategy_id}] {label} {pos['symbol']} "
          f"@ {exit_px:.2f} → PnL {pnl:+.2f}$")


def check_positions() -> dict:
    """Mark-to-market : TP1 → sortie 50% + SL au breakeven ; TP2/SL → sortie totale.

    Sous verrou : ce cycle lecture-modification-écriture tourne dans le cron
    (processus distinct), en parallèle des ouvertures et clôtures du webhook.
    """
    with positions_lock():
        return _check_locked()


def _check_locked() -> dict:
    positions = _load_positions()
    if not positions:
        return {"open": 0, "actions": []}

    still_open, actions = [], []
    for pos in positions:
        try:
            price, _ = _last_price_and_atr(pos["symbol"])
        except Exception as e:
            still_open.append(pos)  # data KO : on garde, prochain check
            actions.append(f"{pos['symbol']}: prix indisponible ({str(e)[:60]})")
            continue

        is_long = pos["side"] == "long"
        hit_sl = price <= pos["sl"] if is_long else price >= pos["sl"]
        hit_tp1 = (price >= pos["tp1"] if is_long else price <= pos["tp1"]) and not pos["tp1_done"]
        hit_tp2 = price >= pos["tp2"] if is_long else price <= pos["tp2"]

        if hit_sl:
            qty = pos["qty"] if not pos["tp1_done"] else pos["qty"] / 2
            label = "SL" if not pos["tp1_done"] else "BE-stop"
            _write_trade(pos, pos["sl"], qty, label)
            actions.append(f"{pos['symbol']}: {label} @ {pos['sl']}")
        elif hit_tp2:
            qty = pos["qty"] / 2 if pos["tp1_done"] else pos["qty"]
            _write_trade(pos, pos["tp2"], qty, "TP2")
            actions.append(f"{pos['symbol']}: TP2 @ {pos['tp2']}")
        elif hit_tp1:
            _write_trade(pos, pos["tp1"], pos["qty"] / 2, "TP1")
            pos["tp1_done"] = True
            pos["sl"] = pos["entry_price"]  # stop au breakeven
            still_open.append(pos)
            actions.append(f"{pos['symbol']}: TP1 @ {pos['tp1']}, SL→BE")
        else:
            still_open.append(pos)

    _save_positions(still_open)
    return {"open": len(still_open), "actions": actions}


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "check":
        print(json.dumps(check_positions(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(_load_positions(), indent=2, ensure_ascii=False))
