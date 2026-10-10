"""Conversation, message and import schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from ume_app.domain.enums import ConversationStatus, MessageRole, Sensitivity

MAX_MESSAGES_PER_IMPORT = 5000


def _non_blank(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class ConversationCreate(BaseModel):
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=255)
    source_type: str = Field(default="generic", max_length=64)
    retention_policy: str = Field(default="retain", max_length=64)
    external_conversation_id: str | None = Field(default=None, max_length=255)
    started_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        return None if value is None else _non_blank(value)


class ConversationPatch(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    project_id: uuid.UUID | None = None
    retention_policy: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, max_length=32)

    @field_validator("status")
    @classmethod
    def _known_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(ConversationStatus(value))
        except ValueError as exc:
            allowed = ", ".join(str(item) for item in ConversationStatus)
            raise ValueError(f"status must be one of: {allowed}") from exc

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


class MessageIn(BaseModel):
    """One inbound message, as accepted by both the append and import routes."""

    external_message_id: str | None = Field(default=None, max_length=255)
    role: str
    content: str | None = None
    content_ref: dict[str, Any] | None = None
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    sensitivity: str = Field(default="normal", max_length=32)

    @field_validator("role")
    @classmethod
    def _known_role(cls, value: str) -> str:
        try:
            return str(MessageRole(value))
        except ValueError as exc:
            allowed = ", ".join(str(item) for item in MessageRole)
            raise ValueError(f"role must be one of: {allowed}") from exc

    @field_validator("sensitivity")
    @classmethod
    def _known_sensitivity(cls, value: str) -> str:
        try:
            return str(Sensitivity(value))
        except ValueError as exc:
            allowed = ", ".join(str(item) for item in Sensitivity)
            raise ValueError(f"sensitivity must be one of: {allowed}") from exc

    @field_validator("timestamp")
    @classmethod
    def _require_timezone(cls, value: datetime | None) -> datetime | None:
        # Naive timestamps would be stored as-is and then compared against
        # tz-aware rows, which silently skews every dedup window.
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamp must carry a timezone offset")
        return value

    @model_validator(mode="after")
    def _require_content(self) -> "MessageIn":
        if self.content is None and self.content_ref is None:
            raise ValueError("either content or content_ref is required")
        return self


class MessagesAppend(BaseModel):
    messages: list[MessageIn] = Field(min_length=1, max_length=MAX_MESSAGES_PER_IMPORT)


class ConversationImport(BaseModel):
    """The unified import envelope from section 10.1."""

    format_version: str = Field(default="1.0", max_length=16)
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None = None
    source: str = Field(default="generic", max_length=64)
    connector_id: uuid.UUID | None = None
    external_conversation_id: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=255)
    retention_policy: str = Field(default="retain", max_length=64)
    messages: list[MessageIn] = Field(min_length=1, max_length=MAX_MESSAGES_PER_IMPORT)

    @field_validator("format_version")
    @classmethod
    def _supported_version(cls, value: str) -> str:
        if value != "1.0":
            raise ValueError(f"unsupported format_version {value!r}; this build accepts '1.0'")
        return value


class ImportPreviewOut(BaseModel):
    valid: bool
    workspace_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    conversation_action: str
    message_count: int
    duplicate_count: int
    new_message_count: int
    first_message_at: datetime | None = None
    last_message_at: datetime | None = None
    problems: list[dict[str, Any]] = Field(default_factory=list)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None
    title: str | None
    source_type: str
    retention_policy: str
    status: str
    started_at: datetime | None
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    external_message_id: str | None
    role: str
    content_text: str | None
    content_ref: dict[str, Any] | None
    sensitivity: str
    message_at: datetime
    created_at: datetime


class ImportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None
    idempotency_key: str
    status: str
    input_summary: dict[str, Any]
    result_summary: dict[str, Any]
    error_summary: dict[str, Any]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
