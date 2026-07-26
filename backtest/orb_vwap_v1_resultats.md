# KB ORB+VWAP v1 — Résultats Backtest (2026-07-09)

Stratégie mécanique ORB 15min NY + filtres VWAP/EMA200. RR 1.2, risque 1.5%, max 2 trades/jour.
Fichier : `pine_scripts/strategies/kb_orb_vwap_v1.pine`

## Résultats par marché (22 mars → 9 juil 2026, 5m)

| Marché | P&L | WR | PF | Max DD | Trades |
|---|---|---|---|---|---|
| MES (S&P micro) | −15,60% | 42,2% | 0,758 | 26,15% | 90 |
| XAUUSD (Gold) | −5,10% | 47,2% | 0,922 | 16,87% | 72 |

**Verdict : PERD sur les 2 marchés.** Gold moins pire que S&P.

## vs Objectifs

| Objectif | MES | XAUUSD |
|---|---|---|
| 15%/mois | ❌ −4,5%/mois | ❌ −1,5%/mois |
| WR 60% | ❌ 42% | ❌ 47% |
| PF 1,6 | ❌ 0,76 | ❌ 0,92 |
| DD <20% | ❌ 26% | ✓ 17% |

## Leçons

1. **ORB mécanique brut = edge arbitré.** Le 83% WR du rapport hebdo (trading discrétionnaire) ne se transfère PAS en mécanique : 83% → 42%.
2. **Breakeven RR 1,2 = 45,5% WR.** MES à 42% = perte mécanique garantie.
3. **⚠️ PIÈGE Pine v6 : `margin_long` défaut = 100%** → ordres futures rejetés silencieusement (0 trades, aucune erreur). Fix : `margin_long=5, margin_short=5` dans strategy(). → À ajouter à PINE_ERRORS.md

## Optimisations à tester (ordre de priorité)

1. Long-only (biais haussier indices)
2. RR 2,0 + trailing stop (accepter WR bas, gains gros)
3. Filtre range OR : skip si range < 0,15% ou > 0,5% du prix
4. OR 30 min au lieu de 15
5. Filtre ADX ≥ 20 (gagnant sur PP-ST BTC 4H)

## Notes techniques MCP

- Injection Pine : `pbcopy` + clic éditeur + Cmd+A/Cmd+V via osascript = fiable. `pine_set_source` écrit dans un modèle invisible si 2 scripts ouverts.
- Ajout au chart : bouton "Ajouter au Graphique" via ui_evaluate, ou Cmd+Enter éditeur focus.
- Échelle flottante : après re-add, épingler via clic droit légende → Déplacer vers → Échelle droite (fusionner).
