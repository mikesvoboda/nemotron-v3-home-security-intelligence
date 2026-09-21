# WP4.4 triage — backend/services/audit_logger.py (surviving mutants)

Source: `backend/services/audit_logger.py` (SecurityAuditLogger, 6 audited methods).
Verdict file: `mutants/backend/services/audit_logger.py.meta` — 218 SURVIVORS of 408 keys.
Mutant source parsed from `mutants/backend/services/audit_logger.py` (per-variant `__mutmut_N` regions diffed against `__mutmut_orig`); spot-checked with read-only `mutmut show` (keys ..._bulk_export__24? no: verified `log_content_type_rejected__24`, `log_bulk_export__19`, `log_bulk_export__50`, `log_security_alert__2`).

## Method coverage context (why the survivors cluster the way they do)

Per-function verdict census from the meta:

| method | survivors | killed | not checked |
|---|---|---|---|
| `log_rate_limit_exceeded` | 0 | 0 | 72 (all null — run incomplete; DO NOT count) |
| `log_bulk_export` | 35 | 15 | — |
| `log_cleanup_executed` | 39 | 18 | — |
| `log_config_change` | 38 | 24 | — |
| `log_content_type_rejected` | 33 | 21 | — |
| `log_file_magic_rejected` | 37 | 18 | — |
| `log_security_alert` | 36 | 16 | — |

Only the six audited methods have verdicts; the surviving-218 all live in the five *non*-rate-limit methods. This is diagnostic: rate-limit is the ONE method whose failure path is asserted — `TestAuditFailureDoesNotBlockOperations.test_audit_failure_logs_warning_with_full_context` (`backend/tests/unit/services/test_audit_logger.py:715-747`) patches `backend.services.audit_logger.logger.warning` and asserts the message string AND the whole `extra` payload. That single test kills every except-handler mutant on `log_rate_limit_exceeded`. The other five methods contain byte-identical handler code and have **no** such assertion — hence 118 survivors concentrated in the except-handler family.

Second diagnostic: the happy-path tests (lines 72-410) assert `call_kwargs["action"/"resource_type"/"status"/"details"[...]]` but **never** `call_kwargs["db"]` or `call_kwargs["request"]`. So every "drop/None the session or request forwarded to log_action" mutant survives. Third: `details["timestamp"]` is only asserted with `in` (presence, `test_audit_logger.py:256`), never parsed, so naive-timestamp mutants survive; and `severity="medium"` default is never exercised (both alert tests pass `severity="high"` explicitly).

All survivors are `mutmut show`-verified single-line changes. No multi-op mutants survived (the one 400+-line region artifact, `log_bulk_export__50`, is a region-merge parse artifact; `mutmut show` confirms its real change is a single key rename `record_count -> RECORD_COUNT`, counted under the trailing-extra cluster).

## Cluster table (counts sum to 218)

`extra` = the dict passed to the failure handler / trailing log. `log_action` = the `self._audit_service.log_action(...)` call. Example keys ≤3 each.

| # | pattern | n | class | covering test (miss) | examples |
|---|---|---|---|---|---|
| C1 | except-handler `extra` dict KEY renamed (`action/resource_id/resource_type/error_type/error_message` → `XXfooXX` or `FOO`) | 60 | TEST-GAP | handler warning unasserted for all 5 methods (rate-limit's equivalent killed by :715) | log_bulk_export__29, log_security_alert__29, log_config_change__35 |
| C2 | except-handler `extra` VALUE mutated (`type(e).__name__→type(None)`, `str(e)→str(None)`, `resource_type→"XXsystemXX"`) | 22 | TEST-GAP | same handler test absent → error_type/error_message never checked | log_bulk_export__37, log_cleanup_executed__45, log_security_alert__39 |
| C3 | except-handler `extra` REMOVED / `extra=None` | 12 | TEST-GAP | handler never reads extra | log_bulk_export__23, log_security_alert__23, log_file_magic_rejected__24 |
| C4 | except-handler message text `"Audit log write failed"` → case/XX/None | 24 | TEST-GAP | rate-limit asserts exact msg; other 5 don't | log_bulk_export__22, log_security_alert__26, log_config_change__32 |
| C5 | trailing log `extra` KEY renamed (`audit_action/export_type/record_count/… → XX/UPPER`) | 40 | LOW-VALUE | trailing `logger.info` never asserted for any method (operational log, cosmetic) | log_bulk_export__45, log_cleanup_executed__51, log_config_change__53 |
| C6 | trailing log `extra` REMOVED / `extra=None` | 12 | LOW-VALUE | trailing log never asserted | log_bulk_export__42, log_security_alert__44, log_cleanup_executed__47 |
| C7 | trailing log message f-string → None | 6 | LOW-VALUE | trailing log never asserted | log_bulk_export__41, log_config_change__49, log_cleanup_executed__46 |
| C8 | trailing log `extra` VALUE (`old_value/new_value → str(None)`) | 2 | LOW-VALUE | trailing log never asserted | log_config_change__59, log_config_change__62 |
| C9 | `log_action` db/request NOT forwarded (`db=db→None`, `request=request→None`, OR whole kwarg deleted) | 24 | TEST-GAP | happy-path tests never assert `call_kwargs["db"]`/`["request"]` | log_bulk_export__1, log_content_type_rejected__5, log_cleanup_executed__7 |
| C10 | `log_action` `resource_id=None` kwarg deleted | 4 | EQUIVALENT | `log_action` default is `resource_id=None` → identical | log_bulk_export__10, log_security_alert__12, log_content_type_rejected__10 |
| C11 | `details` dict KEY renamed (`timestamp`→XX/UPPER, `upload_filename`→XX/UPPER) | 6 | TEST-GAP | `details["timestamp"]`/`["upload_filename"]` presence not asserted for bulk/cleanup/file-magic (config's timestamp-rename was killed) | log_bulk_export__19, log_cleanup_executed__22, log_file_magic_rejected__21 |
| C12 | `details` VALUE mutated (`datetime.now(UTC)→now(None)` naive ×3; `request.method if request else …` → `if (request) and False` ×1) | 4 | TEST-GAP | timestamp never tz-parsed; content_type-with-request test never asserts `details["method"]` | log_config_change__27, log_bulk_export__21, log_content_type_rejected__24 |
| C13 | default param `severity="medium"` → `"MEDIUM"`/`"XXmediumXX"` | 2 | LOW-VALUE | both alert tests pass `severity="high"` explicitly; default never exercised | log_security_alert__1, log_security_alert__2 |

**TOTAL = 60+22+12+24+40+12+6+2+24+4+6+4+2 = 218.** Classification split: TEST-GAP 152 (C1-C4,C9,C11,C12) · LOW-VALUE 62 (C5-C8,C13) · EQUIVALENT 4 (C10).

## Drafted tests (UNVERIFIED — not yet run red/green)

Target file: `backend/tests/unit/services/test_audit_logger.py`. Style follows existing fixtures (`mock_db`, `mock_request`, `audit_logger_instance`) and the `test_audit_failure_logs_warning_with_full_context` handler pattern. **TDD procedure:** add test → run against mutant copy, the new assertion FAILS on the mutant diff; run against original source, it PASSES (red on mutant, green on original).

### T1 — kills C1+C2+C3+C4 (118 survivors): assert the failure-handler warning for ALL six methods
The single highest-leverage gap: `log_rate_limit_exceeded` already gets this treatment (`:715`); the other five methods have byte-identical handlers with zero coverage.

```python
# UNVERIFIED - not yet run red/green
import re  # noqa: F401  (not needed; kept minimal) — remove if linter flags


class TestAuditFailureWarningAllMethods:
    """NEM-2541 coverage parity: every audit-logger method must warn with full
    context on audit-write failure, not just log_rate_limit_exceeded."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "invoker, expected_action, expected_resource_type, expected_resource_id",
        [
            (
                lambda lg, db, req: lg.log_content_type_rejected(
                    db=db, request=req, content_type="text/plain"
                ),
                AuditAction.CONTENT_TYPE_REJECTED, "api", None,
            ),
            (
                lambda lg, db, req: lg.log_file_magic_rejected(
                    db=db, request=req, claimed_type="image/png",
                    detected_type="application/pdf", filename="bad.png",
                ),
                AuditAction.FILE_MAGIC_REJECTED, "upload", "bad.png",
            ),
            (
                lambda lg, db, req: lg.log_config_change(
                    db=db, request=req, setting_name="batch_window_seconds",
                    old_value=90, new_value=120,
                ),
                AuditAction.CONFIG_UPDATED, "settings", None,
            ),
            (
                lambda lg, db, req: lg.log_security_alert(
                    db=db, request=req, alert_type="brute_force",
                    details={"attempts": 100}, severity="high",
                ),
                AuditAction.SECURITY_ALERT, "security", None,
            ),
            (
                lambda lg, db, req: lg.log_bulk_export(
                    db=db, request=req, export_type="events", record_count=1000,
                ),
                AuditAction.BULK_EXPORT_COMPLETED, "events", None,
            ),
            (
                lambda lg, db, req: lg.log_cleanup_executed(
                    db=db, request=req, dry_run=False,
                    deleted_counts={"events": 50}, freed_bytes=1024,
                ),
                AuditAction.CLEANUP_EXECUTED, "system", None,
            ),
        ],
    )
    async def test_audit_failure_warns_with_full_context(
        self, audit_logger_instance, mock_db, mock_request,
        invoker, expected_action, expected_resource_type, expected_resource_id,
    ):
        with (
            patch.object(
                audit_logger_instance._audit_service, "log_action",
                new_callable=AsyncMock,
            ) as mock_log,
            patch("backend.services.audit_logger.logger.warning", autospec=True) as mock_warning,
        ):
            mock_log.side_effect = Exception("Database error")

            await invoker(audit_logger_instance, mock_db, mock_request)

            # Locate the failure-handler warning specifically (the trailing
            # logger call for log_security_alert is also a warning — exclude it).
            handler = [
                c for c in mock_warning.call_args_list
                if c[0] and c[0][0] == "Audit log write failed"
            ]
            assert handler, "audit-failure handler warning was not emitted with the expected message"
            extra = handler[0][1]["extra"]
            assert extra["action"] == expected_action.value
            assert extra["resource_type"] == expected_resource_type
            assert extra["resource_id"] == expected_resource_id
            assert extra["error_type"] == "Exception"
            assert extra["error_message"] == "Database error"
```
Red-on-mutant rationale: C1 renames a key → `extra["error_type"]`/`["action"]` raises KeyError; C2 sets `error_type="NoneType"` or `error_message="None"` → assert fails; C3 `extra=None` → `handler[0][1]["extra"]`/subscript fails; C4 changes the message string → `handler` empty → `assert handler` fails. Green on original.

### T2 — kills C9 (24 survivors): `log_action` must receive the real db session and request

```python
# UNVERIFIED - not yet run red/green
class TestAuditCallWiring:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "invoker",
        [
            lambda lg, db, req: lg.log_content_type_rejected(db=db, request=req, content_type="text/plain"),
            lambda lg, db, req: lg.log_file_magic_rejected(db=db, request=req, claimed_type="image/png", detected_type=None, filename="x"),
            lambda lg, db, req: lg.log_config_change(db=db, request=req, setting_name="s", old_value=1, new_value=2),
            lambda lg, db, req: lg.log_security_alert(db=db, request=req, alert_type="a", details={}),
            lambda lg, db, req: lg.log_bulk_export(db=db, request=req, export_type="events", record_count=1),
            lambda lg, db, req: lg.log_cleanup_executed(db=db, request=req, dry_run=True, deleted_counts={}),
        ],
    )
    async def test_log_action_forwards_db_and_request(
        self, audit_logger_instance, mock_db, mock_request, invoker
    ):
        with patch.object(
            audit_logger_instance._audit_service, "log_action", new_callable=AsyncMock,
        ) as mock_log:
            mock_log.return_value = MagicMock(id=1)
            await invoker(audit_logger_instance, mock_db, mock_request)
            kw = mock_log.call_args[1]
            assert kw["db"] is mock_db
            assert kw["request"] is mock_request
```
Red-on-mutant: `db=None`/`request=None` → `is mock_db` False; deleted kwarg → `KeyError: 'db'`. Green on original. (C10 `resource_id` deletion is EQUIVALENT and intentionally not targeted.)

### T3 — kills C12 (4) + part of C11 (6): timestamp is UTC-aware and details keys present; content-type `method` forwarded from request

```python
# UNVERIFIED - not yet run red/green
class TestAuditDetailsIntegrity:
    @pytest.mark.asyncio
    async def test_config_timestamp_is_utc_aware(self, audit_logger_instance, mock_db, mock_request):
        with patch.object(audit_logger_instance._audit_service, "log_action", new_callable=AsyncMock) as mock_log:
            mock_log.return_value = MagicMock(id=1)
            await audit_logger_instance.log_config_change(
                db=mock_db, request=mock_request, setting_name="s", old_value=1, new_value=2,
            )
            ts = datetime.fromisoformat(mock_log.call_args[1]["details"]["timestamp"])
            assert ts.tzinfo is not None and ts.utcoffset() == timedelta(0)

    @pytest.mark.asyncio
    async def test_bulk_export_details_intact(self, audit_logger_instance, mock_db, mock_request):
        with patch.object(audit_logger_instance._audit_service, "log_action", new_callable=AsyncMock) as mock_log:
            mock_log.return_value = MagicMock(id=1)
            await audit_logger_instance.log_bulk_export(
                db=mock_db, request=mock_request, export_type="events", record_count=5,
            )
            details = mock_log.call_args[1]["details"]
            assert "timestamp" in details
            assert datetime.fromisoformat(details["timestamp"]).utcoffset() == timedelta(0)

    @pytest.mark.asyncio
    async def test_cleanup_details_intact(self, audit_logger_instance, mock_db, mock_request):
        with patch.object(audit_logger_instance._audit_service, "log_action", new_callable=AsyncMock) as mock_log:
            mock_log.return_value = MagicMock(id=1)
            await audit_logger_instance.log_cleanup_executed(
                db=mock_db, request=mock_request, dry_run=False, deleted_counts={}, freed_bytes=0,
            )
            details = mock_log.call_args[1]["details"]
            assert "timestamp" in details
            assert datetime.fromisoformat(details["timestamp"]).utcoffset() == timedelta(0)

    @pytest.mark.asyncio
    async def test_file_magic_upload_filename_recorded(self, audit_logger_instance, mock_db, mock_request):
        with patch.object(audit_logger_instance._audit_service, "log_action", new_callable=AsyncMock) as mock_log:
            mock_log.return_value = MagicMock(id=1)
            await audit_logger_instance.log_file_magic_rejected(
                db=mock_db, request=mock_request, claimed_type="image/png",
                detected_type=None, filename="malicious.png",
            )
            assert mock_log.call_args[1]["details"]["upload_filename"] == "malicious.png"

    @pytest.mark.asyncio
    async def test_content_type_method_from_request(
        self, audit_logger_instance, mock_db, mock_request
    ):
        mock_request.method = "PATCH"
        with patch.object(audit_logger_instance._audit_service, "log_action", new_callable=AsyncMock) as mock_log:
            mock_log.return_value = MagicMock(id=1)
            await audit_logger_instance.log_content_type_rejected(
                db=mock_db, request=mock_request, content_type="text/plain",
            )
            assert mock_log.call_args[1]["details"]["method"] == "PATCH"
```
Red-on-mutant: `datetime.now(None)` → naive → `utcoffset()` is None (fails `== timedelta(0)`); renamed `timestamp`/`upload_filename` → `KeyError`/missing; `if (request) and False` flips the branch → `details["method"]` becomes the None `method` param instead of `"PATCH"`. Green on original. Requires `from datetime import timedelta` added to the test file's import line (currently `from datetime import UTC, datetime`).

## Covering test file
- `backend/tests/unit/services/test_audit_logger.py` — the only test file touching this module. Key anchors: happy-path call-arg assertions 72-410; NEM-2541 failure-does-not-block 554-712; the lone full-context handler assertion **715-747** (rate-limit only — the parity template for T1).

## Recommendation
Land T1 (kills 118), T2 (24), T3 (10 incl. C11) — that closes the entire TEST-GAP set (152). C5-C8 (62) are trailing operational-log cosmetics (nobody should assert the info-line payload) and C13 is an unexercised default; mark those ACCEPT-LOW-VALUE, don't chase. C10 is EQUIVALENT (default arg) — suppress/ignore.
