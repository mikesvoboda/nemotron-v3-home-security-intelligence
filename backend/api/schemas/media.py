"""Pydantic schemas for media API responses."""

from pydantic import BaseModel, ConfigDict, Field


class MediaErrorResponse(BaseModel):
    """Error response for media access failures."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "File not found",
                "path": "/export/foscam/front_door/image_001.jpg",
            }
        }
    )

    error: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Error message describing what went wrong",
    )
    path: str = Field(
        ...,
        min_length=0,
        max_length=4096,
        description="The path that was attempted to be accessed",
    )
