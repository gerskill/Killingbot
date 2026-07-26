# Stoic Lens Dashboard — Killingbot

Dashboard HTML standalone pour le protocole **Stoic Trader** (@StoicTA), branché sur l'indicateur Pine v6 `stoic_confluence_indicator.pine`.

## 🚀 Utilisation immédiate

Ouvre `stoic_dashboard.html` dans n'importe quel navigateur. Aucun build, aucune dépendance locale — Tailwind + Alpine.js + Chart.js sont chargés depuis CDN.

```bash
open app/stoic_dashboard.html
```

## 🧭 Les 5 onglets

| Onglet | Rôle |
|--------|------|
| 📊 **Rapports Stoic** | Cartes setup par actif avec scoring 4 piliers et niveaux clés (HCOM/LCOM/PDH/PDL/PDC). Cliquable → détail + pré-remplissage checklist. |
| ✅ **Checklist manuelle** | Validation pré-trade : 5 filtres Stoic + 4 piliers + risk management. Verdict GO/NO-GO automatique. Logger comme trade pris ou skippé. |
| 📜 **Historique auto** | Tous les trades (auto webhook + manuels). Stats live : WR, PF, Net R. Outcome éditable. Equity curve. Export CSV. |
| 📥 **Inbox JSON** | Coller le payload JSON envoyé par le webhook TradingView. Auto-création des rapports + logging trades (score ≥ 3). |
| ⚙️ **Réglages** | Export / import complet (backup), infos. |

## 🔗 Pipeline complet

```
TradingView
   │ Indicateur Pine v6 (stoic_confluence_indicator.pine)
   │ Alerte JSON déclenchée au score ≥ 3
   ▼
Webhook server (webhook_server.py, port 5001)
   │ Persiste le JSON
   ▼
Dashboard (stoic_dashboard.html)
   │ Lit / colle JSON via onglet Inbox
   │ Met à jour Rapports + Historique
   ▼
Trader (manuel)
   │ Valide via Checklist
   │ Logge l'outcome après clôture
   ▼
Stats agrégées (WR, PF, R cumulé)
```

## 📦 Stockage

Toutes les données sont dans `localStorage` (navigateur). Pour conserver :
- Onglet **Réglages → Export complet (JSON)** → fichier de backup.
- Re-import via le même onglet.

## 🚧 Vercel deployment (étape suivante)

Pour transformer ce dashboard en SaaS multi-device :
1. Wrapper dans un Next.js minimal (`pages/index.tsx` qui sert le HTML).
2. Remplacer `localStorage` par Supabase (Postgres + Auth).
3. Endpoint `/api/webhook` qui reçoit les alertes TradingView et persiste en DB.
4. Déployer sur Vercel.

Étape réservée à une session ultérieure (voir CLAUDE.md — l'objectif actuel est l'option la plus simple et interactive).

## 🎨 Stack

- **Tailwind CSS** (CDN) — styling
- **Alpine.js 3** (CDN) — réactivité
- **Chart.js 4** (CDN) — équity curve
- **Vanilla JS + localStorage** — persistance

## 📜 Crédits

Protocole : [@StoicTA](https://twitter.com/StoicTA)
Implémentation : Claude Trading Architect × Killingbot
