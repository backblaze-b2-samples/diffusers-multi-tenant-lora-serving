"""Run one claimed job end to end. Stateless: everything comes from the claim.

Order: tenant check, cache lookup or verified fetch, load, generate, unload,
upload, complete. The adapter is unloaded in a `finally`, so a failure in any
step never leaves one tenant's adapter loaded for the next job.
"""

import hashlib
import logging
import threading
import time

from worker.api_client import DispatcherClient, StaleAttempt
from worker.cache import AdapterCache
from worker.fetch import ChecksumMismatch, FetchFailed, download_verified
from worker.pipeline import Engine, LeaseLost, elapsed_ms

logger = logging.getLogger("worker")


class JobFailed(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class Heartbeater:
    """Background heartbeats carrying the attempt, the current phase and step."""

    def __init__(self, client: DispatcherClient, job: dict, every: float):
        self.client, self.job, self.every = client, job, every
        self.step: int | None = None
        self.total: int | None = None
        self.phase: str | None = None
        self.lost = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def beat(self) -> None:
        try:
            self.client.heartbeat(self.job["job_id"], self.job["attempt"], self.step, self.total,
                                  self.phase)
        except StaleAttempt:
            self.lost.set()
        except Exception as e:  # transient: the lease absorbs a missed beat
            logger.warning("heartbeat failed: %s", e)

    def _run(self) -> None:
        while not self._stop.wait(self.every):
            self.beat()

    def set_phase(self, phase: str) -> None:
        """Report a phase change right away, so the UI does not wait a full beat."""
        self.phase = phase
        self.beat()

    def on_step(self, step: int, total: int) -> None:
        self.step, self.total = step, total
        if self.lost.is_set():
            raise LeaseLost()

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=5)


def check_tenant(job: dict) -> None:
    adapter = job.get("adapter")
    if not adapter:
        return
    tenant = job["tenant_id"]
    if adapter["tenant_id"] != tenant or f"/adapters/{tenant}/" not in "/" + adapter["weight_key"]:
        raise JobFailed("manifest_tenant_mismatch", "claim adapter does not belong to the tenant")


def run_job(job: dict, client: DispatcherClient, cache: AdapterCache, engine: Engine,
            heartbeat_seconds: float) -> dict | None:
    """Execute the job and report it. Returns the dispatcher's job, None if lease lost."""
    job_id, attempt = job["job_id"], job["attempt"]
    adapter = job.get("adapter")
    name = f"job-{job_id}-{attempt}"
    result = {"cache": "none", "bytes_fetched": 0, "sha256_verified": False, "fetch_ms": 0,
              "load_ms": 0, "generate_ms": 0, "unload_ms": 0}
    loaded = False
    try:
        with Heartbeater(client, job, heartbeat_seconds) as hb:
            hb.beat()
            check_tenant(job)
            if adapter:
                t = time.perf_counter()
                hb.set_phase("verifying")
                path = cache.lookup(job["tenant_id"], adapter["sha256"], adapter["size_bytes"])
                if path is not None:
                    result["cache"] = "hit"
                else:
                    path = cache.path_for(job["tenant_id"], adapter["sha256"])
                    hb.set_phase("fetching")
                    try:
                        result["bytes_fetched"] = download_verified(
                            client.http, adapter["url"], path, adapter["sha256"],
                            adapter["size_bytes"])
                    except ChecksumMismatch as e:
                        raise JobFailed("checksum_mismatch", str(e)) from e
                    except FetchFailed as e:
                        raise JobFailed("fetch_failed", str(e)) from e
                    result["cache"] = "miss"
                    cache.evict(keep=path)
                result["sha256_verified"] = True
                result["fetch_ms"] = elapsed_ms(t)
                t = time.perf_counter()
                loaded = True
                hb.set_phase("loading")
                engine.load_adapter(path, name, adapter["scale"])
                result["load_ms"] = elapsed_ms(t)
            t = time.perf_counter()
            hb.set_phase("generating")
            png = engine.generate(job["prompt"], job.get("negative_prompt"), job["seed"],
                                  job["steps"], job["width"], job["height"], hb.on_step)
            result["generate_ms"] = elapsed_ms(t)
            if adapter:
                t = time.perf_counter()
                hb.set_phase("unloading")
                result["adapters_after_unload"] = engine.unload_adapter(name)
                loaded = False
                result["unload_ms"] = elapsed_ms(t)
            else:
                result["adapters_after_unload"] = engine.loaded_adapters()
            hb.set_phase("uploading")
            client.put_output(job["output_url"], png)
            result["output_sha256"] = hashlib.sha256(png).hexdigest()
        return client.complete(job_id, attempt, result)
    except (LeaseLost, StaleAttempt):
        logger.warning("job %s attempt %d: lease lost, dropping the result", job_id, attempt)
        return None
    except JobFailed as e:
        return _fail(client, job_id, attempt, e.code, str(e))
    except Exception as e:
        logger.exception("job %s failed", job_id)
        return _fail(client, job_id, attempt, "generation_failed", f"{type(e).__name__}: {e}")
    finally:
        if loaded:
            engine.unload_adapter(name)


def _fail(client: DispatcherClient, job_id: str, attempt: int, code: str, msg: str) -> dict | None:
    try:
        return client.fail(job_id, attempt, code, msg)
    except StaleAttempt:
        return None
