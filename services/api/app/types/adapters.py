"""Adapter registry models: manifests as stored in B2, and API views of them."""

from typing import Literal

from pydantic import BaseModel, Field

from app.types.base import ResponseModel


class BaseModelRef(BaseModel):
    id: str
    revision: str | None = None


class AdapterSource(BaseModel):
    type: Literal["huggingface", "upload"]
    repo_id: str | None = None
    revision: str | None = None
    filename: str | None = None


class VersionManifest(BaseModel):
    """`adapters/<tenant>/<adapter>/<version>/manifest.json`. Immutable once written."""

    schema_version: int = 1
    tenant_id: str
    adapter: str
    version: str
    weight_key: str
    format: Literal["safetensors"] = "safetensors"
    sha256: str
    size_bytes: int
    base_model: BaseModelRef
    default_scale: float = 1.0
    trigger_words: list[str] = Field(default_factory=list)
    license: str
    source: AdapterSource
    published_at: str


class TenantVersionEntry(BaseModel):
    manifest_key: str
    weight_key: str
    sha256: str
    size_bytes: int
    base_model: BaseModelRef
    published_at: str = ""
    license: str = ""
    source: AdapterSource | None = None


class TenantAdapterEntry(BaseModel):
    display_name: str
    default_scale: float = 1.0
    trigger_words: list[str] = Field(default_factory=list)
    current_version: str
    versions: dict[str, TenantVersionEntry]


class TenantManifest(BaseModel):
    """`adapters/<tenant>/manifest.json`: the only index requests resolve through.

    Written LAST on every publish, so a request never resolves to a version
    whose weight or version manifest is not already in B2.
    """

    schema_version: int = 1
    tenant_id: str
    updated_at: str
    adapters: dict[str, TenantAdapterEntry] = Field(default_factory=dict)


class TenantSummary(ResponseModel):
    tenant_id: str
    adapter_count: int
    version_count: int
    total_bytes: int
    updated_at: str


class AdapterSummary(ResponseModel):
    tenant_id: str
    adapter: str
    display_name: str
    current_version: str
    version_count: int
    default_scale: float
    license: str
    size_bytes: int = Field(description="Size of the current version's weight file.")


class AdapterVersion(ResponseModel):
    version: str
    sha256: str
    size_bytes: int
    base_model: BaseModelRef
    published_at: str
    source: AdapterSource | None = None
    license: str
    manifest_key: str
    weight_key: str
    is_current: bool


class AdapterDetail(ResponseModel):
    tenant_id: str
    adapter: str
    display_name: str
    current_version: str
    default_scale: float
    trigger_words: list[str]
    license: str
    size_bytes: int
    versions: list[AdapterVersion]


class AdapterUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    default_scale: float | None = Field(default=None, ge=0.0, le=2.0)
    trigger_words: list[str] | None = None
    current_version: str | None = None


class DeleteAdapterResult(ResponseModel):
    deleted_keys: list[str]


class VerifyResult(ResponseModel):
    sha256_expected: str
    sha256_actual: str
    size_expected: int
    size_actual: int
    match: bool
