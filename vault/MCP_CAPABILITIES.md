# TradingView MCP — Carte des Capacités (diagnostic JARVIS 2026-07-09)

Diagnostic systématique de l'armure. État réel de chaque système.

## ✅ SYSTÈMES OPÉRATIONNELS

### Core
| Tool | État | Note |
|---|---|---|
| `tv_health_check` | ✅ | CDP + API interne dispo |
| `chart_get_state` | ✅ | Symbole, TF, studies + entity IDs |

### Données marché
| Tool | État | Note |
|---|---|---|
| `quote_get` | ✅ | Prix temps réel |
| `data_get_ohlcv` | ✅ | Toujours `summary=true` |
| `data_get_study_values` | ✅ | Valeurs indicateurs live (data window) |
| `symbol_search` | ✅ | 15+ sources par requête |
| `watchlist_get` | ✅ | 22 symboles avec prix |

### Navigation
| Tool | État | Note |
|---|---|---|
| `chart_set_symbol` | ✅ | Studies persistent au switch |
| `chart_set_timeframe` | ✅ | |
| `tab_list` / `tab_switch` | ✅ | ⚠️ 2 tabs ouverts = confusion possible |
| `pane_list` | ✅ | |

### Pine Script
| Tool | État | Note |
|---|---|---|
| `pine_check` | ✅ ⭐ | Compile SERVEUR sans toucher l'UI — valider AVANT injection |
| `pine_list_scripts` | ✅ | 146 scripts persos listés |
| `pine_open` | ✅ | REQUIERT éditeur ouvert (`ui_open_panel` d'abord) |
| `pine_get_errors` | ✅ | Markers Monaco |
| `pine_save` | ✅ | Dispatch Ctrl+S |

### Visuel & UI
| Tool | État | Note |
|---|---|---|
| `capture_screenshot` | ✅ | regions: full / chart / strategy_tester |
| `ui_open_panel` | ✅ | pine-editor, strategy-tester, watchlist... |
| `ui_evaluate` | ✅ ⭐ | JS arbitraire — l'outil le plus puissant, répare tout le reste |
| `ui_mouse_click` | ✅ | Clics CDP coords page |
| `ui_find_element` | ✅ | |
| `draw_shape` | ✅ | Création seulement (voir cassés) |
| `alert_list` | ✅ | |
| `replay_status` | ✅ | Replay dispo, non testé start/stop |

## ❌ SYSTÈMES CASSÉS (bugs MCP internes)

| Tool | Erreur | Workaround |
|---|---|---|
| `data_get_strategy_results` | "is_price_study" null | `ui_evaluate` → lire textContent du panneau tester ✓ prouvé |
| `data_get_trades` | idem | idem |
| `data_get_equity` | idem | idem |
| `draw_list` / `draw_clear` / `draw_remove_one` | "getChartApi is not defined" | Suppression manuelle uniquement |
| `chart_scroll_to_date` | "evaluate is not defined" | `ui_evaluate` custom |
| `chart_get_visible_range` | idem | idem |
| `symbol_info` | idem | `quote_get` donne l'essentiel |
| `batch_run` | Navigation OK, lecture KO | Boucle manuelle set_symbol + get_ohlcv |
| `pine_set_source` | Écrit modèle Monaco invisible | **Injection clipboard** (ci-dessous) |

## 🔧 PROCÉDURE INJECTION PINE FIABLE (prouvée)

```bash
# 1. Valider côté serveur
pine_check(source)  # 0 erreurs requis

# 2. Copier dans clipboard
cat script.pine | pbcopy

# 3. Focus éditeur (clic physique)
ui_mouse_click(x=1400, y=400)  # dans la zone éditeur

# 4. Coller via vraies frappes (osascript)
osascript: activate TradingView → Cmd+A → Cmd+V

# 5. Ajouter au chart
ui_evaluate: click button[title="Ajouter au Graphique"]
# ou si déjà sur chart: button[title="Actualiser sur le graphique"]

# 6. Lire résultats
ui_evaluate: document.querySelector('[id*="bottom-area"]').textContent
```

## ⚠️ PIÈGES CONNUS

1. **Pine v6 `margin_long` défaut 100%** → futures rejetés silencieusement (PINE_ERRORS.md #2)
2. **2 tabs TradingView ouverts** → tools tapent le tab actif CDP, fermer l'inutile
3. **Échelle flottante après re-add** → clic droit légende → Déplacer vers → Échelle droite (fusionner)
4. **`depth_get`** → nécessite panneau DOM ouvert manuellement
5. **`pine_open`** → toujours `ui_open_panel(pine-editor, open)` d'abord
6. **Ligne test fantôme** à 4130 sur XAUUSD (draw_clear cassé) → suppression manuelle
