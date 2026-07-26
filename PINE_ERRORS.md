# Pine Script v6 — Journal des Erreurs Connues

> **RÈGLE** : Avant toute livraison de script Pine Script, l'agent de vérification DOIT
> scanner le code contre cette liste. Si une erreur est trouvée, corriger ET mettre à jour ce fichier.

---

## ❌ ERREUR #1 — Multi-ligne ternaire avec déclaration typée (CE10156)

**Symptôme :** `Syntax error at input "end of line without line continuation" (CE10156)`

**Pattern interdit :** une variable déclarée avec son type (`float`, `int`, `bool`, `string`, `color`)
dont la valeur ternaire se coupe sur plusieurs lignes avec `:` en fin de ligne.

```pine
// ❌ INTERDIT
float pnl_pct = condition1 ? valeur1 :
                condition2 ? valeur2 : na

// ❌ INTERDIT
string sig_txt = cond_a ? "A" :
                 cond_b ? "B" : "C"

// ❌ INTERDIT  
color sig_col = cond ? color.lime :
                color.red
```

**Règle :** Toute déclaration typée avec ternaire → **une seule ligne**, aussi longue soit-elle.

```pine
// ✅ CORRECT
float pnl_pct = condition1 ? valeur1 : condition2 ? valeur2 : na

// ✅ CORRECT
string sig_txt = cond_a ? "A" : cond_b ? "B" : "C"

// ✅ CORRECT
color sig_col = cond ? color.lime : color.red
```

**Exception :** les variables **sans annotation de type** peuvent casser sur plusieurs lignes
si chaque ligne se termine par `:` — Pine infère le type et accepte la continuation.

```pine
// ✅ ACCEPTÉ (pas de type explicite)
fill_col = range_hard ? color.red :
           is_range   ? color.purple :
           color.gray
```

**Fichiers corrigés :** killingbot_v1.1.pine (pnl_pct, sig_txt, sig_col) — 2026-05-10

---

## ❌ ERREUR #2 — margin_long défaut 100% en v6 : ordres futures rejetés silencieusement

**Symptôme :** Stratégie compile sans erreur, signaux déclenchent `strategy.entry()`,
mais Strategy Tester affiche **0 trades** ("Ce rapport nécessite les données sur le trade").
Aucun message d'erreur nulle part.

**Cause :** En Pine v6, `strategy()` a `margin_long=100, margin_short=100` par défaut
(= cash-secured). Sur futures, le notionnel dépasse le capital → TOUS les ordres rejetés
silencieusement. Ex : 6 contrats MES = $225 000 notionnel vs $25 000 capital.

```pine
// ❌ INTERDIT pour futures/levier — ordres rejetés sans erreur
strategy("Ma Strat", initial_capital=25000)

// ✅ CORRECT — marge futures réelle (~5%)
strategy("Ma Strat", initial_capital=25000, margin_long=5, margin_short=5)
```

**Diagnostic :** si 0 trades inattendu → ajouter compteurs debug
(`if signalCondition \n    cnt += 1` + `plot(cnt, display=display.data_window)`).
Si compteurs > 0 mais 0 trades → problème de marge.

**Fichiers corrigés :** kb_orb_vwap_v1.pine — 2026-07-09

---

## ❌ ERREUR #3 — overlay=true mélange scales incompatibles (indicateurs qui flottent)

**Symptôme :** Indicateur affiché sur le chart, mais les plots "flottent" quand on bouge/zoom.
Niveaux de prix (BB, SMA) et valeurs normalisées (RSI 0-100, state 0-2) partagent le même axe Y.

**Cause :** `overlay=true` place TOUS les plots sur l'axe Y du prix. Si tu plottes:
- Prices (4125, 4130, 4140) = l'échelle réelle
- States (0, 1, 2) = différent ordre de magnitude

→ Pine normalise sur le range du prix, pas des states → flottage visuel.

```pine
// ❌ MAUVAIS — overlay=true avec mixed scales
indicator("Markov", overlay=true)
plot(current_state, ...)      // 0-2, flotte vs prix
plot(rsi_val, ...)             // 0-100, toujours hors cadre
plot(bb_up, ...)               // Prix réel = l'axe dominant
```

**Fix :** Deux approches:

**Approche 1 (recommandée):** `overlay=false` → panneau séparé
```pine
indicator("Markov", overlay=false)  // Panneau propre sous le chart
plot(current_state, ...)       // 0-2, OK
plot(rsi_val, ...)             // 0-100, OK
plot(robustness, ...)          // 0-1, OK
```

**Approche 2 (avancée):** Normaliser tout en prix scale (complexe, rarement utile).

**Fichiers corrigés :** markov_stochastic_mtf.pine (changé overlay=false) — 2026-07-11
**Status:** ✅ RÉSOLU — indicateur affiche correctement en panneau séparé, sans flottage lors mouvement chart

---

## ✅ Patterns SÛRS — Pine Script v6

| Pattern | OK ? | Notes |
|---------|------|-------|
| `bool x = cond and\n  cond2` | ✅ | `and` en fin de ligne = continuation valide |
| `bool x = cond or\n  cond2` | ✅ | `or` en fin de ligne = continuation valide |
| `x = ternaire\n  : suite` | ✅ si non typé | Variable sans annotation de type |
| `float x = ternaire\n  : suite` | ❌ | Doit tenir sur une ligne |
| `ta.atr()`, `ta.ema()`, etc. | ✅ | Appels standard |
| `request.security()` avec tuple | ✅ | `[a, b] = request.security(...)` |
| Multi-ligne dans `if/else` | ✅ | Pas de restriction sur les blocs |

---

## 📋 Checklist Agent Vérification (avant chaque livraison)

```
[ ] Aucune déclaration typée (float/int/bool/string/color) ne se termine par ":" en fin de ligne
[ ] Aucun ternaire avec type explicite ne s'étend sur plusieurs lignes
[ ] Toutes les fonctions sont appelées avec les bons types d'arguments
[ ] Les strategy.exit() référencent des strategy.entry() existants
[ ] Pas de variable réutilisée avec "=" au lieu de ":=" après déclaration
[ ] Les plots non-affichés utilisent color=na (pas de couleur visible)
```
