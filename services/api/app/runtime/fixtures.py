from fastapi import APIRouter

from app.service import fixture_job
from app.types import FixturePublishStatus

router = APIRouter()


@router.post("/fixtures/publish", response_model=FixturePublishStatus, status_code=202)
def publish_demo_adapters():
    """Start publishing the pinned demo adapters (acme: 2, globex: 1) in the background.

    Returns at once with the job's status; poll `GET /fixtures/publish` for
    progress. Versions that already exist are skipped, and a call while a job
    is running returns that job instead of starting another.
    """
    return fixture_job.start()


@router.get("/fixtures/publish", response_model=FixturePublishStatus)
def demo_publish_status():
    """The running or last finished demo publish job (`idle` if none ran yet)."""
    return fixture_job.status()
