"""Backward compatibility module for Zone model.

This module re-exports from camera_zone.py for backward compatibility.
The Zone model has been renamed to CameraZone in Phase 5.3 of NEM-3113
to distinguish detection polygons from logical Areas.

DEPRECATED: Import from backend.models.camera_zone instead.
"""

from backend.models.camera_zone import (
    CameraZone,
    CameraZoneShape,
    CameraZoneType,
    Zone,
    ZoneShape,
    ZoneType,
)

__all__ = [
    "CameraZone",
    "CameraZoneShape",
    "CameraZoneType",
    "Zone",
    "ZoneShape",
    "ZoneType",
]
