import json

from app.service import keys
from app.service.reports import build_report

SHA = "b" * 64


def _row(job_id, state, *, attempt=1, cache="miss", load=100, gen=1000, adapter="pixel-art"):
    return {
        "job_id": job_id, "tenant_id": "acme", "adapter": adapter, "version": "v1",
        "adapter_sha256": SHA, "worker_id": "w1", "attempt": attempt, "state": state,
        "cache": cache, "bytes_fetched": 0 if cache == "hit" else 10, "fetch_ms": 5,
        "load_ms": load, "generate_ms": gen, "unload_ms": 7, "total_ms": load + gen + 20,
        "seed": 1, "steps": 15, "width": 768, "height": 768, "output_key": f"o/{job_id}.png",
        "output_sha256": SHA, "error_code": None, "device": "mps", "created_at": job_id,
    }


def test_report_shape_and_summary_math():
    rows = [
        _row("j1", "succeeded", load=100, gen=1000),
        _row("j2", "succeeded", cache="hit", load=300, gen=3000, attempt=2),
        _row("j3", "failed", load=0, gen=0),
        _row("j4", "succeeded", load=0, gen=2000, adapter=None, cache="none"),
    ]
    r = build_report("run-1", rows, "2026-11-23T00:00:00Z")
    doc = json.loads(r.model_dump_json())
    assert set(doc) == {"run_id", "created_at", "base_model", "device_summary", "jobs", "summary"}
    assert doc["device_summary"] == ["mps"]
    s = doc["summary"]
    assert s == {"jobs": 4, "succeeded": 3, "failed": 1, "cache_hits": 1,
                 "load_ms_p50": 200, "generate_ms_p50": 2000, "retried_jobs": 1}
    assert set(doc["jobs"][0]) >= {
        "job_id", "tenant_id", "adapter", "version", "adapter_sha256", "worker_id", "attempt",
        "state", "cache", "bytes_fetched", "fetch_ms", "load_ms", "generate_ms", "unload_ms",
        "total_ms", "seed", "steps", "width", "height", "output_key", "output_sha256",
    }


async def test_report_written_when_last_job_terminal(client, publish, fake_store):
    from app.config import settings

    publish("acme", "pixel-art")
    await client.post("/worker/register", json={
        "worker_id": "w1", "device": "mps", "dtype": "float16", "base_model": settings.base_model})
    r = await client.post("/runs/compare", json={
        "tenant_id": "acme", "adapters": ["pixel-art"], "include_base": True, "prompt": "x",
        "seed": 3, "steps": 15, "size": 768})
    run_id = r.json()["run_id"]
    key = keys.report_key(run_id)
    for i in range(2):
        job = (await client.post("/worker/jobs/claim",
                                 json={"worker_id": "w1", "wait_seconds": 0})).json()["job"]
        fake_store.objects[job["output_key"]] = b"png"
        await client.post(f"/worker/jobs/{job['job_id']}/complete", json={
            "worker_id": "w1", "attempt": 1, "cache": "miss" if job["adapter"] else "none",
            "bytes_fetched": 0, "sha256_verified": True, "fetch_ms": 0, "load_ms": 10,
            "generate_ms": 20, "unload_ms": 1, "output_sha256": SHA,
            "adapters_after_unload": []})
        assert (key in fake_store.objects) == (i == 1)
    report = (await client.get(f"/runs/{run_id}/report")).json()
    assert report["summary"]["succeeded"] == 2
    assert report["device_summary"] == ["mps"]
    run = (await client.get(f"/runs/{run_id}")).json()
    assert run["report_key"] == key


async def test_report_404_until_written(client, publish):
    publish("acme", "pixel-art")
    r = await client.post("/tenants/acme/generations", json={"adapter": "pixel-art", "prompt": "x"})
    rr = await client.get(f"/runs/{r.json()['run_id']}/report")
    assert rr.status_code == 404 and rr.json()["code"] == "report_not_ready"
