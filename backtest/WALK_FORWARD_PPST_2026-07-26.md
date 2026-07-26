# G1b — Walk-forward de `pp_st_btc_4h_final.pine`

_26 juillet 2026 · `agents/ppst_wf.py` + `agents/validation.py`_
_Données : API Binance (même source que le test Pine) · 4h · 2017-10 → 2026-07 · 19 189 barres_
_70 % in-sample / 30 % out-of-sample · commission 0,1 % · slippage 1 · sizing 100 % équité_

## Pourquoi ce test

`pp_st_btc_4h_final` était la seule stratégie confirmée en direct dans le
Strategy Tester (+2947 %), mais **jamais soumise au walk-forward**. Deux questions
restaient ouvertes :

1. La performance survit-elle hors de la période où les paramètres ont été choisis ?
2. Un système **long only** sur un actif qui a fait ×9 bat-il seulement le buy & hold ?

## Résultats par symbole

| Symbole | IS (%/m) | PF IS | OOS (%/m) | PF OOS | Dégrad. | Total | vs Buy & Hold |
|---|---|---|---|---|---|---|---|
| BTCUSDT  | +3,88 | 5,33 | **+0,50** | **1,40** | −87 % | +1653 % | **+695 %** ✅ |
| ETHUSDT  | +3,39 | 6,03 | **+1,63** | **3,08** | −52 % | +1625 % | **+1087 %** ✅ |
| SOLUSDT  | +2,35 | 1,50 | −0,99 | 0,23 | −142 % | +219 % | −2259 % ❌ |
| BNBUSDT  | +2,20 | 4,02 | **+0,20** | **1,17** | −91 % | +438 % | −33203 % ❌ |
| XRPUSDT  | +0,22 | 1,23 | **+3,22** | **1,79** | +1364 % | +202 % | **+182 %** ✅ |
| ADAUSDT  | +1,78 | 2,22 | **+1,49** | **1,58** | −16 % | +442 % | **+478 %** ✅ |
| AVAXUSDT | +5,55 | 2,65 | −0,22 | 0,74 | −104 % | +1283 % | **+1247 %** ✅ |
| LINKUSDT | +1,92 | 1,81 | **+1,61** | **1,90** | −16 % | +470 % | −1154 % ❌ |
| DOTUSDT  | −1,75 | 0,03 | −1,51 | 0,00 | +14 % | −71 % | +2 % ✅ |
| DOGEUSDT | +6,08 | 2,25 | −0,31 | 0,72 | −105 % | +3115 % | **+1271 %** ✅ |

**OOS positif : 6/10 · bat le buy & hold : 7/10 · dégradation médiane −70 %**

## Niveau panier

| Mesure | Valeur |
|---|---|
| OOS moyen | **+0,56 %/mois** (≈ +6,9 %/an) |
| OOS médian | **+0,35 %/mois** (≈ +4,3 %/an) |
| Écart-type | 1,36 |
| Pire symbole | −1,51 %/mois (DOT) |
| Meilleur | +3,22 %/mois (XRP) |

**Le panier reste positif out-of-sample.** C'est la différence de fond avec le ruban.

## Comparaison directe avec le ruban

| | Ruban 1-2-3 | **PP-ST** |
|---|---|---|
| OOS positif | 3/10 | **6/10** |
| Dégradation médiane | −131 % | **−70 %** |
| Panier OOS | négatif | **+0,35 %/mois médian** |
| Monte Carlo | 100 % stable | 100 % stable |
| Deflated Sharpe | 0,86 | 0,03 |
| **Verdict** | **échoue** | **survit, avec réserves** |

## Deflated Sharpe : 0,025 — pourquoi si bas

Le DSR répond à une question précise : *le meilleur symbole se distingue-t-il du
meilleur tirage parmi 10 essais ?* Ici la dispersion inter-symboles est énorme
(PF de 0,03 sur DOT à 6,03 sur ETH). Plus la dispersion est grande, plus le
« meilleur attendu par hasard » est haut — et BTC ne s'en détache pas.

**Ce que ça dit** : sélectionner le meilleur symbole après coup n'a aucune valeur
statistique. **Ce que ça ne dit pas** : que le système ne marche pas. La question
pertinente pour une stratégie appliquée uniformément à un panier est la moyenne
du panier — et elle est positive.

## Les trois problèmes réels

### 1. Le système coupe les gros gagnants

Sur les trois symboles où il perd contre le buy & hold, l'écart est brutal :

- **BNB** : buy & hold +33 641 %, stratégie +438 %
- **SOL** : buy & hold +2478 %, stratégie +219 %
- **LINK** : buy & hold +1624 %, stratégie +470 %

Caractérisation honnête : un système de suivi de tendance long only avec sortie
sur cassure d'EMA200 **sort des mouvements paraboliques trop tôt**. Il gagne
contre le buy & hold sur les actifs qui corrigent (ADA −36 % en B&H, stratégie
+442 %), et perd massivement sur ceux qui montent sans respirer.

### 2. Aucune protection quand le système ne convient pas au symbole

**DOT : PF 0,03 en in-sample.** Un profit factor de 0,03 signifie que la
stratégie perd presque tout ce qu'elle engage. Aucun garde-fou ne la coupe
automatiquement — il a fallu ce test pour le voir.

### 3. La dégradation reste forte

−70 % de médiane. Sur BTC : +3,88 %/mois in-sample → **+0,50 %/mois**
out-of-sample. Le chiffre reste positif, mais il faut diviser l'attente par
sept par rapport à ce que le backtest suggérait.

## Verdict

`pp_st_btc_4h_final` **passe le walk-forward, contrairement au ruban** — mais
l'edge réel est bien plus modeste que le +2947 % ne le laissait croire :
de l'ordre de **+0,35 à +0,56 %/mois** au niveau panier, pas +3,88 %.

C'est la première stratégie du projet dont la performance survit hors échantillon.
Elle reste exploitable, à condition d'accepter :

- un rendement attendu autour de **4 à 7 %/an** (pas ×30),
- une sélection de symboles **décidée à l'avance**, jamais après coup,
- l'exclusion explicite des symboles où le PF in-sample est dégradé (DOT).

## Réserves

- Échantillons OOS minces : 7 à 18 trades par symbole. C'est la cohérence des
  dix qui fait signal, pas un résultat isolé.
- Le split 70/30 est unique. Un walk-forward glissant sur fenêtres successives
  serait plus robuste.
- Le port Python reproduit la logique Pine (pivots, bandes à cliquet, filtres
  EMA200 + ADX) mais la mécanique d'exécution intra-barre de TradingView diffère
  légèrement. Le total obtenu (+1653 % BTC) est du même ordre que le +2947 %
  du Strategy Tester ; l'écart vient des coûts et du timing de remplissage.
- Univers crypto uniquement. Le comportement sur actions, indices et forex
  n'est pas testé ici.

## Suite logique

1. **Walk-forward glissant** (fenêtres successives) pour confirmer les +0,35 %/mois.
2. **`stoic_lens_pure_v2`** — même traitement, c'est le dernier candidat non testé.
3. **Filtre d'éligibilité par symbole** : refuser automatiquement tout symbole
   dont le PF in-sample est sous un seuil (le cas DOT).
4. Le sizing GARCH (G3) ne devient utile qu'après ces étapes.
