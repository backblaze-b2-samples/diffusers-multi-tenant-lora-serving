"use client";

import { Activity, Cpu, Database, Layers, Users } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useJobs, useTenants, useWorkers } from "@/lib/queries";
import { cacheHitRate } from "@/lib/report-chart";

/** Tenants, adapters, jobs by state, workers online and the cache hit rate. */
export function StatsCards() {
  const tenants = useTenants();
  const jobs = useJobs();
  const workers = useWorkers();
  if (tenants.error) {
    return (
      <Card>
        <CardContent className="p-0">
          <ErrorState error={tenants.error} onRetry={() => tenants.refetch()} />
        </CardContent>
      </Card>
    );
  }
  const t = tenants.data ?? [];
  const j = jobs.data ?? [];
  const count = (s: string) => j.filter((x) => x.state === s).length;
  const rate = cacheHitRate(j);
  const cards = [
    { title: "Tenants", value: String(t.length), hint: `${t.reduce((n, x) => n + x.adapter_count, 0)} adapters`, icon: Users },
    { title: "Adapter versions", value: String(t.reduce((n, x) => n + x.version_count, 0)), hint: "in B2", icon: Layers },
    { title: "Jobs", value: `${count("succeeded")} ok`, hint: `${count("queued")} queued · ${count("running")} running · ${count("failed")} failed`, icon: Activity },
    { title: "Workers online", value: String((workers.data ?? []).filter((w) => w.online).length), hint: `${(workers.data ?? []).length} registered`, icon: Cpu },
    { title: "Cache hit rate", value: rate === null ? "—" : `${Math.round(rate * 100)}%`, hint: "adapter jobs served from a worker's cache", icon: Database },
  ];
  const loading = tenants.isLoading || jobs.isLoading;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {cards.map((c, i) => (
        <Card key={c.title} className={`animate-fade-in-up stagger-${Math.min(i + 1, 5)}`}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 pt-4 px-5">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{c.title}</CardTitle>
            <c.icon className="h-4 w-4 text-muted-foreground" aria-hidden />
          </CardHeader>
          <CardContent className="px-5 pb-4">
            {loading ? <Skeleton className="h-7 w-16" /> : <div className="text-2xl font-semibold tabular-nums">{c.value}</div>}
            <p className="mt-1 text-xs text-muted-foreground">{c.hint}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
