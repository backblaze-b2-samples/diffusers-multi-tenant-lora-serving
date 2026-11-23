"""The shared base pipeline and per-request LoRA load, generate, unload.

The base model loads once per worker. Each job loads its adapter under a
job-scoped name, generates with a CPU generator seeded from the job (so any
worker renders the same image), and deletes the adapter again. The pre-build
spike (scripts/spike_lora_swap.py) confirmed `delete_adapters` leaves
`get_list_adapters()` empty and the next base render bit-identical.
"""

import io
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any


class LeaseLost(Exception):
    """Raised from the step callback when the dispatcher took the job back."""


class Engine:
    def __init__(self, pipe: Any, device: str, dtype: str, torch_module: Any = None):
        self.pipe = pipe
        self.device = device
        self.dtype = dtype
        self._torch = torch_module

    @classmethod
    def load(cls, base_model: str, revision: str | None, device: str, dtype: str) -> "Engine":
        import torch
        from diffusers import StableDiffusionXLPipeline

        torch_dtype = getattr(torch, dtype)
        pipe = StableDiffusionXLPipeline.from_pretrained(
            base_model,
            revision=revision,
            torch_dtype=torch_dtype,
            variant="fp16" if torch_dtype == torch.float16 else None,
            use_safetensors=True,
        ).to(device)
        pipe.set_progress_bar_config(disable=True)
        return cls(pipe, device, dtype, torch)

    def load_adapter(self, path: Path, name: str, scale: float) -> None:
        self.pipe.load_lora_weights(str(path), adapter_name=name)
        self.pipe.set_adapters([name], adapter_weights=[scale])

    def unload_adapter(self, name: str) -> list[str]:
        """Delete the adapter and return any adapter names still loaded."""
        if name in self.loaded_adapters():
            self.pipe.delete_adapters(name)
        return self.loaded_adapters()

    def loaded_adapters(self) -> list[str]:
        listed = self.pipe.get_list_adapters() or {}
        return sorted({n for names in listed.values() for n in names})

    def generate(
        self,
        prompt: str,
        negative_prompt: str | None,
        seed: int,
        steps: int,
        width: int,
        height: int,
        on_step: Callable[[int, int], None] | None = None,
    ) -> bytes:
        """Render one PNG. `on_step(step, total)` runs after every denoising step."""
        torch = self._torch
        generator = torch.Generator("cpu").manual_seed(seed) if torch else seed

        def callback(_pipe, step_index, _timestep, kwargs):
            if on_step is not None:
                on_step(step_index + 1, steps)
            return kwargs

        image = self.pipe(
            prompt,
            negative_prompt=negative_prompt or None,
            num_inference_steps=steps,
            width=width,
            height=height,
            generator=generator,
            callback_on_step_end=callback,
        ).images[0]
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
