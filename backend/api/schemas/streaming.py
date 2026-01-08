"""Streaming event schemas for SSE responses (NEM-1665)."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class StreamingErrorCode(str, Enum):
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_CONNECTION_ERROR = "LLM_CONNECTION_ERROR"
    LLM_SERVER_ERROR = "LLM_SERVER_ERROR"
    BATCH_NOT_FOUND = "BATCH_NOT_FOUND"
    NO_DETECTIONS = "NO_DETECTIONS"
    CANCELLED = "CANCELLED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class StreamingProgressEvent(BaseModel):
    event_type: Literal["progress"] = Field(default="progress")
    content: str = Field(description="The new content chunk from LLM")
    accumulated_text: str = Field(default="", description="All text received so far")
    progress_percent: float | None = Field(default=None)


class StreamingCompleteEvent(BaseModel):
    event_type: Literal["complete"] = Field(default="complete")
    event_id: int = Field(description="The created event ID")
    risk_score: int = Field(description="Risk score (0-100)")
    risk_level: str = Field(description="Risk level")
    summary: str = Field(description="Event summary")
    reasoning: str = Field(description="Risk reasoning")


class StreamingErrorEvent(BaseModel):
    event_type: Literal["error"] = Field(default="error")
    error_code: str | StreamingErrorCode = Field(description="Error code")
    error_message: str = Field(description="Human-readable error message")
    recoverable: bool = Field(default=True)
