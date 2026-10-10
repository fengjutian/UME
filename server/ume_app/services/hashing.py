"""Canonical request hashing for idempotency (section 9.4).

The hash must be stable across Python runs and across the two CLI
implementations, so it is computed over a sorted JSON encoding rather than over
the raw bytes the client happened to send.
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any


def _default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone().isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    raise TypeError(f"unhashable payload member: {type(value).__name__}")


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_default, ensure_ascii=False)


def request_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def content_hash(content: str | None, content_ref: dict[str, Any] | None) -> str:
    """Stable hash used for message deduplication (section 10.3).

    Hashes the canonical JSON of the *reference* when there is no inline text,
    so a re-run that reorders reference keys still dedupes.
    """
    material = content if content is not None else canonical_json(content_ref or {})
    return hashlib.sha256(material.strip().encode("utf-8")).hexdigest()
