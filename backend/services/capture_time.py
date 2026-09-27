"""Capture time from Foscam upload filenames (synthbench spec §5.3, D10).

Foscam cameras name each upload after the moment they captured it, on the
camera's LOCAL clock:

    snap/MDAlarm_20260911-123100.jpg     motion-alarm still
    snap/HMDAlarm_20260616-134454.jpg    human-motion-alarm still
    record/MDalarm_20260728_111148.mkv   alarm clip (underscore, lowercase 'a')

Probed on the owner's footage 2026-09-27: every file's mtime is its filename
time + 4 h (America/New_York, EDT) + 2-4 s of upload lag. The filename is
local wall time, so parsing needs the camera timezone (CAMERA_TIMEZONE).

Scope (settled by the P0 plan): capture time feeds ONLY the VLM's time
context - the AssessInput snapshot timestamp and the prompt's Time line.
`Detection.detected_at` stays arrival time, because retention, the orphan
sweep, re-ID recency and the context windows all compare it with "now".
With CAMERA_TIMEZONE unset, nothing here changes behavior.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import PurePath
from zoneinfo import ZoneInfo

from backend.core.logging import get_logger

logger = get_logger(__name__)

# A camera clock may run a little ahead of the server's. Beyond this, the
# filename time is a wrong timezone or clock, not a capture.
MAX_FUTURE_SKEW = timedelta(minutes=5)

_FOSCAM_NAME = re.compile(r"^h?mdalarm_(\d{8})[-_](\d{6})", re.IGNORECASE)


def camera_tz(name: str | None) -> ZoneInfo | None:
    """The configured camera timezone, or None when unset (parsing off)."""
    return ZoneInfo(name) if name else None


def parse_capture_time(file_path: str | None, tz: tzinfo) -> datetime | None:
    """UTC capture time from a Foscam filename, or None if the name is not one.

    An ambiguous local time (the repeated hour when DST ends) resolves to its
    first occurrence (fold=0)."""
    if not file_path:
        return None
    match = _FOSCAM_NAME.match(PurePath(file_path).name)
    if match is None:
        return None
    try:
        local = datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return local.replace(tzinfo=tz).astimezone(UTC)


def resolve_capture_time(
    file_path: str | None, *, detected_at: datetime, tz: tzinfo | None
) -> datetime:
    """The filename's capture time when it yields a plausible one, else detected_at.

    `detected_at` must be timezone-aware (the ORM column is timestamptz): the
    skew check compares it with the aware UTC filename time, so a naive value
    raises TypeError whenever a filename parses."""
    if tz is None:
        return detected_at
    captured = parse_capture_time(file_path, tz)
    if captured is None:
        return detected_at
    if captured > detected_at + MAX_FUTURE_SKEW:
        logger.warning(
            "Foscam filename time is after arrival; check CAMERA_TIMEZONE and the camera clock",
            extra={
                "file_path": file_path,
                "captured_at": captured.isoformat(),
                "detected_at": detected_at.isoformat(),
            },
        )
        return detected_at
    return captured


def render_prompt_time(timestamp: str, tz_name: str | None) -> str:
    """The prompt's Time value: local wall time with zone and UTC offset when a
    camera timezone is configured; otherwise, or for anything that is not an
    aware ISO timestamp, the stored string unchanged."""
    tz = camera_tz(tz_name)
    if tz is None:
        return timestamp
    try:
        moment = datetime.fromisoformat(timestamp)
    except ValueError:
        return timestamp
    if moment.tzinfo is None:
        return timestamp
    local = moment.astimezone(tz)
    offset = local.strftime("%z")  # e.g. "-0400"
    return f"{local:%Y-%m-%d %H:%M:%S} local ({tz_name}, UTC{offset[:3]}:{offset[3:]})"
