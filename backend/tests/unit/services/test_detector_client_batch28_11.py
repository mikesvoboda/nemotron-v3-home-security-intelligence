r"""S2 batch-28 lane L9 - ``detector_client`` group dc11 kill battery (47 keys).

Source: ``backend/services/detector_client.py``, md5 ``294c938abe9e37cd0f979f9357982753``.
Manifest: ``/tmp/wp-pw/detector_client/manifest.json`` group
``dc11-detect-response-parse-detection-build`` (47 KILLABLE keys; keys file
``manifest_groups/dc11-detect-response-parse-detection-build.keys``, content identical to
``group_10.keys``).  Splice report ``splice-dc11-detect-response-parse-detection-build.json``:
34 clean / 13 twin / **0 bad** - nothing in this group needs a hand-splice probe.

What the group owns
===================
``DetectorClient.detect_objects`` (def L993, last statement L1442), the RESPONSE-PARSE
half of it:

* L1129-L1135 - the forward of the four keyword arguments into ``_send_detection_request``;
* L1153-L1159 - the missing-``detections`` guard: ONE WARNING (raw text plus a
  ``{"response": str(result)[:500]}`` extra) then ``record_pipeline_error("malformed_response")``
  and ``return []``;
* L1163 - ``detected_at = datetime.now(UTC)`` (a tz-aware stamp, stored on every detection);
* L1172-L1182 - the media selector: the shipped gate is ``video_path is not None AND
  video_metadata is not None``, the video leg takes ``video_metadata.get("file_type",
  "video/mp4")``, the image leg takes the file's MIME type, ``media_type = "image"`` and
  ``is_video = False``;
* L1186-L1201 - per-detection defaults ``confidence`` -> ``0.0`` and ``class`` -> ``"unknown"``,
  the class-threshold lookup ``self._class_thresholds.get(object_class,
  self._confidence_threshold)`` and the low-confidence ``continue``;
* L1203-L1221 - the bbox reader: ``detection_data.get("bbox", {})`` then the dict arm
  (``Invalid bbox dict format: {bbox}`` + ``continue``) and the scalar arm
  (``Invalid bbox format: {bbox}`` + ``continue``);
* L1315-L1322 - the stored detection's ``object_type`` / metric / DEBUG report of the class.

How every occurrence twin is reddened
=====================================
The harness reddens EVERY text-matching candidate of a key, so a key whose ``before`` text
also sits outside the lines this file owns is exercised there too.  Candidate line sets,
recomputed with the harness's own matcher (``replay_lib.candidates``) against this source:

============================================ ==== ==================================================
``before`` text                                n  candidate lines (dc11 keys in brackets)
============================================ ==== ==================================================
``image_name=image_file.name,``                 1  [1132 m114]
``camera_id=camera_id,``                        4  643 [1133 m115] 1282 [1361 m115]
``image_path=image_path,``                      2  644 [1134 m116] 1134
``object_class = detection_data.get(...)``      2  [1187 m210-218] 1315
``continue`` (``keyword:Continue->Break``)      7  1201 [m244/m277] 1209 1221 1240 1262 1278 1334
============================================ ==== ==================================================

* L643/L644 (the ``trace_span(...)`` attributes) run because ``_send_detection_request`` stays
  SHIPPED behind a ``wraps`` spy, so ``trace_span``'s recorded keyword map is read in
  ``test_the_forward_names_this_image_at_every_shipped_home`` together with the forward's own
  kwargs (L1131-L1134), the stored ``Detection.camera_id`` (L1282) and the baseline service's
  ``camera_id=`` keyword (L1361) - one test, four ``camera_id`` homes, two ``image_path`` homes;
* L1315 (the SECOND ``object_class = detection_data.get("class", "unknown")``, the one that
  feeds ``record_detection_by_class``) is read by the same two class-default legs as L1187;
* all SEVEN ``continue`` homes are driven by a ``[bad, good]`` payload, each asserting the
  ``good`` detection is still stored - a ``break`` in any one of them drops it:
  L1201 low confidence, L1209 incomplete bbox dict, L1221 scalar bbox, L1240 bbox completely
  outside the frame, L1262 bbox degenerate after clamping, L1278 non-positive bbox with no
  frame dimensions, L1334 the per-detection ``except`` arm.

Key -> test map (``mNN`` = ``...detect_objects__mutmut_NN``)
============================================================
* L1129-L1135 forward - ``test_the_forward_names_this_image_at_every_shipped_home``:
  m114, m115 (4 candidates), m116 (2 candidates).
* missing ``detections`` WARNING - ``test_a_response_without_detections_is_reported_once``:
  m149, m150, m152, m153, m154, m155, m156, m157, m158, m159 (a 620-char response makes the
  500-char slice observable) and the metric -
  ``test_a_response_without_detections_records_the_malformed_metric``: m160, m161, m162.
* L1163 - ``test_the_stored_stamp_is_utc_aware``: m165.
* L1173 gate - ``test_a_video_path_without_metadata_stays_on_the_image_leg``: m174 (the mutant
  raises ``AttributeError`` on ``None.get`` straight out of ``detect_objects``).
* L1175 - ``test_video_metadata_without_a_file_type_falls_back_to_mp4``: m180, m182, m185, m186;
  ``test_the_video_file_type_comes_from_the_metadata_key``: m179, m183, m184.
* L1182 - ``test_an_image_detection_with_metadata_keeps_the_image_leg_attributes``: m199.
* L1186 - ``test_a_detection_without_a_confidence_is_filtered_as_zero``: m204, m206, m209.
* L1187 - ``test_a_named_class_reaches_the_class_metric``: m211, m215, m216 (and, via the
  threshold lookup, m220-adjacent behaviour); ``test_a_classless_detection_reports_unknown``:
  m210, m212, m213, m214, m217, m218.
* L1187 fallback, read through the threshold lookup -
  ``test_a_classless_item_is_held_to_the_unknown_threshold``: m217, m218 (and the loss-of-
  fallback half of m210/m212/m213/m214, which leg P already reads via the class metric).
* L1191 - ``test_the_class_threshold_filters_a_person_the_default_would_pass``: m220;
  ``test_an_unlisted_class_uses_the_default_threshold``: m221, m223.
* L1204 - ``test_a_missing_bbox_key_hits_the_dict_arm``: m227, m229.
* L1208 - ``test_an_incomplete_bbox_dict_is_reported_with_its_own_text``: m243.
* L1220 - ``test_a_scalar_bbox_is_reported_with_its_own_text``: m276.
* the seven ``continue`` homes - ``test_a_low_confidence_item_does_not_end_the_loop``,
  ``test_an_incomplete_bbox_dict_does_not_end_the_loop``, ``test_a_scalar_bbox_does_not_end_the_loop``,
  ``test_an_outside_frame_bbox_does_not_end_the_loop``,
  ``test_a_degenerate_bbox_after_clamping_does_not_end_the_loop``,
  ``test_a_zero_width_bbox_without_dimensions_does_not_end_the_loop``,
  ``test_a_poisoned_item_does_not_end_the_loop``: m244, m277.

Discipline
----------
Production never bends: ``detect_objects`` and ``_send_detection_request`` run on a REAL
``DetectorClient`` (the construction idiom of the shipped ``test_detector_client.py`` suite),
so the shipped circuit breaker (L336-L344, L1068, L1129), semaphore, retry loop, span
lifecycle, threshold arithmetic, bbox clamping, ``Detection`` construction and commit order are
the code under test.  Patched collaborators are the filesystem reads, the image validator,
the thread offload, ``get_settings``, ``get_inference_semaphore``, ``get_correlation_headers``,
``trace_span``, the HTTP transport, the baseline service and three metrics - every one of them
``autospec=True`` or ``new=`` (WP4.2 ratchet).  There is no import-time global spy, no
session-scope clock and no ``time.monotonic``/``perf_counter`` patch: the only timing this
group touches is ``datetime.now(UTC)``'s tzinfo.  ``caplog.set_level`` does NOT clear the
buffer, so every log-reading leg opens its window with ``set_level`` + ``clear()`` and filters
to this module's logger name.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import detector_client as M

pytestmark = [pytest.mark.unit]

LOG_NAME = M.logger.name

# ---- values INJECTED by this file (never shipped values) --------------------
READ_TIMEOUT = 20.0
CONNECT_TIMEOUT = 30.0
DETECTOR_URL = "http://detector.invalid:8000"
IMAGE_DATA = b"fake-image-bytes-0123456789"  # len 27
IMAGE_NAME = "front-door-0001.jpg"
IMAGE_PATH = "/export/foscam/front_door/front-door-0001.jpg"
CAMERA_ID = "front_door"
VIDEO_PATH = "/export/foscam/parking_lot/time-lapse.mp4"
IMAGE_MIME = "image/jpeg"  # L1180 via get_mime_type_with_default(".jpg")
CONF_THRESHOLD = 0.5
# L1156's slice length, quoted (not imported) so a `[:501]` mutation is visible.
RESPONSE_SLICE = 500
# The malformed response is padded well past RESPONSE_SLICE + 1 so that BOTH the
# `str(None)` substitution and the `+1` slice change the stored value.
JUNK = "M" * 600

MALFORMED_MSG = "Malformed response from detector (missing 'detections')"
PIPELINE_ERROR_MSG = "Error processing detection data"
# L1208 / L1220 - the two bbox warnings, kept as PREFIXES here because the shipped
# f-string interpolates the offending value; each leg closes them with that value.
DICT_BBOX_WARN = "Invalid bbox dict format: "
SCALAR_BBOX_WARN = "Invalid bbox format: "


# =============================================================================
# Payload builders (the shipped detector's response shape)
# =============================================================================

OMIT = "<<omit>>"


def detection(
    object_class: Any = OMIT,
    confidence: Any = OMIT,
    bbox: Any = OMIT,
) -> dict[str, Any]:
    """One detection dict in the shipped shape, with any key omittable.

    ``OMIT`` leaves the key out entirely - which is what makes a ``.get()`` default
    observable - while any other value is stored verbatim, including a wrong type.
    """
    item: dict[str, Any] = {}
    if object_class is not OMIT:
        item["class"] = object_class
    if confidence is not OMIT:
        item["confidence"] = confidence
    if bbox is not OMIT:
        item["bbox"] = bbox
    return item


def payload(*items: dict[str, Any], width: Any = None, height: Any = None) -> dict[str, Any]:
    """A response body; the two dimension keys are omitted unless supplied (L1169-1170)."""
    body: dict[str, Any] = {"detections": list(items)}
    if width is not None:
        body["image_width"] = width
    if height is not None:
        body["image_height"] = height
    return body


GOOD = (0.9, [1, 2, 3, 4])  # a confident person in a tight, well-formed box


def good_item() -> dict[str, Any]:
    return detection("person", GOOD[0], list(GOOD[1]))


# =============================================================================
# Record observation
# =============================================================================


def _baseline_attrs() -> frozenset[str]:
    """Attribute names that are NOT part of a shipped ``extra=`` payload.

    The union of what ``logging.LogRecord.__init__`` always sets and what this
    module's ``ContextFilter`` injects (idempotent, so one pass adds exactly the
    injected names).  ``message`` is excluded - the formatter sets it.
    """
    probe = logging.LogRecord("baseline.probe", logging.DEBUG, "f", 1, "probe", (), None)
    core = set(probe.__dict__)
    injected = set(M.logger.filter(probe).__dict__) - core
    return frozenset(core | injected | {"message"})


BASELINE_ATTRS = _baseline_attrs()


def shipped_extra(record: logging.LogRecord) -> dict[str, Any]:
    """The ``extra=`` dict the shipped call passed, as the record shows it."""
    return {k: v for k, v in record.__dict__.items() if k not in BASELINE_ATTRS}


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer."""
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def msgs(caplog: pytest.LogCaptureFixture, level: int) -> list[Any]:
    """The RAW ``record.msg`` of every record at ``level`` from this logger, in order."""
    return [r.msg for r in mine(caplog) if r.levelno == level]


def record_with(caplog: pytest.LogCaptureFixture, level: int, msg: str) -> logging.LogRecord:
    """The single record at ``level`` carrying this raw text."""
    found = [r for r in mine(caplog) if r.levelno == level and r.msg == msg]
    assert len(found) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record {msg!r} from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in mine(caplog)]}"
    )
    assert tuple(found[0].args or ()) == (), f"unexpected lazy args: {found[0].args!r}"
    return found[0]


# =============================================================================
# Span recorder
# =============================================================================


class RecorderSpan:
    """The shipped ``SpanProtocol`` surface ``_send_detection_request`` writes."""

    def __init__(self) -> None:
        self.attrs: dict[str, Any] = {}
        self.setattr_calls: list[tuple[str, Any]] = []

    def set_attribute(self, key: str, value: Any) -> None:
        self.setattr_calls.append((key, value))
        self.attrs[key] = value

    def is_recording(self) -> bool:
        return True


@contextlib.contextmanager
def _yields(recorder: RecorderSpan) -> Any:
    """``trace_span``'s fake body: the shipped ``as span`` binds ``recorder``."""
    yield recorder


# =============================================================================
# Route harness: the shipped detect_objects with only I/O, socket and DB replaced
# =============================================================================


def _inline_offload(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Run an ``asyncio.to_thread`` offload on the current loop (L1083, L1090)."""
    return fn(*args, **kwargs)


class Route:
    """The shipped ``detect_objects`` route plus the doubles a leg reads back.

    ``_send_detection_request`` stays SHIPPED behind a ``wraps`` spy, so the span
    it opens and the ``post`` it makes are production behaviour; the response body
    is whatever ``body`` holds at the moment the shipped ``json()`` reads it.
    """

    def __init__(self, client: Any, session: Any) -> None:
        self.client = client
        self.session = session
        self.body: dict[str, Any] = {}
        self.span = RecorderSpan()
        self.trace_span = MagicMock(name="trace_span", side_effect=self._open_span)
        self.sent: Any = None

    def _open_span(self, *_args: Any, **_kwargs: Any) -> Any:
        return _yields(self.span)

    async def respond(self, *_args: Any, **_kwargs: Any) -> Any:
        """The ``post`` double: a coroutine function, so the shipped ``await``
        receives the RESPONSE rather than an un-awaited coroutine."""
        assert self.body is not None, "the leg forgot to set route.body"
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.raise_for_status.return_value = None
        resp.json.return_value = self.body
        return resp

    async def detect(
        self,
        *,
        video_path: Any = None,
        video_metadata: Any = None,
    ) -> list[Any]:
        return await self.client.detect_objects(
            IMAGE_PATH,
            CAMERA_ID,
            self.session,
            video_path=video_path,
            video_metadata=video_metadata,
        )

    @property
    def forwarded(self) -> dict[str, Any]:
        """The keyword map of the shipped L1129-L1135 forward.

        ``autospec`` of a BOUND method takes ``self`` out of the signature, so the
        record is exactly ``call(image_data=..., image_name=..., camera_id=...,
        image_path=...)``.
        """
        assert self.sent.call_count == 1, f"expected one forwarded call, got {self.sent.call_count}"
        call = self.sent.call_args
        assert call.args == (), f"the shipped forward passes no positionals: {call.args!r}"
        return dict(call.kwargs)


@pytest.fixture
def thresholds(request: pytest.FixtureRequest) -> dict[str, float]:
    """``settings.detection_class_thresholds`` - legs override via indirect params."""
    return dict(getattr(request, "param", {}))


@pytest.fixture
def default_threshold() -> float:
    return CONF_THRESHOLD


@pytest.fixture
def settings(default_threshold: Any, thresholds: Any) -> Any:
    st = MagicMock()
    st.ai_gateway_url = None
    st.use_ai_gateway = False
    st.yolo26_url = DETECTOR_URL
    st.yolo26_api_key = None
    st.yolo26_read_timeout = READ_TIMEOUT
    st.ai_connect_timeout = CONNECT_TIMEOUT
    st.ai_health_timeout = 2.0
    st.detector_max_retries = 3
    st.ai_max_concurrent_inferences = 11
    st.detection_confidence_threshold = default_threshold
    st.detection_class_thresholds = thresholds
    st.ai_warmup_enabled = False
    st.ai_cold_start_threshold_seconds = 60.0
    with patch("backend.services.detector_client.get_settings", autospec=True) as factory:
        factory.return_value = st
        yield st


@pytest.fixture(autouse=True)
def baseline_service() -> Any:
    """The shipped suite's autouse mock of ``get_baseline_service`` (L1352)."""
    service = MagicMock()
    service.update_baseline = AsyncMock()
    with patch("backend.services.detector_client.get_baseline_service", autospec=True) as factory:
        factory.return_value = service
        yield service


@pytest.fixture(autouse=True)
def metrics() -> Any:
    """Three metrics spied by name inside ``M`` - the shipped counters stay untouched."""
    with contextlib.ExitStack() as stack:
        yield SimpleNamespace(
            pipeline_error=stack.enter_context(
                patch.object(M, "record_pipeline_error", autospec=True)
            ),
            filtered=stack.enter_context(
                patch.object(M, "record_detection_filtered", autospec=True)
            ),
            by_class=stack.enter_context(
                patch.object(M, "record_detection_by_class", autospec=True)
            ),
        )


@pytest.fixture
def mock_session() -> Any:
    """DB session double in the shipped suite's shape; ``get`` finds no camera."""
    session = AsyncMock(spec=AsyncSession)
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def route(settings: Any, mock_session: Any) -> Any:
    """A REAL ``DetectorClient`` driven through the shipped ``detect_objects``."""
    client = M.DetectorClient(max_retries=1)
    assert client._confidence_threshold == CONF_THRESHOLD
    holder = Route(client, mock_session)
    with (
        patch.object(M.Path, "exists", autospec=True, return_value=True),
        patch.object(M.Path, "read_bytes", autospec=True, return_value=IMAGE_DATA),
        patch.object(
            client, "_validate_image_for_detection_async", autospec=True, return_value=True
        ),
        patch.object(M.asyncio, "to_thread", autospec=True, side_effect=_inline_offload),
        patch.object(
            M, "get_inference_semaphore", autospec=True, return_value=asyncio.Semaphore(4)
        ),
        patch.object(M, "get_correlation_headers", autospec=True, return_value={}),
        patch.object(M, "trace_span", new=holder.trace_span),
        patch.object(M.httpx.AsyncClient, "post", autospec=True, side_effect=holder.respond),
        patch.object(
            client,
            "_send_detection_request",
            autospec=True,
            wraps=client._send_detection_request,
        ) as sent,
    ):
        holder.sent = sent
        yield holder


def stored_paths(stored: list[Any]) -> list[Any]:
    return [d.object_type for d in stored]


# =============================================================================
# L1129-L1135: the forward and its three other homes (m114 / m115 / m116)
# =============================================================================


@pytest.mark.asyncio
async def test_the_forward_names_this_image_at_every_shipped_home(
    route: Any, mock_session: Any, baseline_service: Any
) -> None:
    """L643/L644 + L1131-L1134 + L1282 + L1361: every home of the three keywords.

    ``m115`` has FOUR text candidates and ``m116`` TWO, so all of them are read by
    this one conversation: the span's keyword map, the forward's keyword map, the
    ``Detection.camera_id`` the shipped constructor stores, and the baseline
    service's keyword.
    """
    route.body = payload(good_item())

    stored = await route.detect()

    assert route.forwarded == {
        "image_data": IMAGE_DATA,
        "image_name": IMAGE_NAME,
        "camera_id": CAMERA_ID,
        "image_path": IMAGE_PATH,
    }
    assert list(route.forwarded) == ["image_data", "image_name", "camera_id", "image_path"]

    opened = route.trace_span.call_args
    assert opened.kwargs == {
        "camera_id": CAMERA_ID,
        "image_path": IMAGE_PATH,
        "image_size_bytes": len(IMAGE_DATA),
    }

    assert len(stored) == 1
    assert stored[0].camera_id == CAMERA_ID
    assert stored[0].file_path == IMAGE_PATH
    assert mock_session.add.call_count == 1

    assert baseline_service.update_baseline.call_count == 1
    assert list(baseline_service.update_baseline.call_args.kwargs) == [
        "camera_id",
        "detection_class",
        "timestamp",
        "session",
    ]
    assert baseline_service.update_baseline.call_args.kwargs["camera_id"] == CAMERA_ID


# =============================================================================
# L1153-L1159: the missing-'detections' guard (m149-m162)
# =============================================================================


@pytest.mark.asyncio
async def test_a_response_without_detections_is_reported_once(
    route: Any, mock_session: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1154-L1157: the raw WARNING text and the ``str(result)[:500]`` extra.

    The body is a 620-char dict, so the shipped slice is exactly ``RESPONSE_SLICE``
    characters of ``str(body)``: ``str(None)`` (m158) reads ``"None"`` and the
    ``+1`` slice (m159) is one character longer, so both miss.  Dropping or
    renaming ``extra=`` removes the ``response`` key (m150/m152/m156/m157) and
    ``None``-ing / recasing the message replaces its text (m149/m153/m154/m155).
    """
    body = {"unexpected": JUNK}
    route.body = body
    expected = str(body)[:RESPONSE_SLICE]

    win(caplog)
    result = await route.detect()

    assert result == []
    assert not mock_session.add.called
    assert not mock_session.commit.called
    assert msgs(caplog, logging.WARNING) == [MALFORMED_MSG]
    assert msgs(caplog, logging.ERROR) == []
    extra = shipped_extra(record_with(caplog, logging.WARNING, MALFORMED_MSG))
    assert extra == {"response": expected}
    assert len(extra["response"]) == RESPONSE_SLICE


@pytest.mark.asyncio
async def test_a_response_without_detections_records_the_malformed_metric(
    route: Any, metrics: Any
) -> None:
    """L1158: ``record_pipeline_error("malformed_response")`` - once, verbatim."""
    route.body = {"unexpected": JUNK}

    result = await route.detect()

    assert result == []
    assert metrics.pipeline_error.call_args_list == [call("malformed_response")]
    assert metrics.filtered.call_args_list == []
    assert metrics.by_class.call_args_list == []


# =============================================================================
# L1163: the detection stamp (m165)
# =============================================================================


@pytest.mark.asyncio
async def test_the_stored_stamp_is_utc_aware(route: Any) -> None:
    """L1163: ``datetime.now(UTC)`` - the stamp on the stored detection is tz-aware UTC.

    ``datetime.now(None)`` still produces a datetime, so the only read that shows
    it is the tzinfo/utcoffset of the value the shipped code stored.
    """
    route.body = payload(good_item())

    stored = await route.detect()

    assert len(stored) == 1
    stamp = stored[0].detected_at
    assert isinstance(stamp, datetime)
    assert stamp.tzinfo is UTC
    assert stamp.utcoffset().total_seconds() == 0


# =============================================================================
# L1172-L1182: the media selector (m174 / m179-m186 / m199)
# =============================================================================


@pytest.mark.asyncio
async def test_a_video_path_without_metadata_stays_on_the_image_leg(route: Any) -> None:
    """L1173: the gate is AND.  A ``video_path`` with ``video_metadata=None`` is an IMAGE.

    The shipped else-leg reads the image's own MIME type; the ``or`` mutant enters
    the video leg and calls ``None.get("file_type", ...)`` - an ``AttributeError``
    the outer arms do not catch, so it leaves ``detect_objects``.
    """
    route.body = payload(good_item())

    stored = await route.detect(video_path=VIDEO_PATH, video_metadata=None)

    assert len(stored) == 1
    assert stored[0].file_path == IMAGE_PATH
    assert stored[0].file_type == IMAGE_MIME
    assert stored[0].media_type == "image"


@pytest.mark.asyncio
async def test_video_metadata_without_a_file_type_falls_back_to_mp4(route: Any) -> None:
    """L1175 default leg: ``{}`` metadata yields the shipped ``"video/mp4"``."""
    route.body = payload(good_item())

    stored = await route.detect(video_path=VIDEO_PATH, video_metadata={})

    assert len(stored) == 1
    assert stored[0].file_path == VIDEO_PATH
    assert stored[0].file_type == "video/mp4"
    assert stored[0].media_type == "video"


@pytest.mark.asyncio
async def test_the_video_file_type_comes_from_the_metadata_key(route: Any) -> None:
    """L1175 key leg: a present ``file_type`` wins over the default."""
    route.body = payload(good_item())

    stored = await route.detect(
        video_path=VIDEO_PATH,
        video_metadata={"file_type": "video/x-matroska"},
    )

    assert len(stored) == 1
    assert stored[0].file_type == "video/x-matroska"
    assert stored[0].media_type == "video"


@pytest.mark.asyncio
async def test_an_image_detection_with_metadata_keeps_the_image_leg_attributes(
    route: Any,
) -> None:
    """L1182 ``is_video = False``: metadata alone does not make this a video detection.

    ``video_path`` is None but ``video_metadata`` is truthy, so the shipped gate
    takes the image leg (L1178) and the L1296 read
    ``if is_video and video_metadata:`` is False - the frame dimensions therefore
    land in ``video_width``/``video_height`` (NEM-3903) and NO video field is
    copied.  The ``is_video = True`` mutant instead copies the codec out of the
    metadata and leaves the dimensions unset.
    """
    route.body = payload(good_item(), width=10, height=8)

    stored = await route.detect(video_path=None, video_metadata={"video_codec": "h264"})

    assert len(stored) == 1
    det = stored[0]
    assert det.media_type == "image"
    assert det.file_path == IMAGE_PATH
    assert det.file_type == IMAGE_MIME
    assert det.video_width == 10
    assert det.video_height == 8
    assert det.video_codec is None
    assert det.duration is None


# =============================================================================
# L1186: the confidence default (m204 / m206 / m209)
# =============================================================================


@pytest.mark.asyncio
async def test_a_detection_without_a_confidence_is_filtered_as_zero(
    route: Any, mock_session: Any, metrics: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1186: an item with no ``confidence`` is treated as ``0.0`` and FILTERED.

    0.0 is below the 0.5 default, so the shipped run records one filtered metric
    and stores nothing.  A ``None`` default (m204/m206) makes
    ``None < 0.5`` a ``TypeError``, which the per-detection arm turns into an ERROR
    record plus a ``detection_processing_error`` metric - a different conversation,
    so both the metric and the log are read.  A ``1.0`` default (m209) stores it.
    """
    route.body = payload(detection("person", bbox=[1, 2, 3, 4]))

    win(caplog)
    stored = await route.detect()

    assert stored == []
    assert mock_session.add.call_count == 0
    assert metrics.filtered.call_count == 1
    assert metrics.pipeline_error.call_args_list == []
    assert metrics.by_class.call_args_list == []
    assert msgs(caplog, logging.ERROR) == []
    assert msgs(caplog, logging.WARNING) == []


# =============================================================================
# L1187 / L1315: the class default (m210-m218)
# =============================================================================


@pytest.mark.asyncio
async def test_a_named_class_reaches_the_class_metric(route: Any, metrics: Any) -> None:
    """L1187 + L1315: a present ``class`` is used verbatim, never the fallback.

    A lookup under a renamed or ``None`` key reads the fallback instead, and
    ``detection_data.get("unknown")`` (m213) reads a key the response does not
    have - all of them surface as a different ``record_detection_by_class``
    argument than the shipped ``"person"``.
    """
    route.body = payload(good_item())

    stored = await route.detect()

    assert stored_paths(stored) == ["person"]
    assert stored[0].object_type == "person"
    assert metrics.by_class.call_args_list == [call("person")]
    assert metrics.filtered.call_count == 0


@pytest.mark.asyncio
async def test_a_classless_detection_reports_unknown(
    route: Any, metrics: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1187 fallback leg: no ``class`` key -> threshold key ``"unknown"``, stored type None.

    The two consumers differ by design: the threshold lookup and the class metric
    get ``"unknown"`` while ``Detection.object_type`` gets ``detection_data.get
    ("class")`` - ``None``.  Every loss of the fallback (m210/m212/m213/m214) or
    recasing of it (m217/m218) changes the metric argument, and a lost fallback
    that yields ``None`` also changes the DEBUG text.
    """
    route.body = payload(detection(confidence=GOOD[0], bbox=list(GOOD[1])))

    win(caplog)
    stored = await route.detect()

    assert len(stored) == 1
    assert stored[0].object_type is None
    assert metrics.by_class.call_args_list == [call("unknown")]
    assert msgs(caplog, logging.WARNING) == []
    assert msgs(caplog, logging.ERROR) == []
    record_with(
        caplog,
        logging.DEBUG,
        "Created detection: None (confidence: 0.90, bbox: [1, 2, 3, 4])",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("thresholds", [{"unknown": 0.9}], indirect=["thresholds"])
async def test_a_classless_item_is_held_to_the_unknown_threshold(
    route: Any, mock_session: Any, metrics: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1187 fallback leg, read through the THRESHOLD: the fallback text IS the key.

    With ``{"unknown": 0.9}`` configured, a classless item at 0.50 is filtered
    because the shipped fallback looks its own threshold up.  Every mutant that
    loses the fallback (m210 ``None``, m212/m214 a ``None``/dropped default, m213
    the key-swap) looks up a key the dict does not have and therefore lands on the
    0.5 default, which lets the same item through; the recased fallbacks
    (m217/m218) do the same for the same reason.
    """
    route.body = payload(detection(confidence=0.5, bbox=list(GOOD[1])))

    win(caplog)
    stored = await route.detect()

    assert stored == []
    assert mock_session.add.call_count == 0
    assert metrics.filtered.call_count == 1
    assert metrics.by_class.call_args_list == []
    assert metrics.pipeline_error.call_args_list == []
    # L1196-L1198 interpolates the looked-up class, so the fallback's TEXT is read
    # here too - a recased fallback never reaches this record at all (it lands on
    # the default and is stored), which the asserts above already catch.
    record_with(
        caplog,
        logging.DEBUG,
        "Filtering out detection with low confidence: unknown (0.50 < 0.90)",
    )
    assert msgs(caplog, logging.WARNING) == []
    assert msgs(caplog, logging.ERROR) == []


# =============================================================================
# L1191: the class-threshold lookup (m220 / m221 / m223)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("thresholds", [{"person": 0.9}], indirect=["thresholds"])
async def test_the_class_threshold_filters_a_person_the_default_would_pass(
    route: Any, mock_session: Any, metrics: Any
) -> None:
    """L1191 first key: a listed class is held to ITS threshold, not the default.

    0.50 confidence against ``{"person": 0.9}`` is filtered.  Looking the class up
    under ``None`` (m220) always lands on the 0.5 default, which lets the same item
    through.
    """
    route.body = payload(detection("person", 0.5, [1, 2, 3, 4]))

    stored = await route.detect()

    assert stored == []
    assert mock_session.add.call_count == 0
    assert metrics.filtered.call_count == 1
    assert metrics.pipeline_error.call_args_list == []


@pytest.mark.asyncio
@pytest.mark.parametrize("thresholds", [{"person": 0.9}], indirect=["thresholds"])
async def test_an_unlisted_class_uses_the_default_threshold(
    route: Any, metrics: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1191 second key: an unlisted class falls back to ``self._confidence_threshold``.

    A ``car`` at 0.50 against a 0.5 default is stored.  A dropped or ``None``
    fallback (m221/m223) makes the comparison ``0.5 < None``, which the shipped
    ``except TypeError`` arm reports as a processing error instead.
    """
    route.body = payload(detection("car", 0.5, [1, 2, 3, 4]))

    win(caplog)
    stored = await route.detect()

    assert stored_paths(stored) == ["car"]
    assert stored[0].confidence == 0.5
    assert metrics.filtered.call_count == 0
    assert metrics.pipeline_error.call_args_list == []
    assert msgs(caplog, logging.ERROR) == []


# =============================================================================
# L1204-L1221: the bbox reader (m227 / m229 / m243 / m276)
# =============================================================================


@pytest.mark.asyncio
async def test_a_missing_bbox_key_hits_the_dict_arm(
    route: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1204: no ``bbox`` key means an EMPTY DICT, which is the dict arm's problem.

    ``{}`` is a dict that lacks all four keys, so the shipped run warns with the
    DICT-format text naming ``{}``; a ``None`` default (m227/m229) is not a dict,
    so the same item falls to the scalar arm's different text.
    """
    route.body = payload(detection("person", GOOD[0]), good_item())

    win(caplog)
    stored = await route.detect()

    assert msgs(caplog, logging.WARNING) == [f"{DICT_BBOX_WARN}{{}}"]
    assert msgs(caplog, logging.ERROR) == []
    assert stored_paths(stored) == ["person"]


@pytest.mark.asyncio
async def test_an_incomplete_bbox_dict_is_reported_with_its_own_text(
    route: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1208: the dict arm warns with the offending value interpolated (m243)."""
    bbox = {"x": 1, "y": 2, "width": 3}
    route.body = payload(detection("person", GOOD[0], bbox))

    win(caplog)
    stored = await route.detect()

    assert stored == []
    assert msgs(caplog, logging.WARNING) == [f"{DICT_BBOX_WARN}{bbox}"]
    assert msgs(caplog, logging.ERROR) == []


@pytest.mark.asyncio
async def test_a_scalar_bbox_is_reported_with_its_own_text(
    route: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1220: a bbox that is neither a dict nor a 4-sequence warns with ITS text (m276)."""
    bbox = "not-a-container"
    route.body = payload(detection("person", GOOD[0], bbox))

    win(caplog)
    stored = await route.detect()

    assert stored == []
    assert msgs(caplog, logging.WARNING) == [f"{SCALAR_BBOX_WARN}{bbox}"]
    assert msgs(caplog, logging.ERROR) == []


# =============================================================================
# The seven continue homes: m244 (L1209) and m277 (L1221) each match all SEVEN
# =============================================================================


async def _both(route: Any, bad: dict[str, Any]) -> list[Any]:
    """Run a ``[bad, good]`` payload and report what survived the loop."""
    route.body = payload(bad, good_item())
    return await route.detect()


@pytest.mark.asyncio
async def test_a_low_confidence_item_does_not_end_the_loop(route: Any) -> None:
    """L1201: the low-confidence arm SKIPS the item; the loop continues."""
    stored = await _both(route, detection("person", 0.05, [1, 2, 3, 4]))

    assert stored_paths(stored) == ["person"]
    assert stored[0].confidence == GOOD[0]


@pytest.mark.asyncio
async def test_an_incomplete_bbox_dict_does_not_end_the_loop(
    route: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1209: the dict arm skips and keeps going (the key's own home)."""
    win(caplog)
    stored = await _both(route, detection("person", GOOD[0], {"x": 1, "y": 2}))

    assert stored_paths(stored) == ["person"]
    assert msgs(caplog, logging.WARNING) == [f"{DICT_BBOX_WARN}{{'x': 1, 'y': 2}}"]
    assert msgs(caplog, logging.ERROR) == []


@pytest.mark.asyncio
async def test_a_scalar_bbox_does_not_end_the_loop(
    route: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1221: the scalar arm skips and keeps going (the second key's own home)."""
    win(caplog)
    stored = await _both(route, detection("person", GOOD[0], "nope"))

    assert stored_paths(stored) == ["person"]
    assert msgs(caplog, logging.WARNING) == [f"{SCALAR_BBOX_WARN}nope"]


@pytest.mark.asyncio
async def test_an_outside_frame_bbox_does_not_end_the_loop(
    route: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1240: a box entirely outside the 10x8 frame is skipped, not fatal."""
    win(caplog)
    route.body = payload(
        detection("person", GOOD[0], [50, 50, 1, 1]),
        good_item(),
        width=10,
        height=8,
    )

    stored = await route.detect()

    assert stored_paths(stored) == ["person"]
    assert msgs(caplog, logging.WARNING) == [
        "Skipping detection with bbox completely outside image: "
        "bbox=(50, 50, 1, 1), image=(10x8), class=person"
    ]


@pytest.mark.asyncio
async def test_a_degenerate_bbox_after_clamping_does_not_end_the_loop(
    route: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1262: a partially-inside box that clamps to zero width is skipped.

    ``[3, 3, 0, 5]`` in a 10x10 frame is NOT completely outside (its x stays inside
    and ``x + 0 > 0``), so clamping produces a zero-width box - the L1256 warning -
    and the loop continues.
    """
    win(caplog)
    route.body = payload(
        detection("person", GOOD[0], [3, 3, 0, 5]),
        good_item(),
        width=10,
        height=10,
    )

    stored = await route.detect()

    assert stored_paths(stored) == ["person"]
    assert msgs(caplog, logging.WARNING) == [
        "Skipping detection with bbox too small after clamping: "
        "original=(3, 3, 0, 5), clamped=(3, 3, 0, 5), image=(10x10), class=person"
    ]


@pytest.mark.asyncio
async def test_a_zero_width_bbox_without_dimensions_does_not_end_the_loop(
    route: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1278: with no frame dimensions, a non-positive box is skipped by the elif arm."""
    win(caplog)
    route.body = payload(detection("person", GOOD[0], [3, 3, 0, 5]), good_item())

    stored = await route.detect()

    assert stored_paths(stored) == ["person"]
    assert msgs(caplog, logging.WARNING) == [
        "Skipping detection with non-positive bbox dimensions: bbox=(3, 3, 0, 5), class=person"
    ]


@pytest.mark.asyncio
async def test_a_poisoned_item_does_not_end_the_loop(
    route: Any, caplog: pytest.LogCaptureFixture, metrics: Any
) -> None:
    """L1334: the per-detection ``except`` arm CONTINUES to the next item.

    The poison is a bbox coordinate the shipped ``int()`` at L1210 cannot parse -
    the ``ValueError`` lands in this arm (the telemetry inside the request only
    reads ``confidence``/``class``, so the response is still a valid one).  The arm
    logs the error with its traceback, records ``detection_processing_error`` and
    moves on, so the second item is still stored.
    """
    win(caplog)
    route.body = payload(
        detection("person", GOOD[0], {"x": "abc", "y": 2, "width": 3, "height": 4}),
        good_item(),
    )

    stored = await route.detect()

    assert stored_paths(stored) == ["person"]
    assert msgs(caplog, logging.WARNING) == []
    assert msgs(caplog, logging.ERROR) == [PIPELINE_ERROR_MSG]
    assert metrics.pipeline_error.call_args_list == [call("detection_processing_error")]
    poisoned = record_with(caplog, logging.ERROR, PIPELINE_ERROR_MSG)
    assert shipped_extra(poisoned).keys() == {"error"}
    assert poisoned.exc_info is not False


# =============================================================================
# Control: the whole image-leg contract on one clean detection
# =============================================================================


@pytest.mark.asyncio
async def test_one_clean_detection_is_stored_with_the_shipped_image_leg_fields(
    route: Any, mock_session: Any, metrics: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1184-L1322 control: attributes, bbox ints, media fields and the commit order."""
    route.body = payload(detection("person", 0.87, [7, 8, 9, 10]), width=1920, height=1080)

    win(caplog)
    stored = await route.detect()

    assert len(stored) == 1
    det = stored[0]
    assert det.camera_id == CAMERA_ID
    assert det.file_path == IMAGE_PATH
    assert det.file_type == IMAGE_MIME
    assert det.media_type == "image"
    assert det.object_type == "person"
    assert det.confidence == 0.87
    assert (det.bbox_x, det.bbox_y, det.bbox_width, det.bbox_height) == (7, 8, 9, 10)
    assert det.video_width == 1920
    assert det.video_height == 1080
    assert isinstance(det.detected_at, datetime)
    assert mock_session.add.call_args_list == [call(det)]
    assert mock_session.commit.await_count == 1

    assert metrics.filtered.call_count == 0
    assert metrics.pipeline_error.call_args_list == []
    assert msgs(caplog, logging.WARNING) == []
    assert msgs(caplog, logging.ERROR) == []
    assert msgs(caplog, logging.INFO) == ["Stored detections"]
