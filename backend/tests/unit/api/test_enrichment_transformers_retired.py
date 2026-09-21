"""WP3.4 A6 deletion lock — the `api/helpers/` dead twin is GONE.

Why this deletion was licensed (ADDENDUM 2 §A6, five conditions, each
checked at `a6153643` and re-quoted in the commit body):

`backend/api/helpers/enrichment_transformers.py` (773 lines, 11 classes)
was a COMPLETE PARALLEL IMPLEMENTATION of the live enrichment responder.
The shipped path is `api/routes/detections.py:878 _transform_enrichment_data`
(plus its own `_sanitize_errors` at :133), called from detections.py:1037
and re-imported by events.py:2262. The helper package had ZERO non-test
importers repo-wide — module-level, symbol-level, and package-level censuses
all `rc=1` (the `sanitize_errors` recall is detections' own `_sanitize_errors`,
a different symbol; `*Extractor` hits are `services/florence_extractor.py`,
unrelated).

The measurement that made it worth deleting: the integration tier's merged
coverage (CI run 35551624215, 7 shards combined) shows the module at 0.0%
with 262 uncovered lines — the single largest zero-execution module in the
tier — while its 65 exclusive unit tests all pass. Passing tests on
unreachable code is exactly the signal-free coverage the WP3 tier exists to
surface: they cannot fail for a production reason.

If someone restores the extractor pattern for real (callers + integration
coverage), rewrite this lock to assert the shipped contract — do not delete
it (house precedent: test_materialized_views_retired.py).
"""

from __future__ import annotations

import importlib

import pytest

RETIRED_MODULES = [
    "backend.api.helpers",
    "backend.api.helpers.enrichment_transformers",
]


@pytest.mark.parametrize("module", RETIRED_MODULES)
def test_retired_module_stays_unimportable(module: str) -> None:
    """A re-added module without callers is the drift this lock names."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


def test_detections_inline_transformer_is_the_live_path() -> None:
    """The deletion is a de-duplication, not a loss: assert the LIVE path
    still serves the response shape the 65 deleted cases asserted. If this
    goes red, the two implementations were never twins and the deletion was
    wrong — restore from git and re-adjudicate."""
    from datetime import UTC, datetime

    from backend.api.routes.detections import _transform_enrichment_data

    result = _transform_enrichment_data(
        7,
        {
            "license_plates": [{"plate_text": "ABC123", "confidence": 0.9}],
            "faces": [{"confidence": 0.9}, {"confidence": 0.7}],
            "violence_detection": {"is_violent": True, "confidence": 0.8},
            "errors": ["Traceback (most recent call last): /etc/passwd leaked"],
        },
        datetime(2026, 9, 21, tzinfo=UTC),
    )
    assert result["detection_id"] == 7
    assert result["license_plate"]["detected"] is True
    assert result["face"]["count"] == 2
    assert result["violence"]["detected"] is True
    assert result["violence"]["score"] == 0.8
    # sanitizer contract survives (detections._sanitize_errors): the raw
    # traceback leaks neither the path nor the stack frame
    assert result["errors"] == ["Enrichment processing error"]


def test_live_transformer_still_has_unit_coverage() -> None:
    """The deleted suite's judgement (shape + sanitization) must still be
    covered somewhere, or the deletion dropped assertion signal rather than
    moving it. The live-path tests live in tests/unit/api/routes/."""
    import inspect
    from pathlib import Path

    import backend.api.routes.detections as detections_module

    # path is importlib-resolved from the installed package itself, not
    # user input (house precedent: inline nosemgrep, e.g. system.py:2560)
    src = Path(inspect.getfile(detections_module)).read_text(  # nosemgrep: path-traversal-open
        encoding="utf-8"
    )
    assert "def _transform_enrichment_data" in src
    keepers = Path(inspect.getfile(detections_module)).parents[2] / "tests/unit/api/routes"
    covered = [
        p.name
        for p in keepers.glob("test_*.py")
        if "_transform_enrichment_data" in p.read_text(encoding="utf-8")
    ]
    assert covered, "no unit test covers the live _transform_enrichment_data"
