"""The B2 key layout, in one place. Every builder takes validated identifiers."""

from app.config import settings


def adapters_root() -> str:
    return f"{settings.prefix}adapters/"


def tenant_root(tenant_id: str) -> str:
    return f"{adapters_root()}{tenant_id}/"


def tenant_manifest_key(tenant_id: str) -> str:
    return f"{tenant_root(tenant_id)}manifest.json"


def adapter_root(tenant_id: str, adapter: str) -> str:
    return f"{tenant_root(tenant_id)}{adapter}/"


def version_root(tenant_id: str, adapter: str, version: str) -> str:
    return f"{adapter_root(tenant_id, adapter)}{version}/"


def weight_key(tenant_id: str, adapter: str, version: str) -> str:
    return f"{version_root(tenant_id, adapter, version)}adapter.safetensors"


def version_manifest_key(tenant_id: str, adapter: str, version: str) -> str:
    return f"{version_root(tenant_id, adapter, version)}manifest.json"


def output_key(tenant_id: str, run_id: str, job_id: str) -> str:
    return f"{settings.prefix}outputs/{tenant_id}/{run_id}/{job_id}.png"


def report_key(run_id: str) -> str:
    return f"{settings.prefix}reports/{run_id}/adapters.json"
