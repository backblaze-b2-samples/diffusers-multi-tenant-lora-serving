"use client";

import { Activity, Cpu, Database, Layers, Users } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useJobs, useTenants, useWorkers } from "@/lib/queries";
import { cacheHitRate } from "@/lib/report-chart";

interface StatQuery {
  isLoading: boolean;
  error: Error | null;
  refetch: () => unknown;
}

/**
 * Tenants, adapters, jobs by state, workers online and the cache hit rate.
 * Each card follows only the query it reads, so a slow or failing B2 listing
 * (tenants) never blanks the workers or jobs cards, which come from the API's
 * own database.
 */
export function StatsCards() {
  const tenants = useTenants();
  const jobs = useJobs();
  const workers = useWorkers();
  const t = tenants.data ?? [];
  const j = jobs.data ?? [];
  const count = (s: string) => j.filter((x) => x.state === s).length;
  const rate = cacheHitRate(j);
  const w = workers.data ?? [];
  const online = w.filter((x) => x.online).length;
  const offline = w.length - online;
  const cards: { title: string; value: string; hint: string; icon: typeof Users; q: StatQuery }[] = [
    { title: "Tenants", value: String(t.length), hint: `${t.reduce((n, x) => n + x.adapter_count, 0)} adapters`, icon: Users, q: tenants },
    { title: "Adapter versions", value: String(t.reduce((n, x) => n + x.version_count, 0)), hint: "in B2", icon: Layers, q: tenants },
    { title: "Jobs", value: `${count("succeeded")} ok`, hint: `${count("queued")} queued · ${count("running")} running · ${count("failed")} failed`, icon: Activity, q: jobs },
    { title: "Workers online", value: String(online), hint: offline > 0 ? `${offline} registered earlier, not responding` : online > 0 ? "heartbeating now" : "none registered yet", icon: Cpu, q: workers },
    { title: "Cache hit rate", value: rate === null ? "-" : `${Math.round(rate * 100)}%`, hint: "adapter jobs served from a worker's cache", icon: Database, q: jobs },
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {cards.map((c, i) => (
        <Card key={c.title} className={`animate-fade-in-up stagger-${Math.min(i + 1, 5)}`}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 pt-4 px-5">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{c.title}</CardTitle>
            <c.icon className="h-4 w-4 text-muted-foreground" aria-hidden />
          </CardHeader>
          <CardContent className="px-5 pb-4">
            {c.q.error ? (
              <>
                <div className="text-2xl font-semibold text-muted-foreground">-</div>
                <p className="mt-1 text-xs text-destructive">
                  Couldn&apos;t load.{" "}
                  <button type="button" className="underline underline-offset-2" onClick={() => c.q.refetch()}>
                    Retry
                  </button>
                </p>
              </>
            ) : (
              <>
                {c.q.isLoading ? (
                  <Skeleton className="h-7 w-16" aria-label={`Loading ${c.title.toLowerCase()}`} />
                ) : (
                  <div className="text-2xl font-semibold tabular-nums">{c.value}</div>
                )}
                <p className="mt-1 text-xs text-muted-foreground">{c.q.isLoading ? "Loading…" : c.hint}</p>
              </>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
