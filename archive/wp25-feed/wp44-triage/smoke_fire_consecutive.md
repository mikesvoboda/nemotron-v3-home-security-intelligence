# WP4.4 Triage Dossier — backend/services/smoke_fire_consecutive.py

Wave: gen-2 NEW tier (never-tallied module). Source: `backend/services/smoke_fire_consecutive.py` (418 lines).
Mutants: 161 total, 80 killed, **81 survivors** (verdict source: `mutants/backend/services/smoke_fire_consecutive.py.meta`, exit_code_by_key == 0; all keys checked, zero unchecked).
Covering test file (sole): `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_smoke_fire_consecutive.py` (773 lines; AsyncMock-based fixtures that stub `redis.get/set/exists` **argument-agnostically** — the root cause of most survivors).
Diffs extracted by diffing each `__mutmut_N` variant block in `mutants/backend/services/smoke_fire_consecutive.py` against its `__mutmut_orig` (cross-checked `uv run mutmut show` — works, consistent).

## Why the mocks let this many through
1. `redis.get = AsyncMock(return_value=<json>)` returns the same payload for ANY key → every "key identity" mutation (key=None, key=_key(None), get(None)) is invisible.
2. No test asserts the JSON written through `redis.set` (payload schema, TTL) — `assert_called()` (test file line 113) and `call_count >= 1` (line 653) are the strongest available.
3. `test_camera_redis_key_format` (line 481) asserts `"front_yard" in str(set.call_args) or "smoke_fire" in str(...)` — the `or "smoke_fire"` escape hatch always passes since the prefix is in every mutant key.
4. `to_dict` test (lines 602-605) checks only camera_id/detection_type/consecutive_count/should_alert — confidence, alert_severity, first_detection_time unchecked → schema-key mutants on those entries survive.
5. The 5-second-window tests use real `time.time()` offsets; the `<=` vs `<` flip only differs inside a 10ms epsilon band no test occupies.

## Cluster table (counts sum to 81)

| # | Cluster | Keys (fn__mutmut_N) | Count | Class | Why it survives / what it changes |
|---|---------|--------------------|-------|-------|-----------------------------------|
| C-A | State read/write round-trip through Redis unverified: get/set key identity, payload dict clobbered, dict key names renamed, downstream call args nulled | `_get_tracking_state` 1,2,4; `_set_tracking_state` 2,3,4,5,6,7,8,9,10,11,13,16,18; `track_detection` 5,54,55,56,57,58 | 22 | **TEST-GAP** | Every mutation corrupts or mis-addresses the persisted tracking state (wrong key, "XXcountXX", count=None…) so the *next* detection can never see it and the sequence resets. Tests stub `get` with a canned payload and never read back what `set` wrote, so the write side is never executed against the read side. In prod: no consecutive alert ever fires. |
| C-B | Cooldown Redis contract unasserted: key identity, value, TTL, and wrong-camera calls | `_set_cooldown` 1–9; `_is_in_cooldown` 1,2,4; `track_detection` 66,70 | 14 | **TEST-GAP** | `test_alert_sets_cooldown` asserts only `set.call_count >= 1`; `test_alert_suppressed_during_cooldown` stubs `exists` for any key. Mutants check/set cooldown on key `smoke_fire:None:cooldown` (cross-camera suppression collision) and `expire=None`/dropped → cooldown never expires → that camera is silenced forever after one alert. |
| C-C | Tracking-key TTL (300s) dropped on write | `_set_tracking_state` 14 (expire=None), 17 (expire kwarg dropped) | 2 | **TEST-GAP** | Redis keys would live forever instead of aging out in 5 min. No test asserts the `expire=` kwarg. |
| C-D | `to_dict()` output-schema key renames on unchecked entries | `to_dict` 5,6 (confidence), 11,12 (alert_severity), 13,14 (first_detection_time) | 6 | **TEST-GAP** | `test_tracking_result_to_dict` indexes only 4 of the 7 keys; renamed keys vanish from any consumer (alert pipeline) silently. |
| C-E | `track_detection` result identity / timeline unasserted | `track_detection` 3,32,36,37,51,53,88,89,90,93,99 | 11 | **TEST-GAP** | Tests assert only consecutive_count/should_alert on the returned TrackingResult; camera_id/detection_type/confidence/first_detection_time never checked, and `datetime.now(None)`/`tz=None` produce naive datetimes never checked for tzinfo (naive timestamps get `.timestamp()`-ed into Redis as local-time-shifted values). |
| C-F | Window boundary `<=` → `<` (epsilon band) | `track_detection` 45 | 1 | **TEST-GAP** | Behavioral delta only when `time_since_last` is exactly `window + 0.01` (or within float noise of it). `test_detection_exactly_at_5s_boundary` sits at ~5.000005s, far from the flip point. Needs a monkeypatched clock to kill. |
| C-G1 | Debug-log message text case/padding mutations | `track_detection` 75–87 | 13 | EQUIVALENT | `"Tracked smoke/fire detection"` → case/XX-wrapped variants and `extra={...}` dict-key renames inside a `logger.debug` call. Observability text only; no test or consumer reads it. |
| C-G2 | Debug-log call clobbers (msg→None, extra→None/dropped) | `track_detection` 71,72,74 | 3 | LOW-VALUE | `logger.debug(None)`, `extra=None`, and `logger.debug("msg")` are all valid — behavior unchanged except losing debug-level structured fields. Nobody should assert debug-log structure. |
| C-H | `state.get(key, DEFAULT)` default tweaks unreachable with payloads this module writes | `track_detection` 17,19,22 (count default 0→None/missing/1); 25,27,30 (last default 0→None/missing/1); 33,35 (first default→None/missing) | 8 | EQUIVALENT | `_set_tracking_state` always writes all four keys, so the default branch of each `.get` only fires on foreign/corrupt payloads the module itself never produces. Dead defensive tweaks (the *read-key* mutations td32/36/37 are NOT in this cluster — those change the lookup key and are real, folded into C-E). |
| C-J | `isinstance(parsed, dict)` → `(isinstance…) or True` | `_get_tracking_state` 9 | 1 | EQUIVALENT | Mutant path: `dict(<list>)` raises TypeError → outer `except Exception` → log + return None; original returns None directly. Same observable result for every input. |

Totals: TEST-GAP 56 (22+14+2+6+11+1), EQUIVALENT 22 (13+8+1), LOW-VALUE 3. Sum = 81.

## Drafted kill-tests (UNVERIFIED — not yet run red/green)

TDD procedure (one line): add each test → run against the mutant source (red on the asserted behavior change) → run against original (green); kill-proves cluster.

All target file: `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_smoke_fire_consecutive.py` (append classes; style mirrors existing async class-scoped fixtures with local imports).

```python
# // UNVERIFIED - not yet run red/green

class _KeyedFakeRedis:
    """Minimal keyed Redis double — real get/set round-trip by key string."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, expire: int | None = None) -> bool:
        self.store[key] = value
        return True

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    async def delete(self, key: str) -> int:
        return 1 if self.store.pop(key, None) is not None else 0


class TestTrackingStateRoundTrip:
    """Kills C-A (22 mutants): the write path must be readable by the read path."""

    @pytest.mark.asyncio
    async def test_second_detection_round_trips_through_redis(self) -> None:
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        redis = _KeyedFakeRedis()
        tracker = SmokeFireConsecutiveTracker(redis_client=redis)

        first = await tracker.track_detection(
            camera_id="front_yard", detection_type="smoke", confidence=0.80,
        )
        assert first.consecutive_count == 1
        assert first.should_alert is False

        # Payload schema written under the camera-scoped key
        payload = json.loads(redis.store["smoke_fire:front_yard:tracking"])
        assert set(payload) == {
            "detection_type", "count", "first_detection_time", "last_detection_time",
        }

        second = await tracker.track_detection(
            camera_id="front_yard", detection_type="smoke", confidence=0.82,
        )
        # Any key-identity/payload mutation (None key, "XXcountXX", count=None, ...)
        # makes the second call lose the state -> count 1 -> red here.
        assert second.consecutive_count == 2
        assert second.should_alert is True


class TestCooldownRedisContract:
    """Kills C-B (14 mutants): cooldown exists/set calls carry the right camera key, value, TTL."""

    @pytest.fixture
    def mock_redis_with_previous(self) -> AsyncMock:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=json.dumps({
            "detection_type": "smoke", "count": 1,
            "first_detection_time": time.time() - 2,
            "last_detection_time": time.time() - 2,
        }))
        redis.set = AsyncMock(return_value=True)
        redis.exists = AsyncMock(return_value=0)
        return redis

    @pytest.mark.asyncio
    async def test_alert_writes_cooldown_with_correct_key_value_and_ttl(
        self, mock_redis_with_previous: AsyncMock
    ) -> None:
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(
            redis_client=mock_redis_with_previous, cooldown_seconds=90,
        )
        result = await tracker.track_detection(
            camera_id="front_yard", detection_type="smoke", confidence=0.80,
        )
        assert result.should_alert is True

        cooldown_key = "smoke_fire:front_yard:cooldown"
        mock_redis_with_previous.exists.assert_awaited_once_with(cooldown_key)
        cooldown_calls = [
            c for c in mock_redis_with_previous.set.call_args_list
            if c.args and c.args[0] == cooldown_key
        ]
        assert len(cooldown_calls) == 1
        assert cooldown_calls[0].args[1] == "1"
        assert cooldown_calls[0].kwargs.get("expire") == 90


class TestTrackingStateTtl:
    """Kills C-C (2 mutants): tracking key is written with the 300s TTL."""

    @pytest.mark.asyncio
    async def test_tracking_key_written_with_ttl(self) -> None:
        from backend.services.smoke_fire_consecutive import (
            TRACKING_KEY_TTL_SECONDS, SmokeFireConsecutiveTracker,
        )

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)

        tracker = SmokeFireConsecutiveTracker(redis_client=redis)
        await tracker.track_detection(
            camera_id="front_yard", detection_type="smoke", confidence=0.80,
        )

        tracking_calls = [
            c for c in redis.set.call_args_list
            if c.args and c.args[0] == "smoke_fire:front_yard:tracking"
        ]
        assert len(tracking_calls) == 1
        assert tracking_calls[0].kwargs.get("expire") == TRACKING_KEY_TTL_SECONDS


class TestTrackingResultFullSchema:
    """Kills C-D (6 mutants): to_dict exposes every serialized field under its exact key."""

    def test_to_dict_exposes_all_fields(self) -> None:
        from backend.services.smoke_fire_consecutive import TrackingResult

        when = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = TrackingResult(
            camera_id="front_yard", detection_type="smoke", confidence=0.77,
            consecutive_count=2, should_alert=True, first_detection_time=when,
        )
        assert result.to_dict() == {
            "camera_id": "front_yard",
            "detection_type": "smoke",
            "confidence": 0.77,
            "consecutive_count": 2,
            "should_alert": True,
            "alert_severity": "high",
            "first_detection_time": when.isoformat(),
        }


class TestTrackResultIdentityAndTimeline:
    """Kills C-E (11 mutants): result echoes inputs and the sequence timeline is tz-aware."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis._client = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_first_detection_result_has_aware_timestamp(
        self, mock_redis: AsyncMock
    ) -> None:
        # kills td3 (datetime.now(None) naive)
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis)
        result = await tracker.track_detection(
            camera_id="front_yard", detection_type="smoke", confidence=0.80,
        )
        assert result.camera_id == "front_yard"
        assert result.first_detection_time.tzinfo is not None

    @pytest.mark.asyncio
    async def test_continued_sequence_preserves_identity_and_first_time(
        self, mock_redis: AsyncMock
    ) -> None:
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        prev_first = time.time() - 2.0
        mock_redis.get = AsyncMock(return_value=json.dumps({
            "detection_type": "smoke", "count": 1,
            "first_detection_time": prev_first,
            "last_detection_time": time.time() - 2.0,
        }))

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis)
        result = await tracker.track_detection(
            camera_id="front_yard", detection_type="smoke", confidence=0.82,
        )

        assert result.camera_id == "front_yard"          # kills td88
        assert result.detection_type == "smoke"          # kills td89
        assert result.confidence == 0.82                 # kills td90
        expected = datetime.fromtimestamp(prev_first, tz=UTC)
        assert result.first_detection_time.tzinfo is not None  # kills td51, td53
        assert result.first_detection_time == expected   # kills td32,36,37,93,99


class TestWindowEpsilonBoundary:
    """Kills C-F (1 mutant): the boundary is inclusive — delta == window + epsilon counts."""

    @pytest.mark.asyncio
    async def test_detection_at_window_plus_epsilon_boundary_still_counts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import backend.services.smoke_fire_consecutive as mod
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        # Exactly window_seconds + the hard-coded 10ms epsilon; float-exact because
        # both sides evaluate the literal expression 3 + 0.01 and prev_last is 0.0.
        boundary = 3 + 0.01
        monkeypatch.setattr(mod.time, "time", lambda: boundary)

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=json.dumps({
            "detection_type": "smoke", "count": 1,
            "first_detection_time": 0.0, "last_detection_time": 0.0,
        }))
        redis.set = AsyncMock(return_value=True)
        redis.exists = AsyncMock(return_value=0)

        tracker = SmokeFireConsecutiveTracker(redis_client=redis, window_seconds=3)
        result = await tracker.track_detection(
            camera_id="front_yard", detection_type="smoke", confidence=0.80,
        )
        # original: 5.01 <= 5.01 -> continue (2); mutant `<`: 5.01 < 5.01 -> reset (1)
        assert result.consecutive_count == 2
```

## Kill-mechanism notes
- C-A fake is keyed by string: every key-identity mutant stores under a key the reader never asks for; every payload/schema mutant breaks the JSON the reader parses; count/first/last=None mutants crash arithmetic/`fromtimestamp` on the second call or drop the sequence. All red on `assert second.consecutive_count == 2` (or TypeError, itself red).
- C-B `assert_awaited_once_with("smoke_fire:front_yard:cooldown")` kills exists-key mutants and `td66` (`_is_in_cooldown(None)`); the call-args triple on the cooldown `set` kills sc1–sc9 and `td70`.
- C-H default tweaks (td17/19/22/25/27/30/33/35) intentionally left EQUIVALENT: to exercise them you would need to inject payloads that deliberately lack keys this module always writes — asserting on foreign-schema tolerance is scope creep, not a test gap. (Note td22 `count` default 0→1 and td30 `last` default 0→1 are the same dead-default argument.)
- Tail noise in raw diffs for `_set_cooldown__9`, `_set_tracking_state__18`, `track_detection__99` is an extraction artifact (trailing blank line + next `def` captured in the diff region); the real mutation is the first +/- pair only.
