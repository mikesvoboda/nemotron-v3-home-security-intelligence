"""Add extended GPU metrics columns for comprehensive monitoring

Revision ID: add_extended_gpu_metrics_columns
Revises: add_extended_gpu_stats_columns
Create Date: 2026-01-17 14:00:00.000000

This migration adds new columns to the gpu_stats table for comprehensive GPU monitoring:

High-value metrics (for throttling and error detection):
- throttle_reasons: Bitfield of current throttle reasons (0=none)
- power_limit: Power limit in watts
- sm_clock_max: Maximum SM clock frequency in MHz
- compute_processes_count: Number of active compute processes
- pcie_replay_counter: PCIe replay counter (error indicator)
- temp_slowdown_threshold: Temperature threshold for GPU slowdown

Medium-value metrics (for hardware monitoring):
- memory_clock: Current memory clock frequency in MHz
- memory_clock_max: Maximum memory clock frequency in MHz
- pcie_link_gen: PCIe link generation (1-4)
- pcie_link_width: PCIe link width (1, 2, 4, 8, 16)
- pcie_tx_throughput: PCIe TX throughput in KB/s
- pcie_rx_throughput: PCIe RX throughput in KB/s
- encoder_utilization: Video encoder utilization percentage
- decoder_utilization: Video decoder utilization percentage
- bar1_used: BAR1 memory used in MB

All columns are nullable to maintain compatibility with fallback data sources
(nvidia-smi, AI containers) that may not provide these extended metrics.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_extended_gpu_metrics_columns"
down_revision: str | Sequence[str] | None = "add_extended_gpu_stats_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add extended GPU metrics columns for comprehensive monitoring."""
    # High-value metrics for throttling and error detection
    op.add_column(
        "gpu_stats",
        sa.Column("throttle_reasons", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gpu_stats",
        sa.Column("power_limit", sa.Float(), nullable=True),
    )
    op.add_column(
        "gpu_stats",
        sa.Column("sm_clock_max", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gpu_stats",
        sa.Column("compute_processes_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gpu_stats",
        sa.Column("pcie_replay_counter", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gpu_stats",
        sa.Column("temp_slowdown_threshold", sa.Float(), nullable=True),
    )

    # Medium-value metrics for hardware monitoring
    op.add_column(
        "gpu_stats",
        sa.Column("memory_clock", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gpu_stats",
        sa.Column("memory_clock_max", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gpu_stats",
        sa.Column("pcie_link_gen", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gpu_stats",
        sa.Column("pcie_link_width", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gpu_stats",
        sa.Column("pcie_tx_throughput", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gpu_stats",
        sa.Column("pcie_rx_throughput", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gpu_stats",
        sa.Column("encoder_utilization", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gpu_stats",
        sa.Column("decoder_utilization", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gpu_stats",
        sa.Column("bar1_used", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove extended GPU metrics columns."""
    # Medium-value metrics
    op.drop_column("gpu_stats", "bar1_used")
    op.drop_column("gpu_stats", "decoder_utilization")
    op.drop_column("gpu_stats", "encoder_utilization")
    op.drop_column("gpu_stats", "pcie_rx_throughput")
    op.drop_column("gpu_stats", "pcie_tx_throughput")
    op.drop_column("gpu_stats", "pcie_link_width")
    op.drop_column("gpu_stats", "pcie_link_gen")
    op.drop_column("gpu_stats", "memory_clock_max")
    op.drop_column("gpu_stats", "memory_clock")

    # High-value metrics
    op.drop_column("gpu_stats", "temp_slowdown_threshold")
    op.drop_column("gpu_stats", "pcie_replay_counter")
    op.drop_column("gpu_stats", "compute_processes_count")
    op.drop_column("gpu_stats", "sm_clock_max")
    op.drop_column("gpu_stats", "power_limit")
    op.drop_column("gpu_stats", "throttle_reasons")
