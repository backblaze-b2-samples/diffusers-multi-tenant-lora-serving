"use client";

import { ImageOff, Loader2 } from "lucide-react";
import type { Job } from "@diffusers-multi-tenant-lora-serving/shared";

import { Skeleton } from "@/components/ui/skeleton";
import { JobStateBadge } from "@/components/jobs/job-state-badge";
import { cacheLabel } from "@/lib/job-state";
import { useJobOutput } from "@/lib/queries";

/** One job as a card: the generated image (presigned GET) or its progress. */
export function JobImage({ job, title }: { job: Job; title?: string }) {
  const done = job.state === "succeeded";
  const { data: output } = useJobOutput(job.job_id, done);
  const heading =
    title ?? (job.adapter ? `${job.tenant_id}/${job.adapter}@${job.version}` : `${job.tenant_id} · base model`);
  return (
    <figure className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="relative aspect-square bg-muted/40">
        {done && output ? (
          // eslint-disable-next-line @next/next/no-img-element -- presigned B2 URL, not a static asset
          <img src={output.url} alt={`Output of ${heading}`} className="h-full w-full object-cover" />
        ) : done ? (
          <Skeleton className="h-full w-full" />
        ) : job.state === "failed" ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 p-4 text-center">
            <ImageOff className="h-6 w-6 text-destructive" aria-hidden />
            <span className="font-mono text-xs text-destructive">{job.error_code}</span>
            <span className="text-xs text-muted-foreground line-clamp-3">{job.error_message}</span>
          </div>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
            {job.state === "running"
              ? `Step ${job.step ?? 0} / ${job.steps} on ${job.worker_id}`
              : "Waiting for a worker"}
          </div>
        )}
      </div>
      <figcaption className="space-y-1 border-t border-border p-3 text-xs">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate font-medium" title={heading}>
            {heading}
          </span>
          <JobStateBadge state={job.state} />
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-muted-foreground tabular-nums">
          <span>seed {job.seed}</span>
          {job.worker_id && <span>{job.worker_id}</span>}
          {job.attempt > 1 && <span>attempt {job.attempt}</span>}
          {done && <span>{cacheLabel(job.cache)}</span>}
          {job.timings && (
            <span>
              load {job.timings.load_ms} ms · gen {job.timings.generate_ms} ms
            </span>
          )}
        </div>
      </figcaption>
    </figure>
  );
}
