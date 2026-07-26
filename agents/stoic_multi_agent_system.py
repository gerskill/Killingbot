"""
╔══════════════════════════════════════════════════════════════════════════════════╗
║  KILLINGBOT — STOIC LENS MULTI-AGENT SYSTEM v1.0                               ║
║  Framework @StoicTA × TraderMorin × aiedge                                     ║
║                                                                                  ║
║  7 agents autonomes qui apprennent ensemble et s'adaptent au marché             ║
║  Architecture : Orchestrator → [MarketAnalyst | MacroNewsAgent |                ║
║                                  SetupValidator | RiskManager |                 ║
║                                  ExecutionAgent | LearningAgent]                ║
╚══════════════════════════════════════════════════════════════════════════════════╝

DÉPENDANCES :
    pip install anthropic aiohttp aiosqlite python-dotenv websockets schedule

CONFIGURATION :
    Créer un fichier .env avec :
        ANTHROPIC_API_KEY=sk-ant-...
        BROKER=oanda               # oanda | ibkr | tradovate
        BROKER_API_KEY=...
        BROKER_ACCOUNT_ID=...
        WEBHOOK_SECRET=...
        FOREX_FACTORY_API=...      # optionnel
"""

import asyncio
import json
import logging
import math
import os
import random
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import aiohttp
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-20s  %(levelname)-7s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/stoic_agents.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("StoicSystem")

# ──────────────────────────────────────────────────────────────────────────────
# TYPES & MODÈLES
# ──────────────────────────────────────────────────────────────────────────────

class Momentum(Enum):
    HCOM  = "HCOM"    # Higher Close Over Mean → biais long
    LCOM  = "LCOM"    # Lower  Close Over Mean → biais short
    DOJI  = "DOJI"    # Neutre

class SetupType(Enum):
    GOLDEN_SBS  = "GOLDEN_SBS"     # 4/4 piliers alignés
    BNR         = "BNR"            # Break and Retest
    SFP         = "SFP"            # Swing Failure Pattern
    FIB_ENTRY   = "FIB_ENTRY"      # Entrée en zone Fib 61.8–78.6%
    NO_EDGE     = "NO_EDGE"        # Zone centrale → pas d'entrée

class TradeDirection(Enum):
    LONG  = "BUY"
    SHORT = "SELL"
    FLAT  = "FLAT"

@dataclass
class DailyContext:
    """Contexte journalier pour une paire (PDH/PDL/PDC + momentum + SMA)"""
    symbol:     str
    timestamp:  str
    pdh:        float   # Previous Day High
    pdl:        float   # Previous Day Low
    pdc:        float   # Previous Day Close
    pdo:        float   # Previous Day Open
    phow:       float   # Previous Week High
    plow:       float   # Previous Week Low
    sma_20:     float
    sma_200:    float
    atr_14:     float
    momentum:   Momentum
    d_bias:     str     # "BULL" | "BEAR"
    news_impact: str = "NONE"   # NONE | LOW | MEDIUM | HIGH
    news_events: list  = field(default_factory=list)

@dataclass
class StoicSetup:
    """Signal de trading Stoic Lens complet"""
    symbol:    str
    direction: TradeDirection
    setup:     SetupType
    score:     int              # 0–4 (4 = Golden SBS)
    entry:     float
    sl:        float
    tp1:       float
    tp2:       float
    rr_tp1:    float
    rr_tp2:    float
    atr:       float
    momentum:  str
    fib_618:   float
    fib_786:   float
    in_fib:    bool
    confidence: float = 0.0     # 0.0–1.0 (enrichi par LearningAgent)
    context:   DailyContext = None
    timestamp: str = ""

@dataclass
class TradeResult:
    """Résultat d'un trade fermé (alimenté le LearningAgent)"""
    trade_id:   str
    symbol:     str
    direction:  str
    setup_type: str
    score:      int
    momentum:   str
    entry:      float
    sl:         float
    tp1:        float
    tp2:        float
    exit_price: float
    pnl_r:      float   # P&L en termes de R (unités de risque)
    duration_h: float   # Durée en heures
    day_of_week: int    # 0=Lundi
    session:    str     # LONDON | NY | ASIA | OVERLAP
    news_impact: str
    timestamp:  str

# ──────────────────────────────────────────────────────────────────────────────
# BASE DE DONNÉES SQLite PARTAGÉE
# ──────────────────────────────────────────────────────────────────────────────

class AgentDatabase:
    """
    SQLite partagée entre tous les agents.
    - Persistance des trades, de la mémoire des agents, des signaux rejetés
    - Thread-safe via asyncio lock
    """

    DB_PATH = os.environ.get("DB_PATH", "data/stoic_agents.db")

    def __init__(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        self._lock = asyncio.Lock()
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id    TEXT PRIMARY KEY,
                symbol      TEXT,
                direction   TEXT,
                setup_type  TEXT,
                score       INTEGER,
                momentum    TEXT,
                entry       REAL,
                sl          REAL,
                tp1         REAL,
                tp2         REAL,
                exit_price  REAL DEFAULT NULL,
                pnl_r       REAL DEFAULT NULL,
                duration_h  REAL DEFAULT NULL,
                day_of_week INTEGER,
                session     TEXT,
                news_impact TEXT,
                status      TEXT DEFAULT 'OPEN',
                timestamp   TEXT
            );

            CREATE TABLE IF NOT EXISTS agent_memory (
                agent       TEXT,
                key         TEXT,
                value       TEXT,
                updated_at  TEXT,
                PRIMARY KEY (agent, key)
            );

            CREATE TABLE IF NOT EXISTS rejected_signals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol      TEXT,
                direction   TEXT,
                reason      TEXT,
                score       INTEGER,
                timestamp   TEXT
            );

            CREATE TABLE IF NOT EXISTS learning_weights (
                condition   TEXT PRIMARY KEY,
                wins        REAL DEFAULT 1.0,
                losses      REAL DEFAULT 1.0,
                last_update TEXT
            );

            CREATE TABLE IF NOT EXISTS market_context (
                symbol      TEXT,
                date        TEXT,
                pdh         REAL,
                pdl         REAL,
                pdc         REAL,
                pdo         REAL,
                atr_14      REAL,
                momentum    TEXT,
                d_bias      TEXT,
                news_impact TEXT,
                PRIMARY KEY (symbol, date)
            );
        """)
        conn.commit()
        conn.close()
        log.info("DB initialisée : %s", self.DB_PATH)

    async def save_trade(self, setup: StoicSetup) -> str:
        trade_id = f"{setup.symbol}_{int(time.time())}"
        async with self._lock:
            conn = sqlite3.connect(self.DB_PATH)
            conn.execute("""
                INSERT OR IGNORE INTO trades VALUES (
                    ?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL,?,?,?,?,?
                )
            """, (
                trade_id, setup.symbol, setup.direction.value,
                setup.setup.value, setup.score, setup.momentum,
                setup.entry, setup.sl, setup.tp1, setup.tp2,
                datetime.now(timezone.utc).isoweekday() - 1,
                self._detect_session(), setup.context.news_impact if setup.context else "NONE",
                "OPEN", setup.timestamp or datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
            conn.close()
        return trade_id

    async def close_trade(self, trade_id: str, exit_price: float, pnl_r: float, duration_h: float):
        async with self._lock:
            conn = sqlite3.connect(self.DB_PATH)
            conn.execute("""
                UPDATE trades
                   SET exit_price=?, pnl_r=?, duration_h=?, status='CLOSED'
                 WHERE trade_id=?
            """, (exit_price, pnl_r, duration_h, trade_id))
            conn.commit()
            conn.close()

    async def get_closed_trades(self, limit: int = 200) -> list[dict]:
        async with self._lock:
            conn = sqlite3.connect(self.DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM trades
                 WHERE status='CLOSED'
                 ORDER BY timestamp DESC
                 LIMIT ?
            """, (limit,)).fetchall()
            conn.close()
        return [dict(r) for r in rows]

    async def get_learning_weight(self, condition: str) -> tuple[float, float]:
        """Retourne (wins, losses) pour une condition (Thompson Sampling)"""
        async with self._lock:
            conn = sqlite3.connect(self.DB_PATH)
            row = conn.execute("""
                SELECT wins, losses FROM learning_weights WHERE condition=?
            """, (condition,)).fetchone()
            conn.close()
        return (row[0], row[1]) if row else (1.0, 1.0)

    async def update_learning_weight(self, condition: str, won: bool):
        """Met à jour Beta(α,β) via Thompson Sampling"""
        wins, losses = await self.get_learning_weight(condition)
        if won:
            wins += 1
        else:
            losses += 1
        async with self._lock:
            conn = sqlite3.connect(self.DB_PATH)
            conn.execute("""
                INSERT INTO learning_weights (condition, wins, losses, last_update)
                VALUES (?,?,?,?)
                ON CONFLICT(condition) DO UPDATE SET wins=excluded.wins, losses=excluded.losses, last_update=excluded.last_update
            """, (condition, wins, losses, datetime.now(timezone.utc).isoformat()))
            conn.commit()
            conn.close()

    async def set_memory(self, agent: str, key: str, value: Any):
        async with self._lock:
            conn = sqlite3.connect(self.DB_PATH)
            conn.execute("""
                INSERT INTO agent_memory (agent, key, value, updated_at)
                VALUES (?,?,?,?)
                ON CONFLICT(agent,key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """, (agent, key, json.dumps(value), datetime.now(timezone.utc).isoformat()))
            conn.commit()
            conn.close()

    async def get_memory(self, agent: str, key: str, default=None) -> Any:
        async with self._lock:
            conn = sqlite3.connect(self.DB_PATH)
            row = conn.execute("""
                SELECT value FROM agent_memory WHERE agent=? AND key=?
            """, (agent, key)).fetchone()
            conn.close()
        return json.loads(row[0]) if row else default

    def _detect_session(self) -> str:
        h = datetime.now(timezone.utc).hour
        if   0 <= h < 7:  return "ASIA"
        elif 7 <= h < 9:  return "LONDON_OPEN"
        elif 9 <= h < 13: return "LONDON"
        elif 13 <= h < 16: return "OVERLAP"
        elif 16 <= h < 22: return "NY"
        else:              return "CLOSE"

# ──────────────────────────────────────────────────────────────────────────────
# AGENT DE BASE
# ──────────────────────────────────────────────────────────────────────────────

class BaseAgent:
    """Classe mère — tous les agents héritent d'ici"""

    MODEL = "claude-haiku-4-5-20251001"   # Modèle rapide pour inférences courantes
    MODEL_HEAVY = "claude-sonnet-4-6"      # Pour analyses complexes

    def __init__(self, name: str, db: AgentDatabase):
        self.name   = name
        self.db     = db
        self.client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.log    = logging.getLogger(name)

    async def think(self, prompt: str, data: dict = None, heavy: bool = False) -> str:
        """Appel Claude API avec contexte optionnel"""
        messages = [{"role": "user", "content": prompt}]
        if data:
            messages[0]["content"] = f"{prompt}\n\nDonnées:\n```json\n{json.dumps(data, indent=2)}\n```"

        model = self.MODEL_HEAVY if heavy else self.MODEL
        resp = await self.client.messages.create(
            model=model,
            max_tokens=1024,
            system=f"Tu es {self.name}, un agent de trading expert du framework Stoic Lens. Tu analyses les marchés avec précision et rigueur.",
            messages=messages,
        )
        return resp.content[0].text

    async def remember(self, key: str, value: Any):
        await self.db.set_memory(self.name, key, value)

    async def recall(self, key: str, default=None) -> Any:
        return await self.db.get_memory(self.name, key, default)

# ──────────────────────────────────────────────────────────────────────────────
# AGENT 1 — MARKET ANALYST
# ──────────────────────────────────────────────────────────────────────────────

class MarketAnalystAgent(BaseAgent):
    """
    Calcule le contexte Stoic Lens pour chaque paire :
    HCOM/LCOM, PDH/PDL/PDC, SMA20/200, zones Fib
    """

    TV_API = os.environ.get("TV_DESKTOP_URL", "http://localhost:3000")

    def __init__(self, db: AgentDatabase):
        super().__init__("MarketAnalyst", db)
        self._session: aiohttp.ClientSession = None

    async def start(self):
        self._session = aiohttp.ClientSession()

    async def stop(self):
        if self._session:
            await self._session.close()

    async def analyze(self, symbol: str) -> DailyContext | None:
        """Récupère les données OHLCV via TradingView Desktop MCP et calcule le contexte"""
        try:
            ctx = await self._fetch_tv_data(symbol)
            await self.remember(f"last_ctx_{symbol}", asdict(ctx))
            return ctx
        except Exception as e:
            self.log.error("Erreur analyse %s: %s", symbol, e)
            return None

    async def _fetch_tv_data(self, symbol: str) -> DailyContext:
        """
        Appelle TradingView Desktop MCP via HTTP pour obtenir les données OHLCV
        Adapté au format du wrapper tv_mcp local (port 3000 par défaut)
        """
        # Appel au MCP TradingView pour les données Daily
        payload_daily = {
            "tool": "data_get_ohlcv",
            "args": {
                "symbol": symbol,
                "timeframe": "1D",
                "bars": 3,
                "summary": True
            }
        }
        payload_weekly = {
            "tool": "data_get_ohlcv",
            "args": {
                "symbol": symbol,
                "timeframe": "1W",
                "bars": 2,
                "summary": True
            }
        }

        try:
            async with self._session.post(f"{self.TV_API}/call_tool", json=payload_daily) as r:
                daily_data = await r.json()
            async with self._session.post(f"{self.TV_API}/call_tool", json=payload_weekly) as r:
                weekly_data = await r.json()
        except Exception:
            # Fallback : données mock pour développement / test
            self.log.warning("TV MCP non disponible — utilisation de données mock pour %s", symbol)
            daily_data  = self._mock_daily(symbol)
            weekly_data = self._mock_weekly(symbol)

        # Parser les réponses
        d = self._parse_ohlcv(daily_data)
        w = self._parse_ohlcv(weekly_data)

        # Journée précédente
        prev  = d[-2] if len(d) >= 2 else d[-1]
        pprev = d[-3] if len(d) >= 3 else prev
        prevw = w[-2] if len(w) >= 2 else w[-1]

        pdh, pdl, pdc, pdo = prev["high"], prev["low"], prev["close"], prev["open"]
        phow  = prevw["high"]
        plow  = prevw["low"]

        # SMAs approximées sur les barres disponibles
        closes = [bar["close"] for bar in d]
        sma_20  = sum(closes[-min(20,  len(closes)):]) / min(20,  len(closes))
        sma_200 = sum(closes[-min(200, len(closes)):]) / min(200, len(closes))

        # ATR simplifié (moyenne des True Ranges sur les barres dispo)
        trs = []
        for i in range(1, len(d)):
            hl = d[i]["high"] - d[i]["low"]
            hc = abs(d[i]["high"] - d[i-1]["close"])
            lc = abs(d[i]["low"]  - d[i-1]["close"])
            trs.append(max(hl, hc, lc))
        atr_14 = sum(trs[-14:]) / len(trs[-14:]) if trs else (pdh - pdl) * 0.5

        # HCOM / LCOM
        if pdc > pdo:
            momentum = Momentum.HCOM
        elif pdc < pdo:
            momentum = Momentum.LCOM
        else:
            momentum = Momentum.DOJI

        d_bias = "BULL" if sma_20 > sma_200 else "BEAR"

        return DailyContext(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc).isoformat(),
            pdh=pdh, pdl=pdl, pdc=pdc, pdo=pdo,
            phow=phow, plow=plow,
            sma_20=sma_20, sma_200=sma_200,
            atr_14=atr_14,
            momentum=momentum,
            d_bias=d_bias,
        )

    def _parse_ohlcv(self, data: dict) -> list[dict]:
        """Parse la réponse OHLCV du MCP TradingView"""
        bars = data.get("bars") or data.get("result", {}).get("bars") or []
        if not bars and isinstance(data, list):
            bars = data
        return [{"open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"]} for b in bars] if bars else [{"open": 1.0, "high": 1.01, "low": 0.99, "close": 1.005}]

    def _mock_daily(self, symbol: str) -> dict:
        """Données mock pour développement sans TV Desktop"""
        base = {"EURUSD": 1.1600, "GBPUSD": 1.3400, "USDJPY": 160.0, "USDCAD": 1.3900, "XAUUSD": 4500.0}.get(symbol, 100.0)
        r = random.uniform(0.003, 0.012)
        bars = []
        price = base
        for i in range(5):
            o = price
            c = price * (1 + random.uniform(-r, r))
            h = max(o, c) * (1 + random.uniform(0, r * 0.5))
            l = min(o, c) * (1 - random.uniform(0, r * 0.5))
            bars.append({"open": o, "high": h, "low": l, "close": c})
            price = c
        return {"bars": bars}

    def _mock_weekly(self, symbol: str) -> dict:
        d = self._mock_daily(symbol)
        bars = d["bars"]
        week = {"open": bars[0]["open"], "high": max(b["high"] for b in bars), "low": min(b["low"] for b in bars), "close": bars[-1]["close"]}
        return {"bars": [week, week]}

# ──────────────────────────────────────────────────────────────────────────────
# AGENT 2 — MACRO NEWS AGENT
# ──────────────────────────────────────────────────────────────────────────────

class MacroNewsAgent(BaseAgent):
    """
    Scrape le calendrier économique (ForexFactory) et évalue l'impact
    des annonces sur les paires. Bloque les trades HIGH IMPACT ±30min.
    """

    FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

    def __init__(self, db: AgentDatabase):
        super().__init__("MacroNewsAgent", db)
        self._cache: list[dict] = []
        self._cache_time: float = 0

    async def get_news_impact(self, symbol: str) -> tuple[str, list[dict]]:
        """
        Retourne (impact_level, events) pour une paire
        impact_level : NONE | LOW | MEDIUM | HIGH
        """
        currencies = self._symbol_to_currencies(symbol)
        events     = await self._fetch_events()
        now        = datetime.now(timezone.utc)

        upcoming = []
        for ev in events:
            if not any(c in ev.get("country", "").upper() for c in currencies):
                continue
            try:
                ev_time = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
                delta_min = abs((ev_time - now).total_seconds() / 60)
                if delta_min <= 120:   # Fenêtre de 2h
                    upcoming.append({**ev, "delta_min": round(delta_min, 1)})
            except Exception:
                pass

        if not upcoming:
            return "NONE", []

        # Impact maximal parmi les annonces à venir
        impact_map = {"Low": 1, "Medium": 2, "High": 3}
        max_impact = max((impact_map.get(e.get("impact", "Low"), 1) for e in upcoming), default=1)
        level_map  = {1: "LOW", 2: "MEDIUM", 3: "HIGH"}
        return level_map[max_impact], upcoming

    async def should_block_trade(self, symbol: str) -> tuple[bool, str]:
        """Bloque le trade si annonce HIGH IMPACT dans les 30 prochaines minutes"""
        impact, events = await self.get_news_impact(symbol)
        if impact == "HIGH":
            close_events = [e for e in events if e.get("delta_min", 999) <= 30]
            if close_events:
                names = ", ".join(e.get("title", "?") for e in close_events)
                return True, f"Annonce HIGH IMPACT dans <30min : {names}"
        return False, ""

    async def _fetch_events(self) -> list[dict]:
        """Récupère et met en cache le calendrier ForexFactory"""
        now = time.time()
        if now - self._cache_time < 3600:   # Cache 1h
            return self._cache

        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(self.FF_URL, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    self._cache = await r.json(content_type=None)
                    self._cache_time = now
                    self.log.info("Calendrier économique mis à jour : %d événements", len(self._cache))
        except Exception as e:
            self.log.warning("Impossible de charger le calendrier : %s", e)
            self._cache = []

        return self._cache

    def _symbol_to_currencies(self, symbol: str) -> list[str]:
        """EUR/USD → ['EUR', 'USD']"""
        s = symbol.upper().replace("/", "").replace(".", "")
        currency_map = {
            "XAUUSD": ["USD"], "XAGUSD": ["USD"],
            "NAS100": ["USD"], "US30": ["USD"], "US500": ["USD"],
            "BTCUSD": ["USD"], "ETHUSD": ["USD"],
        }
        if s in currency_map:
            return currency_map[s]
        if len(s) == 6:
            return [s[:3], s[3:]]
        return [s[:3]] if len(s) >= 3 else [s]

# ──────────────────────────────────────────────────────────────────────────────
# AGENT 3 — SETUP VALIDATOR
# ──────────────────────────────────────────────────────────────────────────────

class SetupValidatorAgent(BaseAgent):
    """
    Applique les 4 piliers Stoic Lens et calcule le score (0–4).
    Génère le StoicSetup si score ≥ seuil.
    """

    MIN_SCORE = int(os.environ.get("MIN_SCORE", "3"))

    def __init__(self, db: AgentDatabase):
        super().__init__("SetupValidator", db)

    async def validate(self, ctx: DailyContext, direction: TradeDirection) -> StoicSetup | None:
        """Valide un setup potentiel et retourne un StoicSetup si valide"""
        score = self._compute_score(ctx, direction)
        if score < self.MIN_SCORE:
            self.log.debug("%s %s — score trop bas: %d", ctx.symbol, direction.name, score)
            return None

        current_price = ctx.pdc   # Approx — sera raffiné par l'exécution
        setup_type    = SetupType.GOLDEN_SBS if score == 4 else self._detect_pattern(ctx, direction)
        fib_range     = max(ctx.pdh - ctx.pdl, ctx.atr_14 * 0.1)

        if direction == TradeDirection.LONG:
            fib_618 = ctx.pdh - fib_range * 0.618
            fib_786 = ctx.pdh - fib_range * 0.786
            entry   = (fib_618 + fib_786) / 2
            sl      = ctx.pdl - ctx.atr_14 * 1.5
            risk    = max(entry - sl, ctx.atr_14 * 0.5)
            tp1     = entry + risk * 2.0
            tp2     = entry + risk * 3.5
        else:
            fib_618 = ctx.pdl + fib_range * 0.618
            fib_786 = ctx.pdl + fib_range * 0.786
            entry   = (fib_618 + fib_786) / 2
            sl      = ctx.pdh + ctx.atr_14 * 1.5
            risk    = max(sl - entry, ctx.atr_14 * 0.5)
            tp1     = entry - risk * 2.0
            tp2     = entry - risk * 3.5

        rr1 = abs(tp1 - entry) / risk
        rr2 = abs(tp2 - entry) / risk

        in_fib = fib_786 <= current_price <= fib_618 if direction == TradeDirection.LONG else fib_618 <= current_price <= fib_786

        return StoicSetup(
            symbol    = ctx.symbol,
            direction = direction,
            setup     = setup_type,
            score     = score,
            entry     = round(entry, 5),
            sl        = round(sl, 5),
            tp1       = round(tp1, 5),
            tp2       = round(tp2, 5),
            rr_tp1    = round(rr1, 2),
            rr_tp2    = round(rr2, 2),
            atr       = ctx.atr_14,
            momentum  = ctx.momentum.value,
            fib_618   = round(fib_618, 5),
            fib_786   = round(fib_786, 5),
            in_fib    = in_fib,
            context   = ctx,
            timestamp = datetime.now(timezone.utc).isoformat(),
        )

    def _compute_score(self, ctx: DailyContext, direction: TradeDirection) -> int:
        score = 0

        # Pilier 1 — HCOM/LCOM
        if direction == TradeDirection.LONG  and ctx.momentum == Momentum.HCOM: score += 1
        if direction == TradeDirection.SHORT and ctx.momentum == Momentum.LCOM: score += 1

        # Pilier 2 — SMA20/200 bias
        sma_bull = ctx.sma_20 > ctx.sma_200
        if direction == TradeDirection.LONG  and (sma_bull or ctx.d_bias == "BULL"): score += 1
        if direction == TradeDirection.SHORT and (not sma_bull or ctx.d_bias == "BEAR"): score += 1

        # Pilier 3 — Proximité niveau clé (PDH/PDL/PDC/semaine)
        tol = max(ctx.pdc * 0.002, ctx.atr_14 * 0.5)
        if direction == TradeDirection.LONG:
            if abs(ctx.pdc - ctx.pdl) <= tol or abs(ctx.pdc - ctx.plow) <= tol: score += 1
        else:
            if abs(ctx.pdc - ctx.pdh) <= tol or abs(ctx.pdc - ctx.phow) <= tol: score += 1

        # Pilier 4 — Pattern B&R / SFP / Fib
        if self._has_pattern(ctx, direction): score += 1

        return score

    def _has_pattern(self, ctx: DailyContext, direction: TradeDirection) -> bool:
        """Détecte si un pattern d'entrée valide est présent"""
        fib_range = max(ctx.pdh - ctx.pdl, ctx.atr_14 * 0.1)
        tol       = ctx.atr_14 * 0.6

        if direction == TradeDirection.LONG:
            fib_zone = (ctx.pdh - fib_range * 0.618 - tol, ctx.pdh - fib_range * 0.786 + tol)
            near_pdl = abs(ctx.pdc - ctx.pdl) <= ctx.atr_14 * 0.5
            in_fib   = fib_zone[1] <= ctx.pdc <= fib_zone[0]
            return near_pdl or in_fib
        else:
            fib_zone = (ctx.pdl + fib_range * 0.618 - tol, ctx.pdl + fib_range * 0.786 + tol)
            near_pdh = abs(ctx.pdc - ctx.pdh) <= ctx.atr_14 * 0.5
            in_fib   = fib_zone[0] <= ctx.pdc <= fib_zone[1]
            return near_pdh or in_fib

    def _detect_pattern(self, ctx: DailyContext, direction: TradeDirection) -> SetupType:
        """Détermine le type de pattern (B&R vs Fib)"""
        fib_range = max(ctx.pdh - ctx.pdl, ctx.atr_14 * 0.1)
        tol       = ctx.atr_14 * 0.6

        if direction == TradeDirection.LONG:
            fib618 = ctx.pdh - fib_range * 0.618
            fib786 = ctx.pdh - fib_range * 0.786
            if fib786 - tol <= ctx.pdc <= fib618 + tol:
                return SetupType.FIB_ENTRY
        else:
            fib618 = ctx.pdl + fib_range * 0.618
            fib786 = ctx.pdl + fib_range * 0.786
            if fib618 - tol <= ctx.pdc <= fib786 + tol:
                return SetupType.FIB_ENTRY

        return SetupType.BNR

# ──────────────────────────────────────────────────────────────────────────────
# AGENT 4 — RISK MANAGER
# ──────────────────────────────────────────────────────────────────────────────

class RiskManagerAgent(BaseAgent):
    """
    Calcule la taille de position, vérifie les limites de drawdown,
    refuse ou ajuste les trades si les règles de risk sont violées.
    """

    MAX_RISK_PCT    = float(os.environ.get("MAX_RISK_PCT",    "1.0"))    # % du capital par trade
    MAX_DAILY_LOSS  = float(os.environ.get("MAX_DAILY_LOSS",  "3.0"))    # % du capital max/jour
    MAX_OPEN_TRADES = int(os.environ.get("MAX_OPEN_TRADES",   "3"))       # Trades simultanés max
    ACCOUNT_EQUITY  = float(os.environ.get("ACCOUNT_EQUITY",  "10000"))  # Capital en $

    def __init__(self, db: AgentDatabase):
        super().__init__("RiskManager", db)

    async def approve(self, setup: StoicSetup) -> tuple[bool, str, dict]:
        """
        Retourne (approved, reason, position_info)
        position_info contient : qty, risk_usd, rr_tp1, rr_tp2
        """
        # Vérifier drawdown journalier
        daily_loss = await self._get_daily_pnl()
        if daily_loss <= -(self.ACCOUNT_EQUITY * self.MAX_DAILY_LOSS / 100):
            return False, f"Limite perte journalière atteinte : {daily_loss:.0f}$", {}

        # Vérifier nombre de trades ouverts
        open_trades = await self._count_open_trades()
        if open_trades >= self.MAX_OPEN_TRADES:
            return False, f"Max trades ouverts atteint : {open_trades}/{self.MAX_OPEN_TRADES}", {}

        # RR minimal
        if setup.rr_tp1 < 1.5:
            return False, f"RR TP1 trop faible : {setup.rr_tp1:.1f} < 1.5", {}

        # Calcul taille de position
        risk_usd  = self.ACCOUNT_EQUITY * self.MAX_RISK_PCT / 100
        stop_dist = abs(setup.entry - setup.sl)
        if stop_dist <= 0:
            return False, "Distance SL = 0 — setup invalide", {}

        qty = risk_usd / stop_dist

        pos_info = {
            "qty":      round(qty, 4),
            "risk_usd": round(risk_usd, 2),
            "risk_pct": self.MAX_RISK_PCT,
            "rr_tp1":   setup.rr_tp1,
            "rr_tp2":   setup.rr_tp2,
            "stop_dist": round(stop_dist, 5),
        }

        self.log.info("✅ Risk OK — %s %s | Qty=%.4f | Risk=$%.2f | RR1=%.1f | RR2=%.1f",
                      setup.symbol, setup.direction.value, qty, risk_usd, setup.rr_tp1, setup.rr_tp2)
        return True, "Risk approuvé", pos_info

    async def _get_daily_pnl(self) -> float:
        trades = await self.db.get_closed_trades(50)
        today  = datetime.now(timezone.utc).date().isoformat()
        return sum(t.get("pnl_r", 0) * (self.ACCOUNT_EQUITY * self.MAX_RISK_PCT / 100)
                   for t in trades if t.get("timestamp", "")[:10] == today)

    async def _count_open_trades(self) -> int:
        async with self.db._lock:
            conn = sqlite3.connect(self.db.DB_PATH)
            row  = conn.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'").fetchone()
            conn.close()
        return row[0] if row else 0

# ──────────────────────────────────────────────────────────────────────────────
# AGENT 5 — EXECUTION AGENT
# ──────────────────────────────────────────────────────────────────────────────

class ExecutionAgent(BaseAgent):
    """
    Envoie les ordres au broker via webhook TradingView ou API directe.
    Surveille les positions ouvertes et gère le trailing stop.
    """

    BROKER         = os.environ.get("BROKER", "mock")  # mock | oanda | ibkr
    BROKER_API_KEY = os.environ.get("BROKER_API_KEY",  "")
    BROKER_ACCOUNT = os.environ.get("BROKER_ACCOUNT_ID", "")
    WEBHOOK_URL    = os.environ.get("WEBHOOK_URL",      "http://localhost:5001/webhook")

    # Base URLs brokers
    OANDA_URL = "https://api-fxtrade.oanda.com"   # prod
    OANDA_URL_DEMO = "https://api-fxpractice.oanda.com"  # démo

    def __init__(self, db: AgentDatabase):
        super().__init__("ExecutionAgent", db)
        self._open_positions: dict[str, dict] = {}

    async def execute(self, setup: StoicSetup, position_info: dict) -> str | None:
        """Envoie l'ordre et retourne le trade_id"""
        trade_id = await self.db.save_trade(setup)

        payload = self._build_payload(setup, position_info, trade_id)
        success  = await self._send_order(payload)

        if success:
            self._open_positions[trade_id] = {
                "setup": asdict(setup) if hasattr(setup, "__dataclass_fields__") else {},
                "position_info": position_info,
                "trade_id": trade_id,
                "opened_at": time.time(),
            }
            self.log.info("📤 Ordre envoyé — %s %s @ %.5f | SL=%.5f | TP2=%.5f | ID=%s",
                          setup.symbol, setup.direction.value, setup.entry, setup.sl, setup.tp2, trade_id)
            return trade_id
        else:
            self.log.error("❌ Échec envoi ordre — %s", setup.symbol)
            return None

    async def close_position(self, trade_id: str, exit_price: float, reason: str = "SIGNAL"):
        """Ferme une position et enregistre le résultat"""
        if trade_id not in self._open_positions:
            return

        pos    = self._open_positions.pop(trade_id)
        opened = pos.get("opened_at", time.time())
        duration_h = (time.time() - opened) / 3600

        # Calcul P&L en R
        setup_data = pos.get("setup", {})
        entry  = setup_data.get("entry", exit_price)
        sl     = setup_data.get("sl",    exit_price)
        risk   = abs(entry - sl)
        if risk > 0:
            raw_pnl = (exit_price - entry) if setup_data.get("direction") == "BUY" else (entry - exit_price)
            pnl_r   = raw_pnl / risk
        else:
            pnl_r = 0

        await self.db.close_trade(trade_id, exit_price, round(pnl_r, 2), round(duration_h, 2))
        self.log.info("📥 Position fermée — %s | P&L=%.2fR | Durée=%.1fh | Raison=%s",
                      trade_id, pnl_r, duration_h, reason)

    def _build_payload(self, setup: StoicSetup, pos: dict, trade_id: str) -> dict:
        return {
            "trade_id":  trade_id,
            "action":    setup.direction.value,
            "symbol":    setup.symbol,
            "qty":       pos.get("qty", 0),
            "entry":     setup.entry,
            "sl":        setup.sl,
            "tp1":       setup.tp1,
            "tp2":       setup.tp2,
            "setup":     setup.setup.value,
            "score":     setup.score,
            "momentum":  setup.momentum,
            "risk_pct":  pos.get("risk_pct", 1.0),
            "timestamp": setup.timestamp,
        }

    async def _send_order(self, payload: dict) -> bool:
        if self.BROKER == "mock":
            self.log.info("[MOCK] Ordre simulé : %s", json.dumps(payload, indent=2))
            return True

        elif self.BROKER == "oanda":
            return await self._send_oanda(payload)

        else:
            # Fallback : webhook TradingView
            return await self._send_webhook(payload)

    async def _send_oanda(self, payload: dict) -> bool:
        """Envoi via OANDA REST API v20"""
        url = f"{self.OANDA_URL_DEMO}/v3/accounts/{self.BROKER_ACCOUNT}/orders"
        direction = payload["action"]
        units = payload["qty"] if direction == "BUY" else -payload["qty"]

        order_body = {
            "order": {
                "type":         "MARKET",
                "instrument":   payload["symbol"].replace("/", "_"),
                "units":        str(round(units)),
                "stopLossOnFill": {"price": str(round(payload["sl"], 5))},
                "takeProfitOnFill": {"price": str(round(payload["tp2"], 5))},
                "tradeClientExtensions": {"comment": f"{payload['setup']}|{payload['score']}/4"}
            }
        }
        headers = {
            "Authorization": f"Bearer {self.BROKER_API_KEY}",
            "Content-Type":  "application/json",
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, json=order_body, headers=headers) as r:
                    if r.status in (200, 201):
                        data = await r.json()
                        self.log.info("OANDA order créé : %s", data.get("orderCreateTransaction", {}).get("id"))
                        return True
                    else:
                        text = await r.text()
                        self.log.error("OANDA erreur %d : %s", r.status, text)
                        return False
        except Exception as e:
            self.log.error("OANDA exception : %s", e)
            return False

    async def _send_webhook(self, payload: dict) -> bool:
        """Envoie via webhook local (compatible webhook_server.py existant)"""
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(self.WEBHOOK_URL, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    return r.status == 200
        except Exception as e:
            self.log.error("Webhook erreur : %s", e)
            return False

# ──────────────────────────────────────────────────────────────────────────────
# AGENT 6 — LEARNING AGENT
# ──────────────────────────────────────────────────────────────────────────────

class LearningAgent(BaseAgent):
    """
    Apprend des résultats passés via Thompson Sampling (Beta Bandits).
    Ajuste la confiance des setups et partage ses insights avec les autres agents.

    Thompson Sampling :
      - Pour chaque condition (ex: "HCOM_LONG_GOLDEN_SBS"), maintient Beta(α, β)
      - α = wins + 1, β = losses + 1
      - Confiance = E[Beta(α,β)] = α / (α+β)
    """

    def __init__(self, db: AgentDatabase):
        super().__init__("LearningAgent", db)
        self._insights: dict[str, dict] = {}

    async def enrich_setup(self, setup: StoicSetup) -> StoicSetup:
        """Enrichit un setup avec sa confiance estimée via Thompson Sampling"""
        conds = self._build_conditions(setup)
        confidences = []

        for cond in conds:
            alpha, beta_v = await self.db.get_learning_weight(cond)
            # Espérance de la distribution Beta
            confidence = alpha / (alpha + beta_v)
            confidences.append(confidence)

        # Confiance globale = moyenne géométrique
        if confidences:
            product = 1.0
            for c in confidences:
                product *= c
            setup.confidence = round(product ** (1 / len(confidences)), 3)
        else:
            setup.confidence = 0.5

        return setup

    async def learn_from_trade(self, trade: TradeResult):
        """Met à jour Thompson Sampling pour chaque condition du trade"""
        conditions = self._conditions_from_result(trade)
        won        = trade.pnl_r > 0

        for cond in conditions:
            await self.db.update_learning_weight(cond, won)

        await self._update_insights()

    async def get_best_conditions(self, top_n: int = 5) -> list[dict]:
        """Retourne les N meilleures conditions selon Thompson Sampling"""
        async with self.db._lock:
            conn = sqlite3.connect(self.db.DB_PATH)
            rows = conn.execute("""
                SELECT condition, wins, losses,
                       wins / (wins + losses) as wr
                  FROM learning_weights
                 ORDER BY wr DESC
                 LIMIT ?
            """, (top_n,)).fetchall()
            conn.close()
        return [{"condition": r[0], "wins": r[1], "losses": r[2], "wr": round(r[3]*100, 1)} for r in rows]

    async def generate_insight(self) -> str:
        """Génère un insight textuel via Claude sur les patterns appris"""
        trades = await self.db.get_closed_trades(100)
        if not trades:
            return "Pas encore assez de trades pour générer un insight."

        best = await self.get_best_conditions(10)
        summary = {
            "total_trades": len(trades),
            "avg_pnl_r": round(sum(t.get("pnl_r", 0) for t in trades) / len(trades), 2),
            "win_rate": round(sum(1 for t in trades if t.get("pnl_r", 0) > 0) / len(trades) * 100, 1),
            "best_conditions": best,
        }

        return await self.think(
            "Analyse ces statistiques de trading Stoic Lens et donne 3 insights actionnables "
            "pour améliorer les performances. Sois concis et précis.",
            data=summary,
            heavy=False,
        )

    async def _update_insights(self):
        insight = await self.generate_insight()
        await self.remember("latest_insight", {"text": insight, "timestamp": datetime.now(timezone.utc).isoformat()})
        self._insights["latest"] = insight

    def _build_conditions(self, setup: StoicSetup) -> list[str]:
        """Construit les clés de conditions pour Thompson Sampling"""
        base = f"{setup.momentum}_{setup.direction.value}_{setup.setup.value}"
        return [
            base,
            f"{setup.symbol}_{setup.direction.value}",
            f"score_{setup.score}_{setup.direction.value}",
            f"fib_{setup.in_fib}_{setup.direction.value}",
            f"news_{setup.context.news_impact if setup.context else 'NONE'}_{setup.direction.value}",
        ]

    def _conditions_from_result(self, trade: TradeResult) -> list[str]:
        base = f"{trade.momentum}_{trade.direction}_{trade.setup_type}"
        return [
            base,
            f"{trade.symbol}_{trade.direction}",
            f"score_{trade.score}_{trade.direction}",
            f"news_{trade.news_impact}_{trade.direction}",
            f"dow_{trade.day_of_week}_{trade.direction}",
            f"session_{trade.session}_{trade.direction}",
        ]

# ──────────────────────────────────────────────────────────────────────────────
# AGENT 7 — ORCHESTRATEUR
# ──────────────────────────────────────────────────────────────────────────────

class OrchestratorAgent(BaseAgent):
    """
    Coordinateur central — orchestre le flux complet :
    1. Analyse du marché (MarketAnalyst)
    2. Check actualités (MacroNewsAgent)
    3. Validation setup (SetupValidator)
    4. Enrichissement IA (LearningAgent)
    5. Approbation risk (RiskManager)
    6. Exécution (ExecutionAgent)
    7. Apprentissage post-trade (LearningAgent)

    Tourne en boucle asynchrone toutes les N minutes.
    """

    SCAN_INTERVAL_MIN = int(os.environ.get("SCAN_INTERVAL_MIN", "15"))

    # Liste de paires à surveiller (personnalisable)
    WATCHLIST = os.environ.get("WATCHLIST", "EURUSD,GBPUSD,USDJPY,USDCAD,XAUUSD,GBPJPY,AUDUSD,NZDUSD,USDCHF,EURJPY").split(",")

    def __init__(self):
        self.db        = AgentDatabase()
        super().__init__("Orchestrator", self.db)

        self.analyst   = MarketAnalystAgent(self.db)
        self.news      = MacroNewsAgent(self.db)
        self.validator = SetupValidatorAgent(self.db)
        self.risk_mgr  = RiskManagerAgent(self.db)
        self.executor  = ExecutionAgent(self.db)
        self.learner   = LearningAgent(self.db)

        self._running   = False
        self._cycle_n   = 0

    async def start(self):
        """Lance le système multi-agents en boucle"""
        await self.analyst.start()
        self._running = True
        self.log.info("🚀 Stoic Multi-Agent System démarré — watchlist: %s", self.WATCHLIST)
        self.log.info("   Scan toutes les %d minutes", self.SCAN_INTERVAL_MIN)

        while self._running:
            try:
                await self._run_cycle()
            except Exception as e:
                self.log.error("Erreur cycle #%d: %s", self._cycle_n, e, exc_info=True)

            await asyncio.sleep(self.SCAN_INTERVAL_MIN * 60)

    async def stop(self):
        self._running = False
        await self.analyst.stop()
        self.log.info("🛑 Système arrêté")

    async def _run_cycle(self):
        """Un cycle complet d'analyse pour toutes les paires de la watchlist"""
        self._cycle_n += 1
        self.log.info("═══ Cycle #%d (%s) ══════════════════════════════",
                      self._cycle_n, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

        signals_found = 0

        for symbol in self.WATCHLIST:
            setup = await self._process_symbol(symbol)
            if setup:
                signals_found += 1

        # Génération d'insight toutes les 10 cycles
        if self._cycle_n % 10 == 0:
            insight = await self.learner.generate_insight()
            self.log.info("💡 Insight LearningAgent:\n%s", insight)

        self.log.info("─── Fin cycle #%d — %d signal(s) exécuté(s)", self._cycle_n, signals_found)

    async def _process_symbol(self, symbol: str) -> StoicSetup | None:
        """Pipeline complet pour un symbole"""

        # 1. Analyse marché
        ctx = await self.analyst.analyze(symbol)
        if not ctx:
            return None

        # 2. Actualités économiques
        blocked, block_reason = await self.news.should_block_trade(symbol)
        if blocked:
            self.log.info("⛔ %s bloqué — %s", symbol, block_reason)
            return None

        news_impact, news_events = await self.news.get_news_impact(symbol)
        ctx.news_impact = news_impact
        ctx.news_events = news_events

        # 3. Déterminer direction selon HCOM/LCOM
        if ctx.momentum == Momentum.HCOM:
            direction = TradeDirection.LONG
        elif ctx.momentum == Momentum.LCOM:
            direction = TradeDirection.SHORT
        else:
            self.log.debug("%s: DOJI — pas de biais", symbol)
            return None

        # 4. Validation du setup Stoic Lens
        setup = await self.validator.validate(ctx, direction)
        if not setup:
            return None

        # 5. Enrichissement par le LearningAgent (confiance Thompson)
        setup = await self.learner.enrich_setup(setup)

        # Filtre confiance minimale (après > 20 trades seulement)
        trades_count = len(await self.db.get_closed_trades(5))
        if trades_count >= 20 and setup.confidence < 0.35:
            self.log.info("🔴 %s rejeté par LearningAgent — confiance trop basse: %.0f%%",
                          symbol, setup.confidence * 100)
            return None

        # 6. Approbation Risk Manager
        approved, reason, pos_info = await self.risk_mgr.approve(setup)
        if not approved:
            self.log.info("🔴 %s rejeté RiskManager — %s", symbol, reason)
            return None

        # 7. Log du signal
        self.log.info(
            "⭐ SIGNAL %s | %s %s | Score=%d/4 | Confiance=%.0f%% | "
            "Entry=%.5f | SL=%.5f | TP2=%.5f | RR=%.1f | News=%s",
            setup.setup.value, symbol, direction.value,
            setup.score, setup.confidence * 100,
            setup.entry, setup.sl, setup.tp2, setup.rr_tp2,
            news_impact
        )

        # 8. Exécution
        trade_id = await self.executor.execute(setup, pos_info)
        return setup if trade_id else None

    async def process_webhook_close(self, payload: dict):
        """
        Appelé par webhook_server.py quand TradingView envoie une alerte de fermeture.
        Met à jour la DB et déclenche l'apprentissage.
        """
        trade_id   = payload.get("trade_id")
        exit_price = float(payload.get("exit_price", 0))
        pnl_r      = float(payload.get("pnl_r", 0))

        if not trade_id:
            return

        await self.executor.close_position(trade_id, exit_price)

        # Apprentissage
        trade_data = await self._get_trade_for_learning(trade_id, pnl_r)
        if trade_data:
            await self.learner.learn_from_trade(trade_data)
            self.log.info("🧠 LearningAgent mis à jour pour trade %s | P&L=%.2fR", trade_id, pnl_r)

    async def _get_trade_for_learning(self, trade_id: str, pnl_r: float) -> TradeResult | None:
        async with self.db._lock:
            conn = sqlite3.connect(self.db.DB_PATH)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM trades WHERE trade_id=?", (trade_id,)).fetchone()
            conn.close()

        if not row:
            return None

        return TradeResult(
            trade_id    = row["trade_id"],
            symbol      = row["symbol"],
            direction   = row["direction"],
            setup_type  = row["setup_type"],
            score       = row["score"],
            momentum    = row["momentum"],
            entry       = row["entry"],
            sl          = row["sl"],
            tp1         = row["tp1"],
            tp2         = row["tp2"],
            exit_price  = row["exit_price"] or 0,
            pnl_r       = pnl_r,
            duration_h  = row["duration_h"] or 0,
            day_of_week = row["day_of_week"] or 0,
            session     = row["session"] or "UNKNOWN",
            news_impact = row["news_impact"] or "NONE",
            timestamp   = row["timestamp"],
        )

# ──────────────────────────────────────────────────────────────────────────────
# INTEGRATION WEBHOOK SERVER (Flask extension)
# ──────────────────────────────────────────────────────────────────────────────

def create_flask_extension(orchestrator: OrchestratorAgent):
    """
    Retourne un blueprint Flask à monter sur webhook_server.py existant.

    Dans webhook_server.py, ajouter :
        from stoic_multi_agent_system import create_flask_extension, OrchestratorAgent
        orchestrator = OrchestratorAgent()
        app.register_blueprint(create_flask_extension(orchestrator))
        asyncio.run(orchestrator.start())   # dans un thread séparé
    """
    try:
        from flask import Blueprint, request, jsonify

        bp = Blueprint("stoic_agents", __name__)

        @bp.route("/agent/close", methods=["POST"])
        def close_trade():
            payload = request.get_json(force=True)
            asyncio.run(orchestrator.process_webhook_close(payload))
            return jsonify({"status": "ok"})

        @bp.route("/agent/status", methods=["GET"])
        def status():
            return jsonify({
                "cycle": orchestrator._cycle_n,
                "running": orchestrator._running,
                "watchlist": orchestrator.WATCHLIST,
            })

        @bp.route("/agent/insights", methods=["GET"])
        async def insights():
            best = await orchestrator.learner.get_best_conditions(10)
            return jsonify({"best_conditions": best})

        return bp

    except ImportError:
        log.warning("Flask non disponible — blueprint non créé")
        return None

# ──────────────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ──────────────────────────────────────────────────────────────────────────────

async def main():
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    orchestrator = OrchestratorAgent()

    # Gestion arrêt propre
    import signal as sig_module

    def _shutdown(signum, frame):
        log.info("Signal reçu (%s) — arrêt en cours...", signum)
        asyncio.get_event_loop().stop()

    sig_module.signal(sig_module.SIGINT,  _shutdown)
    sig_module.signal(sig_module.SIGTERM, _shutdown)

    await orchestrator.start()


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║   KILLINGBOT — Stoic Multi-Agent System v1.0                      ║
║   Démarrage du système autonome de trading...                     ║
║                                                                    ║
║   Pour mode mock (sans broker) : BROKER=mock dans .env            ║
║   Pour OANDA démo : BROKER=oanda dans .env                        ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    asyncio.run(main())
