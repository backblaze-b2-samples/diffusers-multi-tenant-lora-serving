"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useDeleteAdapter } from "@/lib/queries";

/** Delete every version of an adapter. The user must type the adapter name. */
export function DeleteAdapterDialog({ tenantId, adapter }: { tenantId: string; adapter: string }) {
  const [confirm, setConfirm] = useState("");
  const router = useRouter();
  const del = useDeleteAdapter(tenantId, adapter);
  const onDelete = () =>
    del.mutate(confirm, {
      onSuccess: (r) => {
        toast.success(`Deleted ${adapter}`, { description: `${r.deleted_keys.length} objects removed from B2.` });
        router.push("/adapters");
      },
      onError: (e) => toast.error("Delete failed", { description: e.message }),
    });

  return (
    <AlertDialog onOpenChange={() => setConfirm("")}>
      <AlertDialogTrigger asChild>
        <Button variant="destructive" size="sm">
          <Trash2 className="h-3.5 w-3.5" />
          Delete adapter
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete {tenantId}/{adapter}?</AlertDialogTitle>
          <AlertDialogDescription>
            The adapter leaves the tenant manifest first, then every object under its own prefix
            is deleted from B2. Other adapters and tenants are untouched. This cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2">
          <Label htmlFor="confirm-delete">Type the adapter name to confirm</Label>
          <Input
            id="confirm-delete"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="off"
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <Button variant="destructive" disabled={confirm !== adapter || del.isPending} onClick={onDelete}>
            {del.isPending ? "Deleting…" : "Delete"}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
