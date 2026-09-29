"""The one construction point for the per-event analyzer (Phase 1.5, spec §2:81-84).

Every production construction site of "the analyzer" asks HERE — the
analysis-queue worker's default, the API dependency, the DI container,
and the batch aggregator's lazy fast-path builder. The plan's rule this
exists to enforce: *no path silently runs a stale analyzer*. Before 1.5
each site spelled ``NemotronAnalyzer(...)`` by hand, so flipping the mode
meant finding every site; a fifth seam that copies an old construction
line still trips the source-scan pin in ``test_pipeline_factory.py``.

R8 (2026-09-29) retired the legacy pipeline: ``PIPELINE_MODE`` accepts one
value and raises on the retired spelling, so this module has no mode branch
left. The seam stays — its job was never the branch, it was that there is
exactly one place an analyzer is built, which is what the source-scan pin
enforces.

The import is lazy so importing this seam stays cheap and so a test that
patches the analyzer class does so before the build, not before an import.
"""

from __future__ import annotations

from typing import Any

__all__ = ["build_pipeline_analyzer"]


def build_pipeline_analyzer(*, redis_client: Any | None = None, **kwargs: Any) -> Any:
    """Construct the per-event analyzer.

    Keyword args pass through to the analyzer's constructor; every seam
    today needs only ``redis_client``, and the passthrough keeps the factory
    honest when a seam grows a need.

    Returns:
        VlmAnalyzer — the only analyzer the product has since R8.
    """
    from backend.services.vlm_analyzer import VlmAnalyzer

    return VlmAnalyzer(redis_client=redis_client, **kwargs)
