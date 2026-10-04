---
type: strategie
statut: non-verifie
famille: Hybrid
actif: BTCUSD
timeframe: 4H
direction: long
fichier_pine: pine_scripts/strategies/killingbot_hybrid_v1.pine
rapports:
  - backtest/MATRICE_FINALE.md
derniere_verif: 
tags: [strategie, hybrid]
---

# killingbot_hybrid_v1

> [!note] Non vérifié — aucun chiffre ne fait foi
> PP-ST + boost Stoic + sizing au risque. Chiffres de `MATRICE_FINALE.md` (2026-06-07), antérieurs à la règle de vérification live.

**Fichier** : [`pine_scripts/strategies/killingbot_hybrid_v1.pine`](../../pine_scripts/strategies/killingbot_hybrid_v1.pine)

## Rapports
- [MATRICE_FINALE.md](../../backtest/MATRICE_FINALE.md)

## Pour passer en `walk-forward-ok`
- Porter la logique en Python et la passer à `agents/validation.py` (70/30, Deflated Sharpe, Monte Carlo)
- Puis relire au Strategy Tester pour `prouve-live`

Retour : [[_Tableau de bord stratégies]]
