---
type: strategie
statut: prouve-live
famille: PP-ST
actif: BTCUSDT
timeframe: 4H
direction: long
fichier_pine: pp_st_btc_4h_final.pine
rapports:
  - backtest/WALK_FORWARD_PPST_2026-07-26.md
  - backtest/G8_G9_ELIGIBILITE_ET_GLISSANT_2026-07-26.md
  - Rapport_Analyse_PPST_EMA200_ADX.md
derniere_verif: 2026-07-26
net_pct: 2947.56
dd_pct: 24.53
pf: 2.52
wr_pct: 33.9
trades: 59
sharpe: 0.248
oos_median_pct_mois: 0.35
tags: [strategie, ppst, btc, trend-following]
---

# PP-ST + EMA200 + ADX — BTC 4H

> [!success] Seule stratégie prouvée en direct
> Strategy Tester TradingView, 2026-07-18. Seule ligne qui autorise du capital (paper).

## Logique
- **Signal** : Pivot Point SuperTrend (pivots `prd=2`, bandes ATR `Factor=5`, `Pd=14`) passe haussier
- **Filtre macro** : `close > EMA200`
- **Filtre qualité** : `ADX ≥ 20`
- **Sortie** : retournement du PP-ST (pas de TP fixe — un TP fixe coupe les gros trades sur BTC)

## Résultats vérifiés

| Source | Date | Net | DD | PF | WR | Trades |
|---|---|---|---|---|---|---|
| Strategy Tester — BINANCE:BTCUSDT 2017→2026 | 2026-07-18 | +2947.56 % | 24.53 % | 2.52 | 33.9 % | 59 |
| Strategy Tester — BITSTAMP:BTCUSD | 2026-07-18 | +8058.68 % | 18.77 % | 2.635 | 28.4 % | 81 |

Sharpe ≈ 0.25 sur les deux : la performance tient à peu de gros trades.

### Walk-forward 70/30, 10 paires Binance (2026-07-26)
- **Survit, avec réserves** : OOS positif sur 6/10 paires, bat le buy & hold sur 7/10
- OOS panier : **+0.35 %/mois médian**, +0.56 %/mois moyen (≈ 4 à 7 %/an, pas ×30)
- BTC seul : IS +3.88 %/mois → OOS +0.50 %/mois (dégradation −87 %)
- Deflated Sharpe 0.025 · Monte Carlo 100 % stable
- Filtre d'éligibilité G8 (PF IS ≥ 1.20, ≥ 12 trades) : écarte DOTUSDT, OOS moyen → +0.79 %/mois

Détail : [WALK_FORWARD_PPST](../../backtest/WALK_FORWARD_PPST_2026-07-26.md),
[G8/G9](../../backtest/G8_G9_ELIGIBILITE_ET_GLISSANT_2026-07-26.md).

## Variantes
- [[pp_st_btc_4h]] — sans ADX (backup)
- [[pp_st_btc_4h_v2_ls]] — long + short, SL dur et sizing optionnels

## Questions ouvertes
- `strategies/pp_st_btc_4h/config.json` est marqué `REJECTED` par le pipeline auto
  (variante avec SL 1.5 ATR et risque 1 %, pas la logique du `.pine`) — à réconcilier.
- [[stoic_123_cassure]] bat cette stratégie en walk-forward ; comparaison sur
  fenêtres identiques à faire avant de changer de référence.

## Journal
- 2026-07-18 — confirmée en live (Binance + Bitstamp)
- 2026-07-19 — alerte TradingView active, collecte OOS en paper
- 2026-07-26 — walk-forward : survit, edge réel ≈ +0.35 %/mois médian
