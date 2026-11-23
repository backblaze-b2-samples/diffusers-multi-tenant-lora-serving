"""B2 operations the adapter registry, resolver and job queue need.

Every call reuses the one boto3 client from `b2_client` (custom user agent
`b2ai-diffusers-lora-weights-hub`). Workers never see this module: they reach
B2 only through the presigned URLs issued here.
"""

import hashlib
import json
from collections.abc import Iterator
from typing import Any, BinaryIO

from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings
from app.repo.b2_client import get_s3_client
from app.repo.list_cache import invalidate as _invalidate_list_cache

_HASH_CHUNK = 8 * 1024 * 1024


class _HashingReader:
    """A read-only, non-seekable view of a file that hashes what it hands out.

    boto3's managed upload reads a non-seekable stream strictly in order, so
    the digest is of exactly the bytes sent to B2, computed in the same pass.
    """

    def __init__(self, fileobj: BinaryIO):
        self._f = fileobj
        self.sha256 = hashlib.sha256()
        self.size = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self._f.read(size)
        self.sha256.update(chunk)
        self.size += len(chunk)
        return chunk


def _missing(e: ClientError) -> bool:
    return e.response.get("Error", {}).get("Code", "") in ("404", "NoSuchKey", "NotFound")


def upload_stream(key: str, fileobj: BinaryIO, content_type: str) -> tuple[str, int]:
    """Managed (multipart above 8 MB) upload while hashing. Returns (sha256, size)."""
    reader = _HashingReader(fileobj)
    try:
        get_s3_client().upload_fileobj(
            reader,
            settings.b2_bucket_name,
            key,
            ExtraArgs={"ContentType": content_type},
        )
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 upload failed for '{key}': {e}") from e
    _invalidate_list_cache()
    return reader.sha256.hexdigest(), reader.size


def put_bytes(key: str, body: bytes, content_type: str) -> None:
    try:
        get_s3_client().put_object(
            Bucket=settings.b2_bucket_name, Key=key, Body=body, ContentType=content_type
        )
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 put failed for '{key}': {e}") from e
    _invalidate_list_cache()


def put_json(key: str, data: dict[str, Any]) -> None:
    body = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
    put_bytes(key, body, "application/json")


def get_json(key: str) -> tuple[dict[str, Any], str] | None:
    """Return (document, etag), or None when the object does not exist."""
    try:
        resp = get_s3_client().get_object(Bucket=settings.b2_bucket_name, Key=key)
        body = resp["Body"].read()
    except ClientError as e:
        if _missing(e):
            return None
        raise RuntimeError(f"B2 get failed for '{key}': {e}") from e
    except BotoCoreError as e:
        raise RuntimeError(f"B2 get failed for '{key}': {e}") from e
    return json.loads(body), resp.get("ETag", "")


def head(key: str) -> tuple[int, str] | None:
    """Return (size, etag), or None when the object does not exist."""
    try:
        resp = get_s3_client().head_object(Bucket=settings.b2_bucket_name, Key=key)
    except ClientError as e:
        if _missing(e):
            return None
        raise RuntimeError(f"B2 head failed for '{key}': {e}") from e
    return int(resp["ContentLength"]), resp.get("ETag", "")


def hash_object(key: str) -> tuple[str, int] | None:
    """Stream an object back from B2 and hash it. Returns (sha256, size) or None."""
    digest = hashlib.sha256()
    size = 0
    try:
        resp = get_s3_client().get_object(Bucket=settings.b2_bucket_name, Key=key)
        for chunk in resp["Body"].iter_chunks(_HASH_CHUNK):
            digest.update(chunk)
            size += len(chunk)
    except ClientError as e:
        if _missing(e):
            return None
        raise RuntimeError(f"B2 get failed for '{key}': {e}") from e
    except BotoCoreError as e:
        raise RuntimeError(f"B2 read failed for '{key}': {e}") from e
    return digest.hexdigest(), size


def presign_get(key: str, ttl_seconds: int) -> str:
    try:
        return get_s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.b2_bucket_name, "Key": key},
            ExpiresIn=ttl_seconds,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 presign (GET) failed for '{key}': {e}") from e


def presign_put(key: str, ttl_seconds: int, content_type: str) -> str:
    """A PUT URL bound to one key and content type, for a credential-free worker."""
    try:
        return get_s3_client().generate_presigned_url(
            "put_object",
            Params={"Bucket": settings.b2_bucket_name, "Key": key, "ContentType": content_type},
            ExpiresIn=ttl_seconds,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 presign (PUT) failed for '{key}': {e}") from e


def iter_objects(prefix: str) -> Iterator[dict[str, Any]]:
    """Every object under `prefix` (uncached; the app's own prefix is small)."""
    kwargs: dict[str, Any] = {"Bucket": settings.b2_bucket_name, "Prefix": prefix}
    try:
        while True:
            resp = get_s3_client().list_objects_v2(**kwargs)
            yield from resp.get("Contents", [])
            if not resp.get("IsTruncated"):
                return
            kwargs["ContinuationToken"] = resp["NextContinuationToken"]
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 list failed for '{prefix}': {e}") from e


def list_child_prefixes(prefix: str) -> list[str]:
    """Immediate child "folders" of `prefix` (Delimiter="/")."""
    kwargs: dict[str, Any] = {
        "Bucket": settings.b2_bucket_name,
        "Prefix": prefix,
        "Delimiter": "/",
    }
    out: list[str] = []
    try:
        while True:
            resp = get_s3_client().list_objects_v2(**kwargs)
            out.extend(p["Prefix"] for p in resp.get("CommonPrefixes", []))
            if not resp.get("IsTruncated"):
                return out
            kwargs["ContinuationToken"] = resp["NextContinuationToken"]
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 list failed for '{prefix}': {e}") from e


def delete_keys(keys: list[str]) -> list[str]:
    """Delete exactly these keys (batches of 1000). Returns the keys deleted."""
    client = get_s3_client()
    deleted: list[str] = []
    for i in range(0, len(keys), 1000):
        batch = keys[i : i + 1000]
        try:
            resp = client.delete_objects(
                Bucket=settings.b2_bucket_name,
                Delete={"Objects": [{"Key": k} for k in batch], "Quiet": False},
            )
        except (ClientError, BotoCoreError) as e:
            raise RuntimeError(f"B2 delete failed: {e}") from e
        deleted.extend(d["Key"] for d in resp.get("Deleted", []))
        if resp.get("Errors"):
            raise RuntimeError(f"B2 delete reported errors: {resp['Errors'][:3]}")
    _invalidate_list_cache()
    return deleted
