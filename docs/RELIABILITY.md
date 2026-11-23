<!-- last_verified: 2026-11-23 -->
# Reliability

Reliability expectations and practices for this project.

## Health Checks

- `GET /health` reports B2 connectivity (`healthy` or `degraded`), the base model and the number of workers online; it answers HTTP 200 even when B2 is down
- The B2 client bounds connects to 5 s, reads to 30 s, and retries to 3 total attempts
- `GET /workers` shows each worker's device, last heartbeat or claim, current job and cache size

## Publish: Manifest Last

- A version becomes resolvable only when the tenant manifest is rewritten, after the weight is stored (size checked with `head_object`) and the immutable version manifest is written
- A failure at any earlier step leaves the tenant manifest unchanged, so requests never resolve to a half-published version; the stray weight or version manifest is harmless and the same version can be retried only after deleting it (publishing an existing version is 409)
- One dispatcher owns manifest writes, serialized by a per-tenant lock. Several dispatchers writing one tenant's manifest concurrently is out of scope
- The dispatcher caches a manifest for 10 s, then revalidates it with a HEAD (ETag); its own writes replace the cached copy at once. A manifest edited outside the app is picked up within about 10 s

## Jobs: Leases and Retries

- The queue is SQLite in WAL mode (`JOBS_DB_PATH`); a claim runs in one transaction under one lock, so a job is never handed to two workers
- A claim leases the job for `JOB_LEASE_SECONDS` (default 30) and increments `attempt`; the worker heartbeats every `JOB_HEARTBEAT_SECONDS` (default 5) with the current step
- A worker that dies stops heartbeating; the next claim re-queues the expired job with the same seed (attempt + 1), up to `JOB_MAX_ATTEMPTS` (default 3), then marks it `failed: lease_exhausted`
- **Same seed, same image**: generation uses `torch.Generator("cpu").manual_seed(seed)` on the same base model and the same adapter bytes, so the retry renders the identical image. Measured: the self-test's SIGKILLed job came back bit-identical from the other worker
- **Stale attempts are rejected**: heartbeats, completions and failures are accepted only from the current `(worker_id, attempt)`; anything else gets 409 `stale_attempt`, and a worker that receives it stops at the next denoising step and drops its result
- Presigned URLs are issued fresh on every claim, so a retried job never relies on an expired URL
- The dispatcher checks the output exists in B2 (`head_object`) before marking a job `succeeded`

## Error Handling

- Expected failures use `AppError` and return `{"detail", "code"}` with a stable code
- Uncaught exceptions become a typed JSON 500 in `timing_middleware`
- `CORSMiddleware` is outermost, so error responses keep their CORS headers (regression-guarded by `tests/test_error_handling.py`)

## Worker Robustness

- The adapter is unloaded in a `finally`, so a failed generation never leaves it loaded
- A download streams to a temp file and is moved into the cache only after the sha256 and size match; a cache entry is re-hashed before use (`ADAPTER_CACHE_VERIFY_ON_HIT`), and a bad one is dropped and refetched
- The cache evicts least-recently-used files above `ADAPTER_CACHE_MAX_BYTES`
- A worker retries registration and claims while the dispatcher is unreachable

## Logging

- Structured JSON logging in the dispatcher and the workers; every request has a `request_id`; rejections log tenant and code

## Observability

- `/metrics`: per-route request counts and durations, `adapter_rejections_total{code}`
- `reports/<run-id>/adapters.json`: per-job fetch, load, generate and unload times, cache results and retries

## Stateful Counters, durability caveats

- The job queue survives a dispatcher restart (SQLite file); `/metrics` counters and the download counter are in-process and reset on restart
- The download counter persists to `DOWNLOAD_COUNT_FILE` (default `.data/download_count.json` at the repo root)

## Rate Limiting

- Per-IP limiter on browser routes; `/worker/*` is exempt and gated by `WORKER_TOKEN`

## Graceful Degradation

- No workers online: jobs wait in the queue and run when a worker connects
- B2 unreachable at claim time: the job stays leased without URLs, the lease expires, and a later claim retries it
- Bucket explorer listing is cached and served stale-while-revalidate (`LIST_CACHE_TTL_SECONDS`); `WARM_LIST_CACHE_ON_STARTUP=false` skips the startup scan

## Deployment

- No platform runbook ships: workers need a local GPU. Run one dispatcher and point workers at it with `API_URL` and a shared `WORKER_TOKEN`
- Environment-specific configuration uses environment variables; no values are committed
