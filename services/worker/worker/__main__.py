"""`python -m worker`: load the base model once, then claim and run jobs forever."""

import contextlib
import json
import logging
import signal
import sys
import time
from datetime import UTC, datetime

import httpx

from worker.api_client import DispatcherClient
from worker.cache import AdapterCache
from worker.config import load_config
from worker.device import select_device
from worker.pipeline import Engine
from worker.runner import run_job


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": datetime.now(UTC).isoformat(), "level": record.levelname,
            "logger": record.name, "message": record.getMessage(),
        })


def main() -> int:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    log = logging.getLogger("worker")

    cfg = load_config()
    stopping = {"flag": False}

    def _stop(*_):
        stopping["flag"] = True
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _stop)

    device, dtype = select_device(cfg.torch_device)
    log.info("worker %s loading %s on %s (%s)", cfg.worker_id, cfg.base_model, device, dtype)
    t = time.perf_counter()
    engine = Engine.load(cfg.base_model, cfg.base_model_revision, device, dtype)
    log.info("base model loaded in %d ms", int((time.perf_counter() - t) * 1000))

    cache = AdapterCache(cfg.cache_dir, cfg.cache_max_bytes, cfg.verify_on_hit)
    client = DispatcherClient(cfg.api_url, cfg.worker_id, cfg.worker_token)

    ack = None
    while ack is None:
        try:
            ack = client.register(device, dtype, cfg.base_model, *cache.stats())
        except httpx.HTTPStatusError as e:
            log.error("register rejected: %s", e.response.text)
            return 2
        except httpx.HTTPError as e:
            log.warning("dispatcher not reachable (%s); retrying", e)
            time.sleep(2)
    log.info("registered: heartbeat %ss, lease %ss", ack["heartbeat_seconds"], ack["lease_seconds"])

    while not stopping["flag"]:
        try:
            job = client.claim(wait_seconds=25)
        except httpx.HTTPError as e:
            log.warning("claim failed (%s); retrying", e)
            time.sleep(2)
            continue
        if job is None:
            continue
        log.info("job %s attempt %d tenant=%s adapter=%s", job["job_id"], job["attempt"],
                 job["tenant_id"], (job.get("adapter") or {}).get("adapter"))
        done = run_job(job, client, cache, engine, ack["heartbeat_seconds"])
        if done is not None:
            log.info("job %s -> %s", job["job_id"], done["state"])
            with contextlib.suppress(httpx.HTTPError):
                client.register(device, dtype, cfg.base_model, *cache.stats())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
