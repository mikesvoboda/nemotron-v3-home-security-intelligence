"""P1 measurement helpers and per-record dispatch (fake tools; no GPU)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from synthbench.spikes.p1_bakeoff import cases
from synthbench.spikes.p1_bakeoff import measure as m


def test_normalize_plate_keeps_only_the_alphanumerics() -> None:
    # ALPR-style: the separator a model drew (or OCR dropped) never decides a plate
    assert m.normalize_plate(" 8kxr-417 ") == "8KXR417"
    assert m.normalize_plate("8KXR.417") == m.normalize_plate("8KXR 417") == "8KXR417"


@pytest.mark.parametrize(
    ("pred", "target", "expected"),
    [
        ("8KXR-417", "8KXR-417", 0.0),
        ("8KXR-41", "8KXR-417", 0.125),
        ("", "8KXR-417", 1.0),
    ],
)
def test_cer(pred: str, target: str, expected: float) -> None:
    assert m.cer(pred, target) == pytest.approx(expected)


def test_cosine_distance() -> None:
    assert m.cosine_distance([1.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)
    assert m.cosine_distance([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)


class FakeTools:
    def owl(self, image: Path, queries: tuple[str, ...]) -> dict[str, float]:
        return dict.fromkeys(queries, 0.5)

    def ocr(self, image: Path) -> list[m.Fragment]:
        return [("8KXR-417", (100.0, 180.0, 290.0, 220.0))]

    def face(self, image: Path) -> list[float] | None:
        return [1.0, 0.0]

    def clip_faces(self, clip: Path) -> list[list[float]]:
        return [[1.0, 0.0], [0.6, 0.8]]


def _rec(**kw: Any) -> dict[str, Any]:
    return {
        "model": "flux2-dev",
        "kind": "t2i",
        "case": "knife",
        "seed": 11,
        "output": "images/x.png",
        "ok": True,
    } | kw


def test_case_records_get_owl_scores(tmp_path: Path) -> None:
    out = m.measure_record(_rec(), tmp_path, FakeTools())
    assert out["owl"] == {"a knife": 0.5, "a person": 0.5}


def test_the_plate_case_is_read(tmp_path: Path) -> None:
    out = m.measure_record(_rec(case="legible_plate"), tmp_path, FakeTools())
    assert out["plate_exact"] is True and out["plate_cer"] == 0.0


def test_identity_records_get_an_embedding(tmp_path: Path) -> None:
    out = m.measure_record(_rec(case="identity"), tmp_path, FakeTools())
    assert out["face"] == [1.0, 0.0]


def test_clips_get_frame_drift(tmp_path: Path) -> None:
    out = m.measure_record(
        _rec(kind="i2v", case="identity_walk", output="clips/c.mp4"), tmp_path, FakeTools()
    )
    assert out["frame_drift_max"] == pytest.approx(0.4)


# Fragments as (text, (left, top, right, bottom)), listed in EasyOCR's confidence order.
PLATE = ("8KXR-417", (110.0, 180.0, 290.0, 220.0))
STATE_ABOVE = ("CALIFORNIA", (100.0, 150.0, 300.0, 170.0))  # above the plate, inside its x-span


@pytest.mark.parametrize(
    ("fragments", "exact", "expected_cer"),
    [
        # the reviewer's four probes: a correct plate with other text in the scene stays exact
        ([STATE_ABOVE, PLATE], True, 0.0),
        ([("42", (500.0, 180.0, 540.0, 220.0)), PLATE], True, 0.0),
        (
            [("417", (210.0, 180.0, 290.0, 220.0)), ("8KXR-", (110.0, 180.0, 200.0, 220.0))],
            True,
            0.0,
        ),
        ([("8KR417", (110.0, 180.0, 290.0, 220.0))], False, 1 / 7),
        # split around the state name: joins stay within one line, in left-to-right order
        (
            [
                STATE_ABOVE,
                ("417", (210.0, 180.0, 290.0, 220.0)),
                ("8KXR-", (110.0, 180.0, 200.0, 220.0)),
            ],
            True,
            0.0,
        ),
        # the hyphen lost between split fragments: alphanumerics match, so exact
        (
            [("417", (210.0, 180.0, 290.0, 220.0)), ("8KXR", (110.0, 180.0, 190.0, 220.0))],
            True,
            0.0,
        ),
        # another separator, lower case: still exact
        ([("8kxr.417", (110.0, 180.0, 290.0, 220.0))], True, 0.0),
        ([], False, 1.0),
    ],
)
def test_plate_scoring_takes_the_best_fragment_or_adjacent_join(
    tmp_path: Path, fragments: list[m.Fragment], exact: bool, expected_cer: float
) -> None:
    class Ocr(FakeTools):
        def ocr(self, image: Path) -> list[m.Fragment]:
            return fragments

    out = m.measure_record(_rec(case="legible_plate"), tmp_path, Ocr())
    assert out["plate_exact"] is exact
    assert out["plate_cer"] == pytest.approx(expected_cer)


def test_plate_candidates_join_only_within_a_line() -> None:
    candidates = m.plate_candidates([STATE_ABOVE, ("B", (60.0, 180.0, 90.0, 220.0)), PLATE])
    assert set(candidates) == {"CALIFORNIA", "B", "8KXR-417", "B8KXR-417"}


def test_the_ocr_fragments_are_kept_in_reading_order(tmp_path: Path) -> None:
    class Ocr(FakeTools):
        def ocr(self, image: Path) -> list[m.Fragment]:
            return [("42", (500.0, 180.0, 540.0, 220.0)), PLATE, STATE_ABOVE]

    out = m.measure_record(_rec(case="legible_plate"), tmp_path, Ocr())
    assert out["ocr_fragments"] == ["CALIFORNIA", "8KXR-417", "42"]
    assert out["plate_text"] == "8KXR-417"


def test_the_plate_text_is_kept_as_read(tmp_path: Path) -> None:
    class Ocr(FakeTools):
        def ocr(self, image: Path) -> list[m.Fragment]:
            return [("8kxr", (110.0, 180.0, 190.0, 220.0)), ("417.", (210.0, 180.0, 290.0, 220.0))]

    out = m.measure_record(_rec(case="legible_plate"), tmp_path, Ocr())
    assert out["plate_text"] == "8kxr417."
    assert out["plate_exact"] is True and out["plate_cer"] == 0.0


def test_every_native_size_is_measured_at_the_smallest_ones_area() -> None:
    # I6: OCR, OWL and faces see the same pixel budget whatever the model's native size.
    assert min(cases.MODEL_SIZES.values(), key=lambda wh: wh[0] * wh[1]) == m.MEASURE_SIZE
    area = m.MEASURE_SIZE[0] * m.MEASURE_SIZE[1]
    assert m.measure_size(*m.MEASURE_SIZE) == m.MEASURE_SIZE
    for width, height in [*cases.MODEL_SIZES.values(), *cases.CLIP_SIZES.values()]:
        w, h = m.measure_size(width, height)
        assert w * h == pytest.approx(area, rel=0.005)
        assert w / h == pytest.approx(width / height, rel=0.005)


def test_at_measure_size_resizes_a_pil_image_keeping_its_aspect() -> None:
    image = Image.new("RGB", (1920, 1088))
    resized = m.at_measure_size(image)
    assert resized.size == m.measure_size(1920, 1088) == (1350, 765)
    small = Image.new("RGB", m.MEASURE_SIZE)
    assert m.at_measure_size(small) is small


def test_measure_all_turns_a_failing_record_into_an_error_row(tmp_path: Path) -> None:
    class BrokenOcr(FakeTools):
        def ocr(self, image: Path) -> list[m.Fragment]:
            raise OSError("cannot identify image file")

    records = [
        _rec(case="legible_plate", output="images/plate.png"),
        _rec(output="images/knife.png", ok=False, error="OOM"),
        _rec(output="images/knife.png"),  # the resumed job's last row wins
        _rec(output="images/failed.png", ok=False, error="OOM"),
    ]
    rows = list(m.measure_all(records, tmp_path, BrokenOcr()))
    assert rows[0] == {"output": "images/plate.png", "error": "OSError: cannot identify image file"}
    assert rows[1]["output"] == "images/knife.png" and "owl" in rows[1]
    assert len(rows) == 2  # failed renders are not measured
