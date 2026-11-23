<!-- last_verified: 2026-11-23 -->
# App Workflows

User journeys inside the application.

## Publish and Manage Adapters

- User opens `/adapters`; the table lists every tenant's adapters (filter by tenant)
- Empty registry: **Publish demo adapters** downloads three pinned SDXL LoRAs and publishes `acme/pixel-art`, `acme/3d-render` and `globex/papercut`
- **Publish adapter** dialog: pick a tenant (or "New tenant…"), name the adapter and version, choose Hugging Face (repo, filename, pinned revision) or an uploaded `.safetensors` file, pick the license from the allowlist, optionally a default scale and trigger words. Publishing an existing version is refused (409); publish `v2` to change weights
- The detail page `/adapters/<tenant>/<adapter>` shows versions with sha256, size, source and license, the tenant manifest entry, recent jobs and a Generate panel
- **Edit** sheet changes the display name, default scale, trigger words and current version (the tenant manifest only)
- **Verify checksum** (row action) re-reads the weight from B2 and compares it with the manifest
- Delete one version (row action; not the current one while others exist) or the whole adapter from the danger zone after typing its name
- See: [Adapter Registry](features/adapter-registry.md)

## Generate Images

- User opens `/generate` (or the Generate panel on an adapter page)
- Picks a tenant, an adapter of that tenant (or "None (base model)"), a version, a prompt and optionally a seed; steps and size start from the Settings defaults
- Submits; the card shows "Waiting for a worker", then "Step n / N on w1", then the image with seed, worker, cache result and load and generate times
- **Advanced: raw adapter reference** accepts `owner/name[@version]`; asking for another tenant's adapter shows the 403 and states that no job was created
- **Compare adapters** renders one prompt and seed across up to four adapters plus the base model and shows them side by side
- See: [Generate and Compare](features/generate.md)

## Review Runs

- User opens `/runs`: every run with its job count, state and whether its report exists
- `/runs/<run-id>` shows each job's image labelled with its tenant and adapter, so a cross-tenant leak would be visible, then the `adapters.json` summary (cache hits, load and generate p50, retried jobs) and a stacked timing chart per job
- A job that a dead worker abandoned shows attempt 2 on another worker
- See: [Runs and Reports](features/runs-and-reports.md)

## Browse the Library

- User opens `/library` and optionally filters by tenant
- **Adapters** tab: tenant, then adapter, then version, with every object and its size
- **Outputs** tab: a gallery of generated images; a tile opens the object in the bucket explorer preview
- **Reports** tab: each run's `adapters.json`, linking to the run
- See: [Library](features/library.md)

## Browse the Bucket

- User opens `/files`: the 100 most recent objects in the whole bucket, including objects this app did not write, in a folder tree
- Clicking a file opens its preview with Download and Delete; "Detailed metadata" shows checksums and image size
- See: [Bucket Explorer](features/file-browser.md)

## View Dashboard

- User opens `/`: tenants, adapter versions, jobs by state, workers online and the adapter cache hit rate
- The timing chart stacks fetch, load, generate and unload time for the latest finished jobs; the recent jobs table links each job to its run
- See: [Dashboard](features/dashboard.md)

## Change Preferences

- User opens `/settings`, sets the theme and the default steps and size for new Generate and Compare forms, and saves (stored in this browser)
- The read-only Server card shows the base model, app prefix, presigned URL lifetimes, job lease, workers online and the license allowlist
- See: [Settings](features/settings.md)
