"""Batch 26 part 23 — mutation kill battery for backend/services/enrichment_pipeline.py.

Chunk-23 owns 114 keys across 23 defs: the plate/face/damage legs
(_detect_license_plates, _read_plates, _detect_faces, _detect_vehicle_damage,
_maybe_enhance_low_light), the media-leg helpers (_load_image,
_extract_frame_from_video, _crop_to_bbox, _run_ocr, _get_action_frames), the two
scene-OCR safe wrappers, six thin Phase-1 safe pass-throughs, and the leaf
helpers (_is_fast_alpr_available, _pil_to_bytes, compute_status,
EnrichmentResult.get_weather_risk_modifier, get_enrichment_pipeline).

Rule 1 (pin shipped, never bend): every assert below was written AFTER probing
the pristine shipped function with this exact mock topology (probes/c23/probe*.py),
including the shipped oddities the mutants hide behind — `if x2 < x1` is STRICT
(x2 == x1 is not an inversion, it dies at the clamp check); `_run_ocr`'s guards
are CONJUNCTIVE (a list-valued text_info and a 1-element line are both skipped);
`Image.convert(None)` is a shipped no-op, so the RGB pin needs an L-mode frame;
`Path(obj)` rejects any non-str/non-PathLike object, so the
`isinstance(image, str) else image` branch IS observable through file-like
objects that carry `.suffix`.

SEAM DISCIPLINE (this is what makes the kills real, not harness noise). The
red-check harness rebinds a mutant into a COPY of the module dict taken before
each test runs, so `patch("backend.services.enrichment_pipeline.<global>")` is
INVISIBLE to the mutant — a test that observes only such a patch reports a
failure the shipped code could also produce. Every observation below is
therefore binding-safe, i.e. it survives the rebinding:
  * instance state — self.model_manager / self._frame_buffer / self._scene_ocr_service
    / self._run_yolo_detection / self._load_image (resolved on the instance),
  * ARGS the code under test is handed (the PaddleOCR stub, the images dict),
  * RETURN VALUES and object identity of what comes back,
  * `caplog` — the real logger, captured through the logging hierarchy (works
    under the mutant AND under the repo conftest; verified both),
  * the real counters/callables patched at their OWN source module
    (backend.core.metrics.ENRICHMENT_MODEL_CALLS_TOTAL), which the shipped code
    looks up at call time,
  * names imported INSIDE a function body (numpy, VideoProcessor,
    SceneOCRResult/SceneTextResult/_classify_text_type, get_model_config,
    get_weather_risk_modifier) pinned at their source module or through
    sys.modules — a swap there cannot be hidden by the module-dict copy,
  * the real collaborators, fed deterministic payloads (the real
    vehicle_damage_loader driven by a fake YOLO payload; the real
    zero_dce_loader brightness gate driven by real dark/bright images).

Class-free plain functions; async driven with asyncio.run. No sleeps, no
network, no DB, no ffmpeg (VideoProcessor is always replaced).
"""

from __future__ import annotations

import asyncio
import inspect
import io
import logging
import types
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as REAL_NP
import pytest
from PIL import Image

import backend.services.enrichment_pipeline as M
import backend.services.scene_ocr_service as REPO_SOS
import backend.services.video_processor as REPO_VP

EP_LOGGER = "backend.services.enrichment_pipeline"
IMG = Image.new("RGB", (20, 10), "red")
OCR_IMG = Image.new("RGB", (2, 2), (7, 8, 9))
DARK = Image.new("RGB", (8, 8), (4, 4, 4))
BRIGHT = Image.new("RGB", (8, 8), (240, 240, 240))
BOX = [[0, 0], [1, 0], [1, 1], [0, 1]]


# ------------------------------------------------------------------ plumbing
def run(coro):
    return asyncio.run(coro)


def exc_of(record):
    """The exc_info the call-site actually passed, in a form that separates the 3 shapes.

    `exc_info=True` leaves a 3-tuple on the record, `exc_info=False` leaves False
    and `exc_info=None` leaves None — a truthiness test would collapse the last
    two, so these mutants are pinned on the value itself, not on "is it set".
    """
    info = record.exc_info
    return info[0] if isinstance(info, tuple) else info


def logs(caplog, level):
    """(message, exc_info) for every record THIS module emitted at `level`."""
    caplog.set_level(logging.DEBUG, logger=EP_LOGGER)
    return [
        (r.getMessage(), exc_of(r))
        for r in caplog.records
        if r.name == EP_LOGGER and r.levelno == level
    ]


def watch(caplog):
    """Arm capture before the call under test (records only fill in as they fire)."""
    caplog.set_level(logging.DEBUG, logger=EP_LOGGER)


def pipe():
    return M.EnrichmentPipeline.__new__(M.EnrichmentPipeline)


def mgr(raises=None, payload="PAY"):
    """model_manager stub (instance attribute -> binding-safe): records load(name)."""
    m = MagicMock(name="model_manager")
    m.calls = []

    def load(name):
        m.calls.append(name)
        if raises is not None:
            raise raises
        # A string payload is tagged with the name it was loaded under, so an
        # assert on the object handed downstream also proves the name matched.
        body = f"{payload}:{name}" if isinstance(payload, str) else payload
        return nullcontext(body)

    m.load = load
    return m


def det(det_id, bbox=(1, 2, 6, 7), cls="vehicle"):
    """DetectionInput stand-in with a REAL BoundingBox so the crop leg stays live."""
    d = MagicMock(name="DetectionInput")
    d.id = det_id
    d.class_name = cls
    d.bbox = None if bbox is None else M.BoundingBox(*bbox)
    return d


def png_bytes(n=3, mode="RGB"):
    out = []
    for i in range(n):
        buf = io.BytesIO()
        Image.new(mode, (3, 2), i if mode == "L" else (i, i, i)).save(buf, format="PNG")
        out.append(buf.getvalue())
    return out


class Spy:
    """Awaitable recorder bound to the INSTANCE, so a rebound module cannot hide it."""

    def __init__(self, ret=None, raises=None):
        self.ret = ret
        self.raises = raises
        self.calls = []

    async def __call__(self, *a, **k):
        self.calls.append((a, k))
        if self.raises is not None:
            raise self.raises
        return self.ret


class Ctor:
    """Calls the REAL class but records (args, result).

    The scene-OCR result types are imported INSIDE the function under test, so
    their own module is the only seam; this records the shipped constructor
    ARGUMENTS (what the mutants change) while the shipped object stays genuine.
    """

    def __init__(self, real):
        self.real = real
        self.built = []

    def __call__(self, *a, **k):
        value = self.real(*a, **k)
        self.built.append(((a, k), value))
        return value


class Fn:
    """Wraps a real callable, recording (args, kwargs, result)."""

    def __init__(self, real):
        self.real = real
        self.calls = []

    def __call__(self, *a, **k):
        out = self.real(*a, **k)
        self.calls.append((a, k, out))
        return out


# ============================================================== _load_image
def test_load_image_pil_identity_and_missing_file_returns_none():
    """shipped: a PIL Image passes through by identity; a missing path -> None."""
    p = pipe()
    assert run(M.EnrichmentPipeline._load_image(p, IMG)) is IMG
    assert run(M.EnrichmentPipeline._load_image(p, Path("/nope/missing.jpg"))) is None


def test_load_image_path_failure_logs_the_interpolated_detail(caplog):
    """shipped logs f"Failed to load image: {e}" — a None-arg mutant loses the detail."""
    watch(caplog)
    p = pipe()
    assert run(M.EnrichmentPipeline._load_image(p, Path("/nope/missing.jpg"))) is None
    assert logs(caplog, logging.WARNING) == [
        ("Failed to load image: [Errno 2] No such file or directory: '/nope/missing.jpg'", None)
    ]


def test_load_image_str_path_takes_the_path_branch(caplog):
    """shipped: str -> Path(image) -> open; the null-byte failure proves Path() ran."""
    watch(caplog)
    p = pipe()
    assert run(M.EnrichmentPipeline._load_image(p, "\x00\x01bad")) is None
    assert logs(caplog, logging.WARNING) == [("Failed to load image: embedded null byte", None)]


def test_load_image_non_str_with_suffix_is_NOT_wrapped_in_path():
    """shipped `Path(image) if isinstance(image, str) else image` keeps a non-str object.

    A file-like object carrying `.suffix` opens through Image.open(path).  The
    `... or True` mutant wraps it in Path() instead -> TypeError -> None.
    """

    class TaggedBytes(io.BytesIO):
        suffix = ".png"

    buf = TaggedBytes()
    Image.new("RGB", (3, 2), "white").save(buf, format="PNG")
    buf.seek(0)
    p = pipe()
    out = run(M.EnrichmentPipeline._load_image(p, buf))
    assert out is not None and out.size == (3, 2)


def test_load_image_video_suffix_dispatches_to_the_frame_extractor():
    """shipped: suffix in VIDEO_MIME_TYPES -> await self._extract_frame_from_video(path)."""
    p = pipe()
    got = []

    async def fake(path):
        got.append(path)
        return "FRAME"

    p._extract_frame_from_video = fake
    assert run(M.EnrichmentPipeline._load_image(p, "/media/a.MP4")) == "FRAME"
    assert got == [Path("/media/a.MP4")]


# ================================================================ _crop_to_bbox
def test_crop_to_bbox_normal_crop_uses_int_truncation():
    """shipped: int() truncates toward zero, then the crop is taken."""
    p = pipe()
    out = run(M.EnrichmentPipeline._crop_to_bbox(p, IMG, M.BoundingBox(1.9, 2.9, 6.1, 7.9)))
    assert out is not None and out.size == (5, 5)


def test_crop_to_bbox_swaps_inverted_x_and_logs_it(caplog):
    """shipped `if x2 < x1`: swap plus the strict-inequality warning."""
    watch(caplog)
    p = pipe()
    out = run(M.EnrichmentPipeline._crop_to_bbox(p, IMG, M.BoundingBox(10, 1, 4, 7)))
    assert out is not None and out.size == (6, 6)
    assert logs(caplog, logging.WARNING) == [
        ("Invalid bounding box: x2 (4) < x1 (10). Swapping coordinates.", None)
    ]


def test_crop_to_bbox_equal_x_is_NOT_an_inversion(caplog):
    """shipped: x2 == x1 is not swapped (strict `<`) — it dies at the clamp check.

    The `<=` mutant routes it through the swap branch, emitting an extra warning.
    """
    watch(caplog)
    p = pipe()
    assert run(M.EnrichmentPipeline._crop_to_bbox(p, IMG, M.BoundingBox(5, 1, 5, 7))) is None
    assert logs(caplog, logging.WARNING) == [
        (
            "Bounding box has zero or negative dimensions after clamping: "
            "(5, 1, 5, 7). Skipping crop.",
            None,
        )
    ]


def test_crop_to_bbox_swaps_inverted_y_and_logs_it(caplog):
    watch(caplog)
    p = pipe()
    out = run(M.EnrichmentPipeline._crop_to_bbox(p, IMG, M.BoundingBox(1, 8, 6, 3)))
    assert out is not None and out.size == (5, 5)
    assert logs(caplog, logging.WARNING) == [
        ("Invalid bounding box: y2 (3) < y1 (8). Swapping coordinates.", None)
    ]


def test_crop_to_bbox_equal_y_is_NOT_an_inversion(caplog):
    watch(caplog)
    p = pipe()
    assert run(M.EnrichmentPipeline._crop_to_bbox(p, IMG, M.BoundingBox(1, 5, 6, 5))) is None
    assert logs(caplog, logging.WARNING) == [
        (
            "Bounding box has zero or negative dimensions after clamping: "
            "(1, 5, 6, 5). Skipping crop.",
            None,
        )
    ]


def test_crop_to_bbox_clamps_then_reports_zero_area(caplog):
    """shipped clamp warning interpolates the POST-clamp coordinates."""
    watch(caplog)
    p = pipe()
    assert run(M.EnrichmentPipeline._crop_to_bbox(p, IMG, M.BoundingBox(30, 30, 40, 40))) is None
    assert logs(caplog, logging.WARNING) == [
        (
            "Bounding box has zero or negative dimensions after clamping: "
            "(30, 30, 20, 10). Skipping crop.",
            None,
        )
    ]


def test_crop_to_bbox_swaps_before_clamping(caplog):
    """shipped order is swap FIRST, clamp SECOND: the wide inversion still crops."""
    watch(caplog)
    p = pipe()
    out = run(M.EnrichmentPipeline._crop_to_bbox(p, IMG, M.BoundingBox(15, 1, -4, 7)))
    assert out is not None and out.size == (15, 6)
    assert logs(caplog, logging.WARNING) == [
        ("Invalid bounding box: x2 (-4) < x1 (15). Swapping coordinates.", None)
    ]


def test_crop_to_bbox_load_failure_short_circuits_silently(caplog):
    """shipped: _load_image -> None returns before the try block, no logging."""
    watch(caplog)

    async def none_loader(image):
        return None

    p = pipe()
    p._load_image = none_loader
    assert run(M.EnrichmentPipeline._crop_to_bbox(p, "x", M.BoundingBox(0, 0, 1, 1))) is None
    assert logs(caplog, logging.WARNING) == []


def test_crop_to_bbox_exception_detail_is_interpolated(caplog):
    """shipped logs f"Failed to crop image: {e}" from the int() coercion."""
    watch(caplog)
    p = pipe()
    out = run(M.EnrichmentPipeline._crop_to_bbox(p, IMG, M.BoundingBox("a", 0, 2, 2)))
    assert out is None
    assert logs(caplog, logging.WARNING) == [
        ("Failed to crop image: invalid literal for int() with base 10: 'a'", None)
    ]


# =================================================================== _run_ocr
class StubOCR:
    """PaddleOCR stand-in handed IN as an argument — records the exact call."""

    def __init__(self, result=None, raises=None):
        self.result = result
        self.raises = raises
        self.calls = []

    def ocr(self, *a, **k):
        self.calls.append((a, k))
        if self.raises is not None:
            raise self.raises
        return self.result


def run_ocr(result, raises=None, image=OCR_IMG):
    p = pipe()
    stub = StubOCR(result, raises)
    out = run(M.EnrichmentPipeline._run_ocr(p, stub, image))
    return out, stub


def test_run_ocr_passes_pixel_array_and_cls_flag():
    """shipped: ocr.ocr(np.array(image), cls=True) — one positional, cls True."""
    (text, conf), stub = run_ocr([[[BOX, ("ABC", 0.9)]]])
    assert (text, conf) == ("ABC", 0.9)
    assert len(stub.calls) == 1
    a, k = stub.calls[0]
    assert len(a) == 1 and k == {"cls": True}
    assert a[0] is not None
    assert a[0].shape == (2, 2, 3) and a[0].tolist()[0][0] == [7, 8, 9]


def test_run_ocr_pixel_array_is_built_from_the_image():
    """shipped `img_array = np.array(image)` — pinned by construction at numpy's site.

    `import numpy as np` happens inside the nested closure, so the
    enrichment_pipeline attribute cannot see a swap; sys.modules is the binding
    point (and the module-level `import numpy` of THIS file is unaffected).
    """
    ctor = Fn(REAL_NP.array)

    class Shim:
        array = ctor

    p = pipe()
    stub = StubOCR([[[BOX, ("ABC", 0.9)]]])
    with patch.dict("sys.modules", {"numpy": Shim}):
        out = run(M.EnrichmentPipeline._run_ocr(p, stub, OCR_IMG))
    assert out == ("ABC", 0.9)
    assert ctor.calls != []
    assert ctor.calls[0][0] == (OCR_IMG,)
    assert ctor.calls[0][2].shape == (2, 2, 3)


def test_run_ocr_empty_shapes_return_the_empty_pair():
    """shipped `if not result or not result[0]` -> ("", 0.0) for None / [] / [[]]."""
    for shape in (None, [], [[]]):
        (text, conf), stub = run_ocr(shape)
        assert (text, conf) == ("", 0.0), shape
        assert len(stub.calls) == 1


def test_run_ocr_falsy_result_is_never_indexed(caplog):
    """shipped `not result` short-circuits: result=None must not reach result[0].

    The `and` mutant evaluates `not result[0]` on None -> IndexError, which the
    outer handler turns into a logged "OCR failed: ..." line.
    """
    watch(caplog)
    (text, conf), _stub = run_ocr(None)
    assert (text, conf) == ("", 0.0)
    assert logs(caplog, logging.WARNING) == []


def test_run_ocr_one_element_line_is_skipped_silently(caplog):
    """shipped `if line and len(line) >= 2` skips a 1-element line.

    The `or` mutant enters the body and does line[1] -> IndexError -> a logged
    "OCR failed: ..." line.
    """
    watch(caplog)
    (text, conf), _stub = run_ocr([[[BOX]]])
    assert (text, conf) == ("", 0.0)
    assert logs(caplog, logging.WARNING) == []


def test_run_ocr_list_valued_text_info_is_skipped():
    """shipped `isinstance(text_info, tuple) and len(...) >= 2` rejects a LIST."""
    (text, conf), _stub = run_ocr([[[BOX, ["abc", 0.5]]]])
    assert (text, conf) == ("", 0.0)


def test_run_ocr_one_element_tuple_text_info_is_skipped():
    (text, conf), _stub = run_ocr([[[BOX, ("ABC",)]]])
    assert (text, conf) == ("", 0.0)


def test_run_ocr_multi_region_join_and_average():
    """shipped joins texts with " " and averages the confidences."""
    (text, conf), _stub = run_ocr([[[BOX, ("A", 0.8)], [BOX, ("B", 0.6)]]])
    assert (text, conf) == ("A B", 0.7)


def test_run_ocr_skips_falsy_lines_but_keeps_others():
    (text, conf), _stub = run_ocr([[[], [BOX, ("X", 0.5)]]])
    assert (text, conf) == ("X", 0.5)


def test_run_ocr_failure_detail_is_interpolated(caplog):
    """shipped logs f"OCR failed: {e}" and returns ("", 0.0)."""
    watch(caplog)
    out, _stub = run_ocr(None, raises=RuntimeError("boom"))
    assert out == ("", 0.0)
    assert logs(caplog, logging.WARNING) == [("OCR failed: boom", None)]


# ========================================================= _get_action_frames
def gaf(camera_id, current, num_frames, buffer_ret, have_buffer=True):
    p = pipe()
    if have_buffer:
        buf = MagicMock(name="frame_buffer")
        buf.get_sequence = MagicMock(return_value=buffer_ret)
        p._frame_buffer = buf
    else:
        p._frame_buffer = None
    out = run(M.EnrichmentPipeline._get_action_frames(p, camera_id, current, num_frames))
    seq = p._frame_buffer.get_sequence if have_buffer else None
    return out, seq


def test_get_action_frames_buffer_lookup_args_are_pinned():
    """shipped: get_sequence(camera_id, num_frames) — both positionals, in order."""
    out, seq = gaf("cam1", IMG, 3, png_bytes(3))
    assert seq.call_args_list == [(("cam1", 3), {})]
    assert len(out) == 3


def test_get_action_frames_buffered_debug_message(caplog):
    """shipped two-part f-string join, count and camera included."""
    watch(caplog)
    gaf("cam9", IMG, 2, png_bytes(2))
    assert logs(caplog, logging.DEBUG) == [
        ("Using 2 buffered frames for action recognition (camera: cam9)", None)
    ]


def test_get_action_frames_buffered_frames_are_converted_to_rgb():
    """shipped `raw_img.convert("RGB")`: an L-mode buffered frame comes back RGB."""
    out, _seq = gaf("cam1", IMG, 2, png_bytes(2, mode="L"))
    assert len(out) == 2
    assert [f.mode for f in out] == ["RGB", "RGB"]


def test_get_action_frames_fallback_message_is_the_two_part_join(caplog):
    """shipped: "Using single-frame fallback ... " + f"(camera: {id}, buffer: {..})"."""
    watch(caplog)
    out = gaf("camZ", IMG, 5, None, have_buffer=False)
    assert out[0] == [IMG]
    assert logs(caplog, logging.DEBUG) == [
        (
            "Using single-frame fallback for action recognition (camera: camZ, buffer: False)",
            None,
        )
    ]


def test_get_action_frames_fallback_reports_buffer_present(caplog):
    """shipped `buffer: {self._frame_buffer is not None}` -> True when a buffer exists."""
    watch(caplog)
    gaf("cam1", IMG, 4, png_bytes(3))
    assert logs(caplog, logging.DEBUG) == [
        (
            "Using single-frame fallback for action recognition (camera: cam1, buffer: True)",
            None,
        )
    ]


def test_get_action_frames_short_buffer_still_falls_back(caplog):
    watch(caplog)
    out, seq = gaf("cam1", IMG, 4, png_bytes(3))
    assert out == [IMG]
    assert seq.call_args_list == [(("cam1", 4), {})]
    assert len(logs(caplog, logging.DEBUG)) == 1


def test_get_action_frames_none_sequence_from_buffer_falls_back(caplog):
    watch(caplog)
    out, seq = gaf("cam1", IMG, 3, None)
    assert out == [IMG]
    assert seq.call_args_list == [(("cam1", 3), {})]
    assert logs(caplog, logging.DEBUG) == [
        (
            "Using single-frame fallback for action recognition (camera: cam1, buffer: True)",
            None,
        )
    ]


def test_get_action_frames_camera_none_skips_the_buffer_lookup(caplog):
    watch(caplog)
    out, seq = gaf(None, IMG, 3, png_bytes(3))
    assert out == [IMG]
    assert seq.call_args_list == []
    assert logs(caplog, logging.DEBUG) == [
        (
            "Using single-frame fallback for action recognition (camera: None, buffer: True)",
            None,
        )
    ]


def test_get_action_frames_undecodable_bytes_are_skipped(caplog):
    """shipped: per-frame decode failure logs debug and continues to the fallback."""
    watch(caplog)
    out, seq = gaf("cam1", IMG, 2, [b"junk", b"junk2"])
    assert out == [IMG]
    assert seq.call_args_list == [(("cam1", 2), {})]
    msgs = logs(caplog, logging.DEBUG)
    assert len(msgs) == 3
    assert msgs[0][0].startswith("Failed to decode buffered frame: ")
    assert msgs[1][0].startswith("Failed to decode buffered frame: ")
    assert msgs[2] == (
        "Using single-frame fallback for action recognition (camera: cam1, buffer: True)",
        None,
    )


# ================================================ _extract_frame_from_video
class StubVP:
    """VideoProcessor stand-in installed at its SOURCE module.

    `from backend.services.video_processor import VideoProcessor` executes INSIDE
    the function under test, so the enrichment_pipeline attribute is a non-seam;
    a sys.modules substitution is the binding point for that import.
    """

    ret = None
    exc = None
    last = None

    def __init__(self, output_dir="DEFAULT-DIR", **kw):
        self.output_dir = output_dir
        self.ctor_kw = kw
        if StubVP.exc is not None:
            self.extract_thumbnail = AsyncMock(side_effect=StubVP.exc)
        else:
            self.extract_thumbnail = AsyncMock(return_value=StubVP.ret)
        StubVP.last = self


def efv(ret=None, exc=None, video="/media/clip.mp4"):
    StubVP.ret = ret
    StubVP.exc = exc
    ctors = []

    def factory(*a, **k):
        ctors.append((a, k))
        return StubVP(*a, **k)

    shim = types.ModuleType(REPO_VP.__name__)
    shim.__dict__.update(
        {"VideoProcessor": factory, "VideoProcessingError": REPO_VP.VideoProcessingError}
    )
    p = pipe()
    with patch.dict("sys.modules", {REPO_VP.__name__: shim}):
        out = run(M.EnrichmentPipeline._extract_frame_from_video(p, Path(video)))
    calls = StubVP.last.extract_thumbnail.call_args_list
    return out, ctors, calls


def test_extract_frame_from_video_happy_path_returns_the_frame(tmp_path):
    """shipped: the extracted thumbnail is opened and copied into a PIL Image."""
    jpg = tmp_path / "thumb.jpg"
    buf = io.BytesIO()
    Image.new("RGB", (4, 3), "green").save(buf, format="JPEG")
    jpg.write_bytes(buf.getvalue())
    out, ctors, calls = efv(str(jpg))
    assert out is not None and out.size == (4, 3)
    assert len(ctors) == 1 and len(calls) == 1


def test_extract_frame_from_video_ctor_receives_the_temp_dir():
    """shipped: VideoProcessor(output_dir=temp_dir) — a real temp dir string, not None."""
    _out, ctors, _calls = efv(None)
    a, k = ctors[0]
    assert a == ()
    assert set(k) == {"output_dir"}
    assert isinstance(k["output_dir"], str) and k["output_dir"].startswith("/tmp")


def test_extract_frame_from_video_output_path_is_derived_from_the_temp_dir():
    """shipped: output_path = str(Path(temp_dir)/"<stem>_enrichment_frame.jpg")."""
    _out, ctors, calls = efv(None)
    out_dir = ctors[0][1]["output_dir"]
    assert len(calls) == 1
    assert calls[0].kwargs == {"output_path": str(Path(out_dir) / "clip_enrichment_frame.jpg")}


def test_extract_frame_from_video_passes_str_video_path_positionally():
    """shipped: extract_thumbnail(str(video_path), output_path=...) — both arguments."""
    _out, _ctors, calls = efv(None)
    assert len(calls) == 1
    assert len(calls[0].args) == 1
    assert calls[0].args[0] == "/media/clip.mp4"
    assert set(calls[0].kwargs) == {"output_path"}


def test_extract_frame_from_video_thumbnail_path_is_opened_by_pil(tmp_path):
    """shipped: Image.open(thumbnail_path).copy() opens exactly what the processor returned."""
    jpg = tmp_path / "t.jpg"
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), "blue").save(buf, format="JPEG")
    jpg.write_bytes(buf.getvalue())
    opened = []
    real_open = Image.open

    def spy(fp, *a, **k):
        opened.append(fp)
        return real_open(fp, *a, **k)

    with patch.object(Image, "open", new=spy):
        out, _ctors, _calls = efv(str(jpg))
    assert out is not None and out.size == (2, 2)
    assert opened == [str(jpg)]


def test_extract_frame_from_video_thumbnail_none_warns_with_the_path(caplog):
    watch(caplog)
    out, _ctors, _calls = efv(None)
    assert out is None
    assert logs(caplog, logging.WARNING) == [
        ("Failed to extract frame from video: /media/clip.mp4", None)
    ]


def test_extract_frame_from_video_generic_error_detail(caplog):
    """shipped: bare Exception -> f"Failed to extract frame from video {path}: {e}"."""
    watch(caplog)
    out, _ctors, _calls = efv(None, exc=RuntimeError("boom"))
    assert out is None
    assert logs(caplog, logging.WARNING) == [
        ("Failed to extract frame from video /media/clip.mp4: boom", None)
    ]


def test_extract_frame_from_video_processing_error_has_its_own_message(caplog):
    """shipped: VideoProcessingError is caught by a dedicated handler."""
    watch(caplog)
    out, _ctors, _calls = efv(None, exc=REPO_VP.VideoProcessingError("vpe"))
    assert out is None
    assert logs(caplog, logging.WARNING) == [
        ("Video processing error extracting frame from /media/clip.mp4: vpe", None)
    ]


# ==================================================== _detect_license_plates
def dlp(vehicles, images, raises=None, yolo_ret=None):
    p = pipe()
    p.model_manager = mgr(raises)
    p._run_yolo_detection = AsyncMock(return_value=yolo_ret or [])
    out = run(M.EnrichmentPipeline._detect_license_plates(p, vehicles, images))
    return out, p


def test_detect_license_plates_passes_crop_and_vehicle_id():
    """shipped: _run_yolo_detection(model, cropped, vehicle.id) — three positionals."""
    plate = M.LicensePlateResult(bbox=M.BoundingBox(0, 0, 1, 1), confidence=0.5)
    out, p = dlp([det("v1")], {None: IMG}, yolo_ret=[plate])
    assert out == [plate]
    assert p.model_manager.calls == ["yolo11-license-plate"]
    a, k = p._run_yolo_detection.call_args_list[0]
    assert len(k) == 0 and len(a) == 3
    assert a[0] == "PAY:yolo11-license-plate"
    assert a[1] is not None and a[1].size == (5, 5)
    assert a[2] == "v1"


def test_detect_license_plates_missing_image_skips_detection():
    out, p = dlp([det("v1")], {})
    assert out == [] and p._run_yolo_detection.call_args_list == []


def test_detect_license_plates_no_crop_skips_detection():
    out, p = dlp([det("v1", bbox=(30, 30, 40, 40))], {None: IMG})
    assert out == [] and p._run_yolo_detection.call_args_list == []


def test_detect_license_plates_empty_input_still_loads_the_model():
    out, p = dlp([], {None: IMG})
    assert out == [] and p.model_manager.calls == ["yolo11-license-plate"]


def test_detect_license_plates_other_exceptions_propagate():
    """shipped catches only KeyError/RuntimeError — a ValueError escapes untouched."""
    p = pipe()
    p.model_manager = mgr(ValueError("lethal"))
    with pytest.raises(ValueError):
        run(M.EnrichmentPipeline._detect_license_plates(p, [det("v1")], {None: IMG}))


def test_detect_license_plates_model_missing_warning_is_verbatim(caplog):
    """shipped: KeyError -> logger.warning("yolo11-license-plate model not available")."""
    watch(caplog)
    _out, _p = dlp([det("v1")], {None: IMG}, raises=KeyError("nope"))
    assert logs(caplog, logging.WARNING) == [("yolo11-license-plate model not available", None)]


def test_detect_license_plates_error_renders_the_traceback(caplog):
    """shipped `exc_info=True` puts the traceback in the rendered log stream.

    The exc_info=False/None mutants keep the message identical, so the pin is on
    the rendered record: shipped shows the traceback and the exception line,
    they show neither.  (`exc_info=False` also leaves False on the record where
    shipped leaves a tuple — pinned in the sibling test — and this is the
    stream-level view of the same fact.)
    """
    watch(caplog)
    dlp([det("v1")], {None: IMG}, raises=RuntimeError("bad-plate-boom"))
    assert "License plate detection error" in caplog.text
    assert "Traceback (most recent call last)" in caplog.text
    assert "RuntimeError: bad-plate-boom" in caplog.text


def test_detect_license_plates_error_message_and_exc_info(caplog):
    """shipped: RuntimeError -> logger.error(msg, exc_info=True)."""
    watch(caplog)
    _out, _p = dlp([det("v1")], {None: IMG}, raises=RuntimeError("bad"))
    assert logs(caplog, logging.ERROR) == [("License plate detection error", RuntimeError)]
    assert logs(caplog, logging.WARNING) == []


# ================================================================= _read_plates
def plate(source_id, bbox=(1, 1, 5, 5)):
    return M.LicensePlateResult(bbox=M.BoundingBox(*bbox), source_detection_id=source_id)


def rp(plates, images, raises=None):
    p = pipe()
    p.model_manager = mgr(raises)
    p._run_ocr = AsyncMock(return_value=("TXT", 0.75))
    run(M.EnrichmentPipeline._read_plates(p, plates, images))
    return p


def test_read_plates_empty_list_returns_before_the_model_load():
    """shipped `if not plates: return` — no model load, no OCR."""
    p = rp([], {None: IMG})
    assert p.model_manager.calls == []
    assert p._run_ocr.call_args_list == []


def test_read_plates_loads_paddleocr_by_name_and_writes_back():
    """shipped: load("paddleocr"), OCR over the plate crop, text stored in place."""
    pl = plate(None)
    p = rp([pl], {None: IMG})
    assert (pl.text, pl.ocr_confidence) == ("TXT", 0.75)
    assert p.model_manager.calls == ["paddleocr"]
    a, _k = p._run_ocr.call_args_list[0]
    assert a[0] == "PAY:paddleocr"
    assert a[1].size == (4, 4)


def test_read_plates_uses_the_shared_image_for_an_unknown_source_id():
    """shipped: images.get(plate.source_detection_id) or images.get(None)."""
    pl = plate(99)
    p = rp([pl], {None: IMG})
    assert len(p._run_ocr.call_args_list) == 1
    assert (pl.text, pl.ocr_confidence) == ("TXT", 0.75)


def test_read_plates_missing_image_skips_ocr():
    pl = plate(7)
    p = rp([pl], {})
    assert p._run_ocr.call_args_list == []
    assert (pl.text, pl.ocr_confidence) == ("", 0.0)


def test_read_plates_model_missing_warning_is_verbatim(caplog):
    watch(caplog)
    pl = plate(None)
    p = rp([pl], {None: IMG}, raises=KeyError("k"))
    assert (pl.text, pl.ocr_confidence) == ("", 0.0)
    assert p.model_manager.calls == ["paddleocr"]
    assert p._run_ocr.call_args_list == []
    assert logs(caplog, logging.WARNING) == [("paddleocr model not available", None)]
    assert logs(caplog, logging.ERROR) == []


def test_read_plates_error_message_and_exc_info(caplog):
    watch(caplog)
    _p = rp([plate(None)], {None: IMG}, raises=RuntimeError("r"))
    assert logs(caplog, logging.WARNING) == []
    assert logs(caplog, logging.ERROR) == [("OCR error", RuntimeError)]


# ================================================================= _detect_faces
def df(persons, images, raises=None, face_ret=None):
    p = pipe()
    p.model_manager = mgr(raises)
    p._run_face_detection = AsyncMock(return_value=face_ret or [])
    out = run(M.EnrichmentPipeline._detect_faces(p, persons, images))
    return out, p


def test_detect_faces_passes_crop_and_person_id():
    """shipped: _run_face_detection(model, cropped, person.id)."""
    face = M.FaceResult(bbox=M.BoundingBox(0, 0, 1, 1), confidence=0.4)
    out, p = df([det("p1", cls="person")], {None: IMG}, face_ret=[face])
    assert out == [face]
    assert p.model_manager.calls == ["yolo11-face"]
    a, k = p._run_face_detection.call_args_list[0]
    assert len(k) == 0 and len(a) == 3
    assert a[0] == "PAY:yolo11-face"
    assert a[1] is not None and a[1].size == (5, 5)
    assert a[2] == "p1"


def test_detect_faces_no_crop_skips_detection():
    _out, p = df([det("p1", bbox=(30, 30, 40, 40))], {None: IMG})
    assert p._run_face_detection.call_args_list == []


def test_detect_faces_model_missing_warning_is_verbatim(caplog):
    watch(caplog)
    _out, _p = df([det("p1")], {None: IMG}, raises=KeyError("x"))
    assert logs(caplog, logging.WARNING) == [("yolo11-face model not available", None)]
    assert logs(caplog, logging.ERROR) == []


def test_detect_faces_error_message_and_exc_info(caplog):
    watch(caplog)
    _out, _p = df([det("p1")], {None: IMG}, raises=RuntimeError("f"))
    assert logs(caplog, logging.WARNING) == []
    assert logs(caplog, logging.ERROR) == [("Face detection error", RuntimeError)]


# ======================================================= _detect_vehicle_damage
class FakeDamageModel:
    """YOLO payload for the REAL vehicle_damage_loader (deterministic, no torch weights).

    Loader-side observation matters here: `detect_vehicle_damage` is a module
    global of enrichment_pipeline (invisible to the mutant binding), so the only
    honest way to watch the metric call and the damage summary is to let the
    real loader run over this payload.
    """

    def __init__(self, class_names=()):
        self.class_names = list(class_names)

    def predict(self, *args, **kwargs):
        n = len(self.class_names)
        boxes = MagicMock(name="boxes")
        boxes.__len__ = lambda self, n=n: n
        boxes.xyxy = [np4(i) for i in range(n)]
        boxes.conf = [one(0.9) for _ in range(n)]
        boxes.cls = [one(i) for i in range(n)]
        result = MagicMock(name="result")
        result.boxes = boxes if n else None
        result.masks = None
        result.names = {i: name for i, name in enumerate(self.class_names)}
        return [result]


def np4(seed):
    class Cpu:
        def numpy(self):
            return REAL_NP.array([1.0 + seed, 2.0, 5.0, 6.0])

    return types.SimpleNamespace(cpu=lambda: Cpu())


def one(value):
    class Cpu:
        def numpy(self):
            return value

    return types.SimpleNamespace(cpu=lambda: Cpu())


def dvd(vehicles, raises=None, payload=None):
    from backend.core.metrics import ENRICHMENT_MODEL_CALLS_TOTAL

    p = pipe()
    p.model_manager = mgr(raises, payload=payload if payload is not None else FakeDamageModel())
    with patch("backend.core.metrics.ENRICHMENT_MODEL_CALLS_TOTAL", autospec=True) as counter:
        out = run(M.EnrichmentPipeline._detect_vehicle_damage(p, vehicles, IMG))
    return out, p, counter


def test_detect_vehicle_damage_records_the_model_call_verbatim():
    """shipped: record_enrichment_model_call("vehicle-damage-detection") per vehicle.

    Observed on the real Prometheus counter object at its source module, which
    the shipped helper looks up at call time — a label-string swap shows up.
    """
    out, p, counter = dvd([det("v1")])
    assert list(out) == ["v1"]
    assert p.model_manager.calls == ["vehicle-damage-detection"]
    assert counter.labels.call_args_list == [((), {"model": "vehicle-damage-detection"})]


def test_detect_vehicle_damage_records_even_without_damage():
    """shipped records the metric BEFORE the has_damage log branch."""
    out, _p, counter = dvd([det("v1")])
    assert list(out) == ["v1"]
    assert counter.labels.call_count == 1


def test_detect_vehicle_damage_empty_input_skips_the_model_load():
    out, p, counter = dvd([])
    assert out == {} and p.model_manager.calls == []
    assert counter.labels.call_args_list == []


def test_detect_vehicle_damage_no_crop_skips_the_record():
    out, _p, counter = dvd([det("v1", bbox=(30, 30, 40, 40))])
    assert out == {}
    assert counter.labels.call_args_list == []


def test_detect_vehicle_damage_summary_info_is_interpolated(caplog):
    """shipped logs the 4-part f-string damage summary when damage is present."""
    watch(caplog)
    out, _p, _counter = dvd([det("v7")], payload=FakeDamageModel(["glass shatter"]))
    assert list(out) == ["v7"]
    assert logs(caplog, logging.INFO) == [
        (
            "Vehicle v7 damage detected: types={'glass_shatter'}, count=1, high_security=True",
            None,
        )
    ]


def test_detect_vehicle_damage_model_missing_warning_is_verbatim(caplog):
    """shipped: KeyError -> the exact MODEL_ZOO availability warning."""
    watch(caplog)
    out, _p, counter = dvd([det("v1")], raises=KeyError("k"))
    assert out == {}
    assert counter.labels.call_args_list == []
    assert logs(caplog, logging.WARNING) == [
        ("vehicle-damage-detection model not available in MODEL_ZOO", None)
    ]
    assert logs(caplog, logging.ERROR) == []


def test_detect_vehicle_damage_error_message_and_exc_info(caplog):
    watch(caplog)
    out, _p, _counter = dvd([det("v1")], raises=ValueError("v"))
    assert out == {}
    assert logs(caplog, logging.WARNING) == []
    assert logs(caplog, logging.ERROR) == [("Vehicle damage detection error", ValueError)]


# ==================================================== _maybe_enhance_low_light
def mell(image, raises=None):
    """Real brightness gate (zero_dce_loader) + recording manager (instance attr)."""
    p = pipe()
    p.model_manager = mgr(raises)
    out = run(M.EnrichmentPipeline._maybe_enhance_low_light(p, image))
    return out, p


def test_maybe_enhance_low_light_bright_image_returned_unchanged():
    """shipped: a bright image short-circuits — same object, model never loaded."""
    out, p = mell(BRIGHT, raises=KeyError("unused"))
    assert out is BRIGHT
    assert p.model_manager.calls == []


def test_maybe_enhance_low_light_dark_image_loads_the_named_model():
    """shipped: a dark image reaches load("zero-dce-plus-plus")."""
    out, p = mell(DARK, raises=KeyError("k"))
    assert out is DARK  # the load failure is swallowed and the original returns
    assert p.model_manager.calls == ["zero-dce-plus-plus"]


def test_maybe_enhance_low_light_skip_log_is_verbatim(caplog):
    """shipped: any Exception -> that exact debug line, original image returned."""
    watch(caplog)
    out, _p = mell(DARK, raises=KeyError("k"))
    assert out is DARK
    assert logs(caplog, logging.DEBUG) == [
        ("Zero-DCE++ enhancement skipped (model unavailable or error)", None)
    ]


def test_maybe_enhance_low_light_bright_path_never_logs_the_skip(caplog):
    """shipped: the bright path returns INSIDE the try, so the skip line never fires."""
    watch(caplog)
    mell(BRIGHT, raises=KeyError("k"))
    assert logs(caplog, logging.DEBUG) == []


# ==================================================== _safe_run_scene_ocr_frame
def scene_item(text, conf, bbox=(0, 0, 1, 1)):
    o = MagicMock(name="OcrText")
    o.text = text
    o.confidence = conf
    o.bbox = bbox
    return o


def sframe(items, raises=None, have_service=True):
    p = pipe()
    if have_service:
        svc = MagicMock(name="scene_ocr")
        svc._run_full_frame_ocr = (
            AsyncMock(return_value=items) if raises is None else AsyncMock(side_effect=raises)
        )
        p._scene_ocr_service = svc
    else:
        p._scene_ocr_service = None
    ocr_result = Ctor(REPO_SOS.SceneOCRResult)
    text_result = Ctor(REPO_SOS.SceneTextResult)
    classify = Fn(REPO_SOS._classify_text_type)
    with (
        patch.object(REPO_SOS, "SceneOCRResult", ocr_result),
        patch.object(REPO_SOS, "SceneTextResult", text_result),
        patch.object(REPO_SOS, "_classify_text_type", classify),
    ):
        out = run(M.EnrichmentPipeline._safe_run_scene_ocr_frame(p, IMG))
    svc_calls = p._scene_ocr_service._run_full_frame_ocr.call_args_list if have_service else []
    return out, svc_calls, ocr_result, text_result, classify


def test_safe_run_scene_ocr_frame_no_service_returns_none():
    out, calls, ocr_result, _t, _c = sframe([], have_service=False)
    assert out is None
    assert calls == [] and ocr_result.built == []


def test_safe_run_scene_ocr_frame_maps_items_and_returns_the_result():
    """shipped: _run_full_frame_ocr(image) -> SceneTextResult list -> OCRResult(scene_texts=..)."""
    out, calls, ocr_result, text_result, classify = sframe([scene_item("MAIN ST 5", 0.85)])
    assert calls == [((IMG,), {})]
    assert len(text_result.built) == 1
    kwargs = text_result.built[0][0][1]
    assert kwargs == {
        "value": "MAIN ST 5",
        "confidence": 0.85,
        "bbox": (0, 0, 1, 1),
        "text_type": REPO_SOS._classify_text_type("MAIN ST 5"),
        "is_uncertain": False,
    }
    assert [c[2] for c in classify.calls] == [kwargs["text_type"]]
    assert ocr_result.built[0][1] is out
    assert ocr_result.built[0][0] == ((), {"scene_texts": [text_result.built[0][1]]})
    assert ocr_result.built[0][0][1]["scene_texts"] is not None


def test_safe_run_scene_ocr_frame_uncertain_band_bounds():
    """shipped is_uncertain = 0.50 <= conf < 0.80 (0.5 -> True, 0.8 -> False)."""
    _o, _c, _ocr, text_result, _cl = sframe([scene_item("A", 0.5), scene_item("B", 0.8)])
    assert [b[0][1]["is_uncertain"] for b in text_result.built] == [True, False]


def test_safe_run_scene_ocr_frame_empty_result_yields_an_empty_list():
    """shipped: `scene_texts = []` over an empty OCR result -> [] (NOT None)."""
    out, _calls, ocr_result, text_result, _cl = sframe([])
    assert text_result.built == []
    assert ocr_result.built[0][0] == ((), {"scene_texts": []})
    assert out is ocr_result.built[0][1]


def test_safe_run_scene_ocr_frame_failure_detail(caplog):
    watch(caplog)
    out, _calls, ocr_result, _t, _cl = sframe([], raises=RuntimeError("se"))
    assert out is None and ocr_result.built == []
    assert logs(caplog, logging.WARNING) == [("Full-frame scene OCR failed: se", None)]


# ==================================================== _safe_run_scene_ocr_crops
def scrops(image_arg, detections, frame_result, raises=None, have_service=True):
    p = pipe()
    if have_service:
        svc = MagicMock(name="scene_ocr")
        svc.process_frame = (
            AsyncMock(return_value="CROPPED") if raises is None else AsyncMock(side_effect=raises)
        )
        p._scene_ocr_service = svc
    else:
        p._scene_ocr_service = None
    out = run(
        M.EnrichmentPipeline._safe_run_scene_ocr_crops(p, image_arg, detections, frame_result)
    )
    calls = p._scene_ocr_service.process_frame.call_args_list if have_service else []
    return out, calls


def test_safe_run_scene_ocr_crops_no_service_returns_the_frame_result():
    out, calls = scrops(IMG, [], "FRAME", have_service=False)
    assert out == "FRAME"
    assert calls == []


def test_safe_run_scene_ocr_crops_forwards_image_and_detections():
    """shipped: process_frame(image, detections), result returned verbatim."""
    dets = [det("a")]
    out, calls = scrops(IMG, dets, "FRAME")
    assert out == "CROPPED"
    assert calls == [((IMG, dets), {})]


def test_safe_run_scene_ocr_crops_empty_detections_still_call_the_service():
    out, calls = scrops(IMG, [], "FRAME")
    assert out == "CROPPED"
    assert calls == [((IMG, []), {})]


def test_safe_run_scene_ocr_crops_failure_falls_back_to_frame_result(caplog):
    """shipped: exception -> warning interpolating {e}, then return frame_ocr_result."""
    watch(caplog)
    out, calls = scrops(IMG, [det("a")], "FRAME", raises=RuntimeError("ce"))
    assert out == "FRAME"
    assert len(calls) == 1
    assert logs(caplog, logging.WARNING) == [("Scene OCR crop processing failed: ce", None)]


# ========================================================= safe pass-throughs
def passthru(safe_name, internal_name, args, ret="R", raises=None):
    """Call <safe> with <internal> replaced ON THE CLASS by an awaitable recorder.

    The wrapper resolves `self._internal(...)` through the instance/class dict at
    call time, so the recorder is observed even when the wrapper itself is a
    rebound mutant.
    """
    p = pipe()
    spy = Spy(ret, raises)
    original = getattr(M.EnrichmentPipeline, internal_name)
    setattr(M.EnrichmentPipeline, internal_name, spy)
    try:
        out = run(getattr(M.EnrichmentPipeline, safe_name)(p, *args))
        return out, spy.calls
    except Exception:
        return "RAISED", spy.calls
    finally:
        setattr(M.EnrichmentPipeline, internal_name, original)


def test_safe_assess_image_quality_forwards_both_positional_args():
    """shipped: _assess_image_quality(image, camera_id) — both, in order, unmutated."""
    out, calls = passthru("_safe_assess_image_quality", "_assess_image_quality", (IMG, "cam9"))
    assert out == "R"
    assert calls == [((IMG, "cam9"), {})]


def test_safe_assess_image_quality_forwards_a_none_camera_id():
    """camera_id=None is a legal shipped value: it must arrive, not be dropped."""
    out, calls = passthru("_safe_assess_image_quality", "_assess_image_quality", (IMG, None))
    assert out == "R"
    assert calls == [((IMG, None), {})]


def test_safe_analyze_depth_forwards_detections_and_image():
    dets = [det("a")]
    out, calls = passthru("_safe_analyze_depth", "_analyze_depth", (dets, IMG))
    assert out == "R"
    assert calls == [((dets, IMG), {})]


def test_safe_detect_license_plates_forwards_vehicles_and_images():
    vehicles, images = [det("v1")], {None: IMG}
    out, calls = passthru(
        "_safe_detect_license_plates", "_detect_license_plates", (vehicles, images)
    )
    assert out == "R"
    assert calls == [((vehicles, images), {})]


def test_safe_estimate_poses_forwards_persons_and_image():
    persons = [det("p1", cls="person")]
    out, calls = passthru("_safe_estimate_poses", "_estimate_poses", (persons, IMG))
    assert out == "R"
    assert calls == [((persons, IMG), {})]


def test_safe_classify_weather_forwards_the_image():
    out, calls = passthru("_safe_classify_weather", "_classify_weather", (IMG,))
    assert out == "R"
    assert calls == [((IMG,), {})]


def test_safe_detect_violence_forwards_the_image():
    out, calls = passthru("_safe_detect_violence", "_detect_violence", (IMG,))
    assert out == "R"
    assert calls == [((IMG,), {})]


def test_safe_wrappers_do_not_swallow_errors():
    """shipped wrappers are pure pass-throughs: exceptions propagate untouched."""
    out, _calls = passthru(
        "_safe_classify_weather", "_classify_weather", (IMG,), raises=RuntimeError("w")
    )
    assert out == "RAISED"


# =================================================================== leaf defs
def test_is_fast_alpr_available_requires_config_and_enabled():
    """shipped `config is not None and config.enabled`.

    `get_model_config` is imported INSIDE the function, so the model_zoo module
    attribute is the binding point (the copy the mutant runs against cannot
    shadow it).  The enabled=False case is the discriminator: shipped False,
    `or`-mutant True.
    """
    p = pipe()
    with patch("backend.services.model_zoo.get_model_config", autospec=True) as gmc:
        gmc.return_value = None
        assert M.EnrichmentPipeline._is_fast_alpr_available(p) is False
        on = MagicMock()
        on.enabled = True
        gmc.return_value = on
        assert M.EnrichmentPipeline._is_fast_alpr_available(p) is True
        off = MagicMock()
        off.enabled = False
        gmc.return_value = off
        assert M.EnrichmentPipeline._is_fast_alpr_available(p) is False
    assert [c.args for c in gmc.call_args_list] == [("fast-alpr",)] * 3


def test_is_fast_alpr_available_swallows_lookup_errors():
    """shipped: any Exception from the config lookup -> False."""
    p = pipe()
    with patch("backend.services.model_zoo.get_model_config", autospec=True) as gmc:
        gmc.side_effect = RuntimeError("boom")
        assert M.EnrichmentPipeline._is_fast_alpr_available(p) is False


def test_pil_to_bytes_default_format_produces_png():
    """shipped: default fmt="PNG" yields the PNG signature; "JPEG" the JPEG SOI."""
    p = pipe()
    assert M.EnrichmentPipeline._pil_to_bytes(p, IMG)[:8] == b"\x89PNG\r\n\x1a\n"
    assert M.EnrichmentPipeline._pil_to_bytes(p, IMG, "JPEG")[:3] == b"\xff\xd8\xff"


def test_pil_to_bytes_declares_the_uppercase_png_default():
    """The shipped default is the literal "PNG" on the def line.

    Pillow's save-handler lookup is case-insensitive, so a lower-cased default is
    byte-identical through `save()` (pinned by
    test_pil_to_bytes_default_format_produces_png); the declared default is the
    only observable difference, so it is pinned directly.
    """
    sig = inspect.signature(M.EnrichmentPipeline._pil_to_bytes)
    assert sig.parameters["fmt"].default == "PNG"


def compute_status(successful, failed):
    """Call the shipped classmethod in a form that also works on a rebound variant.

    `compute_status` is a @classmethod; a mutant rebound onto the class arrives
    as a PLAIN function (the descriptor is lost), so `Cls.compute_status(a, b)`
    would raise TypeError for every variant of this def and fake a verdict.
    getattr_static sees both shapes, so the asserts measure the match table.
    """
    attr = inspect.getattr_static(M.EnrichmentTrackingResult, "compute_status")
    fn = attr.__func__ if isinstance(attr, classmethod) else fn_plain(attr)
    return fn(M.EnrichmentTrackingResult, successful, failed)


def fn_plain(attr):
    return attr


def test_compute_status_matrix_over_the_four_reachable_shapes():
    """shipped match table for (bool(successful), bool(failed))."""
    S = M.EnrichmentStatus
    assert compute_status([], []) is S.SKIPPED
    assert compute_status(["a"], []) is S.FULL
    assert compute_status([], ["b"]) is S.FAILED
    assert compute_status(["a"], ["b"]) is S.PARTIAL


def test_compute_status_keys_on_emptiness_not_type():
    """shipped keys are bool() of the containers: empty ones behave like []."""
    S = M.EnrichmentStatus
    assert compute_status("", "") is S.SKIPPED
    assert compute_status({"a"}, set()) is S.FULL


def test_get_weather_risk_modifier_uses_the_nighttime_flag():
    """shipped: get_weather_risk_modifier(self.weather_classification, self._determine_nighttime()).

    Pinned on the REAL helper's return value (clear + night -> +0.25).  Passing
    None for the night flag makes the `condition == "clear" and is_night` branch
    fall away, so the modifier drops to 0.0 — a value-level difference with no
    mocking involved.
    """
    from backend.services.weather_loader import WeatherResult

    er = M.EnrichmentResult()
    er.is_nighttime = True
    er.weather_classification = WeatherResult(
        condition="clear", simple_condition="clear", confidence=0.9, all_scores={}
    )
    assert er.get_weather_risk_modifier() == 0.25


def test_get_weather_risk_modifier_rainy_value():
    """shipped: rainy -> -0.15 regardless of the night flag (guard on the clear arm)."""
    from backend.services.weather_loader import WeatherResult

    er = M.EnrichmentResult()
    er.is_nighttime = False
    er.weather_classification = WeatherResult(
        condition="Rain", simple_condition="rainy", confidence=0.9, all_scores={}
    )
    assert er.get_weather_risk_modifier() == -0.15


# ===================================================== module-level factory
def _cfg(flag):
    """A REAL Settings copy with only the enrichment-service flag flipped.

    A MagicMock settings would be fine for the flag itself, but the shipped
    constructor reads a dozen other settings attributes during __init__ and
    compares one with an int, so a genuine object keeps the focus on the one
    attribute the factory actually forwards.
    """
    import backend.core.config as CFG

    return CFG.get_settings().model_copy(update={"use_enrichment_service": flag})


def _harness_sync(**names):
    """Align the red-check harness's module-dict copy with the shipped module.

    The swap plugin binds a variant into a COPY of the module dict taken BEFORE
    the test body runs, so a `global _enrichment_pipeline` read/write inside a
    module-level mutant cannot see assignments made through `M.<name>` here.
    Pushing the value into that copy keeps the cache branch deterministic (it is
    a no-op in a plain baseline run, where no plugin is loaded).
    """
    try:
        import ep_plugin
    except Exception:  # plain run: nothing to align
        return
    ep_plugin._MOD.update(names)


def factory_with(flag, redis_client=None):
    """Run the shipped factory with the two function-local imports pinned at source."""
    import backend.core.config as CFG
    import backend.core.redis as REDIS

    saved = M._enrichment_pipeline
    M._enrichment_pipeline = None
    _harness_sync(_enrichment_pipeline=None)
    try:
        with (
            patch.object(CFG, "get_settings", autospec=True, return_value=_cfg(flag)),
            patch.object(REDIS, "get_redis_client_sync", autospec=True, return_value=redis_client),
        ):
            return M.get_enrichment_pipeline()
    finally:
        M._enrichment_pipeline = saved
        _harness_sync(_enrichment_pipeline=saved)


def test_get_enrichment_pipeline_forwards_the_true_flag():
    """shipped: EnrichmentPipeline(..., use_enrichment_service=settings.use_enrichment_service).

    The pin is the ATTRIBUTE of the pipeline the factory actually built (the real
    class stores the argument verbatim), so no class substitution is needed and
    the observation survives a rebound mutant.  Settings says True; dropping the
    kwarg yields the constructor default False and `= None` yields None.
    """
    got = factory_with(True)
    assert got.use_enrichment_service is True


def test_get_enrichment_pipeline_forwards_the_false_flag():
    """The True-biased mutants (drop-kwarg / None) also agree with a False setting, so
    the second direction is measured too: shipped forwards False, not None."""
    got = factory_with(False)
    assert got.use_enrichment_service is False


def test_get_enrichment_pipeline_builds_a_real_pipeline():
    """shipped: the global holds an EnrichmentPipeline built with the Redis client."""
    sentinel = object()
    got = factory_with(True, redis_client=sentinel)
    assert isinstance(got, M.EnrichmentPipeline)
    assert got.redis_client is sentinel


def test_get_enrichment_pipeline_reuses_the_cached_singleton():
    """shipped: a non-None global is returned without consulting settings."""
    import backend.core.config as CFG

    saved = M._enrichment_pipeline
    sentinel = object()
    M._enrichment_pipeline = sentinel
    _harness_sync(_enrichment_pipeline=sentinel)
    try:
        with patch.object(CFG, "get_settings", autospec=True) as gs:
            assert M.get_enrichment_pipeline() is sentinel
        assert gs.call_args_list == []
    finally:
        M._enrichment_pipeline = saved
        _harness_sync(_enrichment_pipeline=saved)
