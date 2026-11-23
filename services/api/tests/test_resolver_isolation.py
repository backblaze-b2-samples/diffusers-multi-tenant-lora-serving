"""Tenant isolation: every rejection happens before a job or a URL exists."""

import json

import pytest

from app.repo import jobs_db
from app.service import keys, manifests

BODY = {"prompt": "a lighthouse", "seed": 7, "steps": 15, "size": 768}


@pytest.fixture
def two_tenants(publish):
    publish("acme", "pixel-art")
    publish("acme", "paper-cut", seed=1)
    publish("globex", "toy-face", seed=2)


async def _gen(client, tenant, adapter):
    return await client.post(f"/tenants/{tenant}/generations", json={**BODY, "adapter": adapter})


def _assert_nothing_created(fake_store):
    assert jobs_db.list_jobs() == []
    assert fake_store.presigned == []


async def test_own_adapter_resolves(client, two_tenants, fake_store):
    r = await _gen(client, "acme", "pixel-art")
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["tenant_id"] == "acme" and job["adapter"] == "pixel-art"
    assert job["version"] == "v1" and job["state"] == "queued"
    manifest = json.loads(fake_store.objects[keys.tenant_manifest_key("acme")])
    assert job["adapter_sha256"] == manifest["adapters"]["pixel-art"]["versions"]["v1"]["sha256"]
    assert fake_store.presigned == []  # URLs are issued at claim, not at enqueue


async def test_qualified_cross_tenant_ref_is_403(client, two_tenants, fake_store):
    r = await _gen(client, "acme", "globex/toy-face")
    assert r.status_code == 403
    assert r.json()["code"] == "cross_tenant_adapter"
    _assert_nothing_created(fake_store)


async def test_other_tenants_name_unqualified_is_404(client, two_tenants, fake_store):
    r = await _gen(client, "acme", "toy-face")
    assert r.status_code == 404
    assert r.json()["code"] == "adapter_not_found"
    assert "globex" not in r.text
    _assert_nothing_created(fake_store)


async def test_unknown_version_is_404(client, two_tenants, fake_store):
    r = await _gen(client, "acme", "pixel-art@v9")
    assert r.status_code == 404
    _assert_nothing_created(fake_store)


async def test_tampered_manifest_pointing_at_other_tenant_is_403(client, two_tenants, fake_store):
    key = keys.tenant_manifest_key("acme")
    doc = json.loads(fake_store.objects[key])
    globex = json.loads(fake_store.objects[keys.tenant_manifest_key("globex")])
    stolen = globex["adapters"]["toy-face"]["versions"]["v1"]
    doc["adapters"]["pixel-art"]["versions"]["v1"].update(
        weight_key=stolen["weight_key"], manifest_key=stolen["manifest_key"],
    )
    fake_store.objects[key] = json.dumps(doc).encode()
    manifests.forget()
    r = await _gen(client, "acme", "pixel-art")
    assert r.status_code == 403
    assert r.json()["code"] == "manifest_tenant_mismatch"
    _assert_nothing_created(fake_store)


async def test_version_manifest_naming_other_tenant_is_403(client, two_tenants, fake_store):
    vkey = keys.version_manifest_key("acme", "pixel-art", "v1")
    doc = json.loads(fake_store.objects[vkey])
    doc["tenant_id"] = "globex"
    fake_store.objects[vkey] = json.dumps(doc).encode()
    manifests.forget()
    r = await _gen(client, "acme", "pixel-art")
    assert r.status_code == 403
    assert r.json()["code"] == "manifest_tenant_mismatch"
    _assert_nothing_created(fake_store)


async def test_base_model_mismatch_is_422(client, two_tenants, fake_store):
    vkey = keys.version_manifest_key("acme", "pixel-art", "v1")
    doc = json.loads(fake_store.objects[vkey])
    doc["base_model"]["id"] = "stable-diffusion-v1-5/stable-diffusion-v1-5"
    fake_store.objects[vkey] = json.dumps(doc).encode()
    manifests.forget()
    r = await _gen(client, "acme", "pixel-art")
    assert r.status_code == 422
    assert r.json()["code"] == "base_model_mismatch"
    _assert_nothing_created(fake_store)


async def test_rejections_are_counted_in_metrics(client, two_tenants):
    await _gen(client, "acme", "globex/toy-face")
    await _gen(client, "acme", "toy-face")
    text = (await client.get("/metrics")).text
    assert 'adapter_rejections_total{code="cross_tenant_adapter"} 1' in text
    assert 'adapter_rejections_total{code="adapter_not_found"} 1' in text


async def test_compare_rejects_whole_request_on_one_bad_ref(client, two_tenants, fake_store):
    r = await client.post("/runs/compare", json={
        "tenant_id": "acme", "adapters": ["pixel-art", "globex/toy-face"], "prompt": "x",
        "seed": 1, "steps": 15, "size": 768,
    })
    assert r.status_code == 403
    _assert_nothing_created(fake_store)


async def test_compare_queues_one_job_per_adapter_with_one_seed(client, two_tenants):
    r = await client.post("/runs/compare", json={
        "tenant_id": "acme", "adapters": ["pixel-art", "paper-cut"], "include_base": True,
        "prompt": "x", "seed": 99, "steps": 15, "size": 768,
    })
    assert r.status_code == 202
    jobs = r.json()["jobs"]
    assert [j["adapter"] for j in jobs] == ["pixel-art", "paper-cut", None]
    assert {j["seed"] for j in jobs} == {99}
