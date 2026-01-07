"""High-level audit logging service for security-sensitive operations.

This module provides a convenient interface for logging security events to the
audit trail. It wraps the lower-level AuditService with simpler APIs for common
security logging patterns.

Security events logged include:
- Rate limit violations
- Content-Type validation failures
- File magic number validation failures
- Configuration changes
- Sensitive operations (exports, cleanup, etc.)

Usage:
    from backend.services.audit_logger import audit_logger

    # In an async context with database session
    await audit_logger.log_rate_limit_exceeded(
        db=db,
        request=request,
        tier="default",
        current_count=65,
        limit=60,
    )

    # For configuration changes
    await audit_logger.log_config_change(
        db=db,
        request=request,
        setting_name="batch_window_seconds",
        old_value=90,
        new_value=120,
    )
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import get_logger, mask_ip
from backend.models.audit import AuditAction, AuditStatus
from backend.services.audit import AuditService

logger = get_logger(__name__)


class SecurityAuditLogger:
    """High-level audit logging service for security events.

    This class provides simplified methods for logging common security events.
    All methods are async and require a database session.
    """

    def __init__(self) -> None:
        """Initialize the audit logger."""
        self._audit_service = AuditService()

    async def log_rate_limit_exceeded(
        self,
        db: AsyncSession,
        request: Request | None,
        *,
        tier: str,
        current_count: int,
        limit: int,
        client_ip: str | None = None,
    ) -> None:
        """Log a rate limit violation.

        Args:
            db: Database session
            request: Optional FastAPI request for context
            tier: Rate limit tier that was exceeded
            current_count: Current request count
            limit: Maximum allowed requests
            client_ip: Client IP if request not provided
        """
        ip = client_ip
        if request and request.client:
            ip = request.client.host

        await self._audit_service.log_action(
            db=db,
            action=AuditAction.RATE_LIMIT_EXCEEDED,
            resource_type="api",
            resource_id=None,
            actor=f"ip:{mask_ip(ip)}" if ip else "unknown",
            details={
                "tier": tier,
                "current_count": current_count,
                "limit": limit,
                "path": request.url.path if request else None,
                "method": request.method if request else None,
            },
            request=request,
            status=AuditStatus.FAILURE,
        )

        logger.info(
            f"Audit: Rate limit exceeded for tier {tier}",
            extra={
                "audit_action": AuditAction.RATE_LIMIT_EXCEEDED.value,
                "tier": tier,
                "current_count": current_count,
                "limit": limit,
            },
        )

    async def log_content_type_rejected(
        self,
        db: AsyncSession,
        request: Request | None,
        *,
        content_type: str,
        path: str | None = None,
        method: str | None = None,
    ) -> None:
        """Log a Content-Type validation failure.

        Args:
            db: Database session
            request: Optional FastAPI request for context
            content_type: The rejected Content-Type
            path: Request path (if request not provided)
            method: Request method (if request not provided)
        """
        await self._audit_service.log_action(
            db=db,
            action=AuditAction.CONTENT_TYPE_REJECTED,
            resource_type="api",
            resource_id=None,
            details={
                "content_type": content_type,
                "path": request.url.path if request else path,
                "method": request.method if request else method,
            },
            request=request,
            status=AuditStatus.FAILURE,
        )

        logger.info(
            f"Audit: Content-Type rejected: {content_type}",
            extra={
                "audit_action": AuditAction.CONTENT_TYPE_REJECTED.value,
                "content_type": content_type,
            },
        )

    async def log_file_magic_rejected(
        self,
        db: AsyncSession,
        request: Request | None,
        *,
        claimed_type: str,
        detected_type: str | None,
        filename: str | None = None,
    ) -> None:
        """Log a file magic number validation failure.

        Args:
            db: Database session
            request: Optional FastAPI request for context
            claimed_type: The claimed MIME type
            detected_type: The detected MIME type (or None if unknown)
            filename: The filename of the rejected file
        """
        await self._audit_service.log_action(
            db=db,
            action=AuditAction.FILE_MAGIC_REJECTED,
            resource_type="upload",
            resource_id=filename,
            details={
                "claimed_type": claimed_type,
                "detected_type": detected_type,
                "filename": filename,
            },
            request=request,
            status=AuditStatus.FAILURE,
        )

        logger.info(
            f"Audit: File magic rejected: claimed {claimed_type}, detected {detected_type}",
            extra={
                "audit_action": AuditAction.FILE_MAGIC_REJECTED.value,
                "claimed_type": claimed_type,
                "detected_type": detected_type,
                "filename": filename,
            },
        )

    async def log_config_change(
        self,
        db: AsyncSession,
        request: Request | None,
        *,
        setting_name: str,
        old_value: Any,
        new_value: Any,
        resource_id: str | None = None,
    ) -> None:
        """Log a configuration change.

        Args:
            db: Database session
            request: Optional FastAPI request for context
            setting_name: Name of the setting that changed
            old_value: Previous value
            new_value: New value
            resource_id: Optional resource identifier (e.g., camera_id)
        """
        await self._audit_service.log_action(
            db=db,
            action=AuditAction.CONFIG_UPDATED,
            resource_type="settings",
            resource_id=resource_id,
            details={
                "setting": setting_name,
                "old_value": _serialize_value(old_value),
                "new_value": _serialize_value(new_value),
                "timestamp": datetime.now(UTC).isoformat(),
            },
            request=request,
            status=AuditStatus.SUCCESS,
        )

        logger.info(
            f"Audit: Config change: {setting_name}",
            extra={
                "audit_action": AuditAction.CONFIG_UPDATED.value,
                "setting_name": setting_name,
                "old_value": str(old_value),
                "new_value": str(new_value),
            },
        )

    async def log_security_alert(
        self,
        db: AsyncSession,
        request: Request | None,
        *,
        alert_type: str,
        details: dict[str, Any],
        severity: str = "medium",
    ) -> None:
        """Log a general security alert.

        Args:
            db: Database session
            request: Optional FastAPI request for context
            alert_type: Type of security alert
            details: Additional details about the alert
            severity: Alert severity (low, medium, high, critical)
        """
        await self._audit_service.log_action(
            db=db,
            action=AuditAction.SECURITY_ALERT,
            resource_type="security",
            resource_id=None,
            details={
                "alert_type": alert_type,
                "severity": severity,
                **details,
            },
            request=request,
            status=AuditStatus.FAILURE,
        )

        logger.warning(
            f"Audit: Security alert: {alert_type}",
            extra={
                "audit_action": AuditAction.SECURITY_ALERT.value,
                "alert_type": alert_type,
                "severity": severity,
                **details,
            },
        )

    async def log_bulk_export(
        self,
        db: AsyncSession,
        request: Request | None,
        *,
        export_type: str,
        record_count: int,
        filters: dict[str, Any] | None = None,
    ) -> None:
        """Log a bulk export operation.

        Args:
            db: Database session
            request: Optional FastAPI request for context
            export_type: Type of data exported (events, detections, etc.)
            record_count: Number of records exported
            filters: Filters applied to the export
        """
        await self._audit_service.log_action(
            db=db,
            action=AuditAction.BULK_EXPORT_COMPLETED,
            resource_type=export_type,
            resource_id=None,
            details={
                "record_count": record_count,
                "filters": filters or {},
                "timestamp": datetime.now(UTC).isoformat(),
            },
            request=request,
            status=AuditStatus.SUCCESS,
        )

        logger.info(
            f"Audit: Bulk export completed: {record_count} {export_type} records",
            extra={
                "audit_action": AuditAction.BULK_EXPORT_COMPLETED.value,
                "export_type": export_type,
                "record_count": record_count,
            },
        )

    async def log_cleanup_executed(
        self,
        db: AsyncSession,
        request: Request | None,
        *,
        dry_run: bool,
        deleted_counts: dict[str, int],
        freed_bytes: int | None = None,
    ) -> None:
        """Log a cleanup operation execution.

        Args:
            db: Database session
            request: Optional FastAPI request for context
            dry_run: Whether this was a dry run
            deleted_counts: Counts of deleted items by type
            freed_bytes: Approximate bytes freed
        """
        await self._audit_service.log_action(
            db=db,
            action=AuditAction.CLEANUP_EXECUTED,
            resource_type="system",
            resource_id=None,
            details={
                "dry_run": dry_run,
                "deleted_counts": deleted_counts,
                "freed_bytes": freed_bytes,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            request=request,
            status=AuditStatus.SUCCESS,
        )

        logger.info(
            f"Audit: Cleanup executed (dry_run={dry_run})",
            extra={
                "audit_action": AuditAction.CLEANUP_EXECUTED.value,
                "dry_run": dry_run,
                "deleted_counts": deleted_counts,
                "freed_bytes": freed_bytes,
            },
        )


def _serialize_value(value: Any) -> Any:
    """Serialize a value for JSON storage in audit details.

    Args:
        value: Value to serialize

    Returns:
        JSON-serializable representation of the value
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    # For other types, convert to string
    return str(value)


# Singleton instance for convenience
audit_logger = SecurityAuditLogger()


# Convenience function for getting the audit logger
def get_audit_logger() -> SecurityAuditLogger:
    """Get the singleton audit logger instance.

    Returns:
        SecurityAuditLogger instance
    """
    return audit_logger
