"""Graph, timeline and context schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator
from ume_app.domain.enums import EdgeStatus, RelationType

MAX_EVIDENCE_BYTES = 8000


class EdgeCreate(BaseModel):
    workspace_id: uuid.UUID
    source_memory_id: uuid.UUID
    target_memory_id: uuid.UUID
    relation_type: str
    evidence_ref: dict[str, Any] = Field(default_factory=dict)

    @field_validator("relation_type")
    @classmethod
    def _known(cls, value: str) -> str:
        try:
            return str(RelationType(value))
        except ValueError as exc:
            allowed = ", ".join(str(item) for item in RelationType)
            raise ValueError(f"relation_type must be one of: {allowed}") from exc

    @field_validator("evidence_ref")
    @classmethod
    def _bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        # Evidence points at rows; it must not carry a message body.
        import json

        if len(json.dumps(value, default=str)) > MAX_EVIDENCE_BYTES:
            raise ValueError("evidence_ref is too large; store a reference, not content")
        return value


class EdgePatch(BaseModel):
    status: str
    relation_type: str | None = None

    @field_validator("status")
    @classmethod
    def _known_status(cls, value: str) -> str:
        try:
            return str(EdgeStatus(value))
        except ValueError as exc:
            allowed = ", ".join(str(item) for item in EdgeStatus)
            raise ValueError(f"status must be one of: {allowed}") from exc

    @field_validator("relation_type")
    @classmethod
    def _known_relation(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(RelationType(value))
        except ValueError as exc:
            allowed = ", ".join(str(item) for item in RelationType)
            raise ValueError(f"relation_type must be one of: {allowed}") from exc


class TimelineQuery(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    since: datetime | None = None
    until: datetime | None = None
    project_id: uuid.UUID | None = None


class ContextRequest(BaseModel):
    workspace_id: uuid.UUID
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=10, ge=1, le=100)
    token_budget: int | None = Field(default=None, ge=1, le=64000)
    project_id: uuid.UUID | None = None
