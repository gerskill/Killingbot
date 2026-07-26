"""
core/queue.py — Async task queue (local SQS equivalent)
Pattern: webhook_server enqueue -> worker process async

NOTE: lazy-init pour éviter mismatch event loop (uvicorn vs module-import).
"""
import asyncio
import json
from datetime import datetime
from typing import Callable
from pathlib import Path

DEAD_LETTER = Path(__file__).parent.parent / "logs" / "dead_letter.jsonl"


class TaskQueue:
    def __init__(self, maxsize: int = 100):
        self._maxsize = maxsize
        self._q: asyncio.Queue | None = None
        self._workers: list[asyncio.Task] = []

    def _ensure_queue(self):
        """Lazy-init: crée la queue dans le loop courant."""
        if self._q is None:
            self._q = asyncio.Queue(maxsize=self._maxsize)

    async def enqueue(self, task_type: str, payload: dict) -> str:
        self._ensure_queue()
        task_id = f"{task_type}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        item = {"task_id": task_id, "type": task_type, "payload": payload, "enqueued_at": datetime.utcnow().isoformat()}
        await self._q.put(item)
        return task_id

    def enqueue_nowait(self, task_type: str, payload: dict) -> str:
        self._ensure_queue()
        task_id = f"{task_type}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        item = {"task_id": task_id, "type": task_type, "payload": payload, "enqueued_at": datetime.utcnow().isoformat()}
        self._q.put_nowait(item)
        return task_id

    def start_worker(self, handler: Callable, n: int = 1):
        self._ensure_queue()
        for _ in range(n):
            task = asyncio.create_task(self._worker_loop(handler))
            self._workers.append(task)

    async def _worker_loop(self, handler: Callable):
        while True:
            item = await self._q.get()
            try:
                await handler(item)
            except Exception as e:
                self._dead_letter(item, str(e))
            finally:
                self._q.task_done()

    def _dead_letter(self, item: dict, error: str):
        DEAD_LETTER.parent.mkdir(exist_ok=True)
        entry = {**item, "error": error, "failed_at": datetime.utcnow().isoformat()}
        with open(DEAD_LETTER, "a") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"[QUEUE] dead-letter: {item.get('task_id')} — {error}")

    @property
    def size(self) -> int:
        return self._q.qsize() if self._q else 0


signal_queue = TaskQueue()
