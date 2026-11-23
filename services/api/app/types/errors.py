from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Typed JSON body for every error response.

    The shape mirrors FastAPI's `HTTPException` default (`{"detail": ...}`) so
    the frontend api-client reads `.detail` uniformly for every error status.
    `code` is a stable machine-readable reason (`cross_tenant_adapter`,
    `adapter_not_found`, `stale_attempt`, ...) set by the app's own errors and
    null for generic failures.
    """

    detail: str = "Internal server error"
    code: str | None = None


class AppError(Exception):
    """An expected failure with an HTTP status and a stable `code`.

    Raised by the service layer; `main.py` turns it into an `ErrorResponse`.
    """

    def __init__(self, status: int, code: str, detail: str):
        self.status = status
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")
