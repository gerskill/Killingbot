---
type: strategie
statut: non-verifie
famille: Stoic
actif: 
timeframe: 
direction: long-short
fichier_pine: pine_scripts/strategies/stoic_123_v2.pine
rapports:
  - backtest/PTB_ENTREE_STOICTA_2026-07-27.md
derniere_verif: 
tags: [strategie, stoic]
---

# stoic_123_v2

> [!note] Non vérifié — aucun chiffre ne fait foi
> [[stoic_123]] + garde-fou de viabilité : refuse les trades dont le coût aller-retour mange le budget de risque (crypto 5m).

**Fichier** : [`pine_scripts/strategies/stoic_123_v2.pine`](../../pine_scripts/strategies/stoic_123_v2.pine)

## Rapports
- [PTB_ENTREE_STOICTA_2026-07-27.md](../../backtest/PTB_ENTREE_STOICTA_2026-07-27.md)

## Pour passer en `walk-forward-ok`
- Porter la logique en Python et la passer à `agents/validation.py` (70/30, Deflated Sharpe, Monte Carlo)
- Puis relire au Strategy Tester pour `prouve-live`

Retour : [[_Tableau de bord stratégies]]
