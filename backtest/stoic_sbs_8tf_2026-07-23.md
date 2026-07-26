# STOIC SBS — sweep 8 TF + tuning (BTCUSDT)

_2026-07-23 · `pine_scripts/strategies/stoic_sbs.pine` · défauts sauf mention_

## Baseline 8 TF (défauts)

| TF | P&L | DD | WR | Trades |
|----|-----|-----|-----|--------|
| 1m | — | — | — | 0 (16j data) |
| 5m | +0,75 % | 1,4 % | 62 % | 13 |
| 15m | −4,0 % | 6,7 % | 31 % | 59 |
| 1h | +0,47 % | 7,5 % | 38 % | 123 |
| 4h | −5,4 % | 10,0 % | 36 % | 45 |
| 8h | −10,9 % | 13,0 % | 30 % | ~ |
| D | +2,1 % | 2,0 % | 50 % | 14 |
| W | −2,0 % | 2,0 % | 0 % | 5 |

Faible partout. Négatif ou plat. Échantillons souvent minces.

## Tuning 1h (meilleur échantillon)

| Config | P&L | DD | WR | Trades |
|---|---|---|---|---|
| défauts | +0,47 % | 7,5 % | 38 % | 123 |
| swingLen5 · maxWait50 · fibDeep0.5 | +2,31 % | 9,2 % | 49 % | 278 | ✅ meilleur |
| swingLen3 · fibDeep0.382 | −12,97 % | 18,2 % | 42 % | 157 | ❌ |

Meilleur tune 1h = +2,3 %. Reste faible.

## Verdict

SBS mécanisé **sous-performe** nettement. Meilleur résultat toutes TF/params = +2,3 %.
À comparer : système ruban STOIC-123 = +18 % sur 8h.

**Cause : la méthode de StoicTA est discrétionnaire.** Le "trapped trader" (qui
est piégé, où sont les stops, first tap liquidé, double bottom) se lit à l'œil,
avec du contexte. Mécaniser la séquence en machine à états perd l'edge : le
backtest exécute la forme du pattern sans le jugement qui fait sa valeur.

## Reco

1. **SBS = mauvais candidat pour l'automatisation.** Le garder comme indicateur
   d'aide à la décision (signaux visuels), pas comme strat auto.
2. Pour l'auto, le système **ruban STOIC-123** reste le meilleur (trend-following,
   +18 % 8h crypto/indices).
3. Config SBS la moins pire si vraiment voulu : 1h · swingLen5 · maxWait50 · fibDeep0.5.

Tout in-sample.
