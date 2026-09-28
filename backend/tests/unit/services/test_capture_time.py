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
