#!/usr/bin/env python3
"""
garch_position_sizer.py — Position sizing dynamique basé sur la volatilité prévue (GARCH)
============================================================================================
Couche 6 (Risk Management) de l'architecture Killingbot.

Idée (cf. vidéo "GARCH / Nobel Prize Method") : ne PAS prédire la direction, mais prévoir
le clustering de volatilité pour dimensionner chaque position — plus la vol prévue est
élevée, plus la taille est réduite, et inversement. Objectif : risque en $ constant par
trade, indépendamment de l'actif ou du régime de volatilité courant.

Fonctionnement :
    1. Charge un CSV OHLCV (timestamp, open, high, low, close, volume)
    2. Calcule les rendements log
    3. Ajuste un GARCH(1,1) (librairie `arch`) — fallback EWMA RiskMetrics si `arch`
       n'est pas installée (approximation, pas un vrai GARCH)
    4. Prévoit la volatilité du prochain bar
    5. Calcule un multiplicateur de taille de position (borné) et une taille finale
       en unités de l'actif, à partir d'un risque % de l'équity et d'une distance de stop
    6. Écrit le résultat dans garch_output.json, consommable par webhook_server.py

Installation :
    pip install arch pandas numpy --break-system-packages

Usage CLI :
    python3 garch_position_sizer.py --csv data/BTCUSDT_4h.csv --equity 10000 \
        --risk-pct 1.0 --stop-atr-mult 1.5 --vol-target 0.02

Intégration webhook_server.py (cf. note en bas de fichier) :
    from agents.garch_position_sizer import get_current_multiplier
    multiplier = get_current_multiplier("garch_output.json")
    qty = base_qty * multiplier
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

OUTPUT_FILE = Path(__file__).parent.parent / "garch_output.json"

# ─────────────────────────────────────────────────────────────────────────────
# 1. DONNÉES
# ─────────────────────────────────────────────────────────────────────────────
def load_ohlcv(csv_path: str) -> pd.DataFrame:
    """Charge un CSV OHLCV. Colonnes attendues (insensible à la casse) :
    timestamp/date, open, high, low, close, volume."""
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "close" not in df.columns:
        raise ValueError("Le CSV doit contenir une colonne 'close'.")
    return df


def log_returns(df: pd.DataFrame) -> pd.Series:
    close = df["close"].astype(float)
    rets = np.log(close / close.shift(1)).dropna()
    return rets * 100.0  # en %, échelle attendue par `arch`


# ─────────────────────────────────────────────────────────────────────────────
# 2. MODÈLE DE VOLATILITÉ
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class VolForecast:
    method: str          # "garch" ou "ewma_fallback"
    sigma_forecast_pct: float   # écart-type prévu du prochain bar, en %
    sigma_hist_median_pct: float  # médiane historique (référence de régime "normal")
    vol_regime: str       # "low" | "normal" | "high" | "extreme"


def fit_garch_forecast(rets: pd.Series) -> VolForecast:
    """Ajuste un GARCH(1,1) si `arch` est disponible, sinon fallback EWMA (RiskMetrics,
    lambda=0.94) — approximation raisonnable mais PAS un vrai GARCH (pas de mean-reversion
    de la variance ni de MLE)."""
    try:
        from arch import arch_model  # type: ignore

        am = arch_model(rets, vol="GARCH", p=1, q=1, dist="normal", mean="constant")
        res = am.fit(disp="off")
        fc = res.forecast(horizon=1, reindex=False)
        sigma_next = math.sqrt(float(fc.variance.values[-1, 0]))
        method = "garch"
    except ImportError:
        lam = 0.94
        var = rets.var()
        for r in rets:
            var = lam * var + (1 - lam) * (r ** 2)
        sigma_next = math.sqrt(var)
        method = "ewma_fallback"

    hist_sigma = rets.rolling(30).std().dropna()
    sigma_hist_median = float(hist_sigma.median()) if len(hist_sigma) else sigma_next

    ratio = sigma_next / sigma_hist_median if sigma_hist_median > 0 else 1.0
    if ratio < 0.7:
        regime = "low"
    elif ratio < 1.3:
        regime = "normal"
    elif ratio < 2.0:
        regime = "high"
    else:
        regime = "extreme"

    return VolForecast(
        method=method,
        sigma_forecast_pct=round(sigma_next, 4),
        sigma_hist_median_pct=round(sigma_hist_median, 4),
        vol_regime=regime,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. POSITION SIZING
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class SizingResult:
    vol_forecast: VolForecast
    vol_target_pct: float
    size_multiplier: float     # à multiplier par la taille de base (ex: %equity KB_15m)
    risk_amount: float         # $ risqués sur ce trade (equity * risk_pct)
    position_qty: float | None # en unités de l'actif si stop_distance fourni
    computed_at: str


def position_size_multiplier(
    vol_forecast: VolForecast,
    vol_target_pct: float,
    mult_floor: float = 0.25,
    mult_cap: float = 2.0,
) -> float:
    """multiplier = vol_target / vol_prévue, borné pour éviter les sizes extrêmes.
    Vol prévue haute -> multiplier < 1 (on réduit) ; vol prévue basse -> multiplier > 1
    (on augmente, dans la limite du cap)."""
    if vol_forecast.sigma_forecast_pct <= 0:
        return 1.0
    raw = vol_target_pct / vol_forecast.sigma_forecast_pct
    return float(max(mult_floor, min(mult_cap, raw)))


def compute_sizing(
    csv_path: str,
    equity: float,
    risk_pct: float,
    vol_target_pct: float,
    price: float | None = None,
    stop_distance: float | None = None,
) -> SizingResult:
    df = load_ohlcv(csv_path)
    rets = log_returns(df)
    vf = fit_garch_forecast(rets)
    mult = position_size_multiplier(vf, vol_target_pct)

    risk_amount = equity * (risk_pct / 100.0)
    qty = None
    if price and stop_distance and stop_distance > 0:
        base_qty = risk_amount / stop_distance
        qty = round(base_qty * mult, 6)

    return SizingResult(
        vol_forecast=vf,
        vol_target_pct=vol_target_pct,
        size_multiplier=round(mult, 4),
        risk_amount=round(risk_amount, 2),
        position_qty=qty,
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. SORTIE JSON (consommée par webhook_server.py)
# ─────────────────────────────────────────────────────────────────────────────
def write_output(result: SizingResult, path: Path = OUTPUT_FILE) -> None:
    payload = {
        "vol_forecast": asdict(result.vol_forecast),
        "vol_target_pct": result.vol_target_pct,
        "size_multiplier": result.size_multiplier,
        "risk_amount": result.risk_amount,
        "position_qty": result.position_qty,
        "computed_at": result.computed_at,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def get_current_multiplier(path: str | Path = OUTPUT_FILE, default: float = 1.0) -> float:
    """À importer dans webhook_server.py pour scaler la taille de position à la volée."""
    p = Path(path)
    if not p.exists():
        return default
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return float(data.get("size_multiplier", default))
    except (json.JSONDecodeError, ValueError):
        return default


# ─────────────────────────────────────────────────────────────────────────────
# 5. CLI
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="GARCH position sizing — Killingbot Layer 6")
    ap.add_argument("--csv", required=True, help="CSV OHLCV (timestamp,open,high,low,close,volume)")
    ap.add_argument("--equity", type=float, required=True)
    ap.add_argument("--risk-pct", type=float, default=1.0, help="Risque % de l'equity par trade")
    ap.add_argument("--vol-target", type=float, default=1.0, help="Cible de volatilité en %% (échelle rendements log x100)")
    ap.add_argument("--price", type=float, default=None)
    ap.add_argument("--stop-atr-mult", type=float, default=None, help="Distance de stop en unités de prix (déjà calculée, ex ATR*mult)")
    args = ap.parse_args()

    result = compute_sizing(
        csv_path=args.csv,
        equity=args.equity,
        risk_pct=args.risk_pct,
        vol_target_pct=args.vol_target,
        price=args.price,
        stop_distance=args.stop_atr_mult,
    )
    write_output(result)
    print(json.dumps(asdict(result), indent=2, default=str))
    print(f"\n[OK] Résultat écrit dans {OUTPUT_FILE}")


if __name__ == "__main__":
    main()


# ─────────────────────────────────────────────────────────────────────────────
# NOTE D'INTÉGRATION — webhook_server.py
# ─────────────────────────────────────────────────────────────────────────────
# Dans webhook_server.py, avant append_trade_csv() / log_signal() :
#
#   from agents.garch_position_sizer import get_current_multiplier
#
#   @app.route("/webhook", methods=["POST"])
#   def webhook():
#       payload = request.json
#       multiplier = get_current_multiplier()  # lit garch_output.json (cache dernier calcul)
#       payload["size_multiplier"] = multiplier
#       payload["qty_adjusted"] = float(payload.get("qty", 1)) * multiplier
#       log_signal(payload)
#       ...
#
# Recalculer garch_output.json périodiquement (cron / scheduled task) plutôt qu'à
# chaque alerte : le GARCH n'a pas besoin d'être recalculé plus souvent que le
# timeframe de la stratégie (ex: une fois par bar 4H).
