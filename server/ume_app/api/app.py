"""The mounted `/api/ume/v1` application.

Mounting a separate FastAPI instance (rather than including an APIRouter on the
main app) is what keeps the legacy `/memories` and `/search` routes on their
existing `{"detail": ...}` shape: a mounted app owns its exception middleware, so
these handlers can never fire for a legacy route.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from ume_app.api.responses import failure, failure_from
from ume_app.api.router import build_router
from ume_app.domain.errors import ErrorCode, UmeError

_STATUS_CODES = {
    400: ErrorCode.VALIDATION_FAILED,
    401: ErrorCode.UNAUTHENTICATED,
    403: ErrorCode.PERMISSION_DENIED,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    409: ErrorCode.CONFLICT,
}


def _detail_to_message(detail: object, fallback: str) -> str:
    if isinstance(detail, str):
        return detail
    return fallback


async def ume_error_handler(_: Request, exc: UmeError) -> JSONResponse:
    return failure_from(exc)


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Flatten pydantic errors into `field: message` pairs.

    `loc` starts with ("body", "name"), so the tuple is joined without the
    body/query prefix to keep the field name readable.
    """
    details = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path")]
        details.append({"field": ".".join(location) or None, "message": error.get("msg", "invalid value")})
    return failure(ErrorCode.VALIDATION_FAILED, "Request payload failed validation.", 400, details)


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Translate the existing server auth failures into the UME envelope."""
    code = _STATUS_CODES.get(exc.status_code, ErrorCode.VALIDATION_FAILED)
    message = _detail_to_message(exc.detail, "Request failed.")
    return failure(code, message, exc.status_code)


async def integrity_error_handler(_: Request, exc: IntegrityError) -> JSONResponse:
    logging.warning("UME integrity error: %s", exc.orig)
    return failure(ErrorCode.CONFLICT, "The request conflicts with existing data.", 409)


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logging.exception("Unhandled UME error: %s", type(exc).__name__)
    return failure(ErrorCode.INTERNAL_ERROR, "Internal server error.", 500)


def create_ume_app() -> FastAPI:
    app = FastAPI(
        title="UME API",
        version="1.0.0",
        description="UME business API. Every response uses the {data|error, request_id} envelope.",
    )
    app.include_router(build_router())

    app.add_exception_handler(UmeError, ume_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    return app


ume_api = create_ume_app()
