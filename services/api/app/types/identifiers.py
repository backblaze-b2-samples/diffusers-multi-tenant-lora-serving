"""Identifier rules shared by every layer.

Tenant and adapter names become key segments, so validation is what keeps a
request from escaping its prefix: anything outside these patterns is rejected
before a key is ever built.
"""

import re
from dataclasses import dataclass

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")
VERSION_RE = re.compile(r"^v[0-9]+(\.[0-9]+){0,2}$")
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,62}[a-z0-9]$")


def is_name(value: str) -> bool:
    return bool(NAME_RE.fullmatch(value or ""))


def is_version(value: str) -> bool:
    return bool(VERSION_RE.fullmatch(value or ""))


def is_run_id(value: str) -> bool:
    return bool(RUN_ID_RE.fullmatch(value or ""))


@dataclass(frozen=True)
class AdapterRef:
    """A parsed adapter reference: `name`, `name@version`, `owner/name[@version]`."""

    owner: str | None
    name: str
    version: str | None


def parse_adapter_ref(ref: str) -> AdapterRef:
    """Parse a request's adapter reference. Raises ValueError on a bad shape."""
    text = (ref or "").strip()
    owner: str | None = None
    if "/" in text:
        owner, _, text = text.partition("/")
        if not is_name(owner):
            raise ValueError("invalid owner in adapter reference")
    name, sep, version = text.partition("@")
    if not is_name(name):
        raise ValueError("invalid adapter name in adapter reference")
    if sep and not is_version(version):
        raise ValueError("invalid version in adapter reference")
    return AdapterRef(owner=owner, name=name, version=version if sep else None)
