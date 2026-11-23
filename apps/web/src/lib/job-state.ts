import type { Job } from "@diffusers-multi-tenant-lora-serving/shared";

export type JobState = Job["state"];

export function isTerminal(state: JobState): boolean {
  return state === "succeeded" || state === "failed";
}

export type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

/** Badge styling and label for a job state (one mapping for every screen). */
export function jobStateBadge(state: JobState): { label: string; variant: BadgeVariant } {
  switch (state) {
    case "queued":
      return { label: "Queued", variant: "outline" };
    case "running":
      return { label: "Running", variant: "secondary" };
    case "succeeded":
      return { label: "Succeeded", variant: "default" };
    default:
      return { label: "Failed", variant: "destructive" };
  }
}

/** "Adapter cache hit", "miss", or "base model" for a finished job. */
export function cacheLabel(cache: Job["cache"]): string {
  if (cache === "hit") return "cache hit";
  if (cache === "miss") return "cache miss";
  if (cache === "none") return "base model";
  return "-";
}

const PHASE_LABELS: Record<string, string> = {
  verifying: "Verifying the cached adapter's sha256",
  fetching: "Fetching the adapter from B2 (presigned GET, sha256 checked while streaming)",
  loading: "Loading the adapter",
  unloading: "Unloading the adapter",
  uploading: "Uploading the image to B2",
};

/** What a queued or running job is doing right now, for the live result card. */
export function jobProgressLabel(job: Job): string {
  if (job.state === "queued") return job.attempt > 0 ? "Re-queued, waiting for a worker" : "Waiting for a worker";
  const where = job.worker_id ? ` on ${job.worker_id}` : "";
  const step = `step ${job.step ?? 0} / ${job.steps}`;
  if (!job.phase || job.phase === "generating") return `Generating, ${step}${where}`;
  return `${PHASE_LABELS[job.phase] ?? job.phase}${where}`;
}

/** The warning shown when the claiming worker has stopped heartbeating, else null. */
export function staleWorkerNotice(job: Job, now: number = Date.now()): string | null {
  if (job.state !== "running" || !job.heartbeat_stale) return null;
  const left = job.lease_expires_at ? Math.round((Date.parse(job.lease_expires_at) - now) / 1000) : null;
  const when = left !== null && left > 0 ? ` in about ${left} s` : "";
  return `Worker ${job.worker_id ?? ""} stopped responding. Its lease expires${when}, then the job is retried on another worker with the same seed.`;
}
