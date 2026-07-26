# Hypothèses — pp_st_btc_4h

> ⚠️ **Document reconstitué le 2026-07-25**, après coup. Les hypothèses ci-dessous
> ont été inférées du code Pine et de l'historique du projet, pas écrites avant
> les backtests. Pour toute stratégie suivante, remplir ce fichier **avant** le
> premier chiffre — c'est la seule façon de distinguer une hypothèse d'un
> ajustement rétrospectif.

## Hypothèse économique

Le BTC alterne entre phases de tendance soutenue et longues consolidations. Un
suiveur de tendance gagne peu souvent mais beaucoup quand il gagne : l'essentiel
du résultat provient d'une poignée de mouvements. La difficulté n'est pas de
détecter la tendance, c'est de **ne pas se faire découper pendant les ranges**,
où un signal de retournement produit des faux départs à répétition.

Les deux filtres n'existent donc que pour supprimer des trades, pas pour en
trouver.

## Composants

| Composant | Hypothèse | Effet attendu sur le nombre de trades |
|-----------|-----------|----------------------------------------|
| PP SuperTrend (prd 2, F 5, ATR 14) | détecte le retournement de tendance | — (générateur de signal) |
| EMA200 | filtre de tendance macro : ne pas acheter sous la moyenne longue | ↓ |
| ADX ≥ 20 | écarte les phases de range où le signal produit des faux départs | ↓ 71 → 59 (mesuré) |
| Sortie sur retournement, **sans TP fixe** | laisser courir : un TP coupe les +200-400 % qui portent tout le résultat | ↑ durée de détention |

## Conditions d'invalidation

- Profit Factor sous 1.0 sur 12 mois glissants en paper
- Drawdown au-delà de 30 % (au-dessus des 24,5 % du backtest)
- Plus de 6 pertes consécutives (jamais observé historiquement)
- Écart durable entre les sorties réelles et les sorties du backtest

## Écart connu entre le Pine et le portage Python

Le Pine (`strategy.pine`) est la **référence de production** : c'est lui qui a
passé G6 le 2026-07-18 et qui alimente l'alerte en cours. `logic.py` est un
portage destiné à la boucle de recherche, et il n'est pas identique.

| | Pine (référence) | Portage Python |
|---|---|---|
| Trades sur l'historique complet | 59 | 52 |
| Win rate | 33.9 % | 30.8 % (40.4 % sans stop) |
| Dimensionnement | 100 % de l'équité, composé | risque 1 % par trade |
| Stop | aucun | ATR × 1.5 (requis par le risque fixe) |

Écart d'environ 12 % sur le nombre d'entrées. Origine probable : `ta.pivothigh`,
`ta.dmi` et `ta.atr` ont des détails d'implémentation qui ne se transposent pas
exactement. Le portage reproduit la **forme** de la stratégie, pas son résultat
au trade près.

**Conséquence pratique** : ne jamais utiliser les chiffres du portage pour
juger la stratégie de production. Le portage sert à explorer des variantes ; la
validation reste le Strategy Tester TradingView.

## Statut des portes (portage Python, 2026-07-25)

| Porte | Résultat |
|-------|----------|
| G1 trades | ✅ 51 total, 16 OOS |
| G2 PF OOS | ✅ 2.625 |
| G3 dégradation OOS | ❌ **−74.1 %** (max −30 %) |
| G4 Deflated Sharpe | ✅ 1.0 |
| G5 stabilité Monte Carlo | ❌ **66.7 %** (min 80 %) |
| Drawdown | ✅ 5.96 % |
| G6 test live TradingView | ✅ passé le 2026-07-18 (Pine) |

**La stratégie est REJETÉE par le portage tout en étant confirmée en live.**
Cette contradiction est le fait le plus intéressant du dossier, et elle n'est
pas résolue :

- **G3** compare 2017-2023 (bull runs) à 2023-2026 (autre régime). Une chute du
  rendement mensuel est attendue pour un suiveur de tendance changeant de
  régime — mais c'est aussi exactement ce qu'une porte doit signaler.
- **G5** indique qu'une perturbation de ±10 % des paramètres casse la stratégie
  4 fois sur 10. Préoccupation réelle, cohérente avec un Sharpe de 0.248 et un
  résultat porté par une poignée de gros trades.

Deux lectures possibles, toutes deux partiellement vraies : soit les portes sont
sévères pour un suiveur de tendance à basse fréquence, soit la stratégie est
plus fragile que ses +2947 % ne le laissent croire. **Ne pas ajuster les portes
pour la faire passer** — ce serait reproduire le mécanisme qui a produit les dix
fausses stratégies du sweep KB_*. La question se tranchera avec les données OOS
réelles collectées depuis le 2026-07-19.
