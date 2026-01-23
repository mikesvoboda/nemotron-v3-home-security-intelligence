"""Automatic audit logging using SQLAlchemy session events.

NEM-3406: Implements automatic audit logging for create/update/delete operations
using SQLAlchemy's session event system.

This module provides:
1. Session event hooks (before_flush) that track model changes
2. Automatic audit log creation for tracked models
3. Old/new value comparison for updates
4. Thread-safe audit context for user information

Usage:
    # At application startup (in main.py):
    from backend.core.audit_events import setup_audit_logging
    setup_audit_logging()

    # To set user context for audit entries:
    from backend.core.audit_events import set_audit_context
    set_audit_context(actor="user@example.com", ip_address="192.168.1.1")
"""

from __future__ import annotations

import contextvars
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import event
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


__all__ = [
    "AuditContext",
    "clear_audit_context",
    "get_audit_context",
    "set_audit_context",
    "setup_audit_logging",
    "setup_session_audit_events",
    "teardown_audit_logging",
]

_logger = get_logger(__name__)

# Track whether audit logging is enabled globally
_audit_logging_enabled = False
_audit_logging_lock = threading.Lock()


@dataclass
class AuditContext:
    """Context for audit logging.

    Stores information about the current actor and request context
    for inclusion in audit log entries.
    """

    actor: str = "system"
    ip_address: str | None = None
    user_agent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for audit log creation."""
        return {
            "actor": self.actor,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


# Context variable for storing audit context (async-safe)
_audit_context: contextvars.ContextVar[AuditContext | None] = contextvars.ContextVar(
    "_audit_context", default=None
)


def get_audit_context() -> AuditContext:
    """Get the current audit context.

    Returns:
        Current AuditContext or a default context if not set
    """
    ctx = _audit_context.get()
    if ctx is None:
        return AuditContext()
    return ctx


def set_audit_context(
    *,
    actor: str = "system",
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> contextvars.Token[AuditContext | None]:
    """Set the audit context for the current async context.

    Args:
        actor: The user or system performing the action
        ip_address: The IP address of the request
        user_agent: The user agent string

    Returns:
        A token that can be used to restore the previous context
    """
    ctx = AuditContext(actor=actor, ip_address=ip_address, user_agent=user_agent)
    return _audit_context.set(ctx)


def clear_audit_context() -> None:
    """Clear the current audit context."""
    _audit_context.set(None)


# Models that should be automatically audited
# Maps model class name to the resource_type string for audit logs
AUDITED_MODELS: dict[str, str] = {
    "Camera": "camera",
    "Event": "event",
    "Detection": "detection",
    "AlertRule": "alert_rule",
    "Zone": "zone",
    "PromptConfig": "prompt_config",
    "HouseholdMember": "household_member",
    "RegisteredVehicle": "registered_vehicle",
}

# Fields to exclude from change tracking (e.g., auto-updated timestamps)
EXCLUDED_FIELDS: frozenset[str] = frozenset(
    {
        "updated_at",
        "last_seen_at",
        "search_vector",
    }
)


def _get_model_changes(instance: Any) -> dict[str, dict[str, Any]]:
    """Extract changed fields from a model instance.

    Args:
        instance: SQLAlchemy model instance

    Returns:
        Dictionary mapping field names to {"old": old_val, "new": new_val}
    """
    changes: dict[str, dict[str, Any]] = {}
    mapper = inspect(instance.__class__)
    state = inspect(instance)

    for attr in mapper.column_attrs:
        key = attr.key
        if key in EXCLUDED_FIELDS:
            continue

        history = state.attrs[key].history
        if history.has_changes():
            old_value = history.deleted[0] if history.deleted else None
            new_value = history.added[0] if history.added else getattr(instance, key)

            # Skip if no actual change
            if old_value == new_value:
                continue

            # Convert non-serializable types to strings
            if isinstance(old_value, datetime):
                old_value = old_value.isoformat()
            if isinstance(new_value, datetime):
                new_value = new_value.isoformat()

            changes[key] = {"old": old_value, "new": new_value}

    return changes


def _get_model_values(instance: Any) -> dict[str, Any]:
    """Extract all field values from a model instance.

    Args:
        instance: SQLAlchemy model instance

    Returns:
        Dictionary of field names to values
    """
    values: dict[str, Any] = {}
    mapper = inspect(instance.__class__)

    for attr in mapper.column_attrs:
        key = attr.key
        if key in EXCLUDED_FIELDS:
            continue

        value = getattr(instance, key, None)
        # Convert non-serializable types to strings
        if isinstance(value, datetime):
            value = value.isoformat()
        values[key] = value

    return values


def _get_resource_id(instance: Any) -> str | None:
    """Get the primary key value as a string.

    Args:
        instance: SQLAlchemy model instance

    Returns:
        Primary key value as string, or None if not set
    """
    mapper = inspect(instance.__class__)
    pk_cols = mapper.primary_key

    if len(pk_cols) == 1:
        pk_value = getattr(instance, pk_cols[0].key, None)
        return str(pk_value) if pk_value is not None else None

    # Composite primary key
    pk_values = [str(getattr(instance, col.key, "")) for col in pk_cols]
    return ":".join(pk_values) if all(pk_values) else None


def _create_audit_entry(
    action: str,
    resource_type: str,
    resource_id: str | None,
    details: dict[str, Any],
    context: AuditContext,
) -> dict[str, Any]:
    """Create an audit log entry dictionary.

    Args:
        action: The action performed (created, updated, deleted)
        resource_type: The type of resource
        resource_id: The ID of the resource
        details: Additional details about the action
        context: The audit context with actor info

    Returns:
        Dictionary ready for AuditLog creation
    """
    return {
        "timestamp": datetime.now(UTC),
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "actor": context.actor,
        "ip_address": context.ip_address,
        "user_agent": context.user_agent,
        "details": details,
        "status": "success",
    }


def _before_flush(
    session: Session,
    flush_context: Any,  # noqa: ARG001
    instances: Any,  # noqa: ARG001
) -> None:
    """SQLAlchemy event handler called before session flush.

    Collects changes to audited models and stores them for after_flush processing.
    This is a sync event handler because SQLAlchemy events are synchronous.

    Args:
        session: The SQLAlchemy session
        flush_context: Flush context (required by SQLAlchemy but unused)
        instances: Optional list of instances being flushed (required by SQLAlchemy but unused)
    """
    # Import here to avoid circular dependency and check model availability
    try:
        from backend.models.audit import AuditLog  # noqa: F401
    except ImportError:
        _logger.debug("AuditLog model not available, skipping audit logging")
        return

    context = get_audit_context()
    pending_audits: list[dict[str, Any]] = []

    # Track new objects (INSERT)
    for instance in session.new:
        model_name = instance.__class__.__name__
        if model_name not in AUDITED_MODELS:
            continue

        resource_type = AUDITED_MODELS[model_name]
        resource_id = _get_resource_id(instance)

        audit_entry = _create_audit_entry(
            action=f"{resource_type}_created",
            resource_type=resource_type,
            resource_id=resource_id,
            details={"values": _get_model_values(instance)},
            context=context,
        )
        pending_audits.append(audit_entry)

    # Track modified objects (UPDATE)
    for instance in session.dirty:
        if not session.is_modified(instance, include_collections=False):
            continue

        model_name = instance.__class__.__name__
        if model_name not in AUDITED_MODELS:
            continue

        changes = _get_model_changes(instance)
        if not changes:
            continue

        resource_type = AUDITED_MODELS[model_name]
        resource_id = _get_resource_id(instance)

        audit_entry = _create_audit_entry(
            action=f"{resource_type}_updated",
            resource_type=resource_type,
            resource_id=resource_id,
            details={"changes": changes},
            context=context,
        )
        pending_audits.append(audit_entry)

    # Track deleted objects (DELETE)
    for instance in session.deleted:
        model_name = instance.__class__.__name__
        if model_name not in AUDITED_MODELS:
            continue

        resource_type = AUDITED_MODELS[model_name]
        resource_id = _get_resource_id(instance)

        audit_entry = _create_audit_entry(
            action=f"{resource_type}_deleted",
            resource_type=resource_type,
            resource_id=resource_id,
            details={"deleted_values": _get_model_values(instance)},
            context=context,
        )
        pending_audits.append(audit_entry)

    # Store pending audits in session info for after_flush
    if pending_audits:
        session.info.setdefault("pending_audits", []).extend(pending_audits)


def _after_flush(session: Session, flush_context: Any) -> None:  # noqa: ARG001
    """SQLAlchemy event handler called after session flush.

    Creates the audit log entries that were collected in before_flush.

    Args:
        session: The SQLAlchemy session
        flush_context: Flush context (required by SQLAlchemy but unused)
    """
    try:
        from backend.models.audit import AuditLog
    except ImportError:
        return

    pending_audits = session.info.pop("pending_audits", [])
    if not pending_audits:
        return

    for audit_data in pending_audits:
        try:
            audit_log = AuditLog(**audit_data)
            session.add(audit_log)
        except Exception as e:
            _logger.warning(
                "Failed to create audit log entry",
                extra={
                    "error": str(e),
                    "action": audit_data.get("action"),
                    "resource_type": audit_data.get("resource_type"),
                },
            )


def setup_session_audit_events(session: Session | AsyncSession) -> None:
    """Set up audit logging events for a specific session.

    This is useful for setting up audit logging on individual sessions
    rather than globally on the session factory.

    Args:
        session: The session to attach audit events to
    """
    # For async sessions, get the underlying sync session
    sync_session = session.sync_session if hasattr(session, "sync_session") else session

    event.listen(sync_session, "before_flush", _before_flush)
    event.listen(sync_session, "after_flush", _after_flush)


def setup_audit_logging() -> bool:
    """Set up global audit logging for all sessions.

    Call this once at application startup to enable automatic audit logging.

    Returns:
        True if audit logging was enabled, False if already enabled or error
    """
    global _audit_logging_enabled  # noqa: PLW0603

    with _audit_logging_lock:
        if _audit_logging_enabled:
            _logger.debug("Audit logging already enabled")
            return True

        try:
            # Listen on the Session class to catch all sessions
            event.listen(Session, "before_flush", _before_flush)
            event.listen(Session, "after_flush", _after_flush)

            _audit_logging_enabled = True
            _logger.info(
                "Audit logging enabled",
                extra={"audited_models": list(AUDITED_MODELS.keys())},
            )
            return True
        except Exception as e:
            _logger.error(f"Failed to set up audit logging: {e}")
            return False


def teardown_audit_logging() -> bool:
    """Remove global audit logging event handlers.

    Primarily used for testing to reset state between tests.

    Returns:
        True if audit logging was disabled, False if already disabled or error
    """
    global _audit_logging_enabled  # noqa: PLW0603

    with _audit_logging_lock:
        if not _audit_logging_enabled:
            return True

        try:
            event.remove(Session, "before_flush", _before_flush)
            event.remove(Session, "after_flush", _after_flush)

            _audit_logging_enabled = False
            _logger.info("Audit logging disabled")
            return True
        except Exception as e:
            _logger.error(f"Failed to disable audit logging: {e}")
            return False
