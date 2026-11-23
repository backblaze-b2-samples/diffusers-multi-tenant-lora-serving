"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useServerConfig } from "@/lib/queries";

/** Read-only dispatcher configuration from `GET /settings/server`. */
export function ServerConfigCard() {
  const { data, isLoading, error, refetch } = useServerConfig();
  const rows: [string, string][] = data
    ? [
        ["Base model", data.base_model],
        ["App prefix", data.app_prefix || "(bucket root)"],
        ["Adapter URL lifetime", `${data.adapter_url_ttl_seconds} s`],
        ["Output URL lifetime", `${data.output_url_ttl_seconds} s`],
        ["Job lease", `${data.job_lease_seconds} s`],
        ["Workers online", String(data.workers_online)],
        ["Accepted licenses", data.license_allowlist.join(", ")],
      ]
    : [];
  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Server</CardTitle>
      </CardHeader>
      <CardContent className="p-5">
        {isLoading && <Skeleton className="h-32 w-full" />}
        {error && <ErrorState title="Couldn't load server settings" onRetry={() => refetch()} />}
        {data && (
          <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
            {rows.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted-foreground">{k}</dt>
                <dd className="font-mono text-xs break-all">{v}</dd>
              </div>
            ))}
          </dl>
        )}
        <p className="mt-4 text-xs text-muted-foreground">
          Set through environment variables on the dispatcher; see <code>.env.example</code>.
        </p>
      </CardContent>
    </Card>
  );
}
