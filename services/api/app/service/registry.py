"""Adapter registry: publish, list, edit, delete and verify tenant adapters.

Publish order is the safety rule: validate, upload the weight while hashing,
check its size with HEAD, write the version manifest, and only then rewrite
the tenant manifest. A failure before the last step leaves the tenant manifest
untouched, so no request can resolve to a half-published version.
One dispatcher owns manifest writes; a per-tenant lock serializes them.
"""

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock
from typing import BinaryIO

from app.config import settings
from app.repo import adapter_store
from app.service import keys, manifests
from app.service.safetensors_check import NotSafetensorsError, validate_safetensors
from app.types import (
    AdapterDetail,
    AdapterSource,
    AdapterSummary,
    AdapterUpdate,
    AdapterVersion,
    AppError,
    BaseModelRef,
    DeleteAdapterResult,
    TenantAdapterEntry,
    TenantManifest,
    TenantSummary,
    TenantVersionEntry,
    VerifyResult,
    VersionManifest,
)
from app.types.identifiers import is_name, is_version

logger = logging.getLogger(__name__)
_tenant_locks: dict[str, Lock] = defaultdict(Lock)


@dataclass
class PublishInput:
    tenant_id: str
    adapter: str
    version: str
    license: str
    source: AdapterSource
    display_name: str | None = None
    default_scale: float = 1.0
    trigger_words: list[str] = field(default_factory=list)


def check_name(value: str, what: str) -> None:
    if not is_name(value):
        raise AppError(422, "invalid_identifier", f"{what} must match [a-z0-9-], 3-40 chars")


def _check_version(value: str) -> None:
    if not is_version(value):
        raise AppError(422, "invalid_identifier", "version must look like v1, v1.2 or v1.2.3")


def _manifest_or_404(tenant_id: str) -> TenantManifest:
    check_name(tenant_id, "tenant_id")
    m = manifests.read_tenant_manifest(tenant_id)
    if m is None:
        raise AppError(404, "tenant_not_found", f"tenant '{tenant_id}' has no adapters")
    return m


def _entry_or_404(m: TenantManifest, adapter: str) -> TenantAdapterEntry:
    entry = m.adapters.get(adapter)
    if entry is None:
        raise AppError(404, "adapter_not_found", f"adapter '{adapter}' not found")
    return entry


def publish(
    inp: PublishInput,
    fileobj: BinaryIO,
    size: int,
    filename: str,
    on_bytes: Callable[[int], None] | None = None,
) -> AdapterDetail:
    """Publish one version. `on_bytes` reports upload progress (see adapter_store)."""
    check_name(inp.tenant_id, "tenant_id")
    check_name(inp.adapter, "adapter")
    _check_version(inp.version)
    if inp.license not in settings.license_allowlist:
        raise AppError(422, "license_not_allowed", f"license '{inp.license}' is not in the allowlist")
    if not filename.lower().endswith(".safetensors"):
        raise AppError(422, "not_safetensors", "only .safetensors adapters are accepted")
    if size > settings.max_adapter_bytes:
        raise AppError(413, "adapter_too_large", "adapter file exceeds MAX_ADAPTER_BYTES")
    try:
        validate_safetensors(fileobj, size)
    except NotSafetensorsError as e:
        raise AppError(422, "not_safetensors", str(e)) from None

    t, a, v = inp.tenant_id, inp.adapter, inp.version
    with _tenant_locks[t]:
        current = manifests.read_tenant_manifest(t)
        if current and v in current.adapters.get(a, _EMPTY).versions:
            raise AppError(409, "version_exists", f"{a}@{v} already exists; publish a new version")
        wkey = keys.weight_key(t, a, v)
        if adapter_store.head(keys.version_manifest_key(t, a, v)) is not None:
            raise AppError(409, "version_exists", f"{a}@{v} already exists in storage")
        try:
            sha256, sent = adapter_store.upload_stream(
                wkey, fileobj, "application/octet-stream", on_bytes
            )
        except RuntimeError as e:
            logger.error("adapter upload failed tenant=%s adapter=%s version=%s: %s", t, a, v, e)
            raise AppError(
                502, "b2_upload_failed",
                f"Uploading {t}/{a}@{v} to B2 did not finish: the connection to B2 timed out "
                "or was dropped. Nothing was published; check your network and retry.",
            ) from None
        stored = adapter_store.head(wkey)
        if sent != size or stored is None or stored[0] != size:
            raise AppError(502, "upload_size_mismatch", "stored weight size does not match")
        vm = VersionManifest(
            tenant_id=t, adapter=a, version=v, weight_key=wkey, sha256=sha256, size_bytes=size,
            base_model=BaseModelRef(id=settings.base_model), default_scale=inp.default_scale,
            trigger_words=inp.trigger_words, license=inp.license, source=inp.source,
            published_at=manifests.now_iso(),
        )
        mkey = manifests.write_version_manifest(vm)
        tm = current or TenantManifest(tenant_id=t, updated_at=manifests.now_iso())
        entry = tm.adapters.get(a)
        ventry = TenantVersionEntry(
            manifest_key=mkey, weight_key=wkey, sha256=sha256, size_bytes=size,
            base_model=vm.base_model, published_at=vm.published_at, license=vm.license,
            source=vm.source,
        )
        if entry is None:
            entry = TenantAdapterEntry(
                display_name=inp.display_name or a, default_scale=inp.default_scale,
                trigger_words=inp.trigger_words, current_version=v, versions={},
            )
            tm.adapters[a] = entry
        entry.versions[v] = ventry
        entry.current_version = v
        manifests.write_tenant_manifest(tm)  # LAST: the version becomes resolvable here
    logger.info("adapter published tenant=%s adapter=%s version=%s sha256=%s", t, a, v, sha256)
    return _detail(tm, a)


_EMPTY = TenantAdapterEntry(display_name="", current_version="", versions={})


def _detail(m: TenantManifest, adapter: str) -> AdapterDetail:
    e = _entry_or_404(m, adapter)
    cur = e.versions.get(e.current_version)
    versions = [
        AdapterVersion(
            version=v, sha256=ve.sha256, size_bytes=ve.size_bytes, base_model=ve.base_model,
            published_at=ve.published_at, source=ve.source, license=ve.license,
            manifest_key=ve.manifest_key, weight_key=ve.weight_key,
            is_current=v == e.current_version,
        )
        for v, ve in sorted(e.versions.items(), key=lambda kv: kv[1].published_at, reverse=True)
    ]
    return AdapterDetail(
        tenant_id=m.tenant_id, adapter=adapter, display_name=e.display_name,
        current_version=e.current_version, default_scale=e.default_scale,
        trigger_words=e.trigger_words, license=cur.license if cur else "",
        size_bytes=cur.size_bytes if cur else 0, versions=versions,
    )


def get_adapter(tenant_id: str, adapter: str) -> AdapterDetail:
    return _detail(_manifest_or_404(tenant_id), adapter)


def list_adapters(tenant_id: str) -> list[AdapterSummary]:
    check_name(tenant_id, "tenant_id")
    m = manifests.read_tenant_manifest(tenant_id)
    if m is None:
        return []
    out = []
    for name, e in sorted(m.adapters.items()):
        cur = e.versions.get(e.current_version)
        out.append(AdapterSummary(
            tenant_id=tenant_id, adapter=name, display_name=e.display_name,
            current_version=e.current_version, version_count=len(e.versions),
            default_scale=e.default_scale, license=cur.license if cur else "",
            size_bytes=cur.size_bytes if cur else 0,
        ))
    return out


def list_tenants() -> list[TenantSummary]:
    out = []
    for p in adapter_store.list_child_prefixes(keys.adapters_root()):
        tenant_id = p.rstrip("/").rsplit("/", 1)[-1]
        if not is_name(tenant_id):
            continue
        m = manifests.read_tenant_manifest(tenant_id)
        if m is None:
            continue
        versions = [ve for e in m.adapters.values() for ve in e.versions.values()]
        out.append(TenantSummary(
            tenant_id=tenant_id, adapter_count=len(m.adapters), version_count=len(versions),
            total_bytes=sum(ve.size_bytes for ve in versions), updated_at=m.updated_at,
        ))
    return out


def get_manifest(tenant_id: str) -> TenantManifest:
    return _manifest_or_404(tenant_id)


def update_adapter(tenant_id: str, adapter: str, patch: AdapterUpdate) -> AdapterDetail:
    with _tenant_locks[tenant_id]:
        m = _manifest_or_404(tenant_id)
        e = _entry_or_404(m, adapter)
        if patch.current_version is not None:
            if patch.current_version not in e.versions:
                raise AppError(422, "version_not_found", "current_version must be a published version")
            e.current_version = patch.current_version
        if patch.display_name is not None:
            e.display_name = patch.display_name
        if patch.default_scale is not None:
            e.default_scale = patch.default_scale
        if patch.trigger_words is not None:
            e.trigger_words = [w.strip() for w in patch.trigger_words if w.strip()]
        manifests.write_tenant_manifest(m)
    return _detail(m, adapter)


def _delete_prefix(prefix: str) -> list[str]:
    victims = [o["Key"] for o in adapter_store.iter_objects(prefix)]
    if any(not k.startswith(prefix) for k in victims):  # scope guard
        raise RuntimeError(f"refusing to delete keys outside {prefix}")
    return adapter_store.delete_keys(victims) if victims else []


def delete_adapter(tenant_id: str, adapter: str, confirm: str) -> DeleteAdapterResult:
    check_name(adapter, "adapter")
    if confirm != adapter:
        raise AppError(422, "confirmation_mismatch", "confirm must equal the adapter name")
    with _tenant_locks[tenant_id]:
        m = _manifest_or_404(tenant_id)
        _entry_or_404(m, adapter)
        del m.adapters[adapter]
        manifests.write_tenant_manifest(m)  # stop resolving first, then remove bytes
        deleted = _delete_prefix(keys.adapter_root(tenant_id, adapter))
    logger.info("adapter deleted tenant=%s adapter=%s keys=%d", tenant_id, adapter, len(deleted))
    return DeleteAdapterResult(deleted_keys=deleted)


def delete_version(tenant_id: str, adapter: str, version: str) -> DeleteAdapterResult:
    _check_version(version)
    with _tenant_locks[tenant_id]:
        m = _manifest_or_404(tenant_id)
        e = _entry_or_404(m, adapter)
        if version not in e.versions:
            raise AppError(404, "version_not_found", f"{adapter}@{version} not found")
        if version == e.current_version and len(e.versions) > 1:
            raise AppError(409, "current_version", "make another version current before deleting this one")
        del e.versions[version]
        if not e.versions:
            del m.adapters[adapter]
        manifests.write_tenant_manifest(m)
        deleted = _delete_prefix(keys.version_root(tenant_id, adapter, version))
    return DeleteAdapterResult(deleted_keys=deleted)


def verify_version(tenant_id: str, adapter: str, version: str) -> VerifyResult:
    m = _manifest_or_404(tenant_id)
    ve = _entry_or_404(m, adapter).versions.get(version)
    if ve is None:
        raise AppError(404, "version_not_found", f"{adapter}@{version} not found")
    got = adapter_store.hash_object(ve.weight_key)
    sha, size = got if got else ("", 0)
    return VerifyResult(
        sha256_expected=ve.sha256, sha256_actual=sha, size_expected=ve.size_bytes,
        size_actual=size, match=sha == ve.sha256 and size == ve.size_bytes,
    )
