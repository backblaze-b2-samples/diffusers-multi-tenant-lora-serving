import { describe, expect, it } from "vitest";

import { cacheLabel, isTerminal, jobStateBadge } from "@/lib/job-state";

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
    expect(cacheLabel(null)).toBe("—");
  });
});
