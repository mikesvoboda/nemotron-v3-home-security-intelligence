r"""S3 batch-29 lane dc29a - the two KILLABLE survivors of the `detector_client`
campaign #6 tail, dispositioned by the construction probe
`/tmp/wp-b28/dc-equiv-probe.py` (bank tree, rc=0, positive control
`model_readiness_probe__mutmut_10` reddens; ledger row
"LEDGER CORRECTION (batch-29/dc)" in
docs/plans/2026-09-12-context-map-doc-updates.md, commit 6c46e5be):

* ``xǁDetectorClientǁ_send_detection_request__mutmut_331`` -
  ``e.response.text[:500]`` -> ``[:501]`` at shipped
  ``backend/services/detector_client.py:827``. Reachable ONLY through the
  400 arm with a JSON-unparseable body: ``e.response.json()`` must raise
  (L825's ``except`` -> the raw-text fallback) and
  ``e.response.text`` must be LONGER than 500 chars, else both slices agree.
  The probe's measured diff pair: shipped message len 527, mutant 528.
* ``xǁDetectorClientǁdetect_objects__mutmut_567`` -
  ``sanitize_error(e)`` -> ``sanitize_error(None)`` inside the
  ``DetectorUnavailableError`` f-string at shipped
  ``backend/services/detector_client.py:1441`` (the ``except
  (OSError, RuntimeError)`` arm at L1424-L1443). The probe reddened on BOTH
  error classes: shipped carried the sanitized sentence, mutant carried the
  literal ``None``.

The remaining 8 campaign survivors (`__init__` m20, `_send` m1,
`detect_objects` m198, readiness-probe m4/m7/m12/m14/m21) were dispositioned
EQUIVALENT by the same sweep (dead stores / truthiness-only reads /
byte-identical JPEG payloads on PIL 12.3.0) and are deliberately NOT
authored-for - a test cannot distinguish them by definition.

Fixtures are trimmed copies of the proven batch-28 dc08 battery idioms
(`test_detector_client_batch28_08.py`, md5 294c938abe9e37cd0f979f9357982753
era): a REAL ``DetectorClient`` over patched settings, an ``httpx.Response``
double in shipped shape, ``asyncio.sleep``/``asyncio.timeout`` neutralized so
legs cost no wall clock. All new patches use ``autospec=True`` or ``new=``
(WP4.2 ratchet).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.core.logging import sanitize_error
from backend.services.detector_client import DetectorClient, DetectorUnavailableError

pytestmark = pytest.mark.unit

_CAMERA_ID = "cam-batch29"
_IMAGE_PATH = "/var/lib/hsi/frames/frame-b29-0007.jpg"
_REQUEST = httpx.Request("POST", "http://detector.invalid:8000/detect")


def status_error(*, status, text, json_error):
    """Real ``httpx.HTTPStatusError`` whose response double answers ``.text``
    and raises from ``.json()`` - exactly the shape the shipped 400 fallback
    (L821-L827) reads."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status
    response.text = text
    response.json.side_effect = json_error
    return httpx.HTTPStatusError(f"HTTP {status}", request=_REQUEST, response=response)


class _PassThroughTimeout:
    def __init__(self, seconds):
        self.seconds = seconds

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


@pytest.fixture
def settings():
    """Settings as the shipped suite patches them; real floats keep the real
    ctor usable."""
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
def client(settings):
    instance = DetectorClient(max_retries=1)  # 400s raise without retry; legs stay short
    yield instance


@pytest.fixture
def no_clock():
    with (
        patch("asyncio.sleep", new_callable=AsyncMock) as sleeper,
        patch.object(asyncio, "timeout", new=lambda seconds: _PassThroughTimeout(seconds)),
    ):
        yield sleeper


# --------------------------------------------------------------------------- m331


async def _post_once(client, err):
    with patch.object(httpx.AsyncClient, "post", autospec=True, side_effect=err):
        return await client._send_detection_request(b"BYTES", "f.jpg", _CAMERA_ID, _IMAGE_PATH)


async def test_400_raw_text_fallback_is_truncated_at_exactly_500_chars(client, no_clock):
    """m331 kill pin: the raw-text fallback slices ``[:500]``, so a 600-char
    ``response.text`` yields a message of EXACTLY len 527
    (``len("Detector client error 400: ") == 27``). ``[:501]`` gives 528."""
    err = status_error(status=400, text="E" * 600, json_error=ValueError("no json here"))
    with pytest.raises(ValueError) as ei:
        await _post_once(client, err)
    msg = str(ei.value)
    assert msg == "Detector client error 400: " + "E" * 500, (
        f"raw-text fallback slice mutated (observed len {len(msg)}, shipped is 527)"
    )
    assert len(msg) == 527


async def test_400_raw_text_under_500_chars_survives_whole(client, no_clock):
    """Sibling bound: with 60 chars both shipped and any wider slice agree -
    this leg keeps the 500-pin honest (kills ``[:499]``-style twins too)."""
    err = status_error(status=400, text="E" * 60, json_error=ValueError("x"))
    with pytest.raises(ValueError) as ei:
        await _post_once(client, err)
    assert str(ei.value) == "Detector client error 400: " + "E" * 60


# --------------------------------------------------------------------------- m567


async def _detect_raising(client, exc, frame_path):
    async def boom(**kwargs):
        raise exc

    with (
        patch.object(
            client, "_validate_image_for_detection_async", new=AsyncMock(return_value=True)
        ),
        patch.object(client, "_send_detection_request", new=boom),
        patch(
            "backend.services.detector_client.get_inference_semaphore",
            new=lambda: asyncio.Semaphore(2),
        ),
    ):
        return await client.detect_objects(str(frame_path), _CAMERA_ID, MagicMock())


def _frame(tmp_path):
    """A real file on disk: ``detect_objects`` validates ``Path.exists()``
    (L1036) and reads the bytes through ``asyncio.to_thread`` (L1074) BEFORE
    the send leg, so both must see a real file - only the send is stubbed."""
    p = tmp_path / "frame-b29-0007.jpg"
    p.write_bytes(b"\xff\xd8\xff\xd9")  # JPEG SOI+EOI marker bytes
    return p


@pytest.mark.parametrize("exc", [RuntimeError, OSError], ids=["runtime", "oserror"])
async def test_unexpected_error_message_carries_the_sanitized_exception(
    client, no_clock, exc, tmp_path
):
    """m567 kill pin: the ``except (OSError, RuntimeError)`` arm interpolates
    ``sanitize_error(e)`` - the shipped text, NOT the literal ``None`` the
    mutant produces (probe diff: ``"...detection: IO boom .../tok=hunter2"``
    vs ``"...detection: None"``)."""
    err = exc("IO boom /opt/secrets/tok=hunter2")
    with pytest.raises(DetectorUnavailableError) as ei:
        await _detect_raising(client, err, _frame(tmp_path))
    msg = str(ei.value)
    assert msg == f"Unexpected error during object detection: {sanitize_error(err)}"
    assert "detection: None" not in msg
    assert ei.value.original_error is err


async def test_unexpected_error_message_sanitizes_paths(client, no_clock, tmp_path):
    """Same arm with an OSError and a path-bearing message: the shipped
    sanitizer keeps only the filename - the mutant still says ``None``."""
    err = OSError("read fail /var/lib/app/camera.jpg")
    with pytest.raises(DetectorUnavailableError) as ei:
        await _detect_raising(client, err, _frame(tmp_path))
    assert str(ei.value) == "Unexpected error during object detection: read fail .../camera.jpg"
