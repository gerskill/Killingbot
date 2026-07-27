# Entrée PTB de @StoicTA — testée, et ce qu'elle a révélé

_27 juillet 2026 · `agents/ptb_wf.py` · BTC + 9 alts, 4h Binance, 2017-2026_
_Source : tweet du 27 juillet + schéma annoté + exemple NQ 5 min_

## La règle, telle qu'il l'énonce

> « Step 3 confirms direction and sets the Step 3 High or Low. Price pulls back.
> The PTB is the last pullback candle.
> Bullish: buy stop above the PTB high. Bearish: sell stop below the PTB low.
> When price trades through it, the Entry triggers. »

Le schéma complète : **Step 1** impulsion → **Step 2** creux du repli →
**Step 3** clôture au-dessus du plus haut de Step 1 (direction confirmée) →
repli → **PTB** dernière bougie de repli → **entrée sur ordre stop** au-dessus
de son plus haut.

C'est la pièce qui manquait : jusqu'ici mes versions entraient **au marché sur
la cassure**. Lui attend le repli et place un ordre stop.

## Mon hypothèse — et pourquoi elle était fausse

Raisonnement de départ : entrer sur ordre stop après un repli donne un **stop
plus serré** (sous le PTB au lieu de sous Step 2), donc un meilleur rapport
gain/risque, donc une meilleure espérance à taux de réussite égal.

Le test dit l'inverse.

| Entrée | OOS positif | OOS médian | Taux de réussite | Trades (IS) |
|---|---|---|---|---|
| **PTB** (la sienne) | 6/10 | +0,51 %/mois | **19,4 %** | 383 |
| **Cassure** (au marché) | **10/10** | **+1,25 %/mois** | **40,6 %** | 260 |

**Écart : −0,74 point de %/mois en défaveur du PTB.**

Le taux de réussite s'effondre de moitié. Le stop serré sous le PTB se fait
sortir par le bruit ordinaire d'une bougie 4h crypto ; le stop large sous le
creux de Step 2 y survit. Le gain théorique en rapport gain/risque ne compense
pas la perte en taux de réussite.

### Ce que ça ne dit pas

**Sa méthode n'est pas invalidée.** Il trade le NQ en 5 minutes — instrument et
structure de bruit différents. Sur des futures d'indice à forte liquidité, la
distance PTB haut/bas est probablement large par rapport au bruit ; en crypto 4h,
elle ne l'est pas. Le résultat est : **cette mécanique ne se transpose pas en
crypto 4h**, pas : « elle ne marche pas ».

## Le résultat inattendu

En construisant le témoin (« entrée à la cassure »), j'ai obtenu la meilleure
stratégie du projet à ce jour — meilleure que PP-ST.

| | PP-ST (validée) | **1-2-3 cassure** |
|---|---|---|
| OOS positif (70/30) | 6/10 | **10/10** |
| Fenêtres glissantes positives | 5/6 | **6/6** |
| Écart-type entre fenêtres | 1,80 | **0,38** |
| Dernière fenêtre (2025-02 → 2026-07) | **−0,46 %** | **+1,14 %** |
| Symboles positifs ≥ 60 % des fenêtres | 4/9 | **10/10** |
| Moyenne vs médiane | +2,54 % vs ~+0,5 % (divergent) | +1,70 % vs +1,61 % (cohérent) |

Ce qui la distingue du ruban 1-2-3 déjà testé et rejeté (`stoic_123_ribbon`,
OOS 3/10) : **le placement du stop et la cible**. Ici, stop sous le creux de
Step 2 et cible en extension de Fibonacci 261,8 % — là où l'ancienne version
utilisait un stop basé sur la SMA20 et des cibles en R fixes.

### Détail des fenêtres glissantes

| Fenêtre | Période | Médiane | Symboles + |
|---|---|---|---|
| 1 | 2017-12 → 2019-05 | +2,11 % | 10/10 |
| 2 | 2019-05 → 2020-10 | +2,29 % | 10/10 |
| 3 | 2020-10 → 2022-04 | +1,96 % | 9/10 |
| 4 | 2022-04 → 2023-09 | +1,58 % | 10/10 |
| 5 | 2023-09 → 2025-02 | +1,61 % | 10/10 |
| 6 | 2025-02 → 2026-07 | **+1,10 %** | 9/10 |

Aucune fenêtre négative, y compris la plus récente — celle où PP-ST décroche.

## Trois contrôles anti-biais

**1. Buy & hold** — BTC : +1032 % contre +685 % en achat-conservation.
**+347 points d'écart**. Ce n'est pas du biais haussier déguisé.

**2. Contribution des ventes à découvert** — longs seuls +1,40 %/mois (219 trades),
avec les shorts +2,33 %/mois (400 trades). Les shorts **ajoutent** de la
performance ; le système ne vit pas que de la hausse du marché.

**3. Test de permutation** — mêmes règles appliquées à 12 séries dont les
rendements ont été mélangés (la forme de chaque bougie est conservée, seule la
dépendance temporelle est détruite) :

| | Résultat |
|---|---|
| Bruit — moyenne | **+0,77 %/mois** |
| Bruit — écart-type | 0,36 |
| Réel | +2,33 %/mois |
| **z-score** | **4,3 → distinct du bruit** |

**Nuance importante** : les séries mélangées sont **elles aussi positives, 12
fois sur 12**. Environ **+0,77 %/mois provient de la structure des données**
(dérive haussière, forme des bougies) et non du signal. L'edge réellement
attribuable aux règles est donc de l'ordre de **+1,5 %/mois**, pas +2,33 %.

C'est un contrôle que je n'avais fait sur aucune stratégie précédente. Il
devrait devenir systématique : sans lui, on attribue au signal ce qui vient du
marché.

## Réponse à la question posée

**Faut-il inclure l'entrée PTB dans le Stoic Lens ?**

**Non**, pour deux raisons distinctes :

1. **La mécanique PTB ne se transpose pas** en crypto 4h — mesuré, −0,74 point.
2. **Le Lens n'a pas un problème d'entrée.** Il échoue parce que ses piliers P1
   et P2 sont directionnellement incompatibles (17 % de recouvrement), ce qui le
   limite à 3-14 trades par fenêtre. Changer la façon d'entrer ne corrige pas un
   filtre qui ne laisse presque rien passer.

**Ce qu'il faut retenir à la place** : le détour a produit une stratégie qui
surpasse PP-ST sur tous les critères. C'est elle qui mérite la suite.

## Réserves

- Univers crypto, 10 paires, un seul timeframe (4h).
- Le mode « cassure » n'a pas été confronté au filtre d'éligibilité (G8) ni au
  test de permutation sur l'ensemble du panier — seulement sur BTC.
- La cible en extension 261,8 % est reprise de son chart mais n'a pas été
  comparée à d'autres niveaux ; elle n'est pas optimisée, ce qui est plutôt sain.
- Aucun paramètre n'a été ajusté après lecture des résultats hors échantillon.

## Suite

1. Passer le mode « cassure » au **filtre d'éligibilité** et au **test de
   permutation sur les 10 paires**, pas seulement BTC.
2. Le comparer à PP-ST sur **fenêtres identiques** avant de changer de référence.
3. Si confirmé : c'est cette stratégie qui part en paper trading, pas PP-ST.
4. Tester la mécanique PTB **sur 5 min**, son terrain d'origine — pour savoir si
   l'échec vient du timeframe ou de la mécanique.
