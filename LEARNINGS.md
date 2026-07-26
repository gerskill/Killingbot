# 🧠 LEARNINGS — Killingbot Research (2026)
> Synthèse des backtests avant remise à zéro

---

## ✅ CE QUI FONCTIONNE

### Signal : EMA 7/21 crossover
- **LE seul trigger viable** — tout autre trigger (TK cross, BB break, Kijun bounce) = trop de trades, WR effondré
- Ichimoku + BB = **filtres uniquement**, jamais triggers

### Trailing Stop ATR×2.0 > TP fixe
- WR passe de ~35-40% → **54-60%**
- DD réduit, PF amélioré
- Laisse courir les vrais trends au lieu de couper trop tôt

### Assets viables (EMA×Kijun, 2023+)
| Asset | TF | %/mois | DD | PF |
|-------|-----|---------|-----|-----|
| SOL/USDT | Daily | 7.45% | 21.82% | 1.984 |
| NVDA | 1H | 2.82% | 12.06% | 1.832 |
| GBPUSD | 1H | 2.65%/an | 4.47% | 2.135 |
| AUDUSD | Daily | 6.29%/an | 7.38% | 3.87 |
| PDD | 4H | ~3%/mois | 29% | 2.73 |

### Règles clés validées
- **Crypto → Daily uniquement** (1H/4H trop choppy, whipsaw fatal)
- **Stocks → 1H** (Daily trop peu de trades)
- **Forex → 1H ou Daily** selon la paire
- **Long Only systématiquement** (L+S détruit les résultats sur assets trending)
- **EMA sep min 0.15%** (bloque faux croisements)
- **ATR min 0.3%** (bloque zones compressées)
- **Cooldown 2-3 bars** (anti-whipsaw)

---

## ❌ CE QUI NE FONCTIONNE PAS

- Ichimoku comme trigger → 6547 trades, WR 19%
- BB breakout comme trigger → trop de faux signaux
- L+S sur crypto → bear market 2022 = catastrophe
- SOL/ETH/BTC sur 1H → whipsaw permanent même en bull
- ETH Daily 2023+ → -15.49%, sous-performance structurelle
- AMD, META 1H → choppy, PF < 1.4

---

## 🎯 PARAMÈTRES OPTIMAUX PROUVÉS (base pour futures stratégies)

```
EMA fast/slow : 7 / 21
Kijun : 26
ATR : 14, mult 1.5-2.0
Trailing stop : ATR × 2.0 / syminfo.mintick
EMA sep min : 0.15% (forex) | 0.20% (stocks)
ATR min : 0.3%
Cooldown : 2-3 bars
Commission crypto : 0.1% | Forex : 0.005% | Stocks : 0.1%
Slippage : 1 (crypto/forex) | 2 (stocks)
```

---

## 💡 IDÉES NON TESTÉES (pour futures stratégies)

1. **EMA200 comme filtre macro** → trade seulement si price > EMA200 Daily (coupe 2022 bear)
2. **RSI divergence** comme filtre (ne pas rentrer si RSI diverge)
3. **Volume spike** comme filtre (rentrer seulement avec volume > moyenne × 1.5)
4. **Structure de marché** (HH/HL) comme filtre directionnel macro
5. **Shorts sélectifs** uniquement si EMA200 Daily baissière (filtre macro bear)

---

## 🔌 INFRASTRUCTURE OPÉRATIONNELLE

- TradingView MCP : inject Pine + lire résultats via DOM ✅
- Webhook server Flask port 5001 ✅
- DOM scraping : `t.indexOf('Métriques\n')` → extrait P&L, DD, trades ✅
- Agents Python (orchestrator, memory, strategy_explorer) ✅

---
*Généré : 28 Mai 2026 — avant remise à zéro des stratégies*

---

## 🚀 DÉBUT COLLECTE OOS — 2026-07-19

**Toute donnée antérieure au 2026-07-19 08:15 UTC est PRÉ-OOS** (tests + position legacy KB_15m). Archivée dans `vault/archive/{signals_log,trades}_pre_oos_2026-07-19.*`. `signals_log.jsonl` et `trades.csv` repartent vides.

- Stratégie active : PP-ST + EMA200 + ADX BTC 4H (`pp_st_btc_4h_final.pine`, script TV `PP_ST_BTC_4H_FINAL`, pine_id `USER;b92db3a4...`)
- Alerte : 5179322809, payload JSON setup B, webhook ngrok → Flask 5001
- Position legacy KB_15m (14/07, TF 15) clôturée manuellement via exit_sync (−4.18$)
- Pipeline accepte `dir` : `long`/`buy` = entrée, `sell`/`flat`/`close` = clôture sync (stratégie long-only)
- **Règle** : ne toucher ni paramètres ni filtres pendant 2-4 semaines de collecte

## ⚠️ PIÈGE INFRA — iCloud évince les fichiers du projet (2026-07-19)

Projet dans `~/Documents` = synchronisé iCloud. macOS évince les fichiers peu utilisés (flag `dataless`) → lecture aléatoirement en `OSError: [Errno 11] Resource deadlock avoided`. A causé : 500 intermittents sur le webhook (écriture `signals_log.jsonl`) + crash-loop PM2 (lecture `.env` au boot, 7488 restarts).

- Diagnostic : `ls -lO <fichier>` → flag `dataless`
- Fix ponctuel : `brctl download <fichiers>` (fait le 19/07 sur .env, config, logs, vault/, core/, agents/)
- Fix durable : Finder → clic droit dossier Killingbot → « Garder téléchargé », ou déplacer le projet hors de Documents
- Mitigation code : `log_signal()` et wrap générique = best-effort, un échec d'écriture ne 500 plus jamais
