# 🏆 Meilleures Stratégies KB

_Mise à jour : 2026-05-14 08:30_

> ⚠️ **INVALIDÉ — 2026-07-18** : Toutes les entrées de ce tableau proviennent du même sweep
> automatique de 35 variantes (`agents/strategy_explorer.py`). Le chiffre `[[KB_15m]]`
> (rang 4 : "+7.9%/mois, DD 5.7%, PF implicite élevé, WR 67%, Sharpe 7.57, 414 trades")
> a été re-testé en direct sur TradingView (Strategy Tester, BTCUSDT 15m, données réelles
> disponibles) le 2026-07-18 et s'est révélé **totalement faux** :
> P&L réel −8.76%, Drawdown 8.98%, **Profit Factor 0.465 (stratégie perdante)**,
> Win Rate réel 35.23% (204/579 trades), Sharpe **−1.243**, 579 trades (pas 414).
>
> Aucune des 9 autres entrées n'a été re-vérifiée. **Ne faites confiance à aucun chiffre
> de ce fichier tant qu'il n'a pas été recompilé et testé en direct dans le Strategy Tester
> TradingView** (pas de simulation, pas d'estimation d'agent — le vrai backtest, lu à l'écran).
> Voir `[[AGENT_LOG]]` pour la méthodologie du sweep d'origine et évaluer si les mêmes
> biais (période non précisée, absence de vérification live) s'y sont glissés.

| Rang | Stratégie | %/mois (⚠️ non vérifié) | WR | Trades | Drawdown | Sharpe |
|------|-----------|--------|-----|--------|----------|--------|
| 1 | [[KB_LOOSE_RR2.5_RR3.0]] | 8.0% | 66% | 231 | -12.2% | 7.06 |
| 2 | [[KB_1h]] | 7.9% | 67% | 420 | -6.1% | 7.51 |
| 3 | [[KB_RR4]] | 7.9% | 65% | 214 | -12.2% | 6.43 |
| 4 | ~~[[KB_15m]]~~ **SUPPRIMÉ 2026-07-18** — perdant en réel (PF 0.465) | ~~7.9%~~ | ~~67%~~ | ~~414~~ | ~~-5.7%~~ | ~~7.57~~ |
| 5 | [[KB_RR5]] | 7.8% | 62% | 208 | -14.6% | 5.51 |
| 6 | [[KB_LOOSE_RR2.5_RR3.0_RSI]] | 7.8% | 68% | 215 | -11.5% | 7.45 |
| 7 | [[KB_LOOSE_RR2.5_RSI]] | 7.5% | 68% | 225 | -10.4% | 7.65 |
| 8 | [[KB_LOOSE_RR2.5]] | 7.5% | 66% | 241 | -11.8% | 7.04 |
| 9 | [[KB_LOOSE]] | 7.2% | 69% | 246 | -11.5% | 7.80 |
| 10 | [[KB_LOOSE_RSI]] | 7.0% | 70% | 230 | -10.4% | 8.16 |

## Détail

### [[KB_LOOSE_RR2.5_RR3.0]]
- **Retour mensuel** : 8.02%
- **Win Rate** : 66.2%
- **Trades** : 231
- **Drawdown max** : -12.2%
- **Sharpe** : 7.06
- **Paramètres** : `{"ema_fast": 7, "ema_slow": 21, "kijun_len": 26, "atr_len": 14, "atr_mult": 1.5, "rr": 3.0, "ema_sep_pct": 0.15, "cooldown_bars": 3, "atr_min_pct": 0.3, "use_rsi": false, "use_adx": false, "use_macd": false, "use_volume": false, "use_supertrend": false, "rsi_ob": 65, "rsi_os": 35}`


### [[KB_1h]]
- **Retour mensuel** : 7.94%
- **Win Rate** : 66.7%
- **Trades** : 420
- **Drawdown max** : -6.1%
- **Sharpe** : 7.51
- **Paramètres** : `{"ema_fast": 7, "ema_slow": 21, "kijun_len": 26, "atr_len": 14, "atr_mult": 1.5, "rr": 3.0, "ema_sep_pct": 0.15, "cooldown_bars": 4, "atr_min_pct": 0.3, "use_rsi": false, "use_adx": false, "use_macd": false, "use_volume": false, "use_supertrend": false, "rsi_ob": 65, "rsi_os": 35, "tf_resample": "1h"}`


### [[KB_RR4]]
- **Retour mensuel** : 7.93%
- **Win Rate** : 65.0%
- **Trades** : 214
- **Drawdown max** : -12.2%
- **Sharpe** : 6.43
- **Paramètres** : `{"ema_fast": 7, "ema_slow": 21, "kijun_len": 26, "atr_len": 14, "atr_mult": 1.5, "rr": 4.0, "ema_sep_pct": 0.15, "cooldown_bars": 3, "atr_min_pct": 0.3, "use_rsi": false, "use_adx": false, "use_macd": false, "use_volume": false, "use_supertrend": false, "rsi_ob": 65, "rsi_os": 35}`


### [[KB_15m]]
- **Retour mensuel** : 7.91%
- **Win Rate** : 66.6%
- **Trades** : 414
- **Drawdown max** : -5.7%
- **Sharpe** : 7.57
- **Paramètres** : `{"ema_fast": 7, "ema_slow": 21, "kijun_len": 26, "atr_len": 14, "atr_mult": 1.5, "rr": 3.0, "ema_sep_pct": 0.15, "cooldown_bars": 6, "atr_min_pct": 0.3, "use_rsi": false, "use_adx": false, "use_macd": false, "use_volume": false, "use_supertrend": false, "rsi_ob": 65, "rsi_os": 35, "tf_resample": "15min"}`


### [[KB_RR5]]
- **Retour mensuel** : 7.84%
- **Win Rate** : 62.0%
- **Trades** : 208
- **Drawdown max** : -14.6%
- **Sharpe** : 5.51
- **Paramètres** : `{"ema_fast": 7, "ema_slow": 21, "kijun_len": 26, "atr_len": 14, "atr_mult": 1.5, "rr": 5.0, "ema_sep_pct": 0.15, "cooldown_bars": 2, "atr_min_pct": 0.3, "use_rsi": false, "use_adx": false, "use_macd": false, "use_volume": false, "use_supertrend": false, "rsi_ob": 65, "rsi_os": 35}`


### [[KB_LOOSE_RR2.5_RR3.0_RSI]]
- **Retour mensuel** : 7.83%
- **Win Rate** : 67.5%
- **Trades** : 215
- **Drawdown max** : -11.5%
- **Sharpe** : 7.45
- **Paramètres** : `{"ema_fast": 7, "ema_slow": 21, "kijun_len": 26, "atr_len": 14, "atr_mult": 1.5, "rr": 3.0, "ema_sep_pct": 0.15, "cooldown_bars": 3, "atr_min_pct": 0.3, "use_rsi": true, "use_adx": false, "use_macd": false, "use_volume": false, "use_supertrend": false, "rsi_ob": 65, "rsi_os": 35}`


### [[KB_LOOSE_RR2.5_RSI]]
- **Retour mensuel** : 7.50%
- **Win Rate** : 67.6%
- **Trades** : 225
- **Drawdown max** : -10.4%
- **Sharpe** : 7.65
- **Paramètres** : `{"ema_fast": 7, "ema_slow": 21, "kijun_len": 26, "atr_len": 14, "atr_mult": 1.5, "rr": 2.5, "ema_sep_pct": 0.15, "cooldown_bars": 3, "atr_min_pct": 0.3, "use_rsi": true, "use_adx": false, "use_macd": false, "use_volume": false, "use_supertrend": false, "rsi_ob": 65, "rsi_os": 35}`


### [[KB_LOOSE_RR2.5]]
- **Retour mensuel** : 7.49%
- **Win Rate** : 66.0%
- **Trades** : 241
- **Drawdown max** : -11.8%
- **Sharpe** : 7.04
- **Paramètres** : `{"ema_fast": 7, "ema_slow": 21, "kijun_len": 26, "atr_len": 14, "atr_mult": 1.5, "rr": 2.5, "ema_sep_pct": 0.15, "cooldown_bars": 3, "atr_min_pct": 0.3, "use_rsi": false, "use_adx": false, "use_macd": false, "use_volume": false, "use_supertrend": false, "rsi_ob": 65, "rsi_os": 35}`


### [[KB_LOOSE]]
- **Retour mensuel** : 7.19%
- **Win Rate** : 69.1%
- **Trades** : 246
- **Drawdown max** : -11.5%
- **Sharpe** : 7.80
- **Paramètres** : `{"ema_fast": 7, "ema_slow": 21, "kijun_len": 26, "atr_len": 14, "atr_mult": 1.5, "rr": 2.0, "ema_sep_pct": 0.15, "cooldown_bars": 3, "atr_min_pct": 0.3, "use_rsi": false, "use_adx": false, "use_macd": false, "use_volume": false, "use_supertrend": false, "rsi_ob": 65, "rsi_os": 35}`


### [[KB_LOOSE_RSI]]
- **Retour mensuel** : 7.02%
- **Win Rate** : 70.0%
- **Trades** : 230
- **Drawdown max** : -10.4%
- **Sharpe** : 8.16
- **Paramètres** : `{"ema_fast": 7, "ema_slow": 21, "kijun_len": 26, "atr_len": 14, "atr_mult": 1.5, "rr": 2.0, "ema_sep_pct": 0.15, "cooldown_bars": 3, "atr_min_pct": 0.3, "use_rsi": true, "use_adx": false, "use_macd": false, "use_volume": false, "use_supertrend": false, "rsi_ob": 65, "rsi_os": 35}`
