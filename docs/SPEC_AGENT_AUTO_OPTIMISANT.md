# Spécification — Agent de trading auto-optimisant (Killingbot)

> Version 1.0 — 2026-07-25
> Feuille de route pour la boucle d'apprentissage. Ancrée sur les composants réels du projet.

---

## 0. Correction préalable de l'objectif (à lire avant tout le reste)

L'objectif proposé initialement — **« Sharpe ≥ 1, taux de victoire ≥ 60 % »** — doit être rejeté. Preuve dans les données du projet :

| Stratégie | Sharpe annoncé | WR annoncé | Résultat live réel |
|-----------|----------------|------------|--------------------|
| `pp_st_btc_4h_final` | **0.248** | **33.9 %** | ✅ **+2947 %, PF 2.52** — confirmé en direct |
| `KB_15m` (sweep) | 7.57 | 67 % | ❌ **PF 0.465, P&L −8.76 %** — perdant |
| 9 autres KB_* (sweep) | 5.5 – 8.2 | 62 – 70 % | ⚠️ jamais retestées, présumées identiques |

Un seuil « Sharpe ≥ 1 + WR ≥ 60 % » **rejetterait la seule stratégie rentable confirmée** et **sélectionnerait exactement les variantes surapprises**. C'est l'inverse de l'effet recherché.

**Cause** : un Sharpe > 3 sur un backtest de stratégie discrétionnaire n'est pas un signe de qualité, c'est un **symptôme de surapprentissage**. Idem pour un WR > 65 % : il indique presque toujours des TP serrés et des SL larges (grosse queue de pertes cachée), pas un edge.

**Conséquence structurelle pour cette spec** : la boucle d'apprentissage n'est pas un optimiseur, c'est un **filtre de rejet**. Sa valeur se mesure au nombre de fausses découvertes qu'elle élimine, pas au meilleur chiffre qu'elle produit.

---

## 1. Évaluation des stratégies

### 1.1 Format de données (contrat d'entrée)

```python
# DataFrame pandas, index = DatetimeIndex UTC tz-aware, tri croissant, sans doublon
#                  colonnes = open, high, low, close, volume (float64)
# Barre horodatée à son OUVERTURE. Barre courante incomplète = TOUJOURS exclue.
df.index.tz          # → UTC obligatoire
df.index.is_monotonic_increasing  # → True
df.index.duplicated().any()       # → False
```

Format d'un trade clôturé (`trades.csv`, déjà en place) :

```
date, time, symbol, side, entry_price, exit_price, shares, pnl_usd, pnl_pct, setup_type, notes
```

### 1.2 Métriques, par ordre de fiabilité

| Rang | Métrique | Formule / définition | Pourquoi ce rang |
|------|----------|----------------------|------------------|
| 1 | **Profit Factor** | `Σ gains / |Σ pertes|` | Difficile à truquer. PF < 1 = perdant, sans discussion |
| 2 | **Max Drawdown** | pic-à-creux sur la courbe d'équité | Contrainte de survie, pas de performance |
| 3 | **Espérance en R** | `moyenne(pnl / risque_initial)` | Normalise entre actifs et volatilités. **La métrique de pilotage** |
| 4 | **Nombre de trades** | N | En dessous de 30, aucune métrique n'a de sens statistique |
| 5 | **Deflated Sharpe Ratio** | voir §1.3 | Corrige le biais de sélection multiple |
| 6 | Sharpe brut | `√252 × μ/σ` des rendements | À lire, jamais à optimiser |
| 7 | Win Rate | gagnants / total | **Indicateur trompeur.** À enregistrer, jamais à cibler |

### 1.3 Le correctif indispensable : Deflated Sharpe Ratio

Déjà implémenté — [`agents/validation.py:55`](../agents/validation.py).

Tester 35 variantes garantit que la meilleure aura un bon Sharpe **par pur hasard**. Le DSR répond à : « ce Sharpe survit-il au fait que j'ai regardé 35 fois ? »

```python
from agents.validation import deflated_sharpe_ratio

dsr = deflated_sharpe_ratio(
    observed_sharpe=best["sharpe"],
    trial_sharpes=[r["sharpe"] for r in all_35_results],  # TOUS les essais, y compris ratés
    n_obs=len(returns),
)
if dsr < 0.95:
    reject("Sharpe non distinguable du bruit de sélection")
```

> ⚠️ **Le sweep KB_* de mai 2026 n'a jamais passé cette étape.** Le module `validation.py` existait mais n'a pas été branché sur `strategy_explorer.py`. C'est la cause racine directe des 10 fausses stratégies du tableau invalidé.

### 1.4 Portes de rejet (séquentielles, court-circuit au premier échec)

```
G1. N_trades ≥ 30 ................................ sinon REJET (échantillon insuffisant)
G2. PF_out_of_sample > 1.2 ....................... sinon REJET
G3. dégradation OOS vs IS < 30 % ................. sinon REJET (surapprentissage)
G4. Deflated Sharpe ≥ 0.95 ....................... sinon REJET (biais de sélection)
G5. Monte Carlo : 80 % des perturbations ±10 % restent PF > 1 ... sinon REJET (instable)
G6. Test live Strategy Tester TradingView ........ sinon REJET (règle projet absolue)
```

G1→G5 sont automatisables. **G6 est manuelle et non négociable** : c'est la seule porte qui a réellement démasqué `KB_15m`.

---

## 2. Mécanismes d'amélioration

### 2.1 Optimisation des paramètres — verdict par méthode

| Méthode | Verdict Killingbot | Justification |
|---------|--------------------|---------------|
| **Grid search grossier** (3-5 valeurs/param, ≤ 2 params) | ✅ **Recommandé** | Le peu de données autorise peu d'essais. Une grille grossière limite mécaniquement le surapprentissage |
| **Optimisation bayésienne** (Optuna) | 🟡 Conditionnel | Plus efficace en essais, mais converge vers le pic étroit du bruit. N'utiliser qu'avec DSR + Monte Carlo actifs |
| **Apprentissage par renforcement** | ❌ **Rejeté** | RL demande 10⁴–10⁶ épisodes. La stratégie confirmée produit **~6,5 trades/an**. Rapport signal/bruit incompatible. Un RL ici mémoriserait l'historique BTC, ne généraliserait rien |

**Règle de plateau** : préférer un plateau large à un pic étroit.

```python
# Un optimum entouré de voisins médiocres est un artefact.
voisins = [backtest(df, perturber(p, ±10%)) for _ in range(15)]
if median(v["pf"] for v in voisins) < 1.0:
    reject("pic étroit — pas un edge, un artefact")
```

Contrainte déjà codée dans `killingbot_config.json` : `max_params_changed_per_iteration: 2`. À conserver.

### 2.2 Extension des indicateurs — critères de sélection

Un nouvel indicateur n'est admis que s'il satisfait **les 4 critères** :

1. **Hypothèse économique préalable, écrite avant le test.** « L'ADX filtre les ranges où le SuperTrend produit des faux signaux » = valide. « L'ADX améliore la courbe » = invalide (data mining).
2. **Faible corrélation** avec les indicateurs déjà présents : `|ρ| < 0.7` sur les valeurs de signal.
3. **Réduit les trades, n'en ajoute pas.** Un filtre qui augmente le nombre de trades ajoute du bruit. L'ADX≥20 a fait passer 71 → 59 trades et le PF 2.09 → 2.52. C'est la signature d'un bon filtre.
4. **Passe les portes G1→G6** en tant que variante à part entière.

Procédure d'intégration :

```
1. Écrire l'hypothèse dans docs/ (horodatée, avant tout backtest)
2. Implémenter l'indicateur dans strategy_explorer.py (bibliothèque §7)
3. Backtest variante = stratégie_base + indicateur, un seul changement
4. Portes G1→G5 automatiques
5. Si PASS : implémenter en Pine, compiler, tester en direct (G6)
6. Si PASS : commit Pine + fiche dans vault/strategies/
7. Si FAIL à n'importe quelle étape : consigner l'échec dans LEARNINGS.md et abandonner
```

L'étape 7 est aussi importante que les autres : **le journal des échecs alimente le `trial_sharpes` du DSR**. Jeter les essais ratés casse la correction statistique.

### 2.3 Combinaison de stratégies

| Technique | Verdict |
|-----------|---------|
| **Vote de signaux** (N stratégies indépendantes, entrée si ≥ K d'accord) | ✅ Robuste, peu de paramètres, interprétable |
| **Pondération fixe** par edge historique | 🟡 Acceptable si les poids sont ré-estimés en walk-forward uniquement |
| **Pondération adaptative** (poids ajustés en continu) | ❌ Surapprentissage déguisé — les poids deviennent des paramètres libres non comptabilisés |
| **Stacking** (méta-modèle ML sur les sorties) | ❌ Rejeté à ce stade — demande des milliers d'observations, on en a des dizaines |

**Prérequis absolu** : ne combiner que des stratégies **individuellement validées G1→G6**. Combiner deux stratégies non prouvées produit une troisième stratégie non prouvée, avec deux fois plus de paramètres à surapprendre.

État actuel : **1 seule stratégie validée** → aucune combinaison possible avant d'en avoir une seconde.

---

## 3. Adaptation aux timeframes et aux régimes de marché

### 3.1 Changement de timeframe

Un changement de TF n'est **pas** un changement de paramètre — c'est une **nouvelle stratégie**, revalidation complète G1→G6 obligatoire.

| Élément | Règle d'ajustement |
|---------|--------------------|
| Périodes d'indicateurs | Ne **pas** rescaler mécaniquement (EMA7 en 4H ≠ EMA28 en 1H). Re-tester la plage |
| Coûts | Frais + slippage constants par trade → poids relatif × N quand la fréquence × N. **Cause principale de l'échec de `KB_15m`** |
| Volume de données | Descendre en TF augmente les barres mais **pas** le nombre de cycles de marché indépendants |
| Seuil minimal | En dessous de 15 min, les coûts de microstructure dominent. Hors périmètre |

### 3.2 Détection de régime — déjà en production

[`core/market_regime.py`](../core/market_regime.py) : vote majoritaire 2/3 sur ADX(14), Efficiency Ratio(20), pente BB Width(10) → `TRENDING` / `RANGING` / `UNDECIDED`.

Règle d'adaptation actuelle, à conserver telle quelle :

```
TRENDING  → signal accepté
RANGING   → signal accepté (mais tracé)
UNDECIDED → signal REJETÉ  ← l'abstention est une position
```

**Interdiction explicite** : ne pas passer à des jeux de paramètres par régime (« params A en trend, params B en range ») avant d'avoir ≥ 100 trades **par régime**. En dessous, cela double l'espace de paramètres sur des données déjà insuffisantes.

Extension légitime à moyen terme : moduler la **taille de position** par régime (pas les paramètres d'entrée). Modules `garch_position_sizer.py` / `ewma_vol_sizer.pine` déjà écrits, gelés jusqu'à validation OOS.

---

## 4. Architecture de la boucle d'apprentissage

### 4.1 Schéma

```
┌──────────────────────── BOUCLE RAPIDE (temps réel, déterministe) ──────────────────┐
│                                                                                     │
│  TradingView alerte ──► webhook_server.py ──► filtre RÉGIME ──► filtre MACRO ──►    │
│                                                    │                │               │
│                                              UNDECIDED         event ±2h            │
│                                                    ▼                ▼               │
│                                                 REJET (loggé)   REJET (loggé)        │
│                                                                                     │
│                            ──► paper_executor.py ──► positions ──► trades.csv       │
│                                (SL/TP, sizing 1 %, slippage 5 bps, frais 10 bps)    │
│                                                                                     │
│  ⚠️ AUCUN LLM dans ce chemin. Déterministe, reproductible, auditable.               │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼ (hebdomadaire, dimanche 20h)
┌──────────────────────── BOUCLE LENTE (apprentissage) ──────────────────────────────┐
│                                                                                     │
│  journal_agent.py ──► lit trades.csv + loop_history ──► analyse LLM                 │
│                                        │                                            │
│                                        ▼                                            │
│                          validate() ← VÉRIFICATEUR DÉTERMINISTE EN CODE             │
│                          (levier ≤5, DD hebdo, anti flip-flop N-3, max 2 params)    │
│                                        │                                            │
│                          PASS ─────────┴───────── FAIL ──► mutation rejetée, loggée │
│                            ▼                                                        │
│                    killingbot_config.json muté ──► nouvelle itération               │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼ (mensuel / trimestriel, déclenché humain)
┌──────────────────────── BOUCLE DE RECHERCHE (exploration) ─────────────────────────┐
│                                                                                     │
│  strategy_explorer.py ──► N variantes ──► G1..G5 (validation.py) ──► candidat       │
│                                                                        │            │
│                                                        ┌───────────────┘            │
│                                                        ▼                            │
│                                     G6 : Pine + Strategy Tester TradingView          │
│                                     ⚠️ ÉTAPE HUMAINE — non automatisable            │
│                                                        │                            │
│                                          PASS ─────────┴────── FAIL ──► LEARNINGS.md│
│                                            ▼                                        │
│                                  vault/strategies/ + candidate déploiement          │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Pourquoi trois boucles séparées

| Boucle | Fréquence | Déterminisme | Rôle |
|--------|-----------|--------------|------|
| Rapide | temps réel | 100 % code | Exécuter. Aucune place pour l'incertitude |
| Lente | hebdo | LLM + vérificateur code | Ajuster les paramètres à la marge |
| Recherche | mensuelle+ | LLM + humain | Explorer de nouvelles stratégies |

Séparation critique : **une erreur de la boucle de recherche ne peut pas contaminer un trade en cours.** C'est ce qui distingue ce design d'un « agent qui trade et apprend en même temps » — architecture séduisante et structurellement dangereuse.

### 4.3 Point de rupture identifié — corrigé

`agents/strategy_explorer.py:402` — `_fetch_data(self, yf_symbol)` utilisait **yfinance**, alors que `pp_st_btc_4h_final` a été validé sur données **Binance/Bitstamp**. Backtester sur une source et déployer sur une autre rend le backtest non interprétable. Combiné à l'absence de `validation.py` dans le sweep, cela explique largement l'écart entre les 10 « top stratégies » annoncées et la réalité.

**Statut : corrigé.** [`core/data_source.py`](../core/data_source.py) est désormais la couche d'accès unique, et Yahoo Finance en est volontairement absent. Voir §7.1.

---

## 5. Définition de l'objectif de performance

### 5.1 Seuils recommandés (remplacent « Sharpe ≥ 1, WR ≥ 60 % »)

| Critère | Seuil | Nature |
|---------|-------|--------|
| Profit Factor OOS | > 1.3 | Performance |
| Max Drawdown | < 25 % | **Survie — contrainte dure** |
| Espérance | > 0.15 R / trade | Performance |
| N trades validés | ≥ 30 | Statistique |
| Deflated Sharpe | ≥ 0.95 | Anti-biais de sélection |
| Dégradation OOS/IS | < 30 % | Anti-surapprentissage |
| Stabilité Monte Carlo | 80 % des voisins PF > 1 | Robustesse |
| **Test live TradingView** | **conforme à ±20 %** | **Vérité terrain** |
| Win Rate | *aucun seuil* | Enregistré, jamais ciblé |
| Sharpe brut | *aucun seuil* | Enregistré, jamais ciblé |

Le seuil de drawdown est **différent de nature** : PF et espérance sont des objectifs à maximiser, le DD est une contrainte à ne jamais franchir. Une stratégie à PF 3.0 et DD 60 % est rejetée sans discussion.

### 5.2 Critère d'arrêt : quand l'agent sait qu'il a fini

L'agent s'arrête quand **les trois conditions** sont réunies :

```python
def objectif_atteint(candidat, historique_essais) -> bool:
    return all([
        toutes_les_portes_passees(candidat),           # G1 → G6
        candidat.pf_oos > champion.pf_oos * 1.15,      # +15 % minimum vs titulaire
        deflated_sharpe(candidat, historique_essais) >= 0.95,
    ])
```

Le seuil de **+15 % contre le champion en place** évite le remplacement permanent par du bruit. Sans lui, la boucle change de stratégie chaque semaine sur des écarts non significatifs.

**Condition d'arrêt symétrique — la plus importante** : si après N itérations aucun candidat ne passe, **l'agent conserve le champion et le déclare explicitement**. « Aucune amélioration trouvée » est un résultat valide et attendu la plupart du temps. Un agent qui trouve une amélioration chaque semaine ne cherche pas, il surapprend.

---

## 6. Scénario d'exemple

### 6.1 Illustration demandée (EUR/USD H1) — avec réserve

**Réserve préalable** : le Forex n'est pas supporté nativement par le MCP TradingView de ce projet, et Yahoo Finance ne fournit pas de données FX intraday fiables. Ce scénario est **illustratif du processus**, pas exécutable en l'état sur cette stack.

| Itération | Action | Résultat | Décision |
|-----------|--------|----------|----------|
| 0 | Base : croisement SMA20/SMA50, EUR/USD H1 | PF 1.05, 240 trades, DD 18 % | Marginal — champion faible |
| 1 | + filtre RSI (pas d'achat si RSI > 70) | PF 1.28, 180 trades, WR 58 % | ✅ G1-G5 OK. **Trades ↓ 25 %** = bonne signature de filtre |
| 2 | Test OOS sur holdout 30 % | PF 1.22 (dégradation 5 %) | ✅ G3 OK |
| 3 | DSR sur 12 essais cumulés | 0.91 | ❌ **G4 ÉCHOUE** — en dessous de 0.95 |
| 4 | Fusion avec breakout Bollinger (vote 2/2) | PF 1.61, 95 trades | ⚠️ Chiffre séduisant |
| 5 | DSR sur 18 essais cumulés | 0.88 | ❌ **REJET FINAL** |

**Issue attendue : rejet.** C'est le fonctionnement correct, pas un échec.

L'illustration classique « SMA → +RSI → +Bollinger → objectif atteint » décrit précisément la trajectoire qui produit une stratégie surapprise : chaque ajout améliore le backtest, le DSR se dégrade à chaque essai supplémentaire, et le résultat final ne survit pas au live. **C'est exactement le chemin qu'a suivi le sweep KB_*.**

### 6.2 Scénario réel du projet — le contre-exemple qui a fonctionné

| Étape | Action | Résultat |
|-------|--------|----------|
| 0 | PP SuperTrend seul, BTC 4H | Base |
| 1 | + EMA200 (hypothèse : filtre de tendance macro) | +2039 %, PF 2.09, 71 trades |
| 2 | + ADX ≥ 20 (hypothèse : couper les ranges) | +2947 %, PF 2.52, **59 trades** |
| 3 | Test live Strategy Tester (G6) | ✅ Correspondance quasi parfaite |
| 4 | Contre-validation autre exchange (Bitstamp) | ✅ PF 2.635, DD 18.8 % — même profil ajusté au risque |

Ce qui a fait la différence : **2 ajouts seulement, tous deux motivés par une hypothèse économique préalable, tous deux réduisant le nombre de trades, et validation live avant toute conclusion.** Sharpe 0.248 et WR 33.9 % — deux chiffres qu'un optimiseur naïf aurait rejetés.

---

## 7. Hypothèses, données et outils

### 7.1 Sources de données — implémenté dans [`core/data_source.py`](../core/data_source.py)

**Règle non négociable** : *la source de données du backtest doit être identique à celle de l'exécution.* Toute divergence rend le backtest non interprétable.

Uniquement les sources déjà disponibles dans le projet. **Aucune source externe ajoutée, Yahoo Finance volontairement absent et à ne pas réintroduire.**

| Source | Nature | Couverture | Statut |
|--------|--------|-----------|--------|
| **Binance klines** | Programmatique — Python appelle l'API publique, sans clé, avec pagination | Crypto. BTCUSDT 4H : **19 569 barres, 2017-08-17 → aujourd'hui** en ~15 s | ✅ Opérationnel. Même source que le filtre de régime et le paper executor |
| **TradingView (MCP)** | Médiée par l'agent — cache disque | Actions, indices, forex, crypto d'autres exchanges | ✅ Opérationnel via cache |
| **TradingView Strategy Tester** | Manuelle | Vérité terrain (G6) | ✅ Seule validation faisant foi |
| **ForexFactory** | Programmatique | Calendrier macro | ✅ En production (`core/macro_calendar.py`) |
| **IBKR** | — | Actions, forex, futures | 🔒 Emplacement réservé, **non connecté par décision explicite**. Voir `_fetch_ibkr()` |
| Yahoo Finance | — | — | ❌ **Retiré. Ne pas réintroduire** |

#### Pourquoi TradingView passe par un cache

Le MCP `tradingview-desktop` est un outil **côté agent**, pas une bibliothèque Python : un script ne peut pas l'appeler. Le flux est donc :

```
Agent (MCP data_get_ohlcv) ──► write_cache() ──► data/cache/TV_<SYMBOLE>_<TF>.csv
                                                        │
                                          Python lit ◄──┘  (load() transparent)
```

Si le cache manque, l'erreur indique exactement quoi demander à l'agent — pas d'échec silencieux ni de repli sur une autre source.

#### Contrat unique de sortie

Toute source passe par `_normalize()` :

```python
df.index          # DatetimeIndex UTC tz-aware, croissant, sans doublon
df.columns        # open, high, low, close, volume (float64)
                  # barre horodatée à son OUVERTURE
                  # barre courante incomplète TOUJOURS retirée
```

Retirer la barre en cours n'est pas cosmétique : son `close` bouge encore. La garder revient à décider sur une information qui n'existait pas au moment de la décision — un look-ahead silencieux.

```python
from core.data_source import load

df = load("BTCUSDT", "4h")                      # Binance, historique complet
df = load("BTCUSDT", "4h", start="2020-01-01")  # borné
df = load("NASDAQ:NVDA", "1h")                  # cache TradingView
```

#### Brancher IBKR plus tard

`_fetch_ibkr()` lève une erreur explicite listant ses prérequis (compte IBKR, IB Gateway paper port 4002, `ib_insync`). Le jour venu, implémenter cette seule fonction et renvoyer via `_normalize()` : **aucun autre fichier ne change**. Les stratégies existantes accèdent alors aux actions et au forex sans modification.

### 7.2 Bibliothèques

| Besoin | Recommandation | Note |
|--------|----------------|------|
| Manipulation données | **pandas, NumPy** | Déjà en place, aucune nouvelle dépendance |
| Accès données | **`core/data_source.py`** | ✅ Écrit. Binance + cache TradingView, zéro Yahoo |
| Backtest | **`core/strategy_engine.py`** | ✅ Écrit. Coûts importés de `paper_executor` — backtest et production ne peuvent pas diverger |
| Validation statistique | **`agents/validation.py`** | ✅ Existait, **désormais branché** via `strategy_bot.validate` |
| Orchestration par stratégie | **`core/strategy_bot.py`** | ✅ Écrit. Voir §10 |
| Optimisation | **Optuna** (si §2.1 conditionnel) | Uniquement avec DSR actif. Grid maison suffit à ce stade |
| Métriques / rapports | **quantstats** | Préférer à pyfolio, non maintenu |
| ML / RL | *aucune* | scikit-learn, TensorFlow, Keras : **non recommandés ici** (§2.1) |
| Persistance | **SQLite** | Remplace le couple CSV/JSONL. Voir plan d'amélioration infra |

Aucune bibliothèque de backtest tierce (backtrader, vectorbt, zipline) : la logique est écrite, et une dépendance externe réintroduirait son propre modèle de coûts, différent de celui du paper executor.

### 7.3 Hypothèses explicites

1. **Coûts** : slippage 5 bps + commission 10 bps par côté (Binance spot). Sous-estimé en cas de forte volatilité.
2. **Pas de look-ahead** : décision sur barre `t` fermée, exécution à l'ouverture de `t+1`. Toute violation invalide le backtest.
3. **Pas de biais de survivance** : BTC/USDT existe sur toute la période. Devient critique en multi-actifs (altcoins disparus).
4. **Liquidité infinie supposée** : valide à 25 000 $ sur BTC. À revoir au-delà de ~1 M$.
5. **Capital simulé** : 25 000 $, risque 1 %/trade, max 3 positions.
6. **`deploy_state: "paper"`** — le passage en live est une **décision humaine exclusive**, jamais un choix d'agent.

---

## 8. Ordre d'implémentation

> **Statut au 2026-07-25 : collecte OOS en cours depuis le 2026-07-19.** Aucun élément ci-dessous ne doit être exécuté avant la fin de la fenêtre de 2–4 semaines. Modifier les filtres ou paramètres pendant la collecte détruit la seule donnée hors-échantillon réelle du projet.

| # | Action | Priorité | Statut |
|---|--------|----------|--------|
| 1 | Brancher `validation.py` (portes G1–G5 obligatoires) | 🔴 | ✅ **Fait** — `strategy_bot.validate` |
| 2 | Remplacer yfinance par Binance/TradingView | 🔴 | ✅ **Fait** — `core/data_source.py` |
| 3 | Persister **tous** les essais, échecs compris, pour le DSR | 🔴 | ✅ **Fait** — `trials.jsonl` par stratégie |
| 4 | Moteur de backtest partagé, coûts alignés production | 🔴 | ✅ **Fait** — `core/strategy_engine.py` |
| 5 | Migrer `strategy_explorer.py` vers `data_source` (retirer yfinance) | 🟡 | À faire — 2 h |
| 6 | Porter `pp_st_btc_4h_final` en `strategies/pp_st_btc_4h/` | 🟡 | À faire — 3 h |
| 7 | Migration SQLite (`signals`, `trades`, `positions`, `equity`) | 🟡 | À faire — 1 j |
| 8 | Module `strategy_report.py` (quotidien / hebdo / mensuel) | 🟡 | À faire — 1 j |
| 9 | Routage webhook par `setup_key` (dédup `symbol+setup`) | 🟡 | À faire — 4 h |
| 10 | Dashboard : courbe d'équité, feed signaux, santé pipeline | 🟢 | À faire — 2 j |
| 11 | Sizing GARCH/EWMA en shadow-mode (log seul, zéro impact) | 🟢 | À faire — 1 j |
| 12 | Connexion IBKR (données + exécution paper) | 🟢 | Bloqué : compte + IB Gateway requis |
| 13 | Vote de signaux multi-stratégies | ⛔ | Bloqué : nécessite une 2ᵉ stratégie validée G6 |

---

## 10. Le bot standard par stratégie

Chaque stratégie ajoutée arrive avec son bot. On n'écrit qu'**une fonction de signal** ; données, backtest, portes, optimisation, journal des essais et statut sont fournis automatiquement et à l'identique. Deux stratégies deviennent donc comparables : mêmes données, mêmes coûts, mêmes portes.

### 10.1 Arborescence

```
strategies/<id>/
    config.json     symbole, intervalle, params, grille, portes, setup_key, statut
    logic.py        signals(df, params) → la seule chose à écrire
    hypotheses.md   pourquoi chaque composant existe — à remplir AVANT le backtest
    trials.jsonl    TOUS les essais, succès et échecs (alimente le DSR)
    strategy.pine   source Pine pour G6
```

### 10.2 Le seul contrat à respecter

```python
def signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Renvoie entry_long / exit_long (bool), indexés comme df.
    N'utiliser que des données disponibles à la CLÔTURE de chaque barre."""
```

Le moteur décale lui-même l'exécution à l'ouverture de la barre suivante : **une logique de stratégie ne peut pas oublier le décalage anti-look-ahead**, il est structurel.

### 10.3 Cycle de vie

```
new ──► hypotheses.md ──► logic.py ──► backtest ──► optimize ──► validate ──► G6 ──► deploy
                            │                                       │           │
                            │                                    G1..G5      manuel
                            │                                       │        TradingView
                            ▼                                       ▼           │
                       (à écrire avant                          REJECTED        ▼
                        tout chiffre)                                       VALIDATED
```

```bash
python3 core/strategy_bot.py new ma_strat --symbol BTCUSDT --interval 4h
python3 core/strategy_bot.py backtest ma_strat
python3 core/strategy_bot.py optimize ma_strat
python3 core/strategy_bot.py validate ma_strat
python3 core/strategy_bot.py list
```

Statuts : `DRAFT` → `REJECTED` | `PENDING_G6` → `VALIDATED`.
**Aucun passage à `VALIDATED` sans G6.** C'est la seule porte qui a démasqué `KB_15m`.

### 10.4 Garde-fous intégrés au bot

| Garde-fou | Mécanisme |
|-----------|-----------|
| Validation non contournable | `validate` appelle systématiquement G1→G5 ; impossible de « oublier » `validation.py` comme lors du sweep KB_* |
| Essais ratés conservés | `trials.jsonl` en append ; le DSR reçoit la liste complète, jeter les échecs ferait remonter le bruit au rang de découverte |
| Grille bornée | `optimize` **refuse** plus de 2 paramètres — au-delà, l'espace de recherche dépasse ce que les données peuvent valider |
| OOS préservé | `optimize` ne travaille que sur les 70 % in-sample ; les 30 % restants ne servent qu'à `validate` |
| Sélection par PF | Le vainqueur est choisi sur le Profit Factor, jamais sur le Sharpe ni le win rate (§1.2) |
| Coûts alignés | `strategy_engine` importe `SLIPPAGE_BPS` / `COMMISSION_BPS` de `paper_executor` — backtest et production ne peuvent pas diverger |

### 10.5 Démonstration : le surapprentissage capturé en direct

Test réel effectué à la livraison du bot, sur un croisement EMA volontairement naïf (BTCUSDT 4H, 19 569 barres) :

| Étape | PF in-sample | Dégradation OOS | Stabilité Monte Carlo |
|-------|--------------|-----------------|------------------------|
| Params initiaux (20/50) | 1.83 | **−67 %** | 100 % |
| Après `optimize` (30/60) | **2.66** *(+45 %)* | **−81 %** | **66.7 %** |

L'optimisation a amélioré le backtest de 45 % **et dégradé les deux indicateurs de robustesse**. C'est la signature exacte du surapprentissage, rendue visible par les portes. Les deux versions ont été rejetées.

Sans les portes, la ligne « PF 2.66 » aurait rejoint le tableau des « top stratégies » — comme les dix du sweep KB_*.

---

## 11. Résumé en une phrase

Un agent de trading auto-optimisant utile n'est pas un système qui trouve des stratégies gagnantes — c'est un système qui **rejette de façon fiable les stratégies perdantes qui ont l'air gagnantes**. Le projet possède déjà l'outillage complet pour cela ([`agents/validation.py`](../agents/validation.py)) ; il n'était simplement pas branché lors du sweep qui a produit dix fausses découvertes.
