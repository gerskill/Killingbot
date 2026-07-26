"""
Stoic Lens Runner — Agent autonome d'analyse
Génère l'analyse Stoic Lens sans broker (mode analyse seule).

Usage:
    python agents/stoic_lens_runner.py              # analyse immédiate
    python agents/stoic_lens_runner.py --monitor    # boucle toutes les 15min
    python agents/stoic_lens_runner.py --weekly     # rapport complet du vendredi
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# ── Chargement config ───────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "agents"))

load_dotenv(ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-20s  %(levelname)-7s  %(message)s",
)
log = logging.getLogger("StoicRunner")

with open(ROOT / "agents" / "stoic_agent_config.json") as f:
    CONFIG = json.load(f)

WATCHLIST: list[str] = (
    CONFIG["watchlist"]["forex"]
    + CONFIG["watchlist"]["metals"]
    + CONFIG["watchlist"]["indices"]
)

PILLARS   = CONFIG["stoic_lens_pillars"]
SETUP_CFG = CONFIG["setup_quality"]
RISK_CFG  = CONFIG["risk_management"]


# ── Types ───────────────────────────────────────────────────────────────────

class Momentum(Enum):
    HCOM = "HCOM"
    LCOM = "LCOM"
    DOJI = "DOJI"


class Direction(Enum):
    LONG  = "LONG"
    SHORT = "SHORT"
    FLAT  = "FLAT"


@dataclass
class Bar:
    o: float
    h: float
    l: float
    c: float


@dataclass
class PairContext:
    symbol:    str
    pdh:       float
    pdl:       float
    pdc:       float
    pdo:       float
    sma20:     float
    sma200:    float
    atr14:     float
    momentum:  Momentum
    sma_bias:  str        # "BULL" | "BEAR"
    trend_100: float      # % change over 100 bars
    timestamp: str = ""


@dataclass
class Setup:
    symbol:    str
    direction: Direction
    score:     int
    label:     str
    entry:     float
    sl:        float
    tp1:       float
    tp2:       float
    rr:        float
    fib618:    float
    fib786:    float
    warnings:  list[str] = field(default_factory=list)
    ctx:       Optional[PairContext] = None


# ── TradingView MCP Client (via subprocess / HTTP) ──────────────────────────

class TVClient:
    """
    Wrapper autour du TradingView Desktop MCP.
    Utilise aiohttp pour appeler le serveur MCP local (port 3000).
    """

    BASE = CONFIG["tradingview_desktop_mcp"]["url"]

    def __init__(self):
        try:
            import aiohttp
            self._aiohttp = aiohttp
        except ImportError:
            log.error("aiohttp requis — pip install aiohttp")
            sys.exit(1)

    async def _call(self, tool: str, params: dict) -> dict:
        async with self._aiohttp.ClientSession() as session:
            payload = {"tool": tool, "params": params}
            try:
                async with session.post(
                    f"{self.BASE}/call",
                    json=payload,
                    timeout=self._aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        log.warning("TV MCP error %s: %s", resp.status, text[:200])
                        return {}
                    return await resp.json()
            except Exception as e:
                log.warning("TV MCP unreachable: %s", e)
                return {}

    async def health_check(self) -> bool:
        result = await self._call("tv_health_check", {})
        return bool(result.get("ok") or result.get("status") == "ok")

    async def get_ohlcv(self, symbol: str, tf: str = "D", bars: int = 3) -> list[Bar]:
        result = await self._call("data_get_ohlcv", {
            "symbol": symbol,
            "timeframe": tf,
            "bars": bars,
            "summary": False,
        })
        raw = result.get("bars") or result.get("data") or []
        out = []
        for b in raw:
            out.append(Bar(
                o=float(b.get("open",  b.get("o", 0))),
                h=float(b.get("high",  b.get("h", 0))),
                l=float(b.get("low",   b.get("l", 0))),
                c=float(b.get("close", b.get("c", 0))),
            ))
        return out

    async def get_study(self, symbol: str, name: str, length: int) -> float:
        result = await self._call("data_get_study_values", {
            "symbol": symbol,
            "study_name": name,
            "length": length,
        })
        vals = result.get("values") or result.get("data") or []
        return float(vals[-1]) if vals else 0.0

    async def set_symbol(self, symbol: str, tf: str = "D"):
        await self._call("chart_set_symbol", {"symbol": symbol})
        await self._call("chart_set_timeframe", {"timeframe": tf})


# ── Market Analyst ──────────────────────────────────────────────────────────

class MarketAnalyst:
    def __init__(self, tv: TVClient):
        self.tv = tv

    async def analyze(self, symbol: str) -> Optional[PairContext]:
        await self.tv.set_symbol(symbol, "D")

        # PDH/PDL/PDC/PDO — bars[-1] = previous completed daily
        bars = await self.tv.get_ohlcv(symbol, "D", 3)
        if len(bars) < 2:
            log.warning("%s: not enough bars", symbol)
            return None
        prev = bars[-2]  # yesterday (index -2 because index -1 = today forming)

        # SMAs
        sma20  = await self.tv.get_study(symbol, "Moving Average", 20)
        sma200 = await self.tv.get_study(symbol, "Moving Average", 200)
        atr14  = await self.tv.get_study(symbol, "Average True Range", 14)

        # Momentum
        if prev.c > prev.o:
            mom = Momentum.HCOM
        elif prev.c < prev.o:
            mom = Momentum.LCOM
        else:
            mom = Momentum.DOJI

        # SMA bias
        sma_bias = "BULL" if sma20 > sma200 else "BEAR"

        # 100-bar trend (simplified: check last 2 available bars)
        bars100 = await self.tv.get_ohlcv(symbol, "D", 101)
        trend_100 = 0.0
        if len(bars100) >= 2:
            oldest = bars100[0].c
            newest = bars100[-1].c
            trend_100 = ((newest - oldest) / oldest * 100) if oldest else 0.0

        return PairContext(
            symbol    = symbol,
            pdh       = prev.h,
            pdl       = prev.l,
            pdc       = prev.c,
            pdo       = prev.o,
            sma20     = sma20,
            sma200    = sma200,
            atr14     = atr14,
            momentum  = mom,
            sma_bias  = sma_bias,
            trend_100 = round(trend_100, 2),
            timestamp = datetime.now(timezone.utc).isoformat(),
        )


# ── Setup Validator ─────────────────────────────────────────────────────────

class SetupValidator:

    @staticmethod
    def validate(ctx: PairContext) -> Optional[Setup]:
        if ctx.momentum == Momentum.DOJI:
            return None

        direction = Direction.LONG if ctx.momentum == Momentum.HCOM else Direction.SHORT
        score     = 0
        warnings  = []

        # Pilier 1 — HCOM/LCOM (always 1 since we filtered DOJI)
        score += 1

        # Pilier 2 — SMA bias
        aligned = (direction == Direction.LONG and ctx.sma_bias == "BULL") or \
                  (direction == Direction.SHORT and ctx.sma_bias == "BEAR")
        if aligned:
            score += 1
        else:
            warnings.append(f"Counter-trend: momentum={ctx.momentum.value} but SMA_BIAS={ctx.sma_bias}")

        # Pilier 3 — Near key level
        rng = ctx.pdh - ctx.pdl
        tol = ctx.atr14 * PILLARS["pillar_3_key_levels"]["tolerance_atr_mult"]
        near_pdl = abs(ctx.pdc - ctx.pdl) <= tol
        near_pdh = abs(ctx.pdc - ctx.pdh) <= tol
        near_pdc = abs(ctx.pdc - ctx.pdc) <= tol  # always true, kept for clarity
        if (direction == Direction.LONG and near_pdl) or \
           (direction == Direction.SHORT and near_pdh):
            score += 1

        # Pilier 4 — Fib zone
        fib_tol = ctx.atr14 * PILLARS["pillar_4_pattern"]["fib_tolerance_atr_mult"]
        if direction == Direction.LONG:
            fib618 = ctx.pdh - rng * 0.618
            fib786 = ctx.pdh - rng * 0.786
            in_fib = (fib786 - fib_tol) <= ctx.pdc <= (fib618 + fib_tol)
        else:
            fib618 = ctx.pdl + rng * 0.618
            fib786 = ctx.pdl + rng * 0.786
            in_fib = (fib618 - fib_tol) <= ctx.pdc <= (fib786 + fib_tol)

        if in_fib:
            score += 1

        if score < SETUP_CFG["min_score"]:
            return None

        # Entry / SL / TP
        buf = ctx.atr14 * 0.1
        if direction == Direction.LONG:
            entry = fib618
            sl    = ctx.pdl - buf
            tp1   = ctx.pdh
            tp2   = ctx.pdh + rng * 0.5
        else:
            entry = fib618
            sl    = ctx.pdh + buf
            tp1   = ctx.pdl
            tp2   = ctx.pdl - rng * 0.5

        risk = abs(entry - sl)
        rr   = abs(tp1 - entry) / risk if risk > 0 else 0.0

        if rr < RISK_CFG["min_rr_tp1"]:
            warnings.append(f"Low RR: {rr:.2f} < {RISK_CFG['min_rr_tp1']}")

        label = SETUP_CFG["score_labels"].get(str(score), "Unknown")

        return Setup(
            symbol    = ctx.symbol,
            direction = direction,
            score     = score,
            label     = label,
            entry     = round(entry, 5),
            sl        = round(sl, 5),
            tp1       = round(tp1, 5),
            tp2       = round(tp2, 5),
            rr        = round(rr, 2),
            fib618    = round(fib618, 5),
            fib786    = round(fib786, 5),
            warnings  = warnings,
            ctx       = ctx,
        )


# ── Report Generator ────────────────────────────────────────────────────────

def generate_report(setups: list[Setup], all_ctx: dict[str, PairContext]) -> str:
    now = datetime.now()
    weekday_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    day_name   = weekday_fr[now.weekday()]
    date_str   = now.strftime("%d %B %Y")

    lines = [
        f"# 🏛️ STOIC LENS — {day_name.upper()} {date_str}",
        "### Forex Majors + NQ + XAUUSD | Analyse pré-session",
        "*Généré automatiquement — Stoic Lens Multi-Agent System*",
        "",
        "---",
        "",
        "## 📖 LES 4 PILIERS",
        "",
        "| # | Pilier | Long | Short |",
        "|---|--------|------|-------|",
        "| 1 | **HCOM/LCOM** | HCOM | LCOM |",
        "| 2 | **SMA20/200** | SMA20 > SMA200 | SMA20 < SMA200 |",
        "| 3 | **Key Level** | Near PDL | Near PDH |",
        "| 4 | **Fib 61.8–78.6%** | Long zone | Short zone |",
        "",
        "---",
        "",
    ]

    # Macro bias
    hcom_count = sum(1 for s in setups if s.direction == Direction.LONG)
    lcom_count = sum(1 for s in setups if s.direction == Direction.SHORT)
    macro = "USD STRENGTH / RISK-OFF" if lcom_count > hcom_count else "RISK-ON / GROWTH"
    lines += [
        "## 🌍 BIAIS MACRO",
        "",
        f"**Signal dominant :** {macro}  ",
        f"HCOM count: {hcom_count} | LCOM count: {lcom_count}",
        "",
        "---",
        "",
        "## 📊 ANALYSE PAR PAIRE",
        "",
    ]

    # Per-pair
    sorted_setups = sorted(setups, key=lambda s: s.score, reverse=True)
    no_edge_pairs = [sym for sym, ctx in all_ctx.items()
                     if sym not in {s.symbol for s in setups}]

    rank_emoji = {4: "⭐⭐⭐", 3: "⭐⭐", 2: "⭐", 1: ""}

    for s in sorted_setups:
        ctx  = s.ctx
        rng  = ctx.pdh - ctx.pdl
        emoji = rank_emoji.get(s.score, "")
        dir_emoji = "🟢" if s.direction == Direction.LONG else "🔴"

        lines += [
            f"### {dir_emoji} {s.symbol} — {s.direction.value} BIAS | **{s.label}** {emoji}",
            "```",
            f"PDH : {ctx.pdh}",
            f"PDC : {ctx.pdc}",
            f"PDL : {ctx.pdl}",
            "```",
            "",
            "**Piliers :**",
            f"- {'✅' if ctx.momentum == Momentum.HCOM else '✅'} **{ctx.momentum.value}** : O:{ctx.pdo} → C:{ctx.pdc}",
            f"- {'✅' if (s.direction==Direction.LONG and ctx.sma_bias=='BULL') or (s.direction==Direction.SHORT and ctx.sma_bias=='BEAR') else '⚠️'} **SMA Trend** : SMA20={ctx.sma20:.5f} | SMA200={ctx.sma200:.5f} ({ctx.sma_bias}) | 100d change: {ctx.trend_100:+.2f}%",
            f"- **Score** : {s.score}/4",
            "",
            "**Plan :**",
            f"- Entry zone Fib : **{s.fib786} – {s.fib618}**",
            f"- SL : {s.sl}",
            f"- TP1 : {s.tp1} | TP2 : {s.tp2}",
            f"- RR : {s.rr}:1",
            "",
        ]

        if s.warnings:
            for w in s.warnings:
                lines.append(f"> ⚠️ {w}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # NO EDGE pairs
    if no_edge_pairs:
        lines += [
            "### ❌ NO EDGE — Pairs exclues",
            "",
        ]
        for sym in no_edge_pairs:
            ctx = all_ctx.get(sym)
            reason = "DOJI" if ctx and ctx.momentum == Momentum.DOJI else "Score insuffisant"
            lines.append(f"- **{sym}** : {reason}")
        lines += ["", "---", ""]

    # Summary table
    lines += [
        "## 🎯 TABLEAU RÉCAPITULATIF",
        "",
        "| Rang | Paire | Biais | Qualité | Entry Zone |",
        "|------|-------|-------|---------|------------|",
    ]
    for s in sorted_setups:
        emoji = rank_emoji.get(s.score, "")
        dir_sym = "🟢 LONG" if s.direction == Direction.LONG else "🔴 SHORT"
        lines.append(
            f"| {emoji} | **{s.symbol}** | {dir_sym} | **{s.label}** | {s.fib786}–{s.fib618} |"
        )

    # Checklist
    lines += [
        "",
        "---",
        "",
        "## ✅ STOIC PROCESS CHECKLIST",
        "",
        "```",
        "[ ] 1. HCOM ou LCOM confirmé sur Daily ?",
        "[ ] 2. Prix approche PDH, PDL ou PDC ?",
        "[ ] 3. SMA20 + SMA200 alignés avec le biais ?",
        "[ ] 4. Pattern B&R ou SFP visible sur H1/H4 ?",
        "[ ] 5. Entrée dans la zone Fib 0.618–0.786 ?",
        "[ ] 6. Golden SBS = 4+ cases cochées ?",
        "[ ] 7. RR ≥ 2:1 calculé avant d'entrer ?",
        "[ ] 8. Pas de news HIGH impact dans ±30min ?",
        "```",
        "",
        "> *\"The market tests more than your strategy\"* — @StoicTA",
        "> *Process > impulse. Toujours.*",
        "",
        f"*Généré le {now.strftime('%Y-%m-%d %H:%M UTC')} — Stoic Lens Runner v1.0*",
    ]

    return "\n".join(lines)


# ── Main Loop ────────────────────────────────────────────────────────────────

async def run_analysis(tv: TVClient) -> tuple[list[Setup], dict[str, PairContext]]:
    analyst   = MarketAnalyst(tv)
    validator = SetupValidator()

    setups   = []
    all_ctx  = {}

    for symbol in WATCHLIST:
        log.info("Analysing %s ...", symbol)
        ctx = await analyst.analyze(symbol)
        if not ctx:
            continue
        all_ctx[symbol] = ctx

        setup = validator.validate(ctx)
        if setup:
            log.info("  → %s %s | Score %d/4 | %s", symbol, setup.direction.value, setup.score, setup.label)
            setups.append(setup)
        else:
            log.info("  → %s NO EDGE", symbol)

    return setups, all_ctx


async def main_analysis(tv: TVClient):
    ok = await tv.health_check()
    if not ok:
        log.error("TradingView Desktop MCP not reachable. Start TV first.")
        log.error("Run: bash ~/tradingview-mcp/scripts/launch_tv_debug_mac.sh")
        sys.exit(1)

    log.info("=== STOIC LENS ANALYSIS STARTING ===")
    setups, all_ctx = await run_analysis(tv)

    report = generate_report(setups, all_ctx)

    now = datetime.now()
    weekday = ["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"][now.weekday()]
    filename = ROOT / f"stoic_lens_{weekday}_{now.strftime('%d%b%Y').lower()}.md"

    filename.write_text(report, encoding="utf-8")
    log.info("Report saved → %s", filename)
    print(f"\n✅ Report: {filename}\n")
    print(f"📊 Setups found: {len(setups)}")
    for s in sorted(setups, key=lambda x: x.score, reverse=True):
        print(f"   {s.score}/4 {s.direction.value:5s}  {s.symbol:<10} {s.label}")


async def main_monitor(tv: TVClient, interval_min: int = 15):
    log.info("=== STOIC MONITOR — Scanning every %d min ===", interval_min)
    while True:
        await main_analysis(tv)
        log.info("Next scan in %d minutes...", interval_min)
        await asyncio.sleep(interval_min * 60)


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stoic Lens Runner")
    parser.add_argument("--monitor", action="store_true", help="Loop every 15min")
    parser.add_argument("--interval", type=int, default=15, help="Scan interval minutes")
    args = parser.parse_args()

    tv = TVClient()

    if args.monitor:
        asyncio.run(main_monitor(tv, args.interval))
    else:
        asyncio.run(main_analysis(tv))
