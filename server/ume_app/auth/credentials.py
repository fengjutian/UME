"""Connector credential issuing and verification.

The plaintext token exists only inside `issue()`: what the caller gets back is
the single time it can be read. Verification always re-checks `revoked_at`
rather than trusting a cached decision, so revoking a credential takes effect
on the very next request.
"""

import secrets
from dataclasses import dataclass

from passlib.context import CryptContext
from ume_app.auth.permissions import CONNECTOR_SCOPES, Principal
from ume_app.domain.enums import ActorType
from ume_app.domain.errors import (
    PermissionDeniedError,
    UnauthenticatedError,
    ValidationError,
)
from ume_app.models.base import utcnow
from ume_app.models.connector import Connector

#: Recognisable prefix so a leaked connector token is identifiable at a glance
#: and so the auth resolver can tell connector tokens from user JWTs.
TOKEN_PREFIX = "umec_"
PREFIX_DISPLAY_LENGTH = 16

_hash_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MAX_SCOPES_PER_CONNECTOR = 16


def issue(connector: Connector, *, scopes: list[str], prefix_length: int = PREFIX_DISPLAY_LENGTH) -> str:
    """Return the plaintext token, having stored only its hash on `connector`."""
    raw = f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    connector.credential_prefix = raw[:prefix_length]
    connector.credential_hash = _hash_context.hash(raw)
    connector.scopes = list(scopes)
    return raw


def looks_like_connector_token(token: str) -> bool:
    return isinstance(token, str) and token.startswith(TOKEN_PREFIX)


def normalise_scopes(requested: list[str] | None) -> list[str]:
    """Validate requested scopes against the connector ceiling.

    A connector must never be granted workspace administration or bulk export
    through this path, so an unknown or administrative scope is refused rather
    than silently dropped.
    """
    allowed = set(CONNECTOR_SCOPES)
    if not requested:
        return sorted(allowed)
    if len(requested) > MAX_SCOPES_PER_CONNECTOR:
        raise ValidationError(f"At most {MAX_SCOPES_PER_CONNECTOR} scopes.")
    unknown = [scope for scope in requested if scope not in allowed]
    if unknown:
        raise ValidationError(
            "One or more scopes are not available to connectors.",
            details={"rejected": unknown, "allowed": sorted(allowed)},
        )
    return sorted(set(requested))


@dataclass(frozen=True)
class ResolvedConnector:
    connector: Connector
    principal: Principal


def resolve(token: str, candidates: list[Connector]) -> ResolvedConnector:
    """Turn a presented token into a Principal, or refuse.

    `candidates` is every non-revoked connector whose stored prefix matches, so
    the common case is one bcrypt comparison. Revoked connectors are filtered by
    the caller's query, not by this function, so a revoked credential can never
    authenticate even if its hash still verifies.
    """
    if not looks_like_connector_token(token):
        raise UnauthenticatedError("Invalid connector credential.")
    prefix = token[:PREFIX_DISPLAY_LENGTH]
    for connector in candidates:
        if connector.credential_prefix != prefix:
            continue
        if connector.is_revoked:
            # Deliberately not reported as "revoked": that would confirm the
            # credential ever existed.
            continue
        if not _hash_context.verify(token, connector.credential_hash):
            continue
        return ResolvedConnector(
            connector=connector,
            principal=Principal(
                actor_type=ActorType.CONNECTOR,
                actor_id=connector.id,
                scopes=frozenset(connector.scopes or ()),
                workspace_id=connector.workspace_id,
                project_id=connector.project_id,
            ),
        )
    raise UnauthenticatedError("Invalid connector credential.")


def touch(connector: Connector) -> None:
    connector.last_active_at = utcnow()
    connector.updated_at = utcnow()


def require_scopes(principal: Principal, *scopes: str) -> None:
    for scope in scopes:
        if not principal.has_scope(scope):
            raise PermissionDeniedError("当前主体无权访问该资源")


__all__ = [
    "MAX_SCOPES_PER_CONNECTOR",
    "ResolvedConnector",
    "TOKEN_PREFIX",
    "issue",
    "looks_like_connector_token",
    "normalise_scopes",
    "require_scopes",
    "resolve",
    "touch",
]
