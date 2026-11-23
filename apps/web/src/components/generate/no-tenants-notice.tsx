"use client";

import Link from "next/link";
import { Info } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useTenants } from "@/lib/queries";

/** Explains an empty tenant picker: nothing can run until an adapter is published. */
export function NoTenantsNotice() {
  const { data, isLoading, error } = useTenants();
  if (isLoading || error || (data ?? []).length > 0) return null;
  return (
    <Alert>
      <Info />
      <AlertTitle>No tenants yet</AlertTitle>
      <AlertDescription>
        <p>
          A tenant exists once it has a published adapter. Publish the demo set or your own adapter on
          the{" "}
          <Link href="/adapters" className="font-medium underline underline-offset-4">
            Adapters
          </Link>{" "}
          page, then come back to generate.
        </p>
      </AlertDescription>
    </Alert>
  );
}
