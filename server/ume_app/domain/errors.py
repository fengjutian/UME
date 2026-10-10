"""Business-layer errors.

These carry a stable machine code and an HTTP status so the API layer can map
them onto the unified `{error: {code, message, details}}` envelope from
section 9.2 of the implementation doc without inspecting exception types in
every route.
"""

from typing import Any


class ErrorCode:
    VALIDATION_FAILED = "VALIDATION_FAILED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    WORKSPACE_ARCHIVED = "WORKSPACE_ARCHIVED"


class UmeError(Exception):
    """Base class for expected, client-facing UME failures."""

    code = ErrorCode.VALIDATION_FAILED
    status_code = 400

    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_payload(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class ValidationError(UmeError):
    code = ErrorCode.VALIDATION_FAILED
    status_code = 400


class UnauthenticatedError(UmeError):
    code = ErrorCode.UNAUTHENTICATED
    status_code = 401


class PermissionDeniedError(UmeError):
    code = ErrorCode.PERMISSION_DENIED
    status_code = 403


class NotFoundError(UmeError):
    code = ErrorCode.NOT_FOUND
    status_code = 404


class ConflictError(UmeError):
    code = ErrorCode.CONFLICT
    status_code = 409


class IdempotencyConflictError(ConflictError):
    code = ErrorCode.IDEMPOTENCY_CONFLICT
    status_code = 409


class WorkspaceArchivedError(UmeError):
    """Raised when a write targets a workspace that is no longer active.

    Deliberately 409 rather than 403: the caller is allowed to act on this
    workspace, the workspace state is what blocks the write.
    """

    code = ErrorCode.WORKSPACE_ARCHIVED
    status_code = 409