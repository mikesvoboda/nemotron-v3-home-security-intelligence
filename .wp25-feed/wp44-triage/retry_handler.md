# WP4.4 Triage Dossier — backend/services/retry_handler.py

- **Surviving mutants:** 151 of 545 keys checked (exit_code 0)
- **Clusters:** 23 (TEST-GAP 12 clusters / 54 mutants; EQUIVALENT 2 / 3; LOW-VALUE 9 / 94)
- **Diff extraction:** body-diff of each `__mutmut_N` variant vs its `__mutmut_orig` in `mutants/backend/services/retry_handler.py` (bracket-aware block scan), spot-validated against `mutmut show` (v3, v12, v100, v4, get_retry_handler v4 all match). Raw per-mutant diffs: `/tmp/wp25/wp44-triage/diffs3.txt`.
- **Covering tests (from mutmut-stats.json tests_by_mangled_function_name):**
  - `backend/tests/unit/services/test_retry_handler.py` (primary for every function)
  - `backend/tests/unit/api/routes/test_dlq_api.py` (API-level coverage of get_dlq_stats / get_dlq_jobs / clear_dlq / requeue_dlq_job / move_dlq_job_to_queue / get_retry_handler)
  - `backend/tests/unit/services/test_pipeline_workers.py`, `backend/tests/unit/services/test_redis_streams_integration.py` (with_retry / `__init__` context only)

## Key line anchors in test_retry_handler.py

| Region | Line | Why it matters |
|---|---|---|
| `TestRetryHandler` fixtures + DLQ op tests | 227–688 | `mock_redis` fixtures (230, 797, 1050, 1181, 1445) return constants and **ignore call args**, so queue-name/policy arg mutants pass |
| `test_get_dlq_stats` | 386–404 | asserts returned counts only (side_effect order), never which queue name was queried → C23 |
| `test_move_dlq_job_to_queue` | 554–577 | asserts positional args only, `overflow_policy` kwarg unchecked → C16 |
| `TestDLQCircuitBreaker` | 794–1039 | failure paths assert `status["failure_count"]` but never `_move_to_dlq` return value → C11 |
| `TestDLQJobLossLogging` | 1047–1170 | the ONLY audit assertions are substring + `or` disjunctions: `assert "cam3" in call_str or "lost_job_data" in call_str` (L1129) and `any("lost_job_data" in str(call) or "cam_lost" in str(call) ...)` (L1167–1170) → C12 survives |
| `TestMoveToDlqEdgeCases` | 1178–1226 | success path asserts `result is True` + called-once, payload dict unchecked → C08/C09/C10 |
| `TestRetryHandlerErrorContextCapture` | 1442–1696 | truncation asserted only as `len(stack_trace) <= 4096` (L1563) and `len(response_body) <= 2048` (L1696); trace/body presence via loose substrings (L1507, L1669) → C04/C06/C07 |

## Cluster table

| # | Pattern (function / mutation concern) | n | Class | Example keys (`…ǁRetryHandlerǁ` prefix omitted) |
|---|---|---|---|---|
| C01 | `get_retry_handler`: singleton guard `and` → `or` (silently replaces live `_redis`) | 1 | TEST-GAP | `x_get_retry_handler__mutmut_4` |
| C02 | `_capture_system_context`: captured values clobbered to `None` (depths, breaker state) / redis arg → `None` | 7 | TEST-GAP | `…capture_system_context__mutmut_2, _3, _13` |
| C03 | `_capture_system_context`: debug log msg → `None` | 1 | EQUIVALENT | `…capture_system_context__mutmut_12` |
| C04 | `_extract_error_context`: truncation-suffix text mutated (case flip / XX padding) — final length identical | 4 | TEST-GAP | `…extract_error_context__mutmut_13, _15, _16` |
| C05 | `_extract_error_context`: `format_exception(type(None)|None, …)` — output **byte-identical** (proven, Python 3.14) | 2 | EQUIVALENT | `…extract_error_context__mutmut_20, _26` |
| C06 | `_extract_error_context`: trace content changed (`exc=None` → "NoneType: None"; `tb=None` → traceback frames dropped; `"XXXX".join`) | 3 | TEST-GAP | `…extract_error_context__mutmut_19, _21, _22` |
| C07 | `_extract_error_context`: `>` → `>=` truncation boundary (truncates an exactly-at-limit trace/body) | 2 | TEST-GAP | `…extract_error_context__mutmut_27, _39` |
| C08 | `_move_to_dlq`: JobFailure payload kwargs → `None` (original_job/error/attempt_count/first_failed_at/last_failed_at/queue_name) | 6 | TEST-GAP | `…move_to_dlq__mutmut_38, _39, _43` |
| C09 | `_move_to_dlq`: `datetime.now(UTC)` → `datetime.now(None)` → naive `last_failed_at` | 1 | TEST-GAP | `…move_to_dlq__mutmut_62` |
| C10 | `_move_to_dlq`: `overflow_policy=REJECT` → `None` / kwarg removed (DLQ inherits global policy → silent loss) | 2 | TEST-GAP | `…move_to_dlq__mutmut_66, _69` |
| C11 | `_move_to_dlq`: `return False` → `return True` on queue-full and exception paths (false success claim) | 2 | TEST-GAP | `…move_to_dlq__mutmut_91, _116` |
| C12 | `_move_to_dlq`: CRITICAL DATA-LOSS (circuit-open) ERROR audit `extra` keys mutated + `data_loss` True→False | 21 | TEST-GAP | `…move_to_dlq__mutmut_12, _22, _32` |
| C13 | `_move_to_dlq`: queue-full ERROR log message/extra key mutations (log payload only) | 19 | LOW-VALUE | `…move_to_dlq__mutmut_71, _75, _85` |
| C14 | `_move_to_dlq`: success INFO log message/extra mutations | 11 | LOW-VALUE | `…move_to_dlq__mutmut_92, _96, _100` |
| C15 | `_move_to_dlq`: no-redis WARNING + exception-path ERROR log mutations | 11 | LOW-VALUE | `…move_to_dlq__mutmut_3, _105, _110` |
| C16 | `move_dlq_job_to_queue`: `requeue_dlq_job(None)` / `overflow_policy=DLQ` → `None` / removed | 3 | TEST-GAP | `…move_dlq_job_to_queue__mutmut_4, _8, _11` |
| C17 | `move_dlq_job_to_queue`: failure/backpressure/success/exception log payload mutations | 29 | LOW-VALUE | `…move_dlq_job_to_queue__mutmut_13, _17, _25` |
| C18 | `requeue_dlq_job`: INFO/ERROR log message + extra mutations | 9 | LOW-VALUE | `…requeue_dlq_job__mutmut_6, _7, _10` |
| C19 | `reset_dlq_circuit_breaker`: INFO log message/extra mutations | 8 | LOW-VALUE | `…reset_dlq_circuit_breaker__mutmut_1, _2, _5` |
| C20 | `clear_dlq`: INFO/ERROR log payload mutations | 3 | LOW-VALUE | `…clear_dlq__mutmut_4, _6, _7` |
| C21 | `get_dlq_jobs`: ERROR log payload mutations | 2 | LOW-VALUE | `…get_dlq_jobs__mutmut_10, _11` |
| C22 | `get_dlq_stats`: ERROR log payload mutations | 2 | LOW-VALUE | `…get_dlq_stats__mutmut_13, _14` |
| C23 | `get_dlq_stats`: queue-name arg → `None` (stats read from wrong queue, no error) | 2 | TEST-GAP | `…get_dlq_stats__mutmut_3, _5` |

Totals: TEST-GAP 54, EQUIVALENT 3, LOW-VALUE 94 → **151**.

## Classification notes

- **C05 (EQUIVALENT, proven):** `traceback.format_exception(type(None), e, tb)` passes `etype=None`; CPython then re-derives `type(value)` → output byte-identical; `etype=None` likewise (verified on this sandbox's Python 3.14.4: `m20/m26 identical=True`). No test can kill these; recommend marking skip/survived-intentional.
- **C03 (EQUIVALENT):** only the debug message inside a best-effort `except` becomes `None`; control flow and returned context unchanged.
- **C13/C14/C15/C17–C22 (LOW-VALUE):** real changes to log messages / `logging.extra` payloads on non-audit paths (queue-full detail, success info, clear/get/requeue error text). Nobody should depend on log-payload key spellings; the tests execute these lines and correctly don't assert them. (One nuance: C13's message carries the circuit-failure ratio, but the *behavioral* part — `_record_failure()` + `return False` — is already covered by `TestDLQCircuitBreaker`.)
- **C12 vs C13 boundary:** the circuit-open branch logs the *only* record of a permanently-lost job (module docstring + `wa0t.16` fix). A broken audit key name silently corrupts the data-loss audit trail with no other symptom → real contract, asserted only by substring `or`-disjunctions (test_retry_handler.py:1129, 1167–1170) → TEST-GAP.
- **C06 judgment anomaly:** verified outputs on Python 3.14.4 — m19 inserts `XXXX` between frames, m22 keeps the final `ValueError: …` line but drops every `File "…"` frame, so both sail through the loose substring asserts at test_retry_handler.py:1507; m21 (`exc=None`) replaces the exception line with `NoneType: None`, so `"ValueError" in stack_trace` at :1507 *should* have killed it, yet it survived — re-check m21's execution record during the fix pass (possible cache/verdict artifact). Treat all three as TEST-GAP regardless; the strict follow-on asserts kill them uniformly.
- **C09:** `datetime.now(None).isoformat()` is *timezone-naive* → cross-timezone ordering breaks for DLQ consumers.
- **C10/C16:** `add_to_queue_safe` defaults `overflow_policy=None` to `settings.queue_overflow_policy` (backend/core/redis.py:760–761), so removing `REJECT` lets the DLQ itself silently overflow — exactly what the `_move_to_dlq` comment says must never happen.
- **C01:** `or` variant replaces the singleton's `_redis` on every call that passes any client — defeats "first client wins" (test_get_retry_handler_updates_redis at :719 does not cover the replacement direction).

## Drafted tests (target file: backend/tests/unit/services/test_retry_handler.py)

All UNVERIFIED — not yet run red/green. TDD procedure for each: add test → run → assert must FAIL on the mutant copy (per-cluster mutants listed), then PASS on `backend/services/retry_handler.py` unchanged.

### T1 — kills C12 (21 mutants): exact data-loss audit contract

```python
class TestMoveToDlqAuditContract:
    """Audit extra payload of the CRITICAL DATA LOSS log must keep exact key names."""

    # UNVERIFIED - not yet run red/green.
    # TDD: fails on move_to_dlq__mutmut_12..32 (any XX/UPPER key rename, data_loss=False),
    #      passes on original.

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        redis = MagicMock()
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        redis.get_queue_length = AsyncMock(return_value=0)
        return redis

    @pytest.mark.asyncio
    async def test_data_loss_log_has_exact_audit_contract(
        self, mock_redis: MagicMock
    ) -> None:
        """Circuit-open data loss must log exact audit keys for downstream parsers."""
        handler = RetryHandler(redis_client=mock_redis)
        handler._dlq_circuit_breaker.force_open()

        with patch("backend.services.retry_handler.logger", autospec=True) as mock_logger:
            result = await handler._move_to_dlq(
                job_data={"camera_id": "cam_audit"},
                error="boom",
                attempt_count=3,
                first_failed_at="2025-12-23T10:00:00",
                queue_name="detection_queue",
            )

        assert result is False
        loss_calls = [
            call
            for call in mock_logger.error.call_args_list
            if "CRITICAL DATA LOSS" in str(call.args[0])
        ]
        assert loss_calls, "CRITICAL DATA LOSS log not emitted"
        extra = loss_calls[0].kwargs["extra"]
        assert set(extra) == {
            "queue_name",
            "circuit_state",
            "circuit_failures",
            "circuit_threshold",
            "circuit_recovery_timeout",
            "lost_job_data",
            "lost_job_error",
            "lost_job_attempt_count",
            "lost_job_first_failed_at",
            "data_loss",
        }
        assert extra["data_loss"] is True
        assert extra["lost_job_data"] == {"camera_id": "cam_audit"}
        assert extra["lost_job_error"] == "boom"
        assert extra["lost_job_attempt_count"] == 3
```

### T2 — kills C08 (6 mutants): DLQ payload completeness

```python
class TestMoveToDlqPayloadIntegrity:
    """The JobFailure dict written to the DLQ must carry every field intact."""

    # UNVERIFIED - not yet run red/green.
    # TDD: fails on move_to_dlq__mutmut_38..43 (each kwargs→None), passes on original.

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        redis = MagicMock()
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        redis.get_queue_length = AsyncMock(return_value=0)
        return redis

    @pytest.mark.asyncio
    async def test_stored_failure_keeps_all_core_fields(self, mock_redis: MagicMock) -> None:
        handler = RetryHandler(redis_client=mock_redis)

        moved = await handler._move_to_dlq(
            job_data={"camera_id": "cam1", "file_path": "/p/img.jpg"},
            error="ai down",
            attempt_count=3,
            first_failed_at="2025-12-23T10:00:00",
            queue_name="detection_queue",
        )

        assert moved is True
        payload = mock_redis.add_to_queue_safe.call_args[0][1]
        assert payload["original_job"] == {"camera_id": "cam1", "file_path": "/p/img.jpg"}
        assert payload["error"] == "ai down"
        assert payload["attempt_count"] == 3
        assert payload["first_failed_at"] == "2025-12-23T10:00:00"
        assert payload["last_failed_at"] is not None
        assert payload["queue_name"] == "detection_queue"
```

### T3 — kills C11 (2 mutants): failed DLQ write must report failure

```python
class TestMoveToDlqFailureReporting:
    """_move_to_dlq must return False when the enqueue did not happen."""

    # UNVERIFIED - not yet run red/green.
    # TDD: fails on move_to_dlq__mutmut_91 (queue-full return True) and
    #      move_to_dlq__mutmut_116 (exception return True), passes on original.

    @pytest.mark.asyncio
    async def test_queue_full_returns_false(self) -> None:
        redis = MagicMock()
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=False, queue_length=10000, error="Queue full")
        )
        redis.get_queue_length = AsyncMock(return_value=0)
        handler = RetryHandler(redis_client=redis)

        moved = await handler._move_to_dlq(
            job_data={"camera_id": "cam1"},
            error="boom",
            attempt_count=3,
            first_failed_at="2025-12-23T10:00:00",
            queue_name="detection_queue",
        )
        assert moved is False

    @pytest.mark.asyncio
    async def test_enqueue_exception_returns_false(self) -> None:
        redis = MagicMock()
        redis.add_to_queue_safe = AsyncMock(side_effect=RuntimeError("redis down"))
        redis.get_queue_length = AsyncMock(return_value=0)
        handler = RetryHandler(redis_client=redis)

        moved = await handler._move_to_dlq(
            job_data={"camera_id": "cam1"},
            error="boom",
            attempt_count=3,
            first_failed_at="2025-12-23T10:00:00",
            queue_name="detection_queue",
        )
        assert moved is False
```

### T4 — kills C09 (1 mutant): last_failed_at must be timezone-aware UTC

```python
class TestMoveToDlqTimestamps:
    # UNVERIFIED - not yet run red/green.
    # TDD: fails on move_to_dlq__mutmut_62 (datetime.now(None) -> naive ISO),
    #      passes on original.

    @pytest.mark.asyncio
    async def test_last_failed_at_is_timezone_aware(self) -> None:
        """DLQ consumers compare ISO stamps across sources; naive stamps break ordering."""
        from datetime import datetime, timezone

        redis = MagicMock()
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        redis.get_queue_length = AsyncMock(return_value=0)
        handler = RetryHandler(redis_client=redis)

        await handler._move_to_dlq(
            job_data={"camera_id": "cam1"},
            error="boom",
            attempt_count=1,
            first_failed_at="2025-12-23T10:00:00",
            queue_name="detection_queue",
        )

        payload = redis.add_to_queue_safe.call_args[0][1]
        stamp = datetime.fromisoformat(payload["last_failed_at"])
        assert stamp.tzinfo is not None
        assert stamp.utcoffset() == timezone.utc.utcoffset(None)
```

### T5 — kills C10 (2 mutants): DLQ writes must pin REJECT policy

```python
class TestMoveToDlqOverflowPolicy:
    # UNVERIFIED - not yet run red/green.
    # TDD: fails on move_to_dlq__mutmut_66 (policy=None) and
    #      move_to_dlq__mutmut_69 (kwarg removed), passes on original.
    # (Same test shape kills move_dlq_job_to_queue__mutmut_8/_11 -- C16 --
    #  by driving move_dlq_job_to_queue and asserting QueueOverflowPolicy.DLQ.)

    @pytest.mark.asyncio
    async def test_dlq_write_uses_reject_overflow_policy(self) -> None:
        """DLQ must never silently overflow: REJECT is pinned, not inherited from settings."""
        redis = MagicMock()
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        redis.get_queue_length = AsyncMock(return_value=0)
        handler = RetryHandler(redis_client=redis)

        await handler._move_to_dlq(
            job_data={"camera_id": "cam1"},
            error="boom",
            attempt_count=1,
            first_failed_at="2025-12-23T10:00:00",
            queue_name="detection_queue",
        )

        kwargs = redis.add_to_queue_safe.call_args.kwargs
        assert kwargs["overflow_policy"] is QueueOverflowPolicy.REJECT
```

(`QueueOverflowPolicy` is already imported in the file's header block via `from backend.core.redis import QueueAddResult` — extend that import to `QueueAddResult, QueueOverflowPolicy`.)

### T6 — kills C02 (7 mutants): system context must capture real values

```python
class TestCaptureSystemContextValues:
    # UNVERIFIED - not yet run red/green.
    # TDD: fails on capture_system_context__mutmut_2/_3/_4/_5/_6/_9/_13,
    #      passes on original. Existing test only checks key presence (L1613-1617).

    @pytest.mark.asyncio
    async def test_records_real_depths_and_breaker_state(self) -> None:
        """Depth values and breaker state must be real values read from the right queues."""
        redis = MagicMock()
        depths = {"detection_queue": 150, "analysis_queue": 25}
        redis.get_queue_length = AsyncMock(side_effect=lambda name: depths[name])
        handler = RetryHandler(redis_client=redis)

        ctx = await handler._capture_system_context()

        assert ctx == {
            "detection_queue_depth": 150,
            "analysis_queue_depth": 25,
            "dlq_circuit_breaker_state": "closed",
        }
        redis.get_queue_length.assert_any_call("detection_queue")
        redis.get_queue_length.assert_any_call("analysis_queue")
```

(The name-keyed `side_effect` also kills the arg-`None` mutants _3/_5: a `None` key raises inside the try, the `except` path then leaves the key missing, failing the `==` assert.)

### Follow-on (not drafted, next priority): C01, C23, C04, C06, C07

- C23: reuse T6's name-keyed fake around `get_dlq_stats` and assert `get_queue_length` called with the two DLQ queue names (kills _3/_5).
- C01: `handler = get_retry_handler(redis_a); get_retry_handler(redis_b); assert handler._redis is redis_a` (kills _4).
- C04/C07: strict-truncation asserts — construct a trace/body exactly `max_len` long (no truncation: `endswith` original tail, no `[truncated]`) and one `max_len+1` long (exact `len == max_len` and `endswith("\n... [truncated]")`); kills the `>=` flips and every suffix-text mutant.
- C06: assert `"  File \"" in stack_trace` once (kills _22 dropped frames) and `"XXXX" not in stack_trace` (kills _19) and the `NoneType: None` absence (kills _21, see anomaly note).
