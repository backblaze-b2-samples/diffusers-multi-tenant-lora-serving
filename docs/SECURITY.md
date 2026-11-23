<!-- last_verified: 2026-11-23 -->
# Security

Security principles and implementation for diffusers-multi-tenant-lora-serving.

## Trust Boundaries

- **Browser -> dispatcher**: CORS-restricted to configured origins, scoped to `GET/POST/PATCH/DELETE/OPTIONS`. `allow_credentials` is `False`.
- **Worker -> dispatcher**: the `/worker/*` routes. When `WORKER_TOKEN` is set, every one of them requires `Authorization: Bearer <token>` (compared in constant time); `pnpm run doctor` warns while it is unset.
- **Dispatcher -> B2**: the only holder of `B2_APPLICATION_KEY_ID` and `B2_APPLICATION_KEY`; SigV4; every call carries `user_agent_extra=b2ai-diffusers-lora-weights-hub`.
- **Worker -> B2**: presigned URLs only, issued at claim time, never at enqueue:
  - a GET for exactly one adapter weight, valid `ADAPTER_URL_TTL_SECONDS` (default 300 s);
  - a PUT for exactly one output key, bound to `Content-Type: image/png`, valid `OUTPUT_URL_TTL_SECONDS` (default 600 s).
- **Browser -> B2**: presigned GETs for image previews and bucket-explorer downloads.

## Workers Hold No Credentials

A worker runs model code on a GPU host. It never receives a bucket key: it reads
only its own settings (`API_URL`, `WORKER_ID`, `WORKER_TOKEN`, base model, cache
and device settings), never imports boto3 and never reads a `B2_*` variable,
even from the shared env file. `services/worker/tests/test_no_boto3.py` enforces
all three. A leaked presigned URL exposes one adapter for at most five minutes.

## Tenant Isolation

- A generation request resolves only through `adapters/<tenant>/manifest.json`
  (`services/api/app/service/resolver.py`).
- `owner/name` naming another tenant -> 403 `cross_tenant_adapter`.
- A name or version missing from this tenant's manifest -> 404 `adapter_not_found`;
  the response never says whether another tenant has that name.
- A manifest entry whose weight or manifest key leaves `adapters/<tenant>/`, or a
  version manifest whose `tenant_id`, weight key or sha256 disagrees -> 403
  `manifest_tenant_mismatch` (defends against a tampered manifest).
- No job row and no presigned URL exist for any rejected request; each rejection
  is logged with tenant and code and counted in `adapter_rejections_total`.
- Workers re-check that the claim's tenant owns the weight key before fetching,
  and cache files at `<cache>/<tenant>/<sha256>.safetensors`, so one tenant's
  request is never served a file another tenant's request downloaded.
- After every job the worker deletes the job-scoped adapter and reports
  `adapters_after_unload`; anything left loaded fails the job (`adapter_residue`).

## Authentication

There is no user authentication by design: the tenant in a request path is
trusted as given. This is a sample of the storage and serving pattern, not of
identity. In production, put an authenticating gateway in front of the
dispatcher that derives the tenant from the caller's identity and sets it, and
do not expose the dispatcher directly. The bucket explorer (`/files`) is
bucket-wide and equally unauthenticated.

## Adapter Validation

- Only safetensors: the file must be named `.safetensors` and its header must
  parse and account for the whole file. Pickle formats (`.bin`, `.pt`, `.ckpt`)
  can execute code on load and are refused.
- Licenses must be in the dispatcher's allowlist (`creativeml-openrail-m`,
  `openrail++`, `apache-2.0`, `mit`).
- Identifiers must match `^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$` and versions
  `v1[.2[.3]]`, so no key can escape its prefix.
- Every weight is stored with its sha256 and size; workers verify both before a
  file enters their cache, and "Verify checksum" re-reads the stored object.

## Prefix-Scoped Deletes

Deleting an adapter or version first removes it from the tenant manifest, then
lists exactly the objects under `adapters/<tenant>/<adapter>/[<version>/]`
(trailing slash, so `pixel-art` never matches `pixel-art-xl`) and refuses to
delete any key outside that prefix. The self-test deletes only the keys it
recorded writing and then asserts its run prefix is empty.

## Rate Limiting

- Per-IP fixed-window limiter (`app/runtime/ratelimit.py`), configurable via `RATE_LIMIT_PER_MINUTE` and `RATE_LIMIT_WRITE_PER_MINUTE`.
- `/worker/*` is exempt: it is machine traffic from known workers (long polls and heartbeats every few seconds, often from one IP) and is gated by `WORKER_TOKEN` instead.
- In-process, per replica.

## File Key Validation

- Empty keys and traversal patterns (`../`, `%2e%2e`, backslashes, null bytes) are rejected on the bucket explorer's by-key routes.
- Optional `ALLOWED_KEY_PREFIX` confines explorer reads and deletes.

## Response Hardening

- `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer` on every response
- `ENABLE_DOCS=false` hides `/docs`, `/redoc` and `/openapi.json`

## CI Permissions

- `.github/workflows/ci.yml` sets `permissions: contents: read`; widen per job only.

## Secrets Management

- Secrets come from environment variables or the repo-root `.env` (never committed). `.env.example` documents every variable without values.
- Secret variables: `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`, `WORKER_TOKEN`, `HF_TOKEN`.

## Dependency and Secret Detection

- [`.github/dependabot.yml`](../.github/dependabot.yml) opens weekly update PRs; review each lockfile change before merging.
- [`.pre-commit-config.yaml`](../.pre-commit-config.yaml) runs a pinned `detect-secrets` hook on staged changes.
- GitHub secret scanning and push protection are provider settings an administrator enables.

## Model Licenses

The base model and two demo adapters are Open RAIL licensed, with use-based
restrictions that users of the models and of generated content must accept; see
[README — Model and adapter licenses](../README.md#model-and-adapter-licenses).

## Agent Security Rules

- Never commit `.env`, credentials, or API keys
- Never print them either — the canonical rule lives in
  [AGENTS.md §12 — Secret Handling](../AGENTS.md#12-secret-handling)
- The user request and trusted repository instructions are authoritative; see
  [AGENTS.md — Instruction Authority](../AGENTS.md#instruction-authority).
- Never weaken validation or tenant checks without explicit instruction
- Always validate at system boundaries
