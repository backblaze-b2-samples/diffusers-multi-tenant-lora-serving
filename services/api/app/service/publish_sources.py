"""Where a published adapter file comes from: a pinned Hugging Face file or an upload."""

from pathlib import Path
from typing import BinaryIO

from app.config import settings
from app.repo import hf_source
from app.service.registry import PublishInput, publish
from app.types import AdapterDetail, AdapterSource, AppError


def publish_from_hf(
    inp: PublishInput, repo_id: str, filename: str, revision: str | None
) -> AdapterDetail:
    """Download one pinned file and publish it. 422 when the card names another base."""
    if not repo_id or not filename:
        raise AppError(422, "missing_source", "hf_repo_id and hf_filename are required")
    try:
        base = hf_source.card_base_model(repo_id, revision)
        if base and base != settings.base_model:
            raise AppError(
                422, "base_model_mismatch",
                f"{repo_id} is a LoRA for {base}, not {settings.base_model}",
            )
        path: Path = hf_source.download_adapter(repo_id, filename, revision)
    except RuntimeError as e:
        raise AppError(502, "source_unavailable", str(e)) from None
    inp.source = AdapterSource(
        type="huggingface", repo_id=repo_id, revision=revision, filename=filename
    )
    with path.open("rb") as f:
        return publish(inp, f, path.stat().st_size, filename)


def publish_upload(inp: PublishInput, fileobj: BinaryIO, filename: str) -> AdapterDetail:
    fileobj.seek(0, 2)
    size = fileobj.tell()
    fileobj.seek(0)
    inp.source = AdapterSource(type="upload", filename=filename)
    return publish(inp, fileobj, size, filename)
