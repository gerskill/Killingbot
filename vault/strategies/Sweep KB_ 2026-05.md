---
type: strategie
statut: invalide
famille: KB
actif: multi
timeframe: multi
fichier_pine: pine_scripts/strategies/kb_auto_btc_4h.pine
rapports:
  - vault/archive/BEST_STRATEGIES_INVALIDE_2026-07-18.md
derniere_verif: 2026-07-18
tags: [strategie, kb, invalide]
---

# Sweep KB_* — mai 2026 (35 variantes)

> [!danger] Invalidé — ne jamais recopier ces chiffres
> `KB_15m`, annoncé Sharpe 7.57 / WR 67 %, a donné en live : **−8.76 %, PF 0.465,
> Sharpe −1.243, 579 trades**. Les autres variantes n'ont jamais été retestées et
> sont fausses par défaut.

## Pourquoi
- Données yfinance tronquées (15m plafonné à 60 jours), désalignées de Binance
- `agents/strategy_explorer.py` n'appelait jamais `agents/validation.py`
- 35 essais sans Deflated Sharpe → biais de sélection

Les deux causes sont corrigées depuis le 2026-07-25 (`core/data_source.py`, `core/strategy_bot.py`).

## Archives
- 40 fiches d'origine : `vault/archive/strategies_sweep_invalide/`
- Détail : `vault/archive/BEST_STRATEGIES_INVALIDE_2026-07-18.md`

Les fichiers Pine qui citent encore « best=KB_LOOSE_RR2.5_RR3.0 8.0%/mo » en commentaire
([[kb_auto_btc_4h]], [[kb_sovereign_v1]]) héritent de ce chiffre faux.
