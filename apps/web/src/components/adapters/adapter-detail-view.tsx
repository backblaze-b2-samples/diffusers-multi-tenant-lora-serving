"use client";

import Link from "next/link";
import { ArrowLeft, PackageX } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AdapterVersions } from "@/components/adapters/adapter-versions";
import { DeleteAdapterDialog } from "@/components/adapters/delete-adapter-dialog";
import { EditAdapterSheet } from "@/components/adapters/edit-adapter-sheet";
import { GenerateForm } from "@/components/generate/generate-form";
import { JobStateBadge } from "@/components/jobs/job-state-badge";
import { cacheLabel } from "@/lib/job-state";
import { useAdapter, useJobs, useTenantManifest } from "@/lib/queries";

export function AdapterDetailView({ tenantId, adapter }: { tenantId: string; adapter: string }) {
  const { data, isLoading, error, refetch } = useAdapter(tenantId, adapter);
  const manifest = useTenantManifest(tenantId, { enabled: !!data });
  const { data: jobs = [] } = useJobs(tenantId);
  const recent = jobs.filter((j) => j.adapter === adapter).slice(0, 8);

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (error?.isNotFound) {
    return (
      <EmptyState
        icon={PackageX}
        title={`${tenantId}/${adapter} not found`}
        description="It may have been deleted, or the tenant has no adapter by that name."
        action={<Button asChild size="sm"><Link href="/adapters">Back to adapters</Link></Button>}
      />
    );
  }
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />;
  const entry = manifest.data?.adapters?.[adapter];

  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href="/adapters" className="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-3 w-3" /> Adapters
          </Link>
          <h1 className="page-title">{data.display_name}</h1>
          <p className="mt-1.5 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span className="font-mono">{tenantId}/{adapter}@{data.current_version}</span>
            <Badge variant="outline">{data.license}</Badge>
            <span>scale {data.default_scale.toFixed(1)}</span>
            {data.trigger_words.length > 0 && <span>triggers: {data.trigger_words.join(", ")}</span>}
          </p>
        </div>
        <EditAdapterSheet adapter={data} />
      </div>

      <Card>
        <CardHeader className="border-b border-border py-4 px-5">
          <CardTitle className="card-title">Generate</CardTitle>
          <CardDescription className="text-xs">As tenant {tenantId}</CardDescription>
        </CardHeader>
        <CardContent className="p-5">
          <GenerateForm tenantId={tenantId} adapter={adapter} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="border-b border-border py-4 px-5">
          <CardTitle className="card-title">Versions</CardTitle>
          <CardDescription className="text-xs">Immutable once published; verify re-reads the weight from B2</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <AdapterVersions adapter={data} />
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Manifest entry</CardTitle>
            <CardDescription className="text-xs font-mono">{data.versions.find((v) => v.is_current)?.manifest_key}</CardDescription>
          </CardHeader>
          <CardContent className="p-5">
            <pre className="max-h-80 overflow-auto rounded-md bg-muted/40 p-3 text-[11px] leading-relaxed">
              {entry ? JSON.stringify(entry, null, 2) : "Loading…"}
            </pre>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Recent jobs</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {recent.length === 0 ? (
              <p className="p-5 text-sm text-muted-foreground">No jobs for this adapter yet.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job</TableHead>
                    <TableHead>State</TableHead>
                    <TableHead>Worker</TableHead>
                    <TableHead>Cache</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recent.map((j) => (
                    <TableRow key={j.job_id}>
                      <TableCell className="font-mono text-xs">
                        <Link className="hover:underline" href={`/runs/${j.run_id}`}>{j.job_id}</Link>
                      </TableCell>
                      <TableCell><JobStateBadge state={j.state} /></TableCell>
                      <TableCell className="text-xs">{j.worker_id ?? "-"}</TableCell>
                      <TableCell className="text-xs">{cacheLabel(j.cache)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="border-destructive/40">
        <CardHeader className="border-b border-destructive/30 py-4 px-5">
          <CardTitle className="card-title text-destructive">Danger zone</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center justify-between gap-4 p-5">
          <p className="text-sm text-muted-foreground max-w-xl">
            Deleting removes the adapter from {tenantId}&apos;s manifest, then deletes every version
            under <code className="text-xs">adapters/{tenantId}/{adapter}/</code> in B2.
          </p>
          <DeleteAdapterDialog tenantId={tenantId} adapter={adapter} />
        </CardContent>
      </Card>
    </div>
  );
}
