"""Tenant-scoped, content-addressed adapter cache with LRU eviction.

Entries live at `<cache_dir>/<tenant>/<sha256>.safetensors`. Keying by tenant
as well as hash means one tenant's request can never be served a file another
tenant's request downloaded, even for identical bytes.
"""

import hashlib
import os
import re
import threading
from pathlib import Path

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class AdapterCache:
    def __init__(self, root: Path, max_bytes: int, verify_on_hit: bool = True):
        self.root = Path(root)
        self.max_bytes = max_bytes
        self.verify_on_hit = verify_on_hit
        self._lock = threading.Lock()

    def path_for(self, tenant_id: str, sha256: str) -> Path:
        if not _NAME_RE.fullmatch(tenant_id) or not _SHA_RE.fullmatch(sha256):
            raise ValueError("invalid tenant or sha256 for a cache path")
        return self.root / tenant_id / f"{sha256}.safetensors"

    def lookup(self, tenant_id: str, sha256: str, size_bytes: int) -> Path | None:
        """Return a verified cached file, or None. A bad entry is removed."""
        path = self.path_for(tenant_id, sha256)
        if not path.is_file():
            return None
        if path.stat().st_size != size_bytes or (
            self.verify_on_hit and sha256_file(path) != sha256
        ):
            path.unlink(missing_ok=True)
            return None
        os.utime(path)  # mark as recently used
        return path

    def entries(self) -> list[Path]:
        return [p for p in self.root.glob("*/*.safetensors") if p.is_file()]

    def stats(self) -> tuple[int, int]:
        files = self.entries()
        return len(files), sum(p.stat().st_size for p in files)

    def evict(self, keep: Path | None = None) -> list[Path]:
        """Drop least-recently-used entries until the cache fits `max_bytes`."""
        removed: list[Path] = []
        with self._lock:
            files = sorted(self.entries(), key=lambda p: p.stat().st_mtime)
            total = sum(p.stat().st_size for p in files)
            for p in files:
                if total <= self.max_bytes:
                    break
                if keep is not None and p == keep:
                    continue
                total -= p.stat().st_size
                p.unlink(missing_ok=True)
                removed.append(p)
        return removed
