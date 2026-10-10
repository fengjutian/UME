"""Unified response envelope for `/api/ume/v1` (section 9.2).

Success: `{"data": ..., "request_id": ...}`
Paged:   `{"data": {"items", "next_cursor", "has_more"}, "request_id": ...}`
Failure: `{"error": {"code", "message", "details"}, "request_id": ...}`

The legacy `/memories` and `/search` routes keep their existing `{"detail": ...}`
shape on purpose — they are marked legacy in the doc and changing them would
break the current Dashboard. Isolation comes from mounting UME as its own
FastAPI app, so its exception handlers only ever see UME routes.
"""

from typing import Any

from errors import request_id_var
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from ume_app.domain.errors import UmeError

CACHE_HEADERS = {"Cache-Control": "no-store"}


def current_request_id() -> str:
    return request_id_var.get()


def success(data: Any, *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"data": data, "request_id": current_request_id()})


def created(data: Any) -> JSONResponse:
    return success(data, status_code=201)


def page(items: list[Any], next_cursor: str | None, has_more: bool) -> JSONResponse:
    return success({"items": items, "next_cursor": next_cursor, "has_more": has_more})


def failure(code: str, message: str, status_code: int, details: Any = None) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details}, "request_id": current_request_id()}
    return JSONResponse(status_code=status_code, content=body)


def failure_from(exc: UmeError) -> JSONResponse:
    return failure(exc.code, exc.message, exc.status_code, exc.details)


def dump(model: Any) -> Any:
    """Serialize a Pydantic model or ORM object to JSON-safe primitives.

    ORM rows go through their column mapping rather than `vars()`: SQLAlchemy
    instances carry `_sa_instance_state` in `__dict__`, which is neither part
    of the contract nor serializable.
    """
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    if hasattr(model, "__table__"):
        from ume_app.repositories.base import row_to_dict

        return jsonable_encoder(row_to_dict(model))
    return model
