# Rapport Backtest — DPO Overlay Strategy [Killingbot]
**Date :** 2026-06-04 | **Paramètres :** Length=20, Smooth=5, Anchor=50, SL×1.5ATR, TP×3.0, EMA200 ON, Trailing ON

---

## Résultats Multi-Marchés / Multi-TF

| # | Marché | TF | P&L | Drawdown | Win Rate | Trades | Verdict |
|---|--------|----|-----|----------|----------|--------|---------|
| 1 | BTC/USDT | 4H | **-44.24%** | 52.61% | 17.06% | 551 | ❌ Inutilisable |
| 2 | BTC/USDT | 1D | **-3.84%** | 56.73% | 14.77% | 88 | ❌ Mauvais |
| 3 | ETH/USDT | 4H | **+37.81%** | 54.73% | 16.61% | 626 | ⚠️ Trop de trades / DD élevé |
| 4 | SOL/USDT | 1D | **+237.54%** | 43.89% | 18.64% | 59 | ✅ Bon retour, DD acceptable |
| 5 | XAUUSD | 4H | **+19.47%** | 16.14% | 24.21% | 285 | ✅ DD faible, WR décent |
| 6 | QQQ | 4H | **+74.46%** | 10.82% | 39.66% | 58 | ⭐ Meilleur — DD minimal, WR correct |

---

## Analyse

### ✅ Marchés où la stratégie fonctionne

**QQQ 4H** est de loin le meilleur résultat :
- DD de seulement **10.82%** → très raisonnable
- WR de **39.66%** → le plus élevé du test
- 58 trades sur ~25 ans de données → fréquence saine
- La tendance directionnelle du Nasdaq se marie bien avec un oscillateur momentum

**SOL/USDT Daily** impressionnant en absolu (+237%) mais :
- Période biaisée par le bull run 2021-2024
- DD de 43.89% reste élevé
- 11 trades seulement sur 59 = peu de données

**XAUUSD 4H** est intéressant pour sa stabilité :
- DD le plus faible du test crypto/matières premières : **16.14%**
- 285 trades = statistiquement significatif
- Le Gold répond bien aux oscillateurs momentum volatilité-ajustés

### ❌ Marchés à éviter (paramètres actuels)

**BTC 4H** est le pire cas : 551 trades avec 17% WR → surtrading massif.
Le problème : l'oscillateur DPO génère trop de croisements mean en zone de range sur BTC 4H.

**ETH 4H** : même problème que BTC, 626 trades = bruit excessif.

---

## Diagnostic — Pourquoi BTC échoue et QQQ réussit

Le DPO Overlay est fondamentalement un **oscillateur de momentum relatif à la volatilité**.
Il performe sur les actifs à **tendance directionnelle forte et persistante** (QQQ bull market, Gold trend).
Il surtraide sur **BTC/ETH qui alternent range/trend** de façon brutale.

Le filtre EMA200 est actif mais insuffisant sur crypto — BTC peut rester en range
pendant des semaines au-dessus de son EMA200.

---

## Recommandations d'Optimisation

### Priorité 1 — Réduire le surtrading sur crypto
- **Augmenter Length** : 20 → 35-50 sur BTC/ETH 4H (moins de croisements)
- **Activer filtre ADX ≥ 25** : ne trader que quand le trend est établi
- **Cooldown** : ajouter un délai minimum de 3 bars entre deux signaux

### Priorité 2 — Améliorer le WR global
- **BB Breakout Filter = ON** : n'entrer qu'en expansion momentum (oscillateur > BB std)
- Cela réduit les trades mais augmente significativement la qualité des entrées

### Priorité 3 — Tester sur QQQ/Gold avec paramètres optimisés
Prochains backtests suggérés :
- QQQ 4H : Length=30, ADX≥20, BB filter ON
- XAUUSD 4H : Length=25, Smooth=3 (plus réactif)
- BTC 1D : Length=30, ADX≥25 (timeframe supérieur)

---

## Classement Final

| Rang | Marché/TF | Score | Raison |
|------|-----------|-------|--------|
| 🥇 | QQQ 4H | ⭐⭐⭐⭐⭐ | DD 10%, WR 40%, stable |
| 🥈 | XAUUSD 4H | ⭐⭐⭐⭐ | DD faible, statistiquement robuste |
| 🥉 | SOL Daily | ⭐⭐⭐ | Bon retour mais peu de trades |
| 4 | ETH 4H | ⭐⭐ | Positif mais DD élevé + surtrading |
| 5 | BTC 1D | ⭐ | Quasi neutre, éviter |
| 6 | BTC 4H | ✗ | Inutilisable en l'état |

---

## Conclusion

Le **DPO Overlay Strategy** n'est **pas une stratégie crypto-native** avec les paramètres par défaut.
Il excelle sur les **actifs actions/ETF à tendance longue** (QQQ) et les **matières premières** (Gold).

**Action immédiate recommandée :**
1. Déployer sur **QQQ 4H** avec BB filter ON pour paper trading
2. Tester sur XAUUSD 4H avec Smooth=3
3. Pour BTC : augmenter Length=40, activer ADX≥25 et re-tester

*Fichier stratégie : `dpo_overlay_strategy.pine`*
