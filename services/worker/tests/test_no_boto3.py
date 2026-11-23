"""Workers hold no storage credentials and never talk to B2 except by presigned URL."""

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "worker"
REQS = Path(__file__).resolve().parents[1] / "requirements.txt"


def _sources():
    return list(PKG.rglob("*.py"))


def test_worker_never_imports_boto3():
    for f in _sources():
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            assert not any(n.split(".")[0] in ("boto3", "botocore", "s3fs") for n in names), f


def test_worker_never_reads_b2_settings():
    for f in _sources():
        assert "B2_" not in f.read_text(), f"{f} references a B2_* setting"


def test_boto3_not_a_worker_dependency():
    lines = [ln for ln in REQS.read_text().lower().splitlines() if not ln.startswith("#")]
    assert not any("boto3" in ln for ln in lines)


def test_config_ignores_b2_keys_in_env_file(tmp_path, monkeypatch):
    from worker.config import load_config

    env = tmp_path / "env"
    key_name = "B2_" + "APPLICATION_KEY"
    env.write_text(f"{key_name}=secret\nAPI_URL=http://api.test:9\nWORKER_ID=w7\n")
    monkeypatch.delenv("API_URL", raising=False)
    monkeypatch.delenv("WORKER_ID", raising=False)
    cfg = load_config(env)
    assert cfg.api_url == "http://api.test:9" and cfg.worker_id == "w7"
    assert "secret" not in repr(cfg)
