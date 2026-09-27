"""Unit tests for the VLM verdict contract models.

Covers backend/services/vlm_verdict.py — the `vlm_assess` request/response
pydantic models every other vlm_assess artifact (generated schema, goldens,
FakeProvider, and from 1.3 the vlm_client) derives from. The contract-level
pins (schema == live model, field-set compatibility with the shipped API and
evaluation classes, golden shape) live in scripts/test_gen_ai_contract.py;
this file tests the VALIDATION BEHAVIOR: every §3 invariant expressed as a
Field must actually reject its violation.

Spec §3 invariants under test:
    - verdict is a closed enum {confirmed, rejected, uncertain}
    - risk_score is an int in [0, 100] — and a float is NOT an int (the
      wire's "0.25"-style regression class)
    - no defaults: a partially-echoed response fails, never half-passes
    - extra="forbid" on all three models: a model that starts emitting
      risk_level (or anything else) is rejected at parse, per §3's
      "risk_level NEVER from model" row
    - criteria is non-empty (an empty verification is not a verdict)
    - image_paths is 1..4 (spec §3: up to four key frames)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.services.vlm_verdict import (
    VlmAssessContext,
    VlmAssessRequest,
    VlmCriterion,
    VlmProvenance,
    VlmVerdict,
)

GOOD_VERDICT = {
    "verdict": "confirmed",
    "risk_score": 82,
    "summary": "Courier at the door with a hand-truck",
    "reasoning": "Uniform, badge visible, package in hand",
    "description": "A person in a delivery uniform",
    "criteria": [{"name": "uniform", "passed": True, "evidence": "hi-vis vest"}],
    "provenance": {"engine": "llama-v0.0.0", "model_id": "Qwen3VL-4B"},
}


def _verdict(**over: object) -> dict:
    return {**GOOD_VERDICT, **over}


class TestVlmVerdict:
    def test_valid_verdict_round_trips(self) -> None:
        v = VlmVerdict.model_validate(GOOD_VERDICT)
        assert v.verdict == "confirmed"
        assert v.risk_score == 82
        assert v.criteria[0].name == "uniform"
        assert v.provenance.model_id == "Qwen3VL-4B"

    @pytest.mark.parametrize("verdict", ["confirmed", "rejected", "uncertain"])
    def test_verdict_enum_accepts_all_three(self, verdict: str) -> None:
        assert VlmVerdict.model_validate(_verdict(verdict=verdict)).verdict == verdict

    def test_verdict_enum_rejects_invented_member(self) -> None:
        # the ladder's DEGRADED vocabulary lives in the analyzer, not the wire
        with pytest.raises(ValidationError, match="verdict"):
            VlmVerdict.model_validate(_verdict(verdict="degraded"))

    @pytest.mark.parametrize("score", [-1, 101])
    def test_risk_score_bounds(self, score: int) -> None:
        with pytest.raises(ValidationError, match="risk_score"):
            VlmVerdict.model_validate(_verdict(risk_score=score))

    def test_risk_score_accepts_both_endpoints(self) -> None:
        assert VlmVerdict.model_validate(_verdict(risk_score=0)).risk_score == 0
        assert VlmVerdict.model_validate(_verdict(risk_score=100)).risk_score == 100

    def test_risk_score_rejects_float(self) -> None:
        # §3 types risk_score as an int 0-100; a "0.25"-style float on the
        # wire is the spec's legacy-scale confusion and must not parse.
        with pytest.raises(ValidationError, match="risk_score"):
            VlmVerdict.model_validate(_verdict(risk_score=0.25))

    @pytest.mark.parametrize("field", ["summary", "reasoning", "description"])
    def test_text_fields_reject_empty(self, field: str) -> None:
        with pytest.raises(ValidationError, match=field):
            VlmVerdict.model_validate(_verdict(**{field: ""}))

    def test_criteria_rejects_empty_list(self) -> None:
        with pytest.raises(ValidationError, match="criteria"):
            VlmVerdict.model_validate(_verdict(criteria=[]))

    def test_extra_keys_forbidden(self) -> None:
        # §3: risk_level NEVER comes from the model — SeverityService derives
        # it. A server that starts echoing it fails at parse, not silently.
        with pytest.raises(ValidationError, match="Extra inputs"):
            VlmVerdict.model_validate(_verdict(risk_level="high"))

    def test_no_field_has_a_default(self) -> None:
        # a default would let a partially-echoed response validate while
        # lying about the missing value — every field is required, pinned
        for name, f in VlmVerdict.model_fields.items():
            assert f.is_required(), f"VlmVerdict.{name} grew a default"

    def test_round_trip_json_preserves_everything(self) -> None:
        v = VlmVerdict.model_validate(GOOD_VERDICT)
        assert VlmVerdict.model_validate_json(v.model_dump_json()) == v


class TestVlmCriterion:
    def test_name_and_evidence_must_be_non_empty(self) -> None:
        for over in ({"name": ""}, {"evidence": ""}):
            with pytest.raises(ValidationError):
                VlmCriterion.model_validate({"name": "x", "passed": True, "evidence": "y", **over})

    def test_extra_key_forbidden(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs"):
            VlmCriterion.model_validate(
                {"name": "n", "passed": True, "evidence": "e", "confidence": 0.9}
            )


class TestVlmProvenance:
    def test_both_fields_required_non_empty(self) -> None:
        for over in ({"engine": ""}, {"model_id": ""}, {"engine": None}):
            with pytest.raises(ValidationError):
                VlmProvenance.model_validate({"engine": "e", "model_id": "m", **over})


class TestVlmAssessRequest:
    def _ctx(self) -> dict:
        return {"camera_id": "front_door", "timestamp": "2026-09-25T12:00:00Z"}

    def test_valid_request_round_trips(self) -> None:
        req = VlmAssessRequest.model_validate(
            {
                "image_paths": ["/export/foscam/cam1/000001.jpg"],
                "context": {**self._ctx(), "specialist_outputs": {"faces": "0 faces"}},
            }
        )
        assert req.image_paths[0].endswith("000001.jpg")
        assert req.context.camera_id == "front_door"
        # Rev 6: the context (the AssessInput mirror) is the ONE carrier of
        # the specialist texts - no top-level request duplicate.
        assert req.context.specialist_outputs == {"faces": "0 faces"}
        assert "specialist_outputs" not in VlmAssessRequest.model_fields

    @pytest.mark.parametrize("paths", [[], ["a", "b", "c", "d", "e"]])
    def test_image_paths_bounded_1_to_4(self, paths: list[str]) -> None:
        with pytest.raises(ValidationError, match="image_paths"):
            VlmAssessRequest.model_validate({"image_paths": paths, "context": self._ctx()})

    def test_four_images_accepted(self) -> None:
        req = VlmAssessRequest.model_validate(
            {"image_paths": ["a", "b", "c", "d"], "context": self._ctx()}
        )
        assert len(req.image_paths) == 4

    def test_context_defaults(self) -> None:
        ctx = VlmAssessContext.model_validate({"camera_id": "c", "timestamp": "t"})
        assert ctx.detections == []
        assert ctx.zones == []
        assert ctx.zone_crossing is False
        assert ctx.household == {}

    def test_extra_keys_forbidden_on_request_and_context(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs"):
            VlmAssessRequest.model_validate(
                {"image_paths": ["a"], "context": self._ctx(), "risk_level": "high"}
            )
        with pytest.raises(ValidationError, match="Extra inputs"):
            VlmAssessContext.model_validate({**self._ctx(), "camera_name": "lie"})
