"use client";

import { Cpu } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useWorkers } from "@/lib/queries";

/**
 * Warns before submit that no GPU worker is online: a job would sit queued.
 * Workers are separate stateless processes by design, so the app does not
 * start one; it names the command instead.
 */
export function NoWorkerNotice() {
  const { data, isLoading, error } = useWorkers();
  if (isLoading || error || (data ?? []).some((w) => w.online)) return null;
  const stale = (data ?? []).length;
  return (
    <Alert>
      <Cpu />
      <AlertTitle>No worker online</AlertTitle>
      <AlertDescription>
        <p>
          Jobs you submit wait in the queue until a worker claims them. Start one in a terminal at the
          repo root: <code className="font-mono text-xs">pnpm worker</code>, or{" "}
          <code className="font-mono text-xs">pnpm dev:workers</code> for two.
          {stale > 0 && ` ${stale} worker(s) registered earlier but are not responding.`}
        </p>
      </AlertDescription>
    </Alert>
  );
}
