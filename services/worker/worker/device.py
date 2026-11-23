"""Device selection: CUDA, then Apple MPS, then CPU. `TORCH_DEVICE` overrides."""

from typing import Any


def select_device(override: str | None = None, torch_module: Any = None) -> tuple[str, str]:
    """Return (device, dtype name). fp16 on CUDA and MPS, fp32 on CPU."""
    if torch_module is None:
        import torch as torch_module

    if override:
        device = override
    elif torch_module.cuda.is_available():
        device = "cuda"
    elif getattr(torch_module.backends, "mps", None) and torch_module.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    dtype = "float16" if device.startswith(("cuda", "mps")) else "float32"
    return device, dtype
