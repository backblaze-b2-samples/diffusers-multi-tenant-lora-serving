"""Generation requests: one tenant, one adapter (or the base model)."""

import logging

from fastapi import APIRouter

from app.runtime.metrics import record_rejection
from app.service import jobs
from app.types import AppError, GenerationRequest, Job

logger = logging.getLogger(__name__)
router = APIRouter()

REJECTION_CODES = {
    "cross_tenant_adapter", "adapter_not_found", "manifest_tenant_mismatch",
    "base_model_mismatch",
}


@router.post("/tenants/{tenant_id}/generations", response_model=Job, status_code=202)
def create_generation(tenant_id: str, req: GenerationRequest):
    """Resolve the adapter through this tenant's manifest and queue one job.

    Rejections create no job and sign no URL: 403 `cross_tenant_adapter` or
    `manifest_tenant_mismatch`, 404 `adapter_not_found`, 422 `base_model_mismatch`.
    """
    try:
        return jobs.enqueue_generation(tenant_id, req)
    except AppError as e:
        if e.code in REJECTION_CODES:
            record_rejection(e.code)
            logger.warning("generation rejected tenant=%s code=%s", tenant_id, e.code)
        raise
