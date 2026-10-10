"""Memory request/response schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_TAGS = 32
MAX_MESSAGE_CONTENT = 20000


class MessageIn(BaseModel):
    role: str = Field(default="user", max_length=32)
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CONTENT)


class MemoryCreate(BaseModel):
    workspace_id: uuid.UUID
    messages: list[MessageIn] = Field(min_length=1, max_length=100)
    memory_type: str = Field(default="semantic", max_length=64)
    tags: list[str] = Field(default_factory=list)
    project_ids: list[uuid.UUID] = Field(default_factory=list)
    infer: bool = True
    sources: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def _bounded(cls, value: list[str]) -> list[str]:
        if len(value) > MAX_TAGS:
            raise ValueError(f"at most {MAX_TAGS} tags")
        return [tag.strip() for tag in value if tag and tag.strip()]


class MemoryPatch(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_MESSAGE_CONTENT)
    change_reason: str | None = Field(default=None, max_length=1000)
    tags: list[str] | None = None


class MemoryArchive(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class MemoryForget(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class MemoryRestore(BaseModel):
    version_no: int = Field(ge=1)


class MemoryRetry(BaseModel):
    messages: list[MessageIn] = Field(min_length=1, max_length=100)


class MemorySearchRequest(BaseModel):
    workspace_id: uuid.UUID
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=10, ge=1, le=100)
    project_id: uuid.UUID | None = None


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    engine_memory_id: str
    memory_type: str
    status: str
    current_text: str
    tags: list[str]
    engine_state: str
    engine_error: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class MemorySourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID | None
    message_id: uuid.UUID | None
    source_type: str
    extraction_method: str
    evidence_excerpt: str | None
    confidence: float | None
    created_at: datetime


class MemoryVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_no: int
    text: str
    extra_metadata: dict[str, Any]
    change_type: str
    change_reason: str | None
    actor_type: str
    created_at: datetime


class MemorySearchHit(BaseModel):
    memory: MemoryOut
    score: float | None
    engine_id: str
