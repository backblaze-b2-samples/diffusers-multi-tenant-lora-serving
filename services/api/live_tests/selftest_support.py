"""Process and HTTP helpers for the LoRA serving self-test.

The dispatcher and both workers run as real subprocesses. Workers get an
environment with every `B2_*` key removed, so the self-test also proves that a
worker needs no storage credentials to do its job.
"""

import io
import json
import os
import signal
import socket
import subprocess
import time
from pathlib import Path

import httpx
from PIL import Image, ImageChops, ImageStat

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
WORKER_ROOT = REPO_ROOT / "services" / "worker"
UA = "b2ai-diffusers-lora-weights-hub selftest"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Proc:
    def __init__(self, name: str, args: list[str], cwd: Path, env: dict, log_dir: Path):
        self.name = name
        self.log_path = log_dir / f"{name}.log"
        self._log = self.log_path.open("ab")
        self.p = subprocess.Popen(args, cwd=cwd, env=env, stdout=self._log,
                                  stderr=subprocess.STDOUT, start_new_session=True)

    def alive(self) -> bool:
        return self.p.poll() is None

    def kill(self, sig: int = signal.SIGTERM, timeout: float = 30) -> None:
        if self.alive():
            self.p.send_signal(sig)
            try:
                self.p.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.p.kill()
                self.p.wait(timeout=10)
        self._log.close()


def worker_env(base: dict, api_url: str, worker_id: str, cache_dir: Path, revision: str) -> dict:
    env = {k: v for k, v in base.items() if not k.startswith("B2_")}
    env.update(API_URL=api_url, WORKER_ID=worker_id, ADAPTER_CACHE_DIR=str(cache_dir),
               BASE_MODEL_REVISION=revision, PYTHONUNBUFFERED="1")
    return env


def start_worker(worker_id: str, env: dict, log_dir: Path) -> Proc:
    return Proc(worker_id, [str(WORKER_ROOT / ".venv" / "bin" / "python"), "-m", "worker"],
                WORKER_ROOT, env, log_dir)


class Api:
    def __init__(self, base_url: str):
        self.base = base_url
        self.http = httpx.Client(base_url=base_url, timeout=60, headers={"User-Agent": UA})

    def wait_healthy(self, timeout: float = 60) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.http.get("/health").status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        raise AssertionError("API did not become healthy")

    def wait_workers(self, ids: set[str], timeout: float = 600) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            online = {w["worker_id"] for w in self.http.get("/workers").json() if w["online"]}
            if ids <= online:
                return
            time.sleep(2)
        raise AssertionError(f"workers {ids} did not come online")

    def generate(self, tenant: str, adapter: str | None, **kw) -> httpx.Response:
        body = {"adapter": adapter, "prompt": kw.pop("prompt", "a lighthouse on a cliff at sunset"),
                "seed": kw.pop("seed", 42), "steps": kw.pop("steps", 15),
                "size": kw.pop("size", 768), **kw}
        return self.http.post(f"/tenants/{tenant}/generations", json=body)

    def job(self, job_id: str) -> dict:
        return self.http.get(f"/jobs/{job_id}").json()

    def wait_job(self, job_id: str, timeout: float = 600) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            j = self.job(job_id)
            if j["state"] in ("succeeded", "failed"):
                return j
            time.sleep(1)
        raise AssertionError(f"job {job_id} did not finish")

    def output_png(self, job_id: str) -> bytes:
        url = self.http.get(f"/jobs/{job_id}/output").json()["url"]
        r = httpx.get(url, headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        return r.content


def mad(a: bytes, b: bytes) -> float:
    """Mean absolute pixel difference in [0, 1]."""
    ia, ib = Image.open(io.BytesIO(a)).convert("RGB"), Image.open(io.BytesIO(b)).convert("RGB")
    return sum(ImageStat.Stat(ImageChops.difference(ia, ib)).mean) / 3 / 255


def max_px(a: bytes, b: bytes) -> int:
    ia, ib = Image.open(io.BytesIO(a)).convert("RGB"), Image.open(io.BytesIO(b)).convert("RGB")
    return max(hi for _, hi in ImageChops.difference(ia, ib).getextrema())


def resign_safetensors(data: bytes, marker: str) -> bytes:
    """Same tensors, different header metadata: a valid file with a new sha256."""
    n = int.from_bytes(data[:8], "little")
    header = json.loads(data[8 : 8 + n])
    header["__metadata__"] = {**header.get("__metadata__", {}), "selftest": marker}
    raw = json.dumps(header, separators=(",", ":")).encode()
    raw += b" " * (-len(raw) % 8)
    return len(raw).to_bytes(8, "little") + raw + data[8 + n :]


def base_env() -> dict:
    return dict(os.environ)
