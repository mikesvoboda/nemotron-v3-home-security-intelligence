"""GPU configuration models for multi-GPU support.

This module provides SQLAlchemy models for tracking GPU devices and their
assignments to AI services. Supports manual and auto-assignment strategies
for distributing models across multiple GPUs.

See docs/plans/2025-01-23-multi-gpu-support-design.md for design details.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .camera import Base


class GpuAssignmentStrategy(str, Enum):
    """GPU assignment strategies for AI services.

    Strategies determine how models are distributed across GPUs:
    - MANUAL: User controls each assignment explicitly
    - VRAM_BASED: Largest models assigned to GPU with most VRAM
    - LATENCY_OPTIMIZED: Critical path models on fastest GPU
    - ISOLATION_FIRST: LLM gets dedicated GPU, others share
    - BALANCED: Distribute VRAM evenly across GPUs
    """

    MANUAL = "manual"
    VRAM_BASED = "vram_based"
    LATENCY_OPTIMIZED = "latency_optimized"
    ISOLATION_FIRST = "isolation_first"
    BALANCED = "balanced"

    def __str__(self) -> str:
        """Return string representation of strategy."""
        return self.value


class GpuDevice(Base):
    """GPU device model representing a detected GPU.

    Stores metadata about detected GPUs including VRAM capacity
    and compute capability. Updated during GPU detection scans.
    """

    __tablename__ = "gpu_devices"
    __table_args__ = (
        Index("idx_gpu_devices_gpu_index", "gpu_index", unique=True),
        Index("idx_gpu_devices_last_seen", "last_seen_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default="gen_random_uuid()",
    )
    gpu_index: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vram_total_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vram_available_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compute_capability: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default="now()",
        nullable=False,
    )

    def __repr__(self) -> str:
        """Return string representation of GPU device."""
        return (
            f"<GpuDevice(id={self.id!r}, gpu_index={self.gpu_index}, "
            f"name={self.name!r}, vram_total_mb={self.vram_total_mb})>"
        )


class GpuConfiguration(Base):
    """GPU configuration model for service-to-GPU assignments.

    Stores the GPU assignment for each AI service. Supports manual
    assignment or auto-assignment via strategy selection.
    """

    __tablename__ = "gpu_configurations"
    __table_args__ = (
        Index("idx_gpu_configurations_service_name", "service_name", unique=True),
        Index("idx_gpu_configurations_gpu_index", "gpu_index"),
        Index("idx_gpu_configurations_enabled", "enabled"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default="gen_random_uuid()",
    )
    service_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    gpu_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strategy: Mapped[str] = mapped_column(
        String(32),
        default=GpuAssignmentStrategy.MANUAL.value,
        nullable=False,
    )
    vram_budget_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default="now()",
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default="now()",
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        """Return string representation of GPU configuration."""
        return (
            f"<GpuConfiguration(id={self.id!r}, service_name={self.service_name!r}, "
            f"gpu_index={self.gpu_index}, strategy={self.strategy!r})>"
        )


class SystemSetting(Base):
    """System-wide settings stored as key-value pairs.

    Stores configuration that applies globally, such as default
    GPU assignment strategy. Values are stored as JSONB for flexibility.
    """

    __tablename__ = "system_settings"
    __table_args__ = (Index("idx_system_settings_updated_at", "updated_at"),)

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default="now()",
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        """Return string representation of system setting."""
        return f"<SystemSetting(key={self.key!r}, value={self.value!r})>"
