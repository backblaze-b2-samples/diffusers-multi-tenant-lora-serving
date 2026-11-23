import type { AdapterReport, Job } from "@diffusers-multi-tenant-lora-serving/shared";

export interface TimingRow {
  label: string;
  fetch: number;
  load: number;
  generate: number;
  unload: number;
}

function label(adapter: string | null, version: string | null, jobId: string): string {
  const base = adapter ? `${adapter}${version ? `@${version}` : ""}` : "base";
  return `${base} · ${jobId.slice(-4)}`;
}

/** Stacked-bar rows (ms) for every succeeded job in a run report. */
export function reportTimingRows(report: AdapterReport): TimingRow[] {
  return report.jobs
    .filter((j) => j.state === "succeeded")
    .map((j) => ({
      label: label(j.adapter, j.version, j.job_id),
      fetch: j.fetch_ms,
      load: j.load_ms,
      generate: j.generate_ms,
      unload: j.unload_ms,
    }));
}

/** Same rows from live jobs (the dashboard), newest last, at most `limit`. */
export function jobTimingRows(jobs: Job[], limit = 12): TimingRow[] {
  return jobs
    .filter((j) => j.state === "succeeded" && j.timings)
    .slice(0, limit)
    .reverse()
    .map((j) => ({
      label: label(j.adapter, j.version, j.job_id),
      fetch: j.timings!.fetch_ms,
      load: j.timings!.load_ms,
      generate: j.timings!.generate_ms,
      unload: j.timings!.unload_ms,
    }));
}

/** Share of finished adapter jobs served from a worker's local cache. */
export function cacheHitRate(jobs: Job[]): number | null {
  const served = jobs.filter((j) => j.state === "succeeded" && (j.cache === "hit" || j.cache === "miss"));
  if (served.length === 0) return null;
  return served.filter((j) => j.cache === "hit").length / served.length;
}
