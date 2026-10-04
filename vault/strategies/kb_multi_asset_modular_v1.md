---
type: strategie
statut: non-verifie
famille: KB
actif: multi
timeframe: 
direction: 
fichier_pine: pine_scripts/strategies/kb_multi_asset_modular_v1.pine
rapports: []
derniere_verif: 
tags: [strategie, kb]
---

# kb_multi_asset_modular_v1

> [!note] Non vérifié — aucun chiffre ne fait foi
> Structure 7 couches, régime ADX%-rank + squeeze TTM.

**Fichier** : [`pine_scripts/strategies/kb_multi_asset_modular_v1.pine`](../../pine_scripts/strategies/kb_multi_asset_modular_v1.pine)

## Pour passer en `walk-forward-ok`
- Porter la logique en Python et la passer à `agents/validation.py` (70/30, Deflated Sharpe, Monte Carlo)
- Puis relire au Strategy Tester pour `prouve-live`

Retour : [[_Tableau de bord stratégies]]
