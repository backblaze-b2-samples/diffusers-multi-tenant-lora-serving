import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CompareForm } from "@/components/generate/compare-form";
import { GenerateForm } from "@/components/generate/generate-form";
import { NoTenantsNotice } from "@/components/generate/no-tenants-notice";
import { NoWorkerNotice } from "@/components/generate/no-worker-notice";

export default function GeneratePage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Generate</h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-2xl">
          Every request names a tenant. The dispatcher resolves the adapter through that
          tenant&apos;s manifest only, and a worker fetches just that adapter through a short-lived
          presigned URL, loads it, generates and unloads it.
        </p>
      </div>
      <NoTenantsNotice />
      <NoWorkerNotice />
      <Card className="animate-fade-in-up stagger-2">
        <CardHeader className="border-b border-border py-4 px-5">
          <CardTitle className="card-title">Generate</CardTitle>
          <CardDescription className="text-xs">One tenant, one adapter or the base model</CardDescription>
        </CardHeader>
        <CardContent className="p-5">
          <GenerateForm />
        </CardContent>
      </Card>
      <Card className="animate-fade-in-up stagger-3">
        <CardHeader className="border-b border-border py-4 px-5">
          <CardTitle className="card-title">Compare adapters</CardTitle>
          <CardDescription className="text-xs">Same prompt and seed, side by side</CardDescription>
        </CardHeader>
        <CardContent className="p-5">
          <CompareForm />
        </CardContent>
      </Card>
    </div>
  );
}
