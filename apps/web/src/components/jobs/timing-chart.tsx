"use client";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { BarChart3 } from "lucide-react";

import { type ChartConfig, ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { EmptyState } from "@/components/ui/empty-state";
import type { TimingRow } from "@/lib/report-chart";

const chartConfig = {
  fetch: { label: "Fetch", color: "var(--chart-3)" },
  load: { label: "Load", color: "var(--chart-2)" },
  generate: { label: "Generate", color: "var(--chart-1)" },
  unload: { label: "Unload", color: "var(--chart-4)" },
} satisfies ChartConfig;

/** Stacked fetch / load / generate / unload time (ms) per job. */
export function TimingChart({ rows }: { rows: TimingRow[] }) {
  if (rows.length === 0) {
    return <EmptyState icon={BarChart3} title="No finished jobs yet" description="Timings appear when a job succeeds." />;
  }
  return (
    <ChartContainer config={chartConfig} className="h-[260px] w-full">
      <BarChart data={rows} margin={{ left: 4, right: 4 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={10} interval={0} angle={-20} textAnchor="end" height={50} />
        <YAxis tickLine={false} axisLine={false} fontSize={10} width={48} unit=" ms" />
        <ChartTooltip content={<ChartTooltipContent />} />
        <ChartLegend content={<ChartLegendContent />} />
        <Bar dataKey="fetch" stackId="t" fill="var(--color-fetch)" />
        <Bar dataKey="load" stackId="t" fill="var(--color-load)" />
        <Bar dataKey="generate" stackId="t" fill="var(--color-generate)" />
        <Bar dataKey="unload" stackId="t" fill="var(--color-unload)" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ChartContainer>
  );
}
