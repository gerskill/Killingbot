"""
llm_generator.py — Génération créative de variantes de paramètres via Claude.

Remplace/complète les heuristiques if/else fixes de memory_agent.suggest_next()
(qui ne savent que +0.5 RR, assouplir/serrer filtres, toggle RSI) par une vraie
recherche générative bornée au schéma de params connu de strategy_explorer.py.
"""
import json
import os
import re
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

MODEL = "claude-sonnet-5"

PARAM_SCHEMA = """
ema_fast: int (3-20)
ema_slow: int (15-60, doit être > ema_fast)
kijun_len: int (20-60)
atr_len: int (10-20)
atr_mult: float (0.8-3.0) — multiplicateur ATR pour le stop loss
rr: float (1.5-6.0) — ratio risk/reward (TP = SL * rr)
ema_sep_pct: float (0.1-1.0) — séparation min EMA fast/slow pour valider signal
cooldown_bars: int (2-10) — barres d'attente après un trade
atr_min_pct: float (0.2-1.0) — volatilité min requise pour trader
use_rsi / use_adx / use_macd / use_volume / use_supertrend / use_stoch /
use_bb_squeeze / use_vwap / use_session / use_mtf_filter: bool — filtres additionnels
tf_resample: str optionnel ("15min", "1h", "4h") — timeframe de resampling
"""


def _client():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    return Anthropic(api_key=key)


def generate_variations(top_results: list, explored_names: list, n: int = 3) -> list:
    """
    Demande à Claude n nouvelles combinaisons de params, différentes des
    variations déjà testées et des patterns heuristiques déjà couverts.
    Retourne une liste de dicts params + "_name_hint" + "_reason".
    Retourne [] si pas de clé API ou erreur — jamais d'exception qui casse la boucle.
    """
    client = _client()
    if client is None:
        return []

    top_summary = "\n".join(
        f"- {r['name']}: {json.dumps({k: v for k, v in r['params'].items() if not k.startswith('_')})} "
        f"-> {r['metrics'].get('monthly_return_pct', 0):.1f}%/mois IS, "
        f"dégradation OOS {r['metrics'].get('oos_degradation_pct', 'N/A')}%, "
        f"Sharpe {r['metrics'].get('sharpe_ratio', 0):.2f}, "
        f"deflated_sharpe {r['metrics'].get('deflated_sharpe', 'N/A')}, "
        f"{r['metrics'].get('total_trades', 0)} trades"
        for r in top_results
    )

    prompt = f"""Tu es un quant qui explore un espace de paramètres pour une stratégie
de trend-following crypto (EMA cross + Kijun + ATR stop), backtestée sur 6 paires (4H).

Schéma des paramètres disponibles:
{PARAM_SCHEMA}

Top résultats actuels (perf in-sample, dégradation out-of-sample, Sharpe déflaté
pour biais de sélection sur les essais déjà faits):
{top_summary}

Déjà testé (ne pas reproposer à l'identique): {', '.join(explored_names[-40:])}

Propose {n} NOUVELLES combinaisons de paramètres, réellement différentes (pas
juste +0.5 sur un seul param comme le ferait une règle fixe). Cherche des
hypothèses non testées : interactions entre filtres, plages de params
inexplorées, structures différentes. Priorise les combinaisons qui pourraient
réduire la dégradation OOS — un %/mois qui s'effondre hors échantillon ne
compte pas, même s'il est élevé en in-sample.

Réponds UNIQUEMENT en JSON, liste de {n} objets, rien d'autre:
[{{"_name_hint": "...", "_reason": "1 phrase", "params": {{...tous les params numériques + booléens...}}}}]
"""

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        raw = json.loads(match.group(0))
    except Exception as e:
        print(f"[llm_generator] erreur génération: {e}")
        return []

    variations = []
    for item in raw:
        params = dict(item.get("params", {}))
        params["_name_hint"] = item.get("_name_hint", "KB_LLM_UNKNOWN")
        params["_reason"] = item.get("_reason", "")
        variations.append(params)
    return variations
