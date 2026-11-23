<!-- last_verified: 2026-11-23 -->
# Feature: Library

## Purpose
Show everything this app wrote under `APP_PREFIX`, grouped the way the app thinks about it: tenant, adapter, version; output images; run reports.

## Used By
- UI: `/library` (tenant filter; Adapters, Outputs and Reports tabs)
- API: `GET /library?tenant_id=&kind=`, `GET /files-by-key/preview` for image tiles

## Core Functions
- `services/api/app/service/library.py` — lists `adapters/`, `outputs/`, `reports/` under the prefix and classifies each key
- `apps/web/src/components/library/library-view.tsx` — tree, gallery, report list

## Canonical Files
- `services/api/app/service/library.py`

## Inputs
- `tenant_id?` (validated identifier), `kind?` (`adapters` | `outputs` | `reports`)

## Outputs
- `LibraryEntry[]`: `key`, `kind`, `tenant_id?`, `adapter?`, `version?`, `run_id?`, `size_bytes`, `last_modified`, newest first

## Flow
- Pick a tenant (or all), switch tabs; output tiles open in the bucket explorer's preview; reports link to their run

## Edge Cases
- Objects under the prefix that do not match the layout are skipped
- A tenant filter does not narrow reports (reports are per run, not per tenant)

## UX States
- Empty: "Nothing under the app prefix yet"
- Loading: skeleton
- Error: `ErrorState` with retry

## Verification
- Test files: `services/api/tests/test_adapter_delete_scope.py` (`test_tenants_and_library_listing`)
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full`
- Pass criteria: tests green

## Related Docs
- [File Browser](file-browser.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
