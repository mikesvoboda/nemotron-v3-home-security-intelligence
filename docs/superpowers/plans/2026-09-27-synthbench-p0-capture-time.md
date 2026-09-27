# Synthbench P0 — Capture Time from Foscam Filenames — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `CAMERA_TIMEZONE` is set, the VLM sees the moment a Foscam camera _captured_ an
image (parsed from the upload's filename) as local time, instead of the moment the backend
processed it.

**Architecture:** A new pure module, `backend/services/capture_time.py`, parses Foscam filenames
in the configured camera timezone and renders prompt times. The VLM analyzer's pure snapshot
builder (`build_assess_context`) uses it to set `AssessInput.timestamp`, and `VlmClient` renders
the prompt's `Time:` line in local time. `Detection.detected_at` is **not** changed and no
schema changes: every detection already stores its `file_path`, so capture time is derived at
snapshot time.

**Tech Stack:** Python 3.14, stdlib `zoneinfo` and `re`, pydantic-settings, pytest (asyncio
auto mode).

**Spec:** `docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md` (§5.3,
D10). Read §5.3 before starting.

## Global Constraints

- Type hints on every function; `mypy` clean; `ruff check` + `ruff format` clean; line length 100.
- TDD: every behavior change starts with a failing test that you run and watch fail.
- **No schema changes.** This repo is `create_all`-only (Alembic removed in #4465;
  `backend/models/event_verification.py:18-22`); `create_all` never alters an existing table.
- **`Detection.detected_at` keeps meaning arrival time.** Retention (`cleanup_service.py:284`), the
  orphan sweep (`batch_aggregator.py:1534`), re-ID recency (`reid_matcher.py:167`), the context
  window (`context_enricher.py:533`) and metrics counts all compare it with "now".
- **Unset `CAMERA_TIMEZONE` = today's behavior, byte for byte** (timestamp = earliest
  `detected_at`; prompt shows the UTC ISO string).
- **The `vlm_assess` contract does not change.** `AssessInput` / `VlmAssessContext` field sets stay
  identical; `uv run python scripts/gen-ai-contract.py --check` must pass unchanged.
- Foscam filename patterns (probed on the owner's footage, 2026-09-27):
  `MDAlarm_YYYYMMDD-HHMMSS.jpg`, `HMDAlarm_YYYYMMDD-HHMMSS.jpg` (stills, `snap/`) and
  `MDalarm_YYYYMMDD_HHMMSS.mkv` (clips, `record/`). The time is the camera's **local** clock
  (file mtime = filename time + 4 h in EDT + 2-4 s upload lag).
- A filename time more than **5 minutes after** `detected_at` is a timezone or clock error: fall
  back to `detected_at` and log a warning naming `CAMERA_TIMEZONE`.
- Commits: conventional-commit subject; end every message with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never `--no-verify`. Git hooks are
  not installed in this checkout (`.git/hooks/` is empty), so run
  `uvx pre-commit run --files <changed files>` before each commit and re-stage whatever it fixes.

## Out of Scope (deliberate)

- Event `started_at` / `ended_at` stay arrival time (`vlm_analyzer.py:509-513`). Moving them is a
  follow-up: alerting and cooldown code compares event times with "now".
- Batch windows, retention, the frame buffer (`detector_client.py:1099`) and every
  now-relative query keep wall-clock time.
- Per-camera timezones (one setting covers the deployment).
- The legacy `nemotron_analyzer.py` path (unsupported since VSS rev 5) and the dormant
  `backend/evaluation/control_freeze.py`.

## File Structure

| File                                                                         | Change | Responsibility                                                                 |
| ---------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------ |
| `backend/services/capture_time.py`                                           | Create | Pure: parse a Foscam name → UTC, resolve against arrival, render a prompt time |
| `backend/tests/unit/services/test_capture_time.py`                           | Create | Unit tests for the module                                                      |
| `backend/core/config.py`                                                     | Modify | `camera_timezone` setting + validator                                          |
| `backend/tests/unit/core/test_config.py`                                     | Modify | Setting tests; add `CAMERA_TIMEZONE` to `clean_env`                            |
| `backend/services/vlm_analyzer.py`                                           | Modify | `build_assess_context(capture_tz=…)`; call site passes the configured zone     |
| `backend/tests/unit/services/test_vlm_analyzer.py`                           | Modify | Snapshot timestamp tests + one end-to-end `analyze_batch` test                 |
| `backend/services/vlm_client.py`                                             | Modify | `Time:` line rendered via `render_prompt_time`                                 |
| `backend/tests/unit/services/test_vlm_client.py`                             | Modify | Prompt `Time:` line tests                                                      |
| `.env.example`, `docs/reference/config/env-reference.md`                     | Modify | Document `CAMERA_TIMEZONE`                                                     |
| `backend/services/AGENTS.md`, `backend/evaluation/assess_input.py`           | Modify | Index the module; document the timestamp's meaning                             |
| `docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md` | Modify | Record the settled P0 scope (§5.3) and the runner's filename rule              |

---

### Task 1: `capture_time` module (parse, resolve, render)

**Files:**

- Create: `backend/services/capture_time.py`
- Test: `backend/tests/unit/services/test_capture_time.py`

**Interfaces:**

- Consumes: `backend.core.logging.get_logger` (returns a stdlib `logging.Logger`).
- Produces (all pure, used by Tasks 3 and 4):

  - `MAX_FUTURE_SKEW: timedelta` (5 minutes)
  - `camera_tz(name: str | None) -> ZoneInfo | None`
  - `parse_capture_time(file_path: str | None, tz: tzinfo) -> datetime | None` (aware, UTC)
  - `resolve_capture_time(file_path: str | None, *, detected_at: datetime, tz: tzinfo | None) -> datetime`
  - `render_prompt_time(timestamp: str, tz_name: str | None) -> str`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/services/test_capture_time.py`:

```python
"""capture_time: Foscam filename -> capture moment (synthbench spec §5.3, D10)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from backend.services import capture_time as ct

NY = ZoneInfo("America/New_York")
ARRIVAL = datetime(2026, 9, 25, 15, 0, 0, tzinfo=UTC)  # 11:00 EDT


class TestParseCaptureTime:
    @pytest.mark.parametrize(
        ("file_path", "expected"),
        [
            # motion-alarm still: hyphen separator; EDT is UTC-4
            (
                "/export/foscam/front/FoscamCamera_00626EFE8B21/snap/MDAlarm_20260925-021400.jpg",
                datetime(2026, 9, 25, 6, 14, 0, tzinfo=UTC),
            ),
            # human-motion-alarm still
            ("HMDAlarm_20260925-021400.jpg", datetime(2026, 9, 25, 6, 14, 0, tzinfo=UTC)),
            # alarm clip: underscore separator, lowercase 'a'
            ("record/MDalarm_20260925_021400.mkv", datetime(2026, 9, 25, 6, 14, 0, tzinfo=UTC)),
            # winter: EST is UTC-5
            ("MDAlarm_20260115-021400.jpg", datetime(2026, 1, 15, 7, 14, 0, tzinfo=UTC)),
        ],
    )
    def test_foscam_names_parse_as_camera_local_time(
        self, file_path: str, expected: datetime
    ) -> None:
        assert ct.parse_capture_time(file_path, NY) == expected

    @pytest.mark.parametrize(
        "file_path",
        [
            None,
            "",
            "/media/front_door/det_7.jpg",
            "frame_0001.jpg",
            "MDAlarm_20261399-021400.jpg",  # month 13, day 99
            "MDAlarm_2026092-021400.jpg",  # seven-digit date
            "prefix_MDAlarm_20260925-021400.jpg",  # pattern not at the start of the name
        ],
    )
    def test_other_names_do_not_parse(self, file_path: str | None) -> None:
        assert ct.parse_capture_time(file_path, NY) is None

    def test_ambiguous_dst_hour_takes_the_first_occurrence(self) -> None:
        # 2026-11-01 01:30 happens twice in New York; fold=0 is the EDT one.
        assert ct.parse_capture_time("MDAlarm_20261101-013000.jpg", NY) == datetime(
            2026, 11, 1, 5, 30, 0, tzinfo=UTC
        )


class TestResolveCaptureTime:
    NAME = "MDAlarm_20260925-021400.jpg"  # 06:14 UTC; arrival is 15:00 UTC

    def test_no_timezone_keeps_arrival(self) -> None:
        assert ct.resolve_capture_time(self.NAME, detected_at=ARRIVAL, tz=None) == ARRIVAL

    def test_a_parsed_past_capture_wins(self) -> None:
        assert ct.resolve_capture_time(self.NAME, detected_at=ARRIVAL, tz=NY) == datetime(
            2026, 9, 25, 6, 14, 0, tzinfo=UTC
        )

    def test_an_unparsed_name_keeps_arrival(self) -> None:
        assert ct.resolve_capture_time("det_7.jpg", detected_at=ARRIVAL, tz=NY) == ARRIVAL

    def test_a_camera_clock_slightly_ahead_is_accepted(self) -> None:
        # 11:03 EDT = 15:03 UTC: three minutes after arrival, inside MAX_FUTURE_SKEW
        got = ct.resolve_capture_time("MDAlarm_20260925-110300.jpg", detected_at=ARRIVAL, tz=NY)
        assert got == ARRIVAL + timedelta(minutes=3)

    def test_a_capture_far_after_arrival_is_rejected_and_warned(self, monkeypatch) -> None:
        warn = MagicMock()
        monkeypatch.setattr(ct.logger, "warning", warn)
        # 23:00 EDT = 03:00 UTC next day: a wrong zone or clock, not a capture
        got = ct.resolve_capture_time("MDAlarm_20260925-230000.jpg", detected_at=ARRIVAL, tz=NY)
        assert got == ARRIVAL
        warn.assert_called_once()
        assert "CAMERA_TIMEZONE" in warn.call_args.args[0]


class TestRenderPromptTime:
    TS = "2026-09-25T12:00:00+00:00"

    def test_unset_zone_returns_the_stored_iso(self) -> None:
        assert ct.render_prompt_time(self.TS, None) == self.TS

    def test_local_time_with_zone_and_offset(self) -> None:
        assert ct.render_prompt_time(self.TS, "America/New_York") == (
            "2026-09-25 08:00:00 local (America/New_York, UTC-04:00)"
        )

    def test_winter_offset(self) -> None:
        assert ct.render_prompt_time("2026-01-15T12:00:00+00:00", "America/New_York") == (
            "2026-01-15 07:00:00 local (America/New_York, UTC-05:00)"
        )

    def test_half_hour_zone(self) -> None:
        assert ct.render_prompt_time(self.TS, "Asia/Kolkata") == (
            "2026-09-25 17:30:00 local (Asia/Kolkata, UTC+05:30)"
        )

    @pytest.mark.parametrize("ts", ["2026-09-25T12:00:00", "not a time", ""])
    def test_naive_or_unparseable_values_pass_through(self, ts: str) -> None:
        assert ct.render_prompt_time(ts, "America/New_York") == ts


class TestCameraTz:
    def test_none_and_empty_mean_off(self) -> None:
        assert ct.camera_tz(None) is None
        assert ct.camera_tz("") is None

    def test_a_name_resolves(self) -> None:
        assert ct.camera_tz("America/New_York") == NY
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/services/test_capture_time.py -n0 -q`
Expected: collection error, `ModuleNotFoundError: No module named 'backend.services.capture_time'`.

- [ ] **Step 3: Write the module**

Create `backend/services/capture_time.py`:

```python
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
    """The filename's capture time when it yields a plausible one, else detected_at."""
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/services/test_capture_time.py -n0 -q`
Expected: all 26 cases pass.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check --fix backend/services/capture_time.py backend/tests/unit/services/test_capture_time.py
uv run ruff format backend/services/capture_time.py backend/tests/unit/services/test_capture_time.py
uv run mypy backend/services/capture_time.py
uvx pre-commit run --files backend/services/capture_time.py backend/tests/unit/services/test_capture_time.py
git add backend/services/capture_time.py backend/tests/unit/services/test_capture_time.py
git commit -m "feat(vlm): parse capture time from Foscam upload filenames

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `CAMERA_TIMEZONE` setting

**Files:**

- Modify: `backend/core/config.py` (imports near line 12-19; new field directly after
  `batch_idle_timeout_seconds`, which starts at line 936)
- Modify: `.env.example` (CAMERA INTEGRATION block, after `FOSCAM_BASE_PATH=/export/foscam`,
  line 644)
- Modify: `docs/reference/config/env-reference.md` (Camera Integration table, line 235)
- Test: `backend/tests/unit/core/test_config.py`

**Interfaces:**

- Produces: `Settings.camera_timezone: str | None` — `None` when unset or empty; otherwise a
  name `zoneinfo.ZoneInfo` accepts. Tasks 3 and 4 read it.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/unit/core/test_config.py`, add `"CAMERA_TIMEZONE",` to the `env_vars` list
inside the `clean_env` fixture (next to `"FOSCAM_BASE_PATH",`). Then append:

```python
class TestCameraTimezone:
    """CAMERA_TIMEZONE (synthbench P0): the cameras' clock zone, for filename capture time."""

    def test_default_is_unset(self) -> None:
        # Pydantic Settings still reads .env after delenv (see clean_env), so
        # pin the declared default rather than a constructed instance.
        assert Settings.model_fields["camera_timezone"].default is None

    def test_accepts_an_iana_zone(self, clean_env, monkeypatch) -> None:
        monkeypatch.setenv("CAMERA_TIMEZONE", "America/New_York")
        assert Settings().camera_timezone == "America/New_York"

    def test_empty_means_unset(self, clean_env, monkeypatch) -> None:
        monkeypatch.setenv("CAMERA_TIMEZONE", "")
        assert Settings().camera_timezone is None

    def test_rejects_an_unknown_zone(self, clean_env, monkeypatch) -> None:
        monkeypatch.setenv("CAMERA_TIMEZONE", "Mars/Olympus_Mons")
        with pytest.raises(ValidationError, match="camera_timezone"):
            Settings()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/core/test_config.py::TestCameraTimezone -n0 -q`
Expected: FAIL — `KeyError: 'camera_timezone'` and `AttributeError: 'Settings' object has no attribute 'camera_timezone'`.

- [ ] **Step 3: Add the field and validator**

In `backend/core/config.py`, add to the imports (after `import sys`, keeping stdlib imports
grouped):

```python
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
```

Directly after the `batch_idle_timeout_seconds` field, add:

```python
    # Camera clock timezone (synthbench P0, spec §5.3). Foscam cameras name
    # uploads by LOCAL capture time; with this set, the VLM's time context
    # comes from the filename instead of processing time. Unset keeps
    # arrival time rendered as UTC ISO - today's behavior.
    camera_timezone: str | None = Field(
        default=None,
        description="IANA timezone of the cameras' clocks (e.g. America/New_York). "
        "When set, the VLM's time context uses the capture time in Foscam upload "
        "filenames and shows it as local time. Unset keeps arrival time.",
    )

    @field_validator("camera_timezone")
    @classmethod
    def _validate_camera_timezone(cls, v: str | None) -> str | None:
        if not v:
            return None
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"camera_timezone {v!r} is not an IANA timezone name") from e
        return v
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/core/test_config.py -n0 -q`
Expected: PASS (the whole file, so the `clean_env` edit breaks nothing).

- [ ] **Step 5: Document the variable**

In `.env.example`, after the `FOSCAM_BASE_PATH=/export/foscam` line, add:

```bash

# Timezone of the cameras' clocks (IANA name, e.g. America/New_York).
# Foscam names uploads by LOCAL capture time (MDAlarm_YYYYMMDD-HHMMSS.jpg).
# When set, the VLM sees that capture time, shown as local time, instead of
# the time the backend processed the file. Leave unset to keep processing time.
# CAMERA_TIMEZONE=America/New_York
```

In `docs/reference/config/env-reference.md`, replace the Camera Integration table with:

```markdown
| Variable           | Required | Default          | Description                                                                                                  |
| ------------------ | -------- | ---------------- | ------------------------------------------------------------------------------------------------------------ |
| `FOSCAM_BASE_PATH` | No       | `/export/foscam` | Base directory for camera uploads                                                                            |
| `CAMERA_TIMEZONE`  | No       | unset            | IANA timezone of the cameras' clocks; when set, the VLM's time context uses the Foscam filename capture time |
```

- [ ] **Step 6: Lint, type-check, commit**

```bash
uv run ruff check --fix backend/core/config.py backend/tests/unit/core/test_config.py
uv run ruff format backend/core/config.py backend/tests/unit/core/test_config.py
uv run mypy backend/core/config.py
uvx pre-commit run --files backend/core/config.py backend/tests/unit/core/test_config.py .env.example docs/reference/config/env-reference.md
git add backend/core/config.py backend/tests/unit/core/test_config.py .env.example docs/reference/config/env-reference.md
git commit -m "feat(config): CAMERA_TIMEZONE for Foscam filename capture time

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The VLM snapshot's timestamp is the capture time

**Files:**

- Modify: `backend/services/vlm_analyzer.py` (imports at lines 49-78; `build_assess_context` at
  lines 101-153; call site at line 517; event times at lines 509-516)
- Test: `backend/tests/unit/services/test_vlm_analyzer.py` (class `TestBuildAssessContext`, and a
  new class after it)

**Interfaces:**

- Consumes: `camera_tz`, `resolve_capture_time` (Task 1); `Settings.camera_timezone` (Task 2).
- Produces: `build_assess_context(*, camera_id, detections, zones=None, household=None,
zone_crossing=False, specialist_outputs=None, capture_tz: tzinfo | None = None) -> VlmAssessContext`.
  With `capture_tz=None` the result is identical to today's.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/unit/services/test_vlm_analyzer.py`, add to the imports:

```python
from zoneinfo import ZoneInfo
```

Append these methods to `class TestBuildAssessContext`:

```python
    FOSCAM = "/export/foscam/front_door/FoscamCamera_X/snap/MDAlarm_20260925-{}.jpg"
    ARRIVAL = datetime(2026, 9, 25, 15, 0, 0, tzinfo=UTC)  # 11:00 EDT

    def test_capture_tz_takes_the_timestamp_from_the_foscam_filename(self):
        row = make_detection_row(
            7, detected_at=self.ARRIVAL, file_path=self.FOSCAM.format("021400")
        )
        ctx = va.build_assess_context(
            camera_id="front_door", detections=[row], capture_tz=ZoneInfo("America/New_York")
        )
        assert ctx.timestamp == "2026-09-25T06:14:00+00:00"
        # rows keep arrival time: only the snapshot's moment moves
        assert ctx.detections[0]["detected_at"].startswith("2026-09-25T15:00:00")

    def test_capture_tz_unset_keeps_arrival_time(self):
        row = make_detection_row(
            7, detected_at=self.ARRIVAL, file_path=self.FOSCAM.format("021400")
        )
        ctx = va.build_assess_context(camera_id="front_door", detections=[row])
        assert ctx.timestamp.startswith("2026-09-25T15:00:00")

    def test_capture_tz_picks_the_earliest_capture_across_rows(self):
        rows = [
            make_detection_row(7, detected_at=self.ARRIVAL, file_path=self.FOSCAM.format("021405")),
            make_detection_row(8, detected_at=self.ARRIVAL, file_path=self.FOSCAM.format("021400")),
        ]
        ctx = va.build_assess_context(
            camera_id="front_door", detections=rows, capture_tz=ZoneInfo("America/New_York")
        )
        assert ctx.timestamp == "2026-09-25T06:14:00+00:00"

    def test_a_non_foscam_name_falls_back_to_arrival(self):
        row = make_detection_row(7, detected_at=self.ARRIVAL)  # /media/front_door/det_7.jpg
        ctx = va.build_assess_context(
            camera_id="front_door", detections=[row], capture_tz=ZoneInfo("America/New_York")
        )
        assert ctx.timestamp.startswith("2026-09-25T15:00:00")

    def test_store_rows_pass_through_with_capture_tz_set(self):
        # Replay: an eval-store row already carries its frozen ISO string.
        store_row = {
            "id": 1,
            "object_type": "person",
            "confidence": 0.9,
            "bbox": [1, 2, 3, 4],
            "detected_at": "2026-09-25T12:00:00+00:00",
        }
        ctx = va.build_assess_context(
            camera_id="front_door", detections=[store_row], capture_tz=ZoneInfo("America/New_York")
        )
        assert ctx.timestamp == "2026-09-25T12:00:00+00:00"
```

Directly after `class TestBuildAssessContext`, add:

```python
class TestCaptureTimeReachesTheRequest:
    async def test_analyze_batch_sends_the_filename_capture_time(self, monkeypatch):
        client = FakeClient([make_verdict()])
        row = make_detection_row(
            11,
            detected_at=datetime(2026, 9, 25, 15, 0, 0, tzinfo=UTC),
            file_path="/export/foscam/front_door/FoscamCamera_X/snap/MDAlarm_20260925-021400.jpg",
        )
        analyzer, _, _ = make_analyzer(monkeypatch, client=client, detections=[row])
        analyzer._settings = analyzer._settings.model_copy(
            update={"camera_timezone": "America/New_York"}
        )
        await analyze(analyzer)
        assert client.calls[0].context.timestamp == "2026-09-25T06:14:00+00:00"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/services/test_vlm_analyzer.py -n0 -q -k "capture or foscam"`
Expected: FAIL — `TypeError: build_assess_context() got an unexpected keyword argument 'capture_tz'`,
and the `analyze_batch` test fails on `'2026-09-25T15:00:00+00:00' == '2026-09-25T06:14:00+00:00'`.
`test_capture_tz_unset_keeps_arrival_time` already passes; that is expected, because it pins
today's behavior.

- [ ] **Step 3: Implement**

In `backend/services/vlm_analyzer.py`, change the datetime import (line 52) to:

```python
from datetime import UTC, datetime, tzinfo
```

and add, next to the other `backend.services` imports:

```python
from backend.services.capture_time import camera_tz, resolve_capture_time
```

Change the signature and body of `build_assess_context`: add the keyword parameter
`capture_tz: tzinfo | None = None` after `specialist_outputs`, replace the docstring's
"Timestamp:" paragraph, and compute `times` inside the existing loop. The full function becomes:

```python
def build_assess_context(
    *,
    camera_id: str,
    detections: list[dict[str, Any]],
    zones: list[str] | None = None,
    household: dict[str, Any] | None = None,
    zone_crossing: bool = False,
    specialist_outputs: dict[str, str] | None = None,
    capture_tz: tzinfo | None = None,
) -> VlmAssessContext:
    """Field-for-field AssessInput (spec §5 / G0.4 - the shape pin lives in
    scripts/test_gen_ai_contract.py; this function is that pin's runtime
    half). Detection rows are normalized to the frozen store's keys
    (control_freeze._build_snapshot: id/object_type/confidence/bbox/
    detected_at) so a production-built snapshot and an eval-store snapshot
    are the SAME shape - the corpus stays comparable with what 2.1 replays.

    Timestamp: ISO (UTC) of the EARLIEST capture time. With `capture_tz` set
    (CAMERA_TIMEZONE), a row's capture time is its Foscam filename time
    (capture_time.resolve_capture_time); otherwise, or when the name does
    not parse, it is the row's detected_at. Rows keep detected_at (arrival)
    either way. Already-string values (store rows) pass through untouched."""
    det_rows = []
    times: list[str] = []
    for row in detections:
        det = row.get("detected_at")
        bbox = row.get("bbox")
        if bbox is None:
            bbox = [
                row.get("bbox_x"),
                row.get("bbox_y"),
                row.get("bbox_width"),
                row.get("bbox_height"),
            ]
        det_rows.append(
            {
                "id": row["id"],
                "object_type": row.get("object_type"),
                "confidence": row.get("confidence"),
                "bbox": bbox,
                "detected_at": det.isoformat() if isinstance(det, datetime) else det,
            }
        )
        if isinstance(det, datetime):
            moment = resolve_capture_time(row.get("file_path"), detected_at=det, tz=capture_tz)
            times.append(moment.isoformat())
        elif det:
            times.append(det)

    timestamp = min(times) if times else datetime.now(UTC).isoformat()

    return VlmAssessContext(
        camera_id=camera_id,
        detections=det_rows,
        zones=list(zones or []),
        zone_crossing=zone_crossing,
        household=dict(household or {}),
        timestamp=timestamp,
        # Rev 6 (F11 ruling 4): the snapshot is the ONE carrier of the
        # specialist texts — production fills them, replay loads them from
        # the store, and the request copies them out of the context below.
        specialist_outputs=dict(specialist_outputs or {}),
    )
```

Directly above `start_time = min(` (line 509), add this comment:

```python
        # Event times stay arrival time (detected_at): alerting compares them
        # with "now". Only the VLM's context uses capture time (P0 scope).
```

At the call site (line 517), add the argument:

```python
        context = build_assess_context(
            camera_id=camera_id,
            detections=detections,
            zones=zones,
            household=household,
            zone_crossing=detect_zone_crossing(detections, zone_names_by_det),
            specialist_outputs=specialist_outputs,
            capture_tz=camera_tz(self._settings.camera_timezone),
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/services/test_vlm_analyzer.py -n0 -q`
Expected: PASS (the whole file: the existing `TestBuildAssessContext` cases prove the unset path
is unchanged).

- [ ] **Step 5: Confirm the contract is unchanged**

Run: `uv run python scripts/gen-ai-contract.py --check`
Expected: exits 0 with no drift reported.

- [ ] **Step 6: Lint, type-check, commit**

```bash
uv run ruff check --fix backend/services/vlm_analyzer.py backend/tests/unit/services/test_vlm_analyzer.py
uv run ruff format backend/services/vlm_analyzer.py backend/tests/unit/services/test_vlm_analyzer.py
uv run mypy backend/services/vlm_analyzer.py
uvx pre-commit run --files backend/services/vlm_analyzer.py backend/tests/unit/services/test_vlm_analyzer.py
git add backend/services/vlm_analyzer.py backend/tests/unit/services/test_vlm_analyzer.py
git commit -m "feat(vlm): snapshot timestamp is the Foscam capture time when CAMERA_TIMEZONE is set

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The prompt's `Time:` line is local time

**Files:**

- Modify: `backend/services/vlm_client.py` (imports at lines 49-68; `_render_prompt` at line 461,
  the `Time:` line at 475)
- Test: `backend/tests/unit/services/test_vlm_client.py`

**Interfaces:**

- Consumes: `render_prompt_time` (Task 1); `Settings.camera_timezone` (Task 2);
  `VlmClient._settings` (existing).
- Produces: nothing new for later tasks.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/unit/services/test_vlm_client.py` (it already defines `make_client` and
`_request`; `_request` sets `timestamp="2026-09-25T12:00:00+00:00"`):

```python
class TestPromptTime:
    """The Time line: UTC ISO when CAMERA_TIMEZONE is unset, local time when set."""

    def test_time_line_is_the_iso_string_when_camera_timezone_unset(self) -> None:
        client = make_client(camera_timezone=None)
        prompt = client._render_prompt([], _request(["/x/a.jpg"]))
        assert "Time: 2026-09-25T12:00:00+00:00\n" in prompt

    def test_time_line_is_local_with_zone_when_camera_timezone_set(self) -> None:
        client = make_client(camera_timezone="America/New_York")
        prompt = client._render_prompt([], _request(["/x/a.jpg"]))
        assert "Time: 2026-09-25 08:00:00 local (America/New_York, UTC-04:00)\n" in prompt
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/services/test_vlm_client.py -n0 -q -k TestPromptTime`
Expected: the unset test PASSES (it pins today's behavior) and the local test FAILS, because the
prompt still says `Time: 2026-09-25T12:00:00+00:00`.

- [ ] **Step 3: Implement**

In `backend/services/vlm_client.py`, add next to the other `backend.services` imports:

```python
from backend.services.capture_time import render_prompt_time
```

In `_render_prompt`, replace the line `f"Time: {ctx.timestamp}\n"` with:

```python
            f"Time: {render_prompt_time(ctx.timestamp, self._settings.camera_timezone)}\n"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/services/test_vlm_client.py -n0 -q`
Expected: PASS (the whole file; `test_a_small_prompt_is_untouched_byte_for_byte` must still pass).

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check --fix backend/services/vlm_client.py backend/tests/unit/services/test_vlm_client.py
uv run ruff format backend/services/vlm_client.py backend/tests/unit/services/test_vlm_client.py
uv run mypy backend/services/vlm_client.py
uvx pre-commit run --files backend/services/vlm_client.py backend/tests/unit/services/test_vlm_client.py
git add backend/services/vlm_client.py backend/tests/unit/services/test_vlm_client.py
git commit -m "feat(vlm): show capture time as local time in the VLM prompt

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Documentation and the spec's settled scope

**Files:**

- Modify: `backend/services/AGENTS.md` (the "Core AI Pipeline Services" table, lines 55-64)
- Modify: `backend/evaluation/assess_input.py` (the `timestamp: str` field of `AssessInput`)
- Modify: `docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md` (§5.3)

- [ ] **Step 1: Index the module**

In `backend/services/AGENTS.md`, add this row to the "Core AI Pipeline Services" table directly
after the `batch_aggregator.py` row (let prettier realign the columns):

```markdown
| `capture_time.py` | Foscam filename → capture time for the VLM's time context (CAMERA_TIMEZONE) | No (import directly) |
```

- [ ] **Step 2: Document the timestamp's meaning at its definition**

In `backend/evaluation/assess_input.py`, directly above the `timestamp: str` line inside
`class AssessInput`, add:

```python
    # ISO UTC capture moment (synthbench P0): the earliest Foscam filename
    # time when CAMERA_TIMEZONE is set, else the earliest detected_at.
```

This is a comment only; the field set and types do not change.

- [ ] **Step 3: Record the settled scope in the spec**

In the spec's §5.3, replace the two sentences starting "The runner writes scene time into
filenames on the run's date." with:

```markdown
The runner writes each scene's clock time into filenames at its **most recent past occurrence**:
a filename time more than 5 minutes after arrival is rejected as a clock or timezone error, and
`.env.bench` sets `CAMERA_TIMEZONE`.

**Settled in P0:** capture time feeds only the VLM's time context, meaning the snapshot's
`timestamp` and the prompt's `Time:` line, shown as local time. `Detection.detected_at`, event
start and end times, batch windows, retention, the orphan sweep and every now-relative query keep
arrival time. No schema changes. Unset `CAMERA_TIMEZONE` keeps today's behavior. Moving event
times to capture time is a possible follow-up.
```

- [ ] **Step 4: Check and commit**

```bash
uvx pre-commit run --files backend/services/AGENTS.md backend/evaluation/assess_input.py docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md
uv run python scripts/gen-ai-contract.py --check
git add backend/services/AGENTS.md backend/evaluation/assess_input.py docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md
git commit -m "docs(synthbench): P0 capture-time scope settled; index capture_time

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Full verification

**Files:** none changed (fix anything these commands surface, in the task that introduced it).

- [ ] **Step 1: The unit tier**

Run: `uv run pytest backend/tests/unit/ -n auto -q`
Expected: PASS. One known environmental failure may appear,
`test_deploy_phases.py::test_skips_when_skip_build` (`systemctl` missing in sandboxes); if it
does, record it in the task report rather than "fixing" it.

- [ ] **Step 2: Contract and whole-tree static checks**

```bash
uv run python scripts/gen-ai-contract.py --check
uv run mypy backend/services/capture_time.py backend/services/vlm_analyzer.py backend/services/vlm_client.py backend/core/config.py
uv run ruff check backend/
```

Expected: all exit 0.

- [ ] **Step 3: Report**

Report the commits (`git log --oneline 4bfd6fa4..HEAD`), the unit-tier pass count, and the
outputs of Step 2. **Do not push or open a PR without the owner's go-ahead**: PRs are
outward-facing, and merges are owner-gated.
