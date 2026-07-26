"""
sidecars/journal.py — Trade logging (CSV + JSONL)
Sidecar indépendant : extrait du webhook_server monolithique.
"""
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent.parent
TRADES_CSV  = BASE / "trades.csv"
SIGNALS_LOG = BASE / "signals_log.jsonl"

CSV_FIELDS = [
    "date", "time", "symbol", "side", "entry_price",
    "exit_price", "shares", "pnl_usd", "pnl_pct",
    "setup_type", "risk_usd", "position_size_usd", "notes",
]


def log_signal(payload: dict) -> dict:
    """Ajoute signal brut dans JSONL, retourne entry."""
    entry = {**payload, "received_at": datetime.utcnow().isoformat() + "Z"}
    with open(SIGNALS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def open_trade(payload: dict, risk_usd: float = 0.0, position_size_usd: float = 0.0) -> str:
    """
    Crée ligne dans trades.csv (entry uniquement, exit vide).
    Retourne trade_id pour mise à jour ultérieure.
    """
    now = datetime.utcnow()
    trade_id = f"{payload.get('ticker', 'UNK')}_{now.strftime('%Y%m%d%H%M%S')}"
    row = {
        "date":              now.strftime("%Y-%m-%d"),
        "time":              now.strftime("%H:%M"),
        "symbol":            payload.get("ticker", ""),
        "side":              payload.get("dir", "").lower(),
        "entry_price":       payload.get("price", ""),
        "exit_price":        "",
        "shares":            "",
        "pnl_usd":           "",
        "pnl_pct":           "",
        "setup_type":        payload.get("setup", ""),
        "risk_usd":          risk_usd,
        "position_size_usd": position_size_usd,
        "notes":             f"tf:{payload.get('tf','')} ex:{payload.get('exchange','')} id:{trade_id}",
    }
    _write_row(row)
    return trade_id


def close_trade(trade_id: str, exit_price: float, pnl_usd: float):
    """Met à jour exit_price et PnL pour trade_id dans trades.csv."""
    if not TRADES_CSV.exists():
        return
    rows = []
    with open(TRADES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if trade_id in row.get("notes", ""):
                entry = float(row.get("entry_price") or 0)
                row["exit_price"] = str(exit_price)
                row["pnl_usd"] = str(round(pnl_usd, 2))
                if entry > 0:
                    row["pnl_pct"] = str(round((exit_price - entry) / entry * 100, 3))
            rows.append(row)
    with open(TRADES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def recent_signals(n: int = 20) -> list[dict]:
    if not SIGNALS_LOG.exists():
        return []
    lines = SIGNALS_LOG.read_text().strip().split("\n")
    return [json.loads(l) for l in lines[-n:] if l][::-1]


def _write_row(row: dict):
    write_header = not TRADES_CSV.exists()
    with open(TRADES_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
