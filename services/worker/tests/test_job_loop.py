from tests.conftest import FakePipe, make_job
from worker.pipeline import Engine
from worker.runner import run_job


def test_success_loads_generates_unloads(client, cache, engine, pipe, dispatcher):
    out = run_job(make_job(), client, cache, engine, 60)
    kinds = [c[0] for c in pipe.calls]
    assert kinds == ["load", "set", "generate", "delete"]
    assert pipe.calls[1] == ("set", ("job-job-abc-1",), (0.8,))
    assert out["adapters_after_unload"] == [] and out["sha256_verified"] is True
    assert dispatcher.uploads == [b"\x89PNG fake"]
    assert dispatcher.completed[0]["attempt"] == 1


def test_unload_happens_even_when_generation_fails(client, cache, dispatcher):
    pipe = FakePipe(fail_generate=True)
    out = run_job(make_job(), client, cache, Engine(pipe, "cpu", "float32"), 60)
    assert out["error_code"] == "generation_failed"
    assert pipe.get_list_adapters() == {"unet": []}
    assert ("delete", "job-job-abc-1") in pipe.calls


def test_heartbeat_carries_attempt(client, cache, engine, dispatcher):
    run_job(make_job(attempt=3), client, cache, engine, 60)
    assert dispatcher.heartbeats and all(h["attempt"] == 3 for h in dispatcher.heartbeats)
    assert dispatcher.completed[0]["attempt"] == 3


def test_tenant_mismatch_fails_before_any_fetch(client, cache, engine, pipe, dispatcher):
    out = run_job(make_job("acme", weight_tenant="globex"), client, cache, engine, 60)
    assert out["error_code"] == "manifest_tenant_mismatch"
    assert not [r for r in dispatcher.requests if r.url.host == "b2.example"]
    assert pipe.calls == []


def test_manifest_tenant_field_mismatch_fails(client, cache, engine, dispatcher):
    out = run_job(make_job("acme", manifest_tenant="globex"), client, cache, engine, 60)
    assert out["error_code"] == "manifest_tenant_mismatch"


def test_base_model_job_reports_no_cache(client, cache, engine, pipe, dispatcher):
    out = run_job(make_job(adapter=False), client, cache, engine, 60)
    assert out["cache"] == "none" and out["bytes_fetched"] == 0
    assert [c[0] for c in pipe.calls] == ["generate"]


def test_stale_lease_drops_result_and_unloads(client, cache, engine, pipe, dispatcher):
    dispatcher.stale = True
    assert run_job(make_job(), client, cache, engine, 60) is None
    assert dispatcher.completed == []
    assert pipe.get_list_adapters() == {"unet": []}


def test_heartbeats_report_each_phase_in_order(client, cache, engine, dispatcher):
    run_job(make_job(), client, cache, engine, 60)
    phases = [h["phase"] for h in dispatcher.heartbeats if h.get("phase")]
    assert phases == ["verifying", "fetching", "loading", "generating", "unloading", "uploading"]
