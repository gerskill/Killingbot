# INDEX — État réel des stratégies

_Dernière purge : 2026-07-25. Ce fichier est le seul à lire pour savoir où on en est._

**Règle qui a produit ce fichier** : un chiffre de backtest n'est vrai que s'il a été
recontrôlé au Strategy Tester TradingView, en direct, à l'écran. Un sweep automatique,
même avec 35 variantes, ne prouve rien tant que la meilleure n'a pas passé cette étape —
c'est exactement ce qui manquait au sweep KB_* ci-dessous.

---

## ✅ Prouvé en direct

### [[pp_st_btc_4h_final]] — PP-ST + EMA200 + ADX≥20, BTC 4H
- **+2947% | DD 24.53% | PF 2.52 | WR 33.9% (20/59) | Sharpe 0.248**
- Confirmé Strategy Tester TradingView, BINANCE:BTCUSD, 2026-07-18
- Recontrôlé BITSTAMP:BTCUSD le même jour : +8058.68%, DD 18.77%, PF 2.635 — même
  profil ajusté au risque sur deux exchanges différents
- Fichier : `pp_st_btc_4h_final.pine`
- Alerte TradingView active, collecte OOS en cours depuis 2026-07-19
- Sharpe modeste (0.248) : performance concentrée sur peu de gros trades, pas
  de régularité. Normal pour un suiveur de tendance, pas un défaut caché.

**Seule ligne de ce fichier qui autorise du capital réel (paper) aujourd'hui.**

---

## ⚠️ Non testé en direct — discrétionnaire, pas un edge mécanique

Stoic Lens (méthode StoicTA) : 4 implémentations backtestées, aucune décisive.

| Variante | Meilleur résultat backtesté | Fichier |
|---|---|---|
| stoic_confluence_strategy | BTC 4H, PF 2.77, DD 8.5%, mais +48.9%/9 ans (anémique) | `backtest/stoic_edge_killingbot_rapport.md` |
| stoic_lens_pure_v2 | 15m +8.3%/Daily +6.8%, perdant en 1h–8h | `backtest/stoic_lens_pure_v2_grille_2026-07-22.md` |
| stoic_sbs (SBS mécanisé) | +2.3% au mieux | `backtest/stoic_sbs_8tf_2026-07-23.md` |
| stoic_123_ribbon | 8h +18% (le moins mauvais du lot) | `backtest/stoic_123_ribbon_grille_2026-07-23.md` |

**Conclusion actée le 2026-07-23** (`backtest/stoic_sbs_8tf_2026-07-23.md`) :
> SBS = mauvais candidat pour l'automatisation. La méthode StoicTA est
> discrétionnaire. Mécaniser la séquence perd l'edge.

Traitement recommandé : lens comme **checklist de décision manuelle** (dashboard +
alertes de niveaux), pas comme stratégie à mécaniser. Aucun sweep de paramètres
supplémentaire n'est justifié ici — 4 variantes, 20 symboles, plusieurs TF déjà
couverts sans edge mécanique qui survive.

Matrice complète : `backtest/STOIC_RESULTS_MATRIX.md`. Plan d'origine :
`backtest/STOIC_BACKTEST_PLAN.md`.

---

## ❌ Invalidé — ne pas réutiliser les chiffres

### Sweep KB_* (35 variantes, `agents/strategy_explorer.py`, 2026-05-14)

Le rang 4 du tableau d'origine (`KB_15m`, annoncé Sharpe 7.57, WR 67%, PF implicite
élevé) a été recompilé et testé en direct le 2026-07-18 :

**réel P&L −8.76%, DD 8.98%, PF 0.465 (perdant), WR 35.23%, Sharpe −1.243, 579 trades**
— à l'opposé complet de l'annonce, et avec un nombre de trades différent (579 vs 414),
signe que le backtest d'origine tournait sur un échantillon tronqué (yfinance plafonne
le 15m à 60 jours — corrigé depuis dans `core/data_source.py`).

Les 9 autres lignes du sweep n'ont jamais été retestées et doivent être considérées
fausses par défaut jusqu'à preuve du contraire — même méthodologie, même absence de
validation live, même biais de sélection sur 35 essais sans Deflated Sharpe Ratio.

- Détail de l'invalidation : `vault/archive/BEST_STRATEGIES_INVALIDE_2026-07-18.md`
- 40 fiches originales : `vault/archive/strategies_sweep_invalide/`
- Mémoire de l'agent (source du biais, ne plus relire pour "meilleure stratégie") :
  `vault/archive/memory_sweep_invalide_2026-07-18.json`

**Cause racine corrigée le 2026-07-25** : `agents/strategy_explorer.py` utilisait
yfinance (données tronquées, désalignées de l'exécution Binance) et n'appelait jamais
`agents/validation.py` (walk-forward, Deflated Sharpe, Monte Carlo — le module existait
déjà, personne ne le branchait). Les deux sont corrigés. Voir `core/data_source.py`,
`core/strategy_bot.py`.

---

## Méthodologie — pourquoi ce classement à 3 niveaux

1. **Prouvé** exige G6 : Strategy Tester TradingView, lu à l'écran, pas une estimation
   d'agent. C'est la seule étape qui a démasqué `KB_15m`.
2. **Non testé** n'est pas "probablement faux" — c'est "pas encore vérifié à ce niveau
   d'exigence". Le Stoic Lens a un edge documenté en usage discrétionnaire humain ; le
   perdre en mécanisant n'est pas un échec de la méthode, c'est un échec du portage.
3. **Invalidé** signifie : chiffre contredit par un test live, ou produit par un
   pipeline dont la faille est identifiée (données tronquées, pas de garde-fou
   statistique). Ne jamais recopier ces chiffres, même avec un avertissement en tête —
   c'est ce qui s'est passé ici pendant deux mois.
