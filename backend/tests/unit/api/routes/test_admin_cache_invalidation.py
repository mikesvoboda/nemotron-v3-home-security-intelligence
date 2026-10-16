"""[r223]: the developer-tool handlers schedule invalidation of what they write.

Ruling 223 item 1 directed `seed_cameras` and `clear_seeded_data` to "schedule the
same background invalidation of the cameras cache as the camera routes"
(`_invalidate_cameras_cache_background`, backend/api/routes/cameras.py:132).
Ruling 228's MEASURE had already shown the package premise was deeper: an
invalidator only helps if it reaches the key the route stores, which [r228] fixed
at the key shape. This file is the follow-on pin, one test per handler, plus the
census claim that the set of namespaces is the one #7201 lists.

Each test calls the real handler with a real `BackgroundTasks()` object and then
RUNS the scheduled tasks against a mock CacheService. That shape matters: a test
that only asserts `add_task` was called would pass while scheduling the wrong
thing, and a test that called the helper directly would pass while the handler
never scheduled it at all. Running the task proves both ends.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.routes.admin import (
    ClearDataRequest,
    SeedCamerasRequest,
    SeedEventsRequest,
)
from backend.core.constants import CacheInvalidationReason
from backend.services.cache_service import CacheService

# The seven namespaces the #7201 census lists as changed by all three handlers.
CENSUS_INVALIDATORS = (
    "invalidate_cameras",
    "invalidate_events",
    "invalidate_event_stats",
    "invalidate_timeline_summary",
    "invalidate_trends",
    "invalidate_entities",
    "invalidate_system_status",
)


def _census_cache() -> AsyncMock:
    """A CacheService double whose seven census invalidators are individually mockable."""
    cache = AsyncMock(spec=CacheService)
    for name in CENSUS_INVALIDATORS:
        setattr(cache, name, AsyncMock(return_value=1))
    return cache


async def _run_scheduled(bg_tasks) -> None:
    """Execute what the handler scheduled, so the test measures real scheduling.

    Awaited, not just called: the scheduled func is a coroutine function, so
    calling it without awaiting would build a coroutine, never run it, and let
    every assertion below pass vacuously.
    """
    assert bg_tasks.tasks, "handler scheduled no background task at all"
    for task in bg_tasks.tasks:
        await task.func(*task.args, **task.kwargs)


def _seed_cameras_db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result
    return db


def _seeding_db() -> AsyncMock:
    """Mock session that assigns IDs on flush, as the real DB does for Event/Detection.

    seed_events links detections to events through a junction insert built from
    ``event.id`` and ``detection.id`` right after ``flush()``, so a mock whose
    flush is a no-op leaves those ids None and the handler dies on
    ``int("None")`` before reaching its commit. Same shape as
    create_mock_db_with_id_assignment in test_admin.py.
    """
    db = AsyncMock()
    added: list = []
    counter = {"value": 1}

    def mock_add(obj):
        added.append(obj)

    async def mock_flush():
        for obj in added:
            if hasattr(obj, "id") and obj.id is None:
                obj.id = counter["value"]
                counter["value"] += 1

    db.add = MagicMock(side_effect=mock_add)
    db.commit = AsyncMock()
    db.flush = AsyncMock(side_effect=mock_flush)
    db.execute = AsyncMock()
    return db


class TestDevtoolHandlersScheduleInvalidation:
    """One test per handler: it defers the census invalidation set after commit."""

    @pytest.mark.asyncio
    async def test_seed_cameras_schedules_the_census_invalidators(self) -> None:
        from fastapi import BackgroundTasks

        from backend.api.routes.admin import seed_cameras

        cache, bg = _census_cache(), BackgroundTasks()
        request = SeedCamerasRequest(count=1, clear_existing=False, create_folders=False)

        with (
            patch("backend.api.routes.admin.get_settings", autospec=True) as mock_settings,
            patch("backend.api.routes.admin._get_sample_cameras", autospec=True) as mock_samples,
            patch("backend.api.routes.admin.get_db_audit_service", autospec=True) as mock_audit,
        ):
            mock_settings.return_value.foscam_base_path = "/export/foscam"
            mock_samples.return_value = [
                {
                    "id": "cam1",
                    "name": "Cam 1",
                    "folder_path": "/export/foscam/cam1",
                    "status": "online",
                }
            ]
            mock_audit.return_value.log_action = AsyncMock()
            await seed_cameras(
                request=request,
                http_request=MagicMock(),
                background_tasks=bg,
                cache=cache,
                db=_seed_cameras_db(),
                _admin=None,
            )

        await _run_scheduled(bg)
        for name in CENSUS_INVALIDATORS:
            getattr(cache, name).assert_awaited_once_with(reason=CacheInvalidationReason.MANUAL)

    @pytest.mark.asyncio
    async def test_clear_seeded_data_schedules_the_census_invalidators(self) -> None:
        from fastapi import BackgroundTasks

        from backend.api.routes.admin import clear_seeded_data

        cache, bg = _census_cache(), BackgroundTasks()
        db = _seed_cameras_db()

        with patch("backend.api.routes.admin.get_db_audit_service", autospec=True) as mock_audit:
            mock_audit.return_value.log_action = AsyncMock()
            await clear_seeded_data(
                body=ClearDataRequest(confirm="DELETE_ALL_DATA"),
                request=MagicMock(),
                background_tasks=bg,
                cache=cache,
                db=db,
                _admin=None,
            )

        await _run_scheduled(bg)
        for name in CENSUS_INVALIDATORS:
            getattr(cache, name).assert_awaited_once_with(reason=CacheInvalidationReason.MANUAL)

    @pytest.mark.asyncio
    async def test_seed_events_schedules_the_census_invalidators(self) -> None:
        """seed_events writes events+detections, so it schedules the same superset.

        Ruling 223 names only seed_cameras and clear_seeded_data, but the package's
        MEASURE box lists seed_events as a write that changes cached reads
        ("`seed_events` (`:450`) adds events"), and ruling 228 item 2 says the
        THREE developer-tool handlers call the invalidators.
        """
        from fastapi import BackgroundTasks

        from backend.api.routes.admin import seed_events

        cache, bg = _census_cache(), BackgroundTasks()
        db = _seeding_db()
        camera = MagicMock()
        camera.id = "cam1"
        camera.name = "Cam 1"

        # With clear_existing=False the handler's first query is the cameras
        # select, which must be non-empty or it 400s before seeding. Later
        # executes are the junction inserts, whose results the handler ignores.
        cameras = MagicMock()
        cameras.scalars.return_value.all.return_value = [camera]
        db.execute.return_value = cameras

        with (
            patch("backend.api.routes.admin.random", autospec=True) as mock_random,
            patch("backend.api.routes.admin.get_db_audit_service", autospec=True) as mock_audit,
        ):
            mock_random.choice.return_value = camera
            mock_random.random.return_value = 0.25
            mock_random.randint.side_effect = lambda a, _b: a
            mock_random.uniform.side_effect = lambda a, b: (a + b) / 2
            mock_audit.return_value.log_action = AsyncMock()
            await seed_events(
                request=SeedEventsRequest(count=1, clear_existing=False),
                http_request=MagicMock(),
                background_tasks=bg,
                cache=cache,
                db=db,
                _admin=None,
            )

        await _run_scheduled(bg)
        for name in CENSUS_INVALIDATORS:
            getattr(cache, name).assert_awaited_once_with(reason=CacheInvalidationReason.MANUAL)


class TestEventsHelperCoversEveryEventDerivedRead:
    """[r223] MEASURE: the shared events helper covers four event-derived namespaces.

    Adding timeline_summary and trends here is what makes the timeline/trends
    stale-read bug close for every existing event write path (create, update,
    delete, bulk delete) — not just the developer tools.
    """

    @pytest.mark.asyncio
    async def test_helper_invalidates_events_stats_timeline_and_trends(self) -> None:
        from backend.api.routes.events import _invalidate_events_cache_background

        cache = AsyncMock(spec=CacheService)
        await _invalidate_events_cache_background(cache, "event_created")

        for name in (
            "invalidate_events",
            "invalidate_event_stats",
            "invalidate_timeline_summary",
            "invalidate_trends",
        ):
            getattr(cache, name).assert_awaited_once_with(reason="event_created")

    @pytest.mark.asyncio
    async def test_a_failure_on_one_namespace_does_not_strand_the_rest(self) -> None:
        """Per-namespace isolation: the one-try shape strands everything after the fault.

        This is the property the two-call legacy helpers did not need and a
        seven-namespace helper does: with one try block around all the awaits, a
        Redis error on `events` would leave timeline_summary and trends cached for
        their full TTL — the exact bug class [r223] exists to close.
        """
        from backend.api.routes.events import _invalidate_events_cache_background

        cache = AsyncMock(spec=CacheService)
        cache.invalidate_events = AsyncMock(side_effect=Exception("redis down"))
        for name in ("invalidate_event_stats", "invalidate_timeline_summary", "invalidate_trends"):
            setattr(cache, name, AsyncMock(return_value=1))

        with patch("backend.api.routes.events.logger", autospec=True) as mock_logger:
            await _invalidate_events_cache_background(cache, "event_created")

        cache.invalidate_timeline_summary.assert_awaited_once()
        cache.invalidate_trends.assert_awaited_once()
        assert mock_logger.warning.call_count == 1


class TestEntitiesAndTrendsAreSeparateNamespaces:
    """The narrow invalidators do not over-delete the namespaces they neighbour."""

    @pytest.mark.asyncio
    async def test_invalidate_entities_does_not_sweep_all_summaries(self) -> None:
        """entities lives inside summaries:* but must be deletable on its own.

        The developer tools change FaceDetectionEvent rows (via the camera FK
        cascade) without touching Summary, so sweeping summaries:* would evict
        still-valid narratives on every seed click.
        """
        from backend.api.routes.admin import _invalidate_devtool_caches_background

        cache = _census_cache()
        await _invalidate_devtool_caches_background(cache)

        cache.invalidate_entities.assert_awaited_once()
        # The broad summaries purge is NOT part of the census — no handler here
        # changes Summary rows.
        assert not cache.invalidate_summaries.await_count

    @pytest.mark.asyncio
    async def test_helper_is_fail_soft_across_the_seven_namespaces(self) -> None:
        from backend.api.routes.admin import _invalidate_devtool_caches_background

        cache = _census_cache()
        cache.invalidate_events = AsyncMock(side_effect=Exception("redis down"))

        with patch("backend.api.routes.admin.logger", autospec=True) as mock_logger:
            await _invalidate_devtool_caches_background(cache)

        # Every other namespace still attempted despite the events fault.
        for name in CENSUS_INVALIDATORS:
            if name != "invalidate_events":
                getattr(cache, name).assert_awaited_once()
        assert mock_logger.warning.call_count == 1


class TestManualCacheClearCoversEveryNamespace:
    """POST /maintenance/clear-cache is "clear ALL cached data" — it must mean it.

    [r223] adds `invalidate_timeline_summary` and `invalidate_trends`; a manual
    clear that predates them would still leave the two orphan namespaces
    cached for their full TTL, so the button's docstring claim goes false the
    moment those invalidators exist. This class is the pin that keeps it true.
    """

    @staticmethod
    def _clear_cache_invalidators() -> set[str]:
        """Every real namespace invalidator on CacheService.

        `invalidate_pattern` is the generic helper every one of them calls, not
        a namespace. `invalidate_entities` is exempt because its key lives
        inside `summaries:*`, which `invalidate_summaries` already scans —
        listing both would double-count the same keys in `keys_cleared`.
        """
        return {
            name
            for name in dir(CacheService)
            if name.startswith("invalidate_")
            and name not in ("invalidate_pattern", "invalidate_entities")
        }

    @pytest.mark.asyncio
    async def test_clear_cache_names_every_invalidator_but_entities(self) -> None:
        from backend.api.routes.admin import clear_cache

        cache = AsyncMock(spec=CacheService)
        for name in dir(CacheService):
            if name.startswith("invalidate_"):
                setattr(cache, name, AsyncMock(return_value=1))

        with (
            patch(
                "backend.services.cache_service.get_cache_service",
                AsyncMock(return_value=cache),
            ),
            patch("backend.api.routes.admin.get_db_audit_service", autospec=True) as mock_audit,
        ):
            mock_audit.return_value.log_action = AsyncMock()
            response = await clear_cache(http_request=MagicMock(), db=AsyncMock(), _admin=None)

        # Set equality is the whole claim: every real invalidator ran, and
        # nothing else ran (so a `invalidate_foo` added to CacheService without
        # being wired into the manual clear turns this red, and so does
        # redundantly listing `invalidate_entities` next to `invalidate_summaries`).
        # The isinstance filter is load-bearing: on a spec'd mock the SYNC
        # members are plain MagicMocks whose `.await_count` is an auto-created
        # truthy child, so an unfiltered `getattr(...).await_count` would put
        # every method in the set and the equality would be vacuous.
        # `awaited` holds METHOD names (invalidate_alerts); response.cache_types
        # holds the handler's display labels (alerts, system). The method-name
        # set is the load-bearing invariant; the label list is asserted only
        # for the two namespaces this PR adds, because pinning every label
        # would just duplicate the handler's literal list as a second source
        # of truth (see test_cache_prefix_shape's mirror-assert note).
        awaited = {
            n
            for n in dir(cache)
            if isinstance(getattr(cache, n), AsyncMock) and getattr(cache, n).await_count
        }
        assert awaited == self._clear_cache_invalidators()
        cache.invalidate_summaries.assert_awaited_once()
        assert {"timeline_summary", "trends"} <= set(response.cache_types)
