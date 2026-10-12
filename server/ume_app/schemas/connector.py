"""Connector credential schemas."""

import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

MAX_SCOPES = 16


class ConnectorCreate(BaseModel):
    workspace_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    connector_type: str = Field(min_length=1, max_length=64)
    scopes: list[str] | None = None
    project_id: uuid.UUID | None = None
    client_instance_id: str | None = Field(default=None, max_length=255)
    capabilities: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _clean(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("scopes")
    @classmethod
    def _bounded(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(value) > MAX_SCOPES:
            raise ValueError(f"at most {MAX_SCOPES} scopes")
        return value


class ConnectorPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    scopes: list[str] | None = None
    capabilities: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)
