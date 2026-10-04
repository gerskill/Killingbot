---
type: strategie
statut: non-verifie
famille: Stoic
actif: BTC / ETH
timeframe: 4H
direction: long-short
fichier_pine: pine_scripts/stoic_edge_strategy_v1.pine
rapports:
  - backtest/stoic_edge_killingbot_rapport.md
derniere_verif: 
tags: [strategie, stoic]
---

# stoic_edge_strategy

> [!note] Non vérifié — aucun chiffre ne fait foi
> Famille Stoic Edge : `pine_scripts/stoic_edge_strategy_v1.pine`, `stoic_edge_strategy_v1.1.pine`, `stoic_edge_strategy_v1.2.pine`, `stoic_edge_killingbot.pine`, `stoic_edge_killingbot_v2.pine`. Gestion T1 50 % → BE → T2 25 % → runner. Le commentaire de la v2 signale trop de trades sur BTC 4H.

**Fichier** : [`pine_scripts/stoic_edge_strategy_v1.pine`](../../pine_scripts/stoic_edge_strategy_v1.pine)

## Rapports
- [stoic_edge_killingbot_rapport.md](../../backtest/stoic_edge_killingbot_rapport.md)

## Pour passer en `walk-forward-ok`
- Porter la logique en Python et la passer à `agents/validation.py` (70/30, Deflated Sharpe, Monte Carlo)
- Puis relire au Strategy Tester pour `prouve-live`

Retour : [[_Tableau de bord stratégies]]
