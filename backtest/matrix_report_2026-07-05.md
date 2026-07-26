# Rapport — Matrice multi-marchés / multi-TF + optimisation IS/OOS
**Date : 2026-07-05 | Session : ST-Fin Replica × Killingbot**

## Contexte

Suite du test ST-Fin Replica (réplique du "Smart Trader, Final Episode" d'ATA SABANCI, tweet du 4 juil. 2026). Le test BTC 1m initial était perdant (−1,78 %, PF 0.232, 74 trades). Cette session étend le test à 7 marchés × 4 timeframes × 4 stratégies (112 backtests), puis optimise les meilleurs couples avec validation out-of-sample.

## Méthodologie

Stratégies répliquées en Python vectorisé (`~/tradingview-mcp/backtest_matrix.py`) depuis les .pine du projet. Données : Binance (crypto, jusqu'à 8 760 barres) et Yahoo Finance (actions/indices/forex/or, 4h = resample du 1h). Long only, fill au close confirmé, commission 0,05 %/side, 100 % equity composé. Optimisation : grid search sur 70 % des données (IS), validation sur les 30 % restants (OOS), score = retour/drawdown. Vérification croisée sur TradingView Desktop (ST-FinRep sur NVDA 1D : comportement conforme).

Stratégies :
- **STFIN** — ST-Fin Replica : ancres gelées (lookback), entrée = Low croise ↑ Anchor LL (sweep du floor), sortie = High croise ↓ Anchor HH (ou centre √(HH·LL) en variante v2)
- **PPST_A** — PP SuperTrend (prd 2, F 5, ATR 14) + EMA200 + ADX≥20 (`pp_st_btc_4h_final.pine`)
- **SEKB2** — Stoic Edge × Killingbot v2 : PP-ST + ADX≥25 + ATR%≥0,5 + cooldown, SL 1,5×ATR, TP1 2R (50 %), TP2 4R, trail
- **KB_EMAKJ** — EMA7×21 cross + close > Kijun26

## Résultats matrice (extraits significatifs)

| Stratégie | Marché | TF | Retour | DD | PF | WR | n | vs B&H |
|---|---|---|---|---|---|---|---|---|
| STFIN | NVDA | 1h | +84 % | 16,5 % | 4.58 | 75 % | 16 | +68 % |
| STFIN | NVDA | 1d | +240 % | 60,8 % | 3.40 | 79 % | 14 | +7596 % |
| STFIN | ^GSPC | 1d | +64 % | 28,5 % | 8.19 | 85 % | 13 | +218 % |
| STFIN | GC=F (or) | 4h | +36 % | 26,5 % | 4.23 | 92 % | 13 | +64 % |
| STFIN | BTC/ETH/SOL | 15m-1h | négatif partout | — | 0.36–0.90 | — | — | — |
| PPST_A | ETHUSDT | 4h | +58 % | 26,6 % | 3.05 | 29 % | 14 | −14 % |
| PPST_A | GC=F | 1d | +106 % | 19,0 % | 11.69 | 43 % | 7 | +228 % |
| SEKB2 | ETHUSDT | 4h | +22 % | 5,9 % | 7.92 | 33 % | 6 | −14 % |
| KB_EMAKJ | SOLUSDT | 1d | +834 % | 74,5 % | 3.69 | 30 % | 37 | +136 % |
| KB_EMAKJ | NVDA | 1d | +1072 % | 49,5 % | 2.88 | 45 % | 56 | +7596 % |
| KB_EMAKJ | ^GSPC | 1d | +111 % | 17,1 % | 2.38 | 42 % | 53 | +218 % |

**Lecture structurelle** : le pattern ST-Fin (sweep du floor → reclaim) est un edge de *mean-reversion dans un uptrend* — il fonctionne sur actions/indices/or en 1h-1d et échoue sur crypto bas TF (crashes momentum sans stop). KB_EMAKJ (trend-following) domine en daily sur actifs trending. CSV complet : `~/tradingview-mcp/backtest_results.csv`.

## Optimisation — validés out-of-sample ✅

| Config | IS (70 %) | OOS (30 %) | Verdict |
|---|---|---|---|
| **STFIN NVDA 1d** — lookback 13, exit Center | +739 %, PF 5.62, n=21 | **+219 %, PF 6.22, n=15** | ✅ robuste, meilleur global |
| **KB_EMAKJ NVDA 1d** — 9/13/34 | +1806 %, PF 5.96 | **+477 %, PF 3.92, n=23** | ✅ robuste |
| **KB_EMAKJ ^GSPC 1d** — 9/21/34 | +83 %, PF 3.91, DD 12,5 % | **+59 %, PF 5.80, DD 8,3 %** | ✅ le plus régulier |
| **STFIN ^GSPC 1d** — lookback 47, exit Center | +53 %, PF 6.64 | **+59 %, PF 9.54, n=5** | ✅ (n faible) |
| **STFIN NVDA 1h** — lookback 47, exit Center | +51 %, PF 4.03 | **+39 %, PF 28.6, n=7** | ✅ (n faible) |
| STFIN GC=F 4h — lookback 13, ceiling | +53 %, PF 11.0, WR 96 % | +14 %, PF 2.13 | ⚠️ dégradation, exploitable |

## Rejetés (overfit — IS brillant, OOS négatif) ❌

PPST_A ETHUSDT 4h (IS +140 % → OOS −2,7 %), KB_EMAKJ SOLUSDT 1d 7/13/34 (IS +5032 % → OOS −5,3 %), STFIN EURUSD 4h (OOS négatif sur toutes variantes), SEKB2 partout (trop peu de trades).

## Enseignements clés

1. **Exit au centre √(HH·LL) > exit au ceiling** pour ST-Fin : prendre le profit au milieu du range est plus fiable qu'attendre le plafond (confirme le défaut identifié sur BTC 1m : trades de 4 h sans toucher le HH).
2. Lookback court (13) sur daily actions, long (47) sur 1h — cohérent avec le cycle de l'ancre.
3. Le stop ATR n'améliore pas ST-Fin (les sweeps profonds se rachètent) — mais sans stop, la stratégie est inutilisable sur crypto.
4. ST-Fin sous-performe toujours le buy & hold sur NVDA — son intérêt est le PF élevé et l'exposition partielle, pas le retour absolu.

## Limites

Données Yahoo 1h limitées à 2 ans ; NVDA = biais de sélection (méga-uptrend) ; frais uniformes 0,05 % ; slippage non modélisé ; OOS unique (pas de walk-forward complet) ; ceci n'est pas un conseil financier.

## Fichiers

- `~/tradingview-mcp/backtest_matrix.py` — framework (données + 4 stratégies + métriques)
- `~/tradingview-mcp/optimize_best.py` — grid search IS/OOS
- `~/tradingview-mcp/backtest_results.csv` — 112 résultats bruts
- `~/tradingview-mcp/STFin_Replica.pine` — réplique Pine v6 (avec input Exit level Ceiling/Center)

## Prochaines étapes suggérées

Walk-forward multi-fenêtres sur STFIN NVDA/^GSPC 1d ; étendre KB_EMAKJ 9/21/34 à d'autres indices (NDX, DAX) ; ajouter un régime filter (EMA200) à ST-Fin pour le rendre viable sur crypto 4h.
