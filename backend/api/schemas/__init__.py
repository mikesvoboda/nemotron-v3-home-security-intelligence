"""API schemas for request/response validation."""

from .camera import CameraCreate, CameraListResponse, CameraResponse, CameraUpdate

__all__ = [
    "CameraCreate",
    "CameraUpdate",
    "CameraResponse",
    "CameraListResponse",
]
