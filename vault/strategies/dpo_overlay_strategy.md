---
type: strategie
statut: non-verifie
famille: DPO
actif: 
timeframe: 
direction: 
fichier_pine: dpo_overlay_strategy.pine
rapports:
  - backtest/dpo_overlay_rapport.md
derniere_verif: 
tags: [strategie, dpo]
---

# dpo_overlay_strategy

> [!note] Non vérifié — aucun chiffre ne fait foi
> Detrended Price Oscillator en overlay.

**Fichier** : [`dpo_overlay_strategy.pine`](../../dpo_overlay_strategy.pine)

## Rapports
- [dpo_overlay_rapport.md](../../backtest/dpo_overlay_rapport.md)

## Pour passer en `walk-forward-ok`
- Porter la logique en Python et la passer à `agents/validation.py` (70/30, Deflated Sharpe, Monte Carlo)
- Puis relire au Strategy Tester pour `prouve-live`

Retour : [[_Tableau de bord stratégies]]
