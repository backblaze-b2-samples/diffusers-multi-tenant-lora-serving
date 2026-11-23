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
    case "failed":
      return { label: "Failed", variant: "destructive" };
  }
}

/** "Adapter cache hit", "miss", or "base model" for a finished job. */
export function cacheLabel(cache: Job["cache"]): string {
  if (cache === "hit") return "cache hit";
  if (cache === "miss") return "cache miss";
  if (cache === "none") return "base model";
  return "—";
}
