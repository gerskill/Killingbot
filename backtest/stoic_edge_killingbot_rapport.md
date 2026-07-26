# Rapport Backtest — Stoic Edge × Killingbot v1.0
**Date :** 2026-06-06  
**Fichier :** `stoic_edge_killingbot.pine`  
**Capital :** $10 000 | Commission : 0.1% | Slippage : 2 ticks  
**Paramètres v1.0 :** PP-ST prd=2 F=5 ATR=14 | EMA 7/21/200 | ADX≥20 | ATR%≥0.2% | Cooldown 3 bars | SL×1.5 ATR | TP1=2R(50%) TP2=3R | Trail PP-ST

---

## Résultats Backtest v1.0 — 6 Marchés

| Marché | TF | Période | P&L | DD | WR | Trades | PF | Verdict |
|--------|-----|---------|------|-----|-----|--------|-----|---------|
| BTCUSDT | 4H | 2017–2026 | **+8,38%** | 8,32% | 38,05% | 686 | 1,12 | ✅ Positif |
| ETH/USDT | Daily | 2017–2026 | **+7,63%** | 12,36% | 38,67% | 150 | 1,155 | ✅ Positif |
| EURUSD | 4H | 2013–2026 | **-6,63%** | 6,82% | 28,09% | 591 | 0,51 | ❌ Négatif |
| XAUUSD | 4H | 2013–2026 | **-9,54%** | 9,89% | 28,87% | 755 | 0,63 | ❌ Négatif |
| QQQ | 4H | 2000–2026 | **-1,68%** | 6,54% | 33,93% | 563 | 0,96 | ❌ Négatif |
| GBPUSD | 1H | 2023–2026 | **-0,19%** | 0,29% | 39,53% | 43 | 0,74 | ❌ Flat |

---

## Diagnostic v1.0

### 🔴 Problème Principal : Surcharge de Signaux

Le volume de trades est **anormal** — 500 à 755 trades sur 4H, contre 59 pour le PP-ST pur sur BTC 4H. Les 3 setups combinés (PP-ST flip + SFP + Break & Retest) génèrent trop de signaux, dont une majorité sont du bruit sur les marchés forex et actions.

**Comparaison :**
- PP-ST pur BTC 4H : 59 trades → **+2947%** | PF 2.52
- SE×KB v1.0 BTC 4H : 686 trades → **+8,38%** | PF 1.12

La sélectivité est le facteur de performance critique. Chaque filtre supplémentaire (SFP, B&R) dilue le signal sans améliorer l'expectancy.

### 🔴 Problème #2 : Shorts Contre-productifs sur Crypto/Actions

Sur des marchés structurellement haussiers (BTC, ETH, QQQ), les signaux Short du PP-ST baissier dans un marché globalement bullish créent des pertes systématiques. L'EMA200 et le bias HTF ne filtrent pas assez les faux retournements courts.

### 🔴 Problème #3 : Filtres Trop Souples sur Forex

- ADX ≥ 20 = trop bas pour forex (range fréquent)
- ATR% ≥ 0.2% = insuffisant pour EURUSD/GBPUSD (volatilité naturelle faible)
- Le SFP sur forex génère des faux signaux sur chaque micro-swing

### ✅ Ce Qui Fonctionne

- **Crypto (BTC Daily, ETH Daily)** : PF > 1 avec des trades espacés naturellement
- **Le trail PP-ST** : mécanisme de sortie correct, protège les gains sur ETH
- **Le dashboard** : richesse d'information utile (bias, ADX, setup, PnL)
- **L'architecture 7 couches** : structure solide, bon filtre No Edge Zone visuel

---

## Plan d'Optimisation — v2.0

### Changements Prioritaires

| # | Modification | Raison |
|---|-------------|--------|
| 1 | **Long Only** (désactiver shorts) | Crypto/Actions structurellement haussiers |
| 2 | **ADX min → 25** | Filtrer davantage les phases range |
| 3 | **ATR% min → 0.5%** (crypto) / **0.3%** (forex) | Volatilité minimale plus stricte |
| 4 | **Cooldown → 5 bars** | Réduire la densité des trades |
| 5 | **Désactiver SFP+B&R sur forex** | PP-ST flip seul sur forex |
| 6 | **Swing Length → 8** (forex) | Niveaux plus significatifs |
| 7 | **i_tp1Rr → 1.5R** (forex) | TP1 plus atteignable |

### Architecture v2.0 Proposée

```
Crypto (BTC/ETH)  → Long Only | ADX≥25 | ATR%≥0.5% | Cooldown 5 | SFP+B&R ON
Forex (EUR/GBP)   → Long+Short | ADX≥25 | ATR%≥0.3% | Cooldown 5 | PP-ST ONLY
Gold (XAUUSD)     → Long Only (tendance LT haussière) | ADX≥25 | PP-ST+SFP
Actions (QQQ)     → Long Only | ADX≥25 | Cooldown 7 | PP-ST ONLY
```

### Paramètres Cibles v2.0

```pine
// Crypto
i_ppst = true | i_sfp = true | i_bnr = false
i_adxMin = 25 | i_atrMin = 0.5 | i_cool = 5
i_slMult = 1.5 | i_tp1Rr = 2.0 | i_tp2Rr = 4.0  // TP2 plus loin sur crypto

// Forex / Gold / Actions
i_ppst = true | i_sfp = false | i_bnr = false
i_adxMin = 25 | i_atrMin = 0.3 | i_cool = 5
i_slMult = 1.2 | i_tp1Rr = 1.5 | i_tp2Rr = 2.5
```

---

## Résultats v2.0 — BTC 4H (Post-Optimisation)

**Compilé et testé le 2026-06-06 | Fichier : `stoic_edge_killingbot_v2.pine`**

| Métrique | v1.0 | v2.0 | Δ |
|----------|------|------|---|
| P&L total (10% sizing) | +8,38% | **+4,16%** | Moins mais plus sélectif |
| Drawdown max | 8,32% | **1,45%** | ÷ 5,7 ✅ |
| Facteur de Profit | 1,12 | **2,044** | × 1,8 ✅ |
| Trades | 686 | **58** | ÷ 11,8 ✅ |
| Win Rate | 38,05% | **41,38%** | +3,3 pts ✅ |

**Note sizing :** v2.0 utilise 10% du capital/trade. Pour comparer au PP-ST pur (100% = +2947%), multiplier par ~10 en termes de R-multiples.

---

## Comparaison Globale des Stratégies Killingbot

| Stratégie | BTC 4H | ETH Daily | Forex | Gold | Notes |
|-----------|---------|-----------|-------|------|-------|
| **PP-ST + EMA200 + ADX** ⭐ | **+2947%** | — | — | — | Long only 100%, 59 trades, PF 2.52 |
| **KB_LOOSE_RR2.5_RR3.0** | 8%/mois | — | — | — | EMA 7/21, PF 7.06, Sharpe 7.06 |
| **SE×KB v1.0** | +8,38% PF 1.12 | +7,63% PF 1.16 | ❌ | ❌ | Trop de trades (500-750), forex KO |
| **SE×KB v2.0** ✅ | PF 2.044 DD 1.45% | À tester | Éviter | Éviter | Long only, 58 trades, filtres serrés |

---

## Leçon Stoïque

> _"Less is more."_ — La stratégie PP-ST pure avec 59 trades a généré +2947%. Ajouter 3 setups × 2 directions = 686 trades et +8%. La **sélectivité** est la vraie edge, pas la quantité de setups.

**Prochaine étape :** Créer `stoic_edge_killingbot_v2.pine` — Long Only, ADX≥25, cooldown 5, SFP désactivé par défaut, B&R désactivé. Valider sur BTC 4H en priorité.

---

## Fichiers Liés

- `stoic_edge_killingbot.pine` — Code v1.0 (stratégie testée)
- `pp_st_btc_4h_final.pine` — ⭐ Meilleure stratégie référence
- `vault/BEST_STRATEGIES.md` — Top 10 backtestés
- `PINE_ERRORS.md` — Checklist erreurs Pine v6
