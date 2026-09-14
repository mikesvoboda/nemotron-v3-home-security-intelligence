"""NeMo Data Designer integration for synthetic scenario generation.

This module provides tools to generate synthetic security scenarios using
NVIDIA NeMo Data Designer for improving testing coverage and Nemotron
prompt quality evaluation.

Usage:
    uv run python tools/nemo_data_designer/generate_scenarios.py --preview
    uv run python tools/nemo_data_designer/generate_scenarios.py --generate --rows 100
"""

from tools.nemo_data_designer.config import (
    Detection,
    EnrichmentContext,
    GroundTruth,
    ScenarioBundle,
)

__all__ = [
    "Detection",
    "EnrichmentContext",
    "GroundTruth",
    "ScenarioBundle",
]
