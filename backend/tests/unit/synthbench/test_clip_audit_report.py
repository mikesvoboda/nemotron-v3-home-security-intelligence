"""The bias report behind `clip audit bias` (ISS-038's survivor-bias acceptance).

Three printings, one per thing the audit learns: the survivor rate per intended-motion
class (the ready-over-decided fraction H3's crossing-motion failures would otherwise hide,
Wilson-intervalled because every real round's denominator is tens, not hundreds), the
declared-versus-picked scene and threat matrices (the blind audit's whole point: a clip
whose scene the auditor cannot recover is a clip the corpus misstates), and the two
disclosures that must be on the page whether or not anything was answered (frame-sampled,
not scripted triplets; H3-rendered, not filmed).

The report is a function over already-read files, so these tests hand it rows and a
population directly; the command's own loading is exercised in test_clip_audit_command.py.
"""

from __future__ import annotations

from synthbench.contract.clip_audit import ClipAuditDrawRow
from synthbench.score.clip_audit_report import report
from synthbench.taxonomy.model import load_taxonomy

from backend.evaluation.s_metrics import wilson_interval

TAX = load_taxonomy()
_NOW = "2026-10-07T12:00:00+00:00"


def _row(event_id: str, scenario: str, group: str, **overrides: object) -> ClipAuditDrawRow:
    base: dict[str, object] = {
        "event_id": event_id,
        "side": "incident" if group in ("threat", "suspicious") else "benign",
        "group": group,
        "scenario": scenario,
        "lighting": "day",
        "weather": "clear",
        "intended_motion": "in-place",
        "basis": "ready-census",
    }
    return ClipAuditDrawRow(**{**base, **overrides})


def _report(draw=(), answers=None, population=None) -> str:
    return report(TAX, "clips-x", "tierb-v0", list(draw), answers or {}, population or {}, _NOW)


class TestSurvivor:
    def test_the_rate_is_ready_over_decided_with_a_wilson_interval(self) -> None:
        population = {
            "C-x-000": ("crossing", "ready"),
            "C-x-001": ("crossing", "failed"),
            "C-x-002": ("crossing", "failed"),
            "C-x-003": ("crossing", "failed"),
        }
        text = _report(population=population)
        lo, hi = wilson_interval(1, 4)
        line = next(line for line in text.splitlines() if line.startswith("crossing:"))
        assert line == (
            f"crossing: 1/4 ready (25.0 %, Wilson 95 % CI {lo * 100:.1f}-{hi * 100:.1f} %)"
        )

    def test_clips_still_open_are_counted_out_of_the_denominator(self) -> None:
        # A reroll mid-flight is not a survivor or a casualty; the rate says what clips
        # H3 finished deciding, and the open count is printed beside it.
        population = {f"C-x-00{i}": ("in-place", "open") for i in range(5)}
        population["C-x-009"] = ("in-place", "ready")
        line = next(
            line for line in _report(population=population).splitlines()
            if line.startswith("in-place:")
        )  # fmt: skip
        assert line.startswith("in-place: 1/1 ready (100.0 %") and "5 open" in line

    def test_a_class_with_nothing_decided_says_so_instead_of_a_fake_rate(self) -> None:
        # wilson_interval(0, 0) is (0, 1) - honest as an interval, wrong as a headline.
        text = _report(population={"C-x-000": ("crossing", "open")})
        assert "crossing: no decided clip" in text

    def test_the_unclassified_class_is_counted_out_loud(self) -> None:
        population = {
            "C-x-000": ("other", "ready"),
            "C-x-001": ("other", "failed"),
            "C-x-002": ("in-place", "ready"),
        }
        text = _report(population=population)
        assert "other: 1/2 ready" in text
        assert "classified other: 2" in text  # the count no named class may hide


class TestMatrices:
    def test_scene_agreement_counts_the_auditors_pick_against_the_declaration(self) -> None:
        draw = [
            _row("C-x-000", "package_theft", "threat"),
            _row("C-x-001", "trying_car_doors", "suspicious"),
        ]
        answers = {
            ("C-x-000", "scene"): "package_theft",  # agreement
            ("C-x-001", "scene"): "package_theft",  # the mislabel the audit exists to find
        }
        text = _report(draw, answers)
        assert "scene agreement 1/2 (50.0 %" in text
        assert "trying_car_doors -> package_theft: 1" in text

    def test_an_unanswered_clip_is_not_counted_as_wrong(self) -> None:
        draw = [
            _row("C-x-000", "package_theft", "threat"),
            _row("C-x-001", "package_theft", "threat"),
        ]
        answers = {("C-x-000", "scene"): "package_theft"}
        assert "scene agreement 1/1 (100.0 %" in _report(draw, answers)

    def test_the_threat_matrix_compares_the_declared_group_band_to_the_pick(self) -> None:
        # The three band families are the contract's reading: threat groups are a danger,
        # suspicious groups are record-worthy, everything benign (hard negatives too) is
        # ordinary activity.
        draw = [
            _row("C-x-000", "masked_intruder_night", "threat"),
            _row("C-x-001", "loitering", "suspicious"),
            _row("C-x-002", "power_tools_at_night", "hard_negative"),
        ]
        answers = {
            ("C-x-000", "threat"): "none",  # the auditor calls the danger ordinary
            ("C-x-001", "threat"): "record",  # agreement
            ("C-x-002", "threat"): "none",  # agreement (a hard negative is none)
        }
        text = _report(draw, answers)
        assert "threat agreement 2/3 (66.7 %" in text
        assert "threat -> none: 1" in text

    def test_nothing_answered_prints_no_matrix_rather_than_an_empty_one(self) -> None:
        assert "nothing answered yet" in _report([_row("C-x-000", "package_theft", "threat")])


class TestCompleteness:
    def test_prop_asks_count_toward_a_clip_being_answered(self) -> None:
        # Four always-asked questions; prop opens behind a pick that names a prop, so a
        # package_theft pick without the prop mark leaves the clip short.
        draw = [
            _row("C-x-000", "package_theft", "threat"),
            _row("C-x-001", "neighbor_passing", "benign"),
        ]
        four = {
            "motion": "in-place",
            "scene": "package_theft",
            "conditions": "y",
            "threat": "threat",
        }
        answers = {(f"C-x-{i:03d}", key): value for i in (0, 1) for key, value in four.items()}
        answers[("C-x-001", "scene")] = "neighbor_passing"  # propless: four marks complete it
        answers[("C-x-001", "threat")] = "none"
        assert "answered 1 of 2" in _report(draw, answers)
        answers[("C-x-000", "prop")] = "y"
        assert "answered 2 of 2" in _report(draw, answers)

    def test_prop_marks_are_counted(self) -> None:
        answers = {
            ("C-x-000", "prop"): "y",
            ("C-x-001", "prop"): "y",
            ("C-x-002", "prop"): "n",
        }
        assert "prop marks: y 2, n 1, u 0" in _report(answers=answers)


class TestDisclosures:
    def test_the_two_disclosures_print_even_over_an_empty_audit(self) -> None:
        text = _report()
        assert "frame-sampled from rendered clips, not scripted triplets" in text
        assert "H3 rendered" in text  # realism: nothing here was filmed

    def test_the_header_names_the_round_version_and_generation_time(self) -> None:
        text = _report()
        assert "clip audit bias clips-x (corpus tierb-v0)" in text
        assert _NOW in text
