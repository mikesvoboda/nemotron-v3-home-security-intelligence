# WP4.4 Triage Dossier — backend/services/track_service.py

Date: 2026-09-17 · Wave: dispatched-track-service · Status: DRAFT, tests UNVERIFIED (no pytest run in this lane — live mutation run owns the box).

## Verdict data

- meta: `mutants/backend/services/track_service.py.meta` — 468 keys, **152 survivors** (exit_code 0), remainder killed/timeout, no nulls.
- covering tests (mutmut-stats.json `tests_by_mangled_function_name`): **all 22 covering tests live in one file**:
  `backend/tests/unit/services/test_track_service.py`
  (TestCreateOrUpdateTrack L209, TestGetTrack L317, TestGetTrackHistory L347, TestGetTracksByCamera L382, TestPruneOldTracks L481, TestTrackMetrics L567). All DB access is `AsyncMock()` — statements are constructed then discarded into the mock; metrics calls are `patch(..., autospec=True)` with exact-call assertions.
- **calculate_metrics (137 mutants) and all functions under `get_active_tracks`, `get_track_count_since`, `get_avg_track_duration`, `get_track_counts_by_type`, `get_track_by_id` have ZERO surviving mutants** (pure-function tests + coverage filtering) — they contribute nothing here. Singleton/factory mutants all killed.

## Diff-extraction method (mutmut show was broken — read-only fallback)

`uv run mutmut show` fails for this module (`Could not find original function`): the mutants copy
`mutants/backend/services/track_service.py` is a plain byte-identical copy of the source (the live run
re-copies and rewrites it in place; the expanded `__mutmut_N`-trampolined file existed only during the
generation phase and no snapshot survived). Fallback used (all in `/tmp/wp25/wp44-triage/track-scratch/`,
repo untouched):

1. Re-ran mutmut's own `create_mutations`/`group_by_top_level_node` on the pristine source, then per-mutant
   `func.deep_replace(original_node, mutated_node)` and difflib — produces the full ordered list of 569
   candidate mutants (unfiltered).
2. Pinned meta numbering with the line-span signature: `len(rendered mutant function) == spans[name].end -
spans[name].start + 1` (validated exact-match on 16/16 functions; e.g. get_track 1:20↔19+decorator,
   create_or_update_track 1:122↔122).
3. 14 of 16 functions: per-function meta count == unfiltered generation count → identity index mapping,
   signature-validated. **105 of 152 survivors are therefore exactly mapped.**

### ⚠ Caveat: two alignment-ambiguous functions

`get_tracks_by_camera` (83 meta keys vs 87 generated) and `mark_track_lost` (37 vs 39) had 4 / 2 mutants
excluded by coverage filtering **that are not line-consistently explainable** (mutants sharing a source
line are always kept-or-dropped together — every line-anchored drop-set fails the spans signature; the
`pyproject.toml` was modified 13:17 mid-run, likely a mid-flight config/coverage drift explains the
orphans). Index→diff assignment there is a heuristic (length-signature DP; 151,470 / 378 feasible
solutions). Per-key diffs for these 47 survivors are pattern-family confident, per-index exactness is
not; a few assigned diffs (e.g. `mark_track_lost` autospec-visible arg-drops) contradict survival,
confirming some assignments in those two functions are rotated. Cluster classification below is by
pattern family, which survives the ambiguity. Keys whose exact mutant is uncertain are still counted in
their family cluster; family boundaries are the same for every feasible alignment.

## Cluster table (152 = TEST-GAP 98 + LOW-VALUE 48 + EQUIVALENT 6)

| #   | Function / concern      | Pattern (example mutant keys, suffix)                                                                                                                                                     | n   | Class      |
| --- | ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --- | ---------- |
| 1   | create_or_update_track  | SQL stmt built then handed to mock; stmt=None / where-condition→None / condition removed / `==`→`!=` / execute(None) — L125-130                                                           | 9   | TEST-GAP   |
| 2   | create_or_update_track  | `Track(...)` kwargs → None or removed (track_id..reid_embedding); `track = None` — L134-142                                                                                               | 15  | TEST-GAP   |
| 3   | create_or_update_track  | `db.add(x)`/`db.refresh(x)` args → None (create + update paths) — L143,145,186                                                                                                            | 3   | TEST-GAP   |
| 4   | create_or_update_track  | stored metrics assignment: `calculate_metrics(None)` / `total_distance=None` / `avg_speed=None` — L181-183                                                                                | 3   | TEST-GAP   |
| 5   | create_or_update_track  | debug-log message f-string → None — L148,169,189                                                                                                                                          | 3   | EQUIVALENT |
| 6   | create_or_update_track  | debug-log `extra=` payload mutations (dict→None, key rename XX/UPPER, dict removed) — L149-153,170,190-195                                                                                | 24  | LOW-VALUE  |
| 7   | create_or_update_track  | prune bound `> max_points` → `>=` (slice at len==max is identity — provably equivalent) — L166                                                                                            | 1   | EQUIVALENT |
| 8   | get_track               | same SQL-opaque family: stmt/where/select(None), `==`→`!=`, execute(None) — L215-220                                                                                                      | 9   | TEST-GAP   |
| 9   | get_track_history       | `get_track(None, ...)` / `(id, None)` args; `calculate_metrics(None)` (zero metrics flow into response, never asserted) — L248,263                                                        | 3   | TEST-GAP   |
| 10  | get_tracks_by_camera ⚠ | pagination math: clamp `max(1,min(·,1000))`→`max(1,min(·,1001))`, offset `(page-1)*size` → None / `/ size` / `(page-2)*size` — L309-311                                                   | 6   | TEST-GAP   |
| 11  | get_tracks_by_camera ⚠ | query build + order/offset/limit args: base/count/paginated query → None, `select(None)`, `order_by(None)`, `offset(None)`, execute(None) — L314,326,331-334                              | 9   | TEST-GAP   |
| 12  | get_tracks_by_camera ⚠ | filter guards `is not None`→`is None` (filter skipped when provided / applied when None), `.where(None)`, condition removal — L316-323                                                    | 8   | TEST-GAP   |
| 13  | get_tracks_by_camera ⚠ | response metrics branching: `metrics=""` init, and/or guard flips, `trajectory or []`→None/`and []`, `calculate_metrics(None)`, `metrics=None`/metric removed in TrackResponse — L340-357 | 10  | TEST-GAP   |
| 14  | prune_old_tracks        | cutoff `now - timedelta` → `now + timedelta`; `now(UTC)`→`now(None)` (naive cutoff) — L388                                                                                                | 2   | TEST-GAP   |
| 15  | prune_old_tracks        | delete stmt: None / `where(None)` / `last_seen <` → `<=` (boundary rows survive) / execute(None) — L390-391                                                                               | 4   | TEST-GAP   |
| 16  | prune_old_tracks        | info-log message → None — L396                                                                                                                                                            | 1   | EQUIVALENT |
| 17  | prune_old_tracks        | info-log `extra=` payload mutations — L397-401                                                                                                                                            | 8   | LOW-VALUE  |
| 18  | prune_old_tracks        | log-emission gate `deleted_count > 0` → `>= 0` / `> 1` (log-only) — L394                                                                                                                  | 2   | LOW-VALUE  |
| 19  | mark_track_lost ⚠      | default `reason="timeout"` → `"TIMEOUT"` (tests always pass reason explicitly) — L410                                                                                                     | 1   | TEST-GAP   |
| 20  | mark_track_lost ⚠      | `track = None` lookup swap; `entity_type` fallback → None / `and "unknown"` / `"XXunknownXX"` (fallback path needs object_class=None, never tested) — L436,441                            | 4   | TEST-GAP   |
| 21  | mark_track_lost ⚠      | `record_track_lost(camera_id, reason)` entity arg dropped — L449                                                                                                                          | 1   | TEST-GAP   |
| 22  | mark_track_lost ⚠      | debug-log `extra=` payload mutations — L453-458                                                                                                                                           | 10  | LOW-VALUE  |
| 23  | get_active_track_count  | cutoff `now - timedelta` → `+`; `now(UTC)`→`now(None)` (naive cutoff) — L501                                                                                                              | 2   | TEST-GAP   |
| 24  | get_active_track_count  | count stmt: None / where-clauses → None or removed / `select(None)` / `last_seen >=` → `>` / execute(None) — L503-511                                                                     | 9   | TEST-GAP   |
| 25  | record_reidentification | debug-log message → None — L480                                                                                                                                                           | 1   | EQUIVALENT |
| 26  | record_reidentification | debug-log `extra=` payload mutations — L481                                                                                                                                               | 4   | LOW-VALUE  |

⚠ = the alignment-ambiguous functions (see caveat above).

Why TEST-GAP, not "no coverage": every one of these lines EXECUTES under the covering tests
(`backend/tests/unit/services/test_track_service.py`, 22 tests) — the survivors are exactly the family
the `AsyncMock` session makes opaque: (a) compiled SQL text is never inspected, (b) fallback branches
need `None`/edge inputs the tests never feed, (c) `response.metrics` / stored metric fields are never
read, (d) pagination offsets/limits and cutoff datetimes are never asserted.

## Drafted kill-tests (UNVERIFIED — not yet run red/green)

All target `backend/tests/unit/services/test_track_service.py` (append classes; style matches existing
fixtures `mock_session`/`mock_track`). TDD procedure for each: paste against current mutants file →
pytest must go RED for every listed cluster mutant; on pristine `backend/services/track_service.py` →
GREEN. Verify in the serial pytest lane only.

### T1 — `TestQueryConstruction` (kills clusters 1, 8, 24, 15, 14, 23; also 11's stmt members)

```python
class TestQueryConstruction:
    """WP4.4: pin the SQL each method builds — AsyncMock made query mutants invisible.

    UNVERIFIED - not yet run red/green.
    """

    @staticmethod
    def _sql(stmt) -> str:
        # compile() raises for stmt=None / execute(None) / where(None) mutants -> test fails (red).
        return str(stmt.compile(compile_kwargs={"literal_binds": True}))

    @pytest.mark.asyncio
    async def test_get_track_query_filters_both_keys(self, mock_session, mock_track):
        service = TrackService(mock_session)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_track
        mock_session.execute.return_value = mock_result

        await service.get_track(track_id=42, camera_id="front_door")

        sql = self._sql(mock_session.execute.call_args.args[0])
        assert "track_id = 42" in sql
        assert "camera_id = 'front_door'" in sql

    @pytest.mark.asyncio
    async def test_lookup_query_rejects_swapped_operators(self, mock_session):
        """== flipped to != must not compile silently through this test."""
        service = TrackService(mock_session)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await service.create_or_update_track(
            track_id=7,
            camera_id="yard",
            object_class="car",
            position=(1.0, 2.0),
            timestamp=datetime(2026, 1, 26, 12, 0, 0, tzinfo=UTC),
        )

        sql = self._sql(mock_session.execute.call_args_list[0].args[0])
        assert "track_id = 7" in sql and "camera_id = 'yard'" in sql

    @pytest.mark.asyncio
    async def test_prune_cutoff_is_past_and_aware(self, mock_session):
        service = TrackService(mock_session, track_retention_hours=24)
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        await service.prune_old_tracks()

        sql = self._sql(mock_session.execute.call_args.args[0])
        assert "track.last_seen < " in sql            # strict <, not <=
        assert " <= " not in sql
        # cutoff literal must be tz-aware (kills now(None) naive) and in the PAST (kills - -> +)
        match = re.search(r"'(\d{4}-\d{2}-\d{2} [0-9:.]+(\+\d{2}:\d{2})?)'", sql)
        assert match is not None
        cutoff = datetime.fromisoformat(match.group(1))
        assert cutoff.tzinfo is not None
        assert cutoff < datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_active_count_query_shape(self, mock_session):
        service = TrackService(mock_session, track_retention_hours=24)
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        mock_session.execute.return_value = mock_result

        await service.get_active_track_count("front_door")

        sql = self._sql(mock_session.execute.call_args.args[0])
        assert "camera_id = 'front_door'" in sql
        assert "last_seen >= " in sql                 # >=, not > (boundary second counts)
        match = re.search(r"'(\d{4}-\d{2}-\d{2} [0-9:.]+(\+\d{2}:\d{2})?)'", sql)
        cutoff = datetime.fromisoformat(match.group(1))
        assert cutoff.tzinfo is not None and cutoff < datetime.now(UTC)
```

(add `import re` to the file's imports — `datetime`/`UTC` already imported.)

### T2 — `TestPaginationAndFilters` (kills clusters 10, 12; also 11's order/offset/limit members)

```python
class TestPaginationAndFilters:
    """WP4.4: offset/limit/filter clauses were asserted nowhere — only call_count was.

    UNVERIFIED - not yet run red/green.
    """

    @staticmethod
    def _sql(stmt) -> str:
        return str(stmt.compile(compile_kwargs={"literal_binds": True}))

    @staticmethod
    def _two_results(count: int):
        count_result = MagicMock()
        count_result.scalar_one.return_value = count
        tracks_result = MagicMock()
        tracks_result.scalars.return_value.all.return_value = []
        return [count_result, tracks_result]

    @pytest.mark.asyncio
    async def test_page_two_offset_is_one_full_page(self, mock_session):
        service = TrackService(mock_session)
        mock_session.execute.side_effect = self._two_results(10)

        await service.get_tracks_by_camera("front_door", page=2, page_size=25)

        sql = self._sql(mock_session.execute.call_args.args[0])
        assert "LIMIT 25" in sql and "OFFSET 25" in sql

    @pytest.mark.asyncio
    async def test_page_size_clamped_to_max_and_min(self, mock_session):
        service = TrackService(mock_session)
        mock_session.execute.side_effect = self._two_results(0)
        await service.get_tracks_by_camera("front_door", page=1, page_size=2000)
        assert "LIMIT 1000" in self._sql(mock_session.execute.call_args.args[0])

        mock_session.execute.side_effect = self._two_results(0)
        await service.get_tracks_by_camera("front_door", page=1, page_size=0)
        assert "LIMIT 1" in self._sql(mock_session.execute.call_args.args[0])

    @pytest.mark.asyncio
    async def test_first_seen_desc_order_applied(self, mock_session):
        service = TrackService(mock_session)
        mock_session.execute.side_effect = self._two_results(0)

        await service.get_tracks_by_camera("front_door")

        sql = self._sql(mock_session.execute.call_args.args[0]).lower()
        assert "order by" in sql and "first_seen desc" in sql

    @pytest.mark.asyncio
    async def test_time_and_class_filters_reach_both_queries(self, mock_session):
        service = TrackService(mock_session)
        mock_session.execute.side_effect = self._two_results(0)

        await service.get_tracks_by_camera(
            "front_door",
            start_time=datetime(2026, 1, 26, 11, 0, 0, tzinfo=UTC),
            end_time=datetime(2026, 1, 26, 13, 0, 0, tzinfo=UTC),
            object_class="person",
        )

        for call in mock_session.execute.call_args_list:
            sql = self._sql(call.args[0])
            assert "first_seen >= " in sql
            assert "first_seen <= " in sql
            assert "object_class = 'person'" in sql

    @pytest.mark.asyncio
    async def test_absent_filters_add_no_conditions(self, mock_session):
        service = TrackService(mock_session)
        mock_session.execute.side_effect = self._two_results(0)

        await service.get_tracks_by_camera("front_door")

        for call in mock_session.execute.call_args_list:
            sql = self._sql(call.args[0])
            assert "first_seen >=" not in sql and "object_class" not in sql
```

### T3 — `TestTrackConstruction` (kills clusters 2, 3)

```python
class TestTrackConstruction:
    """WP4.4: the Track built for a new observation was never inspected (add is a MagicMock).

    UNVERIFIED - not yet run red/green.
    """

    @pytest.mark.asyncio
    async def test_created_track_carries_every_field(self, mock_session):
        from backend.models.track import Track

        service = TrackService(mock_session)
        timestamp = datetime(2026, 1, 26, 12, 0, 0, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await service.create_or_update_track(
            track_id=42,
            camera_id="front_door",
            object_class="person",
            position=(640.5, 480.2),
            timestamp=timestamp,
            reid_embedding=b"\x00\x01\x02\x03",
        )

        added = mock_session.add.call_args.args[0]
        assert isinstance(added, Track)
        assert added.track_id == 42
        assert added.camera_id == "front_door"
        assert added.object_class == "person"
        assert added.first_seen == timestamp
        assert added.last_seen == timestamp
        assert added.trajectory == [
            {"x": 640.5, "y": 480.2, "timestamp": timestamp.isoformat()}
        ]
        assert added.reid_embedding == b"\x00\x01\x02\x03"
        assert mock_session.refresh.call_args.args[0] is added
```

### T4 — `TestMetricFieldsPropagate` (kills clusters 4, 9, 13)

```python
class TestMetricFieldsPropagate:
    """WP4.4: stored + response metric fields were written/read but never asserted.

    UNVERIFIED - not yet run red/green.
    """

    @pytest.mark.asyncio
    async def test_update_persists_recalculated_metrics(self, mock_session, mock_track):
        service = TrackService(mock_session)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_track
        mock_session.execute.return_value = mock_result

        await service.create_or_update_track(
            track_id=42,
            camera_id="front_door",
            object_class="person",
            position=(300.0, 400.0),
            timestamp=datetime(2026, 1, 26, 12, 0, 30, tzinfo=UTC),
        )

        expected = TrackService.calculate_metrics(
            mock_track.trajectory[:3] + [{"x": 300.0, "y": 400.0, "timestamp": "2026-01-26T12:00:30+00:00"}]
        )
        assert mock_track.total_distance == pytest.approx(expected.total_distance)
        assert mock_track.avg_speed == pytest.approx(expected.avg_speed)

    @pytest.mark.asyncio
    async def test_history_metrics_match_trajectory(self, mock_session, mock_track):
        service = TrackService(mock_session)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_track
        mock_session.execute.return_value = mock_result

        result = await service.get_track_history(track_id=42, camera_id="front_door")

        expected = TrackService.calculate_metrics(mock_track.trajectory)
        assert result.metrics.total_distance == pytest.approx(expected.total_distance)
        assert expected.total_distance > 0  # guard: fixture is multi-point

    @pytest.mark.asyncio
    async def test_list_response_metrics_populated_from_stored(self, mock_session, mock_track):
        service = TrackService(mock_session)
        mock_track.total_distance = 125.5
        mock_track.avg_speed = 2.5
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        tracks_result = MagicMock()
        tracks_result.scalars.return_value.all.return_value = [mock_track]
        mock_session.execute.side_effect = [count_result, tracks_result]

        result = await service.get_tracks_by_camera("front_door")

        m = result.tracks[0].metrics
        assert m is not None
        expected = TrackService.calculate_metrics(mock_track.trajectory)
        assert m.total_distance == pytest.approx(expected.total_distance)

    @pytest.mark.asyncio
    async def test_list_response_metrics_none_when_avg_speed_missing(self, mock_session):
        """Source guard: metrics computed only when BOTH total_distance and avg_speed are
        stored -> avg_speed=None keeps metrics None. Kills the and->or flip and the
        guard-argument flips (they make metrics non-None on this input)."""
        service = TrackService(mock_session)
        bare = MagicMock()
        bare.id = 1
        bare.track_id = 9
        bare.camera_id = "front_door"
        bare.object_class = "person"
        bare.first_seen = bare.last_seen = datetime(2026, 1, 26, 12, 0, 0, tzinfo=UTC)
        bare.trajectory = []
        bare.total_distance = 125.5
        bare.avg_speed = None

        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        tracks_result = MagicMock()
        tracks_result.scalars.return_value.all.return_value = [bare]
        mock_session.execute.side_effect = [count_result, tracks_result]

        result = await service.get_tracks_by_camera("front_door")

        assert result.tracks[0].metrics is None

    @pytest.mark.asyncio
    async def test_list_response_metrics_computed_from_empty_trajectory(self, mock_session):
        """Both stored, trajectory empty -> branch runs calculate_metrics([]) -> zeroed
        metrics. Kills trajectory->None / calculate_metrics(None) (raise) and the
        metrics=None / metrics-removed survivors (metrics must be present here)."""
        service = TrackService(mock_session)
        bare = MagicMock()
        bare.id = 2
        bare.track_id = 10
        bare.camera_id = "front_door"
        bare.object_class = "person"
        bare.first_seen = bare.last_seen = datetime(2026, 1, 26, 12, 0, 0, tzinfo=UTC)
        bare.trajectory = []
        bare.total_distance = 125.5
        bare.avg_speed = 3.0

        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        tracks_result = MagicMock()
        tracks_result.scalars.return_value.all.return_value = [bare]
        mock_session.execute.side_effect = [count_result, tracks_result]

        result = await service.get_tracks_by_camera("front_door")

        m = result.tracks[0].metrics
        assert m is not None
        assert m.total_distance == pytest.approx(
            TrackService.calculate_metrics([]).total_distance
        )
```

### T5 — `TestMarkTrackLostFallbacks` (kills clusters 19, 20, 21; and the untested `first_seen and last_seen` guard)

```python
class TestMarkTrackLostFallbacks:
    """WP4.4: default reason + object_class fallback + duration guard — all beyond the inputs tested.

    UNVERIFIED - not yet run red/green.
    """

    @pytest.mark.asyncio
    async def test_default_reason_is_timeout(self, mock_session, mock_track):
        from unittest.mock import patch

        service = TrackService(mock_session)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_track
        mock_session.execute.return_value = mock_result

        with patch(
            "backend.services.track_service.record_track_lost", autospec=True
        ) as mock_lost, patch("backend.services.track_service.observe_track_duration", autospec=True):
            await service.mark_track_lost(track_id=42, camera_id="front_door")

        mock_lost.assert_called_once_with("front_door", "person", "timeout")

    @pytest.mark.asyncio
    async def test_missing_object_class_falls_back_to_unknown(self, mock_session, mock_track):
        from unittest.mock import patch

        mock_track.object_class = None
        service = TrackService(mock_session)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_track
        mock_session.execute.return_value = mock_result

        with patch(
            "backend.services.track_service.record_track_lost", autospec=True
        ) as mock_lost, patch("backend.services.track_service.observe_track_duration", autospec=True):
            await service.mark_track_lost(track_id=42, camera_id="front_door", reason="occlusion")

        mock_lost.assert_called_once_with("front_door", "unknown", "occlusion")

    @pytest.mark.asyncio
    async def test_duration_skipped_when_first_seen_missing(self, mock_session, mock_track):
        from unittest.mock import patch

        mock_track.first_seen = None
        service = TrackService(mock_session)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_track
        mock_session.execute.return_value = mock_result

        with patch("backend.services.track_service.record_track_lost", autospec=True), patch(
            "backend.services.track_service.observe_track_duration", autospec=True
        ) as mock_obs:
            await service.mark_track_lost(track_id=42, camera_id="front_door")

        mock_obs.assert_not_called()
```

## Appendix — per-cluster survivor indices

Keys are `backend.services.track_service.xǁTrackServiceǁ<fn>__mutmut_<idx>` (prefix elided below).
⚠ functions: indices within a family are the length-signature-DP assignment (see caveat).

| #   | Function                | Survivor indices (n)                   |
| --- | ----------------------- | -------------------------------------- |
| 1   | create_or_update_track  | 9, 10, 11, 12, 13, 14, 15, 16, 18 (9)  |
| 2   | create_or_update_track  | 21–35 (15)                             |
| 3   | create_or_update_track  | 36, 37, 74 (3)                         |
| 4   | create_or_update_track  | 71, 72, 73 (3)                         |
| 5   | create_or_update_track  | 38, 58, 75 (3)                         |
| 6   | create_or_update_track  | 39, 41–47, 59, 61–65, 76, 78–86 (24)   |
| 7   | create_or_update_track  | 55 (1)                                 |
| 8   | get_track               | 1–8, 10 (9)                            |
| 9   | get_track_history       | 2, 3, 22 (3)                           |
| 10  | get_tracks_by_camera ⚠ | 12, 18, 19, 20, 21, 23 (6)             |
| 11  | get_tracks_by_camera ⚠ | 24, 25, 40, 42, 44, 45, 46, 47, 49 (9) |
| 12  | get_tracks_by_camera ⚠ | 28, 29, 32, 33, 34, 36, 37, 38 (8)     |
| 13  | get_tracks_by_camera ⚠ | 53–60, 68, 75 (10)                     |
| 14  | prune_old_tracks        | 4, 5 (2)                               |
| 15  | prune_old_tracks        | 7, 8, 10, 12 (4)                       |
| 16  | prune_old_tracks        | 18 (1)                                 |
| 17  | prune_old_tracks        | 19, 21–27 (8)                          |
| 18  | prune_old_tracks        | 16, 17 (2)                             |
| 19  | mark_track_lost ⚠      | 2 (1)                                  |
| 20  | mark_track_lost ⚠      | 3, 9, 10, 11 (4)                       |
| 21  | mark_track_lost ⚠      | 26 (1)                                 |
| 22  | mark_track_lost ⚠      | 27, 29–37 (10)                         |
| 23  | get_active_track_count  | 2, 3 (2)                               |
| 24  | get_active_track_count  | 5–9, 11, 12, 13, 15 (9)                |
| 25  | record_reidentification | 2 (1)                                  |
| 26  | record_reidentification | 3, 5, 6, 7 (4)                         |

Totals per function: create_or_update_track 58 · get_track 9 · get_track_history 3 ·
get_tracks_by_camera 33 · mark_track_lost 16 · prune_old_tracks 17 · get_active_track_count 11 ·
record_reidentification 5 = **152**.

## Notes for the WP4.4 fix lane

- T1's `compile(literal_binds=True)` renders params inline; the default dialect is generic — if the
  project's SQLAlchemy version rejects literal_binds for a column type, fall back to `str(stmt)` plus
  `stmt.compile().params` inspection (same kill logic).
- Clusters 5, 16, 25 (EQUIVALENT, 6 keys) and 7 (EQUIVALENT, 1 key): recommend a config-level note —
  `pragma: no mutate` on the `extra=` literals or a mutmut pattern exclusion would retire ~54 of the
  152 survivors cheaply (log payload + message mutants), which is the single biggest score lift
  available for this module without new tests.
- The 4+2 coverage-gap mutants (`get_tracks_by_camera`, `mark_track_lost`) mean the _checked set_ for
  this module drifted mid-run; a full-cache regeneration at run6 resolves the numbering ambiguity —
  re-run this dossier's two ⚠ functions then (scripts kept in `/tmp/wp25/wp44-triage/track-scratch/`:
  `final_diffs.py` validates spans-signature mapping; `survivor_diffs.json` has per-key diffs).
