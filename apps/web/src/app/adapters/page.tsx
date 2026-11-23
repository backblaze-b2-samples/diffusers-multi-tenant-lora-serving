import { AdaptersTable } from "@/components/adapters/adapters-table";
import { PublishAdapterDialog } from "@/components/adapters/publish-adapter-dialog";

export default function AdaptersPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Adapters</h1>
          <p className="text-sm text-muted-foreground mt-1.5 max-w-2xl">
            Each tenant&apos;s LoRA adapters, stored in B2 under that tenant&apos;s own prefix with a
            checksummed manifest. Requests resolve only through the requesting tenant&apos;s manifest.
          </p>
        </div>
        <PublishAdapterDialog />
      </div>
      <div className="animate-fade-in-up stagger-2">
        <AdaptersTable />
      </div>
    </div>
  );
}
