"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { TimingChart } from "@/components/jobs/timing-chart";
import { useJobs } from "@/lib/queries";
import { jobTimingRows } from "@/lib/report-chart";

/** Load vs generate time for the latest finished jobs. */
export function TimingCard() {
  const { data: jobs = [] } = useJobs();
  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Load vs generate time</CardTitle>
        <CardDescription className="text-xs">Latest succeeded jobs, milliseconds</CardDescription>
      </CardHeader>
      <CardContent className="p-5">
        <TimingChart rows={jobTimingRows(jobs)} />
      </CardContent>
    </Card>
  );
}
