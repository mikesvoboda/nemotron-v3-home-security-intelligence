# WP4.4 Triage Dossier — backend/services/summary_generator.py

- **Module:** `backend/services/summary_generator.py` (501 lines, original)
- **Meta:** `mutants/backend/services/summary_generator.py.meta` — 384 keys total: **131 SURVIVED**, 123 killed, 130 still untested (run in progress as of 2026-09-18 00:56; survivor set may shift as the run checks the remainder).
- **Diffs:** all 131 via `uv run mutmut show <key>` (no failures) — raw dump at `/tmp/wp25/wp44-triage/summary_generator_diffs.txt`.
- **Sole covering test file:** `backend/tests/unit/services/test_summary_generator.py` (956 lines, `pytestmark = pytest.mark.unit`). All drafted tests below belong in this file.

## Method + data caveats

- `mutmut show` output was diffed per mutant; hourly/daily mutants were **branch-resolved** by aligning each trampoline variant body (`mutants/backend/services/summary_generator.py`, def `xǁSummaryGeneratorǁ…__mutmut_N`) line-for-line against its `__mutmut_orig` and reading the mutation's indent level: indent >= 20 = the `if session is None:` self-managed branch; indent 8 = the always-executed outer branch / shared statements.
- **Anomaly (verdicts may lie):** 29 survivors live in the session-None branch, and several of them (`summary_type=None`, kwarg-line removals) would *crash* `TestSessionManagement::test_generate_*_without_session` (AttributeError on `None.value` / TypeError on missing required arg) if those tests executed them — yet they survived. The recorded verdicts for the session-None branch look like **stale-cache survivors from an older coverage state** (WP4.3 widened-set reuse), not a real assertion gap for the crashers. WP4.4 must re-prove red/green against the current suite before deleting any drafted test as "already covered". The value-swapping survivors on that branch are genuine TEST-GAP regardless: the without-session tests assert only `result == mock_summary` + `get_session.assert_called_once()` — they never look at the window/type/session arguments being forwarded.
- Trampoline semantics (verified by reading `mutmut.mutation.trampoline`): a mutant variant runs whole-function whenever `MUTANT_UNDER_TEST` matches, so a mutant on a *non-taken* branch survives by construction — that plus the missing assertions above explains the clusters below.

## Cluster table (27 clusters, 131 survivors, sums exactly)

| # | Cluster (pattern x concern) | N | Class | Example keys (short) | Kill vector |
|---|---|---|---|---|---|
| 1 | `generate_hourly_summary`: session-None branch call args swapped to `None` / kwarg-line removed / `period_type` text / window sign flipped / `timedelta(minutes=61)` — self-managed-session path forwards window+type unasserted | 17 | TEST-GAP | `hourly__2, hourly__3, hourly__12` | D1 (without-session half) |
| 2 | `generate_daily_summary`: same family, session-None branch | 12 | TEST-GAP | `daily__17, daily__18, daily__27` | D2 (without-session half) |
| 3 | `generate_hourly_summary`: outer-branch args (`session=None`, `period_type` "HOUR"/"XXhourXX"/None, `datetime.now(None)`, window `+timedelta(60)`/`61`/naive) — executed via every session-passing test but values never asserted | 8 | TEST-GAP | `hourly__19, hourly__29, hourly__34` | D1 (session half) |
| 4 | `generate_daily_summary`: outer-branch args incl. `now=datetime.now(None)`, `midnight_today` `microsecond` kwarg removed (-> microseconds leak into `window_start`) / `microsecond=1` | 7 | TEST-GAP | `daily__2, daily__11, daily__15` | D2 (session half; assert `microsecond == 0`) |
| 5 | `_generate_summary`: `_call_nemotron(...)` kwargs -> `None` (42-45) / lines removed (46-49) — prompt inputs (window, `period_type`, events) forwarded unasserted; existing tests mock `_call_nemotron` but only `assert_called_once()` | 8 | TEST-GAP | `_generate_summary__42, __44, __48` | D1 (nemotron kwargs assert) |
| 6 | `_generate_summary`: `event_context = None` (24) -> `events=None` into nemotron | 1 | TEST-GAP | `_generate_summary__24` | D1 |
| 7 | `_generate_summary`: `EventRepository(None)` (2) / `SummaryRepository(None)` (64) — session plumbing into repos unasserted | 2 | TEST-GAP | `_generate_summary__2, __64` | D1/D2 (`mock_repo_cls.assert_called_once_with(session)`) |
| 8 | `_generate_summary`: `create_summary(window_start/window_end = None or removed)` (70,71,77,78) — stored window lost; existing tests assert only `summary_type/event_count/event_ids` | 4 | TEST-GAP | `_generate_summary__70, __77` | D1/D2 (create kwargs identity vs captured repo window) |
| 9 | `_generate_summary`: `generated_at = None` / `datetime.now(None)` (26,27) and `generated_at=None`/removed in create_summary (72,79) | 4 | TEST-GAP | `_generate_summary__26, __72` | D1 (create-kwargs `generated_at` assert) |
| 10 | Event-query window_end lost: `get_in_date_range(window_start, None, ...)` inside `_get_high_critical_events` (3) and `_get_high_critical_events(repo, ws, None)` in `_generate_summary` (6) — `test_generate_daily_summary_time_window` captures `end` but asserts only `start.hour/minute/second` | 2 | TEST-GAP | `_get_high_critical_events__3, _generate_summary__6` | D1 capture (assert end not None + ~now) |
| 11 | `_get_high_critical_events`: `eager_load_camera=True` -> `None`/`False`/removed (4,7,8) — the flag exists specifically to avoid async lazy-load crashes; capture side-effect receives it but never asserts it | 3 | TEST-GAP | `_get_high_critical_events__4, __7, __8` | D1 capture signature assert |
| 12 | `_generate_summary` logging: f-string message -> `None` (12,32,50,82) | 4 | EQUIVALENT | `__12, __50` | — (msg param positional; None log record, no behavior) |
| 13 | `_generate_summary` logging: `extra=` dict removed / `extra=None` (13,15,33,35,51,53,83,85) | 8 | LOW-VALUE | `__13, __33` | — (structured-log enrichment; no test consumer) |
| 14 | `_generate_summary` logging: `extra` dict *keys* XX-clobbered / uppercased (across the 4 log sites) | 26 | LOW-VALUE | `__16, __54, __86` | — |
| 15 | `_generate_summary` logging: `extra["event_count"] = 0 -> 1` (40) | 1 | LOW-VALUE | `__40` | — |
| 16 | `_generate_summary` logging: `extra["error"] = str(e) -> str(None)` (58) | 1 | EQUIVALENT | `__58` | — |
| 17 | `_build_event_context`: `strftime("%I:%M %p")` format string clobbered/lowercase (6,7,8) | 3 | TEST-GAP | `build__6, build__7, build__8` | D3 (literal expected `"02:15 PM"`) |
| 18 | `_build_event_context`: `"Unknown time"` fallback text (9,10,11) | 3 | TEST-GAP | `build__9, build__10` | D3 |
| 19 | `_build_event_context`: `"timestamp"` dict key -> `"XXtimestampXX"`/`"TIMESTAMP"` (24,25) — would break `build_summary_prompt` render | 2 | TEST-GAP | `build__24, build__25` | D3 (exact key set) |
| 20 | `_build_event_context`: `timestamp = None` (2) | 1 | TEST-GAP | `build__2` | D3 |
| 21 | `_build_event_context`: ternary condition `if (event.started_at) and False` / `or True` (3,4) | 2 | EQUIVALENT | `build__3, build__4` | — (identical outcome; would be a live gap only if a test drove `started_at=None`, which none does — D3 adds one) |
| 22 | `_build_event_context`: `risk_level or "unknown"` fallback text (31,32) | 2 | TEST-GAP | `build__31, build__32` | D3 (falsy-field event, exact strings) |
| 23 | `_build_event_context`: `risk_score or 0` -> `or 1` (36) | 1 | TEST-GAP | `build__36` | D3 |
| 24 | `_build_event_context`: `summary or "No summary available"` fallback text (40,41,42) | 3 | TEST-GAP | `build__40, build__42` | D3 |
| 25 | `_build_event_context`: `object_types or "Unknown objects"` fallback text (46,47,48) | 3 | TEST-GAP | `build__46, build__48` | D3 |
| 26 | `get_summary_generator`: `if _summary_generator is not None:` (1) / `_summary_generator = None` (2) — factory returns `None` yet test passes because it only asserts `generator1 is generator2` (`None is None` holds) | 2 | TEST-GAP | `x_get_summary_generator__1, __2` | D4 |
| 27 | `_get_fallback_content`: zero-event all-clear string XX-wrapped (3) — user-facing dashboard text; test asserts only substrings `"No high-priority"`/`"quiet"` | 1 | TEST-GAP | `fallback__3` | D5 (exact equality) |

**Classification rollup:** TEST-GAP 91, LOW-VALUE 35, EQUIVALENT 5 -> 131.

### Why the big clusters read as TEST-GAP rather than "not worth asserting"
- Clusters 1-4: the window arithmetic (`now-60min`, midnight truncation) and `period_type`/`summary_type` routing are the *product* (a wrong window silently summarizes the wrong events; `"HOUR"` would render wrong prompt text). Tests capture the daily window but assert only hour/min/sec of start.
- Clusters 5-11: `_generate_summary` has 60 survivors; 39 of them are pure logging (classified LOW-VALUE/EQUIVALENT) and the remaining 21 are call-argument forwarding into `_call_nemotron`/repos/`create_summary` — the mock-based tests assert call *counts* but almost never call *args*.
- Cluster 21: `and False`/`or True` on a truthiness guard are behavior-identical -> EQUIVALENT; kept separate from the format-text clusters deliberately.

## Drafted tests (5 tests kill 91 TEST-GAP survivors)

Add to `backend/tests/unit/services/test_summary_generator.py`.
**TDD procedure (one line):** run each test with the cluster's mutant active (`MUTANT_UNDER_TEST=<key>`) — the new assertion must go red on the mutant diff and green on the original; a crash/TypeError under the mutant also counts as red.
**// UNVERIFIED - not yet run red/green**

### D1 — hourly: window, period, session, stored args on BOTH session paths
Kills clusters 1, 3, 5, 6, 7, 8, 9, 10 (hourly half), 11.

```python
    @pytest.mark.asyncio
    async def test_generate_hourly_summary_arguments(
        self,
        mock_session: MagicMock,
        mock_event: MagicMock,
        mock_summary: MagicMock,
    ) -> None:
        """Hourly summary must forward the 60-minute window, session and period to every layer.

        // UNVERIFIED - not yet run red/green
        """
        generator = SummaryGenerator(llm_url="http://localhost:8091")
        captured: dict[str, object] = {}

        async def capture_date_range(
            start: datetime, end: datetime, *, eager_load_camera: bool = False
        ) -> list[MagicMock]:
            captured["start"] = start
            captured["end"] = end
            captured["eager"] = eager_load_camera
            return [mock_event]

        # --- path A: caller-provided session (outer branch) ---
        nemotron = AsyncMock(return_value="Summary text.")
        with (
            patch("backend.services.summary_generator.EventRepository", autospec=True) as ev_cls,
            patch(
                "backend.services.summary_generator.SummaryRepository", autospec=True
            ) as su_cls,
            patch.object(generator, "_call_nemotron", new=nemotron),
        ):
            ev_repo = MagicMock()
            ev_repo.get_in_date_range = AsyncMock(side_effect=capture_date_range)
            ev_cls.return_value = ev_repo
            su_repo = MagicMock()
            su_repo.create_summary = AsyncMock(return_value=mock_summary)
            su_cls.return_value = su_repo

            await generator.generate_hourly_summary(session=mock_session)

            ev_cls.assert_called_once_with(mock_session)  # kills EventRepository(None)
            assert captured["end"] is not None  # kills window_end=None
            assert captured["eager"] is True  # kills eager_load_camera False/None/removed
            delta = (captured["end"] - captured["start"]).total_seconds()
            # naive datetime (datetime.now(None)) makes the above subtraction raise TypeError = kill
            assert delta == pytest.approx(3600, abs=5)  # kills 61min, +60min
            assert captured["end"].tzinfo is UTC

            nk = nemotron.call_args.kwargs
            assert nk["window_start"] == captured["start"]
            assert nk["window_end"] == captured["end"]
            assert nk["period_type"] == "hour"  # kills "HOUR"/"XXhourXX"/None
            assert nk["events"] is not None and len(nk["events"]) == 1  # kills events=None/event_context=None

            ck = su_repo.create_summary.call_args.kwargs
            assert ck["window_start"] == captured["start"]
            assert ck["window_end"] == captured["end"]  # kills create-summary window=None/removals
            assert ck["generated_at"] is not None
            assert ck["generated_at"].tzinfo is UTC
            assert abs((ck["generated_at"] - captured["end"]).total_seconds()) < 5.0

        # --- path B: self-managed session (session-None branch) ---
        captured.clear()
        db_session = MagicMock()
        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=db_session)
        session_ctx.__aexit__ = AsyncMock()
        nemotron = AsyncMock(return_value="Summary text.")
        with (
            patch("backend.services.summary_generator.get_session") as get_session_mock,
            patch("backend.services.summary_generator.EventRepository", autospec=True) as ev_cls,
            patch(
                "backend.services.summary_generator.SummaryRepository", autospec=True
            ) as su_cls,
            patch.object(generator, "_call_nemotron", new=nemotron),
        ):
            get_session_mock.return_value = session_ctx
            ev_repo = MagicMock()
            ev_repo.get_in_date_range = AsyncMock(side_effect=capture_date_range)
            ev_cls.return_value = ev_repo
            su_repo = MagicMock()
            su_repo.create_summary = AsyncMock(return_value=mock_summary)
            su_cls.return_value = su_repo

            await generator.generate_hourly_summary(session=None)

            ev_cls.assert_called_once_with(db_session)  # kills session=None forward into EventRepository
            assert captured["eager"] is True
            assert (captured["end"] - captured["start"]).total_seconds() == pytest.approx(3600, abs=5)
            assert nemotron.call_args.kwargs["period_type"] == "hour"
            assert su_repo.create_summary.call_args.kwargs["window_start"] == captured["start"]
```

### D2 — daily: midnight window (microsecond!), period, summary type, session, stored args, both paths
Kills clusters 2, 4, 7 (daily half), 8 (daily half), 9 (daily half), 10, 11 (daily half).

```python
    @pytest.mark.asyncio
    async def test_generate_daily_summary_arguments(
        self,
        mock_session: MagicMock,
        mock_event: MagicMock,
        mock_summary: MagicMock,
    ) -> None:
        """Daily window is exactly midnight->now and all forwarded args keep their values.

        // UNVERIFIED - not yet run red/green
        """
        generator = SummaryGenerator(llm_url="http://localhost:8091")
        captured: dict[str, object] = {}

        async def capture_date_range(
            start: datetime, end: datetime, *, eager_load_camera: bool = False
        ) -> list[MagicMock]:
            captured["start"] = start
            captured["end"] = end
            captured["eager"] = eager_load_camera
            return [mock_event]

        # --- path A: caller-provided session ---
        nemotron = AsyncMock(return_value="Daily text.")
        with (
            patch("backend.services.summary_generator.EventRepository", autospec=True) as ev_cls,
            patch(
                "backend.services.summary_generator.SummaryRepository", autospec=True
            ) as su_cls,
            patch.object(generator, "_call_nemotron", new=nemotron),
        ):
            ev_repo = MagicMock()
            ev_repo.get_in_date_range = AsyncMock(side_effect=capture_date_range)
            ev_cls.return_value = ev_repo
            su_repo = MagicMock()
            su_repo.create_summary = AsyncMock(return_value=mock_summary)
            su_cls.return_value = su_repo

            await generator.generate_daily_summary(session=mock_session)

            ev_cls.assert_called_once_with(mock_session)
            s, e = captured["start"], captured["end"]
            assert (s.hour, s.minute, s.second, s.microsecond) == (0, 0, 0, 0)
            # kills microsecond kwarg removed (now keeps real microsecs) and microsecond=1
            assert e.tzinfo is UTC  # kills now = datetime.now(None)
            assert e >= s
            assert captured["eager"] is True
            assert nemotron.call_args.kwargs["period_type"] == "day"
            ck = su_repo.create_summary.call_args.kwargs
            assert ck["summary_type"] == SummaryType.DAILY
            assert ck["window_start"] == s
            assert ck["window_end"] == e
            assert ck["generated_at"] is not None

        # --- path B: self-managed session ---
        captured.clear()
        db_session = MagicMock()
        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=db_session)
        session_ctx.__aexit__ = AsyncMock()
        nemotron = AsyncMock(return_value="Daily text.")
        with (
            patch("backend.services.summary_generator.get_session") as get_session_mock,
            patch("backend.services.summary_generator.EventRepository", autospec=True) as ev_cls,
            patch(
                "backend.services.summary_generator.SummaryRepository", autospec=True
            ) as su_cls,
            patch.object(generator, "_call_nemotron", new=nemotron),
        ):
            get_session_mock.return_value = session_ctx
            ev_repo = MagicMock()
            ev_repo.get_in_date_range = AsyncMock(side_effect=capture_date_range)
            ev_cls.return_value = ev_repo
            su_repo = MagicMock()
            su_repo.create_summary = AsyncMock(return_value=mock_summary)
            su_cls.return_value = su_repo

            await generator.generate_daily_summary(session=None)

            ev_cls.assert_called_once_with(db_session)  # kills daily session=None (mutmut_17)
            s = captured["start"]
            assert (s.hour, s.minute, s.second, s.microsecond) == (0, 0, 0, 0)
            assert nemotron.call_args.kwargs["period_type"] == "day"
            assert su_repo.create_summary.call_args.kwargs["summary_type"] == SummaryType.DAILY
            # NOTE: summary_type=None / kwarg-removal variants on this branch crash on
            # `None.value` inside _generate_summary before reaching these asserts — crash = kill.
```

### D3 — `_build_event_context`: exact dict, both branches of every `or` fallback
Kills clusters 17, 18, 19, 20, 22, 23, 24, 25 (18 mutants).

```python
    def test_build_event_context_exact_keys_and_fallbacks(self) -> None:
        """Context dict keys and all sentinel strings are part of the LLM prompt contract.

        // UNVERIFIED - not yet run red/green
        """
        generator = SummaryGenerator()

        # Full event: timestamp format must be exactly %I:%M %p
        full = MagicMock(spec=Event)
        full.started_at = datetime(2026, 1, 18, 14, 15, 0, tzinfo=UTC)
        full.camera_id = "front_door"
        full.camera = MagicMock()
        full.camera.name = "Front Door"
        full.risk_level = "high"
        full.risk_score = 75
        full.summary = "Person at door"
        full.object_types = "person"

        ctx = generator._build_event_context([full])
        assert set(ctx[0]) == {
            "timestamp",
            "camera_name",
            "risk_level",
            "risk_score",
            "summary",
            "object_types",
        }  # kills "XXtimestampXX"/"TIMESTAMP" key mutants
        assert ctx[0]["timestamp"] == "02:15 PM"  # kills strftime format variants, timestamp=None

        # Falsy event: every `or` sentinel fires; started_at=None exercises the fallback branch
        empty = MagicMock(spec=Event)
        empty.started_at = None
        empty.camera_id = "cam9"
        empty.camera = None
        empty.risk_level = None
        empty.risk_score = None
        empty.summary = None
        empty.object_types = None

        ctx2 = generator._build_event_context([empty])
        assert ctx2[0]["timestamp"] == "Unknown time"  # kills "unknown time"/"UNKNOWN TIME"/XX-wrap
        assert ctx2[0]["camera_name"] == "cam9"
        assert ctx2[0]["risk_level"] == "unknown"  # kills "XXunknownXX"/"UNKNOWN"
        assert ctx2[0]["risk_score"] == 0  # kills `or 1`
        assert ctx2[0]["summary"] == "No summary available"  # kills text-case variants
        assert ctx2[0]["object_types"] == "Unknown objects"  # kills text-case variants
```

### D4 — singleton factory must return an instance, not `None`
Kills cluster 26 (both mutants).

```python
    def test_get_summary_generator_returns_real_instance(self) -> None:
        """The factory must construct and cache a SummaryGenerator (not None).

        // UNVERIFIED - not yet run red/green
        """
        import backend.services.summary_generator as module

        module._summary_generator = None

        generator = get_summary_generator()

        assert isinstance(generator, SummaryGenerator)  # None -> fails on both mutants
        assert get_summary_generator() is generator
```

### D5 — all-clear fallback text is exact (dashboard-visible copy)
Kills cluster 27.

```python
    def test_fallback_content_all_clear_exact_text(self) -> None:
        """All-clear message is shown verbatim on the dashboard — assert exact copy.

        // UNVERIFIED - not yet run red/green
        """
        generator = SummaryGenerator()

        assert generator._get_fallback_content(event_count=0) == (
            "No high-priority security events detected in this period. "
            "The property has been quiet."
        )
```

### Coverage arithmetic
D1 covers clusters 1(17)+3(8)+5(8)+6(1)+10(2)+11(3) plus the hourly halves of 7,8,9 -> >=40 killed outright. D2 covers clusters 2(12)+4(7)+daily halves of 7,8,9. D3: 18 (clusters 17,18,19,20,22,23,24,25). D4: 2. D5: 1. Clusters 7/8/9/10/11 are double-killed by D1+D2, so all 91 TEST-GAP survivors are covered; the 40 LOW-VALUE/EQUIVALENT logging/text mutants stay intentionally unkilled (documented as such).

## Covering test file map (file:line)

| Concern | Test file | Lines | What it asserts / misses |
|---|---|---|---|
| hourly/daily generation | `backend/tests/unit/services/test_summary_generator.py` | 130-378 | counts + `summary_type`/`event_count`/`event_ids` kwargs; window values, `period_type`, `generated_at`, session identity, `eager_load_camera` all missed |
| daily time window | same | 330-378 | captures `start`/`end` but asserts only `start.hour/minute/second` (no microsecond, nothing on `end`) |
| fallback behavior | same | 437-552 | substring checks on content only |
| event context | same | 558-617 | happy-path fields only; no falsy-field event, no `timestamp` key/format assert |
| fallback content text | same | 623-642 | substring asserts (`"No high-priority"`, `"quiet"`) — XX-wrapped string passes |
| singleton | same | 648-661 | identity only (`None is None` passes) |
| session management | same | 808-956 | result identity + `get_session.assert_called_once()` only |

## Notes for WP4.4
1. **Red-prove first:** the 29 session-None-branch survivors look like stale-cache verdicts — several (kwarg removals, `summary_type=None`) *should* crash the current without-session tests. If they flip to killed on a fresh run, D1/D2 path-B blocks become redundant-but-harmless.
2. 130 keys in this module's meta are still `null` (run in progress). Clusters 12-16 (log family, ~35) will likely grow as more of the 60-key `_generate_summary` set is checked; if so it is further LOW-VALUE/EQUIVALENT bulk, not new TEST-GAP.
3. `_call_nemotron` has **0 survivors among checked keys** (payload/ChatML building not yet evaluated) — flag for the next wave: its `max_tokens=256`/`temperature=0.3`/stop-token constants will likely yield a real TEST-GAP ("request payload never asserted") once checked.
