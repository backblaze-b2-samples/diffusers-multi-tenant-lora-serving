"""Adapter registry routes: publish, read, edit, delete, verify."""

from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, UploadFile

from app.service import registry
from app.service.publish_sources import publish_from_hf, publish_upload
from app.types import (
    AdapterDetail,
    AdapterSource,
    AdapterSummary,
    AdapterUpdate,
    AppError,
    DeleteAdapterResult,
    VerifyResult,
)

router = APIRouter()


@router.get("/tenants/{tenant_id}/adapters", response_model=list[AdapterSummary])
def list_adapters(tenant_id: str):
    return registry.list_adapters(tenant_id)


@router.post("/tenants/{tenant_id}/adapters", response_model=AdapterDetail, status_code=201)
def publish_adapter(
    tenant_id: str,
    adapter: Annotated[str, Form()],
    version: Annotated[str, Form()],
    license: Annotated[str, Form()],
    source: Annotated[Literal["huggingface", "upload"], Form()],
    display_name: Annotated[str | None, Form()] = None,
    default_scale: Annotated[float, Form(ge=0.0, le=2.0)] = 1.0,
    trigger_words: Annotated[str | None, Form(description="Comma separated.")] = None,
    hf_repo_id: Annotated[str | None, Form()] = None,
    hf_filename: Annotated[str | None, Form()] = None,
    hf_revision: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
):
    """Publish a new adapter or a new version. The tenant manifest is written last."""
    inp = registry.PublishInput(
        tenant_id=tenant_id, adapter=adapter, version=version, license=license,
        source=AdapterSource(type=source), display_name=display_name or None,
        default_scale=default_scale,
        trigger_words=[w.strip() for w in (trigger_words or "").split(",") if w.strip()],
    )
    if source == "huggingface":
        return publish_from_hf(inp, hf_repo_id or "", hf_filename or "", hf_revision or None)
    if file is None or not file.filename:
        raise AppError(422, "missing_file", "an uploaded .safetensors file is required")
    return publish_upload(inp, file.file, file.filename)


@router.get("/tenants/{tenant_id}/adapters/{adapter}", response_model=AdapterDetail)
def get_adapter(tenant_id: str, adapter: str):
    return registry.get_adapter(tenant_id, adapter)


@router.patch("/tenants/{tenant_id}/adapters/{adapter}", response_model=AdapterDetail)
def update_adapter(tenant_id: str, adapter: str, patch: AdapterUpdate):
    return registry.update_adapter(tenant_id, adapter, patch)


@router.delete("/tenants/{tenant_id}/adapters/{adapter}", response_model=DeleteAdapterResult)
def delete_adapter(tenant_id: str, adapter: str, confirm: str = ""):
    """Delete every version. `confirm` must equal the adapter name."""
    return registry.delete_adapter(tenant_id, adapter, confirm)


@router.delete(
    "/tenants/{tenant_id}/adapters/{adapter}/versions/{version}",
    response_model=DeleteAdapterResult,
)
def delete_version(tenant_id: str, adapter: str, version: str):
    return registry.delete_version(tenant_id, adapter, version)


@router.post(
    "/tenants/{tenant_id}/adapters/{adapter}/versions/{version}/verify",
    response_model=VerifyResult,
)
def verify_version(tenant_id: str, adapter: str, version: str):
    """Re-read the weight from B2 and compare its sha256 and size to the manifest."""
    return registry.verify_version(tenant_id, adapter, version)
