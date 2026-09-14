"""Shared utilities for AI services."""

from __future__ import annotations

__all__ = [
    "gpu_profile",
    "should_profile",
]

from .gpu_profiler import gpu_profile, should_profile
