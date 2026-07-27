# G1c — Walk-forward de `stoic_lens_pure_v2.pine`

_26 juillet 2026 · `agents/lens_wf.py` + `agents/validation.py`_
_Données : API Binance · 10 paires · 70 % in-sample / 30 % out-of-sample_

Dernier candidat non testé. En in-sample il affichait la meilleure généralisation
du projet : **17/20 symboles positifs en Daily, aucun drawdown au-dessus de 8,8 %**.

## Verdict : échoue

Sur les deux sweet spots identifiés en in-sample.

| | Daily | 15 min |
|---|---|---|
| OOS positif | **1/8** | 7/10 |
| Panier OOS moyen | **−0,05 %/mois** | **−0,12 %/mois** |
| Panier OOS médian | −0,06 %/mois | +0,24 %/mois |
| Bat le buy & hold | 2/10 | 9/10 ¹ |
| Monte Carlo | 90 % stable | **20 % stable** |
| Deflated Sharpe | 0,00 | 0,03 |

¹ Trompeur — voir plus bas.

## Un bug de portage qui aurait faussé la conclusion

Premier passage : **zéro trade**, sur tous les symboles. Diagnostic du tunnel de
filtres : biais 1680 barres → hors No Edge Zone 1288 → setup présent 999 →
**score ≥ 3 : jamais**.

Cause : sous NumPy 2.x, `+` entre `np.bool_` est un **OU logique**, pas une
addition. `p1l + bias_long + p3l + p4l` valait `True`, et `True >= 3` est faux.
Le score n'a jamais pu atteindre 3.

```python
# faux — le score vaut True, jamais 3
score_l = p1l + bias_long + p3l + p4l
# correct
score_l = int(p1l) + int(bias_long) + int(p3l) + int(p4l)
```

Sans ce diagnostic, j'aurais conclu « la stratégie ne prend aucun trade » au lieu
de la tester. Corrigé, puis relancé.

## Le vrai problème : deux piliers qui s'excluent

Fréquence de déclenchement de chaque pilier sur BTC Daily (2995 barres) :

| Pilier | Déclenche | |
|---|---|---|
| P1 — extrême mensuel | 77,7 % | |
| P2 — biais SMA | 56,1 % | |
| P3 — niveau daily | 83,4 % | |
| P4 — zone Fib | 17,4 % | ← goulot |

Pris isolément, trois piliers sur quatre déclenchent souvent. Mais **P1 et P2
sont directionnellement incompatibles** :

- P1 long = le prix est près du **plus bas close du mois**
- P2 long = le prix est **au-dessus de SMA20 > SMA200**, donc en tendance haussière

Sur 920 barres en biais long, seules **154 (17 %)** ont aussi P1 long. Exiger 3
piliers sur 4 quand deux d'entre eux se contredisent revient à exiger P3 **et**
P4 quasi systématiquement — et P4 ne sort que 17 % du temps.

Conséquence directe : **3 à 14 trades par fenêtre** en Daily. Le « 17/20 positifs »
in-sample reposait sur des échantillons de cette taille — je l'avais d'ailleurs
signalé à l'époque (« ETH 5 trades, DAX 10, EURUSD 14 — non significatif »).
Le walk-forward le confirme : c'était du bruit.

## Le « bat le buy & hold 9/10 » en 15 min est un artefact

La fenêtre de 500 jours en 15 min tombe sur un marché baissier pour la plupart
des alts. Exemples :

| Symbole | Stratégie | Buy & hold |
|---|---|---|
| ADAUSDT | −9,2 % | −77,4 % |
| DOTUSDT | −12,3 % | −80,1 % |
| AVAXUSDT | −11,8 % | −64,7 % |

Perdre 9 % quand le marché perd 77 %, ce n'est pas un edge — c'est être peu
exposé. **Le total reste négatif sur 8 symboles sur 10.**

Et le Monte Carlo est sans appel : **20 % de stabilité**. Quatre perturbations de
paramètres sur cinq font s'effondrer le résultat.

## Comparaison des trois stratégies testées

| | Ruban 1-2-3 | Lens 4 piliers | **PP-ST** |
|---|---|---|---|
| OOS positif | 3/10 | 1/8 (D) · 7/10 (15m) | **6/10** |
| Panier OOS | négatif | **−0,05 %/mois** | **+0,35 %/mois** |
| Dégradation médiane | −131 % | −231 % (D) | **−70 %** |
| Monte Carlo | 100 % | 90 % (D) · 20 % (15m) | **100 %** |
| **Verdict** | échoue | **échoue** | **survit** |

`pp_st_btc_4h_final` reste la seule stratégie du projet qui survit hors échantillon.

## Ce que ça apprend sur la conception

Le scoring multi-piliers paraît robuste — chaque pilier a un sens, et exiger 3/4
semble prudent. Mais **personne n'avait vérifié que les piliers pouvaient être
vrais en même temps**. Deux d'entre eux décrivent des situations de marché
opposées.

Règle à retenir : avant de valider un système de score, **mesurer le taux de
déclenchement conjoint**, pas seulement le taux individuel.

## Réserves

- Le portage Python produit moins de trades que le Pine sur BTC Daily (12 contre
  36). Une partie de l'écart vient de `.shift(1)` sur HCOM/LCOM — je n'utilise
  que l'information close de la veille, là où le Pine inclut le jour courant.
  Cet écart ne change pas la conclusion : dans les deux cas la fréquence est trop
  basse pour être exploitable.
- Univers crypto uniquement. Le test in-sample couvrait aussi actions, indices et
  forex ; leur comportement hors échantillon n'est pas mesuré ici.
- Fenêtre 15 min limitée à 500 jours et à un régime majoritairement baissier.

## Suite

1. **G8** — filtre d'éligibilité par symbole (le cas DOT sur PP-ST).
2. **G9** — walk-forward glissant pour confirmer les +0,35 %/mois de PP-ST.
3. Si le Lens devait être sauvé : abandonner le score 3/4 au profit de règles où
   les piliers ne se contredisent pas — par exemple P1 **ou** P2 selon qu'on
   cherche un retournement ou une continuation, jamais les deux ensemble.
