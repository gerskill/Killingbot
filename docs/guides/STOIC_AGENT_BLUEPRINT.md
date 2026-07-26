# 🏛️ STOIC LENS MULTI-AGENT SYSTEM — Blueprint

> **Killingbot × @StoicTA Framework × IA Adaptative**
> Version 1.0 | 2026-06-06

---

## Vue d'ensemble

Ce système est composé de **2 livrables** qui fonctionnent ensemble :

| Livrable | Fichier | Rôle |
|----------|---------|------|
| **Pine Script v6** | `pine_scripts/strategies/stoic_lens_strategy.pine` | Backtest + signaux TradingView + alertes JSON |
| **Multi-Agent Python** | `agents/stoic_multi_agent_system.py` | Trading autonome + apprentissage continu |

---

## Architecture : Les 7 Agents

```
                     ┌─────────────────────────────────────┐
                     │         ORCHESTRATEUR                │
                     │  Coordonne le cycle toutes les 15min │
                     └───────────────┬─────────────────────┘
                                     │
        ┌────────────────────────────┼─────────────────────────┐
        │                            │                          │
        ▼                            ▼                          ▼
┌──────────────┐           ┌──────────────────┐       ┌──────────────────┐
│ MARKET       │           │  MACRO NEWS      │       │  SETUP           │
│ ANALYST      │           │  AGENT           │       │  VALIDATOR       │
│              │           │                  │       │                  │
│ PDH/PDL/PDC  │           │ ForexFactory API │       │ 4 piliers Stoic  │
│ HCOM/LCOM    │           │ Block HIGH ±30min│       │ Score 0-4        │
│ SMA20/200    │           │                  │       │ Fib 61.8-78.6%   │
│ ATR14        │           └──────────────────┘       └──────────────────┘
└──────────────┘
                     ┌─────────────────────────────────────┐
                     │         LEARNING AGENT               │
                     │  Thompson Sampling — Beta(α,β)       │
                     │  Confiance par condition              │
                     └───────────────┬─────────────────────┘
                                     │
        ┌────────────────────────────┼─────────────────────────┐
        │                            │                          │
        ▼                            ▼                          ▼
┌──────────────┐           ┌──────────────────┐       ┌──────────────────┐
│ RISK         │           │  EXECUTION        │       │  SQLite DB       │
│ MANAGER      │           │  AGENT            │       │                  │
│              │           │                  │       │ trades           │
│ Max 1% / trade│          │ OANDA/Webhook/   │       │ learning_weights │
│ Max 3% / jour │          │ Mock             │       │ agent_memory     │
│ RR ≥ 1.5     │           │                  │       │ rejected_signals │
└──────────────┘           └──────────────────┘       └──────────────────┘
```

---

## Les 4 Piliers Stoic Lens (score 0–4)

| Pilier | Long | Short | Points |
|--------|------|-------|--------|
| **HCOM/LCOM** | Close journalier > Open (HCOM) | Close journalier < Open (LCOM) | 1 |
| **SMA20/200** | SMA20 > SMA200 (BULL) ou D_BULL | SMA20 < SMA200 (BEAR) ou D_BEAR | 1 |
| **Niveaux clés** | Prix proche PDL / PLOW | Prix proche PDH / PHOW | 1 |
| **Pattern** | B&R / SFP bullish / Zone Fib 61.8-78.6% | B&R / SFP bearish / Zone Fib 61.8-78.6% | 1 |

- **Score 4/4 = GOLDEN SBS** (setup premium)
- **Score 3/4 = B&R Standard** (setup valide)
- **Score ≤ 2 = ignoré**

---

## Fib Entry Zones (calcul)

```
Long Entry Zone :
  fib_618 = PDH - (PDH - PDL) × 0.618
  fib_786 = PDH - (PDH - PDL) × 0.786
  → Entrer entre fib_618 et fib_786

Short Entry Zone :
  fib_618 = PDL + (PDH - PDL) × 0.618
  fib_786 = PDL + (PDH - PDL) × 0.786
  → Entrer entre fib_618 et fib_786
```

---

## Thompson Sampling — Apprentissage

Le LearningAgent maintient une distribution **Beta(α,β)** pour chaque condition :

```
Conditions trackées :
  - "HCOM_BUY_GOLDEN_SBS"     → wins=15, losses=5  → confiance = 15/(15+5) = 75%
  - "EURUSD_BUY"              → wins=8,  losses=3  → confiance = 73%
  - "score_4_BUY"             → wins=22, losses=7  → confiance = 76%
  - "news_NONE_BUY"           → wins=30, losses=12 → confiance = 71%
  - "session_LONDON_BUY"      → wins=18, losses=6  → confiance = 75%
  - "dow_0_BUY"               → wins=10, losses=4  → confiance = 71%

Confiance finale = √(p1 × p2 × ... × pn)  (moyenne géométrique)
Filtre : si confiance < 35% ET > 20 trades → setup rejeté
```

---

## Pipeline de décision (1 cycle = 15 min)

```
Pour chaque paire de la watchlist :

1. MarketAnalyst.analyze(symbol)
   → PDH, PDL, PDC, PDO, SMA20/200, ATR14, HCOM/LCOM

2. MacroNewsAgent.should_block_trade(symbol)
   → Si HIGH IMPACT ±30min → BLOQUÉ

3. SetupValidatorAgent.validate(ctx, direction)
   → Calcule score 0-4
   → Si score < 3 → REJETÉ

4. LearningAgent.enrich_setup(setup)
   → Calcule confiance Thompson
   → Si confiance < 35% (>20 trades) → REJETÉ

5. RiskManagerAgent.approve(setup)
   → Vérifie drawdown journalier (max 3%)
   → Vérifie trades ouverts (max 3)
   → Vérifie RR ≥ 1.5
   → Calcule qty = risk_usd / stop_dist

6. ExecutionAgent.execute(setup, pos_info)
   → Envoie ordre OANDA/Webhook/Mock
   → Enregistre en DB

7. [Quand trade fermé] LearningAgent.learn_from_trade(result)
   → Met à jour Beta(α,β) pour toutes les conditions
```

---

## Installation & Démarrage

### 1. Dépendances

```bash
pip install anthropic aiohttp aiosqlite python-dotenv websockets schedule
```

### 2. Configuration `.env`

```bash
# Copier et remplir
cp agents/.env.example agents/.env

ANTHROPIC_API_KEY=sk-ant-...
BROKER=mock                    # mock | oanda | webhook
BROKER_API_KEY=...
BROKER_ACCOUNT_ID=...
WEBHOOK_URL=http://localhost:5001/webhook
ACCOUNT_EQUITY=10000
MAX_RISK_PCT=1.0
MAX_DAILY_LOSS=3.0
SCAN_INTERVAL_MIN=15
WATCHLIST=EURUSD,GBPUSD,USDJPY,USDCAD,XAUUSD
```

### 3. Lancer le système

```bash
# Mode mock (simulation)
BROKER=mock python3 agents/stoic_multi_agent_system.py

# Mode OANDA démo
BROKER=oanda python3 agents/stoic_multi_agent_system.py

# Intégré au webhook_server.py existant
python3 webhook_server.py   # ajouter blueprint (voir code)
```

### 4. Pine Script → TradingView

1. Ouvrir TradingView
2. Pine Editor → New → Coller `pine_scripts/strategies/stoic_lens_strategy.pine`
3. Save + Add to chart
4. Configurer alert avec message = `{{strategy.order.comment}}` + webhook URL

---

## Flow Webhook (TradingView → Agents)

```
TradingView (Pine alert)
    │
    │  POST {"action":"BUY","symbol":"EURUSD","score":4,...}
    ▼
webhook_server.py (port 5001)
    │
    │  Dispatch
    ├──→ ExecutionAgent (si action BUY/SELL → ordre broker)
    └──→ LearningAgent  (si action CLOSE   → apprentissage)
```

---

## Adaptation quotidienne

Le système s'adapte automatiquement via :

1. **Thompson Sampling** — Confiance par condition mise à jour après chaque trade
2. **Filtres dynamiques** — Min. confiance appliqué après 20 trades
3. **Insights Claude** — Génère des recommandations tous les 10 cycles
4. **Mémoire persistante** — SQLite `data/stoic_agents.db` survit aux redémarrages
5. **News filter** — Calendrier ForexFactory rechargé toutes les heures

---

## Fichiers du système

```
Killingbot/
├── pine_scripts/strategies/
│   └── stoic_lens_strategy.pine      ← Strategy TradingView (7 couches)
├── agents/
│   ├── stoic_multi_agent_system.py   ← 7 agents Python autonomes
│   ├── stoic_agent_config.json       ← Configuration complète
│   └── .env                          ← Secrets (à créer)
├── data/
│   └── stoic_agents.db               ← SQLite (créé au démarrage)
├── logs/
│   └── stoic_agents.log              ← Logs (créé au démarrage)
└── docs/guides/
    └── STOIC_AGENT_BLUEPRINT.md      ← Ce fichier
```
