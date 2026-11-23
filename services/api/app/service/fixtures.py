"""Publish the demo adapter set from `fixtures/adapters.yaml`.

Shared by `scripts/publish_fixtures.py` and the UI's "Publish demo adapters"
button. Each pinned file's sha256 is checked against the fixture before it is
published, and versions that already exist are skipped, so re-running is safe.
"""

import hashlib
from pathlib import Path

import yaml

from app.repo import hf_source
from app.service import manifests
from app.service.registry import PublishInput, publish
from app.types import AdapterDetail, AdapterSource, AppError

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures" / "adapters.yaml"


def load_fixtures(path: Path = FIXTURES) -> list[dict]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [{**e, "tenant_id": t} for t, entries in doc["tenants"].items() for e in entries]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def publish_fixtures(path: Path = FIXTURES) -> list[AdapterDetail]:
    """Publish every fixture not yet published. Returns the adapters touched."""
    out: list[AdapterDetail] = []
    for fx in load_fixtures(path):
        tm = manifests.read_tenant_manifest(fx["tenant_id"])
        entry = tm.adapters.get(fx["adapter"]) if tm else None
        if entry and fx["version"] in entry.versions:
            continue
        try:
            local = hf_source.download_adapter(fx["repo_id"], fx["filename"], fx["revision"])
        except RuntimeError as e:
            raise AppError(502, "source_unavailable", str(e)) from None
        if _sha256(local) != fx["sha256"]:
            raise AppError(502, "fixture_checksum", f"{fx['repo_id']} does not match its pinned sha256")
        inp = PublishInput(
            tenant_id=fx["tenant_id"], adapter=fx["adapter"], version=fx["version"],
            license=fx["license"], display_name=fx.get("display_name"),
            default_scale=float(fx.get("default_scale", 1.0)),
            trigger_words=list(fx.get("trigger_words", [])),
            source=AdapterSource(type="huggingface", repo_id=fx["repo_id"],
                                 revision=fx["revision"], filename=fx["filename"]),
        )
        with local.open("rb") as f:
            out.append(publish(inp, f, local.stat().st_size, fx["filename"]))
    return out
