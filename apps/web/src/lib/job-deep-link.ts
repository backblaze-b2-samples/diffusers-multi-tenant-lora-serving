/**
 * Keeps the Generate form's active job in the URL (`?job=<id>`), so a reload
 * mid-generation resumes polling the same job instead of blanking the result.
 *
 * Reads and writes `window.location` directly rather than `useSearchParams()`,
 * for the same reason as `preview-deep-link.ts`: the page is prerendered static.
 */

export const JOB_PARAM = "job";

/** The job id in the current URL, if any. */
export function readJobIdFromUrl(): string | undefined {
  if (typeof window === "undefined") return undefined;
  return new URL(window.location.href).searchParams.get(JOB_PARAM) || undefined;
}

/** Record `jobId` in the URL without a navigation (replaces the history entry). */
export function writeJobIdToUrl(jobId: string): void {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  url.searchParams.set(JOB_PARAM, jobId);
  window.history.replaceState(null, "", `${url.pathname}${url.search}`);
}

/**
 * The URL alone does not survive sidebar navigation (the nav links carry no
 * query), so the active job is also kept in sessionStorage for this tab. The
 * form clears it once the job reaches a terminal state, so a finished job is
 * shown once on return and then forgotten.
 */
export const ACTIVE_JOB_KEY = "generate.activeJob";

function storage(): Storage | undefined {
  try {
    return typeof window === "undefined" ? undefined : window.sessionStorage;
  } catch {
    return undefined; // blocked storage (private mode, sandboxed frame)
  }
}

export function rememberActiveJob(jobId: string): void {
  try {
    storage()?.setItem(ACTIVE_JOB_KEY, jobId);
  } catch {
    /* storage full or blocked: the URL still carries the job */
  }
}

/** Forget `jobId`, but never a newer job that replaced it. */
export function forgetActiveJob(jobId: string): void {
  try {
    const s = storage();
    if (s?.getItem(ACTIVE_JOB_KEY) === jobId) s.removeItem(ACTIVE_JOB_KEY);
  } catch {
    /* ignore */
  }
}

/** The job to resume on mount: the URL wins, then this tab's stored job. */
export function readActiveJobId(): string | undefined {
  const fromUrl = readJobIdFromUrl();
  if (fromUrl) return fromUrl;
  try {
    return storage()?.getItem(ACTIVE_JOB_KEY) || undefined;
  } catch {
    return undefined;
  }
}
