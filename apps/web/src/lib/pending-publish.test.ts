import { afterEach, describe, expect, it, vi } from "vitest";

import {
  clearPendingPublish,
  PENDING_PUBLISH_TTL_MS,
  pendingPublishLabel,
  pendingPublishStatus,
  readPendingPublish,
  savePendingPublish,
  type PendingPublish,
} from "@/lib/pending-publish";

const base: PendingPublish = {
  tenant_id: "acme",
  adapter: "pixel-art",
  version: "v2",
  stage: "server",
  started_at: 1_000,
};
const withVersions = (...versions: string[]) => ({ versions: versions.map((version) => ({ version })) }) as never;

describe("pending publish", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("round-trips through sessionStorage and clears", () => {
    const store = new Map<string, string>();
    vi.stubGlobal("window", {
      sessionStorage: {
        getItem: (k: string) => store.get(k) ?? null,
        setItem: (k: string, v: string) => void store.set(k, v),
        removeItem: (k: string) => void store.delete(k),
      },
    });
    savePendingPublish(base);
    expect(readPendingPublish()).toEqual(base);
    clearPendingPublish();
    expect(readPendingPublish()).toBeUndefined();
  });

  it("is a no-op without a window", () => {
    expect(() => savePendingPublish(base)).not.toThrow();
    expect(readPendingPublish()).toBeUndefined();
  });

  it("reports published once the version is listed", () => {
    expect(pendingPublishStatus(base, withVersions("v1", "v2"), 2_000)).toBe("published");
    expect(pendingPublishStatus({ ...base, stage: "uploading" }, withVersions("v2"), 2_000)).toBe("published");
  });

  it("reports an upload that never reached the API as interrupted", () => {
    expect(pendingPublishStatus({ ...base, stage: "uploading" }, undefined, 2_000)).toBe("interrupted");
  });

  it("waits for a server-side publish, then expires", () => {
    expect(pendingPublishStatus(base, withVersions("v1"), 2_000)).toBe("waiting");
    expect(pendingPublishStatus(base, undefined, base.started_at + PENDING_PUBLISH_TTL_MS + 1)).toBe("expired");
  });

  it("labels the publish as tenant/adapter@version", () => {
    expect(pendingPublishLabel(base)).toBe("acme/pixel-art@v2");
  });
});
