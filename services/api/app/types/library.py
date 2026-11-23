from typing import Literal

from app.types.base import ResponseModel

LibraryKind = Literal["adapters", "outputs", "reports"]


class LibraryEntry(ResponseModel):
    """One object the app wrote under `APP_PREFIX`, classified by its key."""

    key: str
    tenant_id: str | None = None
    kind: LibraryKind
    adapter: str | None = None
    version: str | None = None
    run_id: str | None = None
    size_bytes: int
    last_modified: str


class ServerConfig(ResponseModel):
    base_model: str
    app_prefix: str
    adapter_url_ttl_seconds: int
    output_url_ttl_seconds: int
    job_lease_seconds: int
    workers_online: int
    license_allowlist: list[str]
