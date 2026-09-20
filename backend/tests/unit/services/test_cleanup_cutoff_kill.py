"""WP3.2 kill tests for CleanupService.run_cleanup — the silent data-loss class.

Proven survivor (plan P §WP3.2): backend/services/cleanup_service.py:266,
    cutoff_date = datetime.now(UTC) - timedelta(days=self.retention_days)
inside run_cleanup() (def at :239). A surviving mutant changes WHAT GETS
DELETED: retention is a product promise (30d, .env-confirmed), and the value
flows straight into three DELETE ... WHERE col < cutoff_date statements
(:283 Detection, :294 Event, :303 GPUStats) — mutated days/sign/operator
deletes live evidence or hoards expired footage with zero errors.

Doctrine: pin the value that reaches the DELETE, never an internal local.
The captured bound-parameter of every delete clause must equal now-retention
(tz-aware). Kills mutants of: the timedelta operand, the - sign, the
comparison operator (clause shape changes), and now(UTC)->now(None) (a naive
datetime cannot compare with the tz-aware columns — and is caught here on
tzinfo before SQLAlchemy ever notices).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from operator import lt
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _settings_env():
    """Same guard as the sibling suite's autouse fixture: pydantic Settings
    validates DATABASE_URL at import, and this file must run standalone."""
    from backend.core.config import get_settings

    # backend/tests/conftest.py sets ENVIRONMENT=test (which relaxes the
    # weak-password validator); the scratch copy must do it itself.
    os.environ.setdefault("ENVIRONMENT", "test")
    original = os.environ.get("DATABASE_URL")
    if original is None:
        os.environ["DATABASE_URL"] = (
            "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
        )
        get_settings.cache_clear()
    yield
    if original is None:
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


class _CapturingStmt:
    """Stands in for delete(model): records (operator, cutoff bound) per .where().

    The operator is captured too: :283/:294/:303 all compare `col < cutoff_date`,
    and a < -> > mutant inverts which rows the DELETE claims (hoards expired
    footage / spares evidence) without changing the bound value at all."""

    def __init__(self, sink: list) -> None:
        self._sink = sink

    def where(self, clause):
        # col < cutoff  ->  BinaryExpression.right is the BindParameter
        right = getattr(clause, "right", None)
        self._sink.append((getattr(clause, "operator", None), getattr(right, "value", "UNBOUND")))
        return self


@pytest.fixture
def jobless_service():
    """CleanupService with the Redis job-tracking path closed off."""
    from backend.services.cleanup_service import CleanupService

    svc = CleanupService(
        cleanup_time="03:00",
        retention_days=30,
        thumbnail_dir="data/thumbnails",
        delete_images=False,
    )
    svc._get_job_status_service = MagicMock(return_value=None)
    return svc


@pytest.mark.asyncio
async def test_run_cleanup_deletes_exactly_at_retention_cutoff(jobless_service):
    """ALL THREE delete bounds == now-30d, tz-aware — the :266 arithmetic
    pinned at the place it is consumed (the DELETE), not where it is computed."""
    bounds: list = []
    session = MagicMock()
    session.execute = AsyncMock(return_value=SimpleNamespace(rowcount=0))
    session.commit = AsyncMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)

    from backend.services import cleanup_service as cs

    with (
        patch.object(cs, "get_session", autospec=True, return_value=cm),
        patch.object(
            cs, "delete", autospec=True, side_effect=lambda _model: _CapturingStmt(bounds)
        ),
        patch.object(
            jobless_service,
            "_get_detection_file_paths_streaming",
            new=AsyncMock(return_value=([], [])),
        ),
        patch.object(jobless_service, "cleanup_old_logs", new=AsyncMock(return_value=0)),
    ):
        before = datetime.now(UTC)
        stats = await jobless_service.run_cleanup()
        after = datetime.now(UTC)

    assert stats is not None
    assert len(bounds) == 3, f"Detection+Event+GPUStats deletes expected, got {bounds!r}"
    lo, hi = before - timedelta(days=30), after - timedelta(days=30)
    for op, b in bounds:
        # operator.lt is a builtin function object, not a type — identity check
        assert op is lt, f"delete clause must be `col < cutoff`, got {op!r}"
        assert isinstance(b, datetime), f"delete bound is not a datetime: {b!r}"
        assert b.tzinfo is not None, f"cutoff must be tz-aware UTC (now(UTC)): {b!r}"
        assert lo <= b <= hi, (
            f"delete bound {b} outside [{lo}, {hi}] — run_cleanup :266 cutoff "
            "arithmetic is mutated (WP3.2 silent-data-loss mutant)"
        )


@pytest.mark.asyncio
async def test_run_cleanup_cutoff_uses_instance_retention_not_default(jobless_service):
    """retention_days is per-instance config; a mutant hardwiring 30 (or any
    constant) while the instance says 7 must be caught — the bound follows
    the INSTANCE value."""
    jobless_service.retention_days = 7
    bounds: list = []
    session = MagicMock()
    session.execute = AsyncMock(return_value=SimpleNamespace(rowcount=0))
    session.commit = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)

    from backend.services import cleanup_service as cs

    with (
        patch.object(cs, "get_session", autospec=True, return_value=cm),
        patch.object(
            cs, "delete", autospec=True, side_effect=lambda _model: _CapturingStmt(bounds)
        ),
        patch.object(
            jobless_service,
            "_get_detection_file_paths_streaming",
            new=AsyncMock(return_value=([], [])),
        ),
        patch.object(jobless_service, "cleanup_old_logs", new=AsyncMock(return_value=0)),
    ):
        before = datetime.now(UTC)
        await jobless_service.run_cleanup()
        after = datetime.now(UTC)

    lo, hi = before - timedelta(days=7), after - timedelta(days=7)
    assert bounds and all(lo <= b <= hi for _op, b in bounds), (
        f"cutoff must follow instance retention (7d): {bounds!r}"
    )
