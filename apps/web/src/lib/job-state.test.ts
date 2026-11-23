import { describe, expect, it } from "vitest";

import type { Job } from "@diffusers-multi-tenant-lora-serving/shared";

import { cacheLabel, isTerminal, jobProgressLabel, jobStateBadge, staleWorkerNotice } from "@/lib/job-state";

describe("job state", () => {
  it("treats only succeeded and failed as terminal", () => {
    expect(isTerminal("queued")).toBe(false);
    expect(isTerminal("running")).toBe(false);
    expect(isTerminal("succeeded")).toBe(true);
    expect(isTerminal("failed")).toBe(true);
  });

  it("maps every state to a badge", () => {
    expect(jobStateBadge("failed")).toEqual({ label: "Failed", variant: "destructive" });
    expect(jobStateBadge("succeeded").variant).toBe("default");
    expect(jobStateBadge("queued").variant).toBe("outline");
    expect(jobStateBadge("running").label).toBe("Running");
  });

  it("labels cache results", () => {
    expect(cacheLabel("hit")).toBe("cache hit");
    expect(cacheLabel("none")).toBe("base model");
    expect(cacheLabel(null)).toBe("-");
  });
});

describe("live job labels", () => {
  const base = {
    state: "running", attempt: 1, worker_id: "w1", step: 7, steps: 25, phase: null,
    heartbeat_stale: false, lease_expires_at: null,
  } as unknown as Job;

  it("names the worker's current phase", () => {
    expect(jobProgressLabel({ ...base, phase: "fetching" })).toMatch(/^Fetching the adapter from B2.*on w1$/);
    expect(jobProgressLabel({ ...base, phase: "generating" })).toBe("Generating, step 7 / 25 on w1");
    expect(jobProgressLabel({ ...base, state: "queued", attempt: 0 })).toBe("Waiting for a worker");
    expect(jobProgressLabel({ ...base, state: "queued", attempt: 1 })).toBe("Re-queued, waiting for a worker");
  });

  it("warns only when a running job's worker went silent", () => {
    expect(staleWorkerNotice(base)).toBeNull();
    const stale = { ...base, heartbeat_stale: true, lease_expires_at: "2026-01-01T00:00:20Z" };
    expect(staleWorkerNotice(stale, Date.parse("2026-01-01T00:00:00Z"))).toMatch(
      /^Worker w1 stopped responding\. Its lease expires in about 20 s/,
    );
  });
});
