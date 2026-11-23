<!-- last_verified: 2026-11-23 -->
# Feature: Generate and Compare

## Purpose
Let a user send one generation request as a tenant, or render one prompt and seed across several of a tenant's adapters plus the base model, and see the results side by side.

## Used By
- UI: `/generate` (Generate card and Compare card), the Generate panel on `/adapters/[tenantId]/[adapter]`
- API: `POST /tenants/{tenant_id}/generations`, `POST /runs/compare`, `GET /jobs/{job_id}`, `GET /jobs/{job_id}/output`, `GET /runs/{run_id}`

## Core Functions
- `apps/web/src/components/generate/generate-form.tsx`: tenant, adapter (the tenant's first adapter by default, or None), version, prompt, seed (empty means random), steps, size, scale, a one-click isolation check, and a collapsed raw-reference field
- `apps/web/src/components/generate/no-worker-notice.tsx`: warns before submit that no worker is online and names `pnpm worker`
- `apps/web/src/lib/job-deep-link.ts`: keeps the active job id in `?job=` so a reload resumes the result card, and in sessionStorage (cleared once the job ends) so sidebar navigation back to Generate resumes it too
- `apps/web/src/components/generate/compare-form.tsx`: tenant, up to four adapters, include-base switch
- `apps/web/src/components/jobs/job-image.tsx`: image via presigned GET, or the worker's live phase and step; a stale-worker warning; checksum and unload confirmation once done
- `apps/web/src/lib/adapter-ref.ts`: reference parsing and the isolation error messages
- `services/api/app/service/jobs.py`: `enqueue_generation`, `enqueue_compare`

## Canonical Files
- `apps/web/src/components/generate/generate-form.tsx`

## Inputs
- See `GenerationRequest` and `CompareRequest` in [Adapter Serving](adapter-serving.md); defaults for steps and size come from Settings

## Outputs
- A job (Generate) or a run with one job per adapter plus base (Compare), all on one seed

## Flow
- Generate: choose tenant and adapter (the tenant's first adapter at its current version by default), write a prompt, optionally fix a seed, submit; the job id goes into the URL and the card polls the job every 2 s until it ends, then shows the image
- Compare: choose adapters (all by default, max 4) and submit; jobs share the seed, so differences come only from the adapters
- Isolation check: the visible "Try <other tenant>/<adapter>" button fills the raw reference with another tenant's adapter; submitting shows the 403 isolation response in place. Editing the reference clears the old rejection

## Edge Cases
- Rejected reference -> alert with the API code and "No job was created"
- No workers running -> a notice above the form names the command; a submitted job stays "Waiting for a worker"
- Claiming worker stops heartbeating (two missed beats) -> the card says the worker stopped responding and that the job is retried on another worker when its lease expires
- Reload or sidebar navigation mid-generation -> `?job=` or the tab's stored job restores the result card (and the tenant, adapter, version and prompt), which resumes polling; a job that finished meanwhile is shown once, then forgotten
- Compare with one bad reference -> the whole request is rejected, no jobs

## UX States
- Empty: dashed placeholder until a job exists
- Loading: "Waiting for a worker", then the worker's phase (verifying a cached adapter, fetching from B2 with streaming sha256, loading, "Generating, step n / N", unloading, uploading), in an `aria-live` region
- Disabled submit: helper text says why (no tenant, or no prompt)
- Error: failed job shows its `error_code` and message

## Verification
- Test files: `apps/web/src/lib/adapter-ref.test.ts`, `apps/web/src/lib/job-state.test.ts`, `apps/web/src/lib/job-deep-link.test.ts`, `apps/web/e2e/adapters.spec.ts`; `services/api/tests/test_resolver_isolation.py`
- Required cases: reference parsing, cross-tenant rejection message, compare enqueues one seed
- Focused verify command: `pnpm test:web`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full`
- Pass criteria: tests green

## Related Docs
- [Adapter Serving](adapter-serving.md)
- [Runs and Reports](runs-and-reports.md)
