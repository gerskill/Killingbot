# Stoic Confluence Strategy — Matrice de résultats (Phase 1)

> **Date** : 2026-06-07
> **Stratégie** : `pine_scripts/strategies/stoic_confluence_strategy.pine`
> **Paramètres** : score_min=3, ATR×1.5 stop, R:R 1:2, cooldown 5 bars, risk 1%, commission 0.05%, slippage 2 pts

---

## 🏆 RÉSULTATS PHASE 1 — 4 BACKTESTS LIVE (TradingView Strategy Tester)

| # | Symbole         | TF   | Période       | Trades | WR     | PF     | Net %    | DD %   | Avg Win | Avg Loss | Verdict |
|---|-----------------|------|---------------|--------|--------|--------|----------|--------|---------|----------|---------|
| 1 | **BTCUSD**      | **4H** | 2017-2026 (9y)| **44** | **52.27%** | **2.768** | **+48.93%** | **8.48%** | +5.78% | -2.32% | ⭐⭐⭐ **EDGE CONFIRMÉ** |
| 2 | BTCUSD          | 1D   | 2014-2026     | 114    | 42.11% | 1.286  | +30.30%  | 11.43% | +10.30% | -7.23% | ⭐ Edge marginal |
| 3 | BTCUSD          | 1H   | 2024-2026     | 2      | 50.00% | 0.19   | -0.82%   | 1.44%  | —       | —        | ❌ Échantillon insuffisant |
| 4 | XAUUSD (OANDA)  | 4H   | 2013-2026     | 7      | 42.86% | 1.891  | +5.09%   | 2.60%  | —       | —        | ⚠️ Échantillon faible |
| 5 | ETHUSDT         | 4H   | 2017-2026 (9y)| 42     | 35.71% | 0.921  | -2.62%   | 13.73% | —       | —        | ❌ Pas d'edge |

---

## 📊 LECTURE DES RÉSULTATS

### ✅ Sweet spot : **BTC/USD en 4H**
PF 2.77, DD 8.48%, WR 52%, 44 trades sur 9 ans → **edge statistique solide**. La rareté des trades (5/an) confirme la philosophie Stoic : "Cash is a position". Sharpe faible (0.128) reflète l'inactivité, pas la mauvaise qualité.

### ⚠️ Daily moins efficace
BTC Daily : PF 1.29, WR 42% — l'edge se dilue. Le protocole Stoic est conçu pour HTF *context* + entrée plus fine (4H/15m). En Daily, on rate les entrées précises.

### ❌ 1H et intraday : pas adapté
Trop peu de trades sur 1H (filtres trop restrictifs : score≥3 + cooldown + robust). Stoic n'est pas conçu pour scalping.

### ❌ ETH 4H : pas d'edge
PF 0.92 — la strat perd. ETH ne respecte pas les niveaux mensuels institutionnels comme BTC. Comportement de marché différent (plus volatil, moins de "trapped traders" identifiables).

### ⚠️ XAUUSD : échantillon trop faible
7 trades sur 13 ans = OANDA limite l'historique chargé dans le strategy tester (~10k bougies). À retester avec plus de données ou en Daily.

---

## 🎯 COMPARAISON AVEC BASELINE PROJET

| Stratégie | Marché | TF | Période | Net % | DD % | PF |
|-----------|--------|----|---------|---|---|----|
| **`pp_st_btc_4h_final.pine`** (baseline) | BTC | 4H | 2020-2026 (6y) | **+2947%** | 24.53% | 2.52 |
| **`stoic_confluence_strategy.pine`** (nouveau) | BTC | 4H | 2017-2026 (9y) | +48.93% | **8.48%** | **2.768** |

**Lecture** : Stoic est *moins explosif* mais *3x plus prudent* (DD 8.48% vs 24.53%). PF légèrement supérieur (2.77 vs 2.52). 5 trades/an vs ~10 = encore plus sélectif.

**Stoic ne remplace pas PP-ST** — c'est un complément, plus défensif, adapté aux phases de marché incertaines. Le sizing 1% du risque + R:R fixe 1:2 limite mécaniquement la performance — la vraie puissance Stoic vient de l'**exécution manuelle** avec runners (T1 50%, T2 25%, T3 trail).

---

## 🚀 PHASE 2 — À LANCER ENSUITE

Pour aller plus loin (sessions suivantes) :

1. **BTC Daily avec R:R 1:3** au lieu de 1:2 (le Daily a un avg_win 10.3% vs avg_loss 7.2% → un target plus grand exploiterait mieux les move directionnels)
2. **SOLUSDT 4H et 1D** (le projet a déjà SOL Daily à 7.45%/mois en baseline EMA)
3. **NAS100 (NQ1!) 4H** — marché institutionnel typique du protocole
4. **Tester score_min=4 uniquement** (GOLDEN setups) — moins de trades, meilleur PF attendu
5. **Ajouter trailing stop après TP1** (option `use_trailing` déjà dans la strat) pour capter les trending days
6. **Multi-symboles via `batch_run`** (MCP TradingView le supporte)

---

## 📁 FICHIERS

- Stratégie Pine : `pine_scripts/strategies/stoic_confluence_strategy.pine`
- Indicateur seul (manuel) : `pine_scripts/indicators/stoic_confluence_indicator.pine`
- Résultats JSON : `backtest/results/stoic_<symbol>_<tf>.json`
- Screenshots : `backtest/screenshots/`
- Dashboard live : `app/stoic_dashboard.html`
