"""Batch-16c mutation-kill battery: nemotron_streaming enrichment/warning shapes.

Target: the 121-key ns16c∩ns16b survivor intersection (measured: 230/303 +
258/275 logs, /tmp/redcheck-ns16.log /tmp/redcheck-ns16b.log; set diff
`comm -12 /tmp/s16.txt /tmp/s16b.txt` = 121 keys: 102 analyze_batch_streaming
+ 19 call_llm_streaming). Root cause of the class: BOTH prior batteries drove
analysis with enrichment=None everywhere (make_analyzer's AsyncMock defaults)
— so `enriched_context=None`/`enrichment_result=None` kwarg mutants were
indistinguishable — and neither pins logger calls at all (grep-verified).

Every expected value MEASURED against shipped production this session
(/tmp/b16c-harness.py -> /tmp/b16c-probes.json); production NOT bent.

- SUCCESS-PATH ENRICHMENT FLOW (kills the =None kwarg family): with POPULATED
  enrichment the shipped code forwards it to SIX call sites; each is pinned
  exact — call_llm_streaming kwargs (analyze L293-294), _build_prompt kwargs
  (call_llm L73-74), _build_enrichment_snapshot + _build_context_sources
  kwargs (L382-389), auto-tuner get_tuning_context kwargs (L231 camera_id/
  session), and the LLMInteraction.household_matches value MEASURED
  {'persons': [1], 'vehicles': [2]} (dict-iteration ships KEYS — pinned as
  shipped, not as arguably-intended; kills vehicle_matches=None and the
  household-dict mutants).
- WARNING SITES (kills the extra={"batch_id","error"} family — UPPER/XX
  renames, str(None), extra=None, whole-extra removal): three drives, each
  raising at exactly one site; message AND extra dict pinned EXACT, and the
  failed context kwarg MEASURED to '' while its siblings flow (camera-health
  ''/TUNE_CTX/HOUSEHOLD_CTX; auto-tuning ''/''/HOUSEHOLD_CTX; household
  ''/TUNE_CTX/'').
- LLMINTERACTION GUARD (kills the 5-key extra family + flow mutants):
  snapshot raise -> warning 'LLMInteraction creation failed' with extra
  EXACT {action,resource_id='456',resource_type,error_type='ValueError',
  error_message='snapboom'}, Event add survives (add_n 1), commit_count 2 —
  the observability-optional contract (NEM-4234) as shipped.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enrichment_pipeline import (
    EnrichmentResult,
    EnrichmentStatus,
    EnrichmentTrackingResult,
)
from backend.services.household_matcher import HouseholdMatch
from backend.tests.unit.services.test_nemotron_streaming_batch16 import (
    NSP,
    SSE_OK,
    make_analyzer,
    make_settings,
    run_analyze,
    run_llm,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

ENRICHED = "ENRICHED_CTX_POP"


def populated_analyzer():
    """MEASURED /tmp/b16c-harness.py populated_analyzer (b16c-probes.json)."""
    a = make_analyzer()
    a._get_enriched_context = AsyncMock(return_value=ENRICHED)
    er = EnrichmentResult(
        person_household_matches={
            1: HouseholdMatch(
                member_id=7,
                member_name="alice",
                similarity=0.91,
                match_type="person",
                member_role="resident",
            )
        },
        vehicle_household_matches={
            2: HouseholdMatch(
                vehicle_id="veh-9",
                vehicle_description="blue van",
                similarity=0.88,
                match_type="license_plate",
            )
        },
    )
    a._get_enrichment_result = AsyncMock(
        return_value=EnrichmentTrackingResult(
            status=EnrichmentStatus.FULL, successful_models=["clip"], data=er
        )
    )
    a._get_recent_scene_changes = AsyncMock(return_value=[])
    tuner = MagicMock()
    tuner.get_tuning_context = AsyncMock(return_value="TUNE_CTX")
    facade = MagicMock()
    facade.get_prompt_auto_tuner.return_value = tuner
    a._get_facade = MagicMock(return_value=facade)
    a._get_household_context = AsyncMock(return_value="HOUSEHOLD_CTX")
    a._build_enrichment_snapshot = MagicMock(return_value={"SNAP": 1})
    a._build_context_sources = MagicMock(return_value={"SOURCES": 2})
    return a, er, tuner


class TestEnrichmentFlowsToEverySite:
    """The =None kwarg family was invisible because both batteries drove
    enrichment=None; a POPULATED drive + exact kwargs pins makes every
    swallow a crash-or-mismatch."""

    async def test_analyze_forwards_enrichment_to_call_llm(self):
        a, er, _ = populated_analyzer()
        r = await run_analyze(a, chunks=("X",))
        kw = r["captured"]["kwargs"]
        # MEASURED b16c-probes A_success: exact values + identity for the
        # result object (an `=None` mutant diverges on BOTH).
        assert kw["enriched_context"] == ENRICHED
        assert kw["enrichment_result"] is er
        assert kw["household_context"] == "HOUSEHOLD_CTX"
        assert kw["auto_tuning_context"] == "TUNE_CTX"
        assert kw["camera_health_context"] == ""
        assert sorted(kw) == [
            "analyzer",
            "auto_tuning_context",
            "camera_health_context",
            "camera_name",
            "detection_dicts",
            "detections_list",
            "end_time",
            "enriched_context",
            "enrichment_result",
            "household_context",
            "start_time",
        ]

    async def test_build_prompt_kwargs_exact(self):
        # call_llm_streaming L73-74: enriched/enrichment kwargs into
        # _build_prompt — kill =None at the SECOND function's own surface.
        a, er, _ = populated_analyzer()
        r = await run_llm(
            a,
            SSE_OK,
            settings=make_settings(),
            enriched_context=ENRICHED,
            enrichment_result=er,
        )
        assert r["chunks"] == ["Based", " on", " the"]
        bp = a._build_prompt.call_args.kwargs
        assert bp["enriched_context"] == ENRICHED
        assert bp["enrichment_result"] is er

    async def test_snapshot_and_sources_kwargs_exact(self):
        a, er, _ = populated_analyzer()
        await run_analyze(a, chunks=("X",))
        snap = a._build_enrichment_snapshot.call_args.kwargs
        assert snap["enrichment_result"] is er
        assert snap["enriched_context"] == ENRICHED
        assert snap["detection_ids"] == [1, 2]  # MEASURED int-cast ids
        cs = a._build_context_sources.call_args.kwargs
        assert cs["enrichment_result"] is er
        assert cs["enriched_context"] == ENRICHED

    async def test_household_matches_measured_shape(self):
        # L390-405: the comprehensions iterate the MATCH DICTS (keys), so
        # shipped ships {'persons': [1], 'vehicles': [2]} — MEASURED, pinned
        # as shipped (production never bends; this is the wire contract the
        # LLMInteraction column stores). vehicle_matches=None mutant ->
        # vehicles [] -> red.
        a, _, _ = populated_analyzer()
        r = await run_analyze(a, chunks=("X",))
        lli = [o for o in (c.args[0] for c in r["add_calls"]) if hasattr(o, "household_matches")]
        assert len(lli) == 1
        assert lli[0].household_matches == {"persons": [1], "vehicles": [2]}

    async def test_tuner_called_with_camera_id_and_session(self):
        # L231 camera_id=camera_id -> None mutant dies on the exact kwargs.
        a, _, tuner = populated_analyzer()
        r = await run_analyze(a, chunks=("X",))
        kw = tuner.get_tuning_context.call_args.kwargs
        assert kw["camera_id"] == "test_camera"
        assert kw["session"] is r["session"]


class TestWarningSitesExactPayload:
    """extra={'batch_id','error'} family: renames/str(None)/None/removal all
    die on the EXACT dict; the message text rides along (None-mutants die on
    the positional pin)."""

    async def _drive(self, site: str, boom: str):
        a, _, _ = populated_analyzer()
        if site == "scene":
            a._get_recent_scene_changes = AsyncMock(side_effect=RuntimeError(boom))
        elif site == "tuner":
            a._get_facade = MagicMock(side_effect=RuntimeError(boom))
        else:
            a._get_household_context = AsyncMock(side_effect=RuntimeError(boom))
        with patch(f"{NSP}.logger.warning", autospec=True) as lw:
            r = await run_analyze(a, chunks=("X",))
        hits = [m for m in lw.call_args_list if "Failed to fetch" in str(m.args)]
        return hits, r, a

    async def test_camera_health_site_payload_and_fallback(self):
        hits, r, a = await self._drive("scene", "sceneboom")
        assert len(hits) == 1
        m = hits[0]
        assert m.args == ("Failed to fetch camera health context for streaming",)
        assert dict(m.kwargs["extra"]) == {"batch_id": "test_batch", "error": "sceneboom"}
        # MEASURED siblings keep flowing while the failed context is ''
        kw = r["captured"]["kwargs"]
        assert kw["camera_health_context"] == ""
        assert kw["auto_tuning_context"] == "TUNE_CTX"
        assert kw["household_context"] == "HOUSEHOLD_CTX"

    async def test_auto_tuning_site_payload_and_fallback(self):
        hits, r, _ = await self._drive("tuner", "tunerboom")
        m = hits[0]
        assert m.args == ("Failed to fetch auto-tuning context for streaming",)
        assert dict(m.kwargs["extra"]) == {"batch_id": "test_batch", "error": "tunerboom"}
        kw = r["captured"]["kwargs"]
        assert kw["auto_tuning_context"] == ""
        assert kw["camera_health_context"] == ""  # scene path OK -> '' (no changes)
        assert kw["household_context"] == "HOUSEHOLD_CTX"

    async def test_household_site_payload_and_fallback(self):
        hits, r, _ = await self._drive("household", "hhboom")
        m = hits[0]
        assert m.args == ("Failed to fetch household context for streaming",)
        assert dict(m.kwargs["extra"]) == {"batch_id": "test_batch", "error": "hhboom"}
        kw = r["captured"]["kwargs"]
        assert kw["household_context"] == ""
        assert kw["auto_tuning_context"] == "TUNE_CTX"


class TestLlmInteractionGuardContract:
    """NEM-4234: observability optional — the 5-key extra and the Event-
    survives flow are the shipped contract (MEASURED: add_n 1, commit 2)."""

    async def test_snapshot_failure_warns_with_five_key_extra(self):
        a, _, _ = populated_analyzer()
        a._build_enrichment_snapshot = MagicMock(side_effect=ValueError("snapboom"))
        with patch(f"{NSP}.logger.warning", autospec=True) as lw:
            r = await run_analyze(a, chunks=("X",))
        m = [x for x in lw.call_args_list if "LLMInteraction" in str(x.args)]
        assert len(m) == 1
        assert m[0].args == ("LLMInteraction creation failed",)
        assert dict(m[0].kwargs["extra"]) == {
            "action": "create_llm_interaction",
            "resource_id": "456",
            "resource_type": "llm_interaction",
            "error_type": "ValueError",
            "error_message": "snapboom",
        }
        # Event add survives, both commits happen, completion still yields
        assert len(r["add_calls"]) == 1
        assert r["commit_count"] == 2
