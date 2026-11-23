"""Tenant routes: discovery and the raw tenant manifest.

SECURITY: the tenant in the path is trusted as given (no authentication in
this sample). Production puts an authenticating gateway in front that sets it.
"""

from fastapi import APIRouter

from app.service import registry
from app.types import TenantManifest, TenantSummary

router = APIRouter()


@router.get("/tenants", response_model=list[TenantSummary])
def list_tenants():
    return registry.list_tenants()


@router.get("/tenants/{tenant_id}/manifest", response_model=TenantManifest)
def get_tenant_manifest(tenant_id: str):
    return registry.get_manifest(tenant_id)
