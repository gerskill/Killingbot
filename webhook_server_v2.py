"""
webhook_server_v2.py — FastAPI async webhook (OSB pattern, remplace Flask)
==========================================================================
Pattern vidéo : client → FastAPI → queue async → worker → sidecars → DB

Architecture :
    TradingView alert
        └─> POST /webhook              (FastAPI, ~5ms)
              └─> signal_queue.enqueue (async, non-bloquant)
                    └─> worker()
                          ├─> signal_filter  (sidecar 1)
                          ├─> risk_manager   (sidecar 2)
                          └─> journal        (sidecar 3)

Démarrage :
    uvicorn webhook_server_v2:app --host 0.0.0.0 --port 5001 --reload

Exposer via ngrok :
    ngrok http 5001
"""
import sys
import asyncio
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

from core.queue import signal_queue
from sidecars import signal_filter, risk_manager, journal

# ─────────────────────────────────────────────────────────────────────────────
# WORKER — traitement async (équivalent SQS worker du vidéo)
# ─────────────────────────────────────────────────────────────────────────────

async def process_signal(item: dict):
    """
    Worker async : reçoit tâche depuis queue, passe dans les 3 sidecars.
    S'exécute hors du thread HTTP → webhook répond en ~5ms.
    """
    payload = item["payload"]
    task_id = item["task_id"]
    print(f"[WORKER] Traitement {task_id}")

    # Sidecar 1 — Validation signal
    filter_result = signal_filter.validate(payload)
    if not filter_result.passed:
        print(f"[FILTER] REJETÉ — {filter_result.rejection_reason}")
        journal.log_signal({**payload, "status": "rejected", "reason": filter_result.rejection_reason})
        return

    for w in filter_result.warnings:
        print(f"[FILTER] ⚠ {w}")

    # Sidecar 2 — Risk management
    risk_result = risk_manager.evaluate(payload)
    if not risk_result.approved:
        print(f"[RISK]   BLOQUÉ — {risk_result.rejection_reason}")
        journal.log_signal({**payload, "status": "risk_blocked", "reason": risk_result.rejection_reason})
        return

    print(f"[RISK]   OK — size={risk_result.position_size_usd}$ risk={risk_result.risk_usd}$ SL={risk_result.stop_loss_pct}%")

    # Sidecar 3 — Journal
    journal.log_signal({**payload, "status": "accepted"})
    trade_id = journal.open_trade(
        payload,
        risk_usd=risk_result.risk_usd,
        position_size_usd=risk_result.position_size_usd,
    )
    print(f"[JOURNAL] Trade ouvert → {trade_id}")

    # Sync dashboard (non-bloquant)
    _sync_dashboard()

    # Signal A* → déclencher agent Claude
    if filter_result.setup == "A*":
        await _call_claude_agent(payload, risk_result, trade_id)


def _sync_dashboard():
    sync_script = Path(__file__).parent / "scripts" / "sync_dashboard.py"
    if sync_script.exists():
        subprocess.Popen(
            ["python3", str(sync_script)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )


async def _call_claude_agent(payload: dict, risk: risk_manager.RiskResult, trade_id: str):
    context = (
        f"Signal A* validé — TraderMorin 5 étapes OK\n"
        f"  Ticker    : {payload.get('ticker')}\n"
        f"  Direction : {payload.get('dir')}\n"
        f"  Timeframe : {payload.get('tf')}\n"
        f"  Prix      : {payload.get('price')}\n"
        f"  Size      : {risk.position_size_usd}$\n"
        f"  Risk      : {risk.risk_usd}$ ({risk.stop_loss_pct}% SL)\n"
        f"  Trade ID  : {trade_id}\n"
        f"Analyse confluence et confirme ou rejette."
    )
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _subprocess_claude, context)


def _subprocess_claude(context: str):
    try:
        subprocess.run(
            ["claude", "-p", context, "--model", "claude-haiku-4-5-20251001"],
            timeout=30, capture_output=True, text=True
        )
    except Exception as e:
        print(f"[CLAUDE] Erreur agent : {e}")


# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Démarre le worker au boot (équivalent SQS consumer)."""
    signal_queue.start_worker(process_signal, n=2)
    print("[SERVER] Workers démarrés (n=2)")
    yield
    print("[SERVER] Shutdown")


app = FastAPI(title="Killingbot Webhook Server v2", lifespan=lifespan)


@app.post("/webhook")
async def webhook(request: Request):
    """
    Reçoit alerte TradingView, enqueue, répond immédiatement (~5ms).
    Le worker traite en arrière-plan.
    """
    try:
        payload = await request.json()
    except Exception:
        raw = await request.body()
        payload = {"raw": raw.decode("utf-8", errors="replace")}

    if not payload:
        return JSONResponse({"status": "error", "msg": "empty payload"}, status_code=400)

    task_id = signal_queue.enqueue_nowait("signal", payload)
    return JSONResponse({"status": "queued", "task_id": task_id, "queue_size": signal_queue.size})


@app.get("/health")
async def health():
    signals_count = 0
    signals_log = Path(__file__).parent / "signals_log.jsonl"
    if signals_log.exists():
        signals_count = signals_log.read_text().count("\n")
    return {
        "status": "running",
        "queue_size": signal_queue.size,
        "signals_logged": signals_count,
        "workers": 2,
    }


@app.get("/signals")
async def signals():
    return journal.recent_signals(20)


@app.post("/sovereign/generate")
async def sovereign_generate(request: Request):
    """Génère un script Pine depuis le context courant (Sovereign endpoint)."""
    body = await request.json()
    from sovereign.engine import PineEngine
    engine = PineEngine()
    title = body.get("title", "KB_SOVEREIGN")
    fname = body.get("filename") or f"{title.lower()}.pine"
    path = engine.generate(
        title=title,
        use_rsi=body.get("use_rsi", False),
        params=body.get("params", {}),
        filename=fname,
    )
    code = path.read_text()
    return {"status": "ok", "file": str(path), "lines": code.count("\n"), "preview": code[:300]}


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════╗
║  KILLINGBOT WEBHOOK SERVER v2 — FastAPI Async (OSB)      ║
╠═══════════════════════════════════════════════════════════╣
║  POST  /webhook              → signal pipeline async     ║
║  GET   /health               → état queue + workers      ║
║  GET   /signals              → 20 derniers signaux       ║
║  POST  /sovereign/generate   → génère Pine depuis ctx    ║
╚═══════════════════════════════════════════════════════════╝
""")
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
