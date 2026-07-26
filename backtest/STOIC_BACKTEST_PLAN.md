# Stoic Confluence — Plan de Backtest Multi-Marchés / Multi-TF

> **Indicateur source** : `pine_scripts/indicators/stoic_confluence_indicator.pine`
> **Date** : 2026-06-07
> **Méthodologie** : Wrapper strategy minimal autour de l'indicateur — entrée sur score ≥ 3, SL = ATR×1.5, TP = 2×SL (R:R 1:2).

---

## 🎯 OBJECTIF

L'indicateur Stoic Confluence est conçu pour l'analyse manuelle (4 piliers, niveaux clés). Pour mesurer son **edge statistique**, on l'enveloppe dans une stratégie de test minimale :

- **Entrée** : sur barre confirmée, score ≥ 3 dans une direction (LONG ou SHORT)
- **Stop** : ATR(14) × 1.5 du prix d'entrée
- **Target** : 2× le stop (R:R fixe 1:2)
- **Risque** : 1% du capital par trade
- **Cooldown** : 5 barres entre trades sur même symbole/direction

Cette stratégie de test **n'est pas** la stratégie finale — c'est un instrument de mesure. La stratégie réelle laissera le trader exécuter manuellement.

---

## 📊 MATRICE COMPLÈTE (cible)

### Marchés — 5 plus gros par catégorie / zone

#### 🇺🇸 USA
| Catégorie | Top 5 |
|-----------|-------|
| **Indices** | SPX500, NAS100, US30, RUT, VIX |
| **Tech mega-caps** | NVDA, AAPL, MSFT, GOOGL, AMZN |
| **Finance** | JPM, BAC, GS, MS, BRK.B |

#### 🇪🇺 Europe
| Catégorie | Top 5 |
|-----------|-------|
| **Indices** | DAX (DEU40), CAC40, FTSE100, EURO STOXX 50, AEX |
| **Large caps** | LVMH, ASML, SAP, NESN (Nestlé), NOVO (Novo Nordisk) |

#### 🇨🇳 Chine / Asie
| Catégorie | Top 5 |
|-----------|-------|
| **Indices** | HSI (Hong Kong), SSEC (Shanghai), SZI (Shenzhen), CSI300, NIKKEI |
| **Large caps** | BABA, TCEHY (Tencent), PDD, JD, BIDU |

#### 🌐 Cross-asset
| Catégorie | Top 5 |
|-----------|-------|
| **Crypto** | BTCUSD, ETHUSD, SOLUSD, BNBUSD, XRPUSD |
| **Forex** | EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD |
| **Metals** | XAUUSD, XAGUSD, XPTUSD, COPPER, ALUMINIUM |

### Timeframes — 7 niveaux
`1m` · `5m` · `15m` · `1h` · `4h` · `1D` · `1W`

### Volume total potentiel
**~45 symboles × 7 TFs = 315 backtests** — à étaler sur plusieurs sessions.

---

## 🏃 PHASAGE RÉALISTE (sessions Claude)

> **Pourquoi phaser** : un backtest via TradingView MCP prend ~30-60s (changement symbole + TF + lecture résultats). 315 backtests = ~3-5 heures de calls MCP en continu. Mieux vaut commencer petit, valider la méthodologie, puis scaler.

### 🟢 Phase 1 — Baseline & validation (cette session ou la suivante)

**12 backtests** sur les marchés à plus forte conviction :

| Marché   | TFs prioritaires |
|----------|------------------|
| BTCUSD   | 4H, 1D, 1W       |
| XAUUSD   | 4H, 1D           |
| NAS100   | 1H, 4H, 1D       |
| SPX500   | 4H, 1D           |
| ETHUSD   | 4H, 1D           |

**Objectif** : valider que la stratégie wrapper produit des stats cohérentes (PF > 1.3, DD < 25%) sur les marchés où Stoic Lens a historiquement de l'edge.

### 🟡 Phase 2 — Extension intraday (session ultérieure)

**~50 backtests** : ajouter 5m, 15m, 1h sur tous les marchés Phase 1 + EURUSD, GBPUSD, USDJPY.

**Objectif** : voir si l'edge tient sur les TFs courts (Stoic Lens est conçu pour HTF — risque de bruit en intraday).

### 🟠 Phase 3 — Matrice large (sessions ultérieures)

**~250 backtests** : tous les marchés × tous les TFs.

**Objectif** : carte de chaleur complète edge par couple (marché, TF). Identifier les "death zones" (configs où ne JAMAIS utiliser Stoic) et les "sweet spots".

---

## 📋 TEMPLATE DE COLLECTE

Pour chaque backtest, enregistrer :

```json
{
  "symbol": "BTCUSD",
  "tf": "4H",
  "period": "2020-01-01 → 2026-06-07",
  "trades": 0,
  "winRate": 0,
  "profitFactor": 0,
  "netReturn": 0,
  "maxDD": 0,
  "sharpe": 0,
  "avgTradeR": 0,
  "longTrades": 0,
  "shortTrades": 0,
  "longWR": 0,
  "shortWR": 0,
  "notes": ""
}
```

**Destination** : `backtest/results/stoic_<symbol>_<tf>.json`
**Agrégation** : `backtest/STOIC_RESULTS_MATRIX.md` (mise à jour automatique).

---

## 🔧 WORKFLOW MCP (quand TV Desktop connecté)

```
1. tv_health_check                              → vérifier CDP
2. chart_set_symbol(symbol)                     → changer ticker
3. chart_set_timeframe(timeframe)               → changer TF
4. chart_manage_indicator("Stoic Confluence")   → ajouter indicateur
5. Lancer Strategy Tester (manuel ou via UI)    → backtest
6. data_get_strategy_results                    → lire stats
7. capture_screenshot("strategy_tester")        → archive visuelle
8. Persister JSON dans backtest/results/
9. Loop
```

Une `batch_run` (tool MCP) peut paralléliser sur plusieurs symboles d'un coup.

---

## ⚠️ RISQUES MÉTHODOLOGIQUES

1. **Survivor bias** — backtests sur HCOM/LCOM utilisent les closes *passés* connus aujourd'hui, mais en live le HCOM du mois courant évolue dynamiquement. L'indicateur Pine v6 le gère correctement (recalcul intra-mois), à vérifier.
2. **Lookahead bias** — `request.security` avec `lookahead=barmerge.lookahead_off` (déjà configuré) prévient cela.
3. **Optimization overfit** — ne PAS tuner les paramètres P3/P4 par backtest. Garder les défauts du protocole Stoic.
4. **R:R fixe 1:2** — sous-estime probablement le potentiel. Tester aussi avec trailing stop (T1 sécurisé 50% à 1:2, runner à 1:3+).
5. **Frais & slippage** — sur 1m/5m, les frais bouffent l'edge. Toujours inclure commission Pine (`commission_value=0.05%` pour crypto, `0.025%` pour FX).

---

## 🚀 LANCEMENT RECOMMANDÉ

**Étape 1** : valider que TradingView Desktop tourne avec CDP enabled :
```bash
bash ~/tradingview-mcp/scripts/launch_tv_debug_mac.sh
```

**Étape 2** : injecter l'indicateur + créer un wrapper strategy minimal (10-15 lignes Pine de plus).

**Étape 3** : lancer Phase 1 (12 backtests) — me redemander dans une nouvelle session de Claude avec le bridge bien connecté.

---

> **Principe stoïcien** : *"On juge la DÉCISION, pas l'outcome."* Un backtest qui valide la méthodologie a plus de valeur qu'un résultat impressionnant sur un seul marché.
