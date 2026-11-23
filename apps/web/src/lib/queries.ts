"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import {
  ApiError,
  compareAdapters,
  createGeneration,
  deleteAdapter,
  deleteAdapterVersion,
  deleteFile,
  getAdapter,
  getAdapters,
  getDownloadUrl,
  getFileDetail,
  getFiles,
  getFileStats,
  getHealth,
  getJob,
  getJobOutput,
  getJobs,
  getLibrary,
  getPreviewUrl,
  getRun,
  getRunReport,
  getRuns,
  getServerConfig,
  getTenantManifest,
  getTenants,
  getUploadActivity,
  getWorkers,
  publishAdapter,
  publishFixtures,
  updateAdapter,
  verifyAdapterVersion,
  type PublishAdapterInput,
} from "@/lib/api-client";
import type {
  AdapterDetail,
  AdapterReport,
  AdapterUpdate,
  CompareRequest,
  FileMetadata,
  FileMetadataDetail,
  FileUrlResponse,
  GenerationRequest,
  Job,
  RunDetail,
} from "@diffusers-multi-tenant-lora-serving/shared";
import { qk } from "@/lib/generated/query-keys";
import { isTerminal } from "@/lib/job-state";

// Query keys are GENERATED from the API contract (`pnpm gen:api`) and their
// hierarchy is declared in `scripts/gen/api-gen.config.json`, so invalidating
// a parent key still reaches its children and no hook can invent a key the API
// cannot answer. Generated keys carry query parameters only; hooks for routes
// with path parameters append those ids to the generated base key.
//
// The caching policy below — staleTime, refetchInterval, retry, `enabled`
// gating, polling while jobs are active, the query-vs-mutation choice, and the
// cache surgery in `dropDeletedFileFromCache` — is hand-written on purpose and
// is never generated.
export { qk };

export type Health = Awaited<ReturnType<typeof getHealth>>;

/** Poll interval while any job on screen is still queued or running. */
export const ACTIVE_POLL_MS = 2_000;

/**
 * Gate a query on something being open/visible. Deliberately the only option we
 * expose, so callers can't drift the caching policy per call site — the ⌘K
 * palette reuses `useFiles`' key (and therefore its cache) instead of fetching
 * its own private, smaller list.
 */
export interface QueryGate {
  enabled?: boolean;
}

export function useFiles(prefix = "", limit = 100, { enabled = true }: QueryGate = {}) {
  return useQuery<FileMetadata[], ApiError>({
    queryKey: qk.files(prefix, limit),
    queryFn: () => getFiles(prefix, limit),
    enabled,
  });
}

export function useFileStats({ enabled = true }: QueryGate = {}) {
  return useQuery({
    queryKey: qk.stats(),
    queryFn: getFileStats,
    enabled,
  });
}

export function useUploadActivity(days = 7) {
  return useQuery({
    queryKey: qk.uploadActivity(days),
    queryFn: () => getUploadActivity(days),
  });
}

// Presigned preview URL — only fetched when `enabled` is true (e.g., when
// the dialog opens for a specific file). Kept short-lived (60s) because
// the URL itself has a presigned expiry and is cheap to regenerate.
export function usePreviewUrl(key: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: qk.preview(key ?? ""),
    queryFn: () => getPreviewUrl(key as string),
    enabled: enabled && !!key,
    staleTime: 60_000,
  });
}

// Core details (checksums, image size) for an already-stored file. The server
// recomputes them on demand (a full object download), so they are only fetched
// when `enabled` — the preview dialog is open AND the user expands details.
export function useFileDetail(key: string | undefined, enabled: boolean) {
  return useQuery<FileMetadataDetail, ApiError>({
    queryKey: qk.detail(key ?? ""),
    queryFn: () => getFileDetail(key as string),
    enabled: enabled && !!key,
    staleTime: 60_000,
  });
}

// Health poll for the top-of-app B2 banner. `retry: false` keeps a down API
// silent (the per-component ErrorState covers that); the banner only reacts to
// an up API reporting b2_connected: false. Polls every 30s and on focus.
export function useHealth() {
  return useQuery<Health>({
    queryKey: qk.health(),
    queryFn: getHealth,
    refetchInterval: 30_000,
    staleTime: 15_000,
    retry: false,
  });
}

/**
 * Drop a deleted object from every cached file list, plus its own cached
 * preview/detail entries, so the row disappears with the success toast instead
 * of after a full re-list. Exported for tests.
 */
export function dropDeletedFileFromCache(qc: QueryClient, fileKey: string) {
  qc.setQueriesData<FileMetadata[]>(
    // Partial key: matches qk.files(prefix, limit) for every prefix/limit.
    { queryKey: [...qk.all, "files"] },
    (previous) =>
      previous ? previous.filter((file) => file.key !== fileKey) : previous,
  );
  qc.removeQueries({ queryKey: qk.preview(fileKey) });
  qc.removeQueries({ queryKey: qk.detail(fileKey) });
}

/**
 * Fetch a download URL for one file. A mutation, not a query: it bumps the
 * download counter server-side and must never be cached or replayed.
 */
export function useDownloadUrl() {
  const qc = useQueryClient();
  return useMutation<FileUrlResponse, ApiError, FileMetadata>({
    mutationFn: (file) => getDownloadUrl(file.key),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.stats() }),
  });
}

export function useDeleteFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fileKey: string) => deleteFile(fileKey),
    onSuccess: (_data, fileKey) => {
      dropDeletedFileFromCache(qc, fileKey);
      qc.invalidateQueries({ queryKey: qk.all });
    },
  });
}

// ---- Tenants and adapters ----

export function useTenants() {
  return useQuery({ queryKey: qk.tenants(), queryFn: getTenants });
}

export function useAdapters(tenantId: string | undefined) {
  return useQuery({
    queryKey: [...qk.adapters(), tenantId ?? ""],
    queryFn: () => getAdapters(tenantId as string),
    enabled: !!tenantId,
  });
}

export function useAdapter(tenantId: string, adapter: string) {
  return useQuery<AdapterDetail, ApiError>({
    queryKey: [...qk.adapter(), tenantId, adapter],
    queryFn: () => getAdapter(tenantId, adapter),
    enabled: !!tenantId && !!adapter,
    retry: (count, err) => !err.isNotFound && count < 2,
  });
}

export function useTenantManifest(tenantId: string, { enabled = true }: QueryGate = {}) {
  return useQuery({
    queryKey: [...qk.tenantManifest(), tenantId],
    queryFn: () => getTenantManifest(tenantId),
    enabled: enabled && !!tenantId,
  });
}

/** Every registry write changes tenants, adapters and manifests: refresh them all. */
function invalidateRegistry(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: qk.tenants() });
  qc.invalidateQueries({ queryKey: qk.library() });
  qc.invalidateQueries({ queryKey: [...qk.all, "files"] });
}

export function usePublishAdapter() {
  const qc = useQueryClient();
  return useMutation<AdapterDetail, ApiError, PublishAdapterInput>({
    mutationFn: publishAdapter,
    onSuccess: () => invalidateRegistry(qc),
  });
}

export function usePublishFixtures() {
  const qc = useQueryClient();
  return useMutation<AdapterDetail[], ApiError, void>({
    mutationFn: () => publishFixtures(),
    onSuccess: () => invalidateRegistry(qc),
  });
}

export function useUpdateAdapter(tenantId: string, adapter: string) {
  const qc = useQueryClient();
  return useMutation<AdapterDetail, ApiError, AdapterUpdate>({
    mutationFn: (patch) => updateAdapter(tenantId, adapter, patch),
    onSuccess: (detail) => {
      qc.setQueryData([...qk.adapter(), tenantId, adapter], detail);
      invalidateRegistry(qc);
    },
  });
}

export function useDeleteAdapter(tenantId: string, adapter: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (confirm: string) => deleteAdapter(tenantId, adapter, confirm),
    onSuccess: () => {
      qc.removeQueries({ queryKey: [...qk.adapter(), tenantId, adapter] });
      invalidateRegistry(qc);
    },
  });
}

export function useDeleteAdapterVersion(tenantId: string, adapter: string) {
  const qc = useQueryClient();
  return useMutation<unknown, ApiError, string>({
    mutationFn: (version) => deleteAdapterVersion(tenantId, adapter, version),
    onSuccess: () => invalidateRegistry(qc),
  });
}

export function useVerifyAdapterVersion(tenantId: string, adapter: string) {
  return useMutation({
    mutationFn: (version: string) => verifyAdapterVersion(tenantId, adapter, version),
  });
}

// ---- Generation, runs and jobs ----

function invalidateJobs(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: qk.jobs() });
  qc.invalidateQueries({ queryKey: qk.runs() });
}

export function useCreateGeneration() {
  const qc = useQueryClient();
  return useMutation<Job, ApiError, { tenantId: string; body: GenerationRequest }>({
    mutationFn: ({ tenantId, body }) => createGeneration(tenantId, body),
    onSuccess: () => invalidateJobs(qc),
  });
}

export function useCompareAdapters() {
  const qc = useQueryClient();
  return useMutation<RunDetail, ApiError, CompareRequest>({
    mutationFn: compareAdapters,
    onSuccess: () => invalidateJobs(qc),
  });
}

/** Jobs list; polls while any listed job is still active. */
export function useJobs(tenantId?: string, state?: string) {
  return useQuery({
    queryKey: qk.jobs(tenantId, state),
    queryFn: () => getJobs(tenantId, state),
    refetchInterval: (q) =>
      q.state.data?.some((j) => !isTerminal(j.state)) ? ACTIVE_POLL_MS : 15_000,
  });
}

/** One job; polls until it reaches a terminal state. */
export function useJob(jobId: string | undefined) {
  return useQuery({
    queryKey: [...qk.job(), jobId ?? ""],
    queryFn: () => getJob(jobId as string),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data && isTerminal(q.state.data.state) ? false : ACTIVE_POLL_MS),
  });
}

/** Presigned URL for a succeeded job's image (cached briefly; URLs expire). */
export function useJobOutput(jobId: string, enabled: boolean) {
  return useQuery({
    queryKey: [...qk.jobOutput(), jobId],
    queryFn: () => getJobOutput(jobId),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useRuns() {
  return useQuery({
    queryKey: qk.runs(),
    queryFn: getRuns,
    refetchInterval: (q) =>
      q.state.data?.some((r) => r.state === "active") ? ACTIVE_POLL_MS : 15_000,
  });
}

/** One run; polls while any of its jobs is active. */
export function useRun(runId: string) {
  return useQuery<RunDetail, ApiError>({
    queryKey: [...qk.run(), runId],
    queryFn: () => getRun(runId),
    refetchInterval: (q) =>
      q.state.data?.jobs.some((j) => !isTerminal(j.state)) ? ACTIVE_POLL_MS : false,
  });
}

/** The run's adapters.json; 404 until the run's last job ends, so no retry. */
export function useRunReport(runId: string, enabled: boolean) {
  return useQuery<AdapterReport, ApiError>({
    queryKey: [...qk.runReport(), runId],
    queryFn: () => getRunReport(runId),
    enabled,
    retry: false,
  });
}

export function useWorkers() {
  return useQuery({ queryKey: qk.workers(), queryFn: getWorkers, refetchInterval: 10_000 });
}

export function useLibrary(tenantId?: string, kind?: string) {
  return useQuery({
    queryKey: qk.library(tenantId, kind),
    queryFn: () => getLibrary(tenantId, kind),
  });
}

export function useServerConfig() {
  return useQuery({ queryKey: qk.serverConfig(), queryFn: getServerConfig, staleTime: 60_000 });
}
