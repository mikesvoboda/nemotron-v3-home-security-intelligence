"""Audit logging service for tracking security-sensitive operations."""

from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.audit import AuditAction, AuditLog, AuditStatus


class AuditService:
    """Service for creating and querying audit logs."""

    @staticmethod
    async def log_action(
        db: AsyncSession,
        action: AuditAction | str,
        resource_type: str,
        actor: str = "anonymous",
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        request: Request | None = None,
        status: AuditStatus | str = AuditStatus.SUCCESS,
    ) -> AuditLog:
        """Log an audit entry for a security-sensitive action.

        Args:
            db: Database session
            action: The action being performed (from AuditAction enum or string)
            resource_type: Type of resource being acted upon (event, alert, rule, camera, settings)
            actor: User identifier or "system" for automated actions
            resource_id: Optional ID of the specific resource
            details: Optional dict with action-specific details
            request: Optional FastAPI request to extract IP and user agent
            status: Success or failure status

        Returns:
            The created AuditLog record
        """
        # Extract action value if enum
        action_str = action.value if isinstance(action, AuditAction) else action
        status_str = status.value if isinstance(status, AuditStatus) else status

        # Extract request info
        ip_address = None
        user_agent = None
        if request:
            # Get client IP, considering proxies
            ip_address = request.client.host if request.client else None
            # Check for X-Forwarded-For header
            forwarded_for = request.headers.get("x-forwarded-for")
            if forwarded_for:
                # Use the first IP in the chain (original client)
                ip_address = forwarded_for.split(",")[0].strip()
            # Get user agent
            user_agent = request.headers.get("user-agent")

        audit_log = AuditLog(
            timestamp=datetime.now(UTC),
            action=action_str,
            resource_type=resource_type,
            resource_id=resource_id,
            actor=actor,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            status=status_str,
        )

        db.add(audit_log)
        await db.flush()  # Flush to get the ID without committing
        return audit_log

    @staticmethod
    async def get_audit_logs(
        db: AsyncSession,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        actor: str | None = None,
        status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """Query audit logs with optional filters.

        Args:
            db: Database session
            action: Filter by action type
            resource_type: Filter by resource type
            resource_id: Filter by specific resource ID
            actor: Filter by actor
            status: Filter by status (success/failure)
            start_date: Filter logs from this date
            end_date: Filter logs until this date
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Tuple of (list of AuditLog records, total count)
        """
        query = select(AuditLog)

        # Apply filters
        if action:
            query = query.where(AuditLog.action == action)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        if actor:
            query = query.where(AuditLog.actor == actor)
        if status:
            query = query.where(AuditLog.status == status)
        if start_date:
            query = query.where(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.where(AuditLog.timestamp <= end_date)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0

        # Sort by timestamp descending (newest first)
        query = query.order_by(AuditLog.timestamp.desc())

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        result = await db.execute(query)
        logs = list(result.scalars().all())

        return logs, total_count

    @staticmethod
    async def get_audit_log_by_id(
        db: AsyncSession,
        audit_id: int,
    ) -> AuditLog | None:
        """Get a specific audit log by ID.

        Args:
            db: Database session
            audit_id: The audit log ID

        Returns:
            AuditLog record or None if not found
        """
        result = await db.execute(select(AuditLog).where(AuditLog.id == audit_id))
        return result.scalar_one_or_none()


# Singleton instance for convenience
audit_service = AuditService()
