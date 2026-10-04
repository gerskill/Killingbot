---
type: strategie
statut: non-verifie
famille: Stoic
actif: 
timeframe: 4H
direction: long-short
fichier_pine: pine_scripts/strategies/stoic_123.pine
rapports:
  - backtest/PTB_ENTREE_STOICTA_2026-07-27.md
derniere_verif: 
tags: [strategie, stoic]
---

# stoic_123

> [!note] Non vérifié — aucun chiffre ne fait foi
> Règle d'origine de @StoicTA : entrée par ordre stop au-dessus du PTB. En walk-forward crypto 4H, l'entrée PTB fait moins bien que la cassure → voir [[stoic_123_cassure]].

**Fichier** : [`pine_scripts/strategies/stoic_123.pine`](../../pine_scripts/strategies/stoic_123.pine)

## Rapports
- [PTB_ENTREE_STOICTA_2026-07-27.md](../../backtest/PTB_ENTREE_STOICTA_2026-07-27.md)

## Pour passer en `walk-forward-ok`
- Porter la logique en Python et la passer à `agents/validation.py` (70/30, Deflated Sharpe, Monte Carlo)
- Puis relire au Strategy Tester pour `prouve-live`

Retour : [[_Tableau de bord stratégies]]
