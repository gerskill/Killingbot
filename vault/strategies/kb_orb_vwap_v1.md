---
type: strategie
statut: non-verifie
famille: KB
actif: futures
timeframe: intraday
direction: 
fichier_pine: pine_scripts/strategies/kb_orb_vwap_v1.pine
rapports:
  - backtest/orb_vwap_v1_resultats.md
derniere_verif: 
tags: [strategie, kb]
---

# kb_orb_vwap_v1

> [!note] Non vérifié — aucun chiffre ne fait foi
> Opening Range Breakout + VWAP.

**Fichier** : [`pine_scripts/strategies/kb_orb_vwap_v1.pine`](../../pine_scripts/strategies/kb_orb_vwap_v1.pine)

## Rapports
- [orb_vwap_v1_resultats.md](../../backtest/orb_vwap_v1_resultats.md)

## Pour passer en `walk-forward-ok`
- Porter la logique en Python et la passer à `agents/validation.py` (70/30, Deflated Sharpe, Monte Carlo)
- Puis relire au Strategy Tester pour `prouve-live`

Retour : [[_Tableau de bord stratégies]]
