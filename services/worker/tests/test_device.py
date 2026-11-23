from types import SimpleNamespace

from worker.device import select_device


def _torch(cuda=False, mps=False):
    return SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: cuda),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: mps)),
    )


def test_cuda_first():
    assert select_device(None, _torch(cuda=True, mps=True)) == ("cuda", "float16")


def test_mps_second():
    assert select_device(None, _torch(mps=True)) == ("mps", "float16")


def test_cpu_fallback_fp32():
    assert select_device(None, _torch()) == ("cpu", "float32")


def test_override_wins():
    assert select_device("cpu", _torch(cuda=True)) == ("cpu", "float32")
    assert select_device("mps", _torch()) == ("mps", "float16")
