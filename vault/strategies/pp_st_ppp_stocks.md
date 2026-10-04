---
type: strategie
statut: non-verifie
famille: PP-ST
actif: actions US (panier 10)
timeframe: 1D / 4H / 1H
direction: long
fichier_pine: pine_scripts/strategies/pp_st_ppp_stocks.pine
rapports: []
derniere_verif:
tags: [strategie, ppst, fondamental, ppp]
---

# PP-ST + EMA200 + ADX + filtre PPP — actions

> [!note] Non vérifié — aucun test n'a encore tourné
> Code prêt (Pine + walk-forward Python), mais le conteneur où il a été écrit n'avait
> accès à aucune source de données. À lancer en local ou au Strategy Tester.

## Idée
Garder le timing de [[pp_st_btc_4h_final]] (PP-ST + EMA200 + ADX) et n'entrer que sur
des actions « pas trop chères » au sens du **Potential Payback Period** : le nombre
d'années de bénéfices actualisés qu'il faut pour rembourser le prix.

$$ \text{PPP} = \frac{\ln[\text{PER}\cdot(q-1)+1]}{\ln q}, \qquad q = \frac{1+g}{1+r} $$

- g = r → PPP = PER
- g < r et PER ≥ (1+r)/(r−g) → jamais remboursé → pas d'entrée
- EPS ≤ 0 ou g inconnu → pas d'entrée

## Paramètres (fixés avant tout test)
| Paramètre | Valeur | Note |
|---|---|---|
| PPP max | 10 ans | seuil choisi a priori, ne pas l'optimiser sur l'OOS |
| r | 8 % | taux actions, pas le taux sans risque (plus flatteur) |
| g | CAGR EPS dilué annuel sur 3 exercices | plafonné à 25 % |
| EPS | dilué TTM | |

## Comment tester
**Python (walk-forward 70/30, filtre ON vs OFF, mêmes données)**
```bash
export SEC_USER_AGENT="Nom email@domaine"   # exigé par la SEC
python agents/ppp_wf.py --report             # NVDA AAPL MSFT AMZN GOOGL META TSLA JPM KO XOM × 1d/4h/1h
```
- Fondamentaux : SEC EDGAR, **point-in-time** (valeur utilisable au lendemain du dépôt,
  première publication seulement, EPS ramené en base d'actions actuelle via les splits)
- 1d sur 10 ans ; 4h/1h limités à 2 ans par yfinance → peu de trades, OOS fragile

**TradingView** — `pp_st_ppp_stocks.pine`, sur chaque actif × TF, lancer avec
« Activer le filtre PPP » ON puis OFF et noter les deux.

## Différences Pine / Python
- Pine : `request.financial` de TradingView (dates d'alignement non documentées → risque d'anticipation)
- Python : SEC point-in-time, plus strict. En cas d'écart, croire le Python sur la date, le Pine sur l'exécution.

## Critères pour passer en `walk-forward-ok`
- Filtre ON meilleur que OFF en OOS médian sur au moins un TF, **et** OOS positif sur ≥ 6/10 actifs
- Deflated Sharpe affiché par le script, pas seulement le meilleur actif

## Journal
- 2026-10-04 — fiche créée, code écrit, tests unitaires OK (formule, TTM, splits, pas d'anticipation). Aucun backtest réel.
