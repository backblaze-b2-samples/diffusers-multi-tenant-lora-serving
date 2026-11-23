from fastapi import APIRouter

from app.config import settings
from app.service.workers import workers_online
from app.types import ServerConfig

router = APIRouter()


@router.get("/settings/server", response_model=ServerConfig)
def server_config():
    """Read-only dispatcher configuration for the Settings page."""
    return ServerConfig(
        base_model=settings.base_model,
        app_prefix=settings.prefix,
        adapter_url_ttl_seconds=settings.adapter_url_ttl_seconds,
        output_url_ttl_seconds=settings.output_url_ttl_seconds,
        job_lease_seconds=settings.job_lease_seconds,
        workers_online=workers_online(),
        license_allowlist=list(settings.license_allowlist),
    )
