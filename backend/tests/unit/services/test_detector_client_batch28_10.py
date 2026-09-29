r"""S2 batch-28 lane L8 - ``detector_client`` group dc12 kill battery (30 keys).

Source: ``backend/services/detector_client.py``, md5 ``294c938abe9e37cd0f979f9357982753``.
Manifest: ``/tmp/wp-pw/detector_client/manifest.json`` group
``dc12-detect-bbox-clamp-geometry`` (30 KILLABLE keys; keys file
``manifest_groups/dc12-detect-bbox-clamp-geometry.keys``, content identical to
``group_11.keys``).  Splice report ``splice-dc12-detect-bbox-clamp-geometry.json``:
30 clean / 0 twin / **0 bad** - every key has exactly ONE text-matching candidate, so no
occurrence twin can hide a sibling and nothing needs a hand-splice probe.

What the group owns
===================
``DetectorClient.detect_objects`` bbox geometry (def L993, last statement L1443):

* L1226 ``if response_image_width is not None and response_image_height is not None:`` -
  the clamp route needs BOTH dimensions; with either one missing the shipped code falls to
  the ``elif`` guard instead (m278);
* L1228-L1243 the "completely outside the image" test - four disjuncts
  ``bbox_x >= W or bbox_y >= H or bbox_x + bbox_width <= 0 or bbox_y + bbox_height <= 0``,
  then the shipped WARNING at L1234 and ``continue``;
* L1244-L1253 the clamp: ``x1 = max(0, min(x, W))``, ``y1 = max(0, min(y, H))``,
  ``x2 = max(0, min(x + w, W))``, ``y2 = max(0, min(y + h, H))`` and the STORED box
  ``(x1, y1, x2 - x1, y2 - y1)``;
* L1256 ``if bbox_width < 1 or bbox_height < 1:`` - ONE degenerate dimension kills the box,
  logged at L1257 as "bbox too small after clamping";
* L1265 ``if original_bbox != (bbox_x, bbox_y, bbox_width, bbox_height):`` - the clamp
  NOTICE at L1266, whose message prints ``original=(o0, o1, o2, o3), clamped=(x, y, w, h),
  image=(WxH), class=C``;
* L1272 ``elif bbox_width <= 0 or bbox_height <= 0:`` - the no-dimensions guard (L1274);
* L1296 ``if is_video and video_metadata:`` - video metadata vs the NEM-3903 image-dimension
  propagation into ``detection.video_width`` / ``video_height``.

Every leg asserts the STORED ``Detection`` row (what ``session.add`` received) plus the
ordered ``(levelname, statement lineno)`` fingerprint of the records it owns, so a mutant
that flips a comparison is caught by the row's geometry AND by the warning that does or does
not accompany it.

Discipline
----------
* production never bends: the shipped ``detect_objects`` runs on a REAL ``DetectorClient``
  (the construction idiom of the shipped ``test_detector_client.py`` suite); the clamp, the
  guards and the record-building code are production code.  Patched collaborators are the
  transport (``_circuit_breaker.call``, autospec'd client), the filesystem/PIL doubles, the
  thread offloads, ``get_settings``, ``get_inference_semaphore``, the metrics reporter and
  the baseline service - every one of them ``autospec=True`` or ``new=`` (WP4.2 ratchet).
  There is no import-time global spy and no logger/handler mutation: only ``caplog``'s own
  handler sees the records.
* ``caplog``'s handler is process-wide and production has lazily-logged sites outside this
  file's ownership, so every leg asserts on the statement lines it owns
  (``mine_where``/``sent`` with its own frozenset).
* no clock is patched: ``time.monotonic``/``time.perf_counter``/``time.time``/``datetime``
  are untouched and every time-derived field is only type-checked.
"""

import ast
import asyncio
import logging
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

import backend.services.detector_client as M
from backend.services.detector_client import MIN_DETECTION_IMAGE_SIZE, DetectorClient

pytestmark = pytest.mark.unit

# --- world-aware shipped-lineno re-anchor (abort-family seventh member) ----------
# The shipped lineno pins in this file hold in the pristine world and in the raw-
# copy replay world, but the bank runs the INSTRUMENTED tree under mutants/,
# where every mutated function is duplicated (backend/services/detector_client.py
# ships 1,443 lines against ~380k instrumented), so every shipped call ALSO fires
# from its per-mutant copies at shifted linenos.  Map every physical lineno of the
# loaded module back onto its pristine statement by matching the full shipped call
# block text; a copy whose block is mutated no longer matches, so its records
# normalize raw and fall OUTSIDE the pin sets -- exactly the red a log-surface
# mutation must produce.  Same strength in the pristine world (identity map).
_PRISTINE = Path(M.__file__)
_parts = _PRISTINE.parts
if "mutants" in _parts:
    _i = len(_parts) - 1 - _parts[::-1].index("mutants")
    _PRISTINE = Path(*_parts[:_i], *_parts[_i + 1 :])


def _logger_call_blocks(text: str) -> dict[int, tuple[str, ...]]:
    """Every shipped ``logger.<level>(...)`` statement: head lineno -> stripped block."""
    tree = ast.parse(text)
    lines = [ln.strip() for ln in text.splitlines()]
    out: dict[int, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "logger"
        ):
            out[node.lineno] = tuple(lines[node.lineno - 1 : node.end_lineno])
    assert len(set(out.values())) == len(out), (
        "two shipped logger calls share block text; the re-anchor map needs "
        "distinct blocks — disambiguate by extending the matched sequence"
    )
    return out


_SHIPPED_BLOCKS = _logger_call_blocks(_PRISTINE.read_text())
_live_src = Path(M.__file__).read_text()  # nosemgrep: path-traversal-open
_live_lines = [ln.strip() for ln in _live_src.splitlines()]
_by_head: dict[str, list[tuple[int, tuple[str, ...]]]] = {}
for _pl, _blk in _SHIPPED_BLOCKS.items():
    _by_head.setdefault(_blk[0], []).append((_pl, _blk))
_LIVE_TO_PRISTINE: dict[int, int] = {}
for _idx, _line in enumerate(_live_lines):
    for _pl, _blk in _by_head.get(_line, ()):
        if tuple(_live_lines[_idx : _idx + len(_blk)]) == _blk:
            assert _LIVE_TO_PRISTINE.setdefault(_idx + 1, _pl) == _pl, (
                f"physical line {_idx + 1} of {M.__file__} holds two shipped blocks"
            )
            break


def _anchor(rec: logging.LogRecord) -> int:
    """The record's shipped (pristine) statement line, in every world."""
    return _LIVE_TO_PRISTINE.get(rec.lineno, rec.lineno)


# The clamp route's own log statement lines (values read straight off the source).
_OUTSIDE = 1234  # "Skipping detection with bbox completely outside image: ..."
_TOO_SMALL = 1257  # "Skipping detection with bbox too small after clamping: ..."
_CLAMPED = 1266  # "Clamped invalid bbox coordinates: ..."
_NO_DIMS = 1274  # "Skipping detection with non-positive bbox dimensions: ..."
_CREATED = 1319  # "Created detection: ..."
_PROC_ERROR = 1328  # "Error processing detection data" - the item-level except arm
_OWNED = frozenset({_OUTSIDE, _TOO_SMALL, _CLAMPED, _NO_DIMS, _CREATED, _PROC_ERROR})

# LogRecord's own attributes plus everything backend.core.logging's ContextFilter injects:
# what is left is the call's own ``extra=`` payload.
_NOISE = frozenset(
    set(logging.LogRecord("n", 0, "p", 0, "m", None, None).__dict__)
    | {
        "asctime",
        "message",
        "request_id",
        "correlation_id",
        "trace_id",
        "span_id",
        "connection_id",
        "task_id",
        "job_id",
        "hostname",
        "container_id",
        "app_version",
        "environment",
    }
)

_IMAGE_PATH = "/export/yard/driveway/frame-0007.jpg"
_CAMERA_ID = "cam-9"
_BYTES = b"image-bytes-here"
# The pinned response dimensions every geometry leg runs against (L1213-L1214 read them).
_W = 100
_H = 50
# The shipped "class=person" label the three clamp messages interpolate.
_CLASS = "person"


# --------------------------------------------------------------------------- observation
def win(caplog):
    """Open a capture window on the shipped module logger (set_level + clear)."""
    caplog.set_level(logging.DEBUG, logger=M.logger.name)
    caplog.clear()


def mine_where(caplog, linenos):
    """This module's captured records restricted to the leg's own shipped call sites."""
    return [r for r in caplog.records if r.name == M.logger.name and _anchor(r) in linenos]


def sent(caplog, linenos):
    """``(levelname, caller lineno)`` of every owned record, IN EMISSION ORDER.

    ``Logger.findCaller`` skips this module's own frames, so the lineno IS the call site.
    """
    return [(r.levelname, _anchor(r)) for r in mine_where(caplog, linenos)]


def surface(caplog, linenos):
    """Every owned record as ``LEVEL lineno | msg | sorted(extras)``."""
    return sorted(
        f"{r.levelname} {_anchor(r)} | {r.msg} | {sorted(fields(r))}"
        for r in mine_where(caplog, linenos)
    )


def fields(rec):
    """The record's own ``extra=`` fields (LogRecord + ContextFilter noise removed)."""
    return {k: v for k, v in rec.__dict__.items() if k not in _NOISE}


def shipped_fields(rec, keys):
    """The named subset of the record's own ``extra=`` fields."""
    got = fields(rec)
    assert set(keys) <= set(got), (sorted(got), keys)
    return {k: got[k] for k in keys}


def one_at(caplog, linenos, level, lineno):
    """The single owned record at (level, lineno)."""
    hits = [r for r in mine_where(caplog, linenos) if (r.levelname, _anchor(r)) == (level, lineno)]
    assert len(hits) == 1, surface(caplog, linenos)
    return hits[0]


# --------------------------------------------------------------------------- doubles
class _DecodedImage:
    """The PIL context manager ``Image.open`` returns; ``load()`` is the shipped
    decompression call, so a no-op stand-in means "this image is intact"."""

    def load(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


async def _to_thread_inline(fn, *args, **kwargs):
    """Runs the offloaded callable on the current loop (``new=`` form, WP4.2 ratchet)."""
    return fn(*args, **kwargs)


class fs(ExitStack):
    """Pins the filesystem the route reads - ``exists`` (L1046), ``stat().st_size`` (L942)
    and ``read_bytes`` (L1084) - plus PIL's open of the validation leg, and runs the two
    ``asyncio.to_thread`` offloads inline, so no leg touches a real file."""

    def __init__(self, *, exists=True, read_bytes=_BYTES, size=MIN_DETECTION_IMAGE_SIZE + 1):
        super().__init__()
        stat = MagicMock()
        stat.st_size = size
        self.enter_context(patch.object(M.Path, "exists", autospec=True, return_value=exists))
        self.enter_context(patch.object(M.Path, "stat", autospec=True, return_value=stat))
        self.enter_context(
            patch.object(M.Path, "read_bytes", autospec=True, return_value=read_bytes)
        )
        self.enter_context(
            patch.object(M.Image, "open", autospec=True, return_value=_DecodedImage())
        )
        self.enter_context(patch.object(M.asyncio, "to_thread", new=_to_thread_inline))


@pytest.fixture(autouse=True)
def baseline_service():
    """The shipped suite's autouse mock of ``get_baseline_service`` (reached at L1351
    whenever a detection is stored)."""
    service = MagicMock()
    service.update_baseline = AsyncMock()
    with patch("backend.services.detector_client.get_baseline_service", autospec=True) as factory:
        factory.return_value = service
        yield service


@pytest.fixture(autouse=True)
def inference_semaphore():
    """The shared inference semaphore the route consumes at L1115, pinned so no leg depends
    on ambient settings or on another test's semaphore."""
    with patch.object(
        M, "get_inference_semaphore", autospec=True, return_value=asyncio.Semaphore(4)
    ):
        yield


@pytest.fixture
def settings():
    """``get_settings`` as the shipped suite patches it, pinned to the values this route
    reads (real floats so a REAL ``DetectorClient`` can be built)."""
    st = MagicMock()
    st.ai_gateway_url = None
    st.use_ai_gateway = False
    st.yolo26_url = "http://detector.invalid:8000"
    st.yolo26_api_key = None
    st.yolo26_read_timeout = 60.0
    st.ai_connect_timeout = 5.0
    st.ai_health_timeout = 5.0
    st.detector_max_retries = 3
    st.ai_max_concurrent_inferences = 4
    st.detection_confidence_threshold = 0.5
    st.detection_class_thresholds = {}
    st.ai_warmup_enabled = False
    st.ai_cold_start_threshold_seconds = 60.0
    with patch("backend.services.detector_client.get_settings", autospec=True) as factory:
        factory.return_value = st
        yield factory


@pytest.fixture
def metrics():
    """Spy on the shipped metrics reporter (imported by name at L76-L83)."""
    with patch.object(M, "record_pipeline_error", autospec=True) as spy:
        yield spy


@pytest.fixture
def client(settings):
    """A REAL ``DetectorClient(max_retries=1)`` - the shipped ``__init__`` runs."""
    instance = DetectorClient(max_retries=1)
    assert instance._detector_type == "yolo26"
    yield instance


@pytest.fixture
def stub_call(client):
    """Short-circuits the transport: ``_circuit_breaker.call`` returns whatever body the leg
    asks for (``run`` below swaps it in).  ``autospec=True`` on the bound attribute (WP4.2
    ratchet), so the shipped L1068 ``allow_call()`` and the L1129 kwargs still execute as
    production code - the spy records them."""

    async def _call(_fn, **kwargs):
        return {"detections": []}

    with patch.object(client._circuit_breaker, "call", autospec=True, side_effect=_call) as spy:
        yield spy


def session_double(*, camera=None):
    """A DB session double: ``get`` answers with ``camera``, ``add``/``commit``/``flush``
    are spies."""
    ses = AsyncMock()
    ses.get = AsyncMock(return_value=camera)
    ses.add = MagicMock()
    ses.commit = AsyncMock()
    ses.flush = AsyncMock()
    return ses


def body(*, bbox, width=_W, height=_H):
    """A detector body carrying exactly ONE shipped-shaped list-format bbox."""
    payload = {
        "detections": [{"class": _CLASS, "confidence": 0.9, "bbox": list(bbox)}],
        "image_width": width,
        "image_height": height,
    }
    if width is None:
        del payload["image_width"]
    if height is None:
        del payload["image_height"]
    return payload


def stored(ses):
    """The ``Detection`` rows handed to ``session.add``."""
    return [c.args[0] for c in ses.add.call_args_list]


def geo(row):
    """The stored bbox quadruple of a ``Detection`` row."""
    return (row.bbox_x, row.bbox_y, row.bbox_width, row.bbox_height)


async def run(client, stub_call, ses, body_value, **over):
    """Drives the shipped ``detect_objects`` with the transport answering ``body_value``."""
    stub_call.side_effect = None
    stub_call.return_value = body_value
    return await client.detect_objects(_IMAGE_PATH, _CAMERA_ID, ses, **over)


_OUTSIDE_MSG = (
    "Skipping detection with bbox completely outside image: "
    "bbox=({bbox}), image=({w}x{h}), class={cls}"
)
_SMALL_MSG = (
    "Skipping detection with bbox too small after clamping: "
    "original=({orig}), clamped=({cl}), image=({w}x{h}), class={cls}"
)
_CLAMP_MSG = (
    "Clamped invalid bbox coordinates: "
    "original=({o0}, {o1}, {o2}, {o3}), clamped=({c0}, {c1}, {c2}, {c3}), "
    "image=({w}x{h}), class={cls}"
)
_NO_DIM_MSG = "Skipping detection with non-positive bbox dimensions: bbox=({bbox}), class={cls}"


def _bbox_str(bbox):
    return ", ".join(str(v) for v in bbox)


# --------------------------------------------------------------------------- tests
# --------------------------------------------------------------------------- tests
# (A) the "completely outside" test: L1228-L1243 + the L1234 WARNING  (m281-m291)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bbox", "edge"),
    [
        ((100, 0, 10, 10), "x == width"),
        ((0, 50, 10, 10), "y == height"),
        ((-20, 0, 20, 10), "x + width == 0"),
        ((0, -30, 10, 30), "y + height == 0"),
        ((200, 0, 10, 10), "x > width"),
    ],
)
async def test_a_box_touching_an_outside_edge_is_dropped(
    caplog, client, stub_call, metrics, bbox, edge
):
    """Every disjunct of L1229-L1232 fires on its OWN edge: each of the four boundary cases
    plus a plainly-off-image box is dropped with the shipped L1234 WARNING and nothing is
    stored (m284/m285 stop treating an exactly-touching box as outside, m287/m290 stop
    treating a sum of exactly zero as outside, m288/m291 widen the sum test to ``<= 1``)."""
    ses = session_double()
    win(caplog)
    with fs():
        assert await run(client, stub_call, ses, body(bbox=bbox)) == []

    assert sent(caplog, _OWNED) == [("WARNING", _OUTSIDE)], surface(caplog, _OWNED)
    warning = one_at(caplog, _OWNED, "WARNING", _OUTSIDE)
    assert warning.msg == _OUTSIDE_MSG.format(bbox=_bbox_str(bbox), w=_W, h=_H, cls=_CLASS)
    assert fields(warning) == {}
    ses.add.assert_not_called()
    # a mutant that raises inside the item loop would report through the except arm instead
    assert metrics.call_args_list == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bbox", "lineno"),
    [
        ((100, 0, 5, 5), _OUTSIDE),
        ((0, 50, 5, 5), _OUTSIDE),
        ((-5, 10, 5, 5), _OUTSIDE),
        ((10, -5, 5, 5), _OUTSIDE),
    ],
)
async def test_a_single_true_disjunct_alone_still_drops_the_box(
    caplog, client, stub_call, metrics, bbox, lineno
):
    """ONE satisfied disjunct is enough: each box below satisfies exactly one of the four
    conditions, so the three ``Or->And`` mutants (m281/m282/m283, which require two or more)
    store it instead - and that box also stops being outside, so the mutant's log surface is
    the L1266 clamp NOTICE, never this L1234 WARNING."""
    ses = session_double()
    win(caplog)
    with fs():
        await run(client, stub_call, ses, body(bbox=bbox))

    assert sent(caplog, _OWNED) == [("WARNING", lineno)], surface(caplog, _OWNED)
    ses.add.assert_not_called()


@pytest.mark.asyncio
async def test_the_x_axis_outside_edges_are_distinguished(caplog, client, stub_call, metrics):
    """``(-20, 0, 20, 10)`` (sum EXACTLY 0) is dropped while ``(-19, 0, 20, 10)`` (sum 1) is
    stored clamped to width 1: that pair is what separates the shipped ``<= 0`` from m287's
    ``< 0`` AND from m288's ``<= 1``, which disagree on opposite sides."""
    ses = session_double()
    win(caplog)
    with fs():
        assert await run(client, stub_call, ses, body(bbox=(-20, 0, 20, 10))) == []
    assert sent(caplog, _OWNED) == [("WARNING", _OUTSIDE)], surface(caplog, _OWNED)
    assert one_at(caplog, _OWNED, "WARNING", _OUTSIDE).msg == _OUTSIDE_MSG.format(
        bbox=_bbox_str((-20, 0, 20, 10)), w=_W, h=_H, cls=_CLASS
    )
    ses.add.assert_not_called()

    ses = session_double()
    win(caplog)
    with fs():
        rows = await run(client, stub_call, ses, body(bbox=(-19, 0, 20, 10)))
    assert [geo(r) for r in stored(ses)] == [(0, 0, 1, 10)]
    assert len(rows) == 1
    assert sent(caplog, _OWNED) == [("WARNING", _CLAMPED), ("DEBUG", _CREATED)], surface(
        caplog, _OWNED
    )
    assert one_at(caplog, _OWNED, "WARNING", _CLAMPED).msg == _CLAMP_MSG.format(
        o0=-19, o1=0, o2=20, o3=10, c0=0, c1=0, c2=1, c3=10, w=_W, h=_H, cls=_CLASS
    )


@pytest.mark.asyncio
async def test_the_y_axis_outside_edges_are_distinguished(caplog, client, stub_call, metrics):
    """The mirror pair on the vertical axis: ``(0, -30, 10, 30)`` (sum EXACTLY 0) is dropped,
    ``(0, -29, 10, 30)`` (sum 1) is stored with height 1 (m290/m291)."""
    ses = session_double()
    win(caplog)
    with fs():
        assert await run(client, stub_call, ses, body(bbox=(0, -30, 10, 30))) == []
    assert sent(caplog, _OWNED) == [("WARNING", _OUTSIDE)], surface(caplog, _OWNED)
    assert one_at(caplog, _OWNED, "WARNING", _OUTSIDE).msg == _OUTSIDE_MSG.format(
        bbox=_bbox_str((0, -30, 10, 30)), w=_W, h=_H, cls=_CLASS
    )
    ses.add.assert_not_called()

    ses = session_double()
    win(caplog)
    with fs():
        assert await run(client, stub_call, ses, body(bbox=(0, -29, 10, 30))) != []
    assert [geo(r) for r in stored(ses)] == [(0, 0, 10, 1)]
    assert sent(caplog, _OWNED) == [("WARNING", _CLAMPED), ("DEBUG", _CREATED)], surface(
        caplog, _OWNED
    )
    assert one_at(caplog, _OWNED, "WARNING", _CLAMPED).msg == _CLAMP_MSG.format(
        o0=0, o1=-29, o2=10, o3=30, c0=0, c1=0, c2=10, c3=1, w=_W, h=_H, cls=_CLASS
    )


# --------------------------------------------------------------------------- (B) the clamp
# --------------------------------------------------------------------------- (B) the clamp: L1244-L1253 + the L1266 NOTICE
# --------------------------------------------------------------------------- (m298/m308/m318/m329/m350-m354)


@pytest.mark.asyncio
async def test_a_box_wider_than_the_image_is_clamped_and_stored(caplog, client, stub_call, metrics):
    """(18, 2, 120, 90) against a 100x50 image: L1244-L1247 clamp the far edges to
    ``(100, 50)``, so the STORED row is ``(18, 2, 82, 48)`` - each of the four ``max(0, ...)``
    calls sits on its own line (m298/m308/m318/m329 turn one of them into ``max(1, ...)``)."""
    ses = session_double()
    win(caplog)
    with fs():
        rows = await run(client, stub_call, ses, body(bbox=(18, 2, 120, 90)))

    assert len(rows) == 1
    assert [geo(r) for r in stored(ses)] == [(18, 2, 82, 48)]
    assert sent(caplog, _OWNED) == [("WARNING", _CLAMPED), ("DEBUG", _CREATED)], surface(
        caplog, _OWNED
    )
    assert one_at(caplog, _OWNED, "WARNING", _CLAMPED).msg == _CLAMP_MSG.format(
        o0=18, o1=2, o2=120, o3=90, c0=18, c1=2, c2=82, c3=48, w=_W, h=_H, cls=_CLASS
    )
    assert metrics.call_args_list == []


@pytest.mark.asyncio
async def test_a_box_off_the_negative_origin_is_clamped_to_zero(caplog, client, stub_call, metrics):
    """(-5, -5, 60, 60): the STORED origin is ``(0, 0)`` - not ``(1, 1)`` - because the
    ``max(0, ...)`` floors of L1244/L1245 are what produce it, and the span is the clamped
    far edge minus that origin, ``(55, 50)``.  m298/m308 shift the stored origin to 1 (and
    shrink the span by 1), m318/m329 raise the far-edge floor to 1, which the two
    fractional-dimension legs below pin."""
    ses = session_double()
    win(caplog)
    with fs():
        await run(client, stub_call, ses, body(bbox=(-5, -5, 60, 60)))

    assert [geo(r) for r in stored(ses)] == [(0, 0, 55, 50)]
    assert sent(caplog, _OWNED) == [("WARNING", _CLAMPED), ("DEBUG", _CREATED)], surface(
        caplog, _OWNED
    )
    assert one_at(caplog, _OWNED, "WARNING", _CLAMPED).msg == _CLAMP_MSG.format(
        o0=-5, o1=-5, o2=60, o3=60, c0=0, c1=0, c2=55, c3=50, w=_W, h=_H, cls=_CLASS
    )


@pytest.mark.asyncio
async def test_an_in_range_box_is_stored_untouched_and_unlogged(caplog, client, stub_call, metrics):
    """(10, 10, 5, 5) needs no clamping: L1265's inequality is false, so there is NO clamp
    NOTICE at all and the row keeps its original quadruple (m350 flips that inequality, which
    both drops this row and logs the NOTICE for every clamped box in the legs above)."""
    ses = session_double()
    win(caplog)
    with fs():
        await run(client, stub_call, ses, body(bbox=(10, 10, 5, 5)))

    assert [geo(r) for r in stored(ses)] == [(10, 10, 5, 5)]
    assert sent(caplog, _OWNED) == [("DEBUG", _CREATED)], surface(caplog, _OWNED)
    assert metrics.call_args_list == []


@pytest.mark.asyncio
async def test_the_clamped_notice_prints_the_original_in_shipped_order(
    caplog, client, stub_call, metrics
):
    """The NOTICE interpolates ``original_bbox[0..3]`` in order, so a single re-indexed slot
    (m352/m353/m354) is a different string; the whole f-string argument is one call argument,
    so m351's ``None`` cannot even be logged."""
    ses = session_double()
    win(caplog)
    with fs():
        await run(client, stub_call, ses, body(bbox=(-2, -3, 40, 100)))

    assert [geo(r) for r in stored(ses)] == [(0, 0, 38, 50)]
    warning = one_at(caplog, _OWNED, "WARNING", _CLAMPED)
    assert warning.msg == _CLAMP_MSG.format(
        o0=-2, o1=-3, o2=40, o3=100, c0=0, c1=0, c2=38, c3=50, w=_W, h=_H, cls=_CLASS
    )
    # the three single-slot re-index mutants (m352/m353/m354) each print a DIFFERENT first
    # two/three slots while leaving the stored row identical - only this string separates them
    assert "original=(-3, -3, 40, 100)" not in warning.msg
    assert "original=(-2, 40, 40, 100)" not in warning.msg
    assert "original=(-2, -3, 100, 100)" not in warning.msg


# --------------------------------------------------------------------------- (C) degenerate
# --------------------------------------------------------------------------- (C) degenerate after clamping: L1256 + L1257
# --------------------------------------------------------------------------- (m345-m349)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bbox", "clamped"),
    [
        ((10, 10, 0, 10), (10, 10, 0, 10)),
        ((10, 10, 10, 0), (10, 10, 10, 0)),
    ],
)
async def test_a_box_degenerate_after_clamping_is_dropped(
    caplog, client, stub_call, metrics, bbox, clamped
):
    """A ZERO-WIDTH box (its right edge at x=10) and a ZERO-HEIGHT box are each dropped by
    L1256 with the shipped L1257 message naming the original and the clamped quadruple.  Each
    case has ONE degenerate dimension and ONE healthy one, which is exactly what m345
    (``bbox_width < 1 and bbox_height < 1``) gets wrong - it stores both of these rows."""
    ses = session_double()
    win(caplog)
    with fs():
        assert await run(client, stub_call, ses, body(bbox=bbox)) == []

    assert sent(caplog, _OWNED) == [("WARNING", _TOO_SMALL)], surface(caplog, _OWNED)
    assert one_at(caplog, _OWNED, "WARNING", _TOO_SMALL).msg == _SMALL_MSG.format(
        orig=_bbox_str(bbox), cl=_bbox_str(clamped), w=_W, h=_H, cls=_CLASS
    )
    ses.add.assert_not_called()
    assert metrics.call_args_list == []


@pytest.mark.asyncio
async def test_a_one_pixel_span_survives_the_degenerate_guard(caplog, client, stub_call, metrics):
    """The shipped floor is ``< 1``: a clamped width of 1 (``-5, 5, 6, 10``) and a clamped
    height of 1 (``5, -5, 10, 6``) are BOTH stored, which kills m346/m347 (``<= 1`` / ``< 2``
    on the width test) and m348/m349 (the same widening on the height test)."""
    ses = session_double()
    win(caplog)
    with fs():
        await run(client, stub_call, ses, body(bbox=(-5, 5, 6, 10)))
    assert [geo(r) for r in stored(ses)] == [(0, 5, 1, 10)]
    assert sent(caplog, _OWNED) == [("WARNING", _CLAMPED), ("DEBUG", _CREATED)], surface(
        caplog, _OWNED
    )
    assert one_at(caplog, _OWNED, "WARNING", _CLAMPED).msg == _CLAMP_MSG.format(
        o0=-5, o1=5, o2=6, o3=10, c0=0, c1=5, c2=1, c3=10, w=_W, h=_H, cls=_CLASS
    )

    ses = session_double()
    win(caplog)
    with fs():
        await run(client, stub_call, ses, body(bbox=(5, -5, 10, 6)))
    assert [geo(r) for r in stored(ses)] == [(5, 0, 10, 1)]
    assert one_at(caplog, _OWNED, "WARNING", _CLAMPED).msg == _CLAMP_MSG.format(
        o0=5, o1=-5, o2=10, o3=6, c0=5, c1=0, c2=10, c3=1, w=_W, h=_H, cls=_CLASS
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("dims", [(0.5, _H), (_W, 0.5)])
async def test_a_sub_pixel_far_edge_clamps_to_a_degenerate_span(
    caplog, client, stub_call, metrics, dims
):
    """L1246/L1247 floor the CLAMPED FAR EDGE at 0: L1213-L1214 take ``image_width`` /
    ``image_height`` straight out of the JSON (no ``int()``), so a sub-pixel reported size is
    reachable and pins that floor.  With the far edge at ``0.5`` the shipped span is
    ``int(0.5 - 0) == 0``, so the box dies at L1256/L1257; m318's (width case) / m329's
    (height case) ``max(1, ...)`` puts the far edge at 1 instead, so the box is STORED and the
    log becomes the L1266 clamp NOTICE - a different geometry and a different record."""
    width, height = dims
    bbox = (0, 0, 1, 10) if width < 1 else (0, 0, 10, 1)
    ses = session_double()
    win(caplog)
    with fs():
        assert await run(client, stub_call, ses, body(bbox=bbox, width=width, height=height)) == []

    assert sent(caplog, _OWNED) == [("WARNING", _TOO_SMALL)], surface(caplog, _OWNED)
    clamped = (0, 0, 0, 10) if width < 1 else (0, 0, 10, 0)
    assert one_at(caplog, _OWNED, "WARNING", _TOO_SMALL).msg == _SMALL_MSG.format(
        orig=_bbox_str(bbox), cl=_bbox_str(clamped), w=width, h=height, cls=_CLASS
    )
    ses.add.assert_not_called()
    assert metrics.call_args_list == []


# --------------------------------------------------------------------------- (D) no dimensions
# --------------------------------------------------------------------------- (D) the no-dimension guard: L1272 + L1274
# --------------------------------------------------------------------------- (m356-m360) and m278


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bbox",
    [(10, 10, 5, 0), (10, 10, 0, 5), (10, 10, -3, 5), (10, 10, 5, -3)],
)
async def test_without_dimensions_a_non_positive_span_is_dropped(
    caplog, client, stub_call, metrics, bbox
):
    """With NO ``image_width``/``image_height`` in the response the route skips the clamp
    route entirely and lands on L1272, where ONE non-positive span is enough to drop the box
    with the shipped L1274 message (m356 needs both, m357/m359 only catch negatives,
    m358/m360 also drop the zero-adjacent 1-pixel box pinned below)."""
    ses = session_double()
    win(caplog)
    with fs():
        assert await run(client, stub_call, ses, body(bbox=bbox, width=None, height=None)) == []

    assert sent(caplog, _OWNED) == [("WARNING", _NO_DIMS)], surface(caplog, _OWNED)
    assert one_at(caplog, _OWNED, "WARNING", _NO_DIMS).msg == _NO_DIM_MSG.format(
        bbox=_bbox_str(bbox), cls=_CLASS
    )
    ses.add.assert_not_called()


@pytest.mark.asyncio
async def test_without_dimensions_a_one_pixel_box_survives(caplog, client, stub_call, metrics):
    """(10, 10, 1, 1) is stored with its own dimensions when no image size is reported -
    m358/m360 drop it (``<= 1``) - and neither NEM-3903 field is set, since both
    ``response_image_*`` values are ``None`` (L1301-L1305)."""
    ses = session_double()
    win(caplog)
    with fs():
        await run(client, stub_call, ses, body(bbox=(10, 10, 1, 1), width=None, height=None))

    rows = stored(ses)
    assert len(rows) == 1
    assert (rows[0].bbox_x, rows[0].bbox_y) == (10, 10)
    assert (rows[0].bbox_width, rows[0].bbox_height) == (1, 1)
    assert rows[0].video_width is None
    assert rows[0].video_height is None
    assert sent(caplog, _OWNED) == [("DEBUG", _CREATED)], surface(caplog, _OWNED)


@pytest.mark.asyncio
@pytest.mark.parametrize("which", ["width", "height"])
async def test_a_single_missing_dimension_uses_the_guard_not_the_clamp(
    caplog, client, stub_call, metrics, which
):
    """L1226 needs BOTH dimensions: with one of them absent the route uses the L1272 guard,
    so a zero span is dropped with the L1274 message and NO clamp notice appears (m278's
    ``or`` instead enters the clamp route and dies comparing against ``None``, which lands in
    the L1328 except arm - a different surface AND a ``detection_processing_error`` report)."""
    over = {"width": None} if which == "width" else {"height": None}
    ses = session_double()
    win(caplog)
    with fs():
        assert await run(client, stub_call, ses, body(bbox=(10, 10, 5, 0), **over)) == []

    assert sent(caplog, _OWNED) == [("WARNING", _NO_DIMS)], surface(caplog, _OWNED)
    assert metrics.call_args_list == []


@pytest.mark.asyncio
async def test_a_single_missing_dimension_skips_the_outside_test_too(
    caplog, client, stub_call, metrics
):
    """The other side of L1226 with a missing dimension: an off-image box ``(200, 0, 10, 10)``
    with ``image_height=None`` is NOT outside-tested and NOT clamped - the shipped row keeps
    ``bbox_x == 200`` - while the present dimension still propagates to ``video_width``
    (L1301).  m278 enters the clamp route here and raises comparing ``int`` with ``None``."""
    ses = session_double()
    win(caplog)
    with fs():
        await run(client, stub_call, ses, body(bbox=(200, 0, 10, 10), height=None))

    rows = stored(ses)
    assert len(rows) == 1
    assert rows[0].bbox_x == 200
    assert rows[0].bbox_y == 0
    assert (rows[0].bbox_width, rows[0].bbox_height) == (10, 10)
    assert rows[0].video_width == _W
    assert rows[0].video_height is None
    assert sent(caplog, _OWNED) == [("DEBUG", _CREATED)], surface(caplog, _OWNED)
    assert metrics.call_args_list == []


# --------------------------------------------------------------------------- (E) dimensions
# --------------------------------------------------------------------------- (E) L1296: video metadata vs image dimensions (m387)


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", [None, {"file_type": "video/mp4"}])
async def test_an_image_run_publishes_the_response_dimensions(
    caplog, client, stub_call, metrics, metadata
):
    """The NEM-3903 ``else`` arm of L1296: an IMAGE-mode run (``video_path is None``, so
    ``is_video`` is False) publishes the response dimensions on ``video_width`` /
    ``video_height`` - and it does so even when ``video_metadata`` IS supplied, because L1296
    needs BOTH the path and the metadata (m387's ``or`` takes the metadata arm here and stamps
    ``None`` into both fields plus a ``None`` codec/duration)."""
    ses = session_double()
    over = {} if metadata is None else {"video_metadata": metadata}
    win(caplog)
    with fs():
        await run(client, stub_call, ses, body(bbox=(10, 10, 5, 5)), **over)

    rows = stored(ses)
    assert len(rows) == 1
    assert rows[0].video_width == _W
    assert rows[0].video_height == _H
    assert rows[0].media_type == "image"
    assert rows[0].file_path == _IMAGE_PATH
    assert rows[0].video_codec is None
    assert rows[0].duration is None


@pytest.mark.asyncio
async def test_a_video_run_publishes_the_metadata_dimensions(caplog, client, stub_call, metrics):
    """The metadata arm of L1296: with ``video_path`` AND ``video_metadata`` present the row
    carries the METADATA dimensions (7x9) and codec/duration, NOT the response's 100x50."""
    ses = session_double()
    metadata = {
        "file_type": "video/mp4",
        "video_width": 7,
        "video_height": 9,
        "video_codec": "h264",
        "duration": 12.5,
    }
    win(caplog)
    with fs():
        await run(
            client,
            stub_call,
            ses,
            body(bbox=(10, 10, 5, 5)),
            video_path="/export/videos/clip-1.mp4",
            video_metadata=metadata,
        )

    rows = stored(ses)
    assert len(rows) == 1
    assert rows[0].video_width == 7
    assert rows[0].video_height == 9
    assert rows[0].video_codec == "h264"
    assert rows[0].duration == 12.5
    assert rows[0].media_type == "video"
    # the geometry was still clamped against the RESPONSE dimensions
    assert geo(rows[0]) == (10, 10, 5, 5)


@pytest.mark.asyncio
async def test_the_transport_kwargs_and_row_fields_are_the_shipped_ones(
    caplog, client, stub_call, metrics
):
    """Pins the one stored row's shipped field set and the ``_circuit_breaker.call`` kwargs
    that produced it, so a leg that mutates geometry cannot silently be mutating routing."""
    ses = session_double()
    win(caplog)
    with fs():
        await run(client, stub_call, ses, body(bbox=(10, 10, 5, 5)))

    rows = stored(ses)
    assert len(rows) == 1
    row = rows[0]
    assert (row.camera_id, row.file_path, row.file_type) == (
        _CAMERA_ID,
        _IMAGE_PATH,
        M.get_mime_type_with_default(M.Path(_IMAGE_PATH)),
    )
    assert row.object_type == _CLASS
    assert row.confidence == 0.9
    assert (
        call(
            client._send_detection_request,
            image_data=_BYTES,
            image_name="frame-0007.jpg",
            camera_id=_CAMERA_ID,
            image_path=_IMAGE_PATH,
        )
        in stub_call.call_args_list
    )
