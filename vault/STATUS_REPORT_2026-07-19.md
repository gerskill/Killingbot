# Killingbot — Rapport de statut (2026-07-19)

## 1. Stratégies

| Fichier | Statut | Preuve |
| --- | --- | --- |
| `pp_st_btc_4h_final.pine` | ✅ **Confirmée rentable en direct** | Strategy Tester TradingView : BINANCE:BTCUSDT 4H +2947.56%/DD 24.53%/PF 2.52/WR 33.9%/59 trades ; recoupé sur BITSTAMP:BTCUSD +8058.68%/DD 18.77%/PF 2.635/81 trades |
| `kb_15m_strategy.pine` | 🗑️ **Supprimé** — annonçait +7.9%/mois mais testé en direct = P&L −8.76%, PF 0.465 (perdant) | Testé BTCUSDT 15m, 579 trades réels |
| `kb_multi_asset_modular_v1.pine` | ⚠️ **Non testé en direct** — code créé (f_regime/f_score/f_risk modulaires) mais jamais compilé/backtesté dans TradingView | À faire avant toute confiance |
| Tableau `vault/BEST_STRATEGIES.md` (9 lignes restantes hors KB_15m) | ⚠️ **Invalidé, non re-vérifié** | Issu du même sweep automatique que KB_15m — aucune preuve live |

**Règle en place** (mémorisée) : plus aucun chiffre de performance n'est présenté comme fiable sans test live dans le Strategy Tester — un commentaire de fichier `.pine` peut mentir.

## 2. Script TradingView lié à l'alerte live

- ID `USER;b92db3a4fafc4fba9bb8f361989f510e`, nom affiché dans la liste TradingView : **"KB_15m — EMA × Kijun × ATR"** (trompeur).
- Contenu réel du script : **PP-ST + EMA200 + ADX — BTC 4H** (celui qui est confirmé rentable) — vérifié via `pine_get_source`.
- Alerte live : id `5176102342`, `BITSTAMP:BTCUSD`, résolution 4H (240), message = `{{strategy.order.alert_message}}` (confirmé par vous après modification manuelle).
- **Action recommandée, non faite** : renommer le script dans TradingView (clic droit → renommer dans la liste des scripts) pour éviter toute confusion future. Aucun outil MCP ne permet ce renommage à distance.
- Chart nettoyé : 2 doublons d'indicateur supprimés, il ne reste que l'instance liée à l'alerte.

## 3. Alertes JSON / webhook

`pp_st_btc_4h_final.pine` envoie désormais un `alert_message` JSON structuré sur les ordres :
```json
{"setup":"A*","dir":"LONG","ticker":"{{ticker}}","tf":"{{interval}}","price":"{{close}}","exchange":"{{exchange}}"}
```
Compilé sans erreur et poussé sur le script live.

## 4. Pipeline webhook — audit et corrections (sans changement de comportement)

Fichier : `webhook_server.py`. Trois défauts de robustesse corrigés aujourd'hui, aucun n'altère le flux fonctionnel existant :

1. **`call_claude_agent()`** — ne capturait que `FileNotFoundError`/`TimeoutExpired`. Une autre exception (ex. erreur du CLI `claude`) faisait planter toute la requête `/webhook` en 500 — **alors que le signal était déjà loggé**. Corrigé : `except Exception` générique, le signal reste loggé, l'agent est simplement ignoré si erreur.
2. **`/signals`** — `json.loads()` sur chaque ligne du fichier JSONL sans protection : une seule ligne corrompue (écriture interrompue) aurait fait planter tout l'endpoint. Corrigé : lignes invalides ignorées individuellement avec log console, le reste des signaux s'affiche normalement.
3. **`/health`** — ouvrait `signals_log.jsonl` sans jamais fermer le descripteur (fuite mineure sur un process long-lived). Corrigé avec `with open(...)`.

**Confirmé fonctionnel de bout en bout** par vos propres tests `curl` (localhost et ngrok) : POST `/webhook` avec JSON `setup=A*` → HTTP 200 `{"action":"logged","setup":"A*","status":"ok"}` → signal visible dans `/signals` avec timestamp correct.

**Non résolu / à surveiller** :
- Le process Python qui bloquait le port 5001 (PID 57999, `kill` simple resté sans effet) n'a jamais été confirmé arrêté. S'il tourne encore en parallèle d'un nouveau process, deux instances pourraient écrire dans les mêmes logs sans casser le fonctionnement, mais un `kill -9 57999` (ou `lsof -i :5001` pour vérifier) reste recommandé pour un état propre.
- Mon environnement sandbox ne peut pas atteindre les domaines `*.ngrok-free.dev` (limitation réseau de ma session, pas de votre machine) — toute vérification connectivité future doit se faire depuis votre propre terminal.

## 5. Modules construits mais non branchés en production

- **`agents/garch_position_sizer.py`** — position sizing GARCH(1,1) avec repli EWMA, testé uniquement sur données synthétiques (`sigma_forecast_pct: 0.959`, `size_multiplier: 1.0428`). Pas encore appelé depuis `webhook_server.py`.
- **`pine_scripts/indicators/ewma_vol_sizer.pine`** — approximation Pine (EWMA λ=0.94) du même concept, avec dashboard. Non testé en direct.
- **`pine_scripts/strategies/kb_multi_asset_modular_v1.pine`** — architecture 7 couches complète (régime, score, risk), conçue pour BTC/EURUSD/XAUUSD/SPX en parallèle. Vérifié uniquement contre la checklist `PINE_ERRORS.md`, jamais compilé/backtesté réellement.

## 6. Prochaines priorités (proposées, à confirmer)

1. Tester en direct `kb_multi_asset_modular_v1.pine` sur au moins un actif hors BTC avant d'y accorder du crédit.
2. Renommer le script TradingView `b92db3a4...` pour lever l'ambiguïté KB_15m / PP-ST.
3. Confirmer l'arrêt du process fantôme sur le port 5001.
4. Vérifier la date d'expiration de l'alerte TradingView live et la renouveler si nécessaire (les alertes gratuites/pro expirent périodiquement selon le plan TradingView) — non vérifié dans cette session.
5. Brancher `garch_position_sizer.py` dans `webhook_server.py` si le sizing dynamique est toujours souhaité.

*Note sur "avec superpowers" : le dossier `superpowers` (contributions au plugin open-source du même nom) est un projet séparé sans lien technique avec Killingbot — ce rapport ne couvre que Killingbot. Si vous vouliez dire autre chose par cette mention, précisez et je creuse.*
