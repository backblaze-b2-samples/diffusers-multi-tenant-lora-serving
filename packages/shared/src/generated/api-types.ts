// GENERATED FILE — DO NOT EDIT.
//
// Written by `pnpm gen:api` from:
//   docs/api/openapi.json
//
// Hand edits are discarded by the next `pnpm gen:api`. `pnpm gen:check`
// (part of `pnpm verify:web`) fails while this file disagrees with the
// contract. To change what is here, change the FastAPI route or Pydantic
// model and re-run `pnpm contract:export && pnpm gen:api`.

export interface AdapterDetail {
  adapter: string;
  current_version: string;
  default_scale: number;
  display_name: string;
  license: string;
  size_bytes: number;
  tenant_id: string;
  trigger_words: string[];
  versions: AdapterVersion[];
}

/** `reports/<run-id>/adapters.json`: per-job timings and cache behaviour. */
export interface AdapterReport {
  base_model: string;
  created_at: string;
  device_summary: string[];
  jobs: ReportJob[];
  run_id: string;
  summary: ReportSummary;
}

export interface AdapterSource {
  filename?: string | null;
  repo_id?: string | null;
  revision?: string | null;
  type: string;
}

export interface AdapterSummary {
  adapter: string;
  current_version: string;
  default_scale: number;
  display_name: string;
  license: string;
  /** Size of the current version's weight file. */
  size_bytes: number;
  tenant_id: string;
  version_count: number;
}

export interface AdapterUpdate {
  current_version?: string | null;
  default_scale?: number | null;
  display_name?: string | null;
  trigger_words?: string[] | null;
}

export interface AdapterVersion {
  base_model: BaseModelRef;
  is_current: boolean;
  license: string;
  manifest_key: string;
  published_at: string;
  sha256: string;
  size_bytes: number;
  source: AdapterSource | null;
  version: string;
  weight_key: string;
}

export interface BaseModelRef {
  id: string;
  revision?: string | null;
}

export interface Body_publish_adapter_tenants__tenant_id__adapters_post {
  adapter: string;
  default_scale?: number;
  display_name?: string | null;
  file?: string | null;
  hf_filename?: string | null;
  hf_repo_id?: string | null;
  hf_revision?: string | null;
  license: string;
  source: string;
  /** Comma separated. */
  trigger_words?: string | null;
  version: string;
}

export interface ClaimRequest {
  wait_seconds?: number;
  worker_id: string;
}

export interface ClaimResponse {
  job: WorkerJob | null;
}

export interface CompareRequest {
  adapters: string[];
  include_base?: boolean;
  prompt: string;
  seed?: number | null;
  size?: number;
  steps?: number;
  tenant_id: string;
}

/** One day's upload count, for the dashboard activity chart. */
export interface DailyUploadCount {
  date: string;
  uploads: number;
}

export interface DeleteAdapterResult {
  deleted_keys: string[];
}

/** Acknowledgement that one object was removed from the bucket. */
export interface DeleteFileResponse {
  deleted: boolean;
  key: string;
}

/** One stored object as the file list and the by-key metadata route see it. */
export interface FileMetadata {
  content_type: string;
  filename: string;
  folder: string;
  key: string;
  size_bytes: number;
  size_human: string;
  uploaded_at: string;
  /**
   * Public object URL, set only when B2_PUBLIC_URL_BASE is configured and
   * the bucket is public. Null otherwise — the UI asks for a presigned URL
   * instead.
   */
  url: string | null;
}

/** Rich metadata recomputed on demand by re-reading the stored object. */
export interface FileMetadataDetail {
  /** Audio/video: bits per second. */
  bitrate: number | null;
  /** Audio/video: codec name. */
  codec: string | null;
  /** Audio/video: duration in seconds. */
  duration_seconds: number | null;
  /**
   * Image-specific: EXIF tags, values stringified. Null for non-images or
   * when no EXIF block was present.
   */
  exif: Record<string, string> | null;
  extension: string;
  filename: string;
  /** Image-specific: pixel height. Null for non-images. */
  image_height: number | null;
  /** Image-specific: pixel width. Null for non-images. */
  image_width: number | null;
  md5: string;
  /**
   * Set when a format-specific extractor was skipped or failed (e.g. an
   * image above Pillow's decompression-bomb limit). The core fields are
   * always exact, so the UI shows this instead of silently dropping the
   * Image / PDF section.
   */
  metadata_warning: string | null;
  mime_type: string;
  /** PDF-specific: author. */
  pdf_author: string | null;
  /** PDF-specific: page count. Null for non-PDFs. */
  pdf_pages: number | null;
  /** PDF-specific: title. */
  pdf_title: string | null;
  sha256: string;
  size_bytes: number;
  size_human: string;
  uploaded_at: string;
}

/** A short-lived presigned GET for downloading or previewing one object. */
export interface FileUrlResponse {
  /**
   * Presigned GET URL. Download URLs force an attachment disposition;
   * preview URLs are signed inline so a PDF renders in place.
   */
  url: string;
}

export interface GenerationRequest {
  /**
   * `name`, `name@version`, `owner/name[@version]`, or null for the base
   * model.
   */
  adapter?: string | null;
  negative_prompt?: string | null;
  prompt: string;
  run_id?: string | null;
  scale?: number | null;
  seed?: number | null;
  size?: number;
  steps?: number;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

/**
 * Liveness plus B2 reachability. The route answers HTTP 200 even when B2
 * is unreachable, so a caller must read `b2_connected` rather than
 * trusting the status code.
 */
export interface HealthStatus {
  /** True when the bucket answered a cheap head request. */
  b2_connected: boolean;
  /** The shared base model every worker loads. */
  base_model: string;
  /** "healthy" when B2 answered, else "degraded". */
  status: string;
  /** Workers seen within the online window. */
  workers_online: number;
}

export interface Heartbeat {
  attempt: number;
  step?: number | null;
  total_steps?: number | null;
  worker_id: string;
}

export interface HeartbeatAck {
  lease_expires_at: string;
}

export interface Job {
  adapter: string | null;
  adapter_sha256: string | null;
  adapters_after_unload: string[] | null;
  attempt: number;
  bytes_fetched: number | null;
  cache: string | null;
  created_at: string;
  error_code: string | null;
  error_message: string | null;
  finished_at: string | null;
  height: number;
  job_id: string;
  negative_prompt: string | null;
  output_key: string;
  output_sha256: string | null;
  prompt: string;
  run_id: string;
  scale: number | null;
  seed: number;
  sha256_verified: boolean | null;
  state: string;
  /** Last denoising step a heartbeat reported. */
  step: number | null;
  steps: number;
  tenant_id: string;
  timings: JobTimings | null;
  version: string | null;
  width: number;
  worker_id: string | null;
}

export interface JobCompletion {
  adapters_after_unload: string[];
  attempt: number;
  bytes_fetched: number;
  cache: string;
  fetch_ms: number;
  generate_ms: number;
  load_ms: number;
  output_sha256: string;
  sha256_verified: boolean;
  unload_ms: number;
  worker_id: string;
}

export interface JobFailure {
  attempt: number;
  code: string;
  message?: string;
  worker_id: string;
}

export interface JobTimings {
  fetch_ms: number;
  generate_ms: number;
  load_ms: number;
  total_ms: number;
  unload_ms: number;
}

/** One object the app wrote under `APP_PREFIX`, classified by its key. */
export interface LibraryEntry {
  adapter: string | null;
  key: string;
  kind: string;
  last_modified: string;
  run_id: string | null;
  size_bytes: number;
  tenant_id: string | null;
  version: string | null;
}

export interface ReportJob {
  adapter: string | null;
  adapter_sha256: string | null;
  attempt: number;
  bytes_fetched: number;
  cache: string | null;
  error_code: string | null;
  fetch_ms: number;
  generate_ms: number;
  height: number;
  job_id: string;
  load_ms: number;
  output_key: string;
  output_sha256: string | null;
  seed: number;
  state: string;
  steps: number;
  tenant_id: string;
  total_ms: number;
  unload_ms: number;
  version: string | null;
  width: number;
  worker_id: string | null;
}

export interface ReportSummary {
  cache_hits: number;
  failed: number;
  generate_ms_p50: number;
  jobs: number;
  load_ms_p50: number;
  retried_jobs: number;
  succeeded: number;
}

export interface RunDetail {
  created_at: string;
  jobs: Job[];
  report_key: string | null;
  run_id: string;
}

export interface RunSummary {
  created_at: string;
  job_count: number;
  report_key: string | null;
  run_id: string;
  state: string;
}

export interface ServerConfig {
  adapter_url_ttl_seconds: number;
  app_prefix: string;
  base_model: string;
  job_lease_seconds: number;
  license_allowlist: string[];
  output_url_ttl_seconds: number;
  workers_online: number;
}

export interface TenantAdapterEntry {
  current_version: string;
  default_scale?: number;
  display_name: string;
  trigger_words?: string[];
  versions: Record<string, TenantVersionEntry>;
}

/**
 * `adapters/<tenant>/manifest.json`: the only index requests resolve
 * through. Written LAST on every publish, so a request never resolves to a
 * version whose weight or version manifest is not already in B2.
 */
export interface TenantManifest {
  adapters?: Record<string, TenantAdapterEntry>;
  schema_version?: number;
  tenant_id: string;
  updated_at: string;
}

export interface TenantSummary {
  adapter_count: number;
  tenant_id: string;
  total_bytes: number;
  updated_at: string;
  version_count: number;
}

export interface TenantVersionEntry {
  base_model: BaseModelRef;
  license?: string;
  manifest_key: string;
  published_at?: string;
  sha256: string;
  size_bytes: number;
  source?: AdapterSource | null;
  weight_key: string;
}

/** Aggregate bucket figures behind the dashboard stat cards. */
export interface UploadStats {
  total_downloads: number;
  total_files: number;
  total_size_bytes: number;
  total_size_human: string;
  uploads_today: number;
}

export interface ValidationError {
  ctx?: Record<string, unknown>;
  input?: unknown;
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface VerifyResult {
  match: boolean;
  sha256_actual: string;
  sha256_expected: string;
  size_actual: number;
  size_expected: number;
}

export interface WorkerAck {
  heartbeat_seconds: number;
  lease_seconds: number;
}

export interface WorkerAdapter {
  adapter: string;
  base_model: string;
  scale: number;
  sha256: string;
  size_bytes: number;
  /** The version manifest's own tenant_id. */
  tenant_id: string;
  url: string;
  url_expires_at: string;
  version: string;
  weight_key: string;
}

export interface WorkerHello {
  base_model: string;
  cache_bytes?: number;
  cache_entries?: number;
  device: string;
  dtype: string;
  worker_id: string;
}

export interface WorkerJob {
  adapter: WorkerAdapter | null;
  attempt: number;
  height: number;
  job_id: string;
  negative_prompt: string | null;
  output_key: string;
  output_url: string;
  prompt: string;
  run_id: string;
  seed: number;
  steps: number;
  tenant_id: string;
  width: number;
}

export interface WorkerStatus {
  base_model: string;
  cache_bytes: number;
  cache_entries: number;
  current_job_id: string | null;
  device: string;
  dtype: string;
  jobs_done: number;
  last_seen: string;
  online: boolean;
  worker_id: string;
}
