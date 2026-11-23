"""Pre-build spike: does per-request LoRA load/generate/unload behave on this device?

Run once before trusting the worker on a new machine:

    .venv/bin/python scripts/spike_lora_swap.py --adapter-a <a.safetensors> \
        --adapter-b <b.safetensors> [--out .spike] [--pair]

1. Load the base pipeline, generate one 768 px image (12 steps, fixed seed).
2. Load adapter A, generate, unload; load adapter B, generate, unload; generate
   with no adapter.
3. Assert A, B and base differ pairwise (mean absolute pixel difference > 3/255),
   the post-unload base equals the first base, and no adapter is left loaded.
4. `--pair` additionally starts two worker-sized pipelines in two processes at
   once and records each one's peak device memory.

Prints one JSON object with every number, for the README's correctness evidence.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE = os.getenv("BASE_MODEL", "stabilityai/stable-diffusion-xl-base-1.0")
PROMPT = "a lighthouse on a cliff at sunset"
SEED, STEPS, SIZE = 42, 12, 768


def pick_device() -> str:
    import torch

    forced = os.getenv("TORCH_DEVICE")
    if forced:
        return forced
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load(device: str):
    import torch
    from diffusers import StableDiffusionXLPipeline

    dtype = torch.float16 if device in ("cuda", "mps") else torch.float32
    t = time.perf_counter()
    pipe = StableDiffusionXLPipeline.from_pretrained(
        BASE,
        revision=os.getenv("BASE_MODEL_REVISION") or None,
        torch_dtype=dtype,
        variant="fp16" if dtype == torch.float16 else None,
        use_safetensors=True,
    ).to(device)
    pipe.set_progress_bar_config(disable=True)
    return pipe, int((time.perf_counter() - t) * 1000), str(dtype).replace("torch.", "")


def gen(pipe):
    import numpy as np
    import torch

    t = time.perf_counter()
    img = pipe(
        PROMPT,
        num_inference_steps=STEPS,
        width=SIZE,
        height=SIZE,
        generator=torch.Generator("cpu").manual_seed(SEED),
    ).images[0]
    return np.asarray(img).astype("float32"), img, int((time.perf_counter() - t) * 1000)


def mad(a, b) -> float:
    return float(abs(a - b).mean() / 255.0)


def peak_mem(device: str) -> int:
    import torch

    if device == "mps":
        return int(torch.mps.driver_allocated_memory())
    if device == "cuda":
        return int(torch.cuda.max_memory_allocated())
    return 0


def swap(args) -> dict:
    device = pick_device()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pipe, load_base_ms, dtype = load(device)
    res: dict = {"device": device, "dtype": dtype, "base_model": BASE, "load_base_ms": load_base_ms}
    base1, im, res["gen_base_ms"] = gen(pipe)
    im.save(out / "base1.png")
    res["base_black"] = bool(base1.max() < 5)
    outs = {}
    for tag, path in (("a", args.adapter_a), ("b", args.adapter_b)):
        name = f"job-spike-{tag}"
        t = time.perf_counter()
        pipe.load_lora_weights(path, adapter_name=name)
        pipe.set_adapters([name], adapter_weights=[1.0])
        res[f"load_{tag}_ms"] = int((time.perf_counter() - t) * 1000)
        outs[tag], im, res[f"gen_{tag}_ms"] = gen(pipe)
        im.save(out / f"{tag}.png")
        t = time.perf_counter()
        pipe.delete_adapters(name)
        res[f"unload_{tag}_ms"] = int((time.perf_counter() - t) * 1000)
        res[f"adapters_after_unload_{tag}"] = pipe.get_list_adapters()
    base2, im, _ = gen(pipe)
    im.save(out / "base2.png")
    res["mad_a_base"] = mad(outs["a"], base1)
    res["mad_b_base"] = mad(outs["b"], base1)
    res["mad_a_b"] = mad(outs["a"], outs["b"])
    res["mad_base1_base2"] = mad(base1, base2)
    res["max_px_base1_base2"] = float(abs(base1 - base2).max())
    res["peak_device_bytes"] = peak_mem(device)
    thr = 3 / 255
    left = [
        v
        for d in (res["adapters_after_unload_a"], res["adapters_after_unload_b"])
        for v in d.values()
        if v
    ]
    res["pass"] = bool(
        res["mad_a_base"] > thr
        and res["mad_b_base"] > thr
        and res["mad_a_b"] > thr
        and res["max_px_base1_base2"] <= 1.0
        and not left
        and not res["base_black"]
    )
    return res


def child() -> None:
    device = pick_device()
    pipe, load_ms, _ = load(device)
    _, _, gen_ms = gen(pipe)
    out = {"load_ms": load_ms, "gen_ms": gen_ms, "peak_device_bytes": peak_mem(device)}
    sys.stdout.write(json.dumps(out) + "\n")


def pair() -> dict:
    t = time.perf_counter()
    procs = [
        subprocess.Popen([sys.executable, __file__, "--child"], stdout=subprocess.PIPE, text=True)
        for _ in range(2)
    ]
    results = []
    for p in procs:
        stdout, _ = p.communicate()
        parsed = json.loads(stdout.strip().splitlines()[-1]) if p.returncode == 0 else {}
        results.append({"returncode": p.returncode, **parsed})
    return {
        "pair": results,
        "pair_wall_ms": int((time.perf_counter() - t) * 1000),
        "pair_ok": all(r["returncode"] == 0 for r in results),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter-a")
    ap.add_argument("--adapter-b")
    ap.add_argument("--out", default=".spike")
    ap.add_argument("--pair", action="store_true")
    ap.add_argument("--child", action="store_true")
    args = ap.parse_args()
    if args.child:
        child()
        return
    res = swap(args) if args.adapter_a and args.adapter_b else {}
    if args.pair:
        res.update(pair())
    sys.stdout.write(json.dumps(res, indent=2) + "\n")


if __name__ == "__main__":
    main()
