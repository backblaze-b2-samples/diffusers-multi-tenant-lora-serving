from typing import Literal

from fastapi import APIRouter

from app.service import library
from app.types import LibraryEntry

router = APIRouter()


@router.get("/library", response_model=list[LibraryEntry])
def list_library(
    tenant_id: str | None = None,
    kind: Literal["adapters", "outputs", "reports"] | None = None,
):
    """Objects under `APP_PREFIX`: adapter weights and manifests, outputs, reports."""
    return library.list_library(tenant_id, kind)
