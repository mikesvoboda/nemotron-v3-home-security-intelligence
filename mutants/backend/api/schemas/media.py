"""Pydantic schemas for media API responses."""

from pydantic import BaseModel, Field


class MediaErrorResponse(BaseModel):
    """Error response for media access failures."""

    error: str = Field(..., description="Error message describing what went wrong")
    path: str = Field(..., description="The path that was attempted to be accessed")
