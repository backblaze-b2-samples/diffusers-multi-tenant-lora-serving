"""Download a pinned adapter file from the Hugging Face Hub for publishing.

Third-party client containment: `huggingface_hub` is imported only here (see
tests/test_structure.py).
"""

from pathlib import Path

from app.config import settings


def download_adapter(repo_id: str, filename: str, revision: str | None) -> Path:
    """Fetch one file into the local Hub cache and return its path.

    Raises RuntimeError with a readable reason on any Hub failure (missing
    repo, file or revision, gated access without a token).
    """
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import HfHubHTTPError

    try:
        path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            revision=revision or None,
            token=settings.hf_token or None,
        )
    except (HfHubHTTPError, OSError, ValueError) as e:
        raise RuntimeError(f"Hugging Face download failed for {repo_id}/{filename}: {e}") from e
    return Path(path)


def card_base_model(repo_id: str, revision: str | None) -> str | None:
    """The base model the model card declares, or None when it declares none."""
    from huggingface_hub import model_info
    from huggingface_hub.errors import HfHubHTTPError

    try:
        info = model_info(repo_id, revision=revision or None, token=settings.hf_token or None)
    except (HfHubHTTPError, OSError, ValueError) as e:
        raise RuntimeError(f"Hugging Face lookup failed for {repo_id}: {e}") from e
    base = getattr(info.card_data, "base_model", None) if info.card_data else None
    if isinstance(base, list):
        base = base[0] if base else None
    return base
