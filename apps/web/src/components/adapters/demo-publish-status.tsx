"use client";

import { AlertTriangle, Loader2 } from "lucide-react";
import type { FixturePublishStatus } from "@diffusers-multi-tenant-lora-serving/shared";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { humanizeBytes } from "@/lib/utils";

/**
 * The background demo publish job, read from the server, so it survives a
 * reload: a spinner, the current step and determinate byte progress while it
 * runs, and a persistent error with a retry once it fails.
 */
export function DemoPublishStatus({
  status,
  onRetry,
  retrying,
}: {
  status: FixturePublishStatus | undefined;
  onRetry: () => void;
  retrying: boolean;
}) {
  if (status?.state === "running") {
    const pct = status.bytes_total ? Math.round((status.bytes_done / status.bytes_total) * 100) : 0;
    return (
      <div role="status" aria-live="polite" className="space-y-2 rounded-md border border-border p-4">
        <p className="flex items-center gap-2 text-sm font-medium">
          <Loader2 aria-hidden="true" className="h-3.5 w-3.5 animate-spin" />
          Publishing demo adapters: {status.stage}
        </p>
        <Progress value={pct} aria-label="Demo publish progress" />
        <p className="text-xs text-muted-foreground tabular-nums">
          {pct}% · {humanizeBytes(status.bytes_done)} of {humanizeBytes(status.bytes_total)} ·{" "}
          {status.adapters_done} of {status.adapters_total} adapters done. This keeps running if you
          leave or reload the page.
        </p>
      </div>
    );
  }
  if (status?.state === "failed") {
    return (
      <Alert variant="destructive">
        <AlertTriangle />
        <AlertTitle>Publishing the demo adapters failed</AlertTitle>
        <AlertDescription>
          <p>{status.error ?? "The publish job stopped without a reason."}</p>
          {status.published.length > 0 && (
            <p>Already published and kept: {status.published.join(", ")}.</p>
          )}
          <Button size="sm" variant="outline" className="mt-2" onClick={onRetry} disabled={retrying}>
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }
  return null;
}
