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

    def gray_std(self, image: Path) -> float:
        return 50.0  # a real render's contrast


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


def _write_clip_with_audio(path: Path, frames: int) -> None:
    """A tiny mp4 like LTX-2.5's and MiniMax-H3's: video plus an AAC track, the audio
    stream first. Frame i is a flat gray of level 8 * i."""
    av = pytest.importorskip("av")
    np = pytest.importorskip("numpy")
    with av.open(str(path), "w") as out:
        audio = out.add_stream("aac", rate=48000, layout="stereo")
        video = out.add_stream("mpeg4", rate=24)
        video.width, video.height, video.pix_fmt = 64, 48, "yuv420p"
        for i in range(frames):
            pixels = np.full((48, 64, 3), 8 * i, dtype=np.uint8)
            out.mux(video.encode(av.VideoFrame.from_ndarray(pixels, format="rgb24")))
        for i in range(frames * 2):  # 2 x 1024 samples per 24 fps frame: longer than the video
            samples = av.AudioFrame.from_ndarray(
                np.zeros((2, 1024), dtype=np.float32), format="fltp", layout="stereo"
            )
            samples.sample_rate, samples.pts = 48000, i * 1024
            out.mux(audio.encode(samples))
        out.mux(video.encode())
        out.mux(audio.encode())


def test_clip_frames_reads_the_video_stream_of_a_clip_with_audio(tmp_path: Path) -> None:
    clip = tmp_path / "clip.mp4"
    _write_clip_with_audio(clip, frames=30)
    frames = m.clip_frames(clip)
    assert len(frames) == 8 and {f.size for f in frames} == {(64, 48)}
    # every third frame (30 // 8), in order: gray levels 0, 24, 48, ... within codec error
    levels = [f.convert("L").getpixel((32, 24)) for f in frames]
    assert levels == pytest.approx([24 * k for k in range(8)], abs=6)


def test_clip_frames_keeps_every_frame_of_a_short_clip(tmp_path: Path) -> None:
    clip = tmp_path / "short.mp4"
    _write_clip_with_audio(clip, frames=5)
    assert len(m.clip_frames(clip)) == 5


def test_measure_all_turns_a_failing_record_into_an_error_row(tmp_path: Path) -> None:
    class BrokenOcr(FakeTools):
        def ocr(self, image: Path) -> list[m.Fragment]:
            if image.name == "plate.png":
                raise OSError("cannot identify image file")
            return []

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


# --- Task 11: Ideogram 4 paints "Image blocked by safety filter" for prompts it refuses ---

CARD = "Image blocked by safety filter"  # the text of every card in /export/synthbench/p1
LINE = (420.0, 360.0, 1500.0, 400.0)


def _frags(*texts: str) -> list[m.Fragment]:
    """One fragment per text, left to right on one line."""
    return [(text, (100.0 * i, 360.0, 100.0 * i + 90.0, 400.0)) for i, text in enumerate(texts)]


@pytest.mark.parametrize(
    "fragments",
    [
        [(CARD, LINE)],
        _frags("Image blocked", "by safety filter"),  # read in pieces
        _frags("IMAGE BLOCKED BY SAFETY FILTER."),
        _frags("Imageblocked", "bysafety", "filter"),  # spaces lost
        _frags("Image blocked by stacte filter"),  # the model garbled a word, as it does
        _frags("Image blocked by sacelt filter"),
        _frags("Image blocked by saficy filke!"),  # both garbled: the card's opening remains
        [("16", (100.0, 100.0, 140.0, 130.0)), (CARD, LINE)],  # scene text beside it
    ],
)
def test_the_refusal_card_text_is_a_refusal(fragments: list[m.Fragment]) -> None:
    assert m.is_refusal_text(fragments) is True


@pytest.mark.parametrize(
    "fragments",
    [
        [],
        [PLATE],
        [STATE_ABOVE, PLATE],
        _frags("safety glass"),
        _frags("blocked driveway"),
        _frags("Blocked", "driveway"),
        _frags("air filter"),
        _frags("Baslumby - 217 2127"),  # a house sign Ideogram painted in a real render
    ],
)
def test_scene_text_is_not_a_refusal(fragments: list[m.Fragment]) -> None:
    assert m.is_refusal_text(fragments) is False


def test_the_card_threshold_sits_between_the_real_cards_and_the_real_renders() -> None:
    # Calibrated on the 312 P1 images at MEASURE_SIZE: Ideogram's 25 uniform cards measure
    # 9.54-12.01, every render of the other five models 23.31 or more.
    assert 12.01 < m.CARD_GRAY_STD_MAX < 23.31
    assert m.looks_like_card(9.54) and m.looks_like_card(12.01)
    assert not m.looks_like_card(23.31) and not m.looks_like_card(m.CARD_GRAY_STD_MAX)


def test_grayscale_std_is_measured_at_the_measure_size() -> None:
    assert m.grayscale_std(Image.new("RGB", (1920, 1088), (110, 110, 110))) == 0.0
    halves = Image.new("RGB", (1920, 1088), (0, 0, 0))
    halves.paste((255, 255, 255), (960, 0, 1920, 1088))
    assert m.grayscale_std(halves) == pytest.approx(127.5, abs=1.0)
    # a gray card with a line of light text (its ink is ~1% of the area) is card-like;
    # a busy scene is not
    card = Image.new("RGB", (1920, 1088), (110, 110, 110))
    card.paste((230, 230, 230), (420, 534, 1500, 546))
    assert m.looks_like_card(m.grayscale_std(card))
    stripes = Image.new("RGB", (1920, 1088), (40, 40, 40))
    for x in range(0, 1920, 64):
        stripes.paste((200, 200, 200), (x, 0, x + 32, 1088))
    assert not m.looks_like_card(m.grayscale_std(stripes))


class CountingTools(FakeTools):
    """FakeTools that read `text` from every image and count the OCR calls."""

    def __init__(self, fragments: list[m.Fragment], std: float = 50.0) -> None:
        self.fragments, self.std, self.ocr_calls = fragments, std, 0

    def ocr(self, image: Path) -> list[m.Fragment]:
        self.ocr_calls += 1
        return self.fragments

    def gray_std(self, image: Path) -> float:
        return self.std


@pytest.mark.parametrize("case", ["knife", "pried_window", "identity", "identity_reference"])
def test_every_image_is_checked_for_the_refusal_card(tmp_path: Path, case: str) -> None:
    tools = CountingTools([(CARD, LINE)], std=10.0)
    out = m.measure_record(_rec(case=case), tmp_path, tools)
    assert (out["refused"], out["card_like"]) == (True, True)
    assert out["ocr_fragments"] == [CARD]  # what the refusal was read from
    assert tools.ocr_calls == 1


def test_a_render_is_not_refused(tmp_path: Path) -> None:
    out = m.measure_record(_rec(), tmp_path, CountingTools([("16", LINE)]))
    assert (out["refused"], out["card_like"]) == (False, False)
    assert "a knife" in out["owl"]  # the other measures run as before


def test_card_like_is_a_diagnostic_beside_the_text(tmp_path: Path) -> None:
    # A card whose text OCR missed stays unrefused; a refusal painted over a scene is refused.
    card_unread = m.measure_record(_rec(), tmp_path, CountingTools([], std=10.0))
    assert (card_unread["refused"], card_unread["card_like"]) == (False, True)
    over_scene = m.measure_record(_rec(), tmp_path, CountingTools([(CARD, LINE)], std=40.0))
    assert (over_scene["refused"], over_scene["card_like"]) == (True, False)


def test_the_plate_case_reads_ocr_once_for_both_the_plate_and_the_refusal(tmp_path: Path) -> None:
    tools = CountingTools([STATE_ABOVE, PLATE])
    out = m.measure_record(_rec(case="legible_plate"), tmp_path, tools)
    assert tools.ocr_calls == 1
    assert out["refused"] is False and out["plate_exact"] is True
    assert out["ocr_fragments"] == ["CALIFORNIA", "8KXR-417"]
    card = m.measure_record(_rec(case="legible_plate"), tmp_path, CountingTools([(CARD, LINE)]))
    assert card["refused"] is True and card["plate_exact"] is False  # a refusal reads no plate


def test_clips_are_never_refused_and_never_read(tmp_path: Path) -> None:
    tools = CountingTools([(CARD, LINE)], std=10.0)
    rec = _rec(kind="i2v", case="identity_walk", output="clips/c.mp4")
    out = m.measure_record(rec, tmp_path, tools)
    assert out["refused"] is False and "card_like" not in out
    assert tools.ocr_calls == 0
