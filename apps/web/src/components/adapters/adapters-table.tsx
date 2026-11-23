"use client";

import { useState } from "react";
import Link from "next/link";
import { useQueries } from "@tanstack/react-query";
import { Layers, PackageOpen } from "lucide-react";
import { toast } from "sonner";
import type { AdapterSummary } from "@diffusers-multi-tenant-lora-serving/shared";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardAction } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getAdapters } from "@/lib/api-client";
import { humanizeBytes } from "@/lib/utils";
import { qk, usePublishFixtures, useTenants } from "@/lib/queries";

const ALL = "__all__";

/** Every tenant's adapters in one table, with a tenant filter. */
export function AdaptersTable() {
  const [tenant, setTenant] = useState(ALL);
  const tenants = useTenants();
  const fixtures = usePublishFixtures();
  const ids = (tenants.data ?? []).map((t) => t.tenant_id);
  const shown = tenant === ALL ? ids : ids.filter((t) => t === tenant);
  // One query per tenant, under the same key `useAdapters` uses.
  const lists = useQueries({
    queries: shown.map((t) => ({ queryKey: [...qk.adapters(), t], queryFn: () => getAdapters(t) })),
  });
  const rows: AdapterSummary[] = lists.flatMap((q) => q.data ?? []);
  const loading = tenants.isLoading || lists.some((q) => q.isLoading);

  const publishDemo = () =>
    fixtures.mutate(undefined, {
      onSuccess: (done) =>
        toast.success(
          done.length ? `Published ${done.length} demo adapter(s)` : "Demo adapters already published",
        ),
      onError: (e) => toast.error("Publishing demo adapters failed", { description: e.message }),
    });

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Adapters</CardTitle>
        <CardAction>
          <Select value={tenant} onValueChange={setTenant}>
            <SelectTrigger className="h-8 w-44" aria-label="Filter by tenant">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All tenants</SelectItem>
              {ids.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardAction>
      </CardHeader>
      <CardContent className="p-0">
        {tenants.error ? (
          <ErrorState error={tenants.error} onRetry={() => tenants.refetch()} />
        ) : loading ? (
          <div className="space-y-2 p-5">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            icon={PackageOpen}
            title="No adapters published yet"
            description="Publish the demo set (two tenants, three SDXL LoRAs pinned on Hugging Face) or your own adapter."
            action={
              <Button size="sm" onClick={publishDemo} disabled={fixtures.isPending}>
                <Layers className="h-3.5 w-3.5" />
                {fixtures.isPending ? "Publishing (downloads ~600 MB)…" : "Publish demo adapters"}
              </Button>
            }
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tenant</TableHead>
                <TableHead>Adapter</TableHead>
                <TableHead>Current</TableHead>
                <TableHead className="text-right">Versions</TableHead>
                <TableHead className="text-right">Scale</TableHead>
                <TableHead>License</TableHead>
                <TableHead className="text-right">Size</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((a) => (
                <TableRow key={`${a.tenant_id}/${a.adapter}`}>
                  <TableCell className="font-mono text-xs">{a.tenant_id}</TableCell>
                  <TableCell>
                    <Link
                      href={`/adapters/${a.tenant_id}/${a.adapter}`}
                      className="font-medium underline-offset-4 hover:underline"
                    >
                      {a.display_name}
                    </Link>
                    <div className="font-mono text-[11px] text-muted-foreground">{a.adapter}</div>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{a.current_version}</TableCell>
                  <TableCell className="text-right tabular-nums">{a.version_count}</TableCell>
                  <TableCell className="text-right tabular-nums">{a.default_scale.toFixed(1)}</TableCell>
                  <TableCell className="text-xs">{a.license}</TableCell>
                  <TableCell className="text-right tabular-nums text-xs">{humanizeBytes(a.size_bytes)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
      {rows.length > 0 && (
        <div className="flex justify-end border-t border-border px-5 py-3">
          <Button variant="outline" size="sm" onClick={publishDemo} disabled={fixtures.isPending}>
            {fixtures.isPending ? "Publishing…" : "Publish demo adapters"}
          </Button>
        </div>
      )}
    </Card>
  );
}
