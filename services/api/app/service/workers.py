"""Worker registry: who is online, on what device, with how much cache."""

import time
from datetime import UTC, datetime

from app.config import settings
from app.repo import jobs_db
from app.types import AppError, WorkerAck, WorkerHello, WorkerStatus

# A worker long-polls claims for up to 25 s, so "online" allows one full poll
# plus slack, or three heartbeats, whichever is longer.
_CLAIM_WAIT_MAX = 25


def online_window() -> float:
    return max(_CLAIM_WAIT_MAX + 10, 3 * settings.job_heartbeat_seconds)


def register(hello: WorkerHello) -> WorkerAck:
    if hello.base_model != settings.base_model:
        raise AppError(
            422, "base_model_mismatch",
            f"worker loads {hello.base_model}; this dispatcher serves {settings.base_model}",
        )
    jobs_db.upsert_worker(hello.model_dump(), time.time())
    return WorkerAck(
        heartbeat_seconds=settings.job_heartbeat_seconds,
        lease_seconds=settings.job_lease_seconds,
    )


def list_workers() -> list[WorkerStatus]:
    now = time.time()
    return [
        WorkerStatus(
            worker_id=w["worker_id"], device=w["device"] or "", dtype=w["dtype"] or "",
            base_model=w["base_model"] or "",
            last_seen=datetime.fromtimestamp(w["last_seen"], UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            online=now - w["last_seen"] <= online_window(),
            current_job_id=w["current_job_id"], jobs_done=w["jobs_done"],
            cache_entries=w["cache_entries"], cache_bytes=w["cache_bytes"],
        )
        for w in jobs_db.list_workers()
    ]


def workers_online() -> int:
    now = time.time()
    return sum(1 for w in jobs_db.list_workers() if now - w["last_seen"] <= online_window())
