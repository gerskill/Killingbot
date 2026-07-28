# Bilan — reconstruction et validation du système @StoicTA

_28 juillet 2026 · Killingbot_

---

## Ce qui a été fait

Reconstruire le système de trading de @StoicTA à partir de ses publications, puis
le soumettre au même protocole de validation que les autres stratégies du projet.
Quatre stratégies ont été codées et testées, trois ont été rejetées, plusieurs
bugs de méthode ont été trouvés — dont deux qui auraient donné des conclusions
fausses.

---

## 1. Le système réel, tel qu'il le trade

Reconstitué à partir de trois sources : ses tweets des 21, 23 et 27 juillet, son
tableau de timeframes, et ses captures d'écran NQ (couleurs relevées au pixel).

**Séquence 1-2-3**

| Étape | Définition |
|---|---|
| Step 1 | impulsion qui inscrit un plus haut (ou plus bas) |
| Step 2 | creux du repli qui suit |
| Step 3 | clôture au-delà du Step 1 → direction confirmée |
| **PTB** | **la dernière bougie du repli qui suit le Step 3** |
| Entrée | **ordre stop** au-dessus du PTB high (ou sous le PTB low) |
| Stop | derrière le PTB · Cibles : 2R puis extension Fib 261,8 % |

Sa formulation exacte : *« The PTB is the last pullback candle. Bullish: buy stop
above the PTB high. When price trades through it, the Entry triggers. »*

**Contexte affiché** : ruban SMA 10/20, SMA 50, SMA 200 pointillée, PDH/PDL/PDC,
HCOM/LCOM (extrêmes de clôture du mois), Opening Range Londres et New York.

**Son tableau de timeframes** — chaque ligne se lit *carte → setup → timing* :

| Style | Carte | Setup | Timing | Gestion |
|---|---|---|---|---|
| Scalp | 15m | 5m | 1m | 5m |
| Day | 60m | 5m | 1m | 5m |
| Swing | Daily | 60m | 15m | 60m |
| Position | Weekly | Daily | 60m | Daily |

---

## 2. Les quatre stratégies testées

| Stratégie | Verdict | Mesure |
|---|---|---|
| **Stoic Lens** (4 piliers HCOM/LCOM) | ❌ échoue | OOS 1/8 en Daily, panier −0,05 %/mois |
| **Ruban 1-2-3** (première version) | ❌ échoue | OOS 3/10, dégradation −131 % |
| **SBS** (séquence 6 étapes) | ❌ rejetée | +2,3 % au mieux, toutes configurations |
| **1-2-3 avec entrée à la cassure** | ✅ meilleur candidat | OOS 10/10, 6/6 fenêtres glissantes |

### Pourquoi le Lens échoue — une cause structurelle

Ses quatre piliers déclenchent souvent pris isolément (P1 78 %, P2 56 %, P3 83 %,
P4 17 %). Mais **P1 et P2 décrivent des situations de marché opposées** :

- P1 long = le prix est près du **plus bas close du mois**
- P2 long = le prix est **en tendance haussière**, au-dessus des deux moyennes

Sur 920 barres en biais long, seules **154 (17 %)** ont aussi P1 long. Exiger 3
piliers sur 4 quand deux se contredisent revient à n'accepter que 3 à 14 trades
par fenêtre. Le « 17/20 symboles positifs » in-sample reposait sur des
échantillons de cette taille.

**Règle qui en découle** : avant de valider un système de score, mesurer le taux
de déclenchement **conjoint** des critères, pas seulement individuel.

---

## 3. Le résultat central — l'entrée PTB et les frais

L'hypothèse de départ était que le PTB, avec son stop serré, devait améliorer
l'espérance. Le test en crypto disait l'inverse. La raison n'est pas celle qu'on
croit.

| | Amplitude médiane d'une bougie | Levier pour risquer 1 % | **Coût aller-retour par trade** |
|---|---|---|---|
| Crypto 4h | 1,444 % | ×0,7 | **0,08 % de l'équité** |
| Crypto 5m | 0,129 % | ×7,7 | **0,93 % de l'équité** |

En 5 minutes crypto, **chaque aller-retour coûte presque autant que ce qu'on
risque**. Il faut gagner ~2R pour simplement rentrer dans ses frais.

Or son instrument n'a rien à voir :

| Instrument | Coût aller-retour (% du notionnel) |
|---|---|
| Crypto spot | 0,120 % |
| MNQ (micro) | ~0,003 % |
| NQ (full) | ~0,001 % |

**40 à 100 fois moins cher.** Le PTB est conçu pour ce régime de frais : un stop
d'une seule bougie n'a de sens que si les frais sont négligeables devant.

**Conclusion** : appliquer le PTB en crypto est une erreur de transposition, pas
un défaut de sa méthode. Rien de ce qui a été mesuré ne condamne son usage sur NQ.

---

## 4. Trois erreurs de méthode trouvées en route

Chacune aurait produit une conclusion fausse si elle n'avait pas été cherchée.

### Le score qui ne pouvait jamais atteindre 3

Sous NumPy 2.x, `+` entre booléens est un **OU logique**, pas une addition.

```python
score = p1 + p2 + p3 + p4   # vaut True, jamais 3
if score >= 3:              # True >= 3 est faux -> aucun trade
```

Diagnostic par le tunnel de filtres : biais 1680 barres → hors No Edge Zone 1288
→ setup présent 999 → **score ≥ 3 : jamais**. Sans ce comptage, la conclusion
aurait été « la stratégie ne prend aucun trade », au lieu de la tester.

### L'entrée Pine qui ne se déclenchait jamais

```pine
else if not na(LptbH) and high > LptbH
    Lst := 0                       // état remis à zéro ici
...
bool goLong = Lst == 1 and ...     // évalué après -> toujours faux
```

Pine exécute les blocs dans l'ordre. Corrigé en posant un **vrai ordre stop**
(`strategy.entry(..., stop=LptbH)`) reposé à chaque barre — ce qui est d'ailleurs
plus fidèle à sa règle que de détecter la traversée soi-même.

### Le walk-forward glissant qui se comptait deux fois

Chaque fenêtre était backtestée avec son contexte de warm-up, et **les trades du
contexte comptaient dans le résultat**. Corrigé avec un paramètre `trade_from`
qui calcule les indicateurs sur le contexte mais n'autorise aucun trade avant le
début de la fenêtre.

| | Avant | Après |
|---|---|---|
| Fenêtres positives | 6/6 | **5/6** |
| Symboles constants | 7/9 | **4/9** |

L'écart mesure exactement la contamination.

---

## 5. La métrique qui manquait

Le rendement mensuel devient ininterprétable quand le stop est serré : risquer
1 % avec un stop de 0,13 % implique un levier ×7,7, et le composé explose dans
les deux sens. C'est ainsi qu'on obtient −60 %/mois d'un côté et +48 %/mois de
l'autre — deux chiffres également faux.

**L'espérance en R est insensible au levier.** Elle isole la qualité du signal.
Ajoutée aux métriques (`expectancy_r`, `total_r`), elle a immédiatement changé la
lecture : en R, le PTB sur crypto 4h affiche une espérance **positive**
(+0,1164 R/trade, 8/10 symboles), là où le rendement mensuel le donnait perdant.

**Règle** : ne jamais comparer via un rendement composé deux stratégies dont les
stops n'ont pas le même ordre de grandeur.

---

## 6. L'amélioration apportée — `stoic_123_v2.pine`

Sa règle reste **inchangée**. Ce qui est ajouté est un garde-fou et un repli
documenté, tous deux fondés sur les mesures ci-dessus.

**Garde-fou de viabilité.** La stratégie refuse le trade quand la distance de
stop vaut moins de N fois le coût aller-retour estimé (6× par défaut, soit des
frais à 17 % du risque au maximum). C'est précisément ce qui manquait : en 5 min
crypto, rien n'arrêtait le saignement. Le refus est affiché sur le graphique.

**Deux mécaniques d'entrée, selon le régime de frais.**

| Marché | Entrée | Frais à renseigner |
|---|---|---|
| NQ / MNQ 5 min | **PTB** — sa règle | ~0,005 % |
| Crypto 4h et plus | **Step 2** — stop sous le creux | ~0,120 % |

**Ratio stop/coût affiché en continu** dans le tableau, avec code couleur — pour
voir avant d'entrer si le trade est viable sur cet instrument.

---

## 7. État du projet

| Stratégie | Statut |
|---|---|
| `pp_st_btc_4h_final` | validée walk-forward — OOS 6/10, ~+0,5 %/mois |
| `1-2-3 cassure` | meilleur candidat — 6/6 fenêtres, à confirmer |
| `stoic_123_v2` | codée, garde-fou intégré, à backtester sur NQ |
| Lens · Ruban v1 · SBS | rejetées, mesures documentées |

**Outils de validation construits** : `validation.py` (walk-forward, deflated
Sharpe, Monte Carlo), `eligibility.py` (filtre par symbole, +0,23 point),
`rolling_wf.py` (fenêtres glissantes isolées), `ptb_wf.py` (A/B des mécaniques
d'entrée, espérance en R).

**Ce qui reste à faire**, dans l'ordre :

1. Backtester `stoic_123_v2` sur **NQ/MNQ 5 min** — son terrain, jamais mesuré.
2. Confirmer le 1-2-3 cassure : filtre d'éligibilité + permutation sur les
   10 paires, pas seulement BTC.
3. Paper trading du gagnant. Pas d'optimisation supplémentaire avant.

---

## Réserves générales

- Univers crypto pour l'essentiel des tests ; son instrument (NQ) n'a pas encore
  été mesuré.
- Les portages Python reproduisent la logique Pine mais l'exécution intra-barre
  de TradingView diffère légèrement.
- Six fenêtres glissantes, c'est peu pour parler de persistance à travers les
  régimes.
- Le test de permutation montre qu'une part du résultat vient de la structure des
  données (+0,77 %/mois sur séries mélangées) et non du signal. Tout chiffre brut
  doit être lu net de cette part.
