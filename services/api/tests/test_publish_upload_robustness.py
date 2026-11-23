"""Publishing large adapters over a slow uplink: upload sizing, typed errors,
background demo publish with progress, and a health probe that our own upload
cannot flip to "not connected"."""

import io
from pathlib import Path

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError

from app.repo import adapter_store, b2_client
from app.service import fixture_job, fixtures, registry
from app.types import AdapterSource, AppError
from tests.fakes import make_safetensors


def _inp(**kw):
    base = dict(tenant_id="acme", adapter="pixel-art", version="v1",
                license="creativeml-openrail-m",
                source=AdapterSource(type="upload", filename="a.safetensors"))
    return registry.PublishInput(**{**base, **kw})


# --- upload client and transfer sizing ---

def test_upload_client_is_separate_and_sized_for_slow_links(monkeypatch):
    made = []
    monkeypatch.setattr(b2_client.boto3, "client", lambda *_a, **kw: made.append(kw) or object())
    assert b2_client.get_upload_client() is not b2_client.get_s3_client()
    up, small = made[0]["config"], made[1]["config"]
    assert up.user_agent_extra == small.user_agent_extra == "b2ai-diffusers-lora-weights-hub"
    assert up.read_timeout >= 120 and small.read_timeout == 30
    assert up.retries["total_max_attempts"] >= 5
    assert up.max_pool_connections > b2_client.UPLOAD_MAX_CONCURRENCY


def test_upload_stream_uses_bounded_concurrency_and_reports_progress(monkeypatch):
    seen = {}

    class Client:
        def upload_fileobj(self, reader, bucket, key, ExtraArgs, Config, Callback):
            seen["config"], seen["in_flight"] = Config, b2_client._uploads_in_flight
            data = reader.read()
            Callback(len(data))

    monkeypatch.setattr(adapter_store, "get_upload_client", lambda: Client())
    got = []
    _sha, size = adapter_store.upload_stream("k", io.BytesIO(b"x" * 10), "a/b", got.append)
    cfg = seen["config"]
    assert cfg.max_concurrency <= 4 and cfg.multipart_chunksize >= 16 * 1024 * 1024
    assert seen["in_flight"] == 1 and b2_client._uploads_in_flight == 0
    assert size == 10 and got == [10]


def test_upload_failure_is_a_typed_502_and_nothing_resolves(fake_store):
    fake_store.fail_on_upload = "adapter.safetensors"
    data = make_safetensors()
    with pytest.raises(AppError) as e:
        registry.publish(_inp(), io.BytesIO(data), len(data), "a.safetensors")
    assert e.value.status == 502 and e.value.code == "b2_upload_failed"
    assert "retry" in e.value.detail
    assert not any(k.endswith("manifest.json") for k in fake_store.objects)


@pytest.mark.asyncio
async def test_form_publish_upload_failure_returns_actionable_error(client, fake_store):
    fake_store.fail_on_upload = "adapter.safetensors"
    r = await client.post(
        "/tenants/acme/adapters",
        data={"adapter": "pixel-art", "version": "v1", "license": "creativeml-openrail-m",
              "source": "upload"},
        files={"file": ("a.safetensors", make_safetensors(), "application/octet-stream")},
    )
    assert r.status_code == 502
    assert r.json()["code"] == "b2_upload_failed"


# --- health probe under upload load ---

def _head_bucket_raises(monkeypatch, exc):
    class Client:
        def head_bucket(self, Bucket):
            raise exc

    monkeypatch.setattr(b2_client, "get_s3_client", lambda: Client())


def test_health_keeps_last_good_answer_when_our_upload_starves_the_probe(monkeypatch):
    b2_client._health_cache = (-1e9, True)  # expired but known-good
    _head_bucket_raises(monkeypatch, ReadTimeoutError(endpoint_url="https://s3"))
    with b2_client.upload_in_flight():
        assert b2_client.check_connectivity() is True


def test_health_reports_refusal_even_during_upload(monkeypatch):
    b2_client._health_cache = (-1e9, True)
    _head_bucket_raises(monkeypatch, ClientError({"Error": {"Code": "403"}}, "HeadBucket"))
    with b2_client.upload_in_flight():
        assert b2_client.check_connectivity() is False


def test_health_timeout_without_upload_is_not_connected(monkeypatch):
    b2_client._health_cache = (-1e9, True)
    _head_bucket_raises(monkeypatch, ReadTimeoutError(endpoint_url="https://s3"))
    assert b2_client.check_connectivity() is False


# --- background demo publish ---

@pytest.fixture
def two_fixtures(tmp_path, monkeypatch, fake_store):
    blobs = {"a.safetensors": make_safetensors(0), "b.safetensors": make_safetensors(1)}
    import hashlib

    lines = ["tenants:", "  acme:"]
    for i, (name, data) in enumerate(blobs.items()):
        (tmp_path / name).write_bytes(data)
        lines += [f"    - adapter: ad-{i}", "      version: v1", f"      repo_id: o/r{i}",
                  f"      filename: {name}", "      revision: abc",
                  "      license: creativeml-openrail-m",
                  f"      sha256: {hashlib.sha256(data).hexdigest()}",
                  f"      size_bytes: {len(data)}"]
    path = tmp_path / "adapters.yaml"
    path.write_text("\n".join(lines) + "\n")
    monkeypatch.setattr(fixtures.hf_source, "download_adapter",
                        lambda _r, filename, _v: Path(tmp_path / filename))
    monkeypatch.setattr(fixture_job, "_status", None)
    return path, sum(len(b) for b in blobs.values())


def test_demo_publish_reports_progress_and_success(two_fixtures):
    path, total = two_fixtures
    assert fixture_job.status(path).state == "idle"
    s = fixture_job.start(path, background=False)
    assert s.state == "succeeded" and s.error is None
    assert s.bytes_done == s.bytes_total == total
    assert s.adapters_done == s.adapters_total == 2
    assert s.published == ["acme/ad-0@v1", "acme/ad-1@v1"]
    again = fixture_job.start(path, background=False)
    assert again.published == [] and again.bytes_done == total  # skipped counts as done


def test_demo_publish_failure_persists_with_actionable_error(two_fixtures, fake_store):
    path, _ = two_fixtures
    fake_store.fail_on_upload = "ad-1/v1/adapter.safetensors"
    s = fixture_job.start(path, background=False)
    assert s.state == "failed" and s.error_code == "b2_upload_failed"
    assert s.published == ["acme/ad-0@v1"]
    assert fixture_job.status(path).state == "failed"  # still readable after a reload


def test_start_while_running_returns_the_running_job(two_fixtures, monkeypatch):
    path, _ = two_fixtures
    monkeypatch.setattr(fixture_job, "_run", lambda _p: None)
    first = fixture_job.start(path)
    second = fixture_job.start(path)
    assert first.state == second.state == "running"
    assert first.started_at == second.started_at


@pytest.mark.asyncio
async def test_publish_route_returns_202_and_status_is_pollable(client, monkeypatch):
    monkeypatch.setattr(fixture_job, "_status", None)
    monkeypatch.setattr(fixture_job, "_run", lambda _p: None)
    r = await client.post("/fixtures/publish")
    assert r.status_code == 202 and r.json()["state"] == "running"
    g = await client.get("/fixtures/publish")
    assert g.status_code == 200 and g.json()["adapters_total"] == 3


def test_demo_publish_b2_unreachable_is_named(two_fixtures, fake_store, monkeypatch):
    path, _ = two_fixtures

    def unreachable(_key):
        raise RuntimeError("B2 get failed: Could not connect to the endpoint URL")

    monkeypatch.setattr(adapter_store, "get_json", unreachable)
    fixtures.manifests.forget()
    s = fixture_job.start(path, background=False)
    assert s.state == "failed" and s.error_code == "b2_unavailable"
    assert "network" in s.error
