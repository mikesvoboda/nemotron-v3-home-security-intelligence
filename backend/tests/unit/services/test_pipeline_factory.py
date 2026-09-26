"""1.5: PIPELINE_MODE selects the analyzer at ONE factory, default vlm.

Spec §2:81-84 (rev 5): ``vlm`` is the default and the only supported mode;
``legacy`` parses only because its code stays until R8 deletes it — never
deployed, never measured, never a rollback target. That ruling shapes
every pin here:

* the default is ``vlm`` — a deployment that sets nothing runs the VLM
  path (the shipped default, not a sandbox-only setting);
* ``legacy`` parses (the code stays) but is LOUD at startup, and an
  unknown value RAISES — a typo must never fall back to either mode,
  least of all to the unsupported one;
* the analyzer is branched at ONE factory, and every production
  construction site goes through it, so no path silently runs a stale
  analyzer (the plan's binding rule: all three seams + container);
* the vlm adapter's streaming surface answers the SAME update vocabulary
  the SSE route serializes — and for a ``verification_failed`` event
  (NULL score, D11) it must answer HONESTLY. nemotron's streaming path
  papers over a NULL score with ``risk_score or 50`` + ``"medium"`` —
  exactly the "default score" lie S5 forbids; the adapter answers an
  error update instead, never a fabricated 50/medium complete.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.config import Settings

pytestmark = pytest.mark.unit


def _settings(**kw) -> Settings:
    """Settings built like the nemotron_* tests do: explicit kwargs, never
    the cached singleton, never a mutated global."""
    return Settings(_env_file=None, **kw)


class TestPipelineModeSetting:
    def test_default_is_vlm(self) -> None:
        """Rev 5: vlm is the DEFAULT. A deployment that spells nothing
        runs the supported path — this single assertion is the shipped
        default, not a sandbox-only setting."""
        assert _settings().pipeline_mode == "vlm"

    def test_legacy_parses_but_warns_loud(self, caplog) -> None:
        """The code stays until R8, so `legacy` must still parse — and
        must be LOUD about it (owner: not deployed, not a rollback)."""
        with caplog.at_level("WARNING"):
            s = _settings(pipeline_mode="legacy")
        assert s.pipeline_mode == "legacy"
        assert any(
            "unsupported" in r.message.lower() or "legacy" in r.message.lower()
            for r in caplog.records
        ), "choosing legacy must be loud at startup, not silent"

    def test_unknown_value_raises_never_falls_back(self) -> None:
        """A typo raises. Falling back — to either mode — would make a
        config mistake silently pick the pipeline, which is exactly how
        the unsupported path would sneak back into a deployment."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            _settings(pipeline_mode="vlmm")
        with pytest.raises(ValidationError):
            _settings(pipeline_mode="")

    def test_value_is_stripped_and_case_normalized(self) -> None:
        assert _settings(pipeline_mode="  VLM ").pipeline_mode == "vlm"


# ---------------------------------------------------------------------------
# The factory: ONE branch point for every production construction site.
# ---------------------------------------------------------------------------


class TestPipelineAnalyzerFactory:
    def test_vlm_mode_builds_the_vlm_analyzer(self, monkeypatch) -> None:
        from backend.services import pipeline_factory as pf

        monkeypatch.setattr(pf, "_settings_for_mode", lambda: _settings(pipeline_mode="vlm"))
        built = pf.build_pipeline_analyzer(redis_client=AsyncMock())
        from backend.services.vlm_analyzer import VlmAnalyzer

        assert isinstance(built, VlmAnalyzer)
        # The uniform surface every seam consumer calls:
        for name in ("analyze_batch", "analyze_detection_fast_path", "analyze_batch_streaming"):
            assert callable(getattr(built, name)), f"seam surface missing {name}"

    def test_legacy_mode_builds_the_nemotron_analyzer(self, monkeypatch) -> None:
        from backend.services import pipeline_factory as pf
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        monkeypatch.setattr(pf, "_settings_for_mode", lambda: _settings(pipeline_mode="legacy"))
        built = pf.build_pipeline_analyzer(redis_client=AsyncMock())
        assert isinstance(built, NemotronAnalyzer)


# ---------------------------------------------------------------------------
# The vlm side of the seam surface: VlmAnalyzer gains the two methods the
# other seams (SSE re-analyze route, aggregator fast path) call, honestly.
# ---------------------------------------------------------------------------


class TestVlmSeamSurface:
    async def test_fast_path_routes_through_the_batch_gate(self, monkeypatch) -> None:
        """The aggregator's `analyze_detection_fast_path` in vlm mode
        routes to analyze_batch with the SAME idempotency key nemotron
        used (`fast_path_<id>`), the camera carried through, and the
        single detection as the batch — the §6 'never originates an
        event' rule stays enforced by the batch gate, not bypassed."""
        from backend.services.vlm_analyzer import VlmAnalyzer

        analyzer = VlmAnalyzer(redis_client=AsyncMock())
        calls: dict = {}

        async def _fake_batch(batch_id, camera_id=None, detection_ids=None, **kw):
            calls.update(batch_id=batch_id, camera_id=camera_id, detection_ids=detection_ids)
            return SimpleNamespace(id=1, risk_score=10, risk_level="low")

        monkeypatch.setattr(analyzer, "analyze_batch", _fake_batch)
        out = await analyzer.analyze_detection_fast_path(camera_id="cam", detection_id=42)
        assert out.id == 1
        assert calls == {"batch_id": "fast_path_42", "camera_id": "cam", "detection_ids": [42]}

    async def test_streaming_scored_answers_the_shared_vocabulary(self, monkeypatch) -> None:
        """The SSE route json.dumps every update, so the update dict must
        carry the shared event_type vocabulary — a scored vlm verdict
        completes with ITS OWN values (no level invention: level comes
        from the severity service exactly as the analyzer stored it)."""
        from backend.services.vlm_analyzer import VlmAnalyzer

        analyzer = VlmAnalyzer(redis_client=AsyncMock())
        event = SimpleNamespace(
            id=7, risk_score=62, risk_level="medium", summary="someone at the door", reasoning="r"
        )
        monkeypatch.setattr(analyzer, "analyze_batch", AsyncMock(return_value=event))
        updates = [u async for u in analyzer.analyze_batch_streaming("b1", camera_id="cam")]
        assert updates, "streaming answers at least one update"
        final = updates[-1]
        assert final["event_type"] == "complete"
        assert final["event_id"] == 7
        assert final["risk_score"] == 62
        assert final["risk_level"] == "medium"

    async def test_streaming_verification_failed_never_lies_50_medium(self, monkeypatch) -> None:
        """S5/D11: a failed verification carries NULL score/level. The
        legacy streaming path defaults them to 50/"medium" — the exact
        default-score lie rev 5 retired. The vlm side answers an error
        update naming the failure instead. (The analyzer's failure arm
        raises nothing, so the adapter sees the NULL-scored Event.)"""
        from backend.services.vlm_analyzer import VlmAnalyzer

        analyzer = VlmAnalyzer(redis_client=AsyncMock())
        failed = SimpleNamespace(
            id=8,
            risk_score=None,
            risk_level=None,
            summary="VLM verification failed; this event needs review.",
            reasoning="engine timeout",
        )
        monkeypatch.setattr(analyzer, "analyze_batch", AsyncMock(return_value=failed))
        updates = [u async for u in analyzer.analyze_batch_streaming("b2", camera_id="cam")]
        final = updates[-1]
        assert final["event_type"] == "error", "a NULL-score event is not a 50/medium complete"
        assert "50" not in str(final)
        assert "medium" not in str(final)


class TestSeamsGoThroughTheFactory:
    """No production path constructs NemotronAnalyzer directly — each
    seam asks the factory, so the mode decision is made once and nowhere
    else. Pinned structurally (source scan): a future fifth seam that
    imports NemotronAnalyzer directly trips this, and the plan's list of
    seam files is the scan's scope."""

    SEAM_FILES: ClassVar[list[str]] = [
        "backend/services/pipeline_workers.py",
        "backend/services/batch_aggregator.py",
        "backend/api/dependencies.py",
        "backend/core/container.py",
    ]

    def test_no_seam_constructs_nemotron_directly(self) -> None:
        from pathlib import Path

        repo = Path(__file__).resolve().parents[4]
        for rel in self.SEAM_FILES:
            text = (repo / rel).read_text()
            # `NemotronAnalyzer(` as a CALL must not appear; type
            # annotations naming the class are fine (they name the union).
            call_lines = [
                ln.strip()
                for ln in text.splitlines()
                if "NemotronAnalyzer(" in ln and not ln.strip().startswith(("#", ">>>"))
            ]
            assert not call_lines, f"{rel} still constructs the analyzer directly: {call_lines}"

    def test_analysis_worker_default_analyzer_is_mode_built(self) -> None:
        """The worker's `analyzer or ...` default line runs the factory,
        not NemotronAnalyzer — vlm mode gets the vlm analyzer even when
        main.py passed no explicit instance."""
        from unittest.mock import patch

        from backend.services import pipeline_workers as pw

        with patch.object(pw, "build_pipeline_analyzer", autospec=True) as factory:
            factory.return_value = MagicMock()
            worker = pw.AnalysisQueueWorker(redis_client=MagicMock())
        factory.assert_called_once()
        assert worker._analyzer is factory.return_value
