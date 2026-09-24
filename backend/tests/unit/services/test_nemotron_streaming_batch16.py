"""Batch-16 battery: nemotron_streaming TEST-GAP clusters from the WP4.4 dossier
(``archive/wp25-feed/wp44-triage/nemotron_streaming.md``).

The shipped suite (``test_nemotron_streaming.py``) asserts *membership* everywhere
(``"content" in ev``, ``ev["event_type"] == "error"``, substring matches on
``error_message``), so key-mangling / default-flipping / argument-clobbering mutants
inside the two ~330-line functions survived (333 survivors, 37.5% score). This
battery pins FULL SHAPES instead.

THIS FIRST SHIPMENT (23 tests) pins the dossier clusters around the request
build and carriers: C1 LLMREQUEST, C2 PAYLOAD-HEADERS, C21 SANITIZE, C22
TRUNCATE, C5'-SSE-FRAME-PARSING, C9 CAMERA-SQL, C10 BATCHFETCH-DETLIST,
C11 ENRICHCACHE-ARGS, C12 HH-DICTKEYS, C14 DETDICTS, C19 JUNCTION and the
LLMInteraction wiring. The dossier's ERROR-PATH clusters (C6 ERRMSG, C7/C8
IDEMPOTENCY, C15 ACCUMTEXT, C16 PARSEFALLBACK, C17 EVENT-CONSTRUCT, C18
COMPLETE-FALLBACK, C20 BROADCAST) have their literals ALREADY MEASURED
(``/tmp/b16-probes.json`` an_err_*/an_parse_*/an_idem_*/an_complete_blank
sections) and are armed for batch-16b — no kill claim is made for them here.
Kill tallies are only claimed after the batch-16 lane red-check; none are
asserted in this file.

EVERY asserted literal below was MEASURED against the pristine shipped source on
2026-09-22/23 by throwaway probes (``/tmp/b16-probe-*.py`` + ``/tmp/b16-harness.py``
run with ``uv run python`` under the repo venv; consolidated dump
``/tmp/b16-probes.json``; re-confirmed 2026-09-23 with ``/tmp/b16-probe-confirm.py``).
No value was guessed and production was NOT bent to any mutant.

Key measured facts that correct / sharpen the dossier:

* ``httpx.AsyncClient`` is constructed with the single keyword ``timeout=<analyzer
 ._timeout>`` (identity-preserved object) and NOTHING else — positional-arg list is
  empty (probe llm_baseline.httpx_ctor / m_httpx).
* ``client.stream`` receives exactly the positionals ``("POST",
  "<llm_url>/completion")`` and exactly the kwargs ``("json", "headers")``.
* The payload dict is a SIX-key dict in shipped order ``prompt, temperature, top_p,
  max_tokens, stop, stream`` with ``temperature == 0.3`` / ``top_p == 0.95``
  hardcoded and ``max_tokens`` taken from ``get_settings().nemotron_max_output_tokens``
  (measured 1536 -> 1536, 2048 -> 2048: the settings value carrier is what the mutant
  would otherwise flatten).
* Headers: ``{"Content-Type": "application/json"}`` is built FIRST then merged with
  ``analyzer._get_auth_headers()`` — the full merged dict is pinned, and the base
  value survives an empty auth-header dict.
* SSE parsing: only lines starting with the exact 6-char prefix ``"data: "`` are
  considered; ``"data:"`` (no space), ``""``, ``"   "`` and non-data lines are
  skipped; a frame whose ``content`` is missing OR empty yields nothing; a frame with
  a non-string content still yields when truthy; ``data: [DONE]`` breaks (a chunk
  after DONE is never emitted); malformed JSON after a valid chunk does not stop the
  stream.
* The two sanitizers are imported *inside* ``call_llm_streaming`` from
  ``backend.services.prompt_sanitizer``, so that is the patch target; their return
  values are what reaches ``_build_prompt``, and the prompt sent to the LLM is the
  return value of ``_validate_and_truncate_prompt`` (not the built prompt).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest
from sqlalchemy.dialects import postgresql

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services import nemotron_streaming as NS

pytestmark = pytest.mark.unit

NSP = "backend.services.nemotron_streaming"
DIALECT = postgresql.dialect()

LLM_URL = "http://localhost:8091"
TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=120.0, pool=10.0)
BASE_TIME = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)


def compiled(stmt) -> str:
    return str(stmt.compile(dialect=DIALECT, compile_kwargs={"literal_binds": True}))


def make_analyzer():
    """MEASURED carrier analyzer (probe harness /tmp/b16-harness.py make_analyzer)."""
    a = MagicMock(name="analyzer")
    a._llm_url = LLM_URL
    a._timeout = TIMEOUT
    a._redis = AsyncMock()
    a._redis.get = AsyncMock(return_value=None)
    a._build_prompt = MagicMock(return_value="BUILT_PROMPT")
    a._validate_and_truncate_prompt = MagicMock(return_value="TRUNCATED_PROMPT")
    a._get_auth_headers = MagicMock(return_value={"X-Auth": "auth-token"})
    a._format_detections = MagicMock(return_value="FORMATTED_DETECTIONS")
    a._parse_llm_response = MagicMock(
        return_value={
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Parsed summary",
            "reasoning": "Parsed reasoning",
        }
    )
    a._validate_risk_data = MagicMock(side_effect=lambda x: x)
    a._check_idempotency = AsyncMock(return_value=None)
    a._set_idempotency = AsyncMock()
    a._get_existing_event = AsyncMock(return_value=None)
    a._get_enriched_context = AsyncMock(return_value=None)
    a._get_enrichment_result = AsyncMock(return_value=None)
    a._broadcast_event = AsyncMock()
    return a


def make_settings(max_tokens=1536):
    s = MagicMock(name="settings")
    s.nemotron_max_output_tokens = max_tokens
    return s


def make_response(sse_lines):
    resp = MagicMock(name="response")
    resp.raise_for_status = MagicMock()

    async def gen():
        for line in sse_lines:
            yield line

    resp.aiter_lines = gen
    return resp


def _stream_cm(response):
    class MockStreamCM:
        async def __aenter__(self):
            return response

        async def __aexit__(self, *args):
            return None

    return MockStreamCM()


async def run_llm(analyzer, sse_lines, *, settings=None, extra_patches=(), **call_kwargs):
    """Drive ``call_llm_streaming`` and return the measured call-site facts."""
    settings = settings or make_settings()
    response = make_response(sse_lines)
    client = MagicMock(name="client")
    client.stream = MagicMock(return_value=_stream_cm(response))
    sem_m = patch(f"{NSP}.get_inference_semaphore", autospec=True)
    httpx_m = patch(f"{NSP}.httpx.AsyncClient", autospec=True)
    settings_m = patch(f"{NSP}.get_settings", return_value=settings, autospec=True)
    ctxs = [settings_m, sem_m, httpx_m, *extra_patches]
    entered = [c.__enter__() for c in ctxs]
    settings_mock, sem, httpx_cls = entered[0], entered[1], entered[2]
    chunks: list = []
    call_kwargs.setdefault("camera_name", "probe_camera")
    call_kwargs.setdefault("start_time", "2025-12-23T14:30:00")
    call_kwargs.setdefault("end_time", "2025-12-23T14:31:00")
    call_kwargs.setdefault("detections_list", "1. person (0.95)")
    try:
        sem.return_value = AsyncMock()
        httpx_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        httpx_cls.return_value.__aexit__ = AsyncMock()
        async for chunk in NS.call_llm_streaming(analyzer=analyzer, **call_kwargs):
            chunks.append(chunk)
    finally:
        for c in ctxs:
            c.__exit__(None, None, None)
    return {
        "chunks": chunks,
        "settings_mock": settings_mock,
        "sem_mock": sem,
        "sem_instance": sem.return_value,
        "httpx_call": httpx_cls.call_args,
        "httpx_calls": httpx_cls.call_args_list,
        "client": client,
        "stream_call": client.stream.call_args,
        "response": response,
    }


def sample_detections():
    """MEASURED fixtures (probe harness sample_detections): det 1 carries a bbox,
    det 2 has None bbox/video/track fields, det 3 has object_type=None, det 4 has
    confidence=None (added for the C14 filter / C12 null-field pins)."""
    return [
        Detection(
            id=1,
            camera_id="test_camera",
            file_path="/export/foscam/test_camera/img1.jpg",
            detected_at=BASE_TIME,
            object_type="person",
            confidence=0.95,
            bbox_x=10,
            bbox_y=20,
            bbox_width=30,
            bbox_height=40,
            video_width=1920,
            video_height=1080,
            track_id=7,
        ),
        Detection(
            id=2,
            camera_id="test_camera",
            file_path="/export/foscam/test_camera/img2.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
            object_type="car",
            confidence=0.88,
            bbox_x=None,
            video_width=None,
            video_height=None,
            track_id=None,
        ),
    ]


_DEFAULT = object()


def make_session(camera=_DEFAULT, event_id=456):
    """Session whose every ``execute`` returns the camera row (MEASURED harness)."""
    if camera is _DEFAULT:
        camera = Camera(id="test_camera", name="Test Camera", folder_path="/test/path")
    session = MagicMock(name="session")
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    camera_result = MagicMock(name="camera_result")
    camera_result.scalar_one_or_none = MagicMock(return_value=camera)
    session.execute = AsyncMock(return_value=camera_result)
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def refresh(obj):
        if isinstance(obj, Event):
            obj.id = event_id

    session.refresh = AsyncMock(side_effect=refresh)
    return session


async def run_analyze(
    analyzer,
    *,
    session=None,
    detections=None,
    chunks=("Based", " on"),
    llm_side_effect=None,
    camera=_DEFAULT,
    event_id=456,
    patches=(),
    **call_kw,
):
    """Drive ``analyze_batch_streaming``; return yielded events + call-site facts."""
    detections = sample_detections() if detections is None else detections
    session = make_session(camera=camera, event_id=event_id) if session is None else session
    captured: dict = {}

    if llm_side_effect is None:

        async def llm_side_effect(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            for c in chunks:
                yield c

    sess_m = patch(f"{NSP}.get_session", return_value=session, autospec=True)
    fetch_m = patch(f"{NSP}.batch_fetch_detections", return_value=detections, autospec=True)
    llm_m = patch(f"{NSP}.call_llm_streaming", side_effect=llm_side_effect, autospec=True)
    ai_m = patch(f"{NSP}.observe_ai_request_duration", autospec=True)
    stage_m = patch(f"{NSP}.observe_stage_duration", autospec=True)
    created_m = patch(f"{NSP}.record_event_created", autospec=True)
    camera_metric_m = patch(f"{NSP}.record_event_by_camera", autospec=True)
    metrics = (ai_m, stage_m, created_m, camera_metric_m)
    ctxs = [sess_m, fetch_m, llm_m, *metrics, *patches]
    entered = [c.__enter__() for c in ctxs]
    events: list = []
    try:
        call_kw.setdefault("analyzer", analyzer)
        call_kw.setdefault("batch_id", "test_batch")
        call_kw.setdefault("camera_id", "test_camera")
        call_kw.setdefault("detection_ids", [1, 2])
        async for ev in NS.analyze_batch_streaming(**call_kw):
            events.append(ev)
    finally:
        for c in ctxs:
            c.__exit__(None, None, None)
    return {
        "events": events,
        "captured": captured,
        "session": session,
        "fetch_mock": entered[1],
        "llm_mock": entered[2],
        "metrics": {
            "observe_ai_request_duration": entered[3],
            "observe_stage_duration": entered[4],
            "record_event_created": entered[5],
            "record_event_by_camera": entered[6],
        },
        "execute_calls": session.execute.call_args_list,
        "add_calls": session.add.call_args_list,
        "commit_count": session.commit.call_count,
    }


# ---------------------------------------------------------------------------
# C1 LLMREQUEST / C2 PAYLOAD-HEADERS
# ---------------------------------------------------------------------------

SSE_OK = [
    'data: {"content": "Based"}',
    'data: {"content": " on"}',
    'data: {"content": " the"}',
    "data: [DONE]",
]


class TestCallLlmRequestShape:
    """C1/C2: the exact HTTP request the shipped code builds (probe llm_baseline)."""

    async def test_httpx_client_kwargs_exactly_timeout(self):
        a = make_analyzer()
        r = await run_llm(a, SSE_OK)
        # MEASURED: no positionals, one kwarg 'timeout', SAME object as analyzer._timeout
        assert r["httpx_call"].args == ()
        assert list(r["httpx_call"].kwargs) == ["timeout"]
        assert r["httpx_call"].kwargs["timeout"] is a._timeout
        assert r["httpx_calls"] == [call(timeout=TIMEOUT)]
        assert r["chunks"] == ["Based", " on", " the"]

    async def test_stream_called_with_exact_positionals_and_kwargs(self):
        a = make_analyzer()
        r = await run_llm(a, SSE_OK)
        call = r["stream_call"]
        assert call.args == ("POST", "http://localhost:8091/completion")
        assert list(call.kwargs) == ["json", "headers"]
        assert r["client"].stream.call_count == 1

    async def test_url_follows_analyzer_llm_url(self):
        a = make_analyzer()
        a._llm_url = "http://llm.internal:9999/v1"
        r = await run_llm(a, SSE_OK)
        assert r["stream_call"].args == ("POST", "http://llm.internal:9999/v1/completion")


# ---------------------------------------------------------------------------
# C3 BUILDPROMPT / C4 CONTEXT-DEFAULTS / C21 SANITIZE / C22 TRUNCATE
# ---------------------------------------------------------------------------


class TestBuildPromptAndSanitize:
    """C3/C4/C21/C22 (probes llm_baseline.build_prompt_kwargs, llm_sanitize)."""

    async def test_build_prompt_receives_all_ten_kwargs_verbatim(self):
        a = make_analyzer()
        await run_llm(a, SSE_OK)
        kwargs = a._build_prompt.call_args.kwargs
        assert list(kwargs) == [
            "camera_name",
            "start_time",
            "end_time",
            "detections_list",
            "enriched_context",
            "enrichment_result",
            "camera_health_context",
            "detection_dicts",
            "auto_tuning_context",
            "household_context",
        ]  # MEASURED key order (llm_baseline)
        assert kwargs["camera_name"] == "probe_camera"
        assert kwargs["start_time"] == "2025-12-23T14:30:00"
        assert kwargs["end_time"] == "2025-12-23T14:31:00"
        assert kwargs["detections_list"] == "1. person (0.95)"
        assert kwargs["enriched_context"] is None
        assert kwargs["enrichment_result"] is None
        assert kwargs["camera_health_context"] == ""
        assert kwargs["detection_dicts"] is None
        assert kwargs["auto_tuning_context"] == ""
        assert kwargs["household_context"] == ""

    async def test_truncate_receives_built_prompt_and_result_is_sent(self):
        a = make_analyzer()
        r = await run_llm(a, SSE_OK)
        a._validate_and_truncate_prompt.assert_called_once_with("BUILT_PROMPT")
        assert r["stream_call"].kwargs["json"]["prompt"] == "TRUNCATED_PROMPT"

    async def test_sanitizers_run_on_camera_and_detections(self):
        a = make_analyzer()
        cam = MagicMock(name="sanitize_camera", return_value="sanitized_camera")
        det = MagicMock(name="sanitize_det", return_value="sanitized_detections")
        # new= so the installed attribute IS our mock (autospec re-wraps on
        # each __enter__ and the run harness enters the ctxs, not us).
        cam_m = patch("backend.services.prompt_sanitizer.sanitize_camera_name", new=cam)
        det_m = patch("backend.services.prompt_sanitizer.sanitize_detection_description", new=det)
        await run_llm(
            a,
            SSE_OK,
            extra_patches=(cam_m, det_m),
            camera_name="<script>alert('xss')</script>",
            detections_list="<img src=x onerror=alert(1)>",
        )
        # MEASURED llm_sanitize: sanitizer receives the RAW input, its RETURN
        # VALUE is what reaches _build_prompt.
        cam.assert_called_once_with("<script>alert('xss')</script>")
        det.assert_called_once_with("<img src=x onerror=alert(1)>")
        kwargs = a._build_prompt.call_args.kwargs
        assert kwargs["camera_name"] == "sanitized_camera"
        assert kwargs["detections_list"] == "sanitized_detections"


# ---------------------------------------------------------------------------
# C5 SSE-FRAME-PARSING (probes llm_frames, /tmp/b16-probe-extra.json e2/e5)
# ---------------------------------------------------------------------------


class TestSseFrameParsing:
    """Only exact-prefix "data: " frames with truthy string content are yielded."""

    async def test_malformed_and_nonmatching_frames_are_skipped_not_fatal(self):
        a = make_analyzer()
        r = await run_llm(
            a,
            [
                'data: {"content": "Valid"}',
                "data: {invalid",  # malformed JSON -> warning, stream continues
                'data: {"content": "After"}',
                'data:{"no-space":"x"}',  # missing space after colon -> NOT a data frame
                "",  # empty line -> skipped
                "   ",  # whitespace line: startswith("data: ")? no -> skipped
                "not-a-frame",
                'data: {"other": 1}',  # data frame without content key -> nothing yielded
                'data: {"content": ""}',  # empty content -> falsy -> nothing yielded
                "data: [DONE]",
                'data: {"content": "post-done"}',  # after DONE: never reached
            ],
        )
        assert r["chunks"] == ["Valid", "After"]  # MEASURED e2_chunks

    async def test_done_breaks_before_emitting_later_chunk(self):
        a = make_analyzer()
        r = await run_llm(a, ['data: {"content": "A"}', "data: [DONE]", 'data: {"content": "B"}'])
        assert r["chunks"] == ["A"]

    async def test_non_string_content_still_yields_when_truthy(self):
        a = make_analyzer()
        r = await run_llm(
            a, ['data: {"content": 7}', 'data:  {"content": "two-space"}', "data: [DONE]"]
        )
        # MEASURED e5: JSON int 7 yields (truthy); "data:  " (two spaces) IS a
        # data: -prefixed frame (prefix is 6 chars "data: " then " {\"content..." ->
        # actually line[6:] == ' {"content..." -> json.loads accepts leading ws)
        assert r["chunks"] == [7, "two-space"]

    async def test_all_frames_no_done_still_drains(self):
        a = make_analyzer()
        r = await run_llm(a, ['data: {"content": "x"}'])
        assert r["chunks"] == ["x"]


# ---------------------------------------------------------------------------
# C2 PAYLOAD full-shape / settings carrier (probes llm_baseline.payload,
# llm_settings_flow, m_httpx)
# ---------------------------------------------------------------------------


class TestPayloadSettingsCarrier:
    async def test_payload_exact_keys_and_hardcoded_sampling(self):
        a = make_analyzer()
        r = await run_llm(a, SSE_OK)
        payload = r["stream_call"].kwargs["json"]
        assert list(payload) == ["prompt", "temperature", "top_p", "max_tokens", "stop", "stream"]
        assert payload["temperature"] == 0.3
        assert payload["top_p"] == 0.95
        assert payload["max_tokens"] == 1536  # from make_settings default
        assert payload["stream"] is True

    async def test_max_tokens_carries_settings_value_not_constant(self):
        a = make_analyzer()
        r = await run_llm(a, SSE_OK, settings=make_settings(max_tokens=2048))
        payload = r["stream_call"].kwargs["json"]
        assert payload["max_tokens"] == 2048  # MEASURED llm_settings_flow

    async def test_httpx_client_built_once_with_timeout_kwarg(self):
        a = make_analyzer()
        r = await run_llm(a, SSE_OK)
        assert len(r["httpx_calls"]) == 1  # MEASURED m_httpx.n
        assert list(r["httpx_call"].kwargs) == ["timeout"]
        assert r["httpx_call"].kwargs["timeout"] is a._timeout  # identity, MEASURED


# ---------------------------------------------------------------------------
# C10 BATCHFETCH-DETLIST / C11 ENRICHCACHE-ARGS / C12 HH-DICTKEYS (dets4)
# probes m_fetch, b16-probe-wire.json enrich, b16-probe-d4.json
# ---------------------------------------------------------------------------


def dets4():
    """MEASURED 4-detection fixture (/tmp/b16-probe-d4.json): det3 object_type=None
    (-> class_name "unknown"), det4 confidence=None (-> filtered out)."""
    dets = sample_detections()
    dets += [
        Detection(
            id=3,
            camera_id="test_camera",
            file_path="/x3.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 30, tzinfo=UTC),
            object_type=None,
            confidence=0.5,
            bbox_x=None,
            video_width=None,
            video_height=None,
            track_id=None,
        ),
        Detection(
            id=4,
            camera_id="test_camera",
            file_path="/x4.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 45, tzinfo=UTC),
            object_type="dog",
            confidence=None,
            bbox_x=None,
            video_width=None,
            video_height=None,
            track_id=None,
        ),
    ]
    return dets


class TestFetchAndEnrichArgs:
    async def test_batch_fetch_exact_args(self):
        a = make_analyzer()
        r = await run_analyze(a)
        assert r["fetch_mock"].call_count == 1
        (sess, ids) = r["fetch_mock"].call_args.args
        assert sess is r["session"]
        assert ids == [1, 2]  # int()-cast of detection_ids, MEASURED m_fetch

    async def test_format_detections_and_llm_detections_list(self):
        a = make_analyzer()
        dets = sample_detections()
        r = await run_analyze(a, detections=dets)
        # Detection has no __eq__ -> pin the carrier by IDENTITY (MEASURED
        # format_call in an_camera_present shows the same fetched list)
        assert a._format_detections.call_args.args[0] is dets
        assert r["captured"]["kwargs"]["detections_list"] == "FORMATTED_DETECTIONS"

    async def test_enriched_context_call_args(self):
        a = make_analyzer()
        r = await run_analyze(a)
        args = a._get_enriched_context.call_args.args
        assert args[0] == "test_batch"
        assert args[1] == "test_camera"
        assert args[2] == [1, 2]
        assert args[3] is r["session"]  # MEASURED b16-probe-wire.enrich

    async def test_enrichment_result_call_args(self):
        a = make_analyzer()
        dets = sample_detections()
        await run_analyze(a, detections=dets)
        kwargs = a._get_enrichment_result.call_args.kwargs
        args = a._get_enrichment_result.call_args.args
        assert args[0] == "test_batch"
        assert args[1] is dets  # identity, see above
        assert kwargs["camera_id"] == "test_camera"


class TestHouseholdDictsAndDetectionDicts:
    """C12 HH-DICTKEYS + C14 DETDICTS (MEASURED /tmp/b16-probe-d4.json)."""

    async def test_household_arg0_full_dict_shape(self):
        a = make_analyzer()
        a._get_household_context = AsyncMock(return_value="HOUSEHOLD_CTX")
        await run_analyze(a, detections=dets4())
        call_args = a._get_household_context.call_args
        assert call_args.args[0] == [
            {
                "id": 1,
                "object_type": "person",
                "confidence": 0.95,
                "file_path": "/export/foscam/test_camera/img1.jpg",
                "bounding_box": {"bbox_x": 10, "bbox_y": 20, "bbox_width": 30, "bbox_height": 40},
                "video_width": 1920,
                "video_height": 1080,
                "detected_at": BASE_TIME,
                "track_id": 7,
                "camera_id": "test_camera",
            },
            {
                "id": 2,
                "object_type": "car",
                "confidence": 0.88,
                "file_path": "/export/foscam/test_camera/img2.jpg",
                "bounding_box": None,
                "video_width": None,
                "video_height": None,
                "detected_at": datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
                "track_id": None,
                "camera_id": "test_camera",
            },
            {
                "id": 3,
                "object_type": None,
                "confidence": 0.5,
                "file_path": "/x3.jpg",
                "bounding_box": None,
                "video_width": None,
                "video_height": None,
                "detected_at": datetime(2025, 12, 23, 14, 30, 30, tzinfo=UTC),
                "track_id": None,
                "camera_id": "test_camera",
            },
            {
                "id": 4,
                "object_type": "dog",
                "confidence": None,
                "file_path": "/x4.jpg",
                "bounding_box": None,
                "video_width": None,
                "video_height": None,
                "detected_at": datetime(2025, 12, 23, 14, 30, 45, tzinfo=UTC),
                "track_id": None,
                "camera_id": "test_camera",
            },
        ]  # det1 keeps nested bbox; dets 2-4 bbox None via the bbox_x-is-None guard

    async def test_household_called_with_two_positionals(self):
        a = make_analyzer()
        a._get_household_context = AsyncMock(return_value="HOUSEHOLD_CTX")
        await run_analyze(a, detections=dets4())
        assert list(a._get_household_context.call_args.kwargs) == []
        assert a._get_household_context.call_args.args[1] is None

    async def test_llm_detection_dicts_and_time_window(self):
        a = make_analyzer()
        r = await run_analyze(a, detections=dets4())
        kw = r["captured"]["kwargs"]
        # MEASURED b16-probe-d4: confidence-None det4 filtered OUT; det3
        # object_type=None -> class_name "unknown"; keys (confidence, class_name)
        assert kw["detection_dicts"] == [
            {"confidence": 0.95, "class_name": "person"},
            {"confidence": 0.88, "class_name": "car"},
            {"confidence": 0.5, "class_name": "unknown"},
        ]
        # MEASURED start_end: min/max of detected_at, isoformat
        assert kw["start_time"] == "2025-12-23T14:30:00+00:00"
        assert kw["end_time"] == "2025-12-23T14:30:45+00:00"
        assert kw["camera_name"] == "Test Camera"  # camera row present


# ---------------------------------------------------------------------------
# C9 CAMERA-SQL / C19 JUNCTION / LLMInteraction wiring
# probes m_camera_where, m_junction, b16-probe-wire.json, b16-probe-last2.json
# ---------------------------------------------------------------------------


class TestCameraSqlJunctionInteraction:
    async def test_camera_select_where_and_param(self):
        a = make_analyzer()
        r = await run_analyze(a)
        stmt = r["execute_calls"][0].args[0]
        sql = compiled(stmt)  # literal_binds: MEASURED m_camera_where shows the bound form
        assert "cameras.id = 'test_camera'" in sql
        assert "FROM cameras" in sql
        assert "cameras.name" in sql
        assert "LIMIT" not in sql  # scalar_one_or_none contract: no LIMIT 1 inserted

    async def test_junction_insert_compiled_shape(self):
        a = make_analyzer()
        r = await run_analyze(a, event_id=456)
        stmt = r["execute_calls"][1].args[0]
        sql = str(stmt.compile(dialect=DIALECT))
        # MEASURED m_junction exact string
        assert sql == (
            "INSERT INTO event_detections (event_id, detection_id, created_at) "
            "VALUES (%(event_id_m0)s, %(detection_id_m0)s, %(created_at)s), "
            "(%(event_id_m1)s, %(detection_id_m1)s, %(created_at_m1)s) "
            "ON CONFLICT (event_id, detection_id) DO NOTHING"
        )
        params = stmt.compile(dialect=DIALECT).params
        assert params == {
            "event_id_m0": 456,
            "detection_id_m0": 1,
            "created_at": None,
            "event_id_m1": 456,
            "detection_id_m1": 2,
            "created_at_m1": None,
        }  # MEASURED JUNC-PARAMS

    async def test_llm_interaction_wiring(self):
        a = make_analyzer()
        r = await run_analyze(a, chunks=("Based", " on"))
        lli = next(
            c.args[0] for c in r["add_calls"] if type(c.args[0]).__name__ == "LLMInteraction"
        )
        assert lli.event_id == 456
        assert lli.raw_response == "Based on"  # MEASURED tf_lli_raw: accumulated
        assert lli.enrichment_snapshot is a._build_enrichment_snapshot.return_value
        assert lli.context_sources is a._build_context_sources.return_value
        assert lli.household_matches is None  # enrichment_result None -> None
        snap_kw = a._build_enrichment_snapshot.call_args.kwargs
        assert snap_kw["detection_ids"] == [1, 2]
        assert snap_kw["enrichment_result"] is None
        assert snap_kw["enriched_context"] is None
