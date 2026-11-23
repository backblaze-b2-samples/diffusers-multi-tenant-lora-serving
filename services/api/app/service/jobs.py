"""Job queue: enqueue, lease-based claim, heartbeat, complete, fail.

A claim is the only moment presigned URLs are issued: a GET for the adapter
weight and a PUT for the output key, each short-lived, so a worker holds a
usable URL only while it holds the lease. A job whose worker stops
heartbeating is re-queued with the same seed on the next claim; completions
are accepted only from the current (worker_id, attempt).
"""

import logging
import secrets
import time
from datetime import UTC, datetime

from app.config import settings
from app.repo import adapter_store, jobs_db
from app.service import keys
from app.service.manifests import now_iso
from app.service.reports import maybe_write_report, to_job
from app.service.resolver import ResolvedAdapter, resolve
from app.service.runs import get_run
from app.types import (
    AppError,
    ClaimResponse,
    CompareRequest,
    GenerationRequest,
    Heartbeat,
    HeartbeatAck,
    Job,
    JobCompletion,
    JobFailure,
    RunDetail,
    WorkerAdapter,
    WorkerJob,
)
from app.types.identifiers import is_run_id

logger = logging.getLogger(__name__)
_POLL_INTERVAL = 0.25


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id() -> str:
    return f"run-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


def _job_row(tenant_id, run_id, r: ResolvedAdapter | None, prompt, negative, seed, steps, size):
    job_id = f"job-{secrets.token_hex(6)}"
    return {
        "job_id": job_id, "run_id": run_id, "tenant_id": tenant_id,
        "adapter": r.adapter if r else None, "version": r.version if r else None,
        "adapter_sha256": r.sha256 if r else None, "adapter_size": r.size_bytes if r else None,
        "adapter_tenant": r.manifest_tenant_id if r else None,
        "weight_key": r.weight_key if r else None, "base_model": settings.base_model,
        "scale": r.scale if r else None, "state": "queued", "seed": seed, "steps": steps,
        "width": size, "height": size, "prompt": prompt, "negative_prompt": negative,
        "output_key": keys.output_key(tenant_id, run_id, job_id), "created_at": now_iso(),
    }


def _run_id(requested: str | None) -> str:
    if requested is None:
        return new_run_id()
    if not is_run_id(requested):
        raise AppError(422, "invalid_identifier", "run_id must match [a-z0-9-], 4-64 chars")
    return requested


def _seed(seed: int | None) -> int:
    return seed if seed is not None else secrets.randbelow(2**31)


def enqueue_generation(tenant_id: str, req: GenerationRequest) -> Job:
    resolved = resolve(tenant_id, req.adapter, req.scale)  # raises before any job exists
    run_id = _run_id(req.run_id)
    row = _job_row(tenant_id, run_id, resolved, req.prompt, req.negative_prompt,
                   _seed(req.seed), req.steps, req.size)
    jobs_db.ensure_run(run_id, now_iso())
    jobs_db.insert_jobs([row])
    return get_job(row["job_id"])


def enqueue_compare(req: CompareRequest) -> RunDetail:
    resolved = [resolve(req.tenant_id, ref, None) for ref in req.adapters]
    if req.include_base:
        resolved.append(None)
    run_id, seed = new_run_id(), _seed(req.seed)
    rows = [_job_row(req.tenant_id, run_id, r, req.prompt, None, seed, req.steps, req.size)
            for r in resolved]
    jobs_db.ensure_run(run_id, now_iso())
    jobs_db.insert_jobs(rows)
    return get_run(run_id)


def get_job(job_id: str) -> Job:
    row = jobs_db.get_job(job_id)
    if row is None:
        raise AppError(404, "job_not_found", f"job '{job_id}' not found")
    return to_job(row)


def list_jobs(tenant_id: str | None, state: str | None) -> list[Job]:
    return [to_job(r) for r in jobs_db.list_jobs(tenant_id=tenant_id, state=state)]


def output_url(job_id: str) -> str:
    job = get_job(job_id)
    if job.state != "succeeded":
        raise AppError(409, "job_not_succeeded", "the job has no output yet")
    return adapter_store.presign_get(job.output_key, settings.output_url_ttl_seconds)


def reap_expired() -> None:
    for row in jobs_db.expire_leases(time.time(), settings.job_max_attempts):
        logger.warning("job %s failed: lease_exhausted", row["job_id"])
        maybe_write_report(row["run_id"])


def _worker_job(row: dict) -> WorkerJob:
    now = time.time()
    adapter = None
    if row["adapter"]:
        adapter = WorkerAdapter(
            tenant_id=row["adapter_tenant"], adapter=row["adapter"], version=row["version"],
            sha256=row["adapter_sha256"], size_bytes=row["adapter_size"],
            base_model=row["base_model"], scale=row["scale"], weight_key=row["weight_key"],
            url=adapter_store.presign_get(row["weight_key"], settings.adapter_url_ttl_seconds),
            url_expires_at=_iso(now + settings.adapter_url_ttl_seconds),
        )
    return WorkerJob(
        job_id=row["job_id"], attempt=row["attempt"], run_id=row["run_id"],
        tenant_id=row["tenant_id"], adapter=adapter, output_key=row["output_key"],
        output_url=adapter_store.presign_put(
            row["output_key"], settings.output_url_ttl_seconds, "image/png"
        ),
        prompt=row["prompt"], negative_prompt=row["negative_prompt"], seed=row["seed"],
        steps=row["steps"], width=row["width"], height=row["height"],
    )


def claim(worker_id: str, wait_seconds: int) -> ClaimResponse:
    if jobs_db.get_worker(worker_id) is None:
        raise AppError(409, "worker_not_registered", "call /worker/register first")
    deadline = time.monotonic() + wait_seconds
    while True:
        reap_expired()
        now = time.time()
        jobs_db.touch_worker(worker_id, now)
        row = jobs_db.claim_next(worker_id, now, settings.job_lease_seconds)
        if row is not None:
            logger.info("job %s claimed by %s attempt=%d", row["job_id"], worker_id, row["attempt"])
            return ClaimResponse(job=_worker_job(row))
        if time.monotonic() >= deadline:
            return ClaimResponse(job=None)
        time.sleep(_POLL_INTERVAL)


def _stale(job_id: str) -> AppError:
    if jobs_db.get_job(job_id) is None:
        return AppError(404, "job_not_found", f"job '{job_id}' not found")
    return AppError(409, "stale_attempt", "this worker no longer holds the job's current attempt")


def heartbeat(job_id: str, hb: Heartbeat) -> HeartbeatAck:
    now = time.time()
    lease = now + settings.job_lease_seconds
    fields = {"lease_expires_at": lease}
    if hb.step is not None:
        fields["step"] = hb.step
    if not jobs_db.update_job_if_current(job_id, hb.worker_id, hb.attempt, fields):
        raise _stale(job_id)
    jobs_db.touch_worker(hb.worker_id, now)
    return HeartbeatAck(lease_expires_at=_iso(lease))


def complete(job_id: str, c: JobCompletion) -> Job:
    row = jobs_db.get_job(job_id)
    if row is None or row["state"] != "running" or row["worker_id"] != c.worker_id \
            or row["attempt"] != c.attempt:
        raise _stale(job_id)
    now = time.time()
    worker = jobs_db.get_worker(c.worker_id) or {}
    fields = {
        "cache": c.cache, "bytes_fetched": c.bytes_fetched,
        "sha256_verified": int(c.sha256_verified), "fetch_ms": c.fetch_ms,
        "load_ms": c.load_ms, "generate_ms": c.generate_ms, "unload_ms": c.unload_ms,
        "total_ms": int((now - (row["started_at"] or now)) * 1000),
        "output_sha256": c.output_sha256, "adapters_after_unload": c.adapters_after_unload,
        "finished_at": _iso(now), "lease_expires_at": None, "device": worker.get("device"),
    }
    error = None
    if c.adapters_after_unload:
        error = ("adapter_residue", f"adapters still loaded after unload: {c.adapters_after_unload}")
    elif row["adapter"] and not c.sha256_verified:
        error = ("checksum_unverified", "worker did not verify the adapter sha256")
    elif adapter_store.head(row["output_key"]) is None:
        error = ("output_missing", "the output image is not in B2")
    if error:
        fields.update(state="failed", error_code=error[0], error_message=error[1])
    else:
        fields["state"] = "succeeded"
    if not jobs_db.update_job_if_current(job_id, c.worker_id, c.attempt, fields):
        raise _stale(job_id)
    jobs_db.touch_worker(c.worker_id, now, job_done=True)
    maybe_write_report(row["run_id"])
    return get_job(job_id)


def fail(job_id: str, f: JobFailure) -> Job:
    now = time.time()
    fields = {"state": "failed", "error_code": f.code, "error_message": f.message[:2000],
              "finished_at": _iso(now), "lease_expires_at": None}
    if not jobs_db.update_job_if_current(job_id, f.worker_id, f.attempt, fields):
        raise _stale(job_id)
    jobs_db.touch_worker(f.worker_id, now)
    logger.warning("job %s failed by %s: %s", job_id, f.worker_id, f.code)
    row = jobs_db.get_job(job_id)
    maybe_write_report(row["run_id"])
    return to_job(row)
