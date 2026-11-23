"""Publish order: weight, then version manifest, then the tenant manifest LAST."""

import io
import json
import pickle

import pytest

from app.service import keys, registry
from app.types import AdapterSource, AppError
from tests.fakes import make_safetensors


def _inp(**kw):
    base = dict(tenant_id="acme", adapter="pixel-art", version="v1",
                license="creativeml-openrail-m",
                source=AdapterSource(type="upload", filename="a.safetensors"))
    return registry.PublishInput(**{**base, **kw})


def _publish(inp, data, filename="a.safetensors"):
    return registry.publish(inp, io.BytesIO(data), len(data), filename)


def test_tenant_manifest_written_last(fake_store):
    detail = _publish(_inp(), make_safetensors())
    order = [k for op, k in fake_store.ops if op in ("upload", "put")]
    assert order == [
        keys.weight_key("acme", "pixel-art", "v1"),
        keys.version_manifest_key("acme", "pixel-art", "v1"),
        keys.tenant_manifest_key("acme"),
    ]
    vm = json.loads(fake_store.objects[keys.version_manifest_key("acme", "pixel-art", "v1")])
    assert vm["sha256"] == detail.versions[0].sha256
    assert vm["tenant_id"] == "acme"
    assert vm["base_model"]["id"] == "stabilityai/stable-diffusion-xl-base-1.0"


def test_failure_before_last_step_leaves_tenant_manifest_unchanged(fake_store):
    _publish(_inp(), make_safetensors(0))
    before = fake_store.objects[keys.tenant_manifest_key("acme")]
    fake_store.fail_on_put = "v2/manifest.json"
    with pytest.raises(RuntimeError):
        _publish(_inp(version="v2"), make_safetensors(1))
    assert fake_store.objects[keys.tenant_manifest_key("acme")] == before


def test_existing_version_is_409(fake_store):
    _publish(_inp(), make_safetensors())
    with pytest.raises(AppError) as e:
        _publish(_inp(), make_safetensors(3))
    assert e.value.status == 409 and e.value.code == "version_exists"


def test_new_version_becomes_current(fake_store):
    _publish(_inp(), make_safetensors(0))
    d = _publish(_inp(version="v2"), make_safetensors(1))
    assert d.current_version == "v2"
    assert {v.version for v in d.versions} == {"v1", "v2"}


@pytest.mark.parametrize("filename", ["a.bin", "a.pt", "a.ckpt"])
def test_pickle_formats_rejected_by_name(fake_store, filename):
    with pytest.raises(AppError) as e:
        _publish(_inp(), make_safetensors(), filename)
    assert e.value.code == "not_safetensors"
    assert fake_store.ops == []


def test_pickle_bytes_named_safetensors_rejected(fake_store):
    data = pickle.dumps({"weights": [1, 2, 3]})
    with pytest.raises(AppError) as e:
        _publish(_inp(), data)
    assert e.value.code == "not_safetensors"
    assert fake_store.ops == []


def test_truncated_safetensors_rejected(fake_store):
    with pytest.raises(AppError):
        _publish(_inp(), make_safetensors()[:-2])


def test_license_outside_allowlist_is_422(fake_store):
    with pytest.raises(AppError) as e:
        _publish(_inp(license="other"), make_safetensors())
    assert e.value.status == 422 and e.value.code == "license_not_allowed"


async def test_publish_route_upload(client, fake_store):
    data = make_safetensors(5)
    r = await client.post(
        "/tenants/acme/adapters",
        data={"adapter": "pixel-art", "version": "v1", "license": "mit", "source": "upload",
              "trigger_words": "pixel art, 8-bit"},
        files={"file": ("pixel.safetensors", io.BytesIO(data), "application/octet-stream")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["trigger_words"] == ["pixel art", "8-bit"]
    assert body["versions"][0]["source"]["type"] == "upload"


async def test_publish_route_rejects_bad_identifier(client, fake_store):
    r = await client.post(
        "/tenants/acme/adapters",
        data={"adapter": "../etc", "version": "v1", "license": "mit", "source": "upload"},
        files={"file": ("a.safetensors", io.BytesIO(make_safetensors()), "application/octet-stream")},
    )
    assert r.status_code == 422
    assert fake_store.ops == []
