"""Shared enums for container orchestration.

This module re-exports enums from the API schemas for convenient access
within the orchestrator package. These enums are the canonical definitions
and should be used consistently across all orchestration modules.

Re-exported from backend.api.schemas.services:
- ServiceCategory: Classification of services (infrastructure, ai, monitoring)
- ContainerServiceStatus: Current status of managed containers
"""

from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory

__all__ = [
    "ContainerServiceStatus",
    "ServiceCategory",
]
