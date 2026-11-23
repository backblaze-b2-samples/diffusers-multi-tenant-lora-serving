# Initial scaffold plan: diffusers-multi-tenant-lora-serving

Starter kit: `backblaze-b2-samples/vibe-coding-starter-kit` at commit
`0e6059e48c38f4512163503826098cfb69793294`. Everything below is the delta against
that tree. The kit is the ceiling: keep what this app uses, trim the rest.

## 1. Purpose

**Problem:** A platform that offers custom LoRA styles to many customers cannot keep every adapter loaded on every GPU, and a worker that loads the wrong customer's adapter leaks one tenant's model into another tenant's images.
**For:** ML platform engineers who serve image generation for many customers from a pool of shared GPU workers.
**What it does:**
- Publishes each tenant's LoRA adapters with a checksummed manifest under that tenant's own prefix
- Resolves each request through the requesting tenant's manifest and rejects cross-tenant adapters
- Fetches only the needed adapter through a short-lived presigned URL into a verified local cache
- Loads, generates with and unloads the adapter per request on one shared SDXL base model
- Finishes a killed worker's job on another worker with the same seed and the same image
**Where B2 fits:** B2 holds every tenant's adapters and manifests, so GPU workers stay stateless, carry no storage credentials and download only the adapter a request needs.

Out of scope: adapter training or fine-tuning, general model or model-hub cache
synchronization, ComfyUI integration, autoscaling, GPU scheduling, a tenant
management UI, and authentication (the tenant in a request is trusted as given;
production puts an authenticating gateway in front that sets it).

## 2. Architecture delta from the starter kit

Two process types, one shared contract:

- **Dispatcher** (`services/api`, FastAPI): the only component with B2
  credentials. Adapter registry (publish, read, edit, delete), manifest
  resolution and tenant checks, presigned URL issuing, the job queue with leases,
  run reports, the bucket explorer and the Library.
- **Workers** (`services/worker`, new Python package, own venv): load the base
  pipeline once, then loop: claim a job over HTTP, fetch the adapter through the
  presigned URL in the claim (or hit the local cache), verify sha256, load,
  generate, unload, upload the image through a presigned PUT, report timings.
  A worker holds no B2 credentials, imports no boto3 and keeps no job state, so
  any worker can take any job and a killed worker loses nothing.

The API layering stays the kit's (`types -> config -> repo -> service -> runtime`,
enforced by `tests/test_structure.py`). All boto3 code lives in
`services/api/app/repo/`. Torch and Diffusers live only in `services/worker/`,
so the API test suite stays fast and torch-free.

| Keep (as is or lightly adapted) | Trim (remove) | Add |
|---|---|---|
| Monorepo layout, pnpm workspaces, `scripts/*` (doctor, setup, dev, gen-api, gen-docs, check-agent-docs, wait-ready, pick-port, python-runtime) | `apps/web/src/app/upload/` and `components/upload/*` | `services/worker/` package: `worker/config.py`, `device.py`, `pipeline.py`, `cache.py`, `fetch.py`, `api_client.py`, `__main__.py`; `requirements.txt`, `requirements.lock`, `pyproject.toml`, `tests/` |
| `app/repo/b2_client.py` (client factory, listing cache, head, delete, presigned GET) | `lib/upload-queue-context.tsx`, `lib/upload-file-types.ts`, `lib/upload-status.ts` and their tests | `app/repo/adapter_store.py`: weight upload (managed multipart via `upload_fileobj`), manifest put/get, streamed sha256 re-read, presigned GET for weights, presigned PUT for outputs, prefix-scoped delete |
| **Bucket explorer** `/files` (`components/files/*`, `lib/file-tree.ts`): full-bucket browse, non-removable | Browser presigned PUT upload: `app/runtime/upload.py`, `app/service/upload.py`, `app/repo/b2_upload.py`, `app/types/upload.py`, `tests/test_upload_*.py` | `app/repo/jobs_db.py`: SQLite job table (stdlib `sqlite3`, WAL), lease and attempt columns, worker registry |
| Health route (extended), metrics, rate limit, error types, structured logging | Metadata extraction (`service/metadata.py`, pypdf, `docs/features/metadata-extraction.md`, its tests); the file detail panel keeps the head-object fields | `app/repo/hf_source.py`: `huggingface_hub` download of a pinned public adapter file for publish |
| Dashboard route `/` (rewritten) and `components/dashboard/*` structure | `infra/vercel/`, `infra/railway/`, root and service `vercel.json`, `railway.json`, `services/api/railway.json`, `services/api/index.py`, `tests/test_vercel_entrypoint.py` (workers need a local GPU; no serverless target) | `app/service/registry.py` (publish, edit, delete, verify), `app/service/resolver.py` (tenant manifest resolution, isolation checks, presign), `app/service/jobs.py` (enqueue, claim, heartbeat, complete, fail, lease reaper), `app/service/reports.py` (`adapters.json` writer), `app/service/library.py` |
| Settings page and `settings-form.tsx` (theme kept; demo fields replaced, see section 4) | `apps/web/e2e/upload.spec.ts` (replaced) | `app/runtime/tenants.py`, `adapters.py`, `generations.py`, `runs.py`, `jobs.py`, `workers.py`, `worker_protocol.py`, `library.py`, `server_settings.py` routers; matching `app/types/*.py` |
| `/design` page, `components/ui/*`, layout, command palette, theme, `api-client.ts`, generated query keys | | Web pages: `/adapters`, `/adapters/[tenantId]/[adapter]`, `/generate`, `/runs`, `/runs/[runId]`, `/library` |
| `docs/` skeleton, generators, `docs/api/openapi.json` (regenerated), `setup_b2_cors.py` (bucket explorer preview of text files still fetches presigned URLs from the browser) | | **Library** asset explorer `/library`: scoped to `APP_PREFIX`, grouped tenant -> adapter -> version, plus outputs gallery and reports |
| CI workflow (adapted: API and web verify; worker offline tests on CPU with a fake pipeline) | | `fixtures/adapters.yaml`, `services/api/scripts/publish_fixtures.py`, `services/worker/scripts/spike_lora_swap.py`, `services/api/live_tests/test_selftest_lora_serving.py`, `scripts/selftest.mjs` |

Tension note: the bucket explorer stays even though the Library covers the app's
own objects. It is the kit's non-removable full-bucket browse and the place to
inspect objects the app did not write.

### Key layout in B2

Every key lives under `APP_PREFIX` (default `lora-serving/`, so the app can share
a bucket). Under it the layout is exactly the requested one:

```
<APP_PREFIX>adapters/<tenant>/manifest.json                         tenant manifest (written last)
<APP_PREFIX>adapters/<tenant>/<adapter>/<version>/adapter.safetensors
<APP_PREFIX>adapters/<tenant>/<adapter>/<version>/manifest.json     version manifest
<APP_PREFIX>outputs/<tenant>/<run-id>/<job-id>.png
<APP_PREFIX>reports/<run-id>/adapters.json
```

Identifiers (`tenant`, `adapter`) match `^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$`;
`version` matches `^v[0-9]+(\.[0-9]+){0,2}$`. Validation rejects anything else,
so no key can escape its prefix.

Version manifest (immutable once written):

```json
{
  "schema_version": 1,
  "tenant_id": "acme",
  "adapter": "pixel-art",
  "version": "v1",
  "weight_key": "lora-serving/adapters/acme/pixel-art/v1/adapter.safetensors",
  "format": "safetensors",
  "sha256": "<hex>",
  "size_bytes": 170543052,
  "base_model": { "id": "stabilityai/stable-diffusion-xl-base-1.0", "revision": null },
  "default_scale": 1.0,
  "trigger_words": ["pixel art"],
  "license": "creativeml-openrail-m",
  "source": { "type": "huggingface", "repo_id": "<org/name>", "revision": "<commit>", "filename": "<file>" },
  "published_at": "2026-11-23T00:00:00Z"
}
```

Tenant manifest: `{schema_version, tenant_id, updated_at, adapters: {<name>:
{display_name, default_scale, trigger_words, current_version, versions: {<v>:
{manifest_key, weight_key, sha256, size_bytes, base_model}}}}}`.

Publish order (the safety rule): validate the file is safetensors (header parse,
no pickle formats accepted), stream it to B2 while hashing, `head_object` size
check, write the version manifest, then rewrite the tenant manifest LAST. A
publish that fails before the last step leaves the tenant manifest unchanged, so
requests never resolve to a half-published version. Publishing an existing
version returns 409. One dispatcher instance owns manifest writes, serialized by
a per-tenant lock (documented assumption; multi-dispatcher writes are out of
scope).

### Request flow

1. `POST /tenants/{tenant_id}/generations` names an adapter as `name`,
   `name@version`, or `owner/name[@version]`, or `null` for the base model.
2. Resolver reads `adapters/<tenant_id>/manifest.json` (cached by ETag, 10 s):
   - `owner` present and different from `tenant_id`: **403 `cross_tenant_adapter`**.
   - name or version not in this tenant's manifest: **404 `adapter_not_found`**
     (the response never reveals whether another tenant has that name).
   - entry's `weight_key` or `manifest_key` not under `adapters/<tenant_id>/`, or
     the version manifest's `tenant_id` differs: **403 `manifest_tenant_mismatch`**
     (defends against a tampered manifest).
   - version manifest `base_model.id` differs from `BASE_MODEL`: **422 `base_model_mismatch`**.
   No job is created and no URL is issued on any rejection; each rejection is
   counted in `/metrics` and logged with tenant and code.
3. The job is queued in SQLite with a fixed seed (random at enqueue when the
   request gives none), so a retry renders the same image.
4. `POST /worker/jobs/claim` (long poll up to 25 s) reaps expired leases, takes
   the oldest queued job, sets `running`, `worker_id`, `attempt += 1`,
   `lease_expires_at = now + JOB_LEASE_SECONDS`, and only then issues fresh
   presigned URLs: GET for the weight (`ADAPTER_URL_TTL_SECONDS`, default 300)
   and PUT for the output key (`OUTPUT_URL_TTL_SECONDS`, default 600). The claim
   carries the version manifest fields the worker needs (tenant, adapter,
   version, sha256, size, base model, scale).
5. The worker:
   - checks the claim's `tenant_id` equals the manifest's `tenant_id` and the
     weight key prefix, else fails the job `manifest_tenant_mismatch`;
   - cache lookup at `ADAPTER_CACHE_DIR/<tenant>/<sha256>.safetensors`; on a hit
     re-hash (configurable, default on) and use it with `bytes_fetched = 0`;
   - on a miss, stream the presigned URL with `httpx` to a temp file while
     hashing, compare to the manifest sha256 and size, and `os.replace` into the
     cache only on a match; a mismatch fails the job `checksum_mismatch` and
     caches nothing; LRU eviction above `ADAPTER_CACHE_MAX_BYTES`;
   - `pipe.load_lora_weights(path, adapter_name=<job-scoped name>)`,
     `pipe.set_adapters([name], adapter_weights=[scale])`, generate with
     `torch.Generator("cpu").manual_seed(seed)`, then `pipe.delete_adapters(name)`
     (or `unload_lora_weights()`, whichever the spike confirms leaves no
     residue) and assert `pipe.get_list_adapters()` is empty;
   - PUT the PNG to the presigned output URL, compute its sha256;
   - heartbeat every `JOB_HEARTBEAT_SECONDS` (default 5) from a thread, with the
     current denoising step from the pipeline callback;
   - `POST /worker/jobs/{id}/complete` with `attempt`, `cache`, `bytes_fetched`,
     `fetch_ms`, `load_ms`, `generate_ms`, `unload_ms`, `output_sha256`,
     `adapters_after_unload`.
6. The dispatcher accepts a completion only from the current `(worker_id,
   attempt)` (**409 `stale_attempt`** otherwise), checks the output with
   `head_object`, marks the job `succeeded`, and when the run's last job reaches
   a terminal state writes `reports/<run-id>/adapters.json`.
7. A worker that dies stops heartbeating; after the lease expires the next claim
   re-queues the job (attempt + 1, up to `JOB_MAX_ATTEMPTS`, default 3, then
   `failed: lease_exhausted`). Same seed, same adapter bytes, same base model,
   same output.

Every worker HTTP request (dispatcher calls and presigned B2 GET and PUT) sends
`User-Agent: b2ai-diffusers-lora-weights-hub worker/<version>`. The User-Agent is
not part of the SigV4 presigned signature, so this is safe. Worker routes
require `Authorization: Bearer $WORKER_TOKEN` when `WORKER_TOKEN` is set
(`doctor` warns when it is unset).

### Report `reports/<run-id>/adapters.json`

```json
{
  "run_id": "...", "created_at": "...", "base_model": "...", "device_summary": ["mps"],
  "jobs": [{
    "job_id": "...", "tenant_id": "acme", "adapter": "pixel-art", "version": "v1",
    "adapter_sha256": "...", "worker_id": "w2", "attempt": 1, "state": "succeeded",
    "cache": "miss", "bytes_fetched": 0, "fetch_ms": 0, "load_ms": 0, "generate_ms": 0,
    "unload_ms": 0, "total_ms": 0, "seed": 42, "steps": 25, "width": 1024, "height": 1024,
    "output_key": "...", "output_sha256": "..."
  }],
  "summary": { "jobs": 0, "succeeded": 0, "failed": 0, "cache_hits": 0,
               "load_ms_p50": 0, "generate_ms_p50": 0, "retried_jobs": 0 }
}
```

### Running locally

No Docker for workers (MPS is not available inside containers). `pnpm dev`
starts API and web as in the kit. `pnpm worker` starts one worker
(`WORKER_ID` defaults to `w-<pid>`); `pnpm dev:workers` starts two (`w1`, `w2`,
separate cache dirs). `pnpm setup` creates both venvs.

## 3. B2 surface

All B2 calls go through the dispatcher's single boto3 client in
`app/repo/b2_client.py`:
`Config(user_agent_extra="b2ai-diffusers-lora-weights-hub", signature_version="s3v4", ...)`,
endpoint derived from `B2_REGION` (`https://s3.<region>.backblazeb2.com`). No
b2-native API call anywhere. Workers reach B2 only through presigned URLs the
dispatcher issues. No bucket configuration (lifecycle, Object Lock) is applied by
the app; `setup_b2_cors.py` stays an explicit, opt-in kit script.

| Operation | Why |
|---|---|
| `upload_fileobj` (managed multipart) / `put_object` | adapter weights; version and tenant manifests; `adapters.json` reports |
| `head_object` / `head_bucket` | weight size check after publish; output check on completion; `/health` probe |
| `get_object` | read manifests; streamed re-read to verify a weight's sha256; read reports; Library and explorer metadata |
| `list_objects_v2` | tenant discovery (`Delimiter="/"` on `adapters/`), Library, bucket explorer, run reports |
| presigned GET | short-lived adapter fetch by workers; image previews and downloads in the UI |
| presigned PUT | credential-free output upload by workers |
| `delete_object` / `delete_objects` | adapter or version delete (scoped to `adapters/<tenant>/<adapter>/[<version>/]`); explorer delete; self-test cleanup of only the keys the run wrote |

### API endpoints (the single list)

Kept from the kit: `GET /metrics`, `GET /files`, `GET /files/stats`,
`GET /files/stats/activity`, `GET /files-by-key/{download,preview,metadata,detail}`,
`DELETE /files-by-key`, and the `/files/{key:path}` equivalents.

Changed: `GET /health` keeps `HealthStatus` and adds `base_model: str`,
`workers_online: int`.

Removed: `POST /upload/presign`, `POST /upload/verify`.

Added:

| Path | Method | Request model | Response model |
|---|---|---|---|
| `/tenants` | GET | none | `list[TenantSummary {tenant_id, adapter_count, version_count, total_bytes, updated_at}]` |
| `/tenants/{tenant_id}/manifest` | GET | none | `TenantManifest` |
| `/tenants/{tenant_id}/adapters` | GET | none | `list[AdapterSummary {tenant_id, adapter, display_name, current_version, version_count, default_scale, license, size_bytes}]` |
| `/tenants/{tenant_id}/adapters` | POST | multipart `AdapterPublishForm {adapter, version, display_name?, default_scale, trigger_words?, license, source: "huggingface"\|"upload", hf_repo_id?, hf_filename?, hf_revision?, file?}` | `AdapterDetail` (201; 409 version exists; 422 not safetensors, license not in allowlist, base model mismatch) |
| `/tenants/{tenant_id}/adapters/{adapter}` | GET | none | `AdapterDetail {..., versions: list[AdapterVersion {version, sha256, size_bytes, base_model, published_at, source, is_current}]}` |
| `/tenants/{tenant_id}/adapters/{adapter}` | PATCH | `AdapterUpdate {display_name?, default_scale?, trigger_words?, current_version?}` | `AdapterDetail` |
| `/tenants/{tenant_id}/adapters/{adapter}` | DELETE | query `confirm` must equal `adapter` | `DeleteAdapterResult {deleted_keys}` |
| `/tenants/{tenant_id}/adapters/{adapter}/versions/{version}` | DELETE | none | `DeleteAdapterResult` (409 when it is the current version and others exist) |
| `/tenants/{tenant_id}/adapters/{adapter}/versions/{version}/verify` | POST | none | `VerifyResult {sha256_expected, sha256_actual, size_expected, size_actual, match}` |
| `/tenants/{tenant_id}/generations` | POST | `GenerationRequest {adapter: str\|null, prompt, negative_prompt?, seed?, steps: 15\|25\|40 = 25, size: 768\|1024 = 1024, scale?, run_id?}` | `Job` (202; 403 `cross_tenant_adapter` / `manifest_tenant_mismatch`; 404 `adapter_not_found`; 422 `base_model_mismatch`) |
| `/runs/compare` | POST | `CompareRequest {tenant_id, adapters: list[str] (1..4), include_base: bool = true, prompt, seed, steps, size}` | `RunDetail` (202; one job per adapter, same seed) |
| `/runs` | GET | none | `list[RunSummary {run_id, created_at, job_count, state, report_key?}]` |
| `/runs/{run_id}` | GET | none | `RunDetail {run_id, created_at, jobs: list[Job], report_key?}` |
| `/runs/{run_id}/report` | GET | none | `AdapterReport` (404 until written) |
| `/jobs` | GET | query `tenant_id?`, `state?` | `list[Job]` |
| `/jobs/{job_id}` | GET | none | `Job {job_id, run_id, tenant_id, adapter, version, adapter_sha256, state, attempt, worker_id, seed, steps, width, height, prompt, timings?, cache?, output_key?, error_code?, created_at, finished_at?}` |
| `/jobs/{job_id}/output` | GET | none | `FileUrlResponse` (presigned GET) |
| `/workers` | GET | none | `list[WorkerStatus {worker_id, device, dtype, base_model, last_seen, current_job_id?, jobs_done, cache_entries, cache_bytes}]` |
| `/worker/register` | POST | `WorkerHello {worker_id, device, dtype, base_model, cache_entries, cache_bytes}` | `WorkerAck {heartbeat_seconds, lease_seconds}` |
| `/worker/jobs/claim` | POST | `ClaimRequest {worker_id, wait_seconds: 0..25}` | `ClaimResponse {job: WorkerJob?}`; `WorkerJob {job_id, attempt, run_id, tenant_id, adapter?: {adapter, version, sha256, size_bytes, base_model, scale, weight_key, url, url_expires_at}, output_key, output_url, prompt, negative_prompt, seed, steps, width, height}` |
| `/worker/jobs/{job_id}/heartbeat` | POST | `Heartbeat {worker_id, attempt, step?, total_steps?}` | `HeartbeatAck {lease_expires_at}` (409 `stale_attempt`) |
| `/worker/jobs/{job_id}/complete` | POST | `JobCompletion {worker_id, attempt, cache: "hit"\|"miss"\|"none", bytes_fetched, sha256_verified, fetch_ms, load_ms, generate_ms, unload_ms, output_sha256, adapters_after_unload: list[str]}` | `Job` (409 `stale_attempt`) |
| `/worker/jobs/{job_id}/fail` | POST | `JobFailure {worker_id, attempt, code, message}` | `Job` |
| `/library` | GET | query `tenant_id?`, `kind?: "adapters"\|"outputs"\|"reports"` | `list[LibraryEntry {key, tenant_id?, kind, adapter?, version?, run_id?, size_bytes, last_modified}]` |
| `/settings/server` | GET | none | `ServerConfig {base_model, app_prefix, adapter_url_ttl_seconds, output_url_ttl_seconds, job_lease_seconds, workers_online, license_allowlist}` |

Error bodies use the kit's error type with a stable `code`.

## 4. Key features

- **Adapter registry**: publish adapters per tenant from a pinned Hugging Face
  file or an uploaded `.safetensors` file, with checksummed version manifests and
  a tenant manifest written last. Doc: `docs/features/adapter-registry.md`.
- **Per-request adapter serving**: tenant-scoped resolution, cross-tenant
  rejection, short-lived presigned URL, verified local cache, load, generate,
  unload. Doc: `docs/features/adapter-serving.md`.
- **Generate and compare**: one request per tenant and adapter, or one prompt and
  seed across several adapters plus the base model, shown side by side. Doc:
  `docs/features/generate.md`.
- **Runs, jobs and worker recovery**: job leases, heartbeats, retry on another
  worker, and the `adapters.json` timing report charted per run. Doc:
  `docs/features/runs-and-reports.md`.
- **Library**: asset explorer scoped to `APP_PREFIX`: tenants, adapters,
  versions, output images and reports. Doc: `docs/features/library.md`.
- **Bucket explorer** (kept), **Dashboard** (rewritten: tenants, adapters, jobs by
  state, workers online, cache hit rate, load vs generate time chart), and
  **Settings**. Docs: `docs/features/file-browser.md`, `dashboard.md`,
  `settings.md`.

### Model and device (no external API)

| Feature | Provider / model | deployment | Est. cost per demo run | Key env var |
|---|---|---|---|---|
| Image generation with per-request LoRA | Diffusers `StableDiffusionXLPipeline`, base `stabilityai/stable-diffusion-xl-base-1.0` (fp16 variant, about 7 GB download from the Hugging Face Hub, not gated) | local | $0 (B2 storage of a few hundred MB of adapters and images) | none (`HF_TOKEN` only for a gated or private adapter source) |
| Adapter fixtures | public SDXL LoRA files from the Hugging Face Hub, pinned by commit | local (downloaded once by the publish script) | $0 | none |

Device rule: CPU default with autodetect CUDA -> Apple MPS -> CPU at worker
start (`TORCH_DEVICE` overrides). dtype fp16 on CUDA and MPS, fp32 on CPU. The
SDXL VAE config's `force_upcast` keeps decode in fp32; if the spike shows black or
NaN images on MPS, switch to the MIT-licensed `madebyollin/sdxl-vae-fp16-fix` VAE
and record it. CPU works but is slow; the README says so. The validation target
is Apple silicon with MPS.

Pre-build spike (`services/worker/scripts/spike_lora_swap.py`, run it
before writing the worker and records the output in the README "Correctness
evidence"):
1. Load SDXL base on MPS; generate one 768 px image, 12 steps, fixed seed.
2. Load adapter A with `load_lora_weights(..., adapter_name=...)`, generate,
   unload; load adapter B, generate, unload; generate with no adapter.
3. Assert the three adapter outputs differ from each other and from base
   (mean absolute pixel difference > 3/255), the post-unload base output equals
   the first base output, and `get_list_adapters()` is empty after unload.
4. Start two worker-sized pipelines at once and record peak memory. If two SDXL
   workers do not fit in unified memory, fall back to
   `stable-diffusion-v1-5/stable-diffusion-v1-5` (CreativeML OpenRAIL-M, commercial
   use permitted) with SD 1.5 LoRA fixtures, and record the switch as a plan
   deviation with the measured numbers.

Fixture selection (`fixtures/adapters.yaml`): two tenants, `acme` with two
adapters and `globex` with one, each a visibly distinct style. Candidates to
check, in order of preference for small size: `nerijs/pixel-art-xl`,
`TheLastBen/Papercut_SDXL`, `ostris/ikea-instructions-lora-sdxl`,
`goofyai/3d_render_style_xl`, `CiroN2022/toy-face`. For each, read the license
and base model from the Hub model card with `huggingface_hub.model_info`, keep
only licenses that permit commercial use (`openrail++`, `creativeml-openrail-m`,
`apache-2.0`, `mit`), require an SDXL 1.0 base and a `.safetensors` file, pin the
commit sha, and record repo, file, commit, license and sha256 in the YAML and in
a README "Model and adapter licenses" table. The README passes on the Open RAIL
use restrictions (link to each license, summary of the use-based restrictions in
Attachment A, and the requirement that users of generated content and of the
models accept them). Weights are never committed; the publish script downloads
them.

No Genblaze: the stack uses no remote AI provider, so the Genblaze SDK is not
needed.

### Primary entity: Adapter (lifecycle in the UI)

| Verb | UI |
|---|---|
| create | `/adapters` "Publish adapter" dialog (new adapter or new version of an existing one), plus "Publish demo adapters" button that runs the fixture set |
| read | `/adapters` table with a tenant filter, and `/adapters/[tenantId]/[adapter]` detail: versions, manifest JSON, sha256, license, source, recent jobs |
| edit | detail page "Edit" sheet: display name, default scale, trigger words, current version |
| delete | detail page danger zone: delete one version (row action) or the whole adapter (`AlertDialog`, type the adapter name); deletes only that adapter's prefix and updates the tenant manifest |
| run | "Generate" panel on the detail page, `/generate` playground, and "Compare adapters" on `/generate`; "Verify checksum" row action re-reads the weight from B2 |

No verb is omitted.

### Form UX conventions

Publish adapter (create) form:

| Field | Control | Default hint (placeholder / FormDescription) |
|---|---|---|
| `tenant_id` | `Select` of existing tenants plus "New tenant" which reveals a text input | placeholder `acme`; "lowercase letters, digits and hyphens" |
| `adapter` | text input | placeholder `pixel-art` |
| `version` | text input | placeholder `v1`; "versions are immutable; publish v2 to change weights" |
| `source` | `RadioGroup`: Hugging Face / Upload file | Hugging Face |
| `hf_repo_id`, `hf_filename`, `hf_revision` | text inputs | placeholders `nerijs/pixel-art-xl`, `pixel-art-xl.safetensors`, "a commit sha keeps the fixture reproducible" |
| `file` | file input, `.safetensors` only | "SDXL LoRA in safetensors format" |
| `license` | `Select` from the server allowlist | none preselected; required |
| `default_scale` | `Select` 0.5 / 0.8 / 1.0 / 1.2 | placeholder hint 1.0 |
| `trigger_words` | text input, comma separated | placeholder `pixel art` |

Edit adapter form (pre-filled): `display_name` text input, `default_scale`
`Select`, `trigger_words` text input, `current_version` `Select` of existing
versions.

Other forms:

| Form | Field | Control | Default |
|---|---|---|---|
| Generate | `tenant_id` | `Select` of tenants | first tenant |
| Generate | `adapter` | `Select` of that tenant's adapters plus "None (base model)" | current adapter on the detail page |
| Generate | `version` | `Select` of that adapter's versions | current version |
| Generate | `prompt` | `Textarea` | placeholder `a lighthouse on a cliff at sunset` |
| Generate | `seed` | number input | placeholder `42`; "same seed and adapter give the same image" |
| Generate | `steps` | `Select` 15 / 25 / 40 | 25 |
| Generate | `size` | `Select` 768 / 1024 | 1024 |
| Generate | `scale` | `Select` 0.5 / 0.8 / 1.0 / 1.2 | adapter default |
| Compare | `adapters` | checkbox list of the tenant's adapters (max 4) | all |
| Compare | `include_base` | `Switch` | on |
| Generate (advanced) | raw adapter reference | text input, collapsed by default | placeholder `globex/toy-face`; shows the 403 rejection to demonstrate isolation |
| Delete adapter | confirmation | text input must equal the adapter name | empty |

Settings: theme (kept), a read-only "Server" card from `GET /settings/server`,
and two demo preferences stored locally (default steps `Select`, default size
`Select`) that prefill the Generate form. `settings-form.tsx` is the exemplar for
both rules.

### Configuration (new env vars)

| Name | Read by | Default | Note |
|---|---|---|---|
| `BASE_MODEL` | API, worker | `stabilityai/stable-diffusion-xl-base-1.0` | must match each manifest's `base_model.id` |
| `BASE_MODEL_REVISION` | worker | unset | optional commit pin |
| `APP_PREFIX` | API | `lora-serving/` | root for `adapters/`, `outputs/`, `reports/` |
| `ADAPTER_URL_TTL_SECONDS` | API | `300` | presigned GET lifetime |
| `OUTPUT_URL_TTL_SECONDS` | API | `600` | presigned PUT lifetime |
| `JOB_LEASE_SECONDS` | API | `30` | self-test lowers it |
| `JOB_HEARTBEAT_SECONDS` | API (sent to workers) | `5` | |
| `JOB_MAX_ATTEMPTS` | API | `3` | |
| `JOBS_DB_PATH` | API | `services/api/.data/jobs.sqlite3` | gitignored |
| `WORKER_TOKEN` | API, worker | unset | secret; when set, `/worker/*` requires it |
| `API_URL` | worker | `http://localhost:8000` | dispatcher address |
| `WORKER_ID` | worker | `w-<pid>` | |
| `ADAPTER_CACHE_DIR` | worker | `services/worker/.cache/adapters` | gitignored |
| `ADAPTER_CACHE_MAX_BYTES` | worker | `4294967296` | LRU limit |
| `ADAPTER_CACHE_VERIFY_ON_HIT` | worker | `true` | re-hash cached file before load |
| `TORCH_DEVICE` | worker | auto | `cuda`, `mps` or `cpu` |
| `HF_TOKEN` | API | unset | secret; only for gated or private adapter sources |

### Tests

API offline tests (`services/api/tests/`, stubbed storage, no network, no torch):

- `test_resolver_isolation.py`: own adapter resolves; `owner/name` with another
  owner -> 403 `cross_tenant_adapter`; another tenant's adapter name unqualified
  -> 404; tampered tenant manifest pointing at another tenant's key -> 403
  `manifest_tenant_mismatch`; base model mismatch -> 422; no job and no presign
  on every rejection.
- `test_publish_manifest.py`: tenant manifest written after weight and version
  manifest (order asserted on the fake store); failure before the last step
  leaves the tenant manifest unchanged; existing version -> 409; pickle and
  `.bin` files rejected; license outside the allowlist -> 422.
- `test_job_leases.py`: claim sets lease and attempt; expired lease re-queues on
  the next claim; completion from a stale attempt -> 409; `JOB_MAX_ATTEMPTS`
  exhausted -> `failed`; presigned URLs are issued at claim time, not enqueue.
- `test_report_writer.py`: `adapters.json` shape, written when the last job of a
  run is terminal, summary math.
- `test_identifiers.py`, `test_adapter_delete_scope.py` (deletes stay inside the
  adapter or version prefix), `test_worker_auth.py`, `test_user_agent.py`
  (client config carries `b2ai-diffusers-lora-weights-hub`), plus the kit's
  retained tests.

Worker offline tests (`services/worker/tests/`, CPU, fake pipeline object with
the same `load_lora_weights` / `set_adapters` / `delete_adapters` /
`get_list_adapters` surface, `httpx.MockTransport`):

- `test_cache.py`: miss then hit, `bytes_fetched == 0` on hit, LRU eviction,
  checksum mismatch caches nothing, tenant-scoped paths.
- `test_fetch.py`: User-Agent header on presigned requests, size and sha256
  verification, partial download cleanup.
- `test_job_loop.py`: unload after every job including failures, heartbeat
  carries attempt, tenant/manifest mismatch fails the job before any fetch.
- `test_no_boto3.py`: the worker package never imports boto3 or reads `B2_*`.
- `test_device.py`: CUDA -> MPS -> CPU selection and `TORCH_DEVICE` override.

Self-test (agent checks, `pnpm selftest` -> `services/api/live_tests/test_selftest_lora_serving.py`,
marker `selftest`; requires real B2 credentials, a local GPU and the base model).
It sets `APP_PREFIX=selftest/<run-id>/lora-serving/`, `JOB_LEASE_SECONDS=15`,
starts the API and two workers (`w1`, `w2`, separate empty cache dirs) as
subprocesses on 768 px, 12 steps, then asserts:

1. Publish: the fixtures publish for `acme` (2 adapters) and `globex` (1); each
   weight re-read from B2 hashes to its manifest sha256.
2. Isolation: one request per tenant submitted together; each job's
   `adapter_sha256` belongs to its own tenant's manifest; both workers report
   `adapters_after_unload == []`.
3. Cross-tenant rejection: `acme` asking for `globex/<adapter>` -> 403; `acme`
   asking for globex's adapter name unqualified -> 404; a tampered `acme`
   manifest entry pointing at a globex key -> 403; no job created for any of them.
4. Checksums: every completion has `sha256_verified == true`; a deliberately
   corrupted version (manifest sha256 does not match the object) fails with
   `checksum_mismatch` and leaves no cache entry.
5. Cache hits: a second request for the same adapter on the same worker reports
   `cache == "hit"` and `bytes_fetched == 0`.
6. Swaps: same prompt and seed with adapter A, adapter B and no adapter on one
   worker, then A again: A, B and base differ pairwise (mean absolute pixel
   difference > 3/255) and the second A equals the first.
7. Worker kill: a reference image R is rendered for request X. With `w2`
   stopped, X is submitted again, `w1` claims it, the test waits for a heartbeat
   with `step >= 2`, sends SIGKILL to `w1`, restarts `w2`; after the lease
   expires `w2` completes attempt 2 and its output equals R (sha256 equal, or
   max per-pixel difference <= 1/255 recorded as such). A late completion for
   attempt 1 is rejected with 409.
8. Report: `reports/<run-id>/adapters.json` exists in B2 with `load_ms` and
   `generate_ms` for every succeeded job, and `retried_jobs >= 1`.

It writes `.local/selftest/<run-id>/evidence.json` plus the output PNGs, then
deletes only the keys it recorded as written and asserts the run prefix is
empty. The README "Correctness evidence" section records the run's numbers.
Web: vitest for new libs (adapter reference parsing, report chart shaping,
state badge mapping); Playwright `e2e/adapters.spec.ts` replaces the upload spec
(list, publish form validation, generate form, cross-tenant error message) with
the API mocked.

Validation (human checks): publish the demo adapters for the two tenants, send one
generation request per tenant, and visually inspect that each image carries its
own tenant's adapter style, using `/runs/[runId]` side-by-side outputs.

## 5. Doc transforms

- Rewrite: `README.md` (generator regions plus hand-written sections: what it
  shows, quickstart with two workers, base model size and download, how
  resolution and isolation work, key layout, the publish safety rule, reading
  `adapters.json`, "Model and adapter licenses" with the Open RAIL use
  restrictions, "Correctness evidence", and "Related samples" linking
  `hf-cache-sync` (model-hub cache sync), `comfyui-cloud-storage` (ComfyUI model
  folders) and `flux-b2-generation-output-lifecycle` (generated outputs), each
  linked only if published under `backblaze-b2-samples`), `ARCHITECTURE.md`,
  `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `PRODUCT.md`, `docs/app-workflows.md`,
  `docs/features/dashboard.md`, `docs/features/file-browser.md`,
  `docs/features/settings.md`, `docs/SECURITY.md` (workers hold no credentials,
  presigned TTLs, tenant checks, safetensors only, worker token, prefix-scoped
  deletes), `docs/RELIABILITY.md` (manifest-last, leases, retry with same seed,
  stale-attempt rejection), `docs/verification.md` (self-test command and what it
  asserts), `docs/dev-workflows.md` (two venvs, starting workers, lockfiles).
- Delete: `docs/features/file-upload.md`, `docs/features/metadata-extraction.md`,
  `infra/vercel/README.md`, `infra/railway/README.md`.
- New stubs from `docs/features/_template.md`: `adapter-registry.md`,
  `adapter-serving.md`, `generate.md`, `runs-and-reports.md`, `library.md`.

### Declared identity (`docs/exec-plans/sample.json`)

This file is written first, before running `pnpm gen:docs`, exactly as
below:

```json
{
  "$schema": "../../scripts/gen/sample.schema.json",
  "schema_version": 1,
  "name": "Diffusers Multi-Tenant LoRA Serving",
  "slug": "diffusers-multi-tenant-lora-serving",
  "package_scope": "@diffusers-multi-tenant-lora-serving",
  "purpose": "Serve many tenants' LoRA adapters from Backblaze B2 on one shared Diffusers base model, with stateless GPU workers that resolve each request through the tenant's manifest, fetch only that adapter through a short-lived presigned URL and a verified cache, and load and unload it per request.",
  "tagline": "One base model, every tenant's LoRA adapters in B2, loaded per request.",
  "primary_entity": { "schema": "AdapterDetail", "singular": "adapter", "plural": "adapters" },
  "features": [
    { "title": "Adapter Registry", "route": "/adapters", "doc": "docs/features/adapter-registry.md", "summary": "publish, version, edit, verify and delete tenant LoRA adapters", "workflow_heading": "Publish and Manage Adapters" },
    { "title": "Adapter Serving", "route": null, "doc": "docs/features/adapter-serving.md", "summary": "tenant-scoped resolution, presigned fetch, verified cache, load and unload per request" },
    { "title": "Generate and Compare", "route": "/generate", "doc": "docs/features/generate.md", "summary": "generate per tenant and adapter, compare adapters on one seed", "workflow_heading": "Generate Images" },
    { "title": "Runs and Reports", "route": "/runs", "doc": "docs/features/runs-and-reports.md", "summary": "jobs, worker recovery and adapters.json timing reports", "workflow_heading": "Review Runs" },
    { "title": "Library", "route": "/library", "doc": "docs/features/library.md", "summary": "adapters, outputs and reports under the app prefix", "workflow_heading": "Browse the Library" },
    { "title": "Bucket Explorer", "route": "/files", "doc": "docs/features/file-browser.md", "summary": "browse, preview, download and delete any object in the bucket", "workflow_heading": "Browse the Bucket" },
    { "title": "Dashboard", "route": "/", "doc": "docs/features/dashboard.md", "summary": "tenants, adapters, workers, cache hits and timings", "workflow_heading": "View Dashboard" },
    { "title": "Settings", "route": "/settings", "doc": "docs/features/settings.md", "summary": "theme, generate defaults and read-only server config", "workflow_heading": "Change Preferences" }
  ],
  "b2_surface": [
    { "operation": "upload_fileobj / put_object", "why": "store adapter weights, manifests and run reports" },
    { "operation": "head_object", "why": "check weight and output sizes, and the /health probe" },
    { "operation": "get_object", "why": "read manifests and reports, and re-read weights to verify sha256" },
    { "operation": "list_objects_v2", "why": "discover tenants and back the Library and bucket explorer" },
    { "operation": "presigned GET", "why": "workers fetch one adapter without credentials; UI image previews" },
    { "operation": "presigned PUT", "why": "workers upload generated images without credentials" },
    { "operation": "delete_object / delete_objects", "why": "delete an adapter or version inside its own prefix, and explorer deletes" }
  ],
  "b2_key_prefix": "lora-serving/",
  "stack": {
    "web": "Next.js 16, React 19, Tailwind v4, shadcn/ui, TanStack Query, Recharts",
    "api": "FastAPI, Python 3.12+, boto3, Pydantic v2, huggingface_hub, SQLite; workers: PyTorch, Diffusers, PEFT, httpx",
    "storage": "Backblaze B2 (S3-compatible API)",
    "package_manager": "pnpm workspaces"
  },
  "deployment_targets": [],
  "env_vars": [
    { "name": "B2_APPLICATION_KEY_ID", "required": true, "secret": true, "note": "B2 application key ID (**keyID** in the B2 console); dispatcher only" },
    { "name": "B2_APPLICATION_KEY", "required": true, "secret": true, "note": "B2 application key (**applicationKey**), shown once at creation; dispatcher only" },
    { "name": "B2_BUCKET_NAME", "required": true, "secret": false, "note": "bucket unique name (**Bucket Unique Name** in the B2 console)" },
    { "name": "B2_REGION", "required": true, "secret": false, "note": "the region inside the bucket's **Endpoint** (`s3.<region>.backblazeb2.com`); the S3 endpoint is derived from it" },
    { "name": "B2_PUBLIC_URL_BASE", "required": false, "secret": false, "note": "public object base URL, when the bucket is public" },
    { "name": "NEXT_PUBLIC_API_URL", "required": false, "secret": false, "note": "separate-origin API only; Next.js inlines it at build time" },
    { "name": "BASE_MODEL", "required": false, "secret": false, "note": "shared base model id; default stabilityai/stable-diffusion-xl-base-1.0" },
    { "name": "BASE_MODEL_REVISION", "required": false, "secret": false, "note": "optional commit pin for the base model (worker)" },
    { "name": "APP_PREFIX", "required": false, "secret": false, "note": "key prefix for adapters, outputs and reports; default lora-serving/" },
    { "name": "ADAPTER_URL_TTL_SECONDS", "required": false, "secret": false, "note": "presigned adapter URL lifetime; default 300" },
    { "name": "OUTPUT_URL_TTL_SECONDS", "required": false, "secret": false, "note": "presigned output upload URL lifetime; default 600" },
    { "name": "JOB_LEASE_SECONDS", "required": false, "secret": false, "note": "job lease before a silent worker's job is retried; default 30" },
    { "name": "JOB_HEARTBEAT_SECONDS", "required": false, "secret": false, "note": "worker heartbeat interval; default 5" },
    { "name": "JOB_MAX_ATTEMPTS", "required": false, "secret": false, "note": "attempts before a job fails; default 3" },
    { "name": "JOBS_DB_PATH", "required": false, "secret": false, "note": "SQLite job queue file; default services/api/.data/jobs.sqlite3" },
    { "name": "WORKER_TOKEN", "required": false, "secret": true, "note": "shared token that worker routes require when set" },
    { "name": "API_URL", "required": false, "secret": false, "note": "dispatcher URL the worker calls; default http://localhost:8000" },
    { "name": "WORKER_ID", "required": false, "secret": false, "note": "worker name in jobs and reports; default w-<pid>" },
    { "name": "ADAPTER_CACHE_DIR", "required": false, "secret": false, "note": "worker adapter cache; default services/worker/.cache/adapters" },
    { "name": "ADAPTER_CACHE_MAX_BYTES", "required": false, "secret": false, "note": "worker cache LRU limit; default 4 GiB" },
    { "name": "ADAPTER_CACHE_VERIFY_ON_HIT", "required": false, "secret": false, "note": "re-hash a cached adapter before load; default true" },
    { "name": "TORCH_DEVICE", "required": false, "secret": false, "note": "cuda, mps or cpu; default autodetect CUDA, then MPS, then CPU" },
    { "name": "HF_TOKEN", "required": false, "secret": true, "note": "only for gated or private Hugging Face adapter sources" }
  ],
  "attribution_token": "b2ai-diffusers-lora-weights-hub",
  "repo": { "org": "backblaze-b2-samples", "name": "diffusers-multi-tenant-lora-serving" },
  "screenshots": []
}
```

If `pnpm gen:check` rejects a field shape (for example the empty
`deployment_targets`), adapt the generator input minimally and record the
deviation; do not change `name`, `slug`, `attribution_token` or `repo`.

## 6. Rename table

| From | To |
|---|---|
| `vibe-coding-starter-kit` (package names, `app_slug`, comments, file-tree and query namespaces, `next.config.ts`, SECURITY and dev-workflows docs, CORS rule id) | `diffusers-multi-tenant-lora-serving` |
| `@vibe-coding-starter-kit/web`, `@vibe-coding-starter-kit/shared`, every `pnpm --filter` | `@diffusers-multi-tenant-lora-serving/web`, `@diffusers-multi-tenant-lora-serving/shared` |
| `Vibe Coding Starter Kit` (`APP_NAME`, `API_TITLE`, `API_DESCRIPTION`, branding check, openapi title) | `Diffusers Multi-Tenant LoRA Serving` |
| `vibe_coding_starter_kit` (any snake case) | `diffusers_multi_tenant_lora_serving` |
| `user_agent_extra="b2ai-oss-start"` | `user_agent_extra="b2ai-diffusers-lora-weights-hub"` |
| the starter-kit `utm_content` value (README, sidebar, doctor) | `utm_content=b2ai-diffusers-lora-weights-hub` |
| `localStorage` namespace (derived from the slug) | `diffusers-multi-tenant-lora-serving` |
| CI workflow name | `diffusers-multi-tenant-lora-serving CI` |
| `.env.example` | keeps the four required `B2_*` names, `B2_PUBLIC_URL_BASE` commented, adds the optional vars from section 4 commented with their defaults |
