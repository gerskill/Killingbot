# 🎯 KB SMC Fractal — Guide d'utilisation

> **Fichier** : `pine_scripts/indicators/smc_fractal_indicator.pine`
> **Type** : Indicator (pas une strategy — décision manuelle)
> **Inspiré** : @low_wick (XAUUSD), Range Scenarios, Elliott Wave corrections
> **Philosophie** : "React don't predict — be a pro, billions will come, chill out"

---

## 🎨 CE QUI S'AFFICHE SUR LE CHART

### 1. Asia Session (lignes bleues étendues)
- **Asia H** : plus haut de la session asiatique (00h-06h UTC par défaut)
- **Asia L** : plus bas de la session
- **Asia Mid** : milieu (pointillé) — niveau de réaction fréquent
- ⚙️ Adapter `Asia start/end UTC` selon l'heure de ton broker

### 2. Fractals (triangles vert/rouge)
- **Triangle rouge bas** = swing high confirmé (top local)
- **Triangle vert haut** = swing low confirmé (bottom local)
- Confirmation = N bougies de chaque côté (par défaut 2)

### 3. FVG — Fair Value Gaps (boxes transparentes vert/rouge)
- **Box verte** = gap haussier (low[1] > high[3]) — zone d'attraction pour pullback long
- **Box rouge** = gap baissier — zone d'attraction pour pullback short
- Le prix tend à les "combler" (fill) avant de continuer

### 4. Order Blocks (boxes pleines vert/rouge)
- **Box verte** = dernière bougie BAISSIÈRE avant une impulsion HAUSSIÈRE forte
- **Box rouge** = dernière bougie HAUSSIÈRE avant une impulsion BAISSIÈRE forte
- = zones où les institutionnels ont laissé des ordres → forte probabilité de réaction

### 5. Liquidity Sweeps (labels SWP↑ / SWP↓)
- **SWP↑** = wick a percé un swing low récent puis close au-dessus → trapped shorts
- **SWP↓** = wick a percé un swing high récent puis close en-dessous → trapped longs
- C'est la signature d'un "stop hunt" institutionnel

### 6. BOS — Break of Structure (lignes dashed + labels BOS↑/BOS↓)
- **BOS↑** = clôture au-dessus du dernier swing high → confirmation hausse
- **BOS↓** = clôture en-dessous du dernier swing low → confirmation baisse
- = changement de structure de marché

### 7. ★ POI — Points of Interest (labels jaunes)
- **★ POI LONG** = Order Block bull + Sweep long dans les 5 dernières barres
- **★ POI SHORT** = Order Block bear + Sweep short dans les 5 dernières barres
- = **SETUPS PRIORITAIRES** — c'est là qu'il faut regarder pour entrer

### 8. ABC corrections (labels A/B/C gris/jaune)
- Marque les 3 swings consécutifs d'une correction Elliott simple
- C en jaune = pivot de fin de correction = potentiel point d'entrée vers reprise du trend

### 9. Dashboard (en haut à droite)
- Tous les niveaux clés à un coup d'œil
- **Bias** auto-calculé (LONG/SHORT selon position vs milieu fractals)
- **Last Sweep timing** : combien de bougies depuis le dernier sweep

---

## 🎯 WORKFLOW DE TRADE (inspiré des Range Scenarios)

### Scénario 1 : Cassure de structure baissière
```
1. Range descendant identifié (swings high lower + swings low lower)
2. Le prix re-test une zone (POI bear ou Order Block bear)
3. → Cherche un sweep SWP↑ qui prend les stops des shorts
4. → BOS↓ confirme la baisse
5. → Entrée SHORT au retest de la zone POI
6. Target : External Range Liq (low du range étendu)
```

### Scénario 2 : Reversal après sweep
```
1. Tendance baissière prolongée
2. SWP↑ apparaît sur un swing low (trapped shorts)
3. ★ POI LONG s'affiche (OB bull + sweep recent)
4. → Entrée LONG sur retest du POI
5. Stop : sous le sweep low
6. Target : Asia H / Last Fract H / FVG bear à combler
```

### Règles d'or
1. **Ne PAS trader le first BOS** = liquidity pool, les stops sont juste au-dessus
2. **Attendre le 2e mouvement** (inducement → sweep → reclaim)
3. **POI = priorité absolue** : confluence multi-facteur = institutional setup
4. **Asia H/L** = niveaux clés pour rejection ou breakout
5. **Bias dashboard** = direction préférentielle (mais peut être inversé si POI fort opposé)

---

## ⚙️ PARAMÈTRES OPTIMAUX PAR TF

### Scalp 1m-5m (style @low_wick XAUUSD)
- `fractal_n` = 2
- `sweep_lookback` = 15-20
- `fvg_min_atr` = 0.2
- `ob_min_impulse_atr` = 1.2
- `poi_window_bars` = 3

### Intraday 15m-1H
- `fractal_n` = 3
- `sweep_lookback` = 20-30
- `fvg_min_atr` = 0.3
- `ob_min_impulse_atr` = 1.5
- `poi_window_bars` = 5

### Swing 4H-1D
- `fractal_n` = 5
- `sweep_lookback` = 30-50
- `fvg_min_atr` = 0.5
- `ob_min_impulse_atr` = 2.0
- `poi_window_bars` = 10

---

## 🔔 ALERTES WEBHOOK

L'indicateur expose 6 conditions d'alerte natives TradingView :

| Alert | Message |
|---|---|
| `POI LONG` | "POI LONG on {{ticker}} {{interval}}" |
| `POI SHORT` | "POI SHORT on {{ticker}} {{interval}}" |
| `BOS Bull` | "BOS Bull on {{ticker}} {{interval}}" |
| `BOS Bear` | "BOS Bear on {{ticker}} {{interval}}" |
| `Sweep Long` | "Sweep Long on {{ticker}} {{interval}}" |
| `Sweep Short` | "Sweep Short on {{ticker}} {{interval}}" |

→ Brancher sur ton webhook `webhook_server.py` (port 5001) ou directement dans le dashboard `app/stoic_dashboard.html` onglet Inbox JSON.

---

## 🚨 LIMITES & WARNINGS

- **Pas une strategy** : aucun ordre auto. Décision 100% manuelle.
- **Fractals à confirmation retardée** : un fractal de N=2 est confirmé 2 bougies APRÈS le top/bottom réel
- **FVG peut être "fake"** : les vrais FVG méritent un retest, pas tous se comblent immédiatement
- **POI sur 5m = beaucoup de bruit** : sur scalp, filtrer par direction du HTF
- **L'indicateur affiche, c'est toi qui filtres** : selon le protocole Stoic, un setup peut être valide mais hors edge zone

---

## 📁 LIVRABLES

| Fichier | Description |
|---|---|
| `pine_scripts/indicators/smc_fractal_indicator.pine` | Code source Pine v6 |
| `docs/guides/SMC_INDICATOR_GUIDE.md` | Ce document |
| `backtest/screenshots/kb_smc_indicator_btc5m.png` | Rendu sur BTC 5m |
