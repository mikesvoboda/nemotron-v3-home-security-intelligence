"""GPU statistics model for monitoring AI inference performance."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .camera import Base


class GPUStats(Base):
    """GPU statistics model for tracking GPU performance metrics.

    Records GPU utilization, memory usage, temperature, power usage,
    and inference performance for monitoring AI model performance.

    Extended metrics (added for better throttling detection):
    - fan_speed: Cooling system health indicator
    - sm_clock: Current SM clock frequency (detects throttling vs max)
    - memory_bandwidth_utilization: Memory controller load %
    - pstate: Performance state P0 (max) to P15 (idle)

    High-value metrics (for throttling and error detection):
    - throttle_reasons: Bitfield of current throttle reasons
    - power_limit: Power limit in watts
    - sm_clock_max: Max SM clock frequency in MHz
    - compute_processes_count: Number of active compute processes
    - pcie_replay_counter: PCIe replay counter (error indicator)
    - temp_slowdown_threshold: Temperature at which GPU throttles

    Medium-value metrics (for hardware monitoring):
    - memory_clock: Current memory clock in MHz
    - memory_clock_max: Max memory clock in MHz
    - pcie_link_gen: PCIe link generation (1-4)
    - pcie_link_width: PCIe link width (x1-x16)
    - pcie_tx_throughput: PCIe TX throughput in KB/s
    - pcie_rx_throughput: PCIe RX throughput in KB/s
    - encoder_utilization: Video encoder utilization %
    - decoder_utilization: Video decoder utilization %
    - bar1_used: BAR1 memory used in MB
    """

    __tablename__ = "gpu_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    gpu_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gpu_utilization: Mapped[float | None] = mapped_column(Float, nullable=True)
    memory_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    power_usage: Mapped[float | None] = mapped_column(Float, nullable=True)
    inference_fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Extended metrics for throttling detection and hardware health
    fan_speed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sm_clock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_bandwidth_utilization: Mapped[float | None] = mapped_column(Float, nullable=True)
    pstate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # High-value metrics for throttling and error detection
    throttle_reasons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    power_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    sm_clock_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compute_processes_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pcie_replay_counter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temp_slowdown_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Medium-value metrics for hardware monitoring
    memory_clock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_clock_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pcie_link_gen: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pcie_link_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pcie_tx_throughput: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pcie_rx_throughput: Mapped[int | None] = mapped_column(Integer, nullable=True)
    encoder_utilization: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decoder_utilization: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bar1_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Indexes for time-series queries
    # BRIN index is more efficient for time-series data (monotonically increasing timestamps)
    __table_args__ = (
        Index(
            "ix_gpu_stats_recorded_at_brin",
            "recorded_at",
            postgresql_using="brin",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<GPUStats(id={self.id}, recorded_at={self.recorded_at}, "
            f"gpu_name={self.gpu_name}, gpu_utilization={self.gpu_utilization}%, "
            f"temperature={self.temperature}°C, power={self.power_usage}W)>"
        )
