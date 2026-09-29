"""S2 batch-28 lane L1 / group dc05 — image validation.

Family probed (all pinned at the CURRENT source of
``backend/services/detector_client.py`` md5 ``294c938abe9e37cd0f979f9357982753``;
production never bends to these tests — every expected value below is transcribed
from the shipped line it defends):

``L105``       ``MIN_DETECTION_IMAGE_SIZE = 10 * 1024`` — the truncation threshold.
``L921-976``   ``_validate_image_for_detection()`` — the size gate (L943), the
               "Image too small for detection" warning (L944-951), the load step
               (L955-957), the ``OSError`` arm (L961-969) and the
               ``ValueError``/``RuntimeError`` arm (L970-976).
``L978-991``   ``_validate_image_for_detection_async()`` — the ``asyncio.to_thread``
               forward of ``(image_path, camera_id)``.

Every stimulus here is a REAL file under ``tmp_path`` (a small JPEG, a JPEG padded
to EXACTLY ``MIN_DETECTION_IMAGE_SIZE``, a truncated JPEG, a path that does not
exist, a path carrying an embedded NUL) plus one loader stand-in injected with
``new=`` — no assertion is steered by a mock return value.

The exactly-MIN-size case is what makes the ``LessThan -> LessThanEqual`` mutant on
L943 observable: the shipped gate is strict, so a file of exactly 10240 bytes is
VALID and emits no warning, while the mutant rejects it.

Occurrence twins: the ``"camera_id"`` / ``"file_path"`` extra-key renames match
THREE sites in this method (L947/L948 in the size gate, L967 in the ``OSError`` arm,
L974 in the ``ValueError`` arm), so all three arms are driven and read here —
whichever site the bank's mutant sits on, a named test reddens.

The two error fields are pinned differently, exactly as the shipped lines differ:
the ``OSError`` arm logs ``"error": str(e)`` (L967) and the second arm logs
``"error": sanitize_error(e)`` (L974). The first is compared against the text of
the same exception produced by the same shipped steps (so a full path must survive),
the second against a literal whose path has been shortened to ``.../<filename>``
(so a ``str()`` substitution cannot pass either).

Windows: ``caplog.set_level`` does NOT clear the buffer (the historical CI-flake
family), so every test opens its window with ``set_level`` + ``clear()`` and filters
records to this module's logger name.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from backend.services import detector_client as M

LOG_NAME = M.logger.name
pytestmark = [pytest.mark.unit]

# Settings values ``__init__`` reads (L280-330); nothing in this group depends on
# them, they only have to be real so the client constructs normally.
YOLO26_URL = "http://yolo26-test:8000"
API_KEY = "sk-dc05-test-key"  # pragma: allowlist secret  # nosemgrep: hardcoded-password

CAMERA_ID = "cam-dc05"


# =============================================================================
# Builders / stimulus
# =============================================================================


def build_client(monkeypatch: pytest.MonkeyPatch) -> Any:
    """A pristine-shaped ``DetectorClient``: settings are mocked at the module
    attribute the shipped code resolves (``get_settings``)."""
    settings = MagicMock()
    settings.yolo26_url = YOLO26_URL
    settings.yolo26_api_key = API_KEY
    settings.yolo26_read_timeout = 42.0
    settings.ai_connect_timeout = 3.5
    settings.ai_health_timeout = 7.0
    settings.ai_max_concurrent_inferences = 3
    settings.__dict__["use_ai_gateway"] = False
    settings.__dict__["ai_gateway_url"] = None
    monkeypatch.setattr(M, "get_settings", lambda: settings)
    return M.DetectorClient(max_retries=1)


def write_jpeg(path: Path, *, size: tuple[int, int] = (64, 48), pad_to: int | None = None) -> int:
    """Write a REAL decodable JPEG and return its final size.

    ``pad_to`` appends NUL bytes after the JPEG trailer: PIL still decodes the
    image (measured), which is what lets a file sit EXACTLY on the 10240-byte
    threshold instead of straddling it.
    """
    Image.new("RGB", size, color="red").save(path, "JPEG", quality=50)
    if pad_to is not None:
        raw = path.read_bytes()
        assert len(raw) <= pad_to, f"cannot pad {len(raw)} bytes up to {pad_to}"
        path.write_bytes(raw + b"\x00" * (pad_to - len(raw)))
    return path.stat().st_size


def write_truncated_jpeg(path: Path) -> int:
    """Write a JPEG cut short mid-scan: large enough to pass the size gate, and
    ``img.load()`` raises ``OSError`` on it (the shipped truncation case)."""
    img = Image.new("RGB", (800, 600))
    for x in range(0, 800, 7):
        for y in range(0, 600, 11):
            img.putpixel((x, y), ((x * 3) % 256, (y * 5) % 256, (x * y) % 256))
    img.save(path, "JPEG", quality=90)
    raw = path.read_bytes()
    path.write_bytes(raw[: int(len(raw) * 0.6)])
    size = path.stat().st_size
    assert size > M.MIN_DETECTION_IMAGE_SIZE, "truncated file must clear the size gate"
    return size


class FailingLoader:
    """Injected with ``new=`` in place of the module-level ``Image`` name: every
    ``open`` call raises, which is how the second ``except`` arm is driven from
    the load step (L955-957) rather than from ``stat()``."""

    def __init__(self, error: BaseException) -> None:
        self._error = error

    def open(self, image_path: Any) -> Any:
        raise self._error


def shipped_error_text(image_path: str) -> str:
    """``str()`` of the ``OSError`` the shipped steps raise for this path.

    L967 logs ``"error": str(e)``, so the expected value is the text of the same
    exception, produced here by the same two steps the shipped method performs
    (``Path(...).stat().st_size`` then ``Image.open(...)`` + ``load()``) rather
    than by a transcribed literal — those messages carry the errno and the path.
    """
    try:
        # The two steps of L942 and L955-957, in order, so the errno and the path
        # in the message are produced the same way the shipped code produces them.
        Path(image_path).stat()
        with Image.open(image_path) as img:
            img.load()
    except OSError as exc:
        return str(exc)
    raise AssertionError(f"{image_path!r} was expected to raise OSError, it did not")


# =============================================================================
# Observation helpers
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer."""
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def warnings_from_module(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME and r.levelno == logging.WARNING]


# Closed world of keys this method ever routes through extra=.
EXTRA_KEYS = ("camera_id", "file_path", "file_size", "min_size", "error")


def one_warning(caplog: pytest.LogCaptureFixture, *, msg: str) -> logging.LogRecord:
    """Exactly one WARNING from this module in the window, with this raw msg."""
    records = warnings_from_module(caplog)
    assert len(records) == 1, f"expected 1 WARNING, got {[(r.msg) for r in records]!r}"
    record = records[0]
    assert record.msg == msg, f"log text mutated: {record.msg!r} != {msg!r}"
    assert record.levelno == logging.WARNING
    assert tuple(record.args or ()) == (), "this shipped call passes no lazy args"
    assert record.exc_info is None, "this shipped call passes no exc_info"
    return record


def extras_of(record: logging.LogRecord, *, expected: tuple[str, ...]) -> dict[str, Any]:
    """The extra= keys actually present on the record, compared as a CLOSED set so
    ``extra=None``, a dropped ``extra=`` and a renamed key all fail."""
    present = {k for k in EXTRA_KEYS if hasattr(record, k)}
    assert present == set(expected), f"extra= keys mutated: {sorted(present)} != {sorted(expected)}"
    return {k: getattr(record, k) for k in expected}


# =============================================================================
# L943-951 — the size gate and its warning
# =============================================================================


def test_small_image_is_rejected_with_the_shipped_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """L943-951: a valid-but-tiny JPEG returns False and emits the size warning
    with all four extra keys carrying the shipped values."""
    client = build_client(monkeypatch)
    path = tmp_path / "small.jpeg"
    file_size = write_jpeg(path)
    assert file_size < M.MIN_DETECTION_IMAGE_SIZE

    win(caplog)
    assert client._validate_image_for_detection(str(path), CAMERA_ID) is False

    record = one_warning(caplog, msg="Image too small for detection")
    assert extras_of(record, expected=("camera_id", "file_path", "file_size", "min_size")) == {
        "camera_id": CAMERA_ID,
        "file_path": str(path),
        "file_size": file_size,
        "min_size": M.MIN_DETECTION_IMAGE_SIZE,
    }


def test_exactly_minimum_size_image_is_accepted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """L943 pins the gate as STRICT: a decodable file of exactly
    ``MIN_DETECTION_IMAGE_SIZE`` bytes is valid and logs nothing. A
    ``LessThanEqual`` gate would reject it."""
    client = build_client(monkeypatch)
    path = tmp_path / "exact.jpeg"
    assert write_jpeg(path, pad_to=M.MIN_DETECTION_IMAGE_SIZE) == M.MIN_DETECTION_IMAGE_SIZE

    win(caplog)
    assert client._validate_image_for_detection(str(path), CAMERA_ID) is True

    assert warnings_from_module(caplog) == []


def test_above_minimum_size_image_is_accepted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The other side of the gate: one byte over the threshold is valid too."""
    client = build_client(monkeypatch)
    path = tmp_path / "above.jpeg"
    assert write_jpeg(path, pad_to=M.MIN_DETECTION_IMAGE_SIZE + 1) == M.MIN_DETECTION_IMAGE_SIZE + 1

    win(caplog)
    assert client._validate_image_for_detection(str(path), CAMERA_ID) is True

    assert warnings_from_module(caplog) == []


def test_min_detection_image_size_constant_is_ten_kib() -> None:
    """L105: the threshold the gate compares against is ``10 * 1024``."""
    assert M.MIN_DETECTION_IMAGE_SIZE == 10 * 1024


# =============================================================================
# L961-969 — the OSError arm
# =============================================================================


def test_missing_file_takes_the_corrupt_truncated_arm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """L942 -> L961-969: a path that cannot be stat'd lands in the ``OSError`` arm,
    whose warning carries ``str(e)`` (full path and all) plus camera_id/file_path."""
    client = build_client(monkeypatch)
    path = tmp_path / "absent.jpeg"
    assert not path.exists()

    win(caplog)
    assert client._validate_image_for_detection(str(path), CAMERA_ID) is False

    record = one_warning(caplog, msg="Image validation failed (corrupt/truncated)")
    assert extras_of(record, expected=("camera_id", "file_path", "error")) == {
        "camera_id": CAMERA_ID,
        "file_path": str(path),
        "error": shipped_error_text(str(path)),
    }


def test_truncated_jpeg_takes_the_corrupt_truncated_arm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """L955-957 -> L961-969: a JPEG cut mid-scan clears the size gate, fails
    ``load()`` with ``OSError`` and lands in the same arm."""
    client = build_client(monkeypatch)
    path = tmp_path / "truncated.jpeg"
    write_truncated_jpeg(path)

    win(caplog)
    assert client._validate_image_for_detection(str(path), CAMERA_ID) is False

    record = one_warning(caplog, msg="Image validation failed (corrupt/truncated)")
    assert extras_of(record, expected=("camera_id", "file_path", "error")) == {
        "camera_id": CAMERA_ID,
        "file_path": str(path),
        "error": shipped_error_text(str(path)),
    }


# =============================================================================
# L970-976 — the ValueError / RuntimeError arm
# =============================================================================


def test_value_error_from_the_loader_takes_the_second_arm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """L955 -> L970-976: a ``ValueError`` out of the loader emits the SHORTER
    warning, and its ``error`` is the SANITIZED text — the shipped line calls
    ``sanitize_error(e)``, which collapses the path to ``.../<filename>``. A plain
    ``str(e)`` substitution would leak the full path and fail here."""
    client = build_client(monkeypatch)
    path = tmp_path / "value-error.jpeg"
    write_jpeg(path, pad_to=M.MIN_DETECTION_IMAGE_SIZE)
    loader = FailingLoader(ValueError("decoder rejected /var/lib/frames/value-error.jpeg"))

    win(caplog)
    with patch("backend.services.detector_client.Image", new=loader):
        assert client._validate_image_for_detection(str(path), CAMERA_ID) is False

    record = one_warning(caplog, msg="Image validation failed")
    assert extras_of(record, expected=("camera_id", "file_path", "error")) == {
        "camera_id": CAMERA_ID,
        "file_path": str(path),
        "error": "decoder rejected .../value-error.jpeg",
    }


def test_runtime_error_from_the_loader_takes_the_second_arm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """L970: ``RuntimeError`` (decoder issues) shares the arm and its warning."""
    client = build_client(monkeypatch)
    path = tmp_path / "runtime-error.jpeg"
    write_jpeg(path, pad_to=M.MIN_DETECTION_IMAGE_SIZE)
    loader = FailingLoader(RuntimeError("decoder died mid-frame"))

    win(caplog)
    with patch("backend.services.detector_client.Image", new=loader):
        assert client._validate_image_for_detection(str(path), CAMERA_ID) is False

    record = one_warning(caplog, msg="Image validation failed")
    assert extras_of(record, expected=("camera_id", "file_path", "error")) == {
        "camera_id": CAMERA_ID,
        "file_path": str(path),
        "error": "decoder died mid-frame",
    }


def test_path_with_an_embedded_nul_takes_the_second_arm_without_any_mock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Mock-free stimulus for the same arm: ``stat()`` itself raises
    ``ValueError`` (not an ``OSError``), so the shipped code skips the corrupt arm
    and logs the short warning with camera_id / file_path intact."""
    client = build_client(monkeypatch)
    image_path = str(tmp_path / "nul\x00embedded.jpeg")

    win(caplog)
    assert client._validate_image_for_detection(image_path, CAMERA_ID) is False

    record = one_warning(caplog, msg="Image validation failed")
    assert extras_of(record, expected=("camera_id", "file_path", "error")) == {
        "camera_id": CAMERA_ID,
        "file_path": image_path,
        "error": "stat: embedded null character in path",
    }


# =============================================================================
# L978-991 — the async wrapper
# =============================================================================


@pytest.mark.asyncio
async def test_async_wrapper_forwards_the_camera_id_it_was_given(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """L991: the wrapper threads BOTH arguments through — the bool is the sync
    validator's and the warning record still carries the passed ``camera_id``
    (an ``arg->None`` here would thread ``None`` and the record would lose the
    camera the operator greps for)."""
    client = build_client(monkeypatch)
    path = tmp_path / "small-async.jpeg"
    file_size = write_jpeg(path)

    win(caplog)
    result = await client._validate_image_for_detection_async(str(path), CAMERA_ID)

    assert result is False
    record = one_warning(caplog, msg="Image too small for detection")
    assert extras_of(record, expected=("camera_id", "file_path", "file_size", "min_size")) == {
        "camera_id": CAMERA_ID,
        "file_path": str(path),
        "file_size": file_size,
        "min_size": M.MIN_DETECTION_IMAGE_SIZE,
    }


@pytest.mark.asyncio
async def test_async_wrapper_agrees_with_the_sync_validator(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """L991: for a valid file the async path returns the sync path's True and logs
    nothing, so the wrapper adds no behaviour of its own."""
    client = build_client(monkeypatch)
    path = tmp_path / "exact-async.jpeg"
    write_jpeg(path, pad_to=M.MIN_DETECTION_IMAGE_SIZE)

    win(caplog)
    async_result = await client._validate_image_for_detection_async(str(path), CAMERA_ID)
    sync_result = client._validate_image_for_detection(str(path), CAMERA_ID)

    assert async_result is True
    assert async_result == sync_result
    assert warnings_from_module(caplog) == []
