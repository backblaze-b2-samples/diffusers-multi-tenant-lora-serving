<!-- last_verified: 2026-11-23 -->
# Feature: Dashboard

## Purpose
Give an at-a-glance view of the serving system: tenants and adapters in B2, jobs by state, workers online, the adapter cache hit rate, and where time goes per job.

## Used By
- UI: `/`
- API: `GET /tenants`, `GET /jobs`, `GET /workers`

## Core Functions
- `apps/web/src/components/dashboard/stats-cards.tsx`: tenants, adapter versions, jobs by state, workers online, cache hit rate
- `apps/web/src/components/dashboard/timing-card.tsx`: stacked fetch / load / generate / unload ms for the latest succeeded jobs
- `apps/web/src/components/dashboard/recent-jobs-table.tsx`: last 8 jobs with worker and cache result
- `apps/web/src/lib/report-chart.ts`: `jobTimingRows`, `cacheHitRate`

## Canonical Files
- `apps/web/src/components/dashboard/stats-cards.tsx`

## Inputs
- None

## Outputs
- Read-only views

## Flow
- Page loads three queries; the jobs query polls every 2 s while any job is active, otherwise every 15 s; workers every 10 s

## Edge Cases
- API unreachable -> `ErrorState` with retry instead of zeros
- No adapter jobs yet -> cache hit rate shows "-"

## UX States
- Loading: skeleton values
- Empty: "No finished jobs yet" chart, "No jobs yet" table

## Verification
- Test files: `apps/web/src/lib/report-chart.test.ts`
- Focused verify command: `pnpm test:web`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full`
- Pass criteria: tests green

## Related Docs
- [Runs and Reports](runs-and-reports.md)
- [App Workflows](../app-workflows.md)
