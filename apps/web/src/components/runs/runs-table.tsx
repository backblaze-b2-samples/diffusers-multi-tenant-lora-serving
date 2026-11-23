"use client";

import Link from "next/link";
import { ListChecks } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useRuns } from "@/lib/queries";

export function RunsTable() {
  const { data: runs = [], isLoading, error, refetch } = useRuns();
  return (
    <Card>
      <CardContent className="p-0">
        {error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : isLoading ? (
          <Skeleton className="m-5 h-24" />
        ) : runs.length === 0 ? (
          <EmptyState icon={ListChecks} title="No runs yet" description="Every generation or comparison starts a run." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Jobs</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Report</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((r) => (
                <TableRow key={r.run_id}>
                  <TableCell className="font-mono text-xs">
                    <Link href={`/runs/${r.run_id}`} className="hover:underline">{r.run_id}</Link>
                  </TableCell>
                  <TableCell className="text-xs tabular-nums">{r.created_at}</TableCell>
                  <TableCell className="text-right tabular-nums">{r.job_count}</TableCell>
                  <TableCell>
                    <Badge variant={r.state === "active" ? "secondary" : "outline"}>{r.state}</Badge>
                  </TableCell>
                  <TableCell className="font-mono text-[11px] text-muted-foreground">
                    {r.report_key ? "adapters.json" : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
