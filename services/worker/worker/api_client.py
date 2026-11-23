"""HTTP calls to the dispatcher and to presigned B2 URLs.

Every request carries `User-Agent: b2ai-diffusers-lora-weights-hub worker/<v>`.
The User-Agent is not part of a SigV4 presigned signature, so setting it on
the presigned GET and PUT is safe.
"""

from typing import Any

import httpx

from worker.config import USER_AGENT


class StaleAttempt(Exception):
    """The dispatcher no longer considers this worker's attempt current (409)."""


class DispatcherClient:
    def __init__(self, api_url: str, worker_id: str, token: str = "", http: httpx.Client | None = None):
        headers = {"User-Agent": USER_AGENT}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.worker_id = worker_id
        self.http = http or httpx.Client(timeout=httpx.Timeout(60.0, connect=5.0))
        self._api = api_url.rstrip("/")
        self._headers = headers

    def _post(self, path: str, body: dict[str, Any], timeout: float | None = None) -> dict:
        kwargs: dict[str, Any] = {"json": body, "headers": self._headers}
        if timeout is not None:
            kwargs["timeout"] = timeout
        resp = self.http.post(f"{self._api}{path}", **kwargs)
        if resp.status_code == 409:
            raise StaleAttempt(resp.text)
        resp.raise_for_status()
        return resp.json()

    def register(self, device: str, dtype: str, base_model: str, entries: int, size: int) -> dict:
        return self._post("/worker/register", {
            "worker_id": self.worker_id, "device": device, "dtype": dtype,
            "base_model": base_model, "cache_entries": entries, "cache_bytes": size,
        })

    def claim(self, wait_seconds: int = 25) -> dict | None:
        body = {"worker_id": self.worker_id, "wait_seconds": wait_seconds}
        return self._post("/worker/jobs/claim", body, timeout=wait_seconds + 15.0)["job"]

    def heartbeat(self, job_id: str, attempt: int, step: int | None, total: int | None,
                  phase: str | None = None) -> dict:
        return self._post(f"/worker/jobs/{job_id}/heartbeat", {
            "worker_id": self.worker_id, "attempt": attempt, "step": step, "total_steps": total,
            "phase": phase,
        })

    def complete(self, job_id: str, attempt: int, result: dict[str, Any]) -> dict:
        return self._post(f"/worker/jobs/{job_id}/complete",
                          {"worker_id": self.worker_id, "attempt": attempt, **result})

    def fail(self, job_id: str, attempt: int, code: str, message: str) -> dict:
        return self._post(f"/worker/jobs/{job_id}/fail", {
            "worker_id": self.worker_id, "attempt": attempt, "code": code,
            "message": message[:2000],
        })

    def put_output(self, url: str, png: bytes) -> None:
        """Upload the image through the presigned PUT (signed for image/png)."""
        resp = self.http.put(url, content=png, headers={
            "User-Agent": USER_AGENT, "Content-Type": "image/png",
        })
        if resp.status_code not in (200, 201, 204):
            raise RuntimeError(f"presigned PUT returned HTTP {resp.status_code}")
