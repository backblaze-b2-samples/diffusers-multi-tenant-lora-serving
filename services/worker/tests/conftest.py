import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker.api_client import DispatcherClient
from worker.cache import AdapterCache
from worker.pipeline import Engine

ADAPTER_BYTES = b"fake-safetensors-bytes" * 100
ADAPTER_SHA = hashlib.sha256(ADAPTER_BYTES).hexdigest()


class FakeImage:
    def save(self, buf, format):
        buf.write(b"\x89PNG fake")


class FakePipe:
    """Same LoRA surface as a Diffusers pipeline, no torch."""

    def __init__(self, fail_generate=False):
        self.adapters: dict[str, float] = {}
        self.calls: list[tuple] = []
        self.fail_generate = fail_generate

    def load_lora_weights(self, path, adapter_name):
        self.calls.append(("load", adapter_name, Path(path).name))
        self.adapters[adapter_name] = 1.0

    def set_adapters(self, names, adapter_weights):
        self.calls.append(("set", tuple(names), tuple(adapter_weights)))

    def delete_adapters(self, name):
        self.calls.append(("delete", name))
        self.adapters.pop(name, None)

    def get_list_adapters(self):
        return {"unet": list(self.adapters)}

    def __call__(self, prompt, num_inference_steps, callback_on_step_end, **kw):
        self.calls.append(("generate", prompt, kw.get("generator")))
        if self.fail_generate:
            raise RuntimeError("boom")
        for i in range(num_inference_steps):
            callback_on_step_end(self, i, 0, {})
        return SimpleNamespace(images=[FakeImage()])


class FakeDispatcher:
    """Records worker protocol calls and serves the adapter and output URLs."""

    def __init__(self, adapter_bytes=ADAPTER_BYTES):
        self.adapter_bytes = adapter_bytes
        self.requests: list[httpx.Request] = []
        self.heartbeats: list[dict] = []
        self.completed: list[dict] = []
        self.failed: list[dict] = []
        self.uploads: list[bytes] = []
        self.stale = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if request.url.host == "b2.example" and request.method == "GET":
            return httpx.Response(200, content=self.adapter_bytes)
        if request.url.host == "b2.example" and request.method == "PUT":
            self.uploads.append(request.content)
            return httpx.Response(200)
        body = json.loads(request.content or b"{}")
        if self.stale and path.endswith(("/heartbeat", "/complete")):
            return httpx.Response(409, json={"code": "stale_attempt"})
        if path.endswith("/heartbeat"):
            self.heartbeats.append(body)
            return httpx.Response(200, json={"lease_expires_at": "x"})
        if path.endswith("/complete"):
            self.completed.append(body)
            return httpx.Response(200, json={"state": "succeeded", **body})
        if path.endswith("/fail"):
            self.failed.append(body)
            return httpx.Response(200, json={"state": "failed", "error_code": body["code"]})
        return httpx.Response(404)


@pytest.fixture
def dispatcher():
    return FakeDispatcher()


@pytest.fixture
def client(dispatcher):
    http = httpx.Client(transport=httpx.MockTransport(dispatcher.handler))
    return DispatcherClient("http://api.test", "w1", http=http)


@pytest.fixture
def cache(tmp_path):
    return AdapterCache(tmp_path / "cache", max_bytes=10_000_000)


@pytest.fixture
def pipe():
    return FakePipe()


@pytest.fixture
def engine(pipe):
    return Engine(pipe, "cpu", "float32")


def make_job(tenant="acme", adapter=True, sha=ADAPTER_SHA, size=None, attempt=1,
             weight_tenant=None, manifest_tenant=None):
    size = len(ADAPTER_BYTES) if size is None else size
    job = {
        "job_id": "job-abc", "attempt": attempt, "run_id": "run-1", "tenant_id": tenant,
        "output_key": f"p/outputs/{tenant}/run-1/job-abc.png",
        "output_url": "https://b2.example/out?sig=1", "prompt": "a lighthouse",
        "negative_prompt": None, "seed": 42, "steps": 4, "width": 64, "height": 64,
        "adapter": None,
    }
    if adapter:
        wt = weight_tenant or tenant
        job["adapter"] = {
            "tenant_id": manifest_tenant or tenant, "adapter": "pixel-art", "version": "v1",
            "sha256": sha, "size_bytes": size, "base_model": "base", "scale": 0.8,
            "weight_key": f"lora-serving/adapters/{wt}/pixel-art/v1/adapter.safetensors",
            "url": "https://b2.example/w?X-Amz-Signature=abc", "url_expires_at": "x",
        }
    return job
