# WP4.4 Triage Dossier — backend/services/ai_fallback.py

**Source:** `backend/services/ai_fallback.py` (705 lines)
**Covering test file (sole):** `backend/tests/unit/services/test_ai_fallback.py` (1061 lines)
**Meta:** `mutants/backend/services/ai_fallback.py.meta` — 292 total keys, **70 survivors** (exit_code 0). All 70 diffs pulled via `uv run mutmut show <key>` (all succeeded, 0 fallbacks).
**Status: UNVERIFIED — no tests were run (live mutation run owns the machine).**

## Key test-file landmarks (file:line)

| Concern | Location in `backend/tests/unit/services/test_ai_fallback.py` |
|---|---|
| Fixtures (`fallback_service`, 4 mock clients) | :49–103 |
| `TestRiskScoreCache` (TTL tests use real sleep) | :270–327 (`test_get_cached_score_expired` :294) |
| `TestAIFallbackServiceInit` | :335–377 |
| `TestStatusCallbacks` (`assert_called_once` only, never args) | :412–466 |
| `TestLifecycleManagement` (start/stop/loop; no `get_name()` assert) | :474–535 |
| `TestHealthChecks` (`test_perform_health_check_*` assert bare `result is True`) | :543–677 (:623–651) |
| `TestDegradationLevel` (only threshold-level outputs) | :733–764 |
| `TestAvailableFeatures` (membership asserts miss 2 entries) | :772–822 |
| `TestDegradationStatus` (key-presence only, timestamp never parsed) | :830–856 |
| `TestGetFallbackRiskAnalysisMethod` (weak substring asserts) | :864–912 |
| `TestFallbackCaption` (weak substring asserts) | :926–955 |
| Task-name precedent elsewhere in repo | `backend/tests/unit/services/test_health_monitor.py:69,94` |

## Cluster table (counts sum to 70)

| # | Pattern | Count | Class | Example keys (≤3) | Note |
|---|---|---|---|---|---|
| C1 | Lifecycle logger text/extra clobber (`logger.info/warning("AIFallbackService initialized/started/stopped/already running")` → None/XX/lower/UPPER, `extra=` dict tweaks) in `__init__`/`start`/`stop` | 20 | EQUIVALENT | `__init__…__mutmut_16`, `start__mutmut_1`, `stop__mutmut_6` | Pure log content; no test inspects records. `extra=None`/dropped kwarg is the stdlib default anyway. |
| C2 | Diagnostic log-only mutants in status path: `check_all_services__9` (log msg→None), `notify_status_change__3/4/6/7` (msg→None, `exc_info` True→None/dropped/False), `register_circuit_breaker__2` (`debug(None)`) | 6 | EQUIVALENT | `notify_status_change__mutmut_4` | Changes traceback rendering only; surviving proves handlers don't crash on None msg. |
| C3 | Dead-field / falsy sentinel in `__init__`: `_health_check_task` `None`→`""` (mutmut_13), `_lock = asyncio.Lock()`→`None` (mutmut_14) | 2 | EQUIVALENT | `__init__…__mutmut_14` | `_lock` is never referenced anywhere in the repo (grep: only the creation line, ai_fallback.py:273). `""` is falsy ≡ `None` in every consumer (`stop()` guards on `_running`; `start()` overwrites before any read); no test asserts `is None` pre-start. |
| C4 | `status_changed = False`→`None` init in `_check_all_services` (mutmut_1) | 1 | EQUIVALENT | `check_all_services__mutmut_1` | Only feeds `if status_changed:`; `None` falsy ≡ `False`. |
| C5 | `break`→`return` in `CancelledError` handler of `_health_check_loop` (mutmut_2) | 1 | EQUIVALENT | `health_check_loop__mutmut_2` | Loop is the final statement — `break` falls through to implicit `return None`; literally identical control flow. |
| C6 | Dead guard branch in `get_fallback_risk_analysis` estimate: `if scores else` → `if (scores) or True` (mutmut_16); else-const 50→51 (mutmut_20) | 2 | EQUIVALENT | `get_fallback_risk_analysis__mutmut_20` | Inside `if object_types:`, the list-comp `scores` is never empty — the else-branch was already unreachable in the original. |
| C7 | Dropped default-arg kwarg `source="default"` (mutmut_36) | 1 | EQUIVALENT | `get_fallback_risk_analysis__mutmut_36` | Dataclass default IS `"default"`; verified `FallbackRiskAnalysis().source == 'default'`. |
| C8 | Internal counter magnitude in `get_degradation_level`: `non_critical_unavailable` `+=`→`= 1` (mutmut_10), `+= 1`→`+= 2` (mutmut_12) | 2 | EQUIVALENT | `get_degradation_level__mutmut_10` | Only consumer is `> 0` threshold; any mutation preserves the boolean outcome for every service combo. |
| C9 | `RiskScoreCache.get_cached_score` missing-timestamp default: `get(cam, 0)`→`None`/omitted (mutmut_4, _6 → TypeError on orphan) / `1` (mutmut_7 ≈ orig since monotonic()≫301) | 3 | LOW-VALUE | `get_cached_score__mutmut_4` | Orphan entry (score without timestamp) is unreachable via public API — `set_cached_score` always writes both dicts in lockstep (ai_fallback.py:176–179). Nobody should assert crash-vs-expire on internal dict surgery. |
| C10 | `_health_check_loop` sleep arg `self._health_check_interval`→`None` (mutmut_1): `sleep(None)` raises TypeError **inside the try**, the `except Exception` recovery handler re-sleeps with the real interval, so the loop keeps running and the existing loop test passes | 1 | TEST-GAP | `health_check_loop__mutmut_1` | Gap: no test asserts a healthy loop logs no "Health check loop error" (caplog), so a crash-loop-with-recovery is invisible. |
| C11 | `_perform_health_check` client-routing bool flips: `==`/`!=` and `and`/`or` on NEMOTRON/FLORENCE/CLIP branches (mutmut_3–8) — routes the probe to the **wrong client** or skips all clients; existing tests assert only `result is True` (all mocks return True) | 6 | TEST-GAP | `perform_health_check__mutmut_3`, `perform_health_check__mutmut_7` | Misses *which* client's method was awaited. Kill requires per-client `assert_awaited_once`/`assert_not_awaited`; mutmut_7/8 additionally need the partial-clients fall-through scenario. |
| C12 | `_notify_status_change` payload: `status = self.get_degradation_status()`→`None` (mutmut_1) and `callback(status)`→`callback(None)` (mutmut_2) — WebSocket broadcast payload destroyed | 2 | TEST-GAP | `notify_status_change__mutmut_1` | Existing callbacks tests only `assert_called_once()` — never inspect the argument. |
| C13 | `_check_all_services` change-detection: init `False`→`True` (mutmut_2 = notify every cycle, callback spam) and `old != new`→`old == new` (mutmut_6 = notify when nothing changed, silent on real change) | 2 | TEST-GAP | `check_all_services__mutmut_6` | `test_check_all_services_triggers_notification` uses `call_count >= 1` after 3 unhealthy cycles — mutant satisfies it trivially. Missing: "no change → no notify" leg. |
| C14 | `start()` task name: `name="ai-fallback-health-check"` → None/dropped/XX/UPPER (mutmut_9, 11–13) | 4 | TEST-GAP | `start__mutmut_9` | NEM-5057 rationale comment in code; repo precedent asserts `get_name()` (test_health_monitor.py:69). ai_fallback test never checks it. |
| C15 | `_check_service_health` healthy-recovery fields unasserted: `state.last_success = datetime.now(UTC)`→`None` (mutmut_16); `state.error_message = None`→`""` (mutmut_20 — visible as `""` vs `null` in `to_dict`) | 2 | TEST-GAP | `check_service_health__mutmut_16` | Recovery-path tests (:576–587) assert only status + failure_count == 0. |
| C16 | `failure_count` arithmetic: CB projection `= cb.failure_count`→`None` (mutmut_8 — `failure_count` is a real property at circuit_breaker.py:360); except-path `+= 1`→`= 1` (mutmut_28, only differs on consecutive failures; existing test asserts fresh count==1) | 2 | TEST-GAP | `check_service_health__mutmut_28` | With-CB tests assert status/circuit_state but never the projected count. |
| C17 | Naive-timestamp swaps `datetime.now(UTC)`→`datetime.now(None)`: `last_check` (mutmut_3), `last_success` (mutmut_17), status `"timestamp"` (get_degradation_status__3) — ISO strings lose `+00:00`, JS `Date` re-parses naive UTC as local | 3 | TEST-GAP | `get_degradation_status__mutmut_3` | Tests assert `last_check is not None` (:661) and key-presence only; nothing parses tzinfo. |
| C18 | TTL boundary flip `>`→`>=` in `get_cached_score` freshness check (mutmut_9) | 1 | TEST-GAP | `get_cached_score__mutmut_9` | Classic off-by-one: entry at exactly `ttl_seconds` is still valid. Existing TTL test sleeps 0.02 s past a 0.01 s TTL — far from the boundary. Kill: patch `backend.services.ai_fallback.time.monotonic` to `ts + ttl_seconds` exactly, assert score still returned. |
| C19 | `get_available_features` list-entry clobbers: `"dense_captioning"` (mutmut_20/21), `"anomaly_detection"` (mutmut_28/29) → XX-wrapped/UPPER | 4 | TEST-GAP | `get_available_features__mutmut_21` | `test_get_available_features_all_healthy` (:775) checks membership of 11 of the 13 entries — exactly these two never appear in any assert; down-tests also only check the other entries' absence. |
| C20 | `get_fallback_caption` join separator `", "`→`"XX, XX"` (mutmut_7) | 1 | TEST-GAP | `get_fallback_caption__mutmut_7` | Tests use weak `in caption.lower()` substring asserts (:935) — "person" survives inside the clobbered join. |
| C21 | `get_fallback_risk_analysis` reasoning join separator `", "`→`"XX, XX"` (mutmut_28) | 1 | TEST-GAP | `get_fallback_risk_analysis__mutmut_28` | Same weakness: `"person" in result.reasoning` passes on the clobbered string. |
| C22 | Default-fallback reasoning text clobbers (mutmut_38/39/40: XX-wrap / lower / UPPER) | 3 | TEST-GAP | `get_fallback_risk_analysis__mutmut_39` | Test exists but asserts too weakly: `"default medium risk" in result.reasoning.lower()` (:901) — the asserted substring survives all three clobbers. Kill with exact string equality. |

**Totals:** 70 = EQUIVALENT 35 (C1–C8) + LOW-VALUE 3 (C9) + TEST-GAP 32 (C10–C22).

## Highest-value TEST-GAP clusters and drafted tests

All drafts go in `backend/tests/unit/services/test_ai_fallback.py` (fixtures `fallback_service` and imports already present; `UTC`, `datetime`, `AsyncMock`, `MagicMock` imported at :24–25).
**TDD procedure for every draft: apply the cluster's mutant diff → the new assert fails (red); restore original → passes (green).**

### D1 → C11 (`test_perform_health_check_uses_registered_client_per_service` + fall-through case, 6 kills)

```python
class TestPerformHealthCheckRouting:
    """WP4.4: probes must execute on the service's OWN client (mutants C11)."""

    @pytest.mark.asyncio
    async def test_perform_health_check_uses_registered_client_per_service(
        self, fallback_service
    ) -> None:
        """Each service's health probe must run on its own client, not another's."""
        cases = [
            (AIService.YOLO26, fallback_service._detector_client.health_check),
            (AIService.NEMOTRON, fallback_service._nemotron_analyzer.health_check),
            (AIService.FLORENCE, fallback_service._florence_client.check_health),
            (AIService.CLIP, fallback_service._clip_client.check_health),
        ]
        all_probes = [probe for _, probe in cases]
        for service, probe in cases:
            for p in all_probes:
                p.reset_mock()
            assert await fallback_service._perform_health_check(service) is True
            probe.assert_awaited_once()
            for other in all_probes:
                if other is not probe:
                    other.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_perform_health_check_does_not_borrow_client_when_service_client_missing(self) -> None:
        """A service whose client is missing must NOT borrow another client's probe."""
        clip = MagicMock()
        clip.check_health = AsyncMock(return_value=True)
        service = AIFallbackService(clip_client=clip)  # detector/nemotron/florence = None

        assert await service._perform_health_check(AIService.YOLO26) is True
        clip.check_health.assert_not_awaited()
```

The second case is required for mutmut_7/8: branch 4 is only reached with `service != CLIP` when the earlier services' clients are absent, and `== CLIP or self._clip_client` / `!= CLIP and self._clip_client` then borrow the CLIP probe.

### D2 → C14 (`test_start_names_health_check_task`, 4 kills)

```python
class TestHealthCheckTaskNaming:
    """WP4.4 / NEM-5057: task name is the debug contract (mutants C14)."""

    @pytest.mark.asyncio
    async def test_start_names_health_check_task(self, fallback_service) -> None:
        await fallback_service.start()
        try:
            assert fallback_service._health_check_task is not None
            assert fallback_service._health_check_task.get_name() == "ai-fallback-health-check"
        finally:
            await fallback_service.stop()
```

### D3 → C19 (`test_get_available_features_exact_list_all_healthy`, 4 kills)

```python
class TestAvailableFeaturesExact:
    """WP4.4: every feature name is a public contract string (mutants C19)."""

    def test_get_available_features_exact_list_all_healthy(self, fallback_service) -> None:
        features = fallback_service.get_available_features()

        assert features == [
            "object_detection",
            "detection_alerts",
            "risk_analysis",
            "llm_reasoning",
            "image_captioning",
            "ocr",
            "dense_captioning",
            "entity_tracking",
            "re_identification",
            "anomaly_detection",
            "event_history",
            "camera_feeds",
            "system_monitoring",
        ]
```

### D4 → C12 (`test_notify_status_change_delivers_full_status_dict`, 2 kills)

```python
class TestNotifyPayload:
    """WP4.4: callback payload IS the WebSocket broadcast (mutants C12)."""

    @pytest.mark.asyncio
    async def test_notify_status_change_delivers_full_status_dict(self, fallback_service) -> None:
        callback = AsyncMock()
        fallback_service.register_status_callback(callback)

        await fallback_service._notify_status_change()

        callback.assert_awaited_once()
        (payload,), _kwargs = callback.call_args
        assert isinstance(payload, dict)
        assert {"timestamp", "degradation_mode", "services", "available_features"} <= payload.keys()
```

### D5 → C13 (`test_check_all_services_notifies_only_when_status_changes`, 2 kills)

```python
class TestNotificationGating:
    """WP4.4: notify fires on change AND only on change (mutants C13)."""

    @pytest.mark.asyncio
    async def test_check_all_services_notifies_only_when_status_changes(self, fallback_service) -> None:
        callback = AsyncMock()
        fallback_service.register_status_callback(callback)

        # Cycle 1: everything healthy -> no status change -> no notification.
        await fallback_service._check_all_services()
        assert callback.call_count == 0

        # Cycle 2: YOLO26 fails -> HEALTHY -> DEGRADED -> exactly one notification.
        fallback_service._detector_client.health_check = AsyncMock(return_value=False)
        await fallback_service._check_all_services()
        assert callback.call_count == 1
```

### D6 → C17 (`test_service_state_timestamps_are_utc_aware`, 3 kills + mutmut_16 from C15)

```python
class TestTimestampAwareness:
    """WP4.4: serialized timestamps must carry the UTC offset (mutants C17)."""

    @pytest.mark.asyncio
    async def test_service_state_timestamps_are_utc_aware(self, fallback_service) -> None:
        await fallback_service._check_service_health(AIService.YOLO26)
        state = fallback_service._service_states[AIService.YOLO26]

        assert state.last_check is not None
        assert state.last_check.tzinfo is UTC
        assert state.last_success is not None
        assert state.last_success.tzinfo is UTC

        status = fallback_service.get_degradation_status()
        assert datetime.fromisoformat(status["timestamp"]).tzinfo is not None
```

Bonus kill: mutmut_16 (`last_success = None`) also dies on the `last_success is not None` line.

## Remaining TEST-GAP clusters (not drafted; recipe noted)

- **C10** (1 key): healthy-loop caplog test — patch all clients healthy, run loop 2 cycles, assert no record contains "Health check loop error".
- **C15** (mutmut_20 only after D6): after a failure with `error_message` set, run a healthy check, assert `state.error_message is None` (kills `""`).
- **C16** (2 keys): (a) register a CB driven to `failure_count == 2`, assert `state.failure_count == 2` (kills mutmut_8); (b) `health_check` returns False twice, then raises → assert `state.failure_count == 3` (kills mutmut_28).
- **C18** (1 key): `cache.set_cached_score("cam", 42)` under `ttl_seconds=300`; `unittest.mock.patch("backend.services.ai_fallback.time.monotonic", return_value=ts + 300)` where `ts = cache._timestamps["cam"]`; assert `get_cached_score("cam") == 42` (original: `300 > 300` False → returns; mutant `>=` → None).
- **C20/C21/C22** (5 keys): replace substring asserts with exact equality: `get_fallback_caption(object_types=["person", "vehicle"], camera_name="front_door") == "Person, vehicle detected at front_door"`; `result.reasoning == "Estimated risk score based on detected objects: person, vehicle. Nemotron analyzer is currently unavailable."`; default path `result.reasoning == "Using default medium risk score. Nemotron analyzer is currently unavailable for detailed analysis."`.

## Verification caveats

- UNVERIFIED: no pytest/mutmut run performed (mutation run owns the machine); classification derived from `mutmut show` diffs (all 70 pulled cleanly), source reading, and grep.
- CircuitBreaker.failure_count confirmed a property (circuit_breaker.py:360), so mutmut_8 executes under any registered CB.
- `FallbackRiskAnalysis().source` default confirmed `"default"`, grounding C7 as EQUIVALENT.
