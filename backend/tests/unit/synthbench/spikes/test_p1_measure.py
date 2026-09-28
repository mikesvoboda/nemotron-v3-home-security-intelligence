"""P1 measurement helpers and per-record dispatch (fake tools; no GPU)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from synthbench.spikes.p1_bakeoff import measure as m


def test_normalize_plate() -> None:
    assert m.normalize_plate(" 8kxr-417 ") == "8KXR-417"
    assert m.normalize_plate("8KXR-417") == "8KXR-417"


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

    def ocr(self, image: Path) -> str:
        return "8KXR-417"

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
