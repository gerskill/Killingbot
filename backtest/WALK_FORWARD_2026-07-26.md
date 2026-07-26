# G1 — Walk-forward du système ruban STOIC 1-2-3

_26 juillet 2026 · `agents/stoic_ribbon_wf.py` + `agents/validation.py`_
_Données yfinance · 70 % in-sample / 30 % out-of-sample · commission 0,04 % · slippage 2 bps_

## Pourquoi ce test

Tous les chiffres produits jusqu'ici (BTC +18,1 % en 8h, SPX +21,1 %, etc.) étaient
**in-sample** : mesurés sur la période même où les paramètres ont été choisis. Le
Strategy Tester de TradingView ne sait pas séparer IS et OOS. La logique Pine a donc
été portée en Python (`stoic_ribbon_wf.py`, port fidèle) pour faire tourner les
garde-fous de `validation.py`.

## Résultats — Daily, 2200 jours

| Symbole | IS (%/mois) | PF IS | OOS (%/mois) | PF OOS | Dégradation |
|---|---|---|---|---|---|
| BTC-USD  | +0,04 | 1,11 | −0,01 | 0,95 | −125 % |
| ETH-USD  | +0,17 | 1,54 | −0,02 | 0,92 | −112 % |
| SOL-USD  | +0,24 | 1,66 | +0,01 | 1,07 | −96 % |
| BNB-USD  | +0,07 | 1,26 | **+0,18** | **2,19** | +157 % |
| XRP-USD  | +0,04 | 1,10 | −0,19 | 0,41 | −575 % |
| ADA-USD  | +0,17 | 1,74 | −0,12 | 0,62 | −171 % |
| AVAX-USD | +0,07 | 1,23 | −0,01 | 0,95 | −114 % |
| LINK-USD | +0,09 | 1,30 | −0,19 | 0,41 | −311 % |
| DOT-USD  | +0,14 | 1,60 | −0,03 | 0,92 | −121 % |
| DOGE-USD | +0,21 | 2,36 | **+0,09** | **1,38** | −57 % |

**IS : 10/10 positifs. OOS : 3/10 positifs. Dégradation médiane −118 %.**

## Résultats — 8h, 720 jours (le « sweet spot » revendiqué)

| Symbole | IS (%/mois) | PF IS | OOS (%/mois) | PF OOS | Dégradation |
|---|---|---|---|---|---|
| BTC-USD  | +0,19 | 1,18 | −0,20 | 0,56 | −205 % |
| ETH-USD  | +0,21 | 1,27 | **+0,28** | **1,77** | +33 % |
| SOL-USD  | +0,60 | 1,65 | −0,56 | 0,43 | −193 % |
| BNB-USD  | +1,07 | 2,21 | −0,09 | 0,87 | −108 % |
| XRP-USD  | +0,45 | 1,35 | **+0,14** | **1,43** | −69 % |
| ADA-USD  | +0,13 | 1,12 | **+0,14** | **1,46** | +8 % |
| AVAX-USD | +0,71 | 2,36 | −0,15 | 0,75 | −121 % |
| LINK-USD | +0,29 | 1,36 | −0,12 | 0,78 | −141 % |
| DOT-USD  | +0,35 | 1,35 | −0,27 | 0,61 | −177 % |
| DOGE-USD | +0,29 | 1,37 | −0,40 | 0,34 | −238 % |

**IS : 10/10 positifs. OOS : 3/10 positifs. Dégradation médiane −131 %.**

## Deflated Sharpe

| Test | Meilleur candidat | Sharpe/trade | Essais | DSR | Verdict |
|---|---|---|---|---|---|
| Daily | DOGE | 0,383 | 10 | **0,865** | < 0,95 → non fiable |
| 8h    | AVAX | 0,404 | 10 | **0,861** | < 0,95 → non fiable |

Le meilleur résultat de chaque série n'est pas distinguable du meilleur tirage
parmi 10 essais. Corrigé du biais de sélection, l'edge disparaît.

## Monte Carlo — la nuance importante

**100 % de stabilité** dans les deux tests : perturber les paramètres de ±10 %
ne dégrade pas la performance (σ 0,04 à 0,11 %/mois).

Ce n'est donc **pas** du sur-apprentissage de paramètres. Les valeurs 10/20/50/200,
le buffer ATR, les cibles R — rien de tout ça n'est finement ajusté sur le bruit.

Le problème est ailleurs : **l'edge lui-même ne persiste pas d'une période à
l'autre**. Le système capture la tendance des marchés qui trendent ; quand le
régime change, il ne capture plus rien. C'est de la dépendance au régime, pas de
l'optimisation excessive.

## Verdict

Le système ruban **échoue le walk-forward**. Deux tests indépendants (Daily et 8h,
horizons et données différents) donnent la même signature :

- performance in-sample uniformément positive (10/10),
- effondrement out-of-sample (3/10),
- deflated Sharpe sous le seuil de fiabilité.

**Les chiffres antérieurs (+18,1 % BTC 8h, +21,1 % SPX) ne doivent plus être
présentés comme des résultats exploitables.** Ils décrivent une période passée,
pas une capacité prédictive.

## Réserves

- Source de données différente des tests Pine (yfinance vs Binance/TradingView) —
  écarts de prix et de volumes attendus, mais la direction du résultat est trop
  nette pour venir de là.
- Échantillons OOS minces (6 à 17 trades par symbole). Peu de trades ⇒ intervalle
  de confiance large. Le résultat isolé d'un symbole ne vaut rien ; c'est la
  cohérence des dix qui fait signal.
- Le split 70/30 est simple. Un walk-forward glissant (fenêtres successives)
  serait plus robuste, mais donnerait un verdict au mieux identique.

## Ce que ça change pour la suite

1. **G2 (grille 40 × 8) perd son sens en l'état.** Elargir une recherche
   in-sample sur un système qui ne passe pas le walk-forward ne produirait que
   des chiffres non exploitables de plus. À ne relancer qu'avec le split IS/OOS
   intégré à la boucle.
2. **Le walk-forward doit devenir la porte d'entrée**, pas la vérification
   finale. Toute stratégie candidate passe par `stoic_ribbon_wf.py` avant d'être
   présentée.
3. **`pp_st_btc_4h_final` reste à tester ainsi.** C'est la seule confirmée en
   direct — mais elle n'a jamais été soumise au walk-forward non plus. Sa
   validation est la prochaine étape prioritaire.
4. **`stoic_lens_pure_v2`** (17/20 symboles positifs en Daily) mérite le même
   traitement : c'est le meilleur candidat restant sur le critère de
   généralisation multi-marchés.
