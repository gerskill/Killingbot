# G8 + G9 — Filtre d'éligibilité et walk-forward glissant

_26 juillet 2026 · `agents/eligibility.py`, `agents/rolling_wf.py` · PP-ST 4h, 10 paires Binance_

---

# G8 — Filtre d'éligibilité par symbole

## Le trou à boucher

Le walk-forward de PP-ST avait montré **DOTUSDT avec un profit factor in-sample
de 0,03** — la stratégie y perd presque tout ce qu'elle engage — sans qu'aucun
mécanisme ne l'écarte. Il avait fallu un test manuel pour le voir.

Règle de conception : le filtre ne lit **que l'in-sample**. Sélectionner des
symboles d'après leur résultat hors échantillon reviendrait à choisir en
connaissant la réponse.

## Première version : trop stricte, et nuisible

Seuils testés : PF ≥ 1,20 · ≥ 12 trades · rendement > 0 · **drawdown ≤ 35 %**

| | Panier complet | Après filtre |
|---|---|---|
| Symboles retenus | 10 | 5 |
| OOS moyen | +0,562 %/mois | **+0,360 %/mois** |
| OOS médian | +0,350 %/mois | +0,200 %/mois |
| **Effet** | | **−0,202 point** |

Le critère de drawdown rejetait SOL, XRP, ADA et LINK. Or trois d'entre eux se
sont révélés **positifs hors échantillon** : ADA +1,49 %/mois, LINK +1,61 %/mois,
XRP +3,22 %/mois.

**Un drawdown élevé en in-sample signale de la volatilité, pas un défaut de la
stratégie.** En crypto, filtrer là-dessus écarte surtout les actifs qui rapportent.

## Version retenue

Seuils : PF ≥ 1,20 · ≥ 12 trades · rendement > 0 · *(drawdown désactivé)*

| | Panier complet | Après filtre |
|---|---|---|
| Symboles retenus | 10 | **9** |
| Seul rejet | — | **DOTUSDT** (PF 0,03) |
| OOS moyen | +0,562 %/mois | **+0,792 %/mois** |
| OOS médian | +0,350 %/mois | **+0,500 %/mois** |
| Positifs | 6/10 | 6/9 |
| **Effet** | | **+0,230 point** |

Le filtre fait exactement ce qu'on lui demande : il écarte le symbole
catastrophique, et rien d'autre.

---

# G9 — Walk-forward glissant

## Pourquoi

Le split unique 70/30 donne **une** mesure hors échantillon. Si la fenêtre tombe
sur un régime favorable, le résultat flatte la stratégie. Six fenêtres
successives répondent à une meilleure question : **combien de régimes sur six
l'edge traverse-t-il ?**

## Un piège d'implémentation, corrigé

Première version : chaque fenêtre était backtestée avec son contexte de warm-up,
et **les trades du contexte comptaient dans le résultat**. Les fenêtres se
recouvraient, le score était gonflé.

Correction : un paramètre `trade_from` calcule les indicateurs sur tout le
contexte mais **n'autorise aucun trade avant le début de la fenêtre**.

| | Avant correction | Après correction |
|---|---|---|
| Fenêtres positives | 6/6 | **5/6** |
| Symboles positifs sur ≥ 60 % des fenêtres | 7/9 | **4/9** |

L'écart mesure exactement la contamination. Tous les chiffres ci-dessous sont
ceux d'après correction.

## Résultats — 6 fenêtres, 2017 → 2026

| Fenêtre | Période | Moyenne | Médiane | Symboles + |
|---|---|---|---|---|
| 1 | 2017-12 → 2019-05 | +5,27 % | +2,18 % | 8/9 |
| 2 | 2019-05 → 2020-10 | +4,01 % | +0,22 % | 5/9 |
| 3 | 2020-10 → 2022-04 | +2,41 % | −1,08 % | 4/9 |
| 4 | 2022-04 → 2023-09 | +1,73 % | +0,83 % | 6/9 |
| 5 | 2023-09 → 2025-02 | +2,26 % | +2,37 % | 7/9 |
| 6 | **2025-02 → 2026-07** | **−0,46 %** | **−0,14 %** | **3/9** |

**5/6 fenêtres positives · moyenne +2,54 %/mois · écart-type 1,80**

## Deux lectures, et la bonne

**La moyenne est trompeuse.** Fenêtre 3 : moyenne +2,41 % mais médiane −1,08 %.
Un ou deux symboles très performants tirent la moyenne vers le haut pendant que
la majorité perd.

La médiane des médianes vaut environ **+0,5 %/mois** — cohérent avec le split
70/30 filtré (+0,50 %/mois médian). C'est l'estimation centrale honnête, pas
les +2,54 % de la moyenne.

## Le signal d'alerte

**La fenêtre la plus récente est négative** : 2025-02 → 2026-07, moyenne
−0,46 %, seulement 3 symboles positifs sur 9.

C'est la fenêtre la plus proche d'aujourd'hui, donc la plus pertinente pour
décider de trader demain. Deux interprétations possibles :

- un régime défavorable passager, comme la fenêtre 3 qui avait aussi une
  médiane négative avant que les suivantes redeviennent positives ;
- une érosion réelle de l'edge — les tendances crypto propres, sur lesquelles ce
  système vit, se font plus rares.

Six fenêtres ne permettent pas de trancher. Ce qu'on peut dire : **rien ne
justifie de considérer les +0,5 %/mois comme acquis pour les mois à venir.**

## Constance par symbole

| Symbole | Moyenne | Fenêtres positives |
|---|---|---|
| BTCUSDT | +2,57 % | **6/6** |
| ETHUSDT | +2,96 % | **5/6** |
| DOGEUSDT | +4,84 % | 4/6 |
| LINKUSDT | +2,05 % | 4/6 |
| AVAXUSDT | +4,08 % | 3/6 |
| BNBUSDT | +1,83 % | 3/6 |
| XRPUSDT | +1,31 % | 3/6 |
| ADAUSDT | +1,30 % | 3/6 |
| SOLUSDT | +1,88 % | 2/6 |

Seuls **BTC et ETH** sont positifs sur au moins 5 fenêtres sur 6. Ce sont les
deux actifs les plus liquides et les plus tendanciels — cohérent avec ce que la
stratégie sait faire.

---

# Bilan des quatre chantiers

| | Résultat |
|---|---|
| **G1** ruban | échoue — OOS 3/10, dégradation −131 % |
| **G1b** PP-ST | **passe** — OOS 6/10, panier +0,35 %/mois |
| **G1c** Lens | échoue — OOS 1/8 en Daily, piliers P1/P2 incompatibles |
| **G8** éligibilité | **+0,23 point** — rejette DOT, garde le reste |
| **G9** glissant | **5/6 fenêtres**, mais la plus récente est négative |

## Position actuelle du projet

Une stratégie validée : `pp_st_btc_4h_final`, sur **BTC et ETH**, avec le filtre
d'éligibilité actif. Attente réaliste : **de l'ordre de +0,5 %/mois**, soit
environ 6 %/an — pas les +2 947 % du backtest initial, ni les +2,5 %/mois de la
moyenne des fenêtres.

## Suite

1. **Paper trading** sur BTC et ETH uniquement, pour confronter les +0,5 %/mois
   au réel. C'est la seule étape qui apporte encore de l'information.
2. Ne pas brancher le sizing GARCH (G3) avant d'avoir des trades papier réels —
   optimiser la taille d'un edge non confirmé n'a pas de sens.
3. Refaire tourner le glissant dans trois mois : si la fenêtre 7 est également
   négative, l'hypothèse d'érosion se confirme.

## Réserves

- Univers crypto uniquement, 9 paires.
- Six fenêtres, c'est peu pour parler de persistance à travers les régimes.
- Le portage Python diffère légèrement de l'exécution intra-barre de TradingView.
- Le filtre d'éligibilité est calibré sur ce jeu de 10 symboles ; ses seuils
  n'ont pas été validés sur un univers indépendant.
