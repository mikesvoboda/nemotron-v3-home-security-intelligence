"""The clip audit instrument's pure half (ISS-038 acceptance; method per ISS-044 v2/OD-15).

The contract rows, the intended-motion classifier over the round's frozen motions, the
write-once audit draw (ready-incident census + benign mirror + flagged residue), and the
blind question sequence. The page and the command tests live in test_clip_audit_command.py;
the confusion matrices in test_clip_audit_report.py.

Real-corpus anchors (computed offline 2026-10-07 from the mounted tierb-v0 corpus, never
read by these tests): the 459 rounds' motions classify exhaustively - crossing 83,
line-of-sight 33, in-place 259 intended - and the ready incidents skew in-place 14/17,
which is the survivor bias the disclosure exists to show (docs/synthbench/h3-prompt-notes.md
records crossing 0/13 for the hooded_jogger runners).
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from synthbench.audit.clip_sample import (
    MOTION_CLASSES,
    audit_draw,
    classify_intended_motion,
    conditions_question,
    motion_question,
    prop_question,
    scene_choices,
    threat_question,
)
from synthbench.contract.clip_audit import (
    MOTION_CHOICES,
    THREAT_CHOICES,
    ClipAuditAnswerRow,
    ClipAuditDrawRow,
    ClipAuditFlagRow,
)
from synthbench.taxonomy.model import load_taxonomy

TAX = load_taxonomy()

_NOW = "2026-10-07T12:00:00+00:00"


def _row(event_id: str = "C-clips-1-000", **overrides: object) -> ClipAuditDrawRow:
    base: dict[str, object] = {
        "event_id": event_id,
        "side": "incident",
        "group": "threat",
        "scenario": "package_theft",
        "lighting": "day",
        "weather": "clear",
        "intended_motion": "in-place",
        "basis": "ready-census",
    }
    return ClipAuditDrawRow(**{**base, **overrides})


class TestDrawRow:
    def test_round_trip(self) -> None:
        row = _row()
        assert ClipAuditDrawRow.model_validate_json(row.model_dump_json()) == row

    def test_basis_is_closed(self) -> None:
        with pytest.raises(ValidationError):
            _row(basis="vibes")


class TestAnswerRow:
    def test_mark_answer_round_trip(self) -> None:
        row = ClipAuditAnswerRow(event_id="C-clips-1-000", question="prop", answer="n", time=_NOW)
        assert ClipAuditAnswerRow.model_validate_json(row.model_dump_json()) == row

    @pytest.mark.parametrize(
        ("question", "pick"),
        [
            ("motion", "crossing"),
            ("scene", "package_theft"),
            ("threat", "record"),
        ],
    )
    def test_picks_round_trip(self, question: str, pick: str) -> None:
        row = ClipAuditAnswerRow(event_id="C-clips-1-000", question=question, pick=pick, time=_NOW)
        assert ClipAuditAnswerRow.model_validate_json(row.model_dump_json()) == row

    def test_both_shapes_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="never both"):
            ClipAuditAnswerRow(
                event_id="C-clips-1-000",
                question="motion",
                answer="y",
                pick="crossing",
                time=_NOW,
            )

    def test_neither_shape_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ClipAuditAnswerRow(event_id="C-clips-1-000", question="motion", time=_NOW)

    def test_motion_pick_is_closed(self) -> None:
        with pytest.raises(ValidationError, match="motion is picked"):
            ClipAuditAnswerRow(
                event_id="C-clips-1-000", question="motion", pick="floating", time=_NOW
            )

    def test_prop_wants_a_mark_not_a_pick(self) -> None:
        with pytest.raises(ValidationError, match="prop is answered"):
            ClipAuditAnswerRow(event_id="C-clips-1-000", question="prop", pick="package", time=_NOW)

    def test_scene_wants_a_pick_not_a_mark(self) -> None:
        with pytest.raises(ValidationError, match="scene is the blind"):
            ClipAuditAnswerRow(event_id="C-clips-1-000", question="scene", answer="y", time=_NOW)


class TestFlagRow:
    def test_note_defaults_empty(self) -> None:
        row = ClipAuditFlagRow(event_id="C-clips-1-000", flagged_by="prop-presence")
        assert row.note == ""
        assert json.loads(row.model_dump_json())["flagged_by"] == "prop-presence"


class TestClassifier:
    """Vocabulary from docs/synthbench/h3-prompt-notes.md's own counted wordings."""

    @pytest.mark.parametrize(
        ("motion", "expected"),
        [
            ("The person runs across the paving past the gate.", "crossing"),
            ("The walker walks along the pavement toward the neighbor's yard.", "crossing"),
            ("The child moves from left to right along the sidewalk.", "crossing"),
            # crossing outranks line-of-sight: notes count "across...toward" as crossing.
            ("She crosses the lawn and walks toward the house.", "crossing"),
            ("The man walks up the drive toward the house.", "line-of-sight"),
            ("The delivery driver approaches the porch steps carrying a package.", "line-of-sight"),
            ("The person backs away from the window slowly.", "line-of-sight"),
            ("The gardener works in place, raking the same patch of lawn.", "in-place"),
            ("The courier stays at the door and keeps scanning a phone.", "in-place"),
            ("The dog remains on the patio and circles its bed.", "in-place"),
            ("Leaves move a little in the wind.", "other"),
        ],
    )
    def test_classify(self, motion: str, expected: str) -> None:
        assert classify_intended_motion(motion) == expected

    def test_the_two_vocabularies_share_three_names_each_keeps_its_own(self) -> None:
        # The classifier's "other" is a motion no keyword family caught - a disclosure
        # count, never a button for a human to press. "unclear" is the reverse: only a
        # viewer can say they cannot tell, and the report folds that pick in (ISS-038's
        # stratifier is the auditor's realized class, so the report needs both).
        assert set(MOTION_CLASSES[:3]) == {"crossing", "line-of-sight", "in-place"}
        assert set(MOTION_CLASSES[:3]) <= set(MOTION_CHOICES)
        assert "other" not in MOTION_CHOICES
        assert "unclear" in MOTION_CHOICES and "unclear" not in MOTION_CLASSES


class _Spec:
    """Enough ClipSpec shape for the sampler: event_id, label and cell facts."""

    def __init__(
        self,
        event_id: str,
        *,
        label: str,
        group: str,
        scenario: str,
        lighting: str,
        weather: str = "clear",
    ) -> None:
        self.event_id = event_id
        self.label = label
        self.cell = _Cell(group, scenario, lighting, weather)


class _Cell:
    def __init__(self, group: str, scenario: str, lighting: str, weather: str) -> None:
        self.group = group
        self.scenario = scenario
        self.lighting = lighting
        self.weather = weather


def _corpus() -> tuple[list[_Spec], dict[str, str], dict[str, str]]:
    """Three ready incidents (two in-place, one crossing), four ready benign (two benign /
    two hard_negative, mixed motion), one rendered-but-untriaged incident (NOT drawn), one
    failed incident (not drawn), one ready ambiguous (drawn nowhere)."""
    specs = [
        _Spec(
            "C-c-000", label="incident", group="threat", scenario="package_theft", lighting="day"
        ),
        _Spec(
            "C-c-001",
            label="incident",
            group="suspicious",
            scenario="loitering",
            lighting="dusk",
            weather="snow",
        ),
        _Spec(
            "C-c-002",
            label="incident",
            group="threat",
            scenario="package_theft",
            lighting="ir_night",
        ),
        _Spec(
            "C-c-003", label="benign", group="benign", scenario="neighbor_passing", lighting="day"
        ),
        _Spec("C-c-004", label="benign", group="benign", scenario="wildlife", lighting="day"),
        _Spec(
            "C-c-005",
            label="benign",
            group="hard_negative",
            scenario="yard_maintenance",
            lighting="dusk",
        ),
        _Spec(
            "C-c-006",
            label="benign",
            group="hard_negative",
            scenario="yard_maintenance",
            lighting="dusk",
        ),
        _Spec(
            "C-c-007", label="incident", group="threat", scenario="package_theft", lighting="day"
        ),
        _Spec("C-c-008", label="incident", group="threat", scenario="loitering", lighting="day"),
        _Spec(
            "C-c-009",
            label="ambiguous",
            group="ambiguous",
            scenario="costume_weapon",
            lighting="dusk",
        ),
    ]
    motions = {
        "C-c-000": "The courier approaches the porch and sets a package down.",  # line-of-sight
        "C-c-001": "The person remains at the corner and keeps scanning the street.",  # in-place
        "C-c-002": "The figure walks across the yard past the shed.",  # crossing
        "C-c-003": "The neighbor walks along the pavement past the hedge.",  # crossing
        "C-c-004": "The dog remains on the patio and circles its bed.",  # in-place
        "C-c-005": "The gardener works in place, raking the same patch.",  # in-place
        "C-c-006": "The gardener works in place, edging the same patch.",  # in-place
        "C-c-007": "The person stays at the car and tries the handle.",  # in-place
        "C-c-008": "The teen loiters in place near the mailbox.",  # in-place
        "C-c-009": "The boy shifts his weight in place on the pavement.",  # in-place
    }
    status = {
        "C-c-000": "ready",
        "C-c-001": "ready",
        "C-c-002": "ready",
        "C-c-003": "ready",
        "C-c-004": "ready",
        "C-c-005": "ready",
        "C-c-006": "ready",
        "C-c-007": "rendered",
        "C-c-008": "failed",
        "C-c-009": "ready",
    }
    return specs, motions, status


class TestAuditDraw:
    def test_incident_side_is_the_ready_census(self) -> None:
        specs, motions, status = _corpus()
        rows = audit_draw(specs, motions, status, round_name="clips-1")
        incidents = [row for row in rows if row.basis == "ready-census"]
        assert [row.event_id for row in incidents] == ["C-c-000", "C-c-001", "C-c-002"]
        assert all(row.side == "incident" for row in incidents)
        assert [row.intended_motion for row in incidents] == [
            "line-of-sight",
            "in-place",
            "crossing",
        ]
        # The row carries the conditions the page may show: the page must never read a
        # spec for them (spec.json holds the motion, which names the scenario's props).
        assert [(row.lighting, row.weather) for row in incidents] == [
            ("day", "clear"),
            ("dusk", "snow"),
            ("ir_night", "clear"),
        ]

    def test_benign_mirrors_the_incident_count(self) -> None:
        # Freeze F2: the benign half mirrors the incident half. 3 ready incidents, 4 ready
        # benign: draw 3, spread one per stratum (benign:crossing, benign:in-place,
        # hard_negative:in-place) - a stratum with two members never takes two slots
        # while another gets none.
        specs, motions, status = _corpus()
        rows = audit_draw(specs, motions, status, round_name="clips-1")
        benign = [row for row in rows if row.basis == "benign-stratified"]
        assert len(benign) == 3
        assert {(row.group, row.intended_motion) for row in benign} == {
            ("benign", "crossing"),
            ("benign", "in-place"),
            ("hard_negative", "in-place"),
        }

    def test_ambiguous_and_nonready_are_never_drawn(self) -> None:
        specs, motions, status = _corpus()
        rows = audit_draw(specs, motions, status, round_name="clips-1")
        ids = {row.event_id for row in rows}
        assert "C-c-009" not in ids  # ready, but ambiguous is no audit side
        assert "C-c-007" not in ids  # rendered, no verdict yet
        assert "C-c-008" not in ids  # failed

    def test_benign_target_can_be_raised(self) -> None:
        specs, motions, status = _corpus()
        rows = audit_draw(specs, motions, status, round_name="clips-1", benign_target=4)
        benign = [row for row in rows if row.basis == "benign-stratified"]
        assert len(benign) == 4  # all four ready benign, never more than exist
        assert [row.event_id for row in benign] == ["C-c-003", "C-c-004", "C-c-005", "C-c-006"]

    def test_flagged_residue_joins_once(self) -> None:
        # The pre-screen flags a not-ready incident and one clip already censused: the
        # former joins (side from its spec), the latter is not listed twice.
        specs, motions, status = _corpus()
        flags = [
            ClipAuditFlagRow(event_id="C-c-007", flagged_by="prop-presence", note="no package"),
            ClipAuditFlagRow(event_id="C-c-000", flagged_by="prop-presence"),
        ]
        rows = audit_draw(specs, motions, status, round_name="clips-1", flagged=flags)
        assert [row.event_id for row in rows].count("C-c-000") == 1
        assert [row.event_id for row in rows].count("C-c-007") == 1
        flag_row = next(row for row in rows if row.basis == "flagged")
        assert flag_row.event_id == "C-c-007" and flag_row.side == "incident"

    def test_draw_is_deterministic(self) -> None:
        specs, motions, status = _corpus()
        first = audit_draw(specs, motions, status, round_name="clips-1")
        second = audit_draw(specs, motions, status, round_name="clips-1")
        assert [row.model_dump() for row in first] == [row.model_dump() for row in second]


class TestQuestions:
    def test_scene_choices_are_the_taxonomy_list_blind(self) -> None:
        choices = scene_choices(TAX)
        assert [choice.id for choice in choices] == sorted(s.id for s in TAX.scenarios)
        # blind means the list carries no per-clip declaration; it is the whole taxonomy.
        assert len(choices) == len(TAX.scenarios)

    def test_motion_question_offers_every_choice(self) -> None:
        question = motion_question()
        assert question.key == "motion"
        assert set(question.choices) == set(MOTION_CHOICES)

    def test_threat_question_offers_every_choice(self) -> None:
        assert set(threat_question().choices) == set(THREAT_CHOICES)

    def test_prop_question_names_the_auditors_own_pick(self) -> None:
        theft = next(s for s in TAX.scenarios if s.id == "package_theft")
        question = prop_question(theft)
        assert question is not None and question.key == "prop"
        assert "package" in question.text
        assert question.choices == ()  # a y/n/u mark

    def test_a_pick_without_props_asks_no_prop_question(self) -> None:
        loitering = next(s for s in TAX.scenarios if s.id == "loitering")
        assert prop_question(loitering) is None

    def test_conditions_question_states_the_claim(self) -> None:
        question = conditions_question("ir_night", "snow")
        assert question.key == "conditions"
        assert "ir night" in question.text and "snow" in question.text
        assert question.choices == ()  # a y/n/u mark
