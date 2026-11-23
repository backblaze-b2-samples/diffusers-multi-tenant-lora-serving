import type {
  AdapterDetail,
  AdapterReport,
  AdapterSummary,
  AdapterUpdate,
  CompareRequest,
  DailyUploadCount,
  DeleteAdapterResult,
  DeleteFileResponse,
  FileMetadata,
  FileMetadataDetail,
  FileUrlResponse,
  GenerationRequest,
  HealthStatus,
  Job,
  LibraryEntry,
  RunDetail,
  RunSummary,
  ServerConfig,
  TenantManifest,
  TenantSummary,
  UploadStats,
  VerifyResult,
  WorkerStatus,
} from "@diffusers-multi-tenant-lora-serving/shared";

import { API_CLIENT_ROUTES } from "./generated/api-routes";

// The route registry is GENERATED from the API contract (`pnpm gen:api`), so
// it cannot drift from FastAPI. Re-exported from here because this module is
// the frontend's API surface: consumers and the contract test import it from
// `lib/api-client`, and that import path should not change just because the
// registry moved behind a generator.
//
// Everything else in this file is hand-written on purpose — error policy
// (including the API's stable error `code`), base URL resolution, the
// legacy-route fallback, the CORS diagnostics and the multipart publish
// request are per-app judgement the contract does not describe. See
// `scripts/gen/api-gen.config.json` (`escapeHatch`).
export { API_CLIENT_ROUTES };

// Single-origin deploys (Vercel `services`: one project serving web + API) put
// the API under /api on the same origin, so no NEXT_PUBLIC_API_URL is needed —
// a production build with it unset defaults to the relative "/api". An explicit
// NEXT_PUBLIC_API_URL still wins (two-project / separate-origin deploys). Local
// dev (NODE_ENV !== "production") falls back to the dev API port.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === "production" ? "/api" : "http://localhost:8000");

/** Typed API error with HTTP status code for caller-side branching. */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    /** Stable machine-readable reason from the API (e.g. `cross_tenant_adapter`). */
    public readonly code: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True for 408, 429, 500, 502, 503, 504 — worth retrying. */
  get isRetryable(): boolean {
    return [408, 429, 500, 502, 503, 504].includes(this.status);
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isConflict(): boolean {
    return this.status === 409;
  }
}

/**
 * Build the right status-0 ApiError for a thrown fetch().
 *
 * fetch() rejects with a TypeError for genuinely-offline/DNS failures AND for
 * responses the browser refused to expose — most notably a cross-origin 500
 * that shipped without `Access-Control-Allow-Origin`. We can't tell those apart
 * from the error object, but `navigator.onLine === false` reliably means the
 * device has no connectivity. Anything else reached the network, so the most
 * likely cause is the server erroring with a CORS-blocked response — point the
 * developer at the API logs instead of blaming their connection.
 */
function networkError(): ApiError {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return new ApiError("You appear to be offline — check your connection", 0);
  }
  return new ApiError(
    "Couldn't reach the API, or the server returned an error the browser blocked (CORS). Check the API logs.",
    0,
  );
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw networkError();
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      typeof body.detail === "string" ? body.detail : `API error: ${res.status}`,
      res.status,
      typeof body.code === "string" ? body.code : null,
    );
  }
  return res.json();
}

function isEndpointUnavailable(error: unknown): error is ApiError {
  return (
    error instanceof ApiError &&
    error.status === 404 &&
    (error.message === "Not Found" || error.message === "API error: 404")
  );
}

async function apiFetchWithLegacyFallback<T>(
  path: string,
  legacyPath: () => string,
  init?: RequestInit
): Promise<T> {
  try {
    return await apiFetch<T>(path, init);
  } catch (error) {
    if (isEndpointUnavailable(error)) {
      return apiFetch<T>(legacyPath(), init);
    }
    throw error;
  }
}

function fileKeyQuery(key: string): string {
  if (key.length === 0) {
    throw new ApiError("File key is required", 400);
  }
  return new URLSearchParams({ key }).toString();
}

function legacyFileKeyPath(
  key: string,
  options: { blockRouteCollisions?: boolean } = {}
): string {
  if (!isLegacyPathFallbackSafe(key, options)) {
    throw new ApiError("Current API version required for this file key", 404);
  }
  return encodeURIComponent(key);
}

/**
 * Substitute a file key into a legacy `{key}` path template. The parameter type
 * requires the literal `{key}` placeholder, so passing a registry path that has
 * no placeholder is a compile error rather than a silent no-op that would send
 * the request to a keyless URL.
 */
function legacyFileKeyRoute(
  path: `${string}{key}${string}`,
  key: string,
  options: { blockRouteCollisions?: boolean } = {}
): string {
  return path.replace("{key}", legacyFileKeyPath(key, options));
}

function isLegacyPathFallbackSafe(
  key: string,
  { blockRouteCollisions = false }: { blockRouteCollisions?: boolean } = {}
): boolean {
  if (/(\.\.\/|\/\.\.|\\|%2e%2e|%00|\x00)/i.test(key)) return false;
  if (!blockRouteCollisions) return true;

  const lowerKey = key.toLowerCase();
  if (lowerKey === "stats" || lowerKey === "stats/activity") return false;
  if (lowerKey.endsWith("/download") || lowerKey.endsWith("/preview")) return false;
  return true;
}

export async function getHealth() {
  return apiFetch<HealthStatus>(API_CLIENT_ROUTES.health.path);
}

export async function getFiles(prefix = "", limit = 100) {
  return apiFetch<FileMetadata[]>(
    `${API_CLIENT_ROUTES.files.path}?prefix=${encodeURIComponent(prefix)}&limit=${limit}`
  );
}

export async function getFileStats() {
  return apiFetch<UploadStats>(API_CLIENT_ROUTES.fileStats.path);
}

export async function getUploadActivity(days = 7) {
  return apiFetch<DailyUploadCount[]>(
    `${API_CLIENT_ROUTES.uploadActivity.path}?days=${days}`
  );
}

export async function getFile(key: string) {
  return apiFetchWithLegacyFallback<FileMetadata>(
    `${API_CLIENT_ROUTES.fileByKeyMetadata.path}?${fileKeyQuery(key)}`,
    () =>
      legacyFileKeyRoute(API_CLIENT_ROUTES.legacyFileMetadata.path, key, {
        blockRouteCollisions: true,
      })
  );
}

/**
 * Rich metadata (checksums, image/PDF fields) for an already-stored file.
 * The server recomputes this on demand by downloading the object, so it's a
 * heavier call than getFile — fetch it lazily (only when the user asks to see
 * details). No legacy path fallback: this endpoint is new, so an older backend
 * wouldn't serve it under any route.
 */
export async function getFileDetail(key: string) {
  return apiFetch<FileMetadataDetail>(
    `${API_CLIENT_ROUTES.fileByKeyDetail.path}?${fileKeyQuery(key)}`
  );
}

export async function getDownloadUrl(key: string) {
  return apiFetchWithLegacyFallback<FileUrlResponse>(
    `${API_CLIENT_ROUTES.fileByKeyDownload.path}?${fileKeyQuery(key)}`,
    () => legacyFileKeyRoute(API_CLIENT_ROUTES.legacyFileDownload.path, key)
  );
}

/** Preview-only presigned URL — does NOT increment the download counter. */
export async function getPreviewUrl(key: string) {
  return apiFetchWithLegacyFallback<FileUrlResponse>(
    `${API_CLIENT_ROUTES.fileByKeyPreview.path}?${fileKeyQuery(key)}`,
    () => legacyFileKeyRoute(API_CLIENT_ROUTES.legacyFilePreview.path, key)
  );
}

export async function deleteFile(key: string) {
  return apiFetchWithLegacyFallback<DeleteFileResponse>(
    `${API_CLIENT_ROUTES.fileByKeyDelete.path}?${fileKeyQuery(key)}`,
    () => legacyFileKeyRoute(API_CLIENT_ROUTES.legacyFileDelete.path, key),
    {
      // Derived from the registry so the verb the contract test checks is the
      // verb actually sent — a hardcoded "DELETE" could silently disagree.
      method: API_CLIENT_ROUTES.fileByKeyDelete.method.toUpperCase(),
    }
  );
}

// ---- LoRA serving ----

const enc = encodeURIComponent;

/** Fill `{name}` placeholders of a registry path with URL-encoded values. */
export function fillPath(path: string, params: Record<string, string>): string {
  return path.replace(/\{(\w+)\}/g, (_m, name: string) => {
    const value = params[name];
    if (value === undefined || value === "") {
      throw new ApiError(`Missing path parameter: ${name}`, 400);
    }
    return enc(value);
  });
}

function jsonInit(method: string, body?: unknown): RequestInit {
  return {
    method: method.toUpperCase(),
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  };
}

const R = API_CLIENT_ROUTES;

export const getTenants = () => apiFetch<TenantSummary[]>(R.tenants.path);

export const getTenantManifest = (tenant_id: string) =>
  apiFetch<TenantManifest>(fillPath(R.tenantManifest.path, { tenant_id }));

export const getAdapters = (tenant_id: string) =>
  apiFetch<AdapterSummary[]>(fillPath(R.adapters.path, { tenant_id }));

export const getAdapter = (tenant_id: string, adapter: string) =>
  apiFetch<AdapterDetail>(fillPath(R.adapter.path, { tenant_id, adapter }));

/** Fields of the publish form; `file` only for `source: "upload"`. */
export interface PublishAdapterInput {
  tenant_id: string;
  adapter: string;
  version: string;
  license: string;
  source: "huggingface" | "upload";
  display_name?: string;
  default_scale: number;
  trigger_words?: string;
  hf_repo_id?: string;
  hf_filename?: string;
  hf_revision?: string;
  file?: File | null;
}

/** Multipart POST: the API reads form fields and an optional file part. */
export function publishAdapter(input: PublishAdapterInput) {
  const form = new FormData();
  const { tenant_id, file, ...fields } = input;
  for (const [name, value] of Object.entries(fields)) {
    if (value !== undefined && value !== null && value !== "") form.append(name, String(value));
  }
  if (input.source === "upload" && file) form.append("file", file, file.name);
  return apiFetch<AdapterDetail>(fillPath(R.publishAdapter.path, { tenant_id }), {
    method: R.publishAdapter.method.toUpperCase(),
    body: form,
  });
}

export const publishFixtures = () =>
  apiFetch<AdapterDetail[]>(R.publishFixtures.path, jsonInit(R.publishFixtures.method));

export const updateAdapter = (tenant_id: string, adapter: string, patch: AdapterUpdate) =>
  apiFetch<AdapterDetail>(
    fillPath(R.updateAdapter.path, { tenant_id, adapter }),
    jsonInit(R.updateAdapter.method, patch),
  );

export const deleteAdapter = (tenant_id: string, adapter: string, confirm: string) =>
  apiFetch<DeleteAdapterResult>(
    `${fillPath(R.deleteAdapter.path, { tenant_id, adapter })}?confirm=${enc(confirm)}`,
    { method: R.deleteAdapter.method.toUpperCase() },
  );

export const deleteAdapterVersion = (tenant_id: string, adapter: string, version: string) =>
  apiFetch<DeleteAdapterResult>(
    fillPath(R.deleteAdapterVersion.path, { tenant_id, adapter, version }),
    { method: R.deleteAdapterVersion.method.toUpperCase() },
  );

export const verifyAdapterVersion = (tenant_id: string, adapter: string, version: string) =>
  apiFetch<VerifyResult>(
    fillPath(R.verifyAdapterVersion.path, { tenant_id, adapter, version }),
    jsonInit(R.verifyAdapterVersion.method),
  );

export const createGeneration = (tenant_id: string, body: GenerationRequest) =>
  apiFetch<Job>(
    fillPath(R.createGeneration.path, { tenant_id }),
    jsonInit(R.createGeneration.method, body),
  );

export const compareAdapters = (body: CompareRequest) =>
  apiFetch<RunDetail>(R.compareAdapters.path, jsonInit(R.compareAdapters.method, body));

export const getRuns = () => apiFetch<RunSummary[]>(R.runs.path);

export const getRun = (run_id: string) => apiFetch<RunDetail>(fillPath(R.run.path, { run_id }));

export const getRunReport = (run_id: string) =>
  apiFetch<AdapterReport>(fillPath(R.runReport.path, { run_id }));

export function getJobs(tenant_id?: string, state?: string) {
  const q = new URLSearchParams();
  if (tenant_id) q.set("tenant_id", tenant_id);
  if (state) q.set("state", state);
  const qs = q.toString();
  return apiFetch<Job[]>(qs ? `${R.jobs.path}?${qs}` : R.jobs.path);
}

export const getJob = (job_id: string) => apiFetch<Job>(fillPath(R.job.path, { job_id }));

export const getJobOutput = (job_id: string) =>
  apiFetch<FileUrlResponse>(fillPath(R.jobOutput.path, { job_id }));

export const getWorkers = () => apiFetch<WorkerStatus[]>(R.workers.path);

export function getLibrary(tenant_id?: string, kind?: string) {
  const q = new URLSearchParams();
  if (tenant_id) q.set("tenant_id", tenant_id);
  if (kind) q.set("kind", kind);
  const qs = q.toString();
  return apiFetch<LibraryEntry[]>(qs ? `${R.library.path}?${qs}` : R.library.path);
}

export const getServerConfig = () => apiFetch<ServerConfig>(R.serverConfig.path);
