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
