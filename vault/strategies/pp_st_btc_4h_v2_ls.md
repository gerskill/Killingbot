---
type: strategie
statut: non-verifie
famille: PP-ST
actif: BTCUSDT
timeframe: 4H
direction: long-short
fichier_pine: pine_scripts/strategies/pp_st_btc_4h_v2_ls.pine
rapports: []
derniere_verif: 
tags: [strategie, pp-st]
---

# pp_st_btc_4h_v2_ls

> [!note] Non vérifié — aucun chiffre ne fait foi
> Logique long identique à [[pp_st_btc_4h_final]] + shorts miroir, SL ATR dur, cooldown, sizing % risque, alertes JSON webhook. Jamais testée avec les shorts activés.

**Fichier** : [`pine_scripts/strategies/pp_st_btc_4h_v2_ls.pine`](../../pine_scripts/strategies/pp_st_btc_4h_v2_ls.pine)

## Pour passer en `walk-forward-ok`
- Porter la logique en Python et la passer à `agents/validation.py` (70/30, Deflated Sharpe, Monte Carlo)
- Puis relire au Strategy Tester pour `prouve-live`

Retour : [[_Tableau de bord stratégies]]
