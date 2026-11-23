import os
import time

from tests.conftest import ADAPTER_BYTES, ADAPTER_SHA, make_job
from worker.cache import AdapterCache
from worker.runner import run_job


def test_miss_then_hit_fetches_once(client, cache, engine, dispatcher):
    first = run_job(make_job(), client, cache, engine, 60)
    second = run_job(make_job(), client, cache, engine, 60)
    assert first["cache"] == "miss" and first["bytes_fetched"] == len(ADAPTER_BYTES)
    assert second["cache"] == "hit" and second["bytes_fetched"] == 0
    gets = [r for r in dispatcher.requests if r.url.host == "b2.example" and r.method == "GET"]
    assert len(gets) == 1


def test_cache_paths_are_tenant_scoped(client, cache, engine, dispatcher):
    run_job(make_job("acme"), client, cache, engine, 60)
    other = run_job(make_job("globex"), client, cache, engine, 60)
    assert other["cache"] == "miss"  # same bytes, other tenant: never shared
    assert (cache.root / "acme" / f"{ADAPTER_SHA}.safetensors").is_file()
    assert (cache.root / "globex" / f"{ADAPTER_SHA}.safetensors").is_file()


def test_checksum_mismatch_caches_nothing(client, cache, engine, dispatcher):
    dispatcher.adapter_bytes = b"tampered" * 10
    out = run_job(make_job(), client, cache, engine, 60)
    assert out["error_code"] == "checksum_mismatch"
    assert dispatcher.failed[0]["code"] == "checksum_mismatch"
    assert cache.entries() == []
    assert not list(cache.root.rglob("*"))  or all(p.is_dir() for p in cache.root.rglob("*"))


def test_corrupted_cache_entry_is_dropped_on_hit(cache):
    path = cache.path_for("acme", ADAPTER_SHA)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * len(ADAPTER_BYTES))
    assert cache.lookup("acme", ADAPTER_SHA, len(ADAPTER_BYTES)) is None
    assert not path.exists()


def test_lru_eviction_keeps_recent(tmp_path):
    cache = AdapterCache(tmp_path, max_bytes=250)
    paths = []
    for i, sha in enumerate(["a" * 64, "b" * 64, "c" * 64]):
        p = cache.path_for("acme", sha)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"0" * 100)
        old = time.time() - 100 + i
        os.utime(p, (old, old))
        paths.append(p)
    removed = cache.evict(keep=paths[0])
    assert removed == [paths[1]]
    assert paths[0].exists() and paths[2].exists()
