import functools
import mimetypes
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import Lock
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import settings
from app.repo.list_cache import cached_listing
from app.repo.list_cache import invalidate as _invalidate_list_cache
from app.repo.list_cache import prewarm as _prewarm_list_cache
from app.types import FileMetadata
from app.types.formatting import humanize_bytes


def _guess_content_type(key: str) -> str:
    mime, _ = mimetypes.guess_type(key)
    return mime or "application/octet-stream"


def _split_key(key: str) -> tuple[str, str]:
    """Return (folder, filename) from an object key."""
    parts = key.rsplit("/", 1)
    if len(parts) == 2:
        return parts[0] + "/", parts[1]
    return "", parts[0]


def _public_url(key: str) -> str | None:
    """Build a public URL for an object key, percent-encoding the path."""
    if not settings.b2_public_url_base:
        return None
    return f"{settings.b2_public_url_base}/{quote(key, safe='/')}"


def _client(config: Config):
    return boto3.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        region_name=settings.b2_region,
        aws_access_key_id=settings.b2_application_key_id,
        aws_secret_access_key=settings.b2_application_key,
        config=config,
    )


@functools.lru_cache(maxsize=1)
def get_s3_client():
    """The client for small, latency-sensitive calls (manifests, lists, heads)."""
    return _client(
        Config(
            connect_timeout=5,
            read_timeout=30,
            retries={"mode": "standard", "total_max_attempts": 3},
            signature_version="s3v4",
            user_agent_extra="b2ai-diffusers-lora-weights-hub",
        )
    )


# Adapter weights are hundreds of MB and may leave over an ordinary home uplink
# (a few MB/s). They get their own client so (a) a multipart upload cannot take
# every pooled connection the dispatcher's manifest and list calls need, and
# (b) one slow part has a timeout and retry budget sized for bulk transfer
# instead of for a manifest read. Concurrency is set in adapter_store.
UPLOAD_MAX_CONCURRENCY = 4


@functools.lru_cache(maxsize=1)
def get_upload_client():
    """The client for adapter weight uploads (multipart, bulk, slow links)."""
    return _client(
        Config(
            connect_timeout=10,
            read_timeout=120,
            retries={"mode": "adaptive", "total_max_attempts": 8},
            max_pool_connections=UPLOAD_MAX_CONCURRENCY + 2,
            tcp_keepalive=True,
            signature_version="s3v4",
            user_agent_extra="b2ai-diffusers-lora-weights-hub",
        )
    )


# Uploads in flight right now. While one saturates the uplink, a health probe
# can time out although B2 and the credentials are fine (see check_connectivity).
_uploads_in_flight = 0
_uploads_lock = Lock()


@contextmanager
def upload_in_flight():
    global _uploads_in_flight
    with _uploads_lock:
        _uploads_in_flight += 1
    try:
        yield
    finally:
        with _uploads_lock:
            _uploads_in_flight -= 1


# Cache the B2 connectivity result briefly so uptime monitors polling /health
# every few seconds don't issue a B2 head_bucket on every call.
_HEALTH_TTL_SECONDS = 5.0
_health_cache: tuple[float, bool] | None = None
_health_lock = Lock()


def check_connectivity() -> bool:
    """True when the bucket answers a head request.

    A timeout or dropped connection while our own adapter upload saturates the
    link keeps the last known answer; a real refusal (ClientError) always wins.
    """
    global _health_cache
    now = time.monotonic()
    with _health_lock:
        cached = _health_cache
    if cached is not None and now - cached[0] < _HEALTH_TTL_SECONDS:
        return cached[1]
    try:
        get_s3_client().head_bucket(Bucket=settings.b2_bucket_name)
        ok = True
    except ClientError:
        ok = False
    except Exception:
        with _uploads_lock:
            busy = _uploads_in_flight > 0
        ok = bool(busy and cached is not None and cached[1])
    with _health_lock:
        _health_cache = (time.monotonic(), ok)
    return ok


def _list_all_objects(prefix: str = "") -> list[dict]:
    """Every object under `prefix`, via the shared single-flight listing cache.

    The returned list is shared and cached, callers must treat it as read-only
    (never sort/mutate in place). Raises RuntimeError on S3 failure.
    """
    return cached_listing(prefix, _fetch_all_objects)


def prewarm_listing() -> None:
    """Kick off the full-bucket scan in the background (startup warm-up).

    Returns immediately. Without it the first user to open the dashboard or the
    file browser waits out the cold scan (8-20s on a 16k-object bucket).
    """
    _prewarm_list_cache("", _fetch_all_objects)


def _fetch_all_objects(prefix: str) -> list[dict]:
    """Paginate B2 for every object under `prefix`. Raises RuntimeError on failure."""
    client = get_s3_client()
    contents: list[dict] = []
    kwargs: dict = {
        "Bucket": settings.b2_bucket_name,
        "Prefix": prefix,
        "MaxKeys": 1000,
    }
    try:
        while True:
            response = client.list_objects_v2(**kwargs)
            contents.extend(response.get("Contents", []))
            if not response.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except ClientError as e:
        raise RuntimeError(f"B2 list failed: {e}") from e
    return contents


def list_files(prefix: str = "") -> list[FileMetadata]:
    """List all files under `prefix`.

    Paginates the whole prefix so callers see every object, not just the first
    1000. Order is unspecified, callers that need newest-first sort themselves
    (see `service.files.get_files`). Raises RuntimeError on S3 failure.
    """
    files: list[FileMetadata] = []
    for obj in _list_all_objects(prefix):
        folder, filename = _split_key(obj["Key"])
        files.append(
            FileMetadata(
                key=obj["Key"],
                filename=filename,
                folder=folder,
                size_bytes=obj["Size"],
                size_human=humanize_bytes(obj["Size"]),
                content_type=_guess_content_type(obj["Key"]),
                uploaded_at=obj["LastModified"],
                url=_public_url(obj["Key"]),
            )
        )
    return files


def get_file_metadata(key: str) -> FileMetadata | None:
    client = get_s3_client()
    try:
        response = client.head_object(
            Bucket=settings.b2_bucket_name, Key=key
        )
    except ClientError as e:
        # Only treat 404/NoSuchKey as "not found"; re-raise other errors
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey"):
            return None
        raise

    folder, filename = _split_key(key)
    return FileMetadata(
        key=key,
        filename=filename,
        folder=folder,
        size_bytes=response["ContentLength"],
        size_human=humanize_bytes(response["ContentLength"]),
        content_type=response.get("ContentType", _guess_content_type(key)),
        uploaded_at=response["LastModified"],
        url=_public_url(key),
    )


def delete_file(key: str) -> None:
    """Delete an object from B2. Raises RuntimeError on failure."""
    client = get_s3_client()
    try:
        client.delete_object(Bucket=settings.b2_bucket_name, Key=key)
    except ClientError as e:
        raise RuntimeError(f"B2 delete failed for '{key}': {e}") from e
    _invalidate_list_cache()  # deleted object must disappear from listings/stats


DISPOSITIONS = ("attachment", "inline")


def get_presigned_url(
    key: str,
    filename: str | None = None,
    expires_in: int = 600,
    disposition: str = "attachment",
) -> str:
    """Generate a presigned GET URL. Raises RuntimeError on S3 failure.

    `disposition` selects the `Content-Disposition` the signed response will
    carry. "attachment" (the default) makes browsers save the file; "inline"
    lets them render it in place, which the preview modal needs, an
    `attachment` response makes an `<iframe>` PDF preview impossible because
    the browser starts a download instead of painting the document.
    Raises ValueError for any other value.
    """
    if disposition not in DISPOSITIONS:
        raise ValueError(
            f"disposition must be one of {DISPOSITIONS}, got {disposition!r}"
        )
    client = get_s3_client()
    params: dict = {"Bucket": settings.b2_bucket_name, "Key": key}
    if filename:
        # RFC 5987 encoding for non-ASCII filenames
        encoded = quote(filename, safe="")
        params["ResponseContentDisposition"] = (
            f"{disposition}; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"
        )
    else:
        params["ResponseContentDisposition"] = disposition
    try:
        return client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 presign failed for '{key}': {e}") from e


def get_upload_stats() -> dict:
    """Aggregate stats across every object in the bucket.

    Raises RuntimeError on S3 failure.
    """
    contents = _list_all_objects()
    total_size = sum(obj["Size"] for obj in contents)
    today = datetime.now(UTC).date()
    uploads_today = sum(
        1 for obj in contents if obj["LastModified"].date() == today
    )
    return {
        "total_files": len(contents),
        "total_size_bytes": total_size,
        "total_size_human": humanize_bytes(total_size),
        "uploads_today": uploads_today,
    }
