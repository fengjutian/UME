"""Audit recording.

`details` is constrained to a short, non-sensitive summary: resource ids, counts
and the names of changed fields. Message bodies, tokens and connector names
never belong here — the audit table is readable by anyone with
`workspace:read`.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session
from ume_app.auth.permissions import Principal
from ume_app.models.audit import AuditEvent


def record(
    db: Session,
    principal: Principal,
    *,
    action: str,
    resource_type: str,
    result: str = "success",
    workspace_id: uuid.UUID | None = None,
    resource_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    """Stage an audit row on the caller's transaction.

    No commit here: the service owns the transaction boundary, so the audit row
    lands exactly when the audited change does.
    """
    from ume_app.api.responses import current_request_id

    event = AuditEvent(
        workspace_id=workspace_id,
        actor_type=str(principal.actor_type),
        actor_id=principal.actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        request_id=request_id or current_request_id(),
        details=details or {},
    )
    db.add(event)
    db.flush()
    return event


def record_denial(
    principal: Principal,
    *,
    action: str,
    resource_type: str,
    workspace_id: uuid.UUID | None = None,
    resource_id: uuid.UUID | None = None,
    reason: str,
) -> None:
    """Persist a refused access on its own connection.

    A denial is raised while the request transaction is still open and is about
    to be rolled back, so the row cannot join that transaction. Failures here
    must never mask the original 403/404, hence the bare except.
    """
    from db import SessionLocal
    from ume_app.api.responses import current_request_id

    try:
        with SessionLocal() as db:
            db.add(
                AuditEvent(
                    workspace_id=workspace_id,
                    actor_type=str(principal.actor_type),
                    actor_id=principal.actor_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    result="denied",
                    request_id=current_request_id(),
                    details={"reason": reason},
                )
            )
            db.commit()
    except Exception:  # pragma: no cover - auditing must not break the response
        pass
