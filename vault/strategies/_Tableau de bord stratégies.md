---
type: tableau-de-bord
tags: [strategie, index]
---

# Tableau de bord des stratégies

Une fiche par stratégie dans `vault/strategies/`. Le champ `statut` du YAML décide
du classement. La source qui fait foi reste [[INDEX]].

## Les statuts

| `statut` | Signification | Capital ? |
|---|---|---|
| `prouve-live` | Chiffres relus au Strategy Tester TradingView, en direct | paper ✅ |
| `walk-forward-ok` | Survit hors échantillon (`agents/validation.py`), pas encore relu en live | non |
| `non-verifie` | Seulement des chiffres annoncés (commentaire du fichier, ancien rapport), ou aucun | non |
| `echoue` | Testé (walk-forward ou grille), pas d'edge mécanique | non |
| `invalide` | Chiffres contredits par un test live — ne jamais les recopier | non |

**Règle** : on ne met des métriques dans le YAML (`net_pct`, `dd_pct`, `pf`…) que
pour `prouve-live` et `walk-forward-ok`. Pour les autres, on renvoie au rapport.

## Vue dynamique (plugin Dataview)

```dataview
TABLE WITHOUT ID
  file.link AS "Stratégie",
  statut AS "Statut",
  actif AS "Actif",
  timeframe AS "TF",
  pf AS "PF",
  dd_pct AS "DD %",
  oos_median_pct_mois AS "OOS médian %/mois",
  derniere_verif AS "Vérifié le"
FROM "vault/strategies"
WHERE type = "strategie"
SORT choice(statut = "prouve-live", 0, choice(statut = "walk-forward-ok", 1, choice(statut = "non-verifie", 2, choice(statut = "echoue", 3, 4)))) ASC, file.name ASC
```

> [!tip] Sans Dataview
> Installer *Dataview* (plugins communautaires). En attendant, la liste statique
> ci-dessous fait le même travail.

## Liste statique

### ✅ Prouvé en direct
- [[pp_st_btc_4h_final]] — PP-ST + EMA200 + ADX, BTC 4H

### 🟡 Walk-forward OK, pas encore live
- [[stoic_123_cassure]] — STOIC 1-2-3, entrée sur cassure (mode issu du test PTB)

### ⚪ Non vérifié
- [[pp_st_ppp_stocks]] — PP-ST + filtre fondamental PPP, actions (code prêt, à tester)
- [[pp_st_btc_4h]] · [[pp_st_btc_4h_v2_ls]]
- [[killingbot_hybrid_v1]] · [[killingbot_hybrid_v2]] · [[killingbot_hybrid_v3_mtf]]
- [[killingbot_intraday_v1]] · [[killingbot_meanrev_v1]]
- [[kb_15m_regime_v1]] · [[kb_confluence_v1]] · [[kb_multi_asset_modular_v1]] · [[kb_orb_vwap_v1]]
- [[kb_sovereign_v1]] · [[kb_auto_btc_4h]] · [[kb_structure_vwap_v1]] · [[kb_vibe_code_multi_signal]]
- [[dpo_overlay_strategy]] · [[mlrsi_ppst_strategy]]
- [[stoic_123]] · [[stoic_123_v2]] · [[stoic_lens_pure_v3]] · [[stoic_lens_strategy]]
- [[stoic_edge_strategy]] (v1, v1.1, v1.2, killingbot, killingbot_v2)

### ❌ Échoue
- [[stoic_123_ribbon]] — walk-forward 2026-07-26
- [[stoic_lens_pure_v2]] — walk-forward 2026-07-26
- [[stoic_sbs]] · [[stoic_confluence_strategy]] — pas d'edge mécanique

### 🚫 Invalidé
- [[Sweep KB_ 2026-05]] — 35 variantes, `KB_15m` démenti en live
