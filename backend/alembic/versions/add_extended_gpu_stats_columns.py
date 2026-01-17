"""Add extended GPU stats columns for throttling detection

Revision ID: add_extended_gpu_stats_columns
Revises: add_trust_status_to_entities
Create Date: 2026-01-17 12:00:00.000000

This migration adds new columns to the gpu_stats table for enhanced GPU monitoring:
- fan_speed: Cooling system health indicator (percentage)
- sm_clock: Current SM clock frequency in MHz (detects throttling vs max)
- memory_bandwidth_utilization: Memory controller load percentage
- pstate: Performance state P0 (max performance) to P15 (idle)

These metrics help detect:
- Thermal throttling (fan speed + temperature correlation)
- Power throttling (SM clock vs max clock)
- Memory bandwidth bottlenecks (memory_bandwidth_utilization)
- GPU activity state (pstate)

All columns are nullable to maintain compatibility with fallback data sources
(nvidia-smi, AI containers) that may not provide these extended metrics.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_extended_gpu_stats_columns"
down_revision: str | Sequence[str] | None = "add_trust_status_to_entities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add extended GPU stats columns for throttling detection."""
    # Add fan_speed column (percentage, 0-100)
    op.add_column(
        "gpu_stats",
        sa.Column("fan_speed", sa.Integer(), nullable=True),
    )

    # Add sm_clock column (MHz)
    op.add_column(
        "gpu_stats",
        sa.Column("sm_clock", sa.Integer(), nullable=True),
    )

    # Add memory_bandwidth_utilization column (percentage, 0-100)
    op.add_column(
        "gpu_stats",
        sa.Column("memory_bandwidth_utilization", sa.Float(), nullable=True),
    )

    # Add pstate column (P0-P15)
    op.add_column(
        "gpu_stats",
        sa.Column("pstate", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove extended GPU stats columns."""
    op.drop_column("gpu_stats", "pstate")
    op.drop_column("gpu_stats", "memory_bandwidth_utilization")
    op.drop_column("gpu_stats", "sm_clock")
    op.drop_column("gpu_stats", "fan_speed")
