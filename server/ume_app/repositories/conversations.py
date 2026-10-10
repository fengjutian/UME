"""Conversation and message persistence."""

import uuid
from datetime import datetime
from typing import Any, Iterable, Sequence

from sqlalchemy import func, select
from ume_app.domain.errors import NotFoundError
from ume_app.models.base import utcnow
from ume_app.models.conversation import Conversation, Message
from ume_app.repositories.base import (
    Page,
    ScopedRepository,
    clamp_page_size,
    decode_cursor,
    encode_cursor,
)


class ConversationRepository(ScopedRepository[Conversation]):
    model = Conversation

    def list_for_workspace(
        self,
        workspace_id: uuid.UUID,
        *,
        project_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page[Conversation]:
        size = clamp_page_size(limit)
        stmt = self.db.query(Conversation).filter(Conversation.workspace_id == workspace_id)
        if project_id is not None:
            stmt = stmt.filter(Conversation.project_id == project_id)
        if status is not None:
            stmt = stmt.filter(Conversation.status == status)
        stmt = stmt.order_by(Conversation.created_at.desc(), Conversation.id.desc())
        return self._build_page(self.apply_cursor(stmt, cursor), size)

    def get_in_workspace(self, workspace_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
        return self.db.execute(
            select(Conversation).where(Conversation.workspace_id == workspace_id, Conversation.id == conversation_id)
        ).scalar_one_or_none()

    def require_in_workspace(self, workspace_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
        conversation = self.get_in_workspace(workspace_id, conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found.")
        return conversation

    def workspace_id_of(self, conversation_id: uuid.UUID) -> uuid.UUID | None:
        return self.db.execute(
            select(Conversation.workspace_id).where(Conversation.id == conversation_id)
        ).scalar_one_or_none()

    def find_by_external(
        self,
        workspace_id: uuid.UUID,
        connector_id: uuid.UUID | None,
        external_conversation_id: str,
    ) -> Conversation | None:
        """Resolve a connector-supplied id to an existing conversation.

        The connector_id comparison uses `IS NOT DISTINCT FROM` semantics via
        explicit `is_(None)`, so an import that has no connector yet still
        resolves its own rows.
        """
        stmt = select(Conversation).where(
            Conversation.workspace_id == workspace_id,
            Conversation.external_conversation_id == external_conversation_id,
        )
        stmt = stmt.where(
            Conversation.connector_id == connector_id
            if connector_id is not None
            else Conversation.connector_id.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, workspace_id: uuid.UUID, **fields: Any) -> Conversation:
        conversation = Conversation(workspace_id=workspace_id, **fields)
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def update(self, conversation: Conversation, **fields: Any) -> Conversation:
        for key, value in fields.items():
            if value is not None:
                setattr(conversation, key, value)
        conversation.updated_at = utcnow()
        self.db.flush()
        return conversation

    def delete(self, conversation: Conversation) -> None:
        self.db.delete(conversation)
        self.db.flush()


class MessageRepository(ScopedRepository[Message]):
    model = Message

    def list_for_conversation(
        self,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        order: str = "asc",
    ) -> Page[Message]:
        """Browse one conversation oldest-first.

        Tombstoned rows are excluded here rather than filtered by the caller:
        a deleted body must never be reachable through any list.
        """
        size = clamp_page_size(limit)
        stmt = self.db.query(Message).filter(
            Message.workspace_id == workspace_id,
            Message.conversation_id == conversation_id,
            Message.deleted_at.is_(None),
        )
        if order == "desc":
            stmt = stmt.order_by(Message.message_at.desc(), Message.id.desc())
            return self._build_page_desc(stmt, size, cursor)
        stmt = stmt.order_by(Message.message_at.asc(), Message.id.asc())
        return self._build_page_asc(stmt, size, cursor)

    def _build_page_asc(self, stmt, limit: int, cursor: str | None) -> Page[Message]:
        if cursor is not None:
            cursor_at, cursor_id = decode_cursor(cursor)
            stmt = stmt.filter(
                (Message.message_at > cursor_at) | ((Message.message_at == cursor_at) & (Message.id > cursor_id))
            )
        return self._materialize(stmt, limit, order="asc")

    def _build_page_desc(self, stmt, limit: int, cursor: str | None) -> Page[Message]:
        if cursor is not None:
            cursor_at, cursor_id = decode_cursor(cursor)
            stmt = stmt.filter(
                (Message.message_at < cursor_at) | ((Message.message_at == cursor_at) & (Message.id < cursor_id))
            )
        return self._materialize(stmt, limit, order="desc")

    def _materialize(self, stmt, limit: int, order: str) -> Page[Message]:
        rows: Sequence[Message] = list(stmt.limit(limit + 1))
        has_more = len(rows) > limit
        items = list(rows[:limit])
        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(last.message_at, last.id)
        return Page(items=items, next_cursor=next_cursor, has_more=has_more)

    def get_in_workspace(self, workspace_id: uuid.UUID, message_id: uuid.UUID) -> Message | None:
        return self.db.execute(
            select(Message).where(Message.workspace_id == workspace_id, Message.id == message_id)
        ).scalar_one_or_none()

    def find_by_external(self, conversation_id: uuid.UUID, external_message_id: str) -> Message | None:
        return self.db.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.external_message_id == external_message_id,
            )
        ).scalar_one_or_none()

    def find_by_hash(self, conversation_id: uuid.UUID, content_hash: str, message_at: datetime) -> Message | None:
        return self.db.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.content_hash == content_hash,
                Message.message_at == message_at,
            )
        ).scalar_one_or_none()

    def count_in_conversation(self, conversation_id: uuid.UUID, *, include_deleted: bool = False) -> int:
        stmt = select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        if not include_deleted:
            stmt = stmt.where(Message.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one()

    def add(self, conversation_id: uuid.UUID, workspace_id: uuid.UUID, **fields: Any) -> Message:
        message = Message(conversation_id=conversation_id, workspace_id=workspace_id, **fields)
        self.db.add(message)
        self.db.flush()
        return message

    def add_many(
        self, conversation_id: uuid.UUID, workspace_id: uuid.UUID, rows: Iterable[dict[str, Any]]
    ) -> list[Message]:
        made = [Message(conversation_id=conversation_id, workspace_id=workspace_id, **row) for row in rows]
        for message in made:
            self.db.add(message)
        self.db.flush()
        return made

    def tombstone(self, message: Message) -> Message:
        """Mark a body deleted while keeping the row for provenance."""
        message.deleted_at = utcnow()
        message.content_text = None
        self.db.flush()
        return message
