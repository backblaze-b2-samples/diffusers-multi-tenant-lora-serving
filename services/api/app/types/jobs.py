"""Generation jobs, runs, reports, and the worker protocol."""

from typing import Literal

from pydantic import BaseModel, Field

from app.types.base import ResponseModel

JobState = Literal["queued", "running", "succeeded", "failed"]
CacheResult = Literal["hit", "miss", "none"]
Steps = Literal[15, 25, 40]
Size = Literal[768, 1024]


class GenerationRequest(BaseModel):
    adapter: str | None = Field(
        default=None,
        description="`name`, `name@version`, `owner/name[@version]`, or null for the base model.",
    )
    prompt: str = Field(min_length=1, max_length=1000)
    negative_prompt: str | None = Field(default=None, max_length=1000)
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)
    steps: Steps = 25
    size: Size = 1024
    scale: float | None = Field(default=None, ge=0.0, le=2.0)
    run_id: str | None = None


class CompareRequest(BaseModel):
    tenant_id: str
    adapters: list[str] = Field(min_length=1, max_length=4)
    include_base: bool = True
    prompt: str = Field(min_length=1, max_length=1000)
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)
    steps: Steps = 25
    size: Size = 1024


class JobTimings(ResponseModel):
    fetch_ms: int
    load_ms: int
    generate_ms: int
    unload_ms: int
    total_ms: int


class Job(ResponseModel):
    job_id: str
    run_id: str
    tenant_id: str
    adapter: str | None
    version: str | None
    adapter_sha256: str | None
    scale: float | None
    state: JobState
    attempt: int
    worker_id: str | None
    seed: int
    steps: int
    width: int
    height: int
    prompt: str
    negative_prompt: str | None
    step: int | None = Field(description="Last denoising step a heartbeat reported.")
    timings: JobTimings | None
    cache: CacheResult | None
    bytes_fetched: int | None
    sha256_verified: bool | None
    output_key: str
    output_sha256: str | None
    adapters_after_unload: list[str] | None
    error_code: str | None
    error_message: str | None
    created_at: str
    finished_at: str | None


class RunSummary(ResponseModel):
    run_id: str
    created_at: str
    job_count: int
    state: Literal["active", "done"]
    report_key: str | None


class RunDetail(ResponseModel):
    run_id: str
    created_at: str
    jobs: list[Job]
    report_key: str | None


class ReportJob(ResponseModel):
    job_id: str
    tenant_id: str
    adapter: str | None
    version: str | None
    adapter_sha256: str | None
    worker_id: str | None
    attempt: int
    state: JobState
    cache: CacheResult | None
    bytes_fetched: int
    fetch_ms: int
    load_ms: int
    generate_ms: int
    unload_ms: int
    total_ms: int
    seed: int
    steps: int
    width: int
    height: int
    output_key: str
    output_sha256: str | None
    error_code: str | None = None


class ReportSummary(ResponseModel):
    jobs: int
    succeeded: int
    failed: int
    cache_hits: int
    load_ms_p50: int
    generate_ms_p50: int
    retried_jobs: int


class AdapterReport(ResponseModel):
    """`reports/<run-id>/adapters.json`: per-job timings and cache behaviour."""

    run_id: str
    created_at: str
    base_model: str
    device_summary: list[str]
    jobs: list[ReportJob]
    summary: ReportSummary


class WorkerStatus(ResponseModel):
    worker_id: str
    device: str
    dtype: str
    base_model: str
    last_seen: str
    online: bool
    current_job_id: str | None
    jobs_done: int
    cache_entries: int
    cache_bytes: int


class WorkerHello(BaseModel):
    worker_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    device: str
    dtype: str
    base_model: str
    cache_entries: int = 0
    cache_bytes: int = 0


class WorkerAck(ResponseModel):
    heartbeat_seconds: int
    lease_seconds: int


class ClaimRequest(BaseModel):
    worker_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    wait_seconds: int = Field(default=0, ge=0, le=25)


class WorkerAdapter(ResponseModel):
    tenant_id: str = Field(description="The version manifest's own tenant_id.")
    adapter: str
    version: str
    sha256: str
    size_bytes: int
    base_model: str
    scale: float
    weight_key: str
    url: str
    url_expires_at: str


class WorkerJob(ResponseModel):
    job_id: str
    attempt: int
    run_id: str
    tenant_id: str
    adapter: WorkerAdapter | None
    output_key: str
    output_url: str
    prompt: str
    negative_prompt: str | None
    seed: int
    steps: int
    width: int
    height: int


class ClaimResponse(ResponseModel):
    job: WorkerJob | None


class Heartbeat(BaseModel):
    worker_id: str
    attempt: int
    step: int | None = None
    total_steps: int | None = None


class HeartbeatAck(ResponseModel):
    lease_expires_at: str


class JobCompletion(BaseModel):
    worker_id: str
    attempt: int
    cache: CacheResult
    bytes_fetched: int = Field(ge=0)
    sha256_verified: bool
    fetch_ms: int = Field(ge=0)
    load_ms: int = Field(ge=0)
    generate_ms: int = Field(ge=0)
    unload_ms: int = Field(ge=0)
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    adapters_after_unload: list[str]


class JobFailure(BaseModel):
    worker_id: str
    attempt: int
    code: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    message: str = Field(default="", max_length=2000)
