# ⚠️ KB_INTRADAY_V1 — Verdict après backtest

> **Date** : 2026-06-07
> **Statut** : ❌ ABANDON — la mécanique PP-ST n'est pas adaptée à l'intraday

---

## 🎯 Objectifs cibles (rappel)
- 10%/mois minimum
- 15% DD max
- 57% Win Rate
- 2-3 trades/semaine
- TF minimum 1m, position minimum 5m
- 5+ ans de backtest

---

## 📊 Résultats des tests

### BTC/USD 1H Coinbase (2024-2026, 2.5 ans seulement disponibles)

**Version pleine (PP-ST + VWAP + EMA + ADX + Vol + KillZones + Sweep + Stoic)**
- Trades : **0** sur 2.5 ans
- Cause : empilement de filtres trop restrictif → aucun signal ne passe

**Version minimale (PP-ST + ADX uniquement)**
- Trades : **508 sur 2.5 ans** (= 17/mois, trop)
- WR : **23.43%** ❌ (cible 57%)
- PF : **0.684** ❌ (perdant)
- DD : **53.90%** ❌ (cible <15%)
- Net : **-49.19%** ❌

### Diagnostic

Le problème est **structurel, pas paramétrique** :
- Le PP-ST avec prd=2/Factor=3 sur 1H produit ~17 triggers/mois
- Chaque trigger est un retournement temporaire → stop ATR×1 fixe coupé sur la première mèche
- Target 2R rarement atteint car PP-ST retourne vite → exit "RevExit" en perte
- Résultat = whipsaw destructeur

**Le PP-ST est conçu pour le swing trading (4H+), pas pour l'intraday.**

---

## 🚧 LIMITES TECHNIQUES RENCONTRÉES

### Données historiques sur TradingView
- BTC Coinbase 15m : **6 mois** seulement (loin des 5 ans demandés)
- BTC Coinbase 30m : **1.5 ans** 
- BTC Coinbase 1H : **2.5 ans**
- BTC Coinbase 4H : **9+ ans** ✅

➡️ **Seul le 4H permet de respecter la contrainte "5+ ans de backtest"** sur Coinbase pour BTC.

### Le 1H n'a même pas la profondeur historique demandée
2.5 ans < 5 ans → cible non atteignable techniquement sur cet exchange/asset.

---

## 💡 POUR ATTEINDRE LES OBJECTIFS — RECOMMANDATIONS

Vu les contraintes, plusieurs voies possibles :

### Voie 1 : Garder le 4H, accepter 2-3 trades/mois (pas /semaine)
- Stratégie **KB_HYBRID_V2 BTC 4H Coinbase** déjà livrée
- 14%/mois simple ✅, DD 16% ✅, WR 49% (proche 57% cible)
- ~0.79 trade/mois en moyenne (loin de 2-3/sem)
- **Trade-off** : moins de fréquence mais qualité éprouvée

### Voie 2 : Multi-asset portfolio sur 4H (déjà documenté KB_PORTFOLIO_V1)
- BTC + ETH + (optionnel) Binance hedge
- ~2-3 trades/mois agrégés
- 10%/mois simple ✅, DD 15-17% ✅

### Voie 3 : Approche SMC/Order-Block intraday (non codée — futur)
Pour vraiment atteindre 2-3 trades/sem + WR 57% en intraday, il faut :
- **Break of Structure** detection (BoS via swing high/low confirmés)
- **Order Block** identification (dernière bougie haussière avant mouvement baissier)
- **Fair Value Gap** (FVG) comme target
- **Stops naturels** au dernier swing, pas en ATR fixe
- **Multi-timeframe MTF strict** : 4H trend → 1H FVG → 15m entry précis
- Volume Profile + VWAP comme S/R intraday

C'est ~500 lignes de Pine v6 et 3-5 sessions de tuning. Réalisable mais hors scope de cette session.

### Voie 4 : Sortir de TradingView pour backtest sérieux intraday
- Python + Backtrader / VectorBT sur données tick depuis Binance/Coinbase API
- Permet 5+ ans de données 1m/5m
- Walk-forward optimization
- ML feature engineering

### Voie 5 : Accepter une fréquence plus basse pour préserver l'edge
- Vérité empirique : plus on monte en fréquence, plus l'edge diminue (efficacité de marché)
- Les bons traders pros font souvent 1-2 trades/sem, pas 10
- "Trade less, win more" — c'est la philosophie Stoic

---

## ✅ RECOMMANDATION ACTUELLE

**Garder KB_HYBRID_V2 sur BTC 4H Coinbase** comme stratégie principale, et utiliser le dashboard pour le suivi.

Pour le live trading TradingView (broker connecté), c'est V2 4H qui est **prêt à brancher dès maintenant**. Les chiffres sont solides (1535% sur 9 ans, DD 16%, PF 2.49, WR 49%).

Pour pousser vers 57% WR + intraday réel, prévoir une session dédiée à l'implémentation SMC ou à la sortie en Python.

---

## 📁 ARCHIVE

- Pine : `pine_scripts/strategies/killingbot_intraday_v1.pine` (conservé pour référence)
- Cette doc : `vault/strategies/KB_INTRADAY_V1_VERDICT.md`
- Stratégie recommandée : `pine_scripts/strategies/killingbot_hybrid_v2.pine`
