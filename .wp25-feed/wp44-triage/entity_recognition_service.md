# WP4.4 Triage Dossier — backend/services/entity_recognition_service.py

- **Survivors:** 56 (of 140 checked: 84 killed, 0 unchecked)
- **Survivor functions:** `get_face_stats` (25), `get_vehicle_stats` (29), `get_hourly_stats` (2)
- **Covering test file:** `backend/tests/unit/services/test_entity_recognition_service.py`
- **Root cause of every SQL survivor:** the tests stub `session.execute` with `AsyncMock`
  and only assert on the *returned* `PersonStats`/`VehicleStats` counts. They never inspect
  the statement object handed to `session.execute`, so any change to the SQL (window clauses,
  operators, `trusted` filter, `group_by`, select-list, or even passing `None` to `execute`)
  is invisible to them. **TEST-GAP** (line executed, statement never asserted).
- **Root cause of every logger survivor:** `logger.debug(...)` argument/message mutations
  cannot change the returned counts, and logging swallows %-format mismatches, so they are
  EQUIVALENT (message-text case/wrapper) or LOW-VALUE (arg clobbered/dropped — nobody should
  assert debug-log contents).

## Cluster table

| # | Pattern | Count | Class | Example keys |
|---|---------|-------|-------|--------------|
| F1 | `get_face_stats`: window WHERE clause / whole statement clobbered to `None` | 3 | TEST-GAP | `…get_face_stats__mutmut_1`, `_3`, `_4` |
| F2 | `get_face_stats`: comparison operator flipped on timestamp bounds (`>=`→`>`, `<`→`<=`) | 2 | TEST-GAP | `…get_face_stats__mutmut_10`, `_11` |
| F3 | `get_face_stats`: `select`-list / `group_by` / `count()` clobbered | 6 | TEST-GAP | `…get_face_stats__mutmut_2`, `_5`, `_7` |
| F4 | `get_face_stats`: `session.execute(None)` | 1 | TEST-GAP | `…get_face_stats__mutmut_13` |
| V1 | `get_vehicle_stats`: household `trusted.is_(True)` / `license_plate.isnot(None)` removed or flipped | 6 | TEST-GAP | `…get_vehicle_stats__mutmut_3`, `_7`, `_8` |
| V2 | `get_vehicle_stats`: household statement / `select` / `execute` clobbered to `None` | 3 | TEST-GAP | `…get_vehicle_stats__mutmut_1`, `_6`, `_10` |
| V3 | `get_vehicle_stats`: plate-window WHERE clauses removed/`None` or operator flipped | 4 | TEST-GAP | `…get_vehicle_stats__mutmut_14`, `_17`, `_18` |
| V4 | `get_vehicle_stats`: plate statement / `select` / `execute` clobbered to `None` | 3 | TEST-GAP | `…get_vehicle_stats__mutmut_13`, `_16`, `_20` |
| H1 | `get_hourly_stats`: `datetime.now(UTC)`→`now(None)` and session forwarding→`None` | 2 | TEST-GAP | `…get_hourly_stats__mutmut_2`, `_7` |
| L1 | `logger.debug` arg replaced with `None` (face + vehicle) | 10 | LOW-VALUE | `…get_face_stats__mutmut_21`, `…get_vehicle_stats__mutmut_29` |
| L2 | `logger.debug` arg dropped entirely (face + vehicle) | 10 | LOW-VALUE | `…get_face_stats__mutmut_26`, `…get_vehicle_stats__mutmut_34` |
| E1 | `logger.debug` message-text casing/wrapping (face + vehicle) | 6 | EQUIVALENT | `…get_face_stats__mutmut_31`, `_32`, `_33` |

Totals: TEST-GAP 30, LOW-VALUE 20, EQUIVALENT 6 = 56.

### Notes
- **F2** is the classic timestamp-freshness boundary flip (`>=`→`>`, `<`→`<=`). With a real DB it
  silently excludes a read landing exactly on `window_start` / includes one exactly on `window_end`.
- **V1** (`trusted.is_(True)` → `is_(False)`/`is_(None)`, and dropping `isnot(None)`) changes which
  vehicles count as "known" — a genuine security-relevant behavior flip that no test can see.
- **H1** mutmut_2 (`now(None)`) produces a *naive* `window_end`; the existing test only checks the
  delta is ~1h, which a naive window still satisfies. Needs a tz-awareness assertion.
- **L1/L2** (`logger.debug` args → `None` or removed): logging formats/`handleError`s internally and
  never raises, and it cannot affect the return value — asserting on debug-log contents would be
  brittle noise. **E1** is pure message-text casing. All are non-assertable.

## Drafted tests (highest-value TEST-GAP clusters)

All four target `backend/tests/unit/services/test_entity_recognition_service.py`, added inside
`class TestEntityRecognitionService`. Style matches existing async tests (project uses
`asyncio_mode = "auto"`, so no decorator). They assert on the **statement passed to the mocked
`session.execute`** — the single blind spot that leaves 30 mutants alive.

**TDD procedure (one line):** run each test against the mutant copy (assert fails red on the
mutated SQL string / `None` arg), then against the original source (passes green).

### Draft 1 — face SQL shape (kills F1 + F2 + F3 + F4: face_1,2,3,4,5,6,7,8,9,10,11,13)

```python
async def test_get_face_stats_builds_expected_grouped_windowed_query(
    self,
    service: EntityRecognitionService,
    mock_session: AsyncMock,
) -> None:
    """get_face_stats must issue a windowed, is_unknown-grouped COUNT query.

    The service-level tests stub session.execute and never inspect the statement,
    so window-clause removal, timestamp operator flips, and select/group_by
    clobbers all survive. Assert the exact compiled SQL handed to execute().
    """
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.execute.return_value = mock_result

    window_start = datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC)
    window_end = datetime(2026, 2, 3, 11, 0, 0, tzinfo=UTC)

    await service.get_face_stats(mock_session, window_start, window_end)

    stmt = mock_session.execute.call_args[0][0]
    compiled = " ".join(str(stmt).split())
    assert compiled == (
        "SELECT face_detection_events.is_unknown, "
        "count(face_detection_events.id) AS count_1 "
        "FROM face_detection_events "
        "WHERE face_detection_events.timestamp >= :timestamp_1 "
        "AND face_detection_events.timestamp < :timestamp_2 "
        "GROUP BY face_detection_events.is_unknown"
    )
```

### Draft 2 — vehicle household query (kills V1 + V2: veh_1,2,3,4,5,6,7,8,10)

```python
async def test_get_vehicle_stats_selects_trusted_registered_plates(
    self,
    service: EntityRecognitionService,
    mock_session: AsyncMock,
) -> None:
    """get_vehicle_stats household query must filter on non-null, trusted plates.

    `trusted.is_(True)` flipped to is_(False)/is_(None) or dropped silently changes
    which vehicles count as 'known' — a security-relevant filter the count-only
    tests cannot observe. Assert the compiled household SQL (first execute call).
    """
    household_result = MagicMock()
    household_result.scalars.return_value.all.return_value = []
    plates_result = MagicMock()
    plates_result.scalars.return_value.all.return_value = []
    mock_session.execute.side_effect = [household_result, plates_result]

    window_start = datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC)
    window_end = datetime(2026, 2, 3, 11, 0, 0, tzinfo=UTC)

    await service.get_vehicle_stats(mock_session, window_start, window_end)

    household_stmt = mock_session.execute.call_args_list[0][0][0]
    compiled = " ".join(str(household_stmt).split())
    assert compiled == (
        "SELECT registered_vehicles.license_plate "
        "FROM registered_vehicles "
        "WHERE registered_vehicles.license_plate IS NOT NULL "
        "AND registered_vehicles.trusted IS true"
    )
```

### Draft 3 — vehicle plate window query (kills V3 + V4: veh_13,14,15,16,17,18,20)

```python
async def test_get_vehicle_stats_window_query_filters_plate_reads(
    self,
    service: EntityRecognitionService,
    mock_session: AsyncMock,
) -> None:
    """get_vehicle_stats plate query must window plate_reads by [start, end).

    Asserts the second execute() gets the windowed select (kills clause removal,
    operator flips, and None clobbers of the plate statement).
    """
    household_result = MagicMock()
    household_result.scalars.return_value.all.return_value = []
    plates_result = MagicMock()
    plates_result.scalars.return_value.all.return_value = []
    mock_session.execute.side_effect = [household_result, plates_result]

    window_start = datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC)
    window_end = datetime(2026, 2, 3, 11, 0, 0, tzinfo=UTC)

    await service.get_vehicle_stats(mock_session, window_start, window_end)

    plates_stmt = mock_session.execute.call_args_list[1][0][0]
    compiled = " ".join(str(plates_stmt).split())
    assert compiled == (
        "SELECT plate_reads.plate_text FROM plate_reads "
        "WHERE plate_reads.timestamp >= :timestamp_1 "
        "AND plate_reads.timestamp < :timestamp_2"
    )
```

### Draft 4 — hourly window tz + session forwarding (kills H1: hourly_2, hourly_7)

```python
async def test_get_hourly_stats_uses_tz_aware_now_and_forwards_session(
    self,
    service: EntityRecognitionService,
    mock_session: AsyncMock,
) -> None:
    """get_hourly_stats must build a UTC-aware 1h window and forward the session.

    The existing window test only checks the ~1h delta, so datetime.now(None)
    (a naive window_end) and dropping the session arg both survive. Assert
    tz-awareness and that the real session is forwarded to get_summary_stats.
    """
    with patch.object(
        service,
        "get_summary_stats",
        return_value=EntityRecognitionStats(
            persons=PersonStats(known=0, unknown=0),
            vehicles=VehicleStats(known=0, unknown=0),
            window_start=datetime.now(UTC),
            window_end=datetime.now(UTC),
        ),
        autospec=True,
    ) as mock_summary:
        await service.get_hourly_stats(mock_session)

        args = mock_summary.call_args[0]
        assert args[0] is mock_session          # kills get_summary_stats(None, ...)
        window_start, window_end = args[1], args[2]
        assert window_end.tzinfo is not None    # kills datetime.now(None) naive
        assert window_start.tzinfo is not None
        assert timedelta(minutes=59) < (window_end - window_start) < timedelta(hours=1, seconds=5)
```

## Verification status
Drafts are **UNVERIFIED — not yet run red/green** (no test execution permitted in this run).
Compiled-SQL strings above were generated read-only against the live SQLAlchemy models
(`str(stmt)` default dialect) so the expected strings match the original source exactly.
