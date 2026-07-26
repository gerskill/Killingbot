# 🏆 KB_HYBRID_V1 — PP-ST + EMA200 + ADX + Stoic Boost

> **Fichier** : `pine_scripts/strategies/killingbot_hybrid_v1.pine`
> **Backtest live** : `backtest/results/kb_hybrid_v1_BTCUSD_4H.json`
> **Date** : 2026-06-07

---

## 🎯 PERFORMANCE — BTC/USD 4H (Coinbase, 2017-2026, 9.1 ans)

| Métrique | Valeur | Objectif | Status |
|---|---|---|---|
| **Net P&L** | **+1 416.99%** | — | ⭐⭐⭐ |
| **Drawdown max** | **16.28%** | < 20% | ✅ |
| **%/mois simple** | **12.88%** | ≥ 10% | ✅ |
| %/mois composé | 2.50% | ≥ 10% | ❌ (très difficile mathématiquement) |
| Profit Factor | 2.541 | > 2 | ✅ |
| CAGR | 33.39%/an | — | Solide |
| Win Rate | 38.89% | — | OK (R:R compense) |
| Trades | 72 (sur 9 ans) | — | Sélectif |
| Avg win | +17.61% | — | ⭐ |
| Avg loss | -3.89% | — | ✅ contrôlé |
| Sharpe | 0.259 | > 1 idéal | À améliorer |

---

## 🧬 ARCHITECTURE (ORDRE DU FLUX)

```
COUCHE 1 — Market Outlook
  └─ EMA200 macro bias : Long uniquement si close > EMA200
                          Short uniquement si close < EMA200

COUCHE 2 — Confluences
  └─ PP-ST (Pivot Point SuperTrend) — pivots 2, factor 5, ATR 14
     └─ Signal d'entrée = retournement de trend PP-ST

COUCHE 3 — Structure & Liquidité
  └─ Niveaux Stoic : HCOM/LCOM (monthly close extremes)
                     PDH/PDL/PDC (daily reference)
                     SMA 20/200 (session bias)

COUCHE 4 — Filtre Range & Robustesse
  └─ ADX(14) ≥ 20 : pas de trade en marché plat
  └─ Cooldown intrinsèque PP-ST (pivots espacés)

COUCHE 5 — Qualité du Setup
  └─ Score Stoic 4 piliers : P1 Monthly, P2 SMA, P3 Daily, P4 Fib
  └─ BOOST de sizing par pilier (+25% par pilier validé)
     → score 0 = taille 100% | score 4 = taille +100% = 200%

COUCHE 6 — Risk Management
  └─ Sizing par % risque : 10% du capital par trade
  └─ Stop = trail PP-ST (dynamique)
  └─ Throttle adaptatif : si DD > 12%, taille divisée par 2
  └─ Cap absolu : risque effectif ≤ 15% du capital

COUCHE 7 — Exécution
  └─ Long & Short bidirectionnel
  └─ Exit sur retournement PP-ST OU breach EMA200
  └─ Process-orders-on-close : pas de bias intra-bar
```

---

## 💡 INNOVATIONS vs BASELINE `pp_st_btc_4h_final.pine`

| Aspect | Baseline | KB_HYBRID_V1 |
|---|---|---|
| Direction | Long only | **Long + Short** |
| Sizing | 100% equity (compose) | **% risk + throttle DD + cap** |
| Margin calls | Possibles | **5 sur 9 ans** (capital initial 10k seulement) |
| Stoic context | Absent | **Score 4 piliers en bonus sizing** |
| DD max | 24.53% | **16.28%** (–34% de risque) |
| Net % | +2947% | +1417% |
| PF | 2.52 | 2.541 |
| Trades | 59 | 72 |

**Trade-off** : ~50% de gain absolu en moins, mais 34% de DD en moins. Profil **plus défensif et plus sain**.

---

## 🚀 USAGE

1. **Charger le script** dans TradingView (Coinbase BTCUSD 4H recommandé)
2. **Paramètres par défaut** = config optimale du backtest. Ne pas modifier sans nouveau backtest.
3. **Sizing** : adapter `risk_pct` à ton appétit risque (5% = très prudent, 10% = équilibré, 15% = agressif)
4. **DD Throttle** : laissé à 12% — réduit auto le sizing en phase difficile
5. **Live trading** : compatible alertes webhook (à ajouter)

---

## ⚠️ LIMITES & PISTES D'AMÉLIORATION

### Pourquoi 10%/mois COMPOSÉ est très difficile
- 10%/mois composé = 213%/an. Quasi aucune strat retail crypto ne soutient ça >2 ans sans exploser.
- Le CAGR actuel (33%) est déjà excellent. Pousser plus = DD > 20% garanti.

### Pistes pour pousser au-delà
1. **Pyramiding** : ajouter à la position gagnante (+1R, +2R) sur signal continuation PP-ST
2. **Funding rates** : timing entry pour collecter funding favorables (crypto perp)
3. **Multi-asset rotation** : capital dynamiquement alloué entre BTC/ETH/SOL selon meilleur score Stoic
4. **Hyperparam optimization** (TradingView Premium ou backtest Python externe) sur prd/Factor/Pd
5. **Sharpe** faible (0.259) — peut être amélioré en filtrant les pires trades (Stoic en gate, pas en boost) — mais réduira drastiquement le nb de trades

### Phases de pertes connues
- Bear market 2018 (PP-ST coupe vite, mais quelques whipsaws)
- Été 2021 (consolidation longue)
- Été 2024 (chop) — visible dans le throttle DD

---

## 📊 FICHIERS LIÉS

- Strategy source : `pine_scripts/strategies/killingbot_hybrid_v1.pine`
- Backtest JSON : `backtest/results/kb_hybrid_v1_BTCUSD_4H.json`
- Screenshots : `backtest/screenshots/kb_hybrid_v1_*.png`
- CSV PP-ST baseline (référence) : `PP-ST-A_COINBASE_BTCUSD_2026-06-07_fdb4d.csv`
- Indicateur Stoic seul : `pine_scripts/indicators/stoic_confluence_indicator.pine`
- Dashboard live : `app/stoic_dashboard.html`
