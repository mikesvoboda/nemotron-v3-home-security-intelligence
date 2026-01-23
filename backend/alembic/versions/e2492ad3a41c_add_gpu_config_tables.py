"""add gpu config tables

Revision ID: e2492ad3a41c
Revises: e5f6g7h8i9j0
Create Date: 2026-01-23 12:00:00.000000

This migration adds tables for GPU configuration management, enabling
multi-GPU support with configurable service-to-GPU assignments.

Tables created:
- gpu_devices: Stores detected GPU hardware information
- gpu_configurations: Service-to-GPU mapping and configuration
- system_settings: Key-value store for system-wide settings

Implements NEM-3293: Add GPU configuration database schema.
Related: Multi-GPU Support Design (docs/plans/2025-01-23-multi-gpu-support-design.md)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2492ad3a41c"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "e5f6g7h8i9j0"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create GPU configuration tables."""

    # =========================================================================
    # GPU_DEVICES TABLE
    # Stores detected GPU hardware information for the system
    # =========================================================================
    op.create_table(
        "gpu_devices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("gpu_index", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("vram_total_mb", sa.Integer(), nullable=True),
        sa.Column("vram_available_mb", sa.Integer(), nullable=True),
        sa.Column("compute_capability", sa.String(16), nullable=True),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Unique constraint on gpu_index
        sa.UniqueConstraint("gpu_index", name="uq_gpu_devices_gpu_index"),
        # Check constraints
        sa.CheckConstraint("gpu_index >= 0", name="ck_gpu_devices_gpu_index_non_negative"),
        sa.CheckConstraint(
            "vram_total_mb IS NULL OR vram_total_mb >= 0",
            name="ck_gpu_devices_vram_total_non_negative",
        ),
        sa.CheckConstraint(
            "vram_available_mb IS NULL OR vram_available_mb >= 0",
            name="ck_gpu_devices_vram_available_non_negative",
        ),
    )

    # Index on gpu_index for fast lookups
    op.create_index(
        "ix_gpu_devices_gpu_index",
        "gpu_devices",
        ["gpu_index"],
    )

    # =========================================================================
    # GPU_CONFIGURATIONS TABLE
    # Service-to-GPU mapping and configuration for AI services
    # =========================================================================
    op.create_table(
        "gpu_configurations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("service_name", sa.String(64), nullable=False),
        sa.Column("gpu_index", sa.Integer(), nullable=True),
        sa.Column("strategy", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("vram_budget_override", sa.Float(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Unique constraint on service_name
        sa.UniqueConstraint("service_name", name="uq_gpu_configurations_service_name"),
        # Check constraints
        sa.CheckConstraint(
            "gpu_index IS NULL OR gpu_index >= 0",
            name="ck_gpu_configurations_gpu_index_non_negative",
        ),
        sa.CheckConstraint(
            "strategy IN ('manual', 'vram_based', 'latency_optimized', 'isolation_first', 'balanced')",
            name="ck_gpu_configurations_strategy_valid",
        ),
        sa.CheckConstraint(
            "vram_budget_override IS NULL OR vram_budget_override > 0",
            name="ck_gpu_configurations_vram_budget_positive",
        ),
    )

    # Index on service_name for fast lookups
    op.create_index(
        "ix_gpu_configurations_service_name",
        "gpu_configurations",
        ["service_name"],
    )

    # Index on enabled for filtering active configurations
    op.create_index(
        "idx_gpu_configurations_enabled",
        "gpu_configurations",
        ["enabled"],
    )

    # =========================================================================
    # SYSTEM_SETTINGS TABLE
    # Key-value store for system-wide configuration settings
    # =========================================================================
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Primary key on key (no separate id column)
        sa.PrimaryKeyConstraint("key"),
    )

    # Index on updated_at for sorting/filtering by last modification
    op.create_index(
        "idx_system_settings_updated_at",
        "system_settings",
        ["updated_at"],
    )


def downgrade() -> None:
    """Drop GPU configuration tables in reverse order."""

    # =========================================================================
    # DROP SYSTEM_SETTINGS TABLE
    # =========================================================================
    op.drop_index(
        "idx_system_settings_updated_at",
        table_name="system_settings",
    )
    op.drop_table("system_settings")

    # =========================================================================
    # DROP GPU_CONFIGURATIONS TABLE
    # =========================================================================
    op.drop_index(
        "idx_gpu_configurations_enabled",
        table_name="gpu_configurations",
    )
    op.drop_index(
        "ix_gpu_configurations_service_name",
        table_name="gpu_configurations",
    )
    op.drop_table("gpu_configurations")

    # =========================================================================
    # DROP GPU_DEVICES TABLE
    # =========================================================================
    op.drop_index(
        "ix_gpu_devices_gpu_index",
        table_name="gpu_devices",
    )
    op.drop_table("gpu_devices")
