"""Deletes stay inside the adapter's (or version's) own prefix."""

from app.service import keys


async def test_delete_adapter_only_touches_its_prefix(client, publish, fake_store):
    publish("acme", "pixel-art")
    publish("acme", "pixel-art", version="v2", seed=1)
    publish("acme", "pixel-art-xl", seed=2)  # shares a name prefix, must survive
    publish("globex", "pixel-art", seed=3)
    r = await client.delete("/tenants/acme/adapters/pixel-art", params={"confirm": "pixel-art"})
    assert r.status_code == 200
    deleted = r.json()["deleted_keys"]
    root = keys.adapter_root("acme", "pixel-art")
    assert deleted and all(k.startswith(root) for k in deleted)
    assert keys.weight_key("acme", "pixel-art-xl", "v1") in fake_store.objects
    assert keys.weight_key("globex", "pixel-art", "v1") in fake_store.objects
    m = (await client.get("/tenants/acme/manifest")).json()
    assert set(m["adapters"]) == {"pixel-art-xl"}


async def test_delete_adapter_requires_confirmation(client, publish, fake_store):
    publish("acme", "pixel-art")
    r = await client.delete("/tenants/acme/adapters/pixel-art", params={"confirm": "nope"})
    assert r.status_code == 422
    assert not any(op == "delete" for op, _ in fake_store.ops)


async def test_delete_version_scope_and_current_guard(client, publish, fake_store):
    publish("acme", "pixel-art")
    publish("acme", "pixel-art", version="v2", seed=1)
    r = await client.delete("/tenants/acme/adapters/pixel-art/versions/v2")
    assert r.status_code == 409  # v2 is current and v1 exists
    r = await client.delete("/tenants/acme/adapters/pixel-art/versions/v1")
    assert r.status_code == 200
    root = keys.version_root("acme", "pixel-art", "v1")
    assert all(k.startswith(root) for k in r.json()["deleted_keys"])
    assert keys.weight_key("acme", "pixel-art", "v2") in fake_store.objects


async def test_edit_and_verify(client, publish, fake_store):
    publish("acme", "pixel-art")
    publish("acme", "pixel-art", version="v2", seed=1)
    r = await client.patch("/tenants/acme/adapters/pixel-art", json={
        "display_name": "Pixel Art", "default_scale": 0.8, "current_version": "v1",
        "trigger_words": ["pixel art"]})
    assert r.status_code == 200
    assert r.json()["current_version"] == "v1" and r.json()["default_scale"] == 0.8
    v = (await client.post("/tenants/acme/adapters/pixel-art/versions/v1/verify")).json()
    assert v["match"] is True
    fake_store.objects[keys.weight_key("acme", "pixel-art", "v1")] = b"corrupted"
    v = (await client.post("/tenants/acme/adapters/pixel-art/versions/v1/verify")).json()
    assert v["match"] is False and v["size_actual"] == 9


async def test_tenants_and_library_listing(client, publish):
    publish("acme", "pixel-art")
    publish("globex", "toy-face", seed=1)
    tenants = (await client.get("/tenants")).json()
    assert [t["tenant_id"] for t in tenants] == ["acme", "globex"]
    lib = (await client.get("/library", params={"tenant_id": "acme"})).json()
    assert lib and all(e["tenant_id"] == "acme" for e in lib)
    assert {e["kind"] for e in lib} == {"adapters"}
