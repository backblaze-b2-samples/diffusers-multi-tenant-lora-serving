import hashlib

import httpx
import pytest

from worker.config import USER_AGENT
from worker.fetch import ChecksumMismatch, FetchFailed, download_verified

DATA = b"adapter" * 1000
SHA = hashlib.sha256(DATA).hexdigest()


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_user_agent_on_presigned_get(tmp_path):
    seen = []

    def handler(req):
        seen.append(req.headers["user-agent"])
        return httpx.Response(200, content=DATA)

    n = download_verified(_client(handler), "https://b2.example/x", tmp_path / "a", SHA, len(DATA))
    assert n == len(DATA)
    assert seen == [USER_AGENT]
    assert USER_AGENT.startswith("b2ai-diffusers-lora-weights-hub worker/")


def test_size_mismatch_raises_and_cleans_up(tmp_path):
    client = _client(lambda req: httpx.Response(200, content=DATA[:-1]))
    with pytest.raises(ChecksumMismatch):
        download_verified(client, "https://b2.example/x", tmp_path / "a", SHA, len(DATA))
    assert list(tmp_path.iterdir()) == []


def test_sha_mismatch_raises(tmp_path):
    bad = b"x" * len(DATA)
    client = _client(lambda req: httpx.Response(200, content=bad))
    with pytest.raises(ChecksumMismatch):
        download_verified(client, "https://b2.example/x", tmp_path / "a", SHA, len(DATA))
    assert not (tmp_path / "a").exists()


def test_http_error_leaves_no_partial(tmp_path):
    client = _client(lambda req: httpx.Response(403, content=b"expired"))
    with pytest.raises(FetchFailed):
        download_verified(client, "https://b2.example/x", tmp_path / "a", SHA, len(DATA))
    assert list(tmp_path.iterdir()) == []


def test_put_output_sends_user_agent_and_png_type(client, dispatcher):
    client.put_output("https://b2.example/out", b"png")
    req = next(r for r in dispatcher.requests if r.method == "PUT")
    assert req.headers["user-agent"] == USER_AGENT
    assert req.headers["content-type"] == "image/png"
