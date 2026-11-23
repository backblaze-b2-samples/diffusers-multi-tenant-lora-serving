import { AdapterDetailView } from "@/components/adapters/adapter-detail-view";

export default async function AdapterDetailPage({
  params,
}: {
  params: Promise<{ tenantId: string; adapter: string }>;
}) {
  const { tenantId, adapter } = await params;
  return <AdapterDetailView tenantId={tenantId} adapter={adapter} />;
}
