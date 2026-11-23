import Link from "next/link";
import { Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GettingStarted } from "@/components/dashboard/getting-started";
import { RecentJobsTable } from "@/components/dashboard/recent-jobs-table";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { TimingCard } from "@/components/dashboard/timing-card";

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1.5 max-w-2xl">
            Tenant adapters in Backblaze B2, served per request by stateless GPU workers on one
            shared base model.
          </p>
        </div>
        <Button asChild size="sm" className="h-8">
          <Link href="/generate">
            <Wand2 className="h-3.5 w-3.5" />
            Generate
          </Link>
        </Button>
      </div>
      <GettingStarted />
      <StatsCards />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="animate-fade-in-up stagger-3">
          <TimingCard />
        </div>
        <div className="animate-fade-in-up stagger-4">
          <RecentJobsTable />
        </div>
      </div>
    </div>
  );
}
