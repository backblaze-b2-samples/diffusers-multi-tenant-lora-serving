from typing import Literal

from fastapi import APIRouter

from app.service import jobs
from app.types import FileUrlResponse, Job

router = APIRouter()


@router.get("/jobs", response_model=list[Job])
def list_jobs(
    tenant_id: str | None = None,
    state: Literal["queued", "running", "succeeded", "failed"] | None = None,
):
    return jobs.list_jobs(tenant_id, state)


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str):
    return jobs.get_job(job_id)


@router.get("/jobs/{job_id}/output", response_model=FileUrlResponse)
def get_job_output(job_id: str):
    """A short-lived presigned GET for the job's generated image."""
    return FileUrlResponse(url=jobs.output_url(job_id))
