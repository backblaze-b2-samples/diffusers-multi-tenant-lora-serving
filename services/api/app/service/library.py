"""Library: every object the app wrote under `APP_PREFIX`, classified by key.

Keys follow the layout in `service/keys.py`:
`adapters/<tenant>/<adapter>/<version>/...`, `adapters/<tenant>/manifest.json`,
`outputs/<tenant>/<run-id>/<job-id>.png`, `reports/<run-id>/adapters.json`.
"""

from app.config import settings
from app.repo import adapter_store
from app.types import AppError, LibraryEntry
from app.types.identifiers import is_name

KINDS = ("adapters", "outputs", "reports")


def _classify(key: str, obj: dict) -> LibraryEntry | None:
    rest = key[len(settings.prefix):]
    parts = rest.split("/")
    kind = parts[0]
    if kind not in KINDS:
        return None
    entry = {
        "key": key, "kind": kind, "size_bytes": int(obj["Size"]),
        "last_modified": obj["LastModified"].strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if kind == "adapters" and len(parts) >= 3:
        entry["tenant_id"] = parts[1]
        if len(parts) >= 5:
            entry["adapter"], entry["version"] = parts[2], parts[3]
    elif kind == "outputs" and len(parts) >= 4:
        entry["tenant_id"], entry["run_id"] = parts[1], parts[2]
    elif kind == "reports" and len(parts) >= 3:
        entry["run_id"] = parts[1]
    return LibraryEntry(**entry)


def list_library(tenant_id: str | None, kind: str | None) -> list[LibraryEntry]:
    if tenant_id is not None and not is_name(tenant_id):
        raise AppError(422, "invalid_identifier", "invalid tenant_id")
    if kind is not None and kind not in KINDS:
        raise AppError(422, "invalid_kind", f"kind must be one of {', '.join(KINDS)}")
    kinds = [kind] if kind else list(KINDS)
    out: list[LibraryEntry] = []
    for k in kinds:
        prefix = f"{settings.prefix}{k}/"
        if tenant_id and k != "reports":
            prefix += f"{tenant_id}/"
        for obj in adapter_store.iter_objects(prefix):
            e = _classify(obj["Key"], obj)
            if e is not None:
                out.append(e)
    out.sort(key=lambda e: e.last_modified, reverse=True)
    return out
