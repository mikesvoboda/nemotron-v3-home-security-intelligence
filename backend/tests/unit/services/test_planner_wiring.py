"""Unit tests for backend.services.alerting.wiring (B4.2).

The wiring module builds the production planner the pipeline hooks use:
a loader that queries recipients+channels+quiet periods, the household
timezone from the Property row, and the DB delivery writer.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.services.alerting.wiring import (
    household_timezone,
    load_recipients_with_channels,
)


def _session_with(prop: object) -> object:
    """A fake session whose select(...) yields ``prop`` (or None)."""

    class _Result:
        def scalars(self) -> object:
            return self

        def first(self) -> object:
            return prop

    class _S:
        async def execute(self, _stmt: object) -> _Result:
            return _Result()

    return _S()


class _Scalars:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _Result:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)


class _Session:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    async def execute(self, _stmt: object) -> _Result:
        return _Result(self._rows)


class TestHouseholdTimezone:
    async def test_returns_property_timezone_when_set(self) -> None:
        prop = SimpleNamespace(timezone="Europe/Berlin")
        assert await household_timezone(_session_with(prop)) == "Europe/Berlin"  # type: ignore[arg-type]

    async def test_returns_utc_when_property_timezone_empty(self) -> None:
        prop = SimpleNamespace(timezone="")
        assert await household_timezone(_session_with(prop)) == "UTC"  # type: ignore[arg-type]

    async def test_returns_utc_when_no_property_row(self) -> None:
        assert await household_timezone(_session_with(None)) == "UTC"  # type: ignore[arg-type]


class TestLoadRecipients:
    async def test_returns_rows_from_session(self) -> None:
        rec = SimpleNamespace(id="r1", enabled=True, channels=[])

        class _MultiSession:
            def __init__(self) -> None:
                self.calls = 0

            async def execute(self, _stmt: object) -> _Result:
                self.calls += 1
                return _Result([] if self.calls > 1 else [rec])

        rows = await load_recipients_with_channels(_MultiSession())  # type: ignore[arg-type]
        assert rows == [rec]
        assert rec.quiet_periods == []

    async def test_groups_quiet_periods_by_recipient(self) -> None:
        rec = SimpleNamespace(id="r1", enabled=True, channels=[])
        period = SimpleNamespace(recipient_id="r1")
        other = SimpleNamespace(recipient_id="r2")

        class _MultiSession:
            def __init__(self) -> None:
                self.calls = 0

            async def execute(self, _stmt: object) -> _Result:
                self.calls += 1
                return _Result({1: [rec], 2: [period, other]}[self.calls])

        await load_recipients_with_channels(_MultiSession())  # type: ignore[arg-type]
        assert rec.quiet_periods == [period]

    async def test_returns_empty_without_rows(self) -> None:
        rows = await load_recipients_with_channels(_Session([]))  # type: ignore[arg-type]
        assert rows == []
