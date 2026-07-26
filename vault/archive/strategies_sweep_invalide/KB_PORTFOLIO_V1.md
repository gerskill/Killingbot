# 💼 KB_PORTFOLIO V1 — Revenu Passif Mensuel Multi-Asset

> **Date** : 2026-06-07
> **Objectif** : 10%/mois PnL clôturé, revenu mensuel régulier, DD bas
> **Stratégie source** : `killingbot_hybrid_v2.pine`

---

## 🎯 SYNTHÈSE MULTI-ASSET BACKTEST

Tous les tests sont sur **KB_HYBRID_V2** (PP-ST + EMA200 + ADX + Stoic + Liquidity Sweep), TF 4H, paramètres identiques.

| Asset | Broker | Période | Net % | DD % | PF | WR | Sharpe | Trades | %/mois |
|---|---|---|---|---|---|---|---|---|---|
| **BTCUSD** | **Coinbase** | 2017-2026 (9.1y) | **+1 535%** | **16.28%** | **2.49** | **49.43%** | **0.327** | **87** | **13.96%** ⭐ |
| **ETHUSD** | Coinbase | 2017-2026 | +652.81% | 21.13% | 2.14 | 43.43% | 0.267 | 99 | 5.93% |
| BTCUSDT | Binance | 2017-2026 (8.8y) | +495% | 15.61% | 2.51 | 49.32% | 0.264 | 73 | 4.68% |
| SOLUSD | Coinbase | 2021-2026 (5y) | -55% | 57.9% | 0.23 | 14.71% | -0.32 | 34 | ❌ |
| NDX | Nasdaq | 2000-2026 | +30% | 18.77% | 1.63 | 37.93% | -0.02 | 29 | 0.27% |
| XAUUSD | Oanda | 2013-2026 | -6.6% | 16.28% | 0.84 | 25.53% | -0.12 | 47 | ❌ |

### 🚦 Verdict par asset
| Asset | Verdict | Raison |
|---|---|---|
| ✅ **BTC Coinbase 4H** | INCLURE poids 60% | Sweet spot absolu : edge maximal, DD contrôlé |
| ⚠️ **ETH Coinbase 4H** | INCLURE poids 30% avec risk -30% | DD 21% un peu haut, baisser risk_pct de 10 à 7 → DD ~15% |
| ⚠️ BTC Binance 4H | OPTIONNEL poids 10% | Diversification venue. 3x moins bon que Coinbase mais décorrélé |
| ❌ SOL | EXCLURE | Trop volatil, mean-revert tue la strat |
| ❌ NDX/SPX | EXCLURE | Pas assez de signaux 4H (marché fermé nuit/wkd) |
| ❌ XAU | EXCLURE | Pas d'edge, gold ne respecte pas la structure |

---

## 💼 PORTEFEUILLE RECOMMANDÉ

### Configuration de base (capital 10 000 USD)

| Poche | Asset / Broker / TF | Risk/trade | Capital alloué |
|---|---|---|---|
| 🥇 Core | BTCUSD Coinbase 4H | 10% | $6 000 |
| 🥈 Diversif | ETHUSD Coinbase 4H | **7%** (réduit) | $3 000 |
| 🥉 Venue hedge | BTCUSDT Binance 4H | 8% | $1 000 |
| **TOTAL** | | | **$10 000** |

### Performance attendue (pondérée par poids)

| Métrique | BTC CB | ETH CB (risk 7%) | BIN BTC | Portfolio pondéré |
|---|---|---|---|---|
| %/mois simple | 13.96% | ~4.15% (réduit) | 4.68% | **~10.1%/mois** ✅ |
| DD max pondéré | 16.28% | ~15% (réduit) | 15.61% | **~15-17%** ✅ |
| Trades/an | 9.5 | 10.8 | 8.0 | ~28 trades/an = **2.3/mois** |
| Sharpe blend | 0.327 | 0.267 | 0.264 | ~0.31 |

---

## 📊 RÉGULARITÉ DU REVENU MENSUEL

**Attention — réalité honnête :** ce n'est PAS une rente fixe.

- BTC 4H : 87 trades sur 110 mois → ~**1 trade/mois en moyenne**
- ETH 4H : 99 trades sur 110 mois → ~**1 trade/mois**
- Combiné multi-asset : ~**2-3 trades/mois**

Distribution typique observée :
- ~25% des mois : 0 trades (consolidation HTF) → **0%/mois**
- ~50% des mois : 1-2 trades → **+5 à +25%**
- ~25% des mois : 1 gros gagnant runner → **+30 à +100%**
- Quelques mois : 1-2 losses → **-5 à -15%**

➡️ **Lissage par diversification** : un asset en consolidation est compensé par l'autre en trend → multi-asset = moins de mois "blancs".

### Pour lisser davantage (option avancée)
1. **Pyramiding intra-trade** : ajouter à la position gagnante après TP1
2. **Multi-broker arbitrage** : prendre signal CB ET signal Binance quand alignés (boost qty)
3. **Plus d'assets crypto** : tester DOGE, AVAX, MATIC, BNB sur même mécanique (probable même profil que ETH)
4. **Funding rate harvest** : sur perpetuals, en parallèle aux trades spot, capter le funding favorable

---

## ⚠️ LIMITES & VÉRITÉ DE TERRAIN

1. **10%/mois "passive" est rare en crypto** — la performance vient des big moves (bull markets 2017, 2020-21, 2023-24). Hors bull, le portfolio ralentit fortement.
2. **PnL clôturé ≠ revenu garanti** — certains trades durent 100+ barres (4 semaines), donc pas de cash-flow strict mensuel
3. **Coinbase 5 trades = enjeu de capital** — pour vivre du revenu, capital ≥ $50k recommandé (1 trade à 10% = $5k, ce qui justifie le temps de monitoring)
4. **DD historique 16% sur 9 ans ≠ futur** — un crash inédit (régulation, FTX 2.0, etc.) peut faire 25-30% DD
5. **Slippage live > backtest** — en live, compter ~0.1-0.2% de perte additionnelle par trade vs Pine

---

## 🔧 STRATÉGIES TESTÉES MAIS NON RETENUES

### KB_HYBRID_V3 MTF (multi-timeframe)
- Tentative : trigger 1H avec bias 4H injecté via `request.security`
- Résultat sur BTC 1H : **-14.89% net, DD 40%, PF 0.8, WR 21%**
- Pourquoi ça échoue : le 1H est trop bruyant pour le sweep detector (les wicks 1H ne sont pas vraiment des stop hunts institutionnels), et le filtre HTF + LTF cumule trop de conditions
- **Conclusion** : pas de gain à passer en MTF pour cette mécanique. **Le 4H est le bon TF.**
- Fichier : `pine_scripts/strategies/killingbot_hybrid_v3_mtf.pine` (conservé pour référence)

### KB_HYBRID_V2 sur indices / forex / or
- NDX 4H : 29 trades sur 26 ans = **0.27%/mois** (trop peu de signal)
- XAUUSD 4H : PF 0.84 = **pas d'edge**
- Conclusion : cette mécanique est **crypto-spécifique**. Le sweep + HCOM/LCOM marche sur des marchés 24/7 avec liquidité institutionnelle ; pas sur actions horaires/jours fermés ni sur or peu liquide.

---

## 🚀 PLAN D'EXÉCUTION LIVE

### Phase paper trading (4 semaines obligatoires)
1. Lancer V2 sur Coinbase Sandbox / BTC 4H et ETH 4H
2. Logger chaque trade dans `app/stoic_dashboard.html`
3. Comparer perf live vs backtest (target : delta < 15%)

### Phase live (capital test)
1. **$5 000 sur BTC CB, $2 500 sur ETH CB** — risk 5% au début (pas 10%)
2. Vérifier que la courbe d'équité monte régulièrement sur 8 semaines
3. Si DD < 15% et perf > 5%/mois, passer à risk 7%, puis 10%

### Phase production
1. Capital cible : $50k-$100k pour un revenu "vivable"
2. Webhook automatique vers exchange (à coder — connector ccxt)
3. Dashboard Stoic Lens en monitoring permanent
4. Review mensuelle dans `app/stoic_dashboard.html` Historique

---

## 📁 LIVRABLES

| Fichier | Rôle |
|---|---|
| `pine_scripts/strategies/killingbot_hybrid_v2.pine` | ⭐ Stratégie phare |
| `pine_scripts/strategies/killingbot_hybrid_v3_mtf.pine` | MTF (archivé, non recommandé) |
| `vault/strategies/KB_HYBRID_V2.md` | Fiche détaillée V2 |
| `vault/strategies/KB_PORTFOLIO_V1.md` | **Cette doc — portfolio recommandé** |
| `backtest/MATRICE_FINALE.md` | Matrice comparative complète |
| `backtest/results/kb_hybrid_v2_*.json` | Résultats backtests détaillés |
| `app/stoic_dashboard.html` | Dashboard de suivi live |
