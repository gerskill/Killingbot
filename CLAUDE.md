# Killingbot — Hybrid AI Trading System

TraderMorin × aiedge | Claude Trading Architect

---

## 🚀 QUICK START (2026-06-03)

**TradingView Desktop MCP** → `~/Library/Application Support/Claude/claude_desktop_config.json`

- Wrapper `~/tradingview-mcp/start-with-tv.sh` → auto-launch TV debug (port 9222) on Claude start
- CDP error: `bash ~/tradingview-mcp/scripts/launch_tv_debug_mac.sh`
- Health: `mcp__tradingview-desktop__tv_health_check`

**⭐ BEST STRATEGY: `pp_st_btc_4h_final.pine`** — ✅ CONFIRMÉ en direct (Strategy Tester TradingView, 2026-07-18)

- PP SuperTrend (prd=2, Factor=5, ATR=14) + EMA200 + ADX≥20
- BTC/USDT 4H (17 août 2017 → 18 juil. 2026, données réelles) : **P&L +2947.56% | DD 24.53% | PF 2.52 | WR 33.90% (20/59) | 59 trades** — correspondance quasi parfaite avec l'annonce d'origine. Sharpe réel : 0.248 (modeste — performance concentrée sur peu de gros trades, pas de régularité élevée). CAGR 46.66%.
- Beats all TradingView "My Scripts"

> ℹ️ **Contexte (2026-07-18)** : `kb_15m_strategy.pine`, annoncé dans son propre commentaire
> à +7.9%/mois, PF élevé, WR 67%, Sharpe 7.57, s'est révélé **perdant** une fois compilé et
> testé en direct : P&L −8.76%, PF 0.465, WR 35.23%, Sharpe −1.243, 579 trades (pas 414).
> **Fichier supprimé du projet le 2026-07-18** (décision : garder uniquement la stratégie
> BTC 4H confirmée). `pp_st_btc_4h_final.pine`, lui, a été re-testé dans la foulée avec la
> même méthode et **confirme intégralement** ses chiffres annoncés — voir ci-dessus, et a
> aussi été confirmé sur BITSTAMP:BTCUSD (+8058.68%, DD 18.77%, PF 2.635, WR 28.40%,
> 81 trades — même stratégie, données d'exchange différentes, Sharpe tout aussi modeste
> ~0.28 dans les deux cas). Conclusion : ne jamais supposer qu'un chiffre de performance
> dans un commentaire de fichier est correct — même au sein du même projet, deux scripts
> peuvent être l'un vrai et l'autre faux. Seul un test live dans le Strategy Tester fait foi.
> Détail du sweep KB_* invalidé (hors KB_15m, supprimé) : `vault/BEST_STRATEGIES.md`.

---

## 🗺️ KEY FILES MAP

| Fichier / Dossier | Rôle |
| --- | --- |
| `pp_st_btc_4h_final.pine` | ⭐ Meilleure stratégie — PP-ST+EMA200+ADX BTC 4H |
| `pp_st_btc_4h.pine` | Version sans ADX (backup) |
| `PP_ST_Indicator.pine` | SuperTrend dual avancé (production-ready) |
| `PINE_ERRORS.md` | ⚠️ OBLIGATOIRE — Checklist erreurs Pine v6 |
| `vault/BEST_STRATEGIES.md` | 🏆 Top 10 stratégies backtestées |
| `vault/AGENT_LOG.md` | Log sessions exploration |
| `vault/memory.json` | Mémoire persistante agents |
| `vault/strategies/` | Fiches variantes KB_* |
| `backtest/rapport_claude.txt` | Rapport hebdo perf (semaine en cours) |
| `backtest/ray_magenta_report.md` | Rapport backtest Ray Magenta |
| `docs/guides/SPRING_INDICATOR_GUIDE.md` | Guide indicateur Spring (Wyckoff) |
| `docs/guides/RESEARCH.md` | Notes recherche — design agent trading |
| `docs/guides/performance-analyst.md` | Agent analyste performance |
| `docs/strategies/` | Exemples setups (XAUUSD, etc.) |
| `pine_scripts/` | Bibliothèque indicateurs + stratégies |
| `agents/` | Orchestrateur multi-agents Python |
| `scanner/killingbot_scanner.py` | Scanner multi-assets |
| `webhook_server.py` | Serveur Flask — alertes TradingView |
| `webhook_config.json` | Config JSON webhooks |
| `GUIDE_DEMARRAGE.md` | Guide démarrage complet |
| `watchlist.json` | Assets surveillés |

---

## ⚠️ PINE SCRIPT v6 — KNOWN ERRORS (MANDATORY)

> **RULE**: Before delivering Pine code, scan against this list.

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

**Exception:** Variables sans type annotation peuvent break lines si chaque ligne finit par `:`.

```pine
// ✅ ACCEPTÉ (pas de type explicite)
fill_col = range_hard ? color.red :
           is_range   ? color.purple :
           color.gray
```

### ✅ SAFE Patterns — Pine v6

| Pattern | OK? | Notes |
| --- | --- | --- |
| `bool x = cond and\n cond2` | ✅ | `and` fin ligne = continuation valide |
| `bool x = cond or\n cond2` | ✅ | `or` fin ligne = continuation valide |
| `x = ternaire\n : suite` | ✅ si non typé | Variable sans annotation |
| `float x = ternaire\n : suite` | ❌ | Doit tenir une ligne |
| `ta.atr()`, `ta.ema()`, etc. | ✅ | Appels standard |
| `request.security()` avec tuple | ✅ | `[a, b] = request.security(...)` |
| Multi-ligne dans `if/else` | ✅ | Pas de restriction blocs |

### 📋 Pre-delivery Checklist Pine

```
[ ] Aucune déclaration typée (float/int/bool/string/color) ne finit par ":" en fin de ligne
[ ] Aucun ternaire avec type explicite ne s'étend sur plusieurs lignes
[ ] Toutes fonctions appelées avec bons types d'arguments
[ ] strategy.exit() référencent strategy.entry() existants
[ ] Pas de variable réutilisée avec "=" au lieu de ":=" après déclaration
[ ] Plots non-affichés utilisent color=na (pas de couleur visible)
```

---

## 🏆 TOP 10 BACKTESTED STRATEGIES (2026-05-14)

> ⚠️ **INVALIDÉ — 2026-07-18** : issu du sweep automatique `agents/strategy_explorer.py`
> (35 variantes), jamais confirmé en direct dans le Strategy Tester TradingView. Le rang 4
> (`KB_15m`) a été recompilé et testé en direct le 2026-07-18 : résultat réel P&L −8.76%,
> DD 8.98%, **PF 0.465 (perdant)**, WR 35.23%, Sharpe −1.243, 579 trades — à l'opposé complet
> de la ligne ci-dessous. Les 9 autres lignes n'ont pas été re-testées et doivent être
> considérées invalides jusqu'à vérification individuelle. Détail : `vault/BEST_STRATEGIES.md`.

| Rang | Stratégie | %/mois (⚠️ non vérifié) | WR | Trades | DD | Sharpe |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | KB_LOOSE_RR2.5_RR3.0 | 8.0% | 66% | 231 | -12.2% | 7.06 |
| 2 | KB_1h | 7.9% | 67% | 420 | -6.1% | 7.51 |
| 3 | KB_RR4 | 7.9% | 65% | 214 | -12.2% | 6.43 |
| 4 | KB_15m | 7.9% | 67% | 414 | -5.7% | 7.57 |
| 5 | KB_RR5 | 7.8% | 62% | 208 | -14.6% | 5.51 |
| 6 | KB_LOOSE_RR2.5_RR3.0_RSI | 7.8% | 68% | 215 | -11.5% | 7.45 |
| 7 | KB_LOOSE_RR2.5_RSI | 7.5% | 68% | 225 | -10.4% | 7.65 |
| 8 | KB_LOOSE_RR2.5 | 7.5% | 66% | 241 | -11.8% | 7.04 |
| 9 | KB_LOOSE | 7.2% | 69% | 246 | -11.5% | 7.80 |
| 10 | KB_LOOSE_RSI | 7.0% | 70% | 230 | -10.4% | 8.16 |

**Common params top:**

- EMA fast/slow: 7/21
- Kijun: 26
- ATR: 14, mult 1.5
- EMA min separation: 0.15%
- Cooldown: 3 bars
- ATR min: 0.3%

**⭐ Best overall:** `KB_LOOSE_RR2.5_RR3.0` — 8.02%/mois, WR 66%, Sharpe 7.06
**⭐ Best Sharpe:** `KB_LOOSE_RSI` — Sharpe 8.16
**⭐ Lowest DD:** `KB_15m` — -5.7%

---

## 📊 WEEKLY PERFORMANCE REPORT (07–11 April 2026)

Account: $25,000 | Risk: 1.0%/trade

| Métrique | Valeur |
| --- | --- |
| Trades | 27 |
| Win Rate | 63% (17W / 10L) |
| Profit Factor | 3.01 |
| Net P&L | +$496.50 |
| Expectancy/trade | +$18.39 |
| Max consec. losses | 2 |

**By setup:** ORB = 83% WR (best), VWAP rejection = 100%, momentum = 43% (avoid)
**By session:** Open 09:30-10:00 = 71% WR (best slot)

---

## 📊 BACKTEST RESULTS — TESTED (2026-06-03)

### ⭐ Best: PP-ST + EMA200 + ADX (BTC 4H)

| Stratégie | Retour | DD | PF | Trades |
| --- | --- | --- | --- | --- |
| **PP-ST + EMA200 + ADX≥20** | **+2947%** | **24.53%** | **2.52** | 59 |
| PP-ST + EMA200 | +2039% | 26.15% | 2.09 | 71 |
| WMS Score v2.1 (multi-indicateurs) | -53.77% | 70% | 0.22 | 93 |

**Key rule:** Fixed TP = bad on BTC. Close on PP-ST reversal = capture +200-400%.

### Best assets (simple EMA×Kijun trailing)

| Asset | TF | %/mois | DD | PF |
| --- | --- | --- | --- | --- |
| SOL/USDT Daily (2023+) | Daily | 7.45% | 21.82% | 1.984 |
| NVDA 1H (2023+) | 1H | 2.82% | 12.06% | 1.832 |

### Scripts TV "My Scripts" analysés

- `PP-ST × QT [v3.0]` — indicator (pas strategy), filtres ICT avancés (SSMT + 90m cycles)
- `PP-ST x QT Strategy [v2.1]` — weighted score strategy, mauvais sur BTC
- `ST Sandwich Backtest` — dual ST MTF, indicator only
- `SuperTrend 4.11.2 Strategy (Cassure)` — simple L+S reversal, no macro filter

**→ Aucun ne bat `pp_st_btc_4h_final.pine`**

### Priorités prochaine session :

1. PP-ST + EMA200 + ADX sur **XAUUSD 4H** (Gold)
2. PP-ST + EMA200 + ADX sur **SOL/USDT Daily**
3. Add **SSMT** filter (ETH/BTC correlation from PP×QT v3.0)
4. Add **webhook JSON alerts** live trading

---

## 🌀 SPRING CONFLUENCE INDICATOR

Indicator **Wyckoff** — détecte springs (institutional stop hunts) sur 5 TFs simultanées.

**Confluence score:**

- `+5` = All TFs bullish 🟢🟢🟢🟢🟢
- `+3/+4` = Strong uptrend
- `0` = Neutral — avoid
- `-3/-4` = Strong downtrend
- `-5` = All TFs bearish 🔴🔴🔴🔴🔴

**Setups:**

- **Setup A (High Prob)**: 1D🟢 + 4H🟢 + 1H Spring UP → 5m entry
- **Setup B (Scalp)**: counter-trend, taille réduite, TP rapide
- **Setup C**: Confluence -5 → sell ou wait only

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

- `orchestrator.py` — Coordinateur session exploration
- `memory_agent.py` — Mémoire persistante + suggestions
- `strategy_explorer.py` — Auto-test variations KB_*

**Sessions completed:** 35 variants | Best: KB_LOOSE_RR2.5_RR3.0 = 8.0%/mois

---

## 🔧 MANDATORY FLOW ORDER (Pine Script)

1. **LAYER 1** — Market Outlook: bias global, MTF structure
2. **LAYER 2** — Confluences: momentum, volume, sentiment
3. **LAYER 3** — Structure & Liquidity: zones institutionnelles, pivots
4. **LAYER 4** — Range Filter & Robustness: detection consolidation
5. **LAYER 5** — Setup Quality: scoring, hiérarchie signaux
6. **LAYER 6** — Risk Management: SL/TP dynamique, RR, trailing
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

**IMPORTANT: Projet a knowledge graph. TOUJOURS utiliser code-review-graph MCP AVANT Grep/Glob/Read.**

| Tool | Use when |
| --- | --- |
| `detect_changes` | Review code changes — analyse risk-scored |
| `get_review_context` | Source snippets review — token-efficient |
| `get_impact_radius` | Blast radius d'un change |
| `query_graph` | Trace callers, callees, imports, tests, deps |
| `semantic_search_nodes` | Trouve fonctions/classes par nom ou keyword |
| `get_architecture_overview` | Structure haut niveau codebase |
