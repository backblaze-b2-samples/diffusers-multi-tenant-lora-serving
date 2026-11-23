"use client";

import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { JobStateBadge } from "@/components/jobs/job-state-badge";
import { cacheLabel } from "@/lib/job-state";
import { useJobs } from "@/lib/queries";

export function RecentJobsTable() {
  const { data: jobs = [] } = useJobs();
  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Recent jobs</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {jobs.length === 0 ? (
          <p className="p-5 text-sm text-muted-foreground">No jobs yet. Start one from Generate.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tenant</TableHead>
                <TableHead>Adapter</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Worker</TableHead>
                <TableHead>Cache</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.slice(0, 8).map((j) => (
                <TableRow key={j.job_id}>
                  <TableCell className="font-mono text-xs">{j.tenant_id}</TableCell>
                  <TableCell className="text-xs">
                    <Link href={`/runs/${j.run_id}`} className="hover:underline">
                      {j.adapter ? `${j.adapter}@${j.version}` : "base model"}
                    </Link>
                  </TableCell>
                  <TableCell><JobStateBadge state={j.state} /></TableCell>
                  <TableCell className="text-xs">{j.worker_id ?? "-"}{j.attempt > 1 ? ` (attempt ${j.attempt})` : ""}</TableCell>
                  <TableCell className="text-xs">{cacheLabel(j.cache)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
