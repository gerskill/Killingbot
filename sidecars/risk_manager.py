"""
sidecars/risk_manager.py — Position sizing + drawdown guard
Sidecar indépendant : calcule size, vérifie limites de risque.
"""
from dataclasses import dataclass
from pathlib import Path
import json

ACCOUNT_SIZE_USD    = 25_000.0
RISK_PER_TRADE_PCT  = 1.0          # 1% par trade
MAX_DAILY_LOSS_PCT  = 3.0          # circuit breaker journalier
MAX_OPEN_POSITIONS  = 3
ATR_MULTIPLIER_SL   = 1.5          # SL = 1.5 × ATR

TRADES_CSV  = Path(__file__).parent.parent / "trades.csv"
SIGNALS_LOG = Path(__file__).parent.parent / "signals_log.jsonl"


@dataclass
class RiskResult:
    approved: bool
    position_size_usd: float = 0.0
    risk_usd: float = 0.0
    stop_loss_pct: float = 0.0
    rejection_reason: str = ""


def _daily_pnl_usd() -> float:
    """Somme PnL du jour depuis signals_log (positions fermées seulement)."""
    from datetime import date
    today = date.today().isoformat()
    pnl = 0.0
    if not TRADES_CSV.exists():
        return 0.0
    import csv
    with open(TRADES_CSV) as f:
        for row in csv.DictReader(f):
            if row.get("date") == today and row.get("pnl_usd"):
                try:
                    pnl += float(row["pnl_usd"])
                except ValueError:
                    pass
    return pnl


def _open_positions() -> int:
    """Compte trades sans exit_price = positions ouvertes."""
    if not TRADES_CSV.exists():
        return 0
    import csv
    count = 0
    with open(TRADES_CSV) as f:
        for row in csv.DictReader(f):
            if not row.get("exit_price"):
                count += 1
    return count


def evaluate(payload: dict, atr_pct: float | None = None) -> RiskResult:
    """
    Calcule position size, vérifie circuit breakers.
    atr_pct : ATR en % du prix courant (optionnel, estimé sinon).
    """
    # Circuit breaker — perte journalière
    daily_pnl = _daily_pnl_usd()
    max_daily_loss = -(ACCOUNT_SIZE_USD * MAX_DAILY_LOSS_PCT / 100)
    if daily_pnl <= max_daily_loss:
        return RiskResult(False, rejection_reason=f"Circuit breaker: PnL jour {daily_pnl:.0f}$ ≤ {max_daily_loss:.0f}$")

    # Limite positions ouvertes
    open_pos = _open_positions()
    if open_pos >= MAX_OPEN_POSITIONS:
        return RiskResult(False, rejection_reason=f"Max positions ouvertes atteint ({open_pos}/{MAX_OPEN_POSITIONS})")

    # Sizing basé sur ATR
    price = float(payload.get("price", 0) or 0)
    if price <= 0:
        return RiskResult(False, rejection_reason="Prix invalide pour sizing")

    sl_pct = (atr_pct or 0.5) * ATR_MULTIPLIER_SL  # défaut 0.5% ATR
    risk_usd = ACCOUNT_SIZE_USD * RISK_PER_TRADE_PCT / 100
    position_size_usd = risk_usd / (sl_pct / 100) if sl_pct > 0 else 0

    # Cap position à 20% du compte
    position_size_usd = min(position_size_usd, ACCOUNT_SIZE_USD * 0.20)

    return RiskResult(
        approved=True,
        position_size_usd=round(position_size_usd, 2),
        risk_usd=round(risk_usd, 2),
        stop_loss_pct=round(sl_pct, 3),
    )
