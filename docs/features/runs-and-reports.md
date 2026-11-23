<!-- last_verified: 2026-11-23 -->
# Feature: Runs and Reports

## Purpose
Group jobs into runs, recover a killed worker's job on another worker with the same seed and the same image, and write a per-run `adapters.json` timing report to B2.

## Used By
- UI: `/runs`, `/runs/[runId]` (outputs side by side, summary, stacked timing chart)
- API: `GET /runs`, `GET /runs/{run_id}`, `GET /runs/{run_id}/report`, `GET /jobs`, `GET /jobs/{job_id}`, `GET /workers`

## Core Functions
- `services/api/app/repo/jobs_db.py` — SQLite (WAL) job, run and worker tables; atomic claim; lease expiry
- `services/api/app/service/jobs.py` — leases, heartbeats, stale-attempt rejection
- `services/api/app/service/reports.py` — `build_report`, `maybe_write_report`
- `services/api/app/service/runs.py` — run detail and report read
- `apps/web/src/components/runs/run-detail-view.tsx`, `apps/web/src/lib/report-chart.ts`

## Canonical Files
- `services/api/app/service/reports.py`

## Inputs
- Worker heartbeats (`attempt`, `step`), completions and failures

## Outputs
- `<APP_PREFIX>reports/<run-id>/adapters.json`: `run_id`, `created_at`, `base_model`, `device_summary`, `jobs[]` (adapter, sha256, worker, attempt, state, cache, bytes fetched, fetch/load/generate/unload/total ms, seed, steps, size, output key and sha256) and `summary` (`jobs`, `succeeded`, `failed`, `cache_hits`, `load_ms_p50`, `generate_ms_p50`, `retried_jobs`)

## Flow
- A claim leases the job for `JOB_LEASE_SECONDS`; the worker heartbeats every `JOB_HEARTBEAT_SECONDS`
- A worker that dies stops heartbeating; the next claim re-queues its job (attempt + 1, same seed) up to `JOB_MAX_ATTEMPTS`, then fails it `lease_exhausted`
- Completions are accepted only from the current `(worker_id, attempt)`; a late one gets 409 `stale_attempt`
- When a run's last job is terminal, the report is written (and rewritten if more jobs join the run)

## Edge Cases
- Report requested before the run ends -> 404 `report_not_ready`
- Output missing in B2 at completion -> job fails `output_missing`
- Dispatcher restart -> queue and runs persist in SQLite; presigned URLs are re-issued on the next claim

## UX States
- Empty: "No runs yet"
- Loading: skeletons; active runs poll every 2 s
- Report pending: "the report appears when they finish"

## Verification
- Test files: `services/api/tests/test_job_leases.py`, `test_report_writer.py`; `apps/web/src/lib/report-chart.test.ts`, `job-state.test.ts`
- Required cases: lease expiry re-queues with the same seed, stale attempt 409, attempts exhausted, report shape and summary math, report written on the last terminal job
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm selftest` (kills a worker with SIGKILL mid-job)
- Pass criteria: tests green; self-test worker-kill step renders the identical image on the second worker

## Related Docs
- [RELIABILITY.md](../RELIABILITY.md)
- [Adapter Serving](adapter-serving.md)
