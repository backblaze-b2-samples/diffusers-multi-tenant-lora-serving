/**
 * A form publish in flight, kept in sessionStorage so the Adapters page can
 * still show it after a reload. The browser's request dies with the page, but
 * once the file reached the API (or for a Hugging Face source, once the
 * request was sent) the API finishes the publish on its own; the page then
 * polls for the version and announces it when it lands.
 */

import type { AdapterDetail } from "@diffusers-multi-tenant-lora-serving/shared";

export const PENDING_PUBLISH_KEY = "adapters.pendingPublish";
/** Give up waiting for the version after this long. */
export const PENDING_PUBLISH_TTL_MS = 10 * 60_000;

export interface PendingPublish {
  tenant_id: string;
  adapter: string;
  version: string;
  /** "uploading": the file had not fully reached the API; "server": the API owns the publish. */
  stage: "uploading" | "server";
  started_at: number;
}

export type PendingPublishStatus = "interrupted" | "waiting" | "published" | "expired";

function storage(): Storage | undefined {
  try {
    return typeof window === "undefined" ? undefined : window.sessionStorage;
  } catch {
    return undefined;
  }
}

/** A new record for a publish that starts now. */
export function newPendingPublish(fields: Omit<PendingPublish, "started_at">): PendingPublish {
  return { ...fields, started_at: Date.now() };
}

export function savePendingPublish(p: PendingPublish): void {
  try {
    storage()?.setItem(PENDING_PUBLISH_KEY, JSON.stringify(p));
  } catch {
    /* blocked storage: the reload notice is a convenience only */
  }
}

export function readPendingPublish(): PendingPublish | undefined {
  try {
    const raw = storage()?.getItem(PENDING_PUBLISH_KEY);
    return raw ? (JSON.parse(raw) as PendingPublish) : undefined;
  } catch {
    return undefined;
  }
}

export function clearPendingPublish(): void {
  try {
    storage()?.removeItem(PENDING_PUBLISH_KEY);
  } catch {
    /* ignore */
  }
}

export function pendingPublishLabel(p: PendingPublish): string {
  return `${p.tenant_id}/${p.adapter}@${p.version}`;
}

/** Where a pending publish stands, given the adapter's current detail (if it exists yet). */
export function pendingPublishStatus(
  p: PendingPublish,
  detail: Pick<AdapterDetail, "versions"> | undefined,
  now: number = Date.now(),
): PendingPublishStatus {
  if (detail?.versions.some((v) => v.version === p.version)) return "published";
  if (p.stage === "uploading") return "interrupted";
  return now - p.started_at > PENDING_PUBLISH_TTL_MS ? "expired" : "waiting";
}
