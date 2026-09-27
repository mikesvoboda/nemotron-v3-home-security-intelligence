"""One branch point for the per-event analyzer (Phase 1.5, spec §2:81-84).

Every production construction site of "the analyzer" asks HERE — the
analysis-queue worker's default, the API dependency, the DI container,
and the batch aggregator's lazy fast-path builder. The plan's rule this
exists to enforce: *no path silently runs a stale analyzer*. Before 1.5
each site spelled ``NemotronAnalyzer(...)`` by hand, so flipping the mode
meant finding every site; after 1.5 the mode is read once per build and
a fifth seam that copies an old construction line trips the source-scan
pin in ``test_pipeline_factory.py``.

``legacy`` builds here because its code stays until R8 deletes it, not
because it is supported — spec rev 5: not deployed, not measured, not a
rollback target. The loud startup warning lives in the settings
validator (one place config mistakes get shouted about), not here: a
worker restart re-builds the analyzer many times and the validator
warns per Settings build already.

The imports are lazy on purpose: the NemotronAnalyzer module drags the
enrichment pipeline's import closure, and a vlm-mode process must not
pay for it (nor a vlm unit test import it transitively through a seam).
"""

from __future__ import annotations

from typing import Any

from backend.core.config import get_settings

__all__ = ["build_pipeline_analyzer"]


def _settings_for_mode() -> Any:
    """The mode's single source of truth, wrapped so tests (and the
    plan's per-subject `legacy_wire`-style fixtures) patch ONE name
    instead of the settings singleton."""
    return get_settings()


def build_pipeline_analyzer(*, redis_client: Any | None = None, **kwargs: Any) -> Any:
    """Construct the analyzer the selected pipeline mode names.

    Keyword args pass through to whichever class is chosen; every seam
    today needs only ``redis_client`` (both constructors accept it), and
    the passthrough keeps the factory honest when a seam grows a need.

    Returns:
        VlmAnalyzer (default, supported) or NemotronAnalyzer (legacy,
        UNSUPPORTED — parses only until R8).
    """
    mode = _settings_for_mode().pipeline_mode
    if mode == "legacy":
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        return NemotronAnalyzer(redis_client=redis_client, **kwargs)

    from backend.services.vlm_analyzer import VlmAnalyzer

    return VlmAnalyzer(redis_client=redis_client, **kwargs)
