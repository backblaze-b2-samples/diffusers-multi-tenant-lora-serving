"use client";

import { ShieldCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";
import type { AdapterDetail } from "@diffusers-multi-tenant-lora-serving/shared";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { humanizeBytes } from "@/lib/utils";
import { useDeleteAdapterVersion, useVerifyAdapterVersion } from "@/lib/queries";

/** Versions with row actions: re-verify the checksum from B2, delete one version. */
export function AdapterVersions({ adapter }: { adapter: AdapterDetail }) {
  const verify = useVerifyAdapterVersion(adapter.tenant_id, adapter.adapter);
  const del = useDeleteAdapterVersion(adapter.tenant_id, adapter.adapter);

  const onVerify = (version: string) =>
    verify.mutate(version, {
      onSuccess: (r) =>
        r.match
          ? toast.success(`${version}: sha256 matches`, { description: r.sha256_actual })
          : toast.error(`${version}: checksum mismatch`, {
              description: `expected ${r.sha256_expected.slice(0, 16)}…, got ${r.sha256_actual.slice(0, 16)}…`,
            }),
      onError: (e) => toast.error("Verify failed", { description: e.message }),
    });

  const onDelete = (version: string) =>
    del.mutate(version, {
      onSuccess: () => toast.success(`Deleted ${version}`),
      onError: (e) => toast.error("Delete failed", { description: e.message }),
    });

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Version</TableHead>
          <TableHead>sha256</TableHead>
          <TableHead className="text-right">Size</TableHead>
          <TableHead>Source</TableHead>
          <TableHead>Published</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {adapter.versions.map((v) => (
          <TableRow key={v.version}>
            <TableCell className="font-mono text-xs">
              {v.version} {v.is_current && <Badge variant="secondary" className="ml-1">current</Badge>}
            </TableCell>
            <TableCell className="font-mono text-[11px]" title={v.sha256}>
              {v.sha256.slice(0, 16)}…
            </TableCell>
            <TableCell className="text-right tabular-nums text-xs">{humanizeBytes(v.size_bytes)}</TableCell>
            <TableCell className="text-xs">
              {v.source?.type === "huggingface" ? (
                <span title={`${v.source.filename} @ ${v.source.revision ?? "main"}`}>{v.source.repo_id}</span>
              ) : (
                "upload"
              )}
            </TableCell>
            <TableCell className="text-xs tabular-nums">{v.published_at}</TableCell>
            <TableCell className="text-right">
              <div className="flex justify-end gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onVerify(v.version)}
                  disabled={verify.isPending && verify.variables === v.version}
                >
                  <ShieldCheck className="h-3.5 w-3.5" />
                  {verify.isPending && verify.variables === v.version ? "Verifying…" : "Verify checksum"}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Delete version ${v.version}`}
                  onClick={() => onDelete(v.version)}
                  disabled={(v.is_current && adapter.versions.length > 1) || del.isPending}
                  title={v.is_current && adapter.versions.length > 1 ? "Make another version current first" : undefined}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
