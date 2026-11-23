<!-- last_verified: 2026-11-23 -->
# Feature: Adapter Serving

## Purpose
Serve every tenant's adapters from one shared base model on stateless workers: resolve each request through the requesting tenant's own manifest, hand the worker a short-lived presigned URL for exactly that adapter, verify it, load it, generate, and unload it.

## Used By
- UI: indirectly, through Generate and Compare
- API: `POST /tenants/{tenant_id}/generations`, `POST /runs/compare` (resolution), and the worker protocol `POST /worker/register`, `/worker/jobs/claim`, `/worker/jobs/{job_id}/heartbeat|complete|fail`
- Job: `services/worker` (`pnpm worker`, `pnpm dev:workers`)

## Core Functions
- `services/api/app/service/resolver.py`: tenant-scoped resolution and isolation checks
- `services/api/app/service/jobs.py`: enqueue, claim (presigns at claim time), heartbeat, complete, fail, lease reaper
- `services/api/app/runtime/worker_protocol.py`: worker routes, `WORKER_TOKEN` bearer check
- `services/worker/worker/runner.py`: one job end to end; unload in `finally`
- `services/worker/worker/fetch.py`: streamed download with sha256 and size check
- `services/worker/worker/cache.py`: `<cache>/<tenant>/<sha256>.safetensors`, re-hash on hit, LRU eviction
- `services/worker/worker/pipeline.py`: `load_lora_weights`, `set_adapters`, generate, `delete_adapters`, `get_list_adapters`
- `services/worker/worker/device.py`: CUDA, then MPS, then CPU

## Canonical Files
- Isolation rules: `services/api/app/service/resolver.py`
- Worker job loop: `services/worker/worker/runner.py`

## Inputs
- `GenerationRequest`: `adapter` (`name`, `name@version`, `owner/name[@version]`, or null), `prompt`, `negative_prompt?`, `seed?`, `steps` (15 | 25 | 40), `size` (768 | 1024), `scale?`, `run_id?`

## Outputs
- A queued `Job`; on completion an image at `<APP_PREFIX>outputs/<tenant>/<run-id>/<job-id>.png` and per-job `fetch_ms`, `load_ms`, `generate_ms`, `unload_ms`, `cache`, `bytes_fetched`, `adapters_after_unload`

## Flow
- Resolver: owner other than the tenant -> 403 `cross_tenant_adapter`; name or version not in this tenant's manifest -> 404 `adapter_not_found` (never reveals other tenants); entry keys outside `adapters/<tenant>/` or a version manifest naming another tenant -> 403 `manifest_tenant_mismatch`; other base model -> 422 `base_model_mismatch`. No job and no URL on any rejection; each is counted in `/metrics`
- The job is queued with a fixed seed (random at enqueue when none is given)
- A claim takes the oldest queued job, sets the lease and `attempt + 1`, and only then signs a GET for the weight (`ADAPTER_URL_TTL_SECONDS`) and a PUT for the output (`OUTPUT_URL_TTL_SECONDS`)
- The worker checks the claim's tenant against the manifest tenant and the weight key, uses its tenant-scoped cache or streams the presigned URL while hashing, loads under a job-scoped adapter name, generates with `torch.Generator("cpu").manual_seed(seed)`, deletes the adapter, asserts none remain, PUTs the PNG, and reports
- Every worker request carries `User-Agent: b2ai-diffusers-lora-weights-hub worker/<version>`; the worker imports no boto3 and reads no `B2_*` key

## Edge Cases
- Checksum or size mismatch -> job fails `checksum_mismatch`, nothing cached
- Cached file changed on disk -> re-hash on hit drops it and refetches
- Leftover adapter after unload -> job fails `adapter_residue`
- Worker loses its lease mid-job -> it stops at the next step and drops the result
- `WORKER_TOKEN` set and missing on a worker -> 401 on every worker route

## UX States
- Covered by Generate and Runs (queued, running with step, succeeded, failed with code)

## Verification
- Test files: `services/api/tests/test_resolver_isolation.py`, `test_job_leases.py`, `test_worker_auth.py`, `test_user_agent.py`; `services/worker/tests/` (`test_cache.py`, `test_fetch.py`, `test_job_loop.py`, `test_no_boto3.py`, `test_device.py`)
- Required cases: every rejection code with no job and no presign; cache miss then hit; checksum mismatch caches nothing; unload after failures; no boto3 in the worker
- Focused verify command: `pnpm test:api && pnpm test:worker`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm selftest` (real B2, GPU, two workers)
- Pass criteria: tests green; self-test isolation, rejection, checksum, cache and swap steps pass

## Related Docs
- [Adapter Registry](adapter-registry.md)
- [Runs and Reports](runs-and-reports.md)
- [SECURITY.md](../SECURITY.md)
