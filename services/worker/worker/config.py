"""Worker configuration.

A worker holds no storage credentials. It reads only the keys below, from the
process environment and, as a fallback, from the repo-root env file; any other
key in that file (including every storage credential) is never loaded into this
process.
"""

import os
from dataclasses import dataclass
from pathlib import Path

VERSION = "0.1.0"
USER_AGENT = f"b2ai-diffusers-lora-weights-hub worker/{VERSION}"

WORKER_KEYS = (
    "API_URL",
    "WORKER_ID",
    "WORKER_TOKEN",
    "BASE_MODEL",
    "BASE_MODEL_REVISION",
    "ADAPTER_CACHE_DIR",
    "ADAPTER_CACHE_MAX_BYTES",
    "ADAPTER_CACHE_VERIFY_ON_HIT",
    "TORCH_DEVICE",
)

WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = WORKER_ROOT.parents[1]


def _file_values(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines, keeping only the worker's own keys."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        if key in WORKER_KEYS:
            out[key] = value.split(" #", 1)[0].strip().strip('"').strip("'")
    return out


@dataclass(frozen=True)
class WorkerConfig:
    api_url: str
    worker_id: str
    worker_token: str
    base_model: str
    base_model_revision: str | None
    cache_dir: Path
    cache_max_bytes: int
    verify_on_hit: bool
    torch_device: str | None


def load_config(env_file: Path | None = None) -> WorkerConfig:
    values = _file_values(env_file or REPO_ROOT / ".env")
    values.update({k: os.environ[k] for k in WORKER_KEYS if k in os.environ})
    cache_dir = Path(values.get("ADAPTER_CACHE_DIR") or WORKER_ROOT / ".cache" / "adapters")
    if not cache_dir.is_absolute():
        cache_dir = REPO_ROOT / cache_dir
    return WorkerConfig(
        api_url=(values.get("API_URL") or "http://localhost:8000").rstrip("/"),
        worker_id=values.get("WORKER_ID") or f"w-{os.getpid()}",
        worker_token=values.get("WORKER_TOKEN", ""),
        base_model=values.get("BASE_MODEL") or "stabilityai/stable-diffusion-xl-base-1.0",
        base_model_revision=values.get("BASE_MODEL_REVISION") or None,
        cache_dir=cache_dir,
        cache_max_bytes=int(values.get("ADAPTER_CACHE_MAX_BYTES") or 4 * 1024**3),
        verify_on_hit=(values.get("ADAPTER_CACHE_VERIFY_ON_HIT") or "true").lower()
        not in ("0", "false", "no"),
        torch_device=values.get("TORCH_DEVICE") or None,
    )
