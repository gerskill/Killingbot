---
type: strategie
statut: non-verifie
famille: Intraday
actif: 
timeframe: intraday
direction: 
fichier_pine: pine_scripts/strategies/killingbot_intraday_v1.pine
rapports:
  - vault/archive/strategies_sweep_invalide/KB_INTRADAY_V1_VERDICT.md
derniere_verif: 
tags: [strategie, intraday]
---

# killingbot_intraday_v1

> [!note] Non vérifié — aucun chiffre ne fait foi
> RR 2:1, stop ATR 1.0. Les cibles du commentaire (10 %/mois, WR ≥ 57 %) sont des objectifs, pas des résultats.

**Fichier** : [`pine_scripts/strategies/killingbot_intraday_v1.pine`](../../pine_scripts/strategies/killingbot_intraday_v1.pine)

## Rapports
- [KB_INTRADAY_V1_VERDICT.md](../../vault/archive/strategies_sweep_invalide/KB_INTRADAY_V1_VERDICT.md)

## Pour passer en `walk-forward-ok`
- Porter la logique en Python et la passer à `agents/validation.py` (70/30, Deflated Sharpe, Monte Carlo)
- Puis relire au Strategy Tester pour `prouve-live`

Retour : [[_Tableau de bord stratégies]]
