# WP4.4 Triage Dossier — `backend/services/job_log_emitter.py`

**Wave**: gen-2 NEW tier (never-tallied module)
**Mutants in meta**: 187 → 127 killed, **60 survived**, 0 unchecked
**Source**: `backend/services/job_log_emitter.py` (419 lines); mutated copy `mutants/backend/services/job_log_emitter.py`
**Diff provenance**: all 60 diffs came from read-only `uv run mutmut show <key>` (no timeouts, no manual diffing). Raw per-key diffs cached at `/tmp/wp25/wp44-triage/jle-diffs/*.txt`.
**Survivor inventory** (verified against `keys.txt`, sums to 60):

| Function | N | Surviving mutant numbers |
|---|---|---|
| `JobLogEmitter.emit_log` | 31 | 2,3,5,6,7,8,9,10,11,31,32,34,35,36,37,38,39,40,41,42,43,45,48,49,50,52,53,54,55,56,57 |
| `emit_job_completed` | 9 | 1,2,3,4,7,15,16,23,24 |
| `emit_job_progress` | 6 | 6,7,8,17,25,26 |
| `emit_job_started` | 5 | 1,9,10,13,14 |
| `emit_job_failed` | 4 | 1,10,15,16 |
| `get_job_log_emitter` | 4 | 8,9,10,11 |
| `_create_log_message` | 1 | 9 |

## Covering tests (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`)

| Test file | Covers | Assert style |
|---|---|---|
| `backend/tests/unit/services/test_job_log_emitter.py` | `emit_log`, all four lifecycle wrappers, singleton, channel name, stats | reads `mock_redis_client.publish.call_args[0][1]`, `json.loads` it, then **spot-checks individual keys** |
| `backend/tests/unit/services/test_job_history_service.py:525` `TestJobHistoryServiceAddLog` (`:529` creates-entry, `:565` normalizes-level) | the only production caller (`job_history_service.py:494` → `emitter.emit_log`) | asserts on the DB `JobLogEntry`, **never** on the published payload |

**The structural fact behind the whole survivor set**: neither covering file contains a `caplog` fixture, a `set_level` call, or any assertion on an `extra=` payload or log-record message text (grep → 0 hits in both files). The emitter's own diagnostics are entirely unobserved. Separately, the lifecycle tests assert *fragments* (`"completed successfully" in message`) and *some* context keys, so any key or branch they never names is unobserved.

## Consumer chain (grades value)

- `backend/api/routes/websocket.py:957` `log_channel = f"job:{job_id}:logs"`; `:982` subscribes; `:1000` relays `log_data` to the browser **verbatim**. Nothing backend-side re-parses the payload, so only a *throwing* mutation breaks the relay — a renamed context key does not, it just reaches the client wrong.
- `frontend/src/hooks/useJobLogsWebSocket.ts:116-132` (`isJobLogMessage`) is the real consumer: it **drops the entire message** unless `data.timestamp`, `data.level` and `data.message` are all `typeof 'string'`. So `message=None` / `level=None` = a silently vanishing log line, not a crash.
- `get_stats()` / `emit_count` / `emit_errors` have **no production consumer** (grep: only `websocket_emitter.py`, a separate service).

---

## Clusters (counts sum to 60)

Key shorthand: `EL_n` = `…xǁJobLogEmitterǁemit_log__mutmut_n`, `CS/CP/CC/CF_n` = started/progress/completed/failed, `SGL_n` = `x_get_job_log_emitter__mutmut_n`, `CLM_9` = `_create_log_message__mutmut_9`. Full key prefix omitted.

| ID | Pattern | N | Keys | Class | Reasoning |
|---|---|---|---|---|---|
| **D1** | lifecycle wrapper forwards `job_id=None` to `emit_log` → publishes to `job:None:logs` | 4 | `CS_1`, `CP_17`, `CC_7`, `CF_1` | **TEST-GAP** | Event never reaches the subscribed browser. All four tests pass because `publish.assert_called_once()` is count-only and none reads `call_args[0][0]`. The generic path *does* pin the channel (`test_job_log_emitter.py:131`); the wrappers don't — an omission, not policy. |
| **F1** | lifecycle `context` **key name** clobbered (`XXkXX`) or UPPER-cased | 8 | `CC_23`,`CC_24` (`duration_seconds`), `CF_15`,`CF_16` (`error`), `CS_13`,`CS_14` (`metadata`), `CP_7`,`CP_8` (`current_step`) | **TEST-GAP** | Renames a published wire-contract key the client receives verbatim. Tests pin `status`, `error_code`, `retryable`, `items_processed`, `items_total`, `progress_percent`, `job_type` — but never `duration_seconds`, `error`, `metadata`, `current_step`. |
| **C1+C2** | `emit_job_completed` default `message` (no `duration_seconds`) → `None` / `XX..XX` / lower / UPPER | 4 | `CC_1`,`CC_2`,`CC_3`,`CC_4` | **TEST-GAP** | The no-duration branch is **never called** (`test_job_log_emitter.py:270-274` always passes `duration_seconds=45.5`). `CC_1` is the module's worst survivor: `emit_log`'s `message[:50]` debug f-string raises, its own `except` swallows it → returns `False` + a bogus `emit_errors`, and `"message": null` fails `isJobLogMessage` so the completion event silently disappears. C2: fragment assert at `:279` only ever runs against the duration message, while the sibling no-step progress branch *is* exact-matched (`:260`). |
| **E2** | lifecycle `level="INFO"` → `"XXINFOXX"` | 3 | `CS_9`,`CP_25`,`CC_15` | **TEST-GAP** | `.upper()` at `:125` keeps it a string, so the payload level becomes `"XXINFOXX"`. Only `test_emit_job_failed:302` asserts a level. |
| **G1** | `emit_job_progress`: `context["current_step"] = current_step` → `= None` | 1 | `CP_6` | **TEST-GAP** | textbook "test exists but asserts too weakly": `:240-242` reads three sibling keys of the same dict and never this one. |
| **I1** | `emit_log` except-branch `self._emit_errors += 1` → `= 1` | 1 | `EL_45` | **TEST-GAP** | N failures report exactly 1 — a monitoring lie. Killed only by ≥2 consecutive failures; `:168` fires exactly one. The sibling `_emit_count += 1` is covered by a two-call test (`:143`), so the fix is a copy of an existing pattern. |
| **A1** | `emit_log` Redis-unavailable guard: debug **message text** → `None`/`XX..XX`/lower/UPPER | 4 | `EL_2`,`EL_6`,`EL_7`,`EL_8` | **EQUIVALENT** | Text is neither published nor captured; the observable outcome (`return False`) is asserted at `:165`. `None` is a legal `Logger.debug()` arg. |
| **A2** | guard `extra=` **shape**: → `None`, key clobber/UPPER, kwarg dropped | 4 | `EL_3`,`EL_5`,`EL_9`,`EL_10` | **EQUIVALENT** | `extra` lands on the `LogRecord`, never in the payload; no `caplog` assertion exists. (`EL_5` is a pure trailing-comma reflow.) |
| **A3** | guard `extra` value `str(job_id)` → `str(None)` | 1 | `EL_11` | **EQUIVALENT** | dict literal still holds the `job_id` key, so the whole extra-family is key-set-insensitive and no value check exists. Debug-only field. |
| **B1** | success-path debug text / `[:50]`→`[:51]` / `extra=None` / kwarg dropped | 4 | `EL_31`,`EL_32`,`EL_34`,`EL_35` | **EQUIVALENT** | pure diagnostic; truncation length only affects a debug string. |
| **B2** | success-path `extra` key names clobbered/UPPER (`job_id`,`level`,`channel`) | 6 | `EL_36`,`EL_37`,`EL_39`,`EL_40`,`EL_42`,`EL_43` | **EQUIVALENT** | unpublished, uncaptured `LogRecord` attributes. |
| **B3** | success-path `extra` **values**: `str(job_id)`→`str(None)`; `level.upper()`→`level.lower()` | 2 | `EL_38`,`EL_41` | **LOW-VALUE** | real change (`job_id` recorded as `"None"`, lowercased level) but debug-only and unobserved; nobody should assert a debug record's shape. |
| **H1** | except-branch `logger.error` text → `None` | 1 | `EL_48` | **EQUIVALENT** | except path is exercised; its observable outcomes (`False`, `emit_errors == 1`) are asserted at `:179-180`. |
| **H2** | except-branch `extra` shape → `None`, kwarg dropped, key clobber/UPPER | 5 | `EL_49`,`EL_52`,`EL_53`,`EL_54`,`EL_55` | **EQUIVALENT** | as A2. |
| **H3** | except-branch `exc_info=True` → `None`/`False` | 2 | `EL_50`,`EL_57` | **LOW-VALUE** | the traceback genuinely stops being attached to the failure record, but the failure *signal* is already covered; pinning `record.exc_info` locks a diagnostics detail. |
| **H4** | except-branch `extra` value `str(job_id)` → `str(None)` | 1 | `EL_56` | **EQUIVALENT** | as A3. |
| **E1** | `_create_log_message`: `datetime.now(UTC)` → `datetime.now(None)` | 1 | `CLM_9` | **EQUIVALENT** | `datetime.now(None)` *is* `datetime.now()` — naive local time. No consumer can throw (relay is a passthrough; the frontend gate only needs a string), so no breakage is observable. Missing observation is tz-awareness. NB `test_job_history_service.py:226`'s `now.isoformat()` check is on `JobLogEntry.to_dict()`, a different serializer — it does not cover this line. |
| **E3** | lifecycle `level` case flip (`"INFO"`→`"info"`, `"ERROR"`→`"error"`) | 4 | `CS_10`,`CP_26`,`CC_16`,`CF_10` | **EQUIVALENT** | `_create_log_message` upper-cases at `:125`, so the published payload is byte-identical. **Unkillable by design.** |
| **A4** | `get_job_log_emitter` init `logger.info` text → `None`/`XX..XX`/lower/UPPER | 4 | `SGL_8`,`SGL_9`,`SGL_10`,`SGL_11` | **LOW-VALUE** | a genuine one-shot startup notice, but nothing should assert a startup banner; singleton identity is already tested (`:339`). LOW-VALUE rather than EQUIVALENT because it does erase an operator-visible line. |

### Totals

| Class | N | Clusters |
|---|---|---|
| **TEST-GAP** | **21** | D1 4 + F1 8 + C1/C2 4 + E2 3 + G1 1 + I1 1 |
| **EQUIVALENT** | **31** | A1 4 + A2 4 + A3 1 + B1 4 + B2 6 + H1 1 + H2 5 + H4 1 + E1 1 + E3 4 |
| **LOW-VALUE** | **8** | B3 2 + H3 2 + A4 4 |
| **Σ** | **60** | ✓ (per-function cross-check: emit_log 31 = A1 4 + A2 4 + A3 1 + B1 4 + B2 6 + B3 2 + H1 1 + H2 5 + H3 2 + H4 1 + I1 1 ✓) |

## Value ranking of the TEST-GAP clusters

1. **D1** (4) — wrong channel = event invisible to the UI, all tests green. Cheapest fix (one line per test).
2. **F1** (8) — renames wire-contract keys the frontend consumes verbatim; largest cluster.
3. **I1** (1) — `_emit_errors` stops at 1; highest-severity single mutant, fix is a copy of an existing two-call test.
4. **E2** (3) — garbage level in the published payload.
5. **C1+C2** (4) — the never-exercised no-duration completion branch; `CC_1` is the only survivor whose mutant form produces a silent user-visible disappearance.
6. **G1** (1) — `current_step` nulled in a dict whose siblings are asserted.

---

## Drafted kill-tests

> **// UNVERIFIED - not yet run red/green** — the harness forbade test execution in this session.
> **TDD procedure (one line)**: add the test, run it against the mutant copy and confirm it fails on the assertion named below, then run it against `backend/services/job_log_emitter.py` and confirm it passes; one mutation-observable difference per assertion.

Style follows the existing file: `@pytest.mark.asyncio`, the `emitter` / `mock_redis_client` / `sample_job_id` fixtures, payload read via `mock_redis_client.publish.call_args[0][1]` + `json.loads`. Append to `backend/tests/unit/services/test_job_log_emitter.py`. Whole-dict (`==`) comparisons are deliberate: each kills the key-clobber, UPPER-case, value-null and level mutants for that payload in one assertion, without pinning `timestamp` (which the existing tests compare per-key).

### 1. Kills D1 (4) — `test_lifecycle_events_publish_to_the_job_channel`

```python
class TestLifecycleChannelContract:
    """Lifecycle wrappers must publish to the *job's own* channel (WP4.4 D1).

    emit_log already pins the channel (TestEmitLog::test_emit_log_publishes_to_redis),
    but the four wrappers only asserted publish was called *once*, so swapping the
    forwarded job_id for None (publishing to "job:None:logs", where no WS client is
    subscribed) survived all four.
    """

    @pytest.mark.asyncio
    async def test_lifecycle_events_publish_to_the_job_channel(
        self,
        emitter: JobLogEmitter,
        mock_redis_client: MagicMock,
        sample_job_id: str,
    ) -> None:
        """Each wrapper must forward job_id so the event lands on job:{job_id}:logs."""
        await emitter.emit_job_started(sample_job_id, "export")
        await emitter.emit_job_progress(sample_job_id, 50, "Processing")
        await emitter.emit_job_completed(sample_job_id, {"ok": True})
        await emitter.emit_job_failed(sample_job_id, "boom")

        channels = [call[0][0] for call in mock_redis_client.publish.call_args_list]
        assert channels == [f"job:{sample_job_id}:logs"] * 4
        assert "job:None:logs" not in channels
```

### 2. Kills I1 (1) — `test_emit_log_error_count_accumulates_across_failures`

```python
    @pytest.mark.asyncio
    async def test_emit_log_error_count_accumulates_across_failures(
        self,
        emitter: JobLogEmitter,
        mock_redis_client: MagicMock,
        sample_job_id: str,
    ) -> None:
        """Every failed publish adds 1 — mirrors test_emit_log_increments_count."""
        mock_redis_client.publish = AsyncMock(side_effect=Exception("Redis down"))

        assert await emitter.emit_log(sample_job_id, "INFO", "first") is False
        assert await emitter.emit_log(sample_job_id, "INFO", "second") is False
        assert await emitter.emit_log(sample_job_id, "INFO", "third") is False

        assert emitter.emit_errors == 3
        assert emitter.emit_count == 0
        assert emitter.get_stats()["emit_errors"] == 3
```

### 3. Kills E2 `CS_9` + F1 `CS_13`,`CS_14` (3) — `test_job_started_payload_pins_level_and_full_context`

```python
    @pytest.mark.asyncio
    async def test_job_started_payload_pins_level_and_full_context(
        self,
        emitter: JobLogEmitter,
        mock_redis_client: MagicMock,
        sample_job_id: str,
    ) -> None:
        """Started event: INFO level plus the complete context key set."""
        await emitter.emit_job_started(sample_job_id, "export", metadata={"format": "csv"})

        data = json.loads(mock_redis_client.publish.call_args[0][1])["data"]
        assert data["message"] == "Job started: export"
        assert data["level"] == "INFO"
        assert data["context"] == {"job_type": "export", "metadata": {"format": "csv"}}
```

### 4. Kills E2 `CP_25` + F1 `CP_7`,`CP_8` + G1 `CP_6` (4) — `test_job_progress_context_includes_current_step`

```python
    @pytest.mark.asyncio
    async def test_job_progress_context_includes_current_step(
        self,
        emitter: JobLogEmitter,
        mock_redis_client: MagicMock,
        sample_job_id: str,
    ) -> None:
        """current_step must reach the payload under its own key, not as None.

        The existing test reads progress_percent/items_processed/items_total from
        this same dict but never current_step, so both the rename and the
        "current_step": None mutants passed.
        """
        await emitter.emit_job_progress(
            sample_job_id, 40, current_step="Exporting", items_processed=40, items_total=100
        )

        data = json.loads(mock_redis_client.publish.call_args[0][1])["data"]
        assert data["level"] == "INFO"
        assert data["context"] == {
            "progress_percent": 40,
            "current_step": "Exporting",
            "items_processed": 40,
            "items_total": 100,
        }

        # Without a step the key must be absent entirely, not None-valued.
        mock_redis_client.publish.reset_mock()
        await emitter.emit_job_progress(sample_job_id, 60)
        bare = json.loads(mock_redis_client.publish.call_args[0][1])["data"]["context"]
        assert "current_step" not in bare
```

### 5. Kills C1 `CC_1`, C2 `CC_2`/`_3`/`_4`, E2 `CC_15`, F1 `CC_23`/`_24` (7) — `test_job_completed_without_duration_message_and_full_context`

```python
    @pytest.mark.asyncio
    async def test_job_completed_without_duration_message_and_full_context(
        self,
        emitter: JobLogEmitter,
        mock_redis_client: MagicMock,
        sample_job_id: str,
    ) -> None:
        """The no-duration branch is the only untested message path in the module.

        It also proves the payload stays WS-renderable: useJobLogsWebSocket drops any
        message whose data.message is not a string, so message=None makes the
        completion event silently vanish (and emit_log's message[:50] debug f-string
        raises, which its except swallows into a bogus emit_error).
        """
        assert await emitter.emit_job_completed(job_id=sample_job_id, result={"ok": True}) is True

        data = json.loads(mock_redis_client.publish.call_args[0][1])["data"]
        assert data["message"] == "Job completed successfully"
        assert data["level"] == "INFO"
        assert data["context"] == {
            "status": "completed",
            "result": {"ok": True},
            "duration_seconds": None,
        }
        assert emitter.emit_errors == 0
```

### 6. Kills F1 `CF_15`,`CF_16` (2) — `test_job_failed_payload_pins_error_key`

```python
    @pytest.mark.asyncio
    async def test_job_failed_payload_pins_error_key(
        self,
        emitter: JobLogEmitter,
        mock_redis_client: MagicMock,
        sample_job_id: str,
    ) -> None:
        """error text must land under "error" — status/error_code/retryable are pinned, it is not."""
        await emitter.emit_job_failed(
            sample_job_id,
            error="Database connection failed",
            error_code="DB_ERROR",
            retryable=False,
        )

        data = json.loads(mock_redis_client.publish.call_args[0][1])["data"]
        assert data["message"] == "Job failed: Database connection failed"
        assert data["level"] == "ERROR"
        assert data["context"] == {
            "status": "failed",
            "error": "Database connection failed",
            "error_code": "DB_ERROR",
            "retryable": False,
        }
```

### Coverage map

| Test | Mutants killed | N |
|---|---|---|
| 1 | `CS_1`, `CP_17`, `CC_7`, `CF_1` | 4 |
| 2 | `EL_45` | 1 |
| 3 | `CS_9`, `CS_13`, `CS_14` | 3 |
| 4 | `CP_25`, `CP_6`, `CP_7`, `CP_8` | 4 |
| 5 | `CC_1`, `CC_2`, `CC_3`, `CC_4`, `CC_15`, `CC_23`, `CC_24` | 7 |
| 6 | `CF_15`, `CF_16` | 2 |
| | **Total** | **21 / 21 TEST-GAP** |

---

## Notes for the fix lane

- **Nothing here is verified**: no test ran and no repo file was modified in this session (harness constraint). Only this dossier was written.
- The 31 EQUIVALENT survivors are dominated by two mechanically-generated families — `XXkeyXX`/`KEY` renames **inside `extra=` dicts**, and log-message `XX`-wrapper/case rewording. Both land on `LogRecord` attributes no test in the repo captures. Recommend both families (A1, A2, A3, B1, B2, H1, H2, H4 = 26) go on the baseline suppress list rather than be chased.
- Genuinely unkillable — spend no fix time on them: **E3** (4 case-flips, erased by `.upper()` at `:125`), **E1** (`datetime.now(None)` *is* `datetime.now()`, and no consumer can observe tz-awareness), **A3/H4** (`str(None)`, key set unchanged).
- Remaining LOW-VALUE (8): A4 (4 startup-banner texts), B3 (2 `extra` value tweaks), H3 (2 `exc_info` flips). Suppress rather than test — asserting any of them pins diagnostics for zero behavioural protection.
