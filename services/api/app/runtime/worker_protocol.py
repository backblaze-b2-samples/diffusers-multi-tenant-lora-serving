"""The worker protocol: register, claim, heartbeat, complete, fail.

Workers hold no B2 credentials. When `WORKER_TOKEN` is set every route here
requires `Authorization: Bearer <token>`; unset, they are open (local demo,
`pnpm doctor` warns).
"""

import hmac

from fastapi import APIRouter, Depends, Header

from app.config import settings
from app.service import jobs, workers
from app.types import (
    AppError,
    ClaimRequest,
    ClaimResponse,
    Heartbeat,
    HeartbeatAck,
    Job,
    JobCompletion,
    JobFailure,
    WorkerAck,
    WorkerHello,
)


def require_worker_token(authorization: str | None = Header(default=None)) -> None:
    expected = settings.worker_token
    if not expected:
        return
    given = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(given.encode(), expected.encode()):
        raise AppError(401, "worker_unauthorized", "missing or wrong worker token")


router = APIRouter(prefix="/worker", dependencies=[Depends(require_worker_token)])


@router.post("/register", response_model=WorkerAck)
def register(hello: WorkerHello):
    return workers.register(hello)


@router.post("/jobs/claim", response_model=ClaimResponse)
def claim(req: ClaimRequest):
    """Long poll (up to `wait_seconds`) for the oldest queued job. URLs are signed here."""
    return jobs.claim(req.worker_id, req.wait_seconds)


@router.post("/jobs/{job_id}/heartbeat", response_model=HeartbeatAck)
def heartbeat(job_id: str, hb: Heartbeat):
    return jobs.heartbeat(job_id, hb)


@router.post("/jobs/{job_id}/complete", response_model=Job)
def complete(job_id: str, body: JobCompletion):
    return jobs.complete(job_id, body)


@router.post("/jobs/{job_id}/fail", response_model=Job)
def fail(job_id: str, body: JobFailure):
    return jobs.fail(job_id, body)
