"""Request/response schemas for the UME API.

Separate from the SQLAlchemy models on purpose: routes must never hand a model
instance straight to the client, because that couples the wire format to
column names and leaks fields nobody meant to publish.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _non_blank(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    default_memory_policy: dict[str, Any] = Field(default_factory=dict)

    _clean_name = field_validator("name")(_non_blank)


class WorkspacePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    default_memory_policy: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        return None if value is None else _non_blank(value)

    def changes(self) -> dict[str, Any]:
        """Only the fields the caller actually sent.

        Without this, `PATCH {"description": null}` would be indistinguishable
        from "not sent" and could never clear a description.
        """
        return self.model_dump(exclude_unset=True)


class WorkspaceMemberCreate(BaseModel):
    user_id: uuid.UUID
    role: str = Field(default="viewer", max_length=32)

    @field_validator("role")
    @classmethod
    def _known_role(cls, value: str) -> str:
        from ume_app.domain.enums import WorkspaceRole

        try:
            return str(WorkspaceRole(value))
        except ValueError as exc:
            allowed = ", ".join(str(role) for role in WorkspaceRole)
            raise ValueError(f"role must be one of: {allowed}") from exc


class WorkspaceMemberPatch(BaseModel):
    role: str = Field(max_length=32)

    @field_validator("role")
    @classmethod
    def _known_role(cls, value: str) -> str:
        from ume_app.domain.enums import WorkspaceRole

        try:
            return str(WorkspaceRole(value))
        except ValueError as exc:
            allowed = ", ".join(str(role) for role in WorkspaceRole)
            raise ValueError(f"role must be one of: {allowed}") from exc


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    tags: list[str] = Field(default_factory=list)

    _clean_name = field_validator("name")(_non_blank)


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    tags: list[str] | None = None
    status: str | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        return None if value is None else _non_blank(value)

    @field_validator("status")
    @classmethod
    def _known_status(cls, value: str | None) -> str | None:
        from ume_app.domain.enums import ProjectStatus

        if value is None:
            return None
        try:
            return str(ProjectStatus(value))
        except ValueError as exc:
            allowed = ", ".join(str(status) for status in ProjectStatus)
            raise ValueError(f"status must be one of: {allowed}") from exc

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    owner_user_id: uuid.UUID
    status: str
    default_memory_policy: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    created_at: datetime
    updated_at: datetime


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    tags: list[str]
    status: str
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime | None
