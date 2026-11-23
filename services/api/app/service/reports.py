"""Run reports: `reports/<run-id>/adapters.json`, written when a run goes idle.

"Idle" means every job in the run is terminal. Adding jobs to the run later
and finishing them rewrites the report, so it always covers the whole run.
"""

import logging
import statistics

from app.config import settings
from app.repo import adapter_store, jobs_db
from app.service import keys
from app.service.manifests import now_iso
from app.types import AdapterReport, Job, JobTimings, ReportJob, ReportSummary

logger = logging.getLogger(__name__)
TERMINAL = ("succeeded", "failed")


def to_job(row: dict) -> Job:
    timings = None
    if row.get("total_ms") is not None:
        timings = JobTimings(
            fetch_ms=row["fetch_ms"] or 0, load_ms=row["load_ms"] or 0,
            generate_ms=row["generate_ms"] or 0, unload_ms=row["unload_ms"] or 0,
            total_ms=row["total_ms"] or 0,
        )
    return Job(
        job_id=row["job_id"], run_id=row["run_id"], tenant_id=row["tenant_id"],
        adapter=row["adapter"], version=row["version"], adapter_sha256=row["adapter_sha256"],
        scale=row["scale"], state=row["state"], attempt=row["attempt"],
        worker_id=row["worker_id"], seed=row["seed"], steps=row["steps"], width=row["width"],
        height=row["height"], prompt=row["prompt"], negative_prompt=row["negative_prompt"],
        step=row["step"], timings=timings, cache=row["cache"],
        bytes_fetched=row["bytes_fetched"], sha256_verified=row["sha256_verified"],
        output_key=row["output_key"], output_sha256=row["output_sha256"],
        adapters_after_unload=row["adapters_after_unload"], error_code=row["error_code"],
        error_message=row["error_message"], created_at=row["created_at"],
        finished_at=row["finished_at"],
    )


def _p50(values: list[int]) -> int:
    return int(statistics.median(values)) if values else 0


def build_report(run_id: str, rows: list[dict], created_at: str) -> AdapterReport:
    jobs = [
        ReportJob(
            job_id=r["job_id"], tenant_id=r["tenant_id"], adapter=r["adapter"],
            version=r["version"], adapter_sha256=r["adapter_sha256"],
            worker_id=r["worker_id"], attempt=r["attempt"], state=r["state"],
            cache=r["cache"], bytes_fetched=r["bytes_fetched"] or 0,
            fetch_ms=r["fetch_ms"] or 0, load_ms=r["load_ms"] or 0,
            generate_ms=r["generate_ms"] or 0, unload_ms=r["unload_ms"] or 0,
            total_ms=r["total_ms"] or 0, seed=r["seed"], steps=r["steps"],
            width=r["width"], height=r["height"], output_key=r["output_key"],
            output_sha256=r["output_sha256"], error_code=r["error_code"],
        )
        for r in rows
    ]
    ok = [j for j in jobs if j.state == "succeeded"]
    return AdapterReport(
        run_id=run_id, created_at=created_at, base_model=settings.base_model,
        device_summary=sorted({r["device"] for r in rows if r.get("device")}),
        jobs=jobs,
        summary=ReportSummary(
            jobs=len(jobs), succeeded=len(ok),
            failed=sum(1 for j in jobs if j.state == "failed"),
            cache_hits=sum(1 for j in ok if j.cache == "hit"),
            load_ms_p50=_p50([j.load_ms for j in ok if j.adapter]),
            generate_ms_p50=_p50([j.generate_ms for j in ok]),
            retried_jobs=sum(1 for j in jobs if j.attempt > 1),
        ),
    )


def maybe_write_report(run_id: str) -> str | None:
    """Write the run's report when its last job is terminal. Returns the key."""
    rows = jobs_db.list_jobs(run_id=run_id, limit=10_000, oldest_first=True)
    if not rows or any(r["state"] not in TERMINAL for r in rows):
        return None
    run = jobs_db.get_run(run_id)
    report = build_report(run_id, rows, run["created_at"] if run else now_iso())
    key = keys.report_key(run_id)
    try:
        adapter_store.put_json(key, report.model_dump(mode="json"))
    except RuntimeError:
        logger.exception("failed to write report for %s", run_id)
        return None
    jobs_db.set_report_key(run_id, key)
    return key
