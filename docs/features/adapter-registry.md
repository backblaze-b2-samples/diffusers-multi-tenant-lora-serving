<!-- last_verified: 2026-11-23 -->
# Feature: Adapter Registry

## Purpose
Publish, version, edit, verify and delete each tenant's LoRA adapters in B2, so a request can only ever resolve to an adapter its own tenant published and that is fully stored.

## Used By
- UI: `/adapters` (table, "Publish adapter" dialog, "Publish demo adapters"), `/adapters/[tenantId]/[adapter]` (versions, manifest, Edit sheet, Verify checksum, delete)
- API: `GET /tenants`, `GET /tenants/{tenant_id}/manifest`, `GET|POST /tenants/{tenant_id}/adapters`, `GET|PATCH|DELETE /tenants/{tenant_id}/adapters/{adapter}`, `DELETE .../versions/{version}`, `POST .../versions/{version}/verify`, `POST /fixtures/publish`
- Script: `services/api/scripts/publish_fixtures.py` (`pnpm publish:fixtures`)

## Core Functions
- `services/api/app/service/registry.py`: `publish`, `update_adapter`, `delete_adapter`, `delete_version`, `verify_version`, `list_tenants`, `list_adapters`
- `services/api/app/service/manifests.py`: tenant and version manifest reads (10 s cache, ETag revalidation) and writes
- `services/api/app/service/safetensors_check.py`: header parse; refuses pickle formats
- `services/api/app/service/publish_sources.py`: pinned Hugging Face file or uploaded file
- `services/api/app/service/fixtures.py`: the demo set from `fixtures/adapters.yaml`
- `services/api/app/repo/adapter_store.py`: managed multipart upload while hashing, head, streamed re-hash, prefix-scoped delete
- `services/api/app/repo/hf_source.py`: `huggingface_hub` download and model-card base model

## Canonical Files
- Publish order: `services/api/app/service/registry.py` (`publish`)
- Key layout: `services/api/app/service/keys.py`

## Inputs
- Multipart form: `adapter`, `version`, `license`, `source` (`huggingface` | `upload`), `display_name?`, `default_scale`, `trigger_words?` (comma separated), `hf_repo_id?`, `hf_filename?`, `hf_revision?`, `file?`
- `AdapterUpdate` JSON: `display_name?`, `default_scale?`, `trigger_words?`, `current_version?`

## Outputs
- B2 objects under `<APP_PREFIX>adapters/<tenant>/`: `<adapter>/<version>/adapter.safetensors`, `<adapter>/<version>/manifest.json` (immutable), and `manifest.json` (the tenant manifest)
- `AdapterDetail` with every version's sha256, size, source, license and keys

## Flow
- Validate identifiers (`^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$`, `v1[.2[.3]]`), license against the allowlist, `.safetensors` name and a well-formed safetensors header that accounts for the whole file
- Under a per-tenant lock: refuse an existing version (409), stream the weight to B2 with `upload_fileobj` while hashing, `head_object` to check the stored size, write the version manifest, then rewrite the tenant manifest LAST
- Edit rewrites only the tenant manifest entry; weights never change
- Delete removes the entry from the tenant manifest first, then deletes exactly the objects listed under the adapter's (or version's) own prefix
- Verify streams the weight back from B2 and compares sha256 and size with the manifest

## Edge Cases
- Failure before the last step -> tenant manifest unchanged, version never resolvable
- `.bin`, `.pt`, `.ckpt`, or pickle bytes named `.safetensors` -> 422 `not_safetensors`
- License outside the allowlist -> 422 `license_not_allowed`
- Hugging Face card names another base model -> 422 `base_model_mismatch`
- Deleting the current version while others exist -> 409; make another version current first
- Adapter names that share a prefix (`pixel-art`, `pixel-art-xl`) -> deletes use a trailing slash, so neither touches the other
- One dispatcher owns manifest writes; running several dispatchers against one prefix is out of scope

## UX States
- Empty: "No adapters published yet" with "Publish demo adapters"
- Loading: skeleton rows
- Error: inline `ErrorState` with retry; publish errors as a toast with the API's detail

## Verification
- Test files: `services/api/tests/test_publish_manifest.py`, `test_adapter_delete_scope.py`, `test_identifiers.py`; `apps/web/e2e/adapters.spec.ts`
- Required cases: manifest-last order, failure leaves manifest unchanged, 409 on existing version, pickle rejected, license 422, delete scope, verify mismatch
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full`; live: `pnpm selftest`
- Pass criteria: tests green; the self-test's publish step re-reads every weight and matches its manifest sha256

## Related Docs
- [Adapter Serving](adapter-serving.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [App Workflows](../app-workflows.md)
