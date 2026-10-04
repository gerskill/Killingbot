---
type: strategie
statut: walk-forward-ok
famille: Stoic
actif: BTC + 9 alts (Binance)
timeframe: 4H
direction: long-short
fichier_pine: pine_scripts/strategies/stoic_123.pine
rapports:
  - backtest/PTB_ENTREE_STOICTA_2026-07-27.md
derniere_verif: 2026-07-27
oos_median_pct_mois: 1.25
wr_pct: 40.6
tags: [strategie, stoic, candidat]
---

# STOIC 1-2-3 — entrée sur cassure

> [!warning] Candidat, pas encore validé en live
> Né d'un test de l'entrée PTB de @StoicTA : la cassure au marché a battu le PTB
> sur tous les critères. Testé en Python (`agents/ptb_wf.py`), **pas encore au
> Strategy Tester**.

## Logique
- Step 1 impulsion → Step 2 creux du repli → Step 3 clôture au-delà du Step 1
- **Entrée au marché sur la cassure** (au lieu d'un ordre stop au-dessus du PTB)
- Stop sous le creux du Step 2 (plus large que sous le PTB — c'est ce qui survit au bruit 4H)
- Cibles 2R puis extension Fib 261.8 %

## Résultats vérifiés (walk-forward 70/30, 2026-07-27)

| Entrée | OOS positif | OOS médian | WR | Trades IS |
|---|---|---|---|---|
| **Cassure** | **10/10** | **+1.25 %/mois** | 40.6 % | 260 |
| PTB (sa règle) | 6/10 | +0.51 %/mois | 19.4 % | 383 |

Détail : [PTB_ENTREE_STOICTA](../../backtest/PTB_ENTREE_STOICTA_2026-07-27.md).

## À faire avant paper
1. Filtre d'éligibilité G8 + test de permutation sur les 10 paires (fait sur BTC seulement)
2. Comparaison avec [[pp_st_btc_4h_final]] sur fenêtres identiques
3. Version Pine du mode cassure + relecture au Strategy Tester

## Voir aussi
[[stoic_123]] · [[stoic_123_v2]] (entrée PTB) · [[stoic_123_ribbon]]
