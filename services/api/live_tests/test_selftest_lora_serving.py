"""End-to-end self-test: real B2, real SDXL, two real workers.

    pnpm selftest

Everything lands under `selftest/<run-id>/lora-serving/` in the bucket and is
deleted again at the end (only the keys this run recorded as written, then the
run prefix is asserted empty). Evidence goes to `.local/selftest/<run-id>/`.

Asserts, in order: publish + re-read checksums; per-tenant isolation across two
workers; cross-tenant rejections that create no job; checksum failure on a
corrupted weight that leaves no cache entry; cache hits; adapter swaps on one
worker (A, B, base differ, A again equals A); a SIGKILLed worker's job finished
by the other worker with the same image and a 409 for the late attempt; and
the `adapters.json` report in B2.
"""

import json
import os
import signal
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from dotenv import load_dotenv

from live_tests.selftest_support import (
    REPO_ROOT,
    Api,
    Proc,
    base_env,
    free_port,
    mad,
    max_px,
    resign_safetensors,
    start_worker,
    worker_env,
)

pytestmark = pytest.mark.selftest

RUN_ID = "st-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
RUN_ROOT = f"selftest/{RUN_ID}/"
PREFIX = f"{RUN_ROOT}lora-serving/"
THRESH = 3 / 255

if os.getenv("RUN_SELFTEST") == "1":
    load_dotenv(REPO_ROOT / ".env")
    os.environ["APP_PREFIX"] = PREFIX


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    if os.getenv("RUN_SELFTEST") != "1":
        pytest.skip("run with `pnpm selftest` (needs real B2 credentials and a GPU)")
    from app.config import settings

    assert settings.prefix == PREFIX, "APP_PREFIX must be set before the app is imported"
    fixtures = yaml.safe_load((REPO_ROOT / "fixtures" / "adapters.yaml").read_text())
    evidence_dir = REPO_ROOT / ".local" / "selftest" / RUN_ID
    evidence_dir.mkdir(parents=True, exist_ok=True)
    tmp = tmp_path_factory.mktemp("selftest")
    port = free_port()
    api_url = f"http://127.0.0.1:{port}"
    env = base_env()
    api_env = {**env, "APP_PREFIX": PREFIX, "JOB_LEASE_SECONDS": "15",
               "JOB_HEARTBEAT_SECONDS": "1", "JOBS_DB_PATH": str(tmp / "jobs.sqlite3"),
               "WARM_LIST_CACHE_ON_STARTUP": "false", "RATE_LIMIT_PER_MINUTE": "100000",
               "RATE_LIMIT_WRITE_PER_MINUTE": "100000", "PYTHONUNBUFFERED": "1"}
    api_proc = Proc("api", [str(Path(".venv/bin/uvicorn")), "main:app", "--port", str(port),
                            "--host", "127.0.0.1"], REPO_ROOT / "services" / "api", api_env,
                    evidence_dir)
    procs = {"api": api_proc}
    rev = fixtures["base_model_revision"]
    wenv = {wid: worker_env(env, api_url, wid, tmp / f"cache-{wid}", rev) for wid in ("w1", "w2")}
    ctx = {"api": Api(api_url), "procs": procs, "wenv": wenv, "tmp": tmp,
           "evidence_dir": evidence_dir, "fixtures": fixtures, "written": set(),
           "evidence": {"run_id": RUN_ID, "prefix": PREFIX, "started_at": datetime.now(UTC).isoformat()}}
    try:
        ctx["api"].wait_healthy()
        yield ctx
    finally:
        for p in procs.values():
            p.kill(signal.SIGTERM)
        _cleanup(ctx)


def _cleanup(ctx) -> None:
    from app.repo import adapter_store

    written = sorted(ctx["written"])
    deleted = adapter_store.delete_keys(written) if written else []
    left = [o["Key"] for o in adapter_store.iter_objects(RUN_ROOT)]
    ev = ctx["evidence"]
    ev["cleanup"] = {"recorded_keys": len(written), "deleted": len(deleted), "left_under_run_prefix": left}
    ev["finished_at"] = datetime.now(UTC).isoformat()
    (ctx["evidence_dir"] / "evidence.json").write_text(json.dumps(ev, indent=2))
    assert left == [], f"objects left under {RUN_ROOT}: {left}"


def _record_adapter(ctx, detail: dict) -> None:
    for v in detail["versions"]:
        ctx["written"].update({v["weight_key"], v["manifest_key"]})
    ctx["written"].add(f"{PREFIX}adapters/{detail['tenant_id']}/manifest.json")


def _record_job(ctx, job: dict) -> None:
    ctx["written"].add(job["output_key"])


def _save(ctx, name: str, png: bytes) -> None:
    (ctx["evidence_dir"] / f"{name}.png").write_bytes(png)


def test_lora_serving_end_to_end(stack):
    from app.repo import adapter_store

    ctx, api = stack, stack["api"]
    ev = ctx["evidence"]
    run = RUN_ID.replace("st-", "run-")

    # 1. Publish the fixtures; each weight re-read from B2 hashes to its manifest.
    t = time.time()
    r = api.http.post("/fixtures/publish")
    assert r.status_code == 202, r.text
    job = r.json()
    while job["state"] == "running" and time.time() - t < 1800:
        time.sleep(5)
        job = api.http.get("/fixtures/publish").json()
    assert job["state"] == "succeeded", job
    for ref in job["published"]:
        tenant_, rest = ref.split("/", 1)
        _record_adapter(ctx, api.http.get(f"/tenants/{tenant_}/adapters/{rest.split('@')[0]}").json())
    ev["publish_seconds"] = round(time.time() - t, 1)
    manifests = {t_: api.http.get(f"/tenants/{t_}/manifest").json() for t_ in ("acme", "globex")}
    assert set(manifests["acme"]["adapters"]) == {"pixel-art", "3d-render"}
    assert set(manifests["globex"]["adapters"]) == {"papercut"}
    shas = {t_: {v["sha256"] for a in m["adapters"].values() for v in a["versions"].values()}
            for t_, m in manifests.items()}
    verified = []
    for tenant, m in manifests.items():
        for name in m["adapters"]:
            v = api.http.post(f"/tenants/{tenant}/adapters/{name}/versions/v1/verify").json()
            assert v["match"], v
            verified.append({"tenant": tenant, "adapter": name, "sha256": v["sha256_actual"],
                             "size": v["size_actual"]})
    ev["publish_verified"] = verified

    # Start both workers (no B2 credentials in their environment).
    for wid in ("w1", "w2"):
        ctx["procs"][wid] = start_worker(wid, ctx["wenv"][wid], ctx["evidence_dir"])
    api.wait_workers({"w1", "w2"})
    jobs_all: list[dict] = []

    def submit(tenant, adapter, **kw):
        resp = api.generate(tenant, adapter, run_id=run, **kw)
        assert resp.status_code == 202, resp.text
        job = resp.json()
        _record_job(ctx, job)
        return job

    def finish(job):
        done = api.wait_job(job["job_id"])
        jobs_all.append(done)
        return done

    # 2. Isolation: one request per tenant submitted together.
    a = submit("acme", "pixel-art")
    g = submit("globex", "papercut")
    a, g = finish(a), finish(g)
    for j, tenant in ((a, "acme"), (g, "globex")):
        assert j["state"] == "succeeded", j
        assert j["adapter_sha256"] in shas[tenant]
        assert j["adapter_sha256"] not in shas["globex" if tenant == "acme" else "acme"]
        assert j["adapters_after_unload"] == []
    assert {a["worker_id"], g["worker_id"]} == {"w1", "w2"}
    _save(ctx, "isolation-acme-pixel-art", api.output_png(a["job_id"]))
    _save(ctx, "isolation-globex-papercut", api.output_png(g["job_id"]))
    ev["isolation"] = {"acme": {"worker": a["worker_id"], "sha256": a["adapter_sha256"]},
                       "globex": {"worker": g["worker_id"], "sha256": g["adapter_sha256"]}}

    # 3. Cross-tenant rejections create no job.
    n_jobs = len(api.http.get("/jobs").json())
    r403 = api.generate("acme", "globex/papercut")
    r404 = api.generate("acme", "papercut")
    assert (r403.status_code, r403.json()["code"]) == (403, "cross_tenant_adapter")
    assert (r404.status_code, r404.json()["code"]) == (404, "adapter_not_found")
    key = f"{PREFIX}adapters/acme/manifest.json"
    original, _ = adapter_store.get_json(key)
    tampered = json.loads(json.dumps(original))
    stolen = manifests["globex"]["adapters"]["papercut"]["versions"]["v1"]
    tampered["adapters"]["pixel-art"]["versions"]["v1"].update(
        weight_key=stolen["weight_key"], manifest_key=stolen["manifest_key"])
    adapter_store.put_json(key, tampered)
    time.sleep(11)  # the dispatcher revalidates its cached manifest after 10 s
    r_tamper = api.generate("acme", "pixel-art")
    adapter_store.put_json(key, original)
    assert (r_tamper.status_code, r_tamper.json()["code"]) == (403, "manifest_tenant_mismatch")
    assert len(api.http.get("/jobs").json()) == n_jobs
    time.sleep(11)
    ev["rejections"] = {"qualified_cross_tenant": 403, "unqualified_other_name": 404,
                        "tampered_manifest": 403, "jobs_created": 0}

    # 4. Corrupted weight: manifest sha256 no longer matches the object.
    render_path = _fixture_file(ctx, "3d-render")
    data = render_path.read_bytes()
    resigned = resign_safetensors(data, RUN_ID)
    pub = api.http.post("/tenants/acme/adapters", data={
        "adapter": "corrupt-check", "version": "v1", "license": "apache-2.0", "source": "upload"},
        files={"file": ("corrupt-check.safetensors", resigned, "application/octet-stream")},
        timeout=600)
    assert pub.status_code == 201, pub.text
    _record_adapter(ctx, pub.json())
    bad_sha = pub.json()["versions"][0]["sha256"]
    adapter_store.put_bytes(pub.json()["versions"][0]["weight_key"], data,
                            "application/octet-stream")
    c = finish(submit("acme", "corrupt-check"))
    assert (c["state"], c["error_code"]) == ("failed", "checksum_mismatch"), c
    cached = [p.name for p in ctx["tmp"].glob("cache-*/acme/*.safetensors")]
    assert f"{bad_sha}.safetensors" not in cached
    ev["checksum_mismatch"] = {"job": c["job_id"], "worker": c["worker_id"],
                               "error_code": c["error_code"], "cache_entry_left": False}

    # 5 + 6. Swaps and cache hits on one worker: stop w2 first.
    ctx["procs"]["w2"].kill(signal.SIGTERM)
    j_a = finish(submit("acme", "pixel-art"))
    j_b = finish(submit("acme", "3d-render"))
    j_base = finish(submit("acme", None))
    j_a2 = finish(submit("acme", "pixel-art"))
    for j in (j_a, j_b, j_base, j_a2):
        assert j["state"] == "succeeded" and j["worker_id"] == "w1", j
        assert j["adapters_after_unload"] == []
    assert j_a2["cache"] == "hit" and j_a2["bytes_fetched"] == 0
    pa, pb, pbase, pa2 = (api.output_png(j["job_id"]) for j in (j_a, j_b, j_base, j_a2))
    for name, png in (("swap-a", pa), ("swap-b", pb), ("swap-base", pbase), ("swap-a-again", pa2)):
        _save(ctx, name, png)
    swaps = {"mad_a_b": mad(pa, pb), "mad_a_base": mad(pa, pbase), "mad_b_base": mad(pb, pbase),
             "a_again_sha_equal": j_a["output_sha256"] == j_a2["output_sha256"],
             "a_again_max_px": max_px(pa, pa2)}
    assert min(swaps["mad_a_b"], swaps["mad_a_base"], swaps["mad_b_base"]) > THRESH, swaps
    assert swaps["a_again_sha_equal"] or swaps["a_again_max_px"] <= 1, swaps
    ev["swaps"] = swaps
    ev["cache_hit"] = {"job": j_a2["job_id"], "cache": j_a2["cache"],
                       "bytes_fetched": j_a2["bytes_fetched"]}

    # 7. Worker kill: render R, then kill w1 mid-job; w2 finishes attempt 2.
    x = {"steps": 40, "seed": 1234, "prompt": "a red fox in a snowy forest, pixel art"}
    ref = finish(submit("acme", "pixel-art", **x))
    assert ref["state"] == "succeeded"
    ref_png = api.output_png(ref["job_id"])
    _save(ctx, "kill-reference", ref_png)
    job_x = submit("acme", "pixel-art", **x)
    deadline = time.time() + 300
    while time.time() < deadline:
        cur = api.job(job_x["job_id"])
        if cur["state"] == "running" and (cur["step"] or 0) >= 2:
            break
        time.sleep(0.3)
    assert cur["worker_id"] == "w1" and cur["attempt"] == 1, cur
    killed_at_step = cur["step"]
    ctx["procs"]["w1"].kill(signal.SIGKILL)
    ctx["procs"]["w2"] = start_worker("w2", ctx["wenv"]["w2"], ctx["evidence_dir"])
    done_x = finish(job_x)
    assert done_x["state"] == "succeeded" and done_x["attempt"] == 2, done_x
    assert done_x["worker_id"] == "w2"
    retry_png = api.output_png(done_x["job_id"])
    _save(ctx, "kill-retry", retry_png)
    late = api.http.post(f"/worker/jobs/{job_x['job_id']}/complete", json={
        "worker_id": "w1", "attempt": 1, "cache": "hit", "bytes_fetched": 0,
        "sha256_verified": True, "fetch_ms": 0, "load_ms": 0, "generate_ms": 0, "unload_ms": 0,
        "output_sha256": "0" * 64, "adapters_after_unload": []})
    assert late.status_code == 409 and late.json()["code"] == "stale_attempt"
    kill = {"killed_worker": "w1", "killed_at_step": killed_at_step,
            "retry_worker": done_x["worker_id"], "retry_attempt": done_x["attempt"],
            "sha_equal": ref["output_sha256"] == done_x["output_sha256"],
            "max_px": max_px(ref_png, retry_png), "late_completion_status": late.status_code}
    assert kill["sha_equal"] or kill["max_px"] <= 1, kill
    ev["worker_kill"] = kill

    # 8. The run report in B2.
    report_key = f"{PREFIX}reports/{run}/adapters.json"
    ctx["written"].add(report_key)
    assert adapter_store.head(report_key) is not None
    report = api.http.get(f"/runs/{run}/report").json()
    ok = [j for j in report["jobs"] if j["state"] == "succeeded"]
    assert ok and all(j["generate_ms"] > 0 for j in ok)
    assert all(j["load_ms"] > 0 for j in ok if j["adapter"])
    assert report["summary"]["retried_jobs"] >= 1
    adapter_jobs = [j for j in jobs_all if j["adapter"] and j["state"] == "succeeded"]
    assert all(j["sha256_verified"] for j in adapter_jobs)
    (ctx["evidence_dir"] / "adapters.json").write_text(json.dumps(report, indent=2))
    ev["report"] = {"key": report_key, "summary": report["summary"],
                    "device_summary": report["device_summary"]}
    ev["jobs"] = [{k: j[k] for k in ("job_id", "tenant_id", "adapter", "state", "attempt",
                                     "worker_id", "cache", "bytes_fetched", "error_code")}
                  | {"timings": j["timings"]} for j in jobs_all]


def _fixture_file(ctx, adapter: str) -> Path:
    from app.repo import hf_source

    for entries in ctx["fixtures"]["tenants"].values():
        for e in entries:
            if e["adapter"] == adapter:
                return hf_source.download_adapter(e["repo_id"], e["filename"], e["revision"])
    raise AssertionError(adapter)

