"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { FileJson, Library } from "lucide-react";
import type { LibraryEntry } from "@diffusers-multi-tenant-lora-serving/shared";

import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingNotice } from "@/components/common/loading-notice";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { humanizeBytes } from "@/lib/utils";
import { previewHref } from "@/lib/preview-deep-link";
import { useLibrary, usePreviewUrl, useTenants } from "@/lib/queries";

const ALL = "__all__";

/** tenant -> adapter -> version -> objects. */
export function groupAdapters(entries: LibraryEntry[]) {
  const tree = new Map<string, Map<string, Map<string, LibraryEntry[]>>>();
  for (const e of entries) {
    if (e.kind !== "adapters" || !e.tenant_id) continue;
    const adapters = tree.get(e.tenant_id) ?? new Map();
    tree.set(e.tenant_id, adapters);
    const name = e.adapter ?? "(tenant manifest)";
    const versions = adapters.get(name) ?? new Map();
    adapters.set(name, versions);
    const v = e.version ?? "";
    versions.set(v, [...(versions.get(v) ?? []), e]);
  }
  return tree;
}

function OutputTile({ entry }: { entry: LibraryEntry }) {
  const { data } = usePreviewUrl(entry.key, true);
  return (
    <a href={previewHref(entry.key)} className="block overflow-hidden rounded-md border border-border" title={entry.key}>
      <div className="aspect-square bg-muted/40">
        {data ? (
          // eslint-disable-next-line @next/next/no-img-element -- presigned B2 URL
          <img src={data.url} alt={entry.key} className="h-full w-full object-cover" loading="lazy" />
        ) : (
          <Skeleton className="h-full w-full" />
        )}
      </div>
      <div className="truncate p-1.5 text-[11px] font-mono">{entry.tenant_id} · {entry.run_id}</div>
    </a>
  );
}

/** Asset explorer scoped to APP_PREFIX: adapters, outputs and reports. */
export function LibraryView() {
  const [tenant, setTenant] = useState(ALL);
  const { data: tenants = [] } = useTenants();
  const tid = tenant === ALL ? undefined : tenant;
  const { data: entries = [], isLoading, error, refetch } = useLibrary(tid);
  const tree = useMemo(() => groupAdapters(entries), [entries]);
  const outputs = entries.filter((e) => e.kind === "outputs");
  const reports = entries.filter((e) => e.kind === "reports");

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Library</CardTitle>
        <CardAction>
          <Select value={tenant} onValueChange={setTenant}>
            <SelectTrigger className="h-8 w-44" aria-label="Library tenant"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All tenants</SelectItem>
              {tenants.map((t) => <SelectItem key={t.tenant_id} value={t.tenant_id}>{t.tenant_id}</SelectItem>)}
            </SelectContent>
          </Select>
        </CardAction>
      </CardHeader>
      <CardContent className="p-5">
        {error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : isLoading ? (
          <div className="space-y-3">
            <LoadingNotice subject="the library" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : entries.length === 0 ? (
          <EmptyState icon={Library} title="Nothing under the app prefix yet" description="Publish adapters and generate images to fill the library." />
        ) : (
          <Tabs defaultValue="adapters">
            <TabsList>
              <TabsTrigger value="adapters">Adapters</TabsTrigger>
              <TabsTrigger value="outputs">Outputs ({outputs.length})</TabsTrigger>
              <TabsTrigger value="reports">Reports ({reports.length})</TabsTrigger>
            </TabsList>
            <TabsContent value="adapters" className="space-y-4 pt-4">
              {[...tree.entries()].map(([t, adapters]) => (
                <section key={t}>
                  <h3 className="font-mono text-sm font-semibold">{t}/</h3>
                  <ul className="ml-4 mt-1 space-y-1 text-sm">
                    {[...adapters.entries()].map(([a, versions]) => (
                      <li key={a}>
                        {a.startsWith("(") ? (
                          <span className="text-muted-foreground">{a}</span>
                        ) : (
                          <Link href={`/adapters/${t}/${a}`} className="font-mono hover:underline">{a}/</Link>
                        )}
                        <ul className="ml-4 text-xs text-muted-foreground">
                          {[...versions.entries()].flatMap(([v, objs]) =>
                            objs.map((o) => (
                              <li key={o.key} className="font-mono">
                                {v && `${v}/`}{o.key.split("/").pop()} · {humanizeBytes(o.size_bytes)}
                              </li>
                            )),
                          )}
                        </ul>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </TabsContent>
            <TabsContent value="outputs" className="pt-4">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-6">
                {outputs.slice(0, 48).map((o) => <OutputTile key={o.key} entry={o} />)}
              </div>
            </TabsContent>
            <TabsContent value="reports" className="pt-4">
              <ul className="space-y-1 text-sm">
                {reports.map((r) => (
                  <li key={r.key} className="flex items-center gap-2">
                    <FileJson className="h-3.5 w-3.5 text-muted-foreground" />
                    <Link href={`/runs/${r.run_id}`} className="font-mono hover:underline">{r.run_id}/adapters.json</Link>
                    <span className="text-xs text-muted-foreground">{humanizeBytes(r.size_bytes)}</span>
                  </li>
                ))}
              </ul>
            </TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
