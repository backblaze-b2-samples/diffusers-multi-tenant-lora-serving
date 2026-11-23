#!/usr/bin/env node
// `pnpm selftest`: the end-to-end LoRA serving check against real B2.
//
// Runs services/api/live_tests/test_selftest_lora_serving.py, which starts the
// API and two workers itself, writes only under selftest/<run-id>/ in the
// bucket, deletes exactly what it wrote, and leaves evidence (evidence.json and
// the output PNGs) in .local/selftest/<run-id>/. Needs real B2 credentials,
// both venvs (`pnpm run setup`) and room for two SDXL pipelines on the GPU.
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const API_DIR = resolve(REPO_ROOT, "services/api");
const result = spawnSync(
  resolve(API_DIR, ".venv/bin/python"),
  [
    "-m",
    "pytest",
    "live_tests/test_selftest_lora_serving.py",
    "-m",
    "selftest",
    "-s",
    "-p",
    "no:cacheprovider",
  ],
  { cwd: API_DIR, stdio: "inherit", env: { ...process.env, RUN_SELFTEST: "1" } },
);
process.exit(result.status ?? 1);
