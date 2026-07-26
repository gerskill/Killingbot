# Killingbot — Hybrid AI Trading System

## TraderMorin × aiedge | Claude Trading Architect

---

## 🚀 QUICK START (UPDATED 2026-06-03)

**TradingView Desktop MCP** → configured in `~/Library/Application Support/Claude/claude_desktop_config.json`

- Wrapper `~/tradingview-mcp/start-with-tv.sh` launches TradingView debug mode (port 9222) **auto** on Claude start
- CDP error: `bash ~/tradingview-mcp/scripts/launch_tv_debug_mac.sh`
- Health check: `mcp__tradingview-desktop__tv_health_check`

**⭐ BEST CURRENT STRATEGY: `pp_st_btc_4h_final.pine`**

- PP SuperTrend (prd=2, Factor=5, ATR=14) + EMA200 + ADX≥20
- Results BTC/USDT 4H (2020-2026): **+2947% | DD 24.53% | PF 2.52 | 59 trades**
- Beats all scripts in TradingView "My Scripts"

---

## 🗺️ KEY FILES MAP


| Fichier / Dossier                       | Rôle                                                |
| --------------------------------------- | --------------------------------------------------- |
| `pp_st_btc_4h_final.pine`               | ⭐ **Meilleure stratégie** — PP-ST+EMA200+ADX BTC 4H |
| `pp_st_btc_4h.pine`                     | Version sans ADX (backup)                           |
| `PP_ST_Indicator.pine`                  | SuperTrend dual avancé (production-ready)           |
| `PINE_ERRORS.md`                        | ⚠️ **OBLIGATOIRE** — Checklist erreurs Pine v6      |
| `vault/BEST_STRATEGIES.md`              | 🏆 Top 10 stratégies backtestées                    |
| `vault/AGENT_LOG.md`                    | Log complet des sessions d'exploration              |
| `vault/memory.json`                     | Mémoire persistante des agents                      |
| `vault/strategies/`                     | Fiches détaillées de chaque variante KB_*           |
| `backtest/rapport_claude.txt`           | Rapport hebdo performance (semaine en cours)        |
| `backtest/ray_magenta_report.md`        | Rapport backtest Ray Magenta                        |
| `docs/guides/SPRING_INDICATOR_GUIDE.md` | Guide indicateur Spring (Wyckoff)                   |
| `docs/guides/RESEARCH.md`               | Notes de recherche — design agent trading           |
| `docs/guides/performance-analyst.md`    | Agent analyste performance                          |
| `docs/strategies/`                      | Exemples de setups (XAUUSD, etc.)                   |
| `pine_scripts/`                         | Bibliothèque d'indicateurs et stratégies            |
| `agents/`                               | Orchestrateur multi-agents Python                   |
| `scanner/killingbot_scanner.py`         | Scanner multi-assets                                |
| `webhook_server.py`                     | Serveur Flask — alertes TradingView                 |
| `webhook_config.json`                   | Config JSON webhooks                                |
| `GUIDE_DEMARRAGE.md`                    | Guide de démarrage complet                          |
| `watchlist.json`                        | Liste des assets surveillés                         |


---

## ⚠️ PINE SCRIPT v6 — KNOWN ERRORS (MANDATORY)

> **RULE**: Before delivering Pine Script code, scan against this list.

### ❌ ERROR #1 — Multi-line ternary with typed declaration (CE10156)

**Symptom:** `Syntax error at input "end of line without line continuation" (CE10156)`

**FORBIDDEN pattern:**

```pine
// ❌ INTERDIT
float pnl_pct = condition1 ? valeur1 :
                condition2 ? valeur2 : na

// ❌ INTERDIT
string sig_txt = cond_a ? "A" :
                 cond_b ? "B" : "C"

// ❌ INTERDIT
color sig_col = cond ? color.lime :
                color.red
```

**Rule:** Typed declaration with ternary → **single line**.

```pine
// ✅ CORRECT
float pnl_pct = condition1 ? valeur1 : condition2 ? valeur2 : na
string sig_txt = cond_a ? "A" : cond_b ? "B" : "C"
color sig_col = cond ? color.lime : color.red
```

**Exception:** Variables without type annotation can break across lines if each line ends with `:`.

```pine
// ✅ ACCEPTÉ (pas de type explicite)
fill_col = range_hard ? color.red :
           is_range   ? color.purple :
           color.gray
```

### ✅ SAFE Patterns — Pine Script v6


| Pattern                         | OK ?          | Notes                                       |
| ------------------------------- | ------------- | ------------------------------------------- |
| `bool x = cond and\n cond2`     | ✅             | `and` en fin de ligne = continuation valide |
| `bool x = cond or\n cond2`      | ✅             | `or` en fin de ligne = continuation valide  |
| `x = ternaire\n : suite`        | ✅ si non typé | Variable sans annotation de type            |
| `float x = ternaire\n : suite`  | ❌             | Doit tenir sur une ligne                    |
| `ta.atr()`, `ta.ema()`, etc.    | ✅             | Appels standard                             |
| `request.security()` avec tuple | ✅             | `[a, b] = request.security(...)`            |
| Multi-ligne dans `if/else`      | ✅             | Pas de restriction sur les blocs            |


### 📋 Pre-delivery Checklist Pine Script

```
[ ] Aucune déclaration typée (float/int/bool/string/color) ne se termine par ":" en fin de ligne
[ ] Aucun ternaire avec type explicite ne s'étend sur plusieurs lignes
[ ] Toutes les fonctions sont appelées avec les bons types d'arguments
[ ] Les strategy.exit() référencent des strategy.entry() existants
[ ] Pas de variable réutilisée avec "=" au lieu de ":=" après déclaration
[ ] Les plots non-affichés utilisent color=na (pas de couleur visible)
```

---

## 🏆 TOP 10 BACKTESTED STRATEGIES (updated 2026-05-14)


| Rang | Stratégie                | %/mois | WR  | Trades | Drawdown | Sharpe |
| ---- | ------------------------ | ------ | --- | ------ | -------- | ------ |
| 1    | KB_LOOSE_RR2.5_RR3.0     | 8.0%   | 66% | 231    | -12.2%   | 7.06   |
| 2    | KB_1h                    | 7.9%   | 67% | 420    | -6.1%    | 7.51   |
| 3    | KB_RR4                   | 7.9%   | 65% | 214    | -12.2%   | 6.43   |
| 4    | KB_15m                   | 7.9%   | 67% | 414    | -5.7%    | 7.57   |
| 5    | KB_RR5                   | 7.8%   | 62% | 208    | -14.6%   | 5.51   |
| 6    | KB_LOOSE_RR2.5_RR3.0_RSI | 7.8%   | 68% | 215    | -11.5%   | 7.45   |
| 7    | KB_LOOSE_RR2.5_RSI       | 7.5%   | 68% | 225    | -10.4%   | 7.65   |
| 8    | KB_LOOSE_RR2.5           | 7.5%   | 66% | 241    | -11.8%   | 7.04   |
| 9    | KB_LOOSE                 | 7.2%   | 69% | 246    | -11.5%   | 7.80   |
| 10   | KB_LOOSE_RSI             | 7.0%   | 70% | 230    | -10.4%   | 8.16   |


**Common params top strategies:**

- EMA fast/slow: 7/21
- Kijun: 26
- ATR: 14, mult 1.5
- EMA min separation: 0.15%
- Cooldown: 3 bars
- ATR min: 0.3%

**⭐ Best overall:** `KB_LOOSE_RR2.5_RR3.0` — 8.02%/month, WR 66%, Sharpe 7.06
**⭐ Best Sharpe:** `KB_LOOSE_RSI` — Sharpe 8.16
**⭐ Lowest DD:** `KB_15m` — -5.7%

---

## 📊 WEEKLY PERFORMANCE REPORT (07–11 April 2026)

Account: $25,000 | Risk: 1.0%/trade


| Métrique           | Valeur          |
| ------------------ | --------------- |
| Trades             | 27              |
| Win Rate           | 63% (17W / 10L) |
| Profit Factor      | 3.01            |
| Net P&L            | +$496.50        |
| Expectancy/trade   | +$18.39         |
| Max consec. losses | 2               |


**By setup:** ORB = 83% WR (best), VWAP rejection = 100%, momentum = 43% (avoid)
**By session:** Open 09:30-10:00 = 71% WR (best slot)

---

## 📊 BACKTEST RESULTS — TESTED STRATEGIES (2026-06-03)

### ⭐ Best strategy: PP-ST + EMA200 + ADX (BTC 4H)


| Stratégie                          | Retour     | DD         | PF       | Trades |
| ---------------------------------- | ---------- | ---------- | -------- | ------ |
| **PP-ST + EMA200 + ADX≥20**        | **+2947%** | **24.53%** | **2.52** | 59     |
| PP-ST + EMA200                     | +2039%     | 26.15%     | 2.09     | 71     |
| WMS Score v2.1 (multi-indicateurs) | -53.77%    | 70%        | 0.22     | 93     |


**Key rule:** Fixed TP = bad on BTC. Close on PP-ST reversal = captures +200-400%.

### Best assets found (simple EMA×Kijun trailing strategy)


| Asset                  | TF    | %/mois | DD     | PF    |
| ---------------------- | ----- | ------ | ------ | ----- |
| SOL/USDT Daily (2023+) | Daily | 7.45%  | 21.82% | 1.984 |
| NVDA 1H (2023+)        | 1H    | 2.82%  | 12.06% | 1.832 |


### TradingView scripts analyzed in "My Scripts"

- `PP-ST × QT [v3.0]` — indicator (not strategy), advanced ICT filters (SSMT + 90m cycles)
- `PP-ST x QT Strategy [v2.1]` — weighted score strategy, tested and bad on BTC
- `ST Sandwich Backtest` — dual ST MTF, indicator only
- `SuperTrend 4.11.2 Strategy (Cassure)` — simple L+S reversal, no macro filter

**→ None beat `pp_st_btc_4h_final.pine`**

### Priority tests next session:

1. PP-ST + EMA200 + ADX on **XAUUSD 4H** (Gold)
2. PP-ST + EMA200 + ADX on **SOL/USDT Daily**
3. Add **SSMT** filter (ETH/BTC correlation from PP×QT v3.0)
4. Add **webhook JSON alerts** for live trading

---

## 🌀 SPRING CONFLUENCE INDICATOR

Indicator based on **Wyckoff method** — detects springs (institutional stop hunts) across 5 TFs simultaneously.

**Confluence score:**

- `+5` = All TFs bullish 🟢🟢🟢🟢🟢
- `+3/+4` = Strong uptrend
- `0` = Neutral — avoid
- `-3/-4` = Strong downtrend
- `-5` = All TFs bearish 🔴🔴🔴🔴🔴

**Setups:**

- **Setup A (High Prob)**: 1D🟢 + 4H🟢 + 1H Spring UP → 5m entry
- **Setup B (Scalp)**: counter-trend, reduced size, quick TP
- **Setup C**: Confluence -5 → sell or wait only

**File:** `pine_scripts/indicators/spring_confluence_indicator.pine`
**Guide:** `docs/guides/SPRING_INDICATOR_GUIDE.md`

---

## 🤖 AGENT ARCHITECTURE

```
webhook_server.py (port 5001)
  └── signal_agent → 5-step TraderMorin validation
        ├── REJECTED → log + reason
        └── ACCEPTED
              ├── journal_agent → trades.csv + report
              └── [weekly] performance_agent → pine_updater
```

**Python agents (`agents/`):**

- `orchestrator.py` — Exploration session coordinator
- `memory_agent.py` — Persistent memory + suggestions
- `strategy_explorer.py` — Auto-testing KB_* variations

**Completed sessions:** 35 variants tested | Best: KB_LOOSE_RR2.5_RR3.0 = 8.0%/month

---

## 🔧 MANDATORY FLOW ORDER (Pine Script)

1. **LAYER 1** — Market Outlook: global bias, MTF structure
2. **LAYER 2** — Confluences: momentum, volume, sentiment
3. **LAYER 3** — Structure & Liquidity: institutional zones, pivots
4. **LAYER 4** — Range Filter & Robustness: consolidation detection
5. **LAYER 5** — Setup Quality: scoring, signal hierarchy
6. **LAYER 6** — Risk Management: dynamic SL/TP, RR, trailing
7. **LAYER 7** — Execution, Visualization & Alerts: dashboard + webhooks

---

## 🚀 QUICK START

```bash
# 1. TradingView en mode debug
bash scripts/launch_tv_debug_mac.sh

# 2. Serveur MCP TradingView
cd ~/tradingview-mcp && node src/server.js

# 3. Serveur webhook
python3 webhook_server.py

# 4. Exposer webhook
ngrok http 5001
```

---

## MCP Tools: code-review-graph

**IMPORTANT: Project has knowledge graph. ALWAYS use code-review-graph MCP tools BEFORE Grep/Glob/Read to explore codebase.**


| Tool                        | Use when                                               |
| --------------------------- | ------------------------------------------------------ |
| `detect_changes`            | Reviewing code changes — gives risk-scored analysis    |
| `get_review_context`        | Need source snippets for review — token-efficient      |
| `get_impact_radius`         | Understanding blast radius of a change                 |
| `query_graph`               | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes`     | Finding functions/classes by name or keyword           |
| `get_architecture_overview` | Understanding high-level codebase structure            |