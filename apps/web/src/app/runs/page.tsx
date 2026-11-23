import { RunsTable } from "@/components/runs/runs-table";

export default function RunsPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Runs</h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-2xl">
          Jobs grouped by run. When a run&apos;s last job ends, the dispatcher writes
          <code className="mx-1 text-xs">reports/&lt;run-id&gt;/adapters.json</code>
          to B2 with per-job fetch, load, generate and unload times.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <RunsTable />
      </div>
    </div>
  );
}
