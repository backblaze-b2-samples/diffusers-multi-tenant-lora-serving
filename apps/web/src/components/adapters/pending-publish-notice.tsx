"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Loader2, X } from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  clearPendingPublish,
  pendingPublishLabel,
  pendingPublishStatus,
  readPendingPublish,
  type PendingPublish,
} from "@/lib/pending-publish";
import { usePendingAdapter, useRefreshRegistry } from "@/lib/queries";

/**
 * A form publish started before this page loaded (a reload or a navigation
 * mid-publish): "Publishing…" until the version lands, then a toast; or a
 * notice that the upload never reached the API and must be sent again.
 */
export function PendingPublishNotice() {
  const [pending, setPending] = useState<PendingPublish>();
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time read of sessionStorage on mount
    setPending(readPendingPublish());
  }, []);
  const [done, setDone] = useState(false);
  const { data: detail, isFetched } = usePendingAdapter(pending?.tenant_id ?? "", pending?.adapter ?? "", !pending || done);
  const refreshRegistry = useRefreshRegistry();
  // Decide only after the first answer, so a version that already landed wins.
  const status = pending && isFetched ? pendingPublishStatus(pending, detail) : undefined;

  useEffect(() => {
    if (!pending || done) return;
    if (status === "published") {
      toast.success(`Published ${pendingPublishLabel(pending)}`, {
        description: "Weight, version manifest, then tenant manifest written to B2.",
      });
      refreshRegistry();
    }
    if (status && status !== "waiting") {
      clearPendingPublish();
      // eslint-disable-next-line react-hooks/set-state-in-effect -- stop polling once settled
      setDone(true);
    }
  }, [pending, done, status, refreshRegistry]);

  if (!pending || !status || status === "published") return null;
  const dismiss = () => setPending(undefined);
  if (status === "waiting") {
    return (
      <div role="status" aria-live="polite" className="flex items-center gap-2 rounded-md border border-border p-4 text-sm">
        <Loader2 aria-hidden="true" className="h-3.5 w-3.5 shrink-0 animate-spin" />
        <span>
          Publishing <code className="font-mono">{pendingPublishLabel(pending)}</code>. The API keeps
          writing it to B2 after a reload; it appears in the table when the tenant manifest is written.
        </span>
      </div>
    );
  }
  return (
    <Alert variant="destructive">
      <AlertTriangle />
      <AlertTitle>
        {status === "interrupted" ? "Upload interrupted" : "Publish did not finish"}
      </AlertTitle>
      <AlertDescription>
        <p>
          {status === "interrupted"
            ? `The page was left before ${pendingPublishLabel(pending)} finished uploading to the API, so nothing was written to B2. Publish it again.`
            : `${pendingPublishLabel(pending)} did not appear within 10 minutes. Check the API logs, then publish it again.`}
        </p>
        <Button size="sm" variant="outline" className="mt-2" onClick={dismiss}>
          <X className="h-3.5 w-3.5" /> Dismiss
        </Button>
      </AlertDescription>
    </Alert>
  );
}
