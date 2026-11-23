"""Download one adapter through a presigned URL, verifying size and sha256.

Bytes stream to a temp file beside the cache while being hashed; the file is
moved into place with `os.replace` only when both checks match, so a corrupt
or partial download never becomes a cache entry.
"""

import hashlib
import os
import tempfile
from pathlib import Path

import httpx

from worker.config import USER_AGENT

_CHUNK = 1024 * 1024


class ChecksumMismatch(Exception):
    def __init__(self, expected_sha: str, actual_sha: str, expected_size: int, actual_size: int):
        self.expected_sha, self.actual_sha = expected_sha, actual_sha
        self.expected_size, self.actual_size = expected_size, actual_size
        super().__init__(
            f"adapter bytes do not match the manifest: sha256 {actual_sha[:12]} != "
            f"{expected_sha[:12]}, size {actual_size} != {expected_size}"
        )


class FetchFailed(Exception):
    pass


def download_verified(
    client: httpx.Client, url: str, dest: Path, sha256: str, size_bytes: int
) -> int:
    """Stream `url` to `dest` if it hashes to `sha256`. Returns bytes fetched."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=".part-", suffix=".tmp")
    digest = hashlib.sha256()
    fetched = 0
    try:
        with (
            os.fdopen(fd, "wb") as out,
            client.stream("GET", url, headers={"User-Agent": USER_AGENT}) as resp,
        ):
            if resp.status_code != 200:
                raise FetchFailed(f"presigned GET returned HTTP {resp.status_code}")
            for chunk in resp.iter_bytes(_CHUNK):
                digest.update(chunk)
                out.write(chunk)
                fetched += len(chunk)
        actual = digest.hexdigest()
        if actual != sha256 or fetched != size_bytes:
            raise ChecksumMismatch(sha256, actual, size_bytes, fetched)
        os.replace(tmp, dest)
        return fetched
    except httpx.HTTPError as e:
        raise FetchFailed(f"adapter download failed: {e}") from e
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
