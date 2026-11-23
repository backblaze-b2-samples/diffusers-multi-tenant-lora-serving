"use client";

import Link from "next/link";
import { CheckCircle2, Circle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useTenants, useWorkers } from "@/lib/queries";

/**
 * First-run guidance: what has to happen before Generate can do anything.
 * Hidden once adapters are published and a worker is online.
 */
export function GettingStarted() {
  const tenants = useTenants();
  const workers = useWorkers();
  if (tenants.isLoading || workers.isLoading) return null;
  const hasAdapters = (tenants.data ?? []).some((t) => t.adapter_count > 0);
  const hasWorker = (workers.data ?? []).some((w) => w.online);
  if (hasAdapters && hasWorker) return null;

  const steps = [
    {
      done: hasAdapters,
      body: (
        <>
          Publish adapters on the{" "}
          <Link href="/adapters" className="font-medium underline underline-offset-4">
            Adapters
          </Link>{" "}
          page (the demo set or your own .safetensors LoRA).
        </>
      ),
    },
    {
      done: hasWorker,
      body: (
        <>
          Start a GPU worker in a terminal at the repo root (a separate process, not started by this
          app): <code className="font-mono text-xs">pnpm worker</code>, or{" "}
          <code className="font-mono text-xs">pnpm dev:workers</code> for two.
        </>
      ),
    },
    {
      done: false,
      body: (
        <>
          Pick a tenant and adapter on{" "}
          <Link href="/generate" className="font-medium underline underline-offset-4">
            Generate
          </Link>
          .
        </>
      ),
    },
  ];

  return (
    <Card className="animate-fade-in">
      <CardHeader className="pb-2 pt-4 px-5">
        <CardTitle className="card-title">Get started</CardTitle>
      </CardHeader>
      <CardContent className="px-5 pb-4">
        <ol className="space-y-2 text-sm">
          {steps.map((s, i) => (
            <li key={i} className="flex items-start gap-2">
              {s.done ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-label="Done" />
              ) : (
                <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-label="To do" />
              )}
              <span className={s.done ? "text-muted-foreground line-through" : undefined}>{s.body}</span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
