"""Runs: a group of jobs sharing a run id, and its `adapters.json` report."""

from app.repo import adapter_store, jobs_db
from app.service import keys
from app.service.reports import to_job
from app.types import AdapterReport, AppError, RunDetail, RunSummary


def get_run(run_id: str) -> RunDetail:
    run = jobs_db.get_run(run_id)
    if run is None:
        raise AppError(404, "run_not_found", f"run '{run_id}' not found")
    rows = jobs_db.list_jobs(run_id=run_id, limit=10_000, oldest_first=True)
    return RunDetail(
        run_id=run_id, created_at=run["created_at"], jobs=[to_job(r) for r in rows],
        report_key=run["report_key"],
    )


def list_runs() -> list[RunSummary]:
    return [
        RunSummary(
            run_id=r["run_id"], created_at=r["created_at"], job_count=r["job_count"] or 0,
            state="active" if (r["active"] or 0) > 0 else "done", report_key=r["report_key"],
        )
        for r in jobs_db.list_runs()
    ]


def get_report(run_id: str) -> AdapterReport:
    if jobs_db.get_run(run_id) is None:
        raise AppError(404, "run_not_found", f"run '{run_id}' not found")
    got = adapter_store.get_json(keys.report_key(run_id))
    if got is None:
        raise AppError(404, "report_not_ready", "the report is written when the run's last job ends")
    return AdapterReport.model_validate(got[0])
