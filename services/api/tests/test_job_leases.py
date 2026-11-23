"""Leases: claim, expiry, retry with the same seed, stale-attempt rejection."""

import time

import pytest

from app.config import settings
from app.repo import jobs_db

SHA = "a" * 64


@pytest.fixture
async def queued(client, publish):
    publish("acme", "pixel-art")
    for wid in ("w1", "w2"):
        r = await client.post("/worker/register", json={
            "worker_id": wid, "device": "cpu", "dtype": "float32",
            "base_model": settings.base_model,
        })
        assert r.status_code == 200
    r = await client.post("/tenants/acme/generations",
                          json={"adapter": "pixel-art", "prompt": "x", "seed": 42, "steps": 15})
    return r.json()


async def _claim(client, wid):
    r = await client.post("/worker/jobs/claim", json={"worker_id": wid, "wait_seconds": 0})
    assert r.status_code == 200
    return r.json()["job"]


def _completion(wid, attempt):
    return {"worker_id": wid, "attempt": attempt, "cache": "miss", "bytes_fetched": 10,
            "sha256_verified": True, "fetch_ms": 1, "load_ms": 2, "generate_ms": 3,
            "unload_ms": 4, "output_sha256": SHA, "adapters_after_unload": []}


def _expire(job_id):
    jobs_db._db().execute("UPDATE jobs SET lease_expires_at = ? WHERE job_id = ?",
                          (time.time() - 1, job_id))


async def test_claim_sets_lease_attempt_and_presigns_then(client, queued, fake_store):
    assert fake_store.presigned == []
    job = await _claim(client, "w1")
    assert job["job_id"] == queued["job_id"] and job["attempt"] == 1
    assert job["adapter"]["url"].startswith("https://")
    assert job["adapter"]["tenant_id"] == "acme"
    assert ("GET", job["adapter"]["weight_key"]) in fake_store.presigned
    assert ("PUT", job["output_key"]) in fake_store.presigned
    row = jobs_db.get_job(job["job_id"])
    assert row["state"] == "running" and row["worker_id"] == "w1"
    assert row["lease_expires_at"] > time.time()
    assert await _claim(client, "w2") is None


async def test_expired_lease_requeues_with_same_seed(client, queued):
    first = await _claim(client, "w1")
    _expire(first["job_id"])
    second = await _claim(client, "w2")
    assert second["job_id"] == first["job_id"]
    assert second["attempt"] == 2 and second["seed"] == first["seed"] == 42


async def test_stale_attempt_completion_is_409(client, queued, fake_store):
    first = await _claim(client, "w1")
    _expire(first["job_id"])
    second = await _claim(client, "w2")
    fake_store.objects[second["output_key"]] = b"png"
    late = await client.post(f"/worker/jobs/{first['job_id']}/complete",
                             json=_completion("w1", 1))
    assert late.status_code == 409 and late.json()["code"] == "stale_attempt"
    hb = await client.post(f"/worker/jobs/{first['job_id']}/heartbeat",
                           json={"worker_id": "w1", "attempt": 1, "step": 3})
    assert hb.status_code == 409
    ok = await client.post(f"/worker/jobs/{second['job_id']}/complete",
                           json=_completion("w2", 2))
    assert ok.status_code == 200 and ok.json()["state"] == "succeeded"
    assert ok.json()["attempt"] == 2


async def test_heartbeat_extends_lease_and_records_step(client, queued):
    job = await _claim(client, "w1")
    r = await client.post(f"/worker/jobs/{job['job_id']}/heartbeat",
                          json={"worker_id": "w1", "attempt": 1, "step": 5, "total_steps": 15})
    assert r.status_code == 200
    assert jobs_db.get_job(job["job_id"])["step"] == 5


async def test_max_attempts_exhausted_fails_job(client, queued, monkeypatch):
    monkeypatch.setattr(settings, "job_max_attempts", 2)
    for wid in ("w1", "w2"):
        job = await _claim(client, wid)
        _expire(job["job_id"])
    assert await _claim(client, "w1") is None
    row = jobs_db.get_job(queued["job_id"])
    assert row["state"] == "failed" and row["error_code"] == "lease_exhausted"


async def test_completion_without_output_object_fails(client, queued):
    job = await _claim(client, "w1")
    r = await client.post(f"/worker/jobs/{job['job_id']}/complete", json=_completion("w1", 1))
    assert r.json()["state"] == "failed" and r.json()["error_code"] == "output_missing"


async def test_adapter_residue_fails_job(client, queued, fake_store):
    job = await _claim(client, "w1")
    fake_store.objects[job["output_key"]] = b"png"
    body = {**_completion("w1", 1), "adapters_after_unload": ["job-x"]}
    r = await client.post(f"/worker/jobs/{job['job_id']}/complete", json=body)
    assert r.json()["error_code"] == "adapter_residue"


async def test_worker_fail_records_code(client, queued):
    job = await _claim(client, "w1")
    r = await client.post(f"/worker/jobs/{job['job_id']}/fail", json={
        "worker_id": "w1", "attempt": 1, "code": "checksum_mismatch", "message": "bad"})
    assert r.json()["state"] == "failed" and r.json()["error_code"] == "checksum_mismatch"


async def test_unregistered_worker_cannot_claim(client, queued):
    r = await client.post("/worker/jobs/claim", json={"worker_id": "ghost", "wait_seconds": 0})
    assert r.status_code == 409


async def test_register_rejects_other_base_model(client):
    r = await client.post("/worker/register", json={
        "worker_id": "w9", "device": "cpu", "dtype": "float32", "base_model": "other/model"})
    assert r.status_code == 422 and r.json()["code"] == "base_model_mismatch"


async def test_heartbeat_phase_and_stale_signal_reach_the_job(client, queued):
    job = await _claim(client, "w1")
    jid = job["job_id"]
    hb = await client.post(f"/worker/jobs/{jid}/heartbeat",
                           json={"worker_id": "w1", "attempt": 1, "phase": "fetching"})
    assert hb.status_code == 200
    live = (await client.get(f"/jobs/{jid}")).json()
    assert live["phase"] == "fetching" and live["heartbeat_stale"] is False
    assert live["lease_expires_at"]
    # The worker goes silent: two missed heartbeats mark the job stale.
    jobs_db._db().execute("UPDATE jobs SET heartbeat_at = ? WHERE job_id = ?",
                          (time.time() - 3 * settings.job_heartbeat_seconds, jid))
    assert (await client.get(f"/jobs/{jid}")).json()["heartbeat_stale"] is True
    _expire(jid)
    await _claim(client, "w2")
    retried = (await client.get(f"/jobs/{jid}")).json()
    assert retried["phase"] is None and retried["heartbeat_stale"] is False


def test_existing_jobs_db_gains_new_columns(tmp_path, monkeypatch):
    import sqlite3

    path = tmp_path / "old.db"
    old_schema = jobs_db._SCHEMA.replace(",\n  phase TEXT, heartbeat_at REAL", "")
    assert old_schema != jobs_db._SCHEMA
    sqlite3.connect(path).executescript(old_schema).connection.close()
    monkeypatch.setattr(settings, "jobs_db_path", str(path))
    jobs_db.reset_for_tests()
    cols = {r["name"] for r in jobs_db._db().execute("PRAGMA table_info(jobs)")}
    assert {"phase", "heartbeat_at"} <= cols
    jobs_db.reset_for_tests()
