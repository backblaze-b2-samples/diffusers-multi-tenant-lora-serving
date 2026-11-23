<!-- last_verified: 2026-11-23 -->
# Feature: Generate and Compare

## Purpose
Let a user send one generation request as a tenant, or render one prompt and seed across several of a tenant's adapters plus the base model, and see the results side by side.

## Used By
- UI: `/generate` (Generate card and Compare card), the Generate panel on `/adapters/[tenantId]/[adapter]`
- API: `POST /tenants/{tenant_id}/generations`, `POST /runs/compare`, `GET /jobs/{job_id}`, `GET /jobs/{job_id}/output`, `GET /runs/{run_id}`

## Core Functions
- `apps/web/src/components/generate/generate-form.tsx` — tenant, adapter (or None), version, prompt, seed, steps, size, scale, and a collapsed raw-reference field
- `apps/web/src/components/generate/compare-form.tsx` — tenant, up to four adapters, include-base switch
- `apps/web/src/components/jobs/job-image.tsx` — image via presigned GET, or progress with the current step
- `apps/web/src/lib/adapter-ref.ts` — reference parsing and the isolation error messages
- `services/api/app/service/jobs.py` — `enqueue_generation`, `enqueue_compare`

## Canonical Files
- `apps/web/src/components/generate/generate-form.tsx`

## Inputs
- See `GenerationRequest` and `CompareRequest` in [Adapter Serving](adapter-serving.md); defaults for steps and size come from Settings

## Outputs
- A job (Generate) or a run with one job per adapter plus base (Compare), all on one seed

## Flow
- Generate: choose tenant and adapter (current version by default), write a prompt, optionally fix a seed, submit; the card polls the job every 2 s until it ends, then shows the image
- Compare: choose adapters (all by default, max 4) and submit; jobs share the seed, so differences come only from the adapters
- Advanced: a raw reference such as `globex/papercut` shows the 403 isolation response in place

## Edge Cases
- Rejected reference -> alert with the API code and "No job was created"
- No workers running -> the job stays "Waiting for a worker"
- Compare with one bad reference -> the whole request is rejected, no jobs

## UX States
- Empty: dashed placeholder until a job exists
- Loading: "Waiting for a worker", then "Step n / N on <worker>"
- Error: failed job shows its `error_code` and message

## Verification
- Test files: `apps/web/src/lib/adapter-ref.test.ts`, `apps/web/e2e/adapters.spec.ts`; `services/api/tests/test_resolver_isolation.py`
- Required cases: reference parsing, cross-tenant rejection message, compare enqueues one seed
- Focused verify command: `pnpm test:web`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full`
- Pass criteria: tests green

## Related Docs
- [Adapter Serving](adapter-serving.md)
- [Runs and Reports](runs-and-reports.md)
