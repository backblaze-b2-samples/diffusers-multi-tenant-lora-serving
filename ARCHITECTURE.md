<!-- last_verified: 2026-11-23 -->
# Architecture

## Components

<!-- gen:begin arch-components -->
Serve many tenants' LoRA adapters from Backblaze B2 on one shared Diffusers base model, with stateless GPU workers that resolve each request through the tenant's manifest, fetch only that adapter through a short-lived presigned URL and a verified cache, and load and unload it per request.

- **apps/web/**: Next.js 16, React 19, Tailwind v4, shadcn/ui, TanStack Query, Recharts
  - Adapter Registry (`/adapters`): publish, version, edit, verify and delete tenant LoRA adapters
  - Generate and Compare (`/generate`): generate per tenant and adapter, compare adapters on one seed
  - Runs and Reports (`/runs`): jobs, worker recovery and adapters.json timing reports
  - Library (`/library`): adapters, outputs and reports under the app prefix
  - Bucket Explorer (`/files`): browse, preview, download and delete any object in the bucket
  - Dashboard (`/`): tenants, adapters, workers, cache hits and timings
  - Settings (`/settings`): theme, generate defaults and read-only server config
- **services/api/**: FastAPI, Python 3.12+, boto3, Pydantic v2, huggingface_hub, SQLite; workers: PyTorch, Diffusers, PEFT, httpx
  - REST API for every operation the frontend consumes, exported to `docs/api/openapi.json`
  - Backblaze B2 (S3-compatible API) access isolated in the `repo/` layer
  - Adapter Serving: tenant-scoped resolution, presigned fetch, verified cache, load and unload per request
  - Structured JSON logging with request tracing, plus `/health` and Prometheus `/metrics`
- **packages/shared/**: TypeScript types generated from the API contract by `pnpm gen:api`, consumed by `apps/web/` as a workspace dependency (pnpm workspaces)
<!-- gen:end arch-components -->

## Backend Layering

Two process types share one contract:

- **Dispatcher** (`services/api`, FastAPI): the only process with B2
  credentials. Adapter registry, tenant-scoped resolution, presigned URL
  issuing, the SQLite job queue with leases, run reports, the Library and the
  bucket explorer.
- **Workers** (`services/worker`, own venv): load the base pipeline once, then
  claim a job over HTTP, fetch one adapter through the presigned URL in the
  claim (or the local cache), verify its sha256, load, generate, unload, upload
  the image through a presigned PUT and report timings. A worker holds no B2
  credentials, imports no boto3 and keeps no job state.

The dispatcher follows a strict layered architecture:

```
types/     Pydantic models and identifier rules, no I/O
  |
config/    Settings (pydantic-settings): depends only on types
  |
repo/      Data access: boto3 B2 client, adapter store, SQLite job DB, Hugging Face source
  |
service/   Registry, resolver, jobs, reports, library, calls repo, returns types
  |
runtime/   FastAPI routes, calls service, never repo directly
```

Torch and Diffusers live only in `services/worker/`, so the dispatcher's test
suite stays fast and torch-free.

### Layering Rules

1. Dependencies flow downward only: `types` -> `config` -> `repo` -> `service` -> `runtime`
2. No backward imports (e.g., service must not import from runtime)
3. `boto3` only allowed in `repo/` layer
4. All boundary data uses Pydantic models (no raw dicts across layers)
5. Authored Python files under `services/api/app/` stay under 300 lines

### Directory Structure

<!-- gen:begin arch-directory -->
```
services/api/
  main.py                  App entrypoint, middleware, router registration
  app/
    types/                 Pydantic models, and the response-model base
    config/                Settings loaded from environment
    repo/                  B2 S3 client (data access layer)
    service/               Business logic
    runtime/               FastAPI route handlers
  scripts/                 Operational scripts (OpenAPI export, bucket CORS)
  tests/                   pytest tests (structural + integration)
```
<!-- gen:end arch-directory -->

## Boundary Invariants

- **No external SDK leakage**: `boto3` is only imported in `app/repo/`, and `huggingface_hub` only in `app/repo/hf_source.py` (both asserted by `tests/test_structure.py`). The dispatcher never imports torch or Diffusers; the worker never imports boto3 or reads a `B2_*` key (`services/worker/tests/test_no_boto3.py`).
- **Tenant isolation**: a request resolves only through `adapters/<tenant>/manifest.json`; every manifest key must stay under `adapters/<tenant>/`. Rejections happen before a job row or a presigned URL exists.
- **Manifest last**: a version becomes resolvable only when the tenant manifest is rewritten, after the weight and the version manifest are in B2. One dispatcher owns manifest writes, serialized by a per-tenant lock.
- **No raw dicts at boundaries**: data crossing layers uses typed Pydantic models; `repo/jobs_db.py` returns rows that `service/reports.py` turns into `Job` models.
- **No cross-layer mutable state**: intra-layer caches (listing cache, manifest cache, connectivity cache, rate-limit and metrics state) are module-local and lock-guarded. The SQLite connection is shared under one lock; WAL mode.
- **Validated inputs**: identifiers match `^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$`, versions `v1[.2[.3]]`, run ids `[a-z0-9-]`; file keys reject traversal patterns.

## Deployment

- **Local**: `pnpm dev` runs the dispatcher (`localhost:8000`) and the web app
  (`localhost:3000`); `pnpm dev:workers` starts two workers (`w1`, `w2`, separate
  adapter caches). Workers run natively, not in Docker: MPS is not available
  inside containers.
- **GPU hosts**: one dispatcher, any number of workers pointed at it with
  `API_URL` and a shared `WORKER_TOKEN`. There is no serverless target, so the
  sample ships no Vercel or Railway runbook (`deployment_targets` is empty).

External provisioning and deployment remain explicit user-approved actions.

## Data Stores

<!-- gen:begin arch-data-stores -->
- **Backblaze B2 (S3-compatible API)**: the only data store; there is no application database
  - Every object this app writes lives under the `lora-serving/` key prefix of one bucket
  - Listing, per-key metadata and presigned URLs all come from the S3 surface below
  - The primary entity is `AdapterDetail`; one adapter is one object
<!-- gen:end arch-data-stores -->

## External Services

<!-- gen:begin arch-external-services -->
- **Backblaze B2 (S3-compatible API)**: reached only through `services/api/app/repo/`, using:
  - `upload_fileobj / put_object`: store adapter weights, manifests and run reports
  - `head_object`: check weight and output sizes, and the /health probe
  - `get_object`: read manifests and reports, and re-read weights to verify sha256
  - `list_objects_v2`: discover tenants and back the Library and bucket explorer
  - `presigned GET`: workers fetch one adapter without credentials; UI image previews
  - `presigned PUT`: workers upload generated images without credentials
  - `delete_object / delete_objects`: delete an adapter or version inside its own prefix, and explorer deletes
<!-- gen:end arch-external-services -->

## Trust Boundaries

See [docs/SECURITY.md](docs/SECURITY.md) for full security documentation.

- **Browser -> dispatcher**: CORS-restricted; `CORSMiddleware` is outermost so error responses keep their headers. No authentication: the tenant in the path is trusted as given; production puts an authenticating gateway in front.
- **Worker -> dispatcher**: `/worker/*` routes; `Authorization: Bearer $WORKER_TOKEN` when the token is set. Exempt from the per-IP rate limit.
- **Dispatcher -> B2**: application key, SigV4, `user_agent_extra=b2ai-diffusers-lora-weights-hub`.
- **Worker -> B2**: only presigned URLs: a GET for one adapter (`ADAPTER_URL_TTL_SECONDS`, default 300) and a PUT for one output key bound to `image/png` (`OUTPUT_URL_TTL_SECONDS`, default 600), issued at claim time.
- **Browser -> B2**: presigned GETs for image previews and explorer downloads.

## Data Flows

- **Publish**: `POST /tenants/{t}/adapters` -> validate -> stream weight to B2 while hashing -> HEAD size check -> version manifest -> tenant manifest (last)
- **Generate**: `POST /tenants/{t}/generations` -> resolver reads the tenant manifest (10 s cache, ETag revalidation) and the version manifest -> job row (fixed seed) in SQLite
- **Claim**: worker `POST /worker/jobs/claim` (long poll up to 25 s) -> reap expired leases -> oldest queued job -> running, `attempt + 1`, lease -> presign weight GET and output PUT
- **Run**: worker cache lookup or presigned download with sha256 check -> `load_lora_weights` -> generate -> `delete_adapters` -> presigned PUT -> `POST .../complete` -> dispatcher HEADs the output -> `succeeded` -> when the run is idle, `reports/<run-id>/adapters.json`
- **Recovery**: no heartbeat until the lease ends -> next claim re-queues (same seed) -> another worker -> late completion from the old attempt 409

## Observability

- Structured JSON logging (dispatcher and workers), with tenant and code on every rejection
- `/metrics` (Prometheus format): request count and latency per route, `adapter_rejections_total{code=...}`
- `/health`: B2 connectivity, base model, workers online
- `/workers`: device, dtype, last seen, current job, cache entries and bytes per worker
- `reports/<run-id>/adapters.json` in B2: per-job fetch, load, generate and unload times

## API Contract

<!-- gen:begin arch-api-contract -->
- Checked-in OpenAPI artifact: `docs/api/openapi.json`
- Export / check: `pnpm contract:export` / `pnpm contract:check`
- Generate the client seam from it: `pnpm gen:api` (drift gate: `pnpm gen:check`)
- FastAPI freshness test: `services/api/tests/test_openapi_contract.py`
- Frontend route drift test: `apps/web/src/lib/api-contract.test.ts`

The FastAPI routers and Pydantic models are the single source of truth. The
frontend's `API_CLIENT_ROUTES` registry, the `qk` query-key factory and the
shared TypeScript types are **generated** from the exported artifact by
`pnpm gen:api`, so the client cannot drift from the backend, there is no
hand-written copy left to disagree. The two contract tests are kept as a
belt-and-braces check that the generated files and the committed artifact are
still in step.

| Route | Returns | Generated client route |
| --- | --- | --- |
| `DELETE /files-by-key` | `DeleteFileResponse` | `fileByKeyDelete` |
| `DELETE /files/{key}` | `DeleteFileResponse` | `legacyFileDelete` |
| `DELETE /tenants/{tenant_id}/adapters/{adapter}` | `DeleteAdapterResult` | `deleteAdapter` |
| `DELETE /tenants/{tenant_id}/adapters/{adapter}/versions/{version}` | `DeleteAdapterResult` | `deleteAdapterVersion` |
| `GET /files` | `FileMetadata[]` | `files` |
| `GET /files-by-key/detail` | `FileMetadataDetail` | `fileByKeyDetail` |
| `GET /files-by-key/download` | `FileUrlResponse` | `fileByKeyDownload` |
| `GET /files-by-key/metadata` | `FileMetadata` | `fileByKeyMetadata` |
| `GET /files-by-key/preview` | `FileUrlResponse` | `fileByKeyPreview` |
| `GET /files/{key}` | `FileMetadata` | `legacyFileMetadata` |
| `GET /files/{key}/download` | `FileUrlResponse` | `legacyFileDownload` |
| `GET /files/{key}/preview` | `FileUrlResponse` | `legacyFilePreview` |
| `GET /files/stats` | `UploadStats` | `fileStats` |
| `GET /files/stats/activity` | `DailyUploadCount[]` | `uploadActivity` |
| `GET /fixtures/publish` | `FixturePublishStatus` | `fixturePublishStatus` |
| `GET /health` | `HealthStatus` | `health` |
| `GET /jobs` | `Job[]` | `jobs` |
| `GET /jobs/{job_id}` | `Job` | `job` |
| `GET /jobs/{job_id}/output` | `FileUrlResponse` | `jobOutput` |
| `GET /library` | `LibraryEntry[]` | `library` |
| `GET /metrics` | - | _server-only_ |
| `GET /runs` | `RunSummary[]` | `runs` |
| `GET /runs/{run_id}` | `RunDetail` | `run` |
| `GET /runs/{run_id}/report` | `AdapterReport` | `runReport` |
| `GET /settings/server` | `ServerConfig` | `serverConfig` |
| `GET /tenants` | `TenantSummary[]` | `tenants` |
| `GET /tenants/{tenant_id}/adapters` | `AdapterSummary[]` | `adapters` |
| `GET /tenants/{tenant_id}/adapters/{adapter}` | `AdapterDetail` | `adapter` |
| `GET /tenants/{tenant_id}/manifest` | `TenantManifest` | `tenantManifest` |
| `GET /workers` | `WorkerStatus[]` | `workers` |
| `PATCH /tenants/{tenant_id}/adapters/{adapter}` | `AdapterDetail` | `updateAdapter` |
| `POST /fixtures/publish` | - | `publishFixtures` |
| `POST /runs/compare` | - | `compareAdapters` |
| `POST /tenants/{tenant_id}/adapters` | - | `publishAdapter` |
| `POST /tenants/{tenant_id}/adapters/{adapter}/versions/{version}/verify` | `VerifyResult` | `verifyAdapterVersion` |
| `POST /tenants/{tenant_id}/generations` | - | `createGeneration` |
| `POST /worker/jobs/{job_id}/complete` | `Job` | _server-only_ |
| `POST /worker/jobs/{job_id}/fail` | `Job` | _server-only_ |
| `POST /worker/jobs/{job_id}/heartbeat` | `HeartbeatAck` | _server-only_ |
| `POST /worker/jobs/claim` | `ClaimResponse` | _server-only_ |
| `POST /worker/register` | `WorkerAck` | _server-only_ |
<!-- gen:end arch-api-contract -->

## Canonical Files

<!-- gen:begin arch-canonical-files -->
Hand-written, this is the file to edit:

- Layered API handler: `services/api/app/runtime/`
- Service orchestration: `services/api/app/service/`
- B2 data access (repo layer): `services/api/app/repo/b2_client.py`
- Pydantic models: `services/api/app/types/` (`base.py` carries the response-model config)
- Config (pydantic-settings): `services/api/app/config/settings.py`
- Structural tests: `services/api/tests/test_structure.py`
- OpenAPI exporter: `services/api/scripts/export_openapi.py`
- Frontend API client, error policy, transport, fallback: `apps/web/src/lib/api-client.ts`
- Frontend data layer, caching, invalidation, polling: `apps/web/src/lib/queries.ts`
- Shared type barrel: `packages/shared/src/types.ts`
- Generator policy: `scripts/gen/api-gen.config.json`
- Sample manifest behind the generated docs: `docs/exec-plans/sample.json`

Generated, **never hand-edit**; change the source and re-run the command:

- `docs/api/openapi.json`: `pnpm contract:export` (source: the routers and models)
- `packages/shared/src/generated/api-types.ts`: `pnpm gen:api`
- `apps/web/src/lib/generated/api-routes.ts`: `pnpm gen:api`
- `apps/web/src/lib/generated/query-keys.ts`: `pnpm gen:api`
- The marker-delimited regions of this file, `AGENTS.md`, `README.md` and the 0 `infra/` runbooks, `pnpm gen:docs`
<!-- gen:end arch-canonical-files -->

## Core Features

<!-- gen:begin arch-core-features -->
- [Adapter Registry](docs/features/adapter-registry.md): publish, version, edit, verify and delete tenant LoRA adapters
- [Adapter Serving](docs/features/adapter-serving.md): tenant-scoped resolution, presigned fetch, verified cache, load and unload per request
- [Generate and Compare](docs/features/generate.md): generate per tenant and adapter, compare adapters on one seed
- [Runs and Reports](docs/features/runs-and-reports.md): jobs, worker recovery and adapters.json timing reports
- [Library](docs/features/library.md): adapters, outputs and reports under the app prefix
- [Bucket Explorer](docs/features/file-browser.md): browse, preview, download and delete any object in the bucket
- [Dashboard](docs/features/dashboard.md): tenants, adapters, workers, cache hits and timings
- [Settings](docs/features/settings.md): theme, generate defaults and read-only server config
<!-- gen:end arch-core-features -->

## References

<!-- gen:begin arch-references -->
- [docs/SECURITY.md](docs/SECURITY.md): security principles and implementation
- [docs/RELIABILITY.md](docs/RELIABILITY.md): reliability expectations
- [AGENTS.md](AGENTS.md): architectural invariants and agent instructions
<!-- gen:end arch-references -->
