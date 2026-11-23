import { describe, expect, it } from "vitest";

import type { AdapterReport, Job } from "@diffusers-multi-tenant-lora-serving/shared";
import { cacheHitRate, jobTimingRows, reportTimingRows } from "@/lib/report-chart";

const reportJob = (id: string, state: "succeeded" | "failed", adapter: string | null) => ({
  job_id: id, tenant_id: "acme", adapter, version: adapter ? "v1" : null, adapter_sha256: null,
  worker_id: "w1", attempt: 1, state, cache: adapter ? ("miss" as const) : ("none" as const),
  bytes_fetched: 0, fetch_ms: 10, load_ms: 20, generate_ms: 300, unload_ms: 5, total_ms: 340,
  seed: 1, steps: 15, width: 768, height: 768, output_key: "k", output_sha256: null, error_code: null,
});

const report: AdapterReport = {
  run_id: "run-1", created_at: "", base_model: "b", device_summary: ["mps"],
  jobs: [reportJob("job-aaaa", "succeeded", "pixel-art"), reportJob("job-bbbb", "failed", null),
         reportJob("job-cccc", "succeeded", null)],
  summary: { jobs: 3, succeeded: 2, failed: 1, cache_hits: 0, load_ms_p50: 20,
             generate_ms_p50: 300, retried_jobs: 0 },
};

function job(id: string, cache: Job["cache"], state: Job["state"] = "succeeded"): Job {
  return {
    job_id: id, run_id: "r", tenant_id: "acme", adapter: "pixel-art", version: "v1",
    adapter_sha256: null, scale: 1, state, attempt: 1, worker_id: "w1", seed: 1, steps: 15,
    width: 768, height: 768, prompt: "p", negative_prompt: null, step: null,
    timings: { fetch_ms: 1, load_ms: 2, generate_ms: 3, unload_ms: 4, total_ms: 10 },
    cache, bytes_fetched: 0, sha256_verified: true, output_key: "k", output_sha256: null,
    adapters_after_unload: [], error_code: null, error_message: null, created_at: "",
    finished_at: null, phase: null, heartbeat_stale: false, lease_expires_at: null,
  };
}

describe("report chart shaping", () => {
  it("keeps succeeded jobs and labels adapter and base rows", () => {
    const rows = reportTimingRows(report);
    expect(rows.map((r) => r.label)).toEqual(["pixel-art@v1 · aaaa", "base · cccc"]);
    expect(rows[0]).toMatchObject({ fetch: 10, load: 20, generate: 300, unload: 5 });
  });

  it("shapes live jobs oldest-first for the dashboard", () => {
    const rows = jobTimingRows([job("job-0002", "hit"), job("job-0001", "miss")]);
    expect(rows.map((r) => r.label)).toEqual(["pixel-art@v1 · 0001", "pixel-art@v1 · 0002"]);
  });

  it("computes the cache hit rate over adapter jobs only", () => {
    expect(cacheHitRate([job("a", "hit"), job("b", "miss"), job("c", "none")])).toBe(0.5);
    expect(cacheHitRate([job("a", "hit", "failed")])).toBeNull();
  });
});
