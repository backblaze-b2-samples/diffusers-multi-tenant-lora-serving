from fastapi import APIRouter

from app.config import settings
from app.repo import check_connectivity
from app.service.workers import workers_online
from app.types import HealthStatus

router = APIRouter()


# Sync `def` so the blocking B2 connectivity check runs in Starlette's
# threadpool rather than on the event loop (see runtime/files.py rationale).
@router.get("/health", response_model=HealthStatus)
def health():
    b2_ok = check_connectivity()
    return HealthStatus(
        status="healthy" if b2_ok else "degraded",
        b2_connected=b2_ok,
        base_model=settings.base_model,
        workers_online=workers_online(),
    )
