"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { JobImage } from "@/components/jobs/job-image";
import { TimingChart } from "@/components/jobs/timing-chart";
import { isTerminal } from "@/lib/job-state";
import { useRun, useRunReport } from "@/lib/queries";
import { reportTimingRows } from "@/lib/report-chart";

/** A run's outputs side by side, and its adapters.json report once written. */
export function RunDetailView({ runId }: { runId: string }) {
  const { data: run, isLoading, error, refetch } = useRun(runId);
  const done = !!run && run.jobs.every((j) => isTerminal(j.state));
  const report = useRunReport(runId, done && !!run?.report_key);

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (error || !run) return <ErrorState error={error} onRetry={() => refetch()} />;
  const summary = report.data?.summary;

  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <Link href="/runs" className="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-3 w-3" /> Runs
        </Link>
        <h1 className="page-title font-mono">{run.run_id}</h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          {run.jobs.length} job(s), created {run.created_at}. Each image is labelled with the tenant and
          adapter that produced it, so a leak between tenants would be visible here.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {run.jobs.map((j) => <JobImage key={j.job_id} job={j} />)}
      </div>
      <Card>
        <CardHeader className="border-b border-border py-4 px-5">
          <CardTitle className="card-title">Timing report</CardTitle>
          <CardDescription className="text-xs font-mono">{run.report_key ?? "written when the run's last job ends"}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 p-5">
          {summary && (
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              {[
                ["Succeeded", `${summary.succeeded} / ${summary.jobs}`],
                ["Cache hits", String(summary.cache_hits)],
                ["Load p50", `${summary.load_ms_p50} ms`],
                ["Generate p50", `${summary.generate_ms_p50} ms`],
                ["Retried jobs", String(summary.retried_jobs)],
                ["Failed", String(summary.failed)],
                ["Devices", report.data!.device_summary.join(", ") || "—"],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="text-xs text-muted-foreground">{k}</dt>
                  <dd className="font-semibold tabular-nums">{v}</dd>
                </div>
              ))}
            </dl>
          )}
          {report.data ? (
            <TimingChart rows={reportTimingRows(report.data)} />
          ) : (
            <p className="text-sm text-muted-foreground">
              {done ? "Report not written yet." : "Jobs are still running; the report appears when they finish."}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
