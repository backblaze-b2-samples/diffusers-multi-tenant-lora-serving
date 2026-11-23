"""Run "publish demo adapters" in the background and expose its progress.

Publishing the demo set downloads and uploads ~600 MB, which takes minutes on
an ordinary uplink. Holding one HTTP request open that long hides all progress
and dies with the browser tab, so the route starts this job and returns at
once; the UI polls `status()` for the stage and byte counts. One job runs at a
time per API process; starting while one runs returns the running job.
"""

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from app.service import fixtures, manifests
from app.types import AppError, FixturePublishStatus

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_status: FixturePublishStatus | None = None


def _initial(path: Path) -> FixturePublishStatus:
    items = fixtures.load_fixtures(path)
    return FixturePublishStatus(
        state="idle", stage="", adapters_total=len(items), adapters_done=0,
        bytes_total=sum(int(fx.get("size_bytes", 0)) for fx in items), bytes_done=0,
        published=[],
    )


def status(path: Path = fixtures.FIXTURES) -> FixturePublishStatus:
    with _lock:
        return (_status or _initial(path)).model_copy(deep=True)


def _update(fn: Callable[[FixturePublishStatus], None]) -> None:
    with _lock:
        if _status is not None:
            fn(_status)


def _on_stage(text: str) -> None:
    _update(lambda s: setattr(s, "stage", text))


def _on_bytes(n: int) -> None:
    def apply(s: FixturePublishStatus) -> None:
        s.bytes_done = max(0, min(s.bytes_total, s.bytes_done + n))

    _update(apply)


def _on_adapter_done(ref: str, published: bool) -> None:
    def apply(s: FixturePublishStatus) -> None:
        s.adapters_done += 1
        if published:
            s.published.append(ref)

    _update(apply)


def _run(path: Path) -> None:
    try:
        fixtures.publish_fixtures(path, _on_stage, _on_bytes, _on_adapter_done)
    except AppError as e:
        _finish("failed", e.detail, e.code)
    except RuntimeError as e:  # repo/ wraps every B2 failure in RuntimeError
        logger.error("demo adapter publish could not reach B2: %s", e)
        _finish("failed", f"Could not reach B2 ({e}). Check your network connection and retry; "
                "adapters already published are kept and skipped.", "b2_unavailable")
    except Exception as e:  # the job thread must always record an outcome
        logger.exception("demo adapter publish failed")
        _finish("failed", f"Publishing the demo adapters failed unexpectedly: {e}", "internal_error")
    else:
        _finish("succeeded", None, None)


def _finish(state: str, error: str | None, code: str | None) -> None:
    def apply(s: FixturePublishStatus) -> None:
        s.state = state  # type: ignore[assignment]
        s.error, s.error_code = error, code
        s.finished_at = manifests.now_iso()
        if state == "succeeded":
            s.bytes_done = s.bytes_total
            s.stage = (
                f"Published {len(s.published)} demo adapter(s)" if s.published
                else "Demo adapters were already published"
            )
        else:
            s.stage = "Stopped"

    _update(apply)


def start(path: Path = fixtures.FIXTURES, *, background: bool = True) -> FixturePublishStatus:
    """Start a publish job unless one is running. Returns the current status."""
    global _status
    with _lock:
        if _status is not None and _status.state == "running":
            return _status.model_copy(deep=True)
        _status = _initial(path)
        _status.state = "running"
        _status.stage = "Starting"
        _status.started_at = manifests.now_iso()
    if background:
        threading.Thread(target=_run, args=(path,), name="fixture-publish", daemon=True).start()
    else:
        _run(path)
    return status(path)
