"""Resolve a request's adapter through the requesting tenant's own manifest.

Isolation rules, checked before any job exists or any URL is signed:
- `owner/name` with an owner other than the tenant: 403 `cross_tenant_adapter`.
- a name or version missing from this tenant's manifest: 404 `adapter_not_found`
  (the answer never reveals whether another tenant has that name).
- a manifest entry whose keys leave `adapters/<tenant>/`, or whose version
  manifest names another tenant: 403 `manifest_tenant_mismatch`.
- a version manifest for another base model: 422 `base_model_mismatch`.
"""

from dataclasses import dataclass

from app.config import settings
from app.service import keys, manifests
from app.types import AppError
from app.types.identifiers import is_name, parse_adapter_ref


@dataclass(frozen=True)
class ResolvedAdapter:
    tenant_id: str
    manifest_tenant_id: str
    adapter: str
    version: str
    sha256: str
    size_bytes: int
    weight_key: str
    base_model: str
    scale: float


def resolve(tenant_id: str, ref: str | None, scale: float | None) -> ResolvedAdapter | None:
    """Return the resolved adapter, None for the base model, or raise AppError."""
    if not is_name(tenant_id):
        raise AppError(422, "invalid_identifier", "invalid tenant_id")
    if ref is None or ref.strip() == "":
        return None
    try:
        parsed = parse_adapter_ref(ref)
    except ValueError as e:
        raise AppError(422, "invalid_adapter_ref", str(e)) from None
    if parsed.owner is not None and parsed.owner != tenant_id:
        raise AppError(
            403, "cross_tenant_adapter",
            f"tenant '{tenant_id}' cannot use adapters owned by another tenant",
        )
    not_found = AppError(404, "adapter_not_found", f"adapter '{parsed.name}' not found")
    tm = manifests.read_tenant_manifest(tenant_id)
    if tm is None:
        raise not_found
    entry = tm.adapters.get(parsed.name)
    if entry is None:
        raise not_found
    version = parsed.version or entry.current_version
    ve = entry.versions.get(version)
    if ve is None:
        raise not_found
    own_root = keys.tenant_root(tenant_id)
    mismatch = AppError(
        403, "manifest_tenant_mismatch",
        "the tenant manifest points outside this tenant's prefix",
    )
    if tm.tenant_id != tenant_id or not (
        ve.weight_key.startswith(own_root) and ve.manifest_key.startswith(own_root)
    ):
        raise mismatch
    vm = manifests.read_version_manifest(ve.manifest_key)
    if vm is None:
        raise not_found
    if vm.tenant_id != tenant_id or vm.weight_key != ve.weight_key or vm.sha256 != ve.sha256:
        raise mismatch
    if vm.base_model.id != settings.base_model:
        raise AppError(
            422, "base_model_mismatch",
            f"{parsed.name}@{version} targets {vm.base_model.id}, not {settings.base_model}",
        )
    return ResolvedAdapter(
        tenant_id=tenant_id, manifest_tenant_id=vm.tenant_id, adapter=parsed.name,
        version=version, sha256=vm.sha256, size_bytes=vm.size_bytes,
        weight_key=vm.weight_key, base_model=vm.base_model.id,
        scale=scale if scale is not None else entry.default_scale,
    )
