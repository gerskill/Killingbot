# STOIC LENS PURE v2 — grille multi-marchés

_Date : 2026-07-22 · Script : `pine_scripts/strategies/stoic_lens_pure_v2.pine`_
_Capital 10 000 · commission 0,04 % · slippage 2 · risque 0,5 % (3/4) — 1 % (4/4)_

## 1. Cartographie timeframes — BINANCE:BTCUSDT, défauts

| TF | Période | P&L | DD | WR | Trades | PF |
|----|---------|-----|-----|-----|--------|-----|
| 1m | 16 j | — | — | — | 0 | — |
| 5m | 2,5 mois | −0,4 % | 0,8 % | 20 % | 5 | 0,55 |
| **15m** | 8 mois | **+8,3 %** | 1,7 % | 56 % | 41 | **3,09** |
| 1h | 2,5 ans | −0,7 % | 6,6 % | 28 % | 111 | 0,96 |
| 4h | 9 ans | −6,2 % | 11,2 % | 20 % | 127 | 0,67 |
| 8h | 9 ans | −1,4 % | 5,1 % | 24 % | 99 | 0,91 |
| **D** | 9 ans | **+6,8 %** | 1,9 % | 47 % | 36 | **2,45** |
| W | 9 ans | −1,0 % | 1,2 % | 0 % | 5 | 0 |

Deux zones viables : **15m** et **Daily**. L'entre-deux (1h–8h) est perdant.
Inverse des 3 autres stratégies du repo, qui mouraient sous 4h.

## 2. Grille 20 symboles — Daily, défauts

### Crypto — 5/5 positifs
| Symbole | P&L | DD | WR | Trades | PF |
|---|---|---|---|---|---|
| BTCUSDT | +6,81 % | 1,86 % | 47,2 % | 36 | 2,45 |
| ETHUSDT | +0,74 % | 0,55 % | 40,0 % | 5 | 2,48 |
| SOLUSDT | +2,16 % | 1,61 % | 34,8 % | 23 | 1,63 |
| BNBUSDT | +2,28 % | 4,35 % | 34,0 % | 50 | 1,35 |
| XRPUSDT | +2,14 % | 2,29 % | 40,0 % | 25 | 1,98 |

### Forex — 4/5 positifs
| Symbole | P&L | DD | WR | Trades | PF |
|---|---|---|---|---|---|
| EURUSD | +3,53 % | 0,78 % | 57,1 % | 14 | **3,98** |
| GBPUSD | +2,78 % | 2,38 % | 33,3 % | 24 | 1,71 |
| USDJPY | −2,17 % | 3,16 % | 16,7 % | 24 | 0,41 |
| AUDUSD | +2,19 % | 2,22 % | 30,9 % | 55 | 1,31 |
| USDCAD | +0,05 % | 3,02 % | 24,0 % | 25 | 1,01 |

### Indices — 4/5 positifs
| Symbole | P&L | DD | WR | Trades | PF |
|---|---|---|---|---|---|
| SPX | +8,26 % | 3,91 % | 36,5 % | 107 | 1,50 |
| NDX | +1,82 % | 1,91 % | 39,3 % | 28 | — |
| DJI | −1,84 % | 7,66 % | 28,9 % | 104 | <1 |
| DAX | +4,42 % | 0,65 % | 60,0 % | 10 | ~3 |
| NI225 | +3,37 % | 1,92 % | 38,1 % | 21 | 1,74 |

### Actions — 4/5 positifs
| Symbole | P&L | DD | WR | Trades | PF |
|---|---|---|---|---|---|
| AAPL | −2,68 % | 8,75 % | 31,6 % | 76 | 0,81 |
| MSFT | +7,16 % | 3,24 % | 45,3 % | 75 | 1,62 |
| NVDA | +1,77 % | 5,15 % | 40,0 % | 60 | 1,17 |
| GOOGL | +1,93 % | 2,00 % | 34,3 % | 35 | 1,42 |
| AMZN | +2,75 % | 3,71 % | 34,4 % | 64 | 1,28 |

**Bilan : 17/20 positifs, aucun DD > 8,8 %.**
Perdants : USDJPY, DJI, AAPL.

## 3. Tuning sur SPX (107 trades, meilleur échantillon)

| Réglage | P&L | DD | Trades | PF |
|---|---|---|---|---|
| Défauts (score≥3, tol 0,5, noEdge 0,35) | +8,26 % | 3,91 % | 107 | 1,50 |
| score ≥ 4 (Golden seul) | −0,38 % | 7,36 % | 37 | <1 |
| tol 1,0×ATR | +10,77 % | 4,10 % | 131 | ~1,6 |
| tol 1,5×ATR | +6,93 % | 4,69 % | 154 | ~1,3 |
| **tol 1,0 + noEdge 0** | **+24,18 %** | **2,77 %** | 113 | **2,19** |
| tol 1,0 + noEdge 0,15 | +8,91 % | 4,08 % | 132 | 1,39 |

Deux enseignements contre-intuitifs :
- Exiger 4/4 (Golden SBS) **détruit** la performance. Le 3/4 est le bon seuil.
- Le filtre No Edge Zone « milieu de range » **coûte** de la performance sur SPX.

## 4. Validation croisée du réglage SPX-optimisé (tol 1,0 · noEdge 0)

| Symbole | Défauts | Réglage SPX | Verdict |
|---|---|---|---|
| SPX | +8,26 % / PF 1,50 | **+24,18 % / PF 2,19** | ✅ |
| BTCUSDT | +6,81 % / PF 2,45 | **−0,50 % / PF 0,85** | ❌ cassé |
| EURUSD | +3,53 % / PF 3,98 | +8,57 % / PF 2,22 | ⚠️ P&L ↑, PF ↓ |

**Conclusion : pas de réglage universel.** Le tuning SPX est partiellement
overfit — il triple la perf sur SPX mais rend BTC perdant. Les paramètres par
défaut restent le meilleur compromis global (17/20 positifs).

## 5. Recommandations

1. **Garder les défauts** comme base multi-marchés. C'est le seul réglage validé
   sur les 4 classes d'actifs.
2. **Tuner par classe d'actif**, pas globalement : indices supportent une
   tolérance large sans No Edge Zone, la crypto a besoin du filtre.
3. **Ne pas monter à 4/4** malgré l'intuition du protocole — testé, contre-productif.
4. Avant tout usage réel : walk-forward sur sous-période non utilisée, puis
   paper trading. Tous les chiffres ci-dessus sont in-sample.

## 6. Réserves

- Le 15m ne dispose que de ~8 mois d'historique (limite TradingView intraday) :
  41 trades, échantillon faible malgré un PF 3,09 séduisant.
- Plusieurs symboles ont < 30 trades (ETH 5, DAX 10, EURUSD 14) — PF élevés
  mais non significatifs statistiquement.
- ~6 combinaisons testées sur SPX → biais de sélection sur le +24,18 %.
