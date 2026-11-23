"""Read and write tenant and version manifests, with a short ETag-checked cache.

Requests resolve through `adapters/<tenant>/manifest.json`. Reading it on every
request costs a B2 GET, so a copy is reused for `_TTL` seconds and then
revalidated with a cheap HEAD: an unchanged ETag keeps the copy. This
dispatcher's own writes replace the cached copy immediately.
"""

import time
from datetime import UTC, datetime
from threading import Lock

from app.repo import adapter_store
from app.service import keys
from app.types import TenantManifest, VersionManifest

_TTL = 10.0
_cache: dict[str, tuple[float, str, TenantManifest | None]] = {}
_vcache: dict[str, tuple[float, str, VersionManifest | None]] = {}
_lock = Lock()


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cached_read(key, cache, model):
    now = time.monotonic()
    with _lock:
        hit = cache.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[2]
    if hit:
        meta = adapter_store.head(key)
        etag = meta[1] if meta else ""
        if etag == hit[1]:
            with _lock:
                cache[key] = (now, hit[1], hit[2])
            return hit[2]
    got = adapter_store.get_json(key)
    value = model.model_validate(got[0]) if got else None
    with _lock:
        cache[key] = (now, got[1] if got else "", value)
    return value


def read_tenant_manifest(tenant_id: str) -> TenantManifest | None:
    return _cached_read(keys.tenant_manifest_key(tenant_id), _cache, TenantManifest)


def read_version_manifest(key: str) -> VersionManifest | None:
    return _cached_read(key, _vcache, VersionManifest)


def write_tenant_manifest(manifest: TenantManifest) -> None:
    key = keys.tenant_manifest_key(manifest.tenant_id)
    manifest.updated_at = now_iso()
    adapter_store.put_json(key, manifest.model_dump(mode="json"))
    with _lock:
        _cache.pop(key, None)


def write_version_manifest(manifest: VersionManifest) -> str:
    key = keys.version_manifest_key(manifest.tenant_id, manifest.adapter, manifest.version)
    adapter_store.put_json(key, manifest.model_dump(mode="json"))
    with _lock:
        _vcache.pop(key, None)
    return key


def forget(tenant_id: str | None = None) -> None:
    """Drop cached manifests (all, or one tenant's)."""
    with _lock:
        if tenant_id is None:
            _cache.clear()
            _vcache.clear()
            return
        root = keys.tenant_root(tenant_id)
        for c in (_cache, _vcache):
            for k in [k for k in c if k.startswith(root)]:
                c.pop(k, None)
