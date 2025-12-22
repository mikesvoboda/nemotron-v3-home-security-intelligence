"""GPU statistics model for monitoring AI inference performance."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .camera import Base


class GPUStats(Base):
    """GPU statistics model for tracking GPU performance metrics.

    Records GPU utilization, memory usage, temperature, and inference
    performance for monitoring AI model performance.
    """

    __tablename__ = "gpu_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    gpu_utilization: Mapped[float | None] = mapped_column(Float, nullable=True)
    memory_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    inference_fps: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Indexes for time-series queries
    __table_args__ = (Index("idx_gpu_stats_recorded_at", "recorded_at"),)

    def __repr__(self) -> str:
        return (
            f"<GPUStats(id={self.id}, recorded_at={self.recorded_at}, "
            f"gpu_utilization={self.gpu_utilization}%, temperature={self.temperature}°C)>"
        )
