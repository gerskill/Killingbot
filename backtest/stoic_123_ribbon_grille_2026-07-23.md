# STOIC 1-2-3 RIBBON (strat) — grille

_Date : 2026-07-23 · `pine_scripts/indicators/stoic_123_ribbon.pine` (version strat)_
_Système réel de @StoicTA : ruban SMA 10/20 + SMA 50/200, séquence 1-2-3._
_Capital 10 000 · commission 0,04 % · slippage 2 · risque 0,5-1 %_

## 1. Cartographie timeframes — BTCUSDT, défauts

| TF | P&L | DD | WR | Trades | PF |
|----|-----|-----|-----|--------|-----|
| 5m  | −1,8 % | 7,1 %  | 35 % | 151 | 0,92 |
| 15m | −11,8 %| 18,4 % | 29 % | 452 | 0,87 |
| 1h  | +5,9 % | 14,3 % | 31 % | 750 | 1,04 |
| 4h  | +13,0 %| 13,3 % | 33 % | 793 | 1,08 |
| **8h**  | **+18,1 %**| 8,8 %  | 36 % | 367 | **1,28** |
| D   | +8,2 % | 4,2 %  | 35 % | 114 | 1,39 |
| W   | +2,6 % | 2,0 %  | 33 % | 12  | 2,03 |

Profil opposé au Stoic Lens (HCOM/LCOM) : ici **toute la moitié haute gagne**,
le bas (5m/15m) perd. Logique — le système ruban est trend-following pur.
Sweet spot = **8h** (meilleur compromis P&L/PF/DD).

## 2. Grille multi-marchés — 8h, défauts

| Symbole | P&L | DD | WR | Trades | PF | Verdict |
|---|---|---|---|---|---|---|
| BTCUSDT | +18,1 % | 8,8 % | 36 % | 367 | 1,28 | ✅ |
| ETHUSDT | +9,8 %  | 14,0 %| 35 % | 420 | ~1,15 | ✅ |
| SPX     | +21,1 % | 8,4 % | 38 % | 281 | ~1,3 | ✅ |
| EURUSD  | −9,4 %  | 20,8 %| 30 % | 646 | 0,93 | ❌ |
| NVDA    | −42,9 % | 60,3 %| 39 % | 292 | <1 | ❌❌ |

## 3. Lecture

- **Crypto + indices en 8h : ça marche** (trend-following sur actifs qui trendent).
- **Forex : cassé** (EURUSD mean-revert, le ruban se fait retourner).
- **Actions en 8h intraday : catastrophe** (NVDA −43 %/DD 60 %). Les bougies 8h
  d'actions coupent les sessions → gaps overnight au milieu des barres → le
  système ruban achète les gaps qui se referment. Pour les actions, utiliser
  **Daily**, pas l'intraday.

## 4. Recommandations

1. **Crypto** : 8h, défauts. BTC +18 %, ETH +10 %.
2. **Indices** : 8h fonctionne (SPX +21 %), mais tester Daily aussi (pas de gaps).
3. **Actions** : jamais en intraday. Daily uniquement.
4. **Forex** : éviter ce système (momentum inadapté au mean-reversion FX).

## 5. Réserves

- 100 % in-sample.
- Tuning des paramètres non fait (index d'inputs MCP non fiables cette session ;
  in_16 coupait tous les trades). À affiner manuellement : needHTF, slBufAtr, brkLook.
- WR structurellement bas (30-38 %) : la perf vient de quelques gros trends.
  Sensible aux périodes sans tendance.
- Le "3" codé = interprétation standard (pullback ruban + cassure structure).
  La règle d'entrée exacte de StoicTA n'est pas 100 % documentée (une seule
  capture de son chart).
