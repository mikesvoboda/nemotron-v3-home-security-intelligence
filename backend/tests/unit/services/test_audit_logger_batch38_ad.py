# TARGET-MODULE: backend.services.audit_logger
"""Battery AD — campaign #28 batch-38 killers for audit_logger.

Campaign #28 (ladder to 85%): the 242 survivor keys sit on the EMISSION
surface of the seven SecurityAuditLogger methods (log_cleanup_executed 39,
log_config_change 38, log_file_magic_rejected 37, log_security_alert 36,
log_bulk_export 35, log_content_type_rejected 33, log_rate_limit_exceeded
24). The shipped suite calls every method and asserts a FEW
call_kwargs["details"]["..."] members - never the WHOLE payload, never the
log records. Each method has three observable surfaces and this battery
pins all of them:

  * the AuditService.log_action call as the RAW kwargs dict. The spy is
    installed by swapping al.AuditService BEFORE constructing the logger
    (the ctor reads the module global at call time), so the recorder sees
    the call as it is literally made. This is deliberate: log_action's
    params have defaults (resource_id=None, status=AuditStatus.SUCCESS)
    under which kwarg-DELETION arms are value-invisible at the callee - a
    signature-faithful spy would silently refill them. The recorder takes
    **kwargs and the tests assert dict EQUALITY plus the sorted-key
    census, so a deleted kwarg is a MISSING KEY, not a refilled default
    (campaign #26's dropped-kwarg lesson); db/request are pinned by
    IDENTITY, the enum members by identity (is, so .value-flip arms die),
    details by whole-dict equality with the volatile timestamp slot
    verified by POLARITY (STAMP placeholder: name censused + ISO parse +
    utcoffset is not None - kills datetime.now(None)'s naive stamp and
    key renames), severity/actor/path/method by value;
  * the except-branch warning: triggered by a raising spy, pinned as the
    FULL msgs() sequence ["Audit log write failed", <tail info>] with
    the extras read by NAME (hasattr + value equality for
    action/resource_id/resource_type/error_type/error_message - kills the
    XX/CASE key renames, the extra=None/deletion, and the
    type(None)/str(None) VALUE arms since the injected error is
    RuntimeError("boom"));
  * the tail record: exact f-string msg (a None value renders "None"),
    exact LEVELNO (security alert is WARNING, all others INFO - kills
    info<->warning swaps), and the extras dict by selected names (the
    ContextFilter injects ambient keys onto every record, so names are
    selected, never censused on the record - campaign #12's lesson).

Why the shipped partial asserts leave 242 survivors: they read
call_kwargs["details"]["record_count"] style paths - a key RENAMED in the
details dict fails only if something READS the old name, the callee
defaults hide the kwarg deletions, and the except/info surfaces are
never observed at all.

Style notes for the b30 sweep (module-level sync test_* only, zero args):
async calls run under asyncio.run INSIDE each test; the request double is
a SimpleNamespace (duck-typed: client.host / url.path / method); the
logger is constructed FRESH per test inside the AuditService swap.

Honesty ledger (EQUIV candidates REGISTERED BY CONSTRUCTION; the sweep
verdict + per-key probes are the evidence - a construction claim is not a
verdict claim).

  Not equivalent, KILLABLE - the arms and where they die:
  - db -> None / db deleted: identity pin + key census (every method).
  - request -> None / request deleted: identity pin + key census; the
    details path/method fallback polarity is a separate value pin.
  - resource_id=None / actor=... / status=... DELETIONS: MISSING KEY in
    the raw kwargs census (value-equal callee defaults are exactly what
    the raw-recorder design exists to catch).
  - details key XX/CASE renames and datetime.now(None): whole-dict
    equality + the STAMP-slot parse with utcoffset.
  - "Audit log write failed" -> None/XX/CASE and extras None/deleted/
    renamed/type(None)/str(None): full failure-round msgs() sequence +
    named extras equality under RuntimeError("boom").
  - tail msgs -> None and extras renames/None/deleted: full msgs() +
    named extras equality + levelno.
  - severity default arms: default-severity round pins details and
    extras severity == "medium".
  - actor arms: no-ip round pins "unknown" (kills `if ip or True` ->
    "ip:unknown", the XX/CASE arms); request round pins
    "ip:192.xxx.xxx.xxx" (kills the ip = None arm).
  - _serialize_value passthrough: config round passes 90/120 through the
    real function and pins both details and info-side str() renderings.

  EQUIV candidates REGISTERED: none yet - every mapped arm has an
  observable polarity under the whole-census design. If the sweep goes
  GREEN on any of them it is re-adjudicated (live-task lesson: check the
  callee's early-return/equality paths before crediting an overwrite or
  a default).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from backend.models.audit import AuditAction, AuditStatus
from backend.services import audit_logger as al

# ---------------------------------------------------------------------------
# capture / spy helpers (no fixtures - the sweep calls plain functions)
# ---------------------------------------------------------------------------


class RecordList(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def msgs(self) -> list[str]:
        return [r.getMessage() for r in self.records]

    def one(self, msg: str) -> logging.LogRecord:
        hits = [r for r in self.records if r.getMessage() == msg]
        assert len(hits) == 1, (msg, self.msgs())
        return hits[0]


@contextmanager
def logcap():
    cap = RecordList()
    old_level = al.logger.level
    al.logger.addHandler(cap)
    al.logger.setLevel(logging.DEBUG)
    try:
        yield cap
    finally:
        al.logger.removeHandler(cap)
        al.logger.setLevel(old_level)


def extras(rec: logging.LogRecord, names: list[str]) -> dict[str, Any]:
    """Selected extras by NAME (never a record-attr census: ContextFilter
    injects ambient keys - request_id/correlation_id/... - on every
    record)."""
    out: dict[str, Any] = {}
    for name in names:
        assert hasattr(rec, name), (name, "attribute missing from record")
        out[name] = getattr(rec, name)
    return out


class SpyService:
    """Raw **kwargs recorder for AuditService.log_action.

    NO signature - log_action's defaults (resource_id=None,
    status=SUCCESS) make kwarg deletions value-invisible if the spy
    refilled them; the raw kwargs dict keeps a deletion as a MISSING KEY.
    Raises the injected error when set (drives the except branch)."""

    def __init__(self, raises: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.raises = raises

    async def log_action(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises


@contextmanager
def spy_logger(raises: Exception | None = None):
    """Swap al.AuditService (the ctor reads the module global), construct
    a fresh SecurityAuditLogger bound to the spy."""
    old_cls = al.AuditService
    svc = SpyService(raises=raises)
    al.AuditService = lambda: svc
    try:
        yield al.SecurityAuditLogger()
    finally:
        al.AuditService = old_cls


def run(coro: Any) -> Any:
    return asyncio.run(coro)


DB = object()  # identity-pinned sentinel session
STAMP = object()  # placeholder for the volatile datetime stamp slot


def make_request() -> Any:
    return SimpleNamespace(
        client=SimpleNamespace(host="192.168.1.100"),
        url=SimpleNamespace(path="/api/x"),
        method="POST",
    )


def pin_timestamp(stamp: Any) -> None:
    """The datetime.now(UTC).isoformat() polarity: tz-aware ISO string
    (now(None) mutants produce a naive stamp -> utcoffset() None)."""
    assert isinstance(stamp, str)
    assert datetime.fromisoformat(stamp).utcoffset() is not None, stamp


def pin_call(spy: SpyService, expected: dict[str, Any]) -> dict[str, Any]:
    """Whole raw-kwargs equality + key census; returns the recorded dict.

    A details entry whose expected value is STAMP is verified by the
    timestamp polarity instead of literal equality (its NAME is still
    censused; every other key/value is whole-pinned)."""
    assert len(spy.calls) == 1, spy.calls
    k = spy.calls[0]
    assert sorted(k) == sorted(expected), (sorted(k), sorted(expected))
    got, exp = dict(k), dict(expected)
    if isinstance(exp.get("details"), dict) and any(v is STAMP for v in exp["details"].values()):
        got_d, exp_d = dict(got["details"]), dict(exp["details"])
        assert sorted(got_d) == sorted(exp_d), (sorted(got_d), sorted(exp_d))
        for name in [n for n, v in exp_d.items() if v is STAMP]:
            exp_d.pop(name)
            pin_timestamp(got_d.pop(name))
        assert got_d == exp_d, (got_d, exp_d)
        got.pop("details")
        exp.pop("details")
    assert got == exp, (got, exp)
    return k


# ---------------------------------------------------------------------------
# log_rate_limit_exceeded
# ---------------------------------------------------------------------------


def test_rate_limit_request_round() -> None:
    req = make_request()

    async def go() -> None:
        with spy_logger() as log, logcap() as cap:
            await log.log_rate_limit_exceeded(DB, req, tier="gold", current_count=65, limit=60)
        k = pin_call(
            log._audit_service,
            {
                "db": DB,
                "action": AuditAction.RATE_LIMIT_EXCEEDED,
                "resource_type": "api",
                "resource_id": None,
                "actor": "ip:192.xxx.xxx.xxx",  # mask_ip out; ip=None -> "unknown"
                "details": {
                    "tier": "gold",
                    "current_count": 65,
                    "limit": 60,
                    "path": "/api/x",
                    "method": "POST",
                },
                "request": req,
                "status": AuditStatus.FAILURE,
            },
        )
        assert k["request"] is req and k["db"] is DB
        assert k["action"] is AuditAction.RATE_LIMIT_EXCEEDED
        assert cap.msgs() == ["Audit: Rate limit exceeded for tier gold"]
        rec = cap.one("Audit: Rate limit exceeded for tier gold")
        assert rec.levelno == logging.INFO
        assert extras(rec, ["audit_action", "tier", "current_count", "limit"]) == {
            "audit_action": "rate_limit_exceeded",
            "tier": "gold",
            "current_count": 65,
            "limit": 60,
        }

    run(go())


def test_rate_limit_no_request_round() -> None:
    async def go() -> None:
        with spy_logger() as log, logcap() as cap:
            await log.log_rate_limit_exceeded(DB, None, tier="gold", current_count=65, limit=60)
        k = pin_call(
            log._audit_service,
            {
                "db": DB,
                "action": AuditAction.RATE_LIMIT_EXCEEDED,
                "resource_type": "api",
                "resource_id": None,
                "actor": "unknown",  # or-True arm -> "ip:unknown"; case arms die
                "details": {
                    "tier": "gold",
                    "current_count": 65,
                    "limit": 60,
                    "path": None,
                    "method": None,
                },
                "request": None,
                "status": AuditStatus.FAILURE,
            },
        )
        assert k["request"] is None
        assert cap.msgs() == ["Audit: Rate limit exceeded for tier gold"]

    run(go())


def test_rate_limit_failure_round() -> None:
    async def go() -> None:
        with spy_logger(raises=RuntimeError("boom")) as log, logcap() as cap:
            await log.log_rate_limit_exceeded(DB, None, tier="gold", current_count=65, limit=60)
        assert len(log._audit_service.calls) == 1
        assert cap.msgs() == [
            "Audit log write failed",
            "Audit: Rate limit exceeded for tier gold",
        ]
        rec = cap.one("Audit log write failed")
        assert rec.levelno == logging.WARNING
        assert extras(
            rec,
            ["action", "resource_id", "resource_type", "error_type", "error_message"],
        ) == {
            "action": "rate_limit_exceeded",
            "resource_id": None,
            "resource_type": "api",  # value arms XXapiXX/API die on equality
            "error_type": "RuntimeError",  # type(None) -> "NoneType"
            "error_message": "boom",  # str(None) -> "None"
        }

    run(go())


# ---------------------------------------------------------------------------
# log_content_type_rejected
# ---------------------------------------------------------------------------


def test_content_type_request_round() -> None:
    req = make_request()

    async def go() -> None:
        with spy_logger() as log, logcap() as cap:
            await log.log_content_type_rejected(
                DB, req, content_type="text/html", path="/fallback", method="PUT"
            )
        # request WINS over the fallback kwargs (an and-False arm falls
        # back to "PUT" even with a live request)
        pin_call(
            log._audit_service,
            {
                "db": DB,
                "action": AuditAction.CONTENT_TYPE_REJECTED,
                "resource_type": "api",
                "resource_id": None,  # deletion -> missing key, census kills it
                "details": {
                    "content_type": "text/html",
                    "path": "/api/x",
                    "method": "POST",
                },
                "request": req,
                "status": AuditStatus.FAILURE,
            },
        )
        assert cap.msgs() == ["Audit: Content-Type rejected: text/html"]
        rec = cap.one("Audit: Content-Type rejected: text/html")
        assert rec.levelno == logging.INFO
        assert extras(rec, ["audit_action", "content_type"]) == {
            "audit_action": "content_type_rejected",
            "content_type": "text/html",
        }

    run(go())


def test_content_type_fallback_round() -> None:
    async def go() -> None:
        with spy_logger() as log, logcap():
            await log.log_content_type_rejected(
                DB, None, content_type="text/html", path="/fallback", method="PUT"
            )
        pin_call(
            log._audit_service,
            {
                "db": DB,
                "action": AuditAction.CONTENT_TYPE_REJECTED,
                "resource_type": "api",
                "resource_id": None,
                "details": {
                    "content_type": "text/html",
                    "path": "/fallback",
                    "method": "PUT",
                },
                "request": None,
                "status": AuditStatus.FAILURE,
            },
        )

    run(go())


def test_content_type_failure_round() -> None:
    async def go() -> None:
        with spy_logger(raises=RuntimeError("boom")) as log, logcap() as cap:
            await log.log_content_type_rejected(
                DB, None, content_type="text/html", path="/p", method="PUT"
            )
        assert cap.msgs() == [
            "Audit log write failed",
            "Audit: Content-Type rejected: text/html",
        ]
        rec = cap.one("Audit log write failed")
        assert rec.levelno == logging.WARNING
        assert extras(
            rec,
            ["action", "resource_id", "resource_type", "error_type", "error_message"],
        ) == {
            "action": "content_type_rejected",
            "resource_id": None,
            "resource_type": "api",
            "error_type": "RuntimeError",
            "error_message": "boom",
        }

    run(go())


# ---------------------------------------------------------------------------
# log_file_magic_rejected
# ---------------------------------------------------------------------------


def test_file_magic_round() -> None:
    async def go() -> None:
        req = make_request()
        with spy_logger() as log, logcap() as cap:
            await log.log_file_magic_rejected(
                DB,
                req,
                claimed_type="image/png",
                detected_type="application/x-ms",
                filename="evil.exe",
            )
        pin_call(
            log._audit_service,
            {
                "db": DB,
                "action": AuditAction.FILE_MAGIC_REJECTED,
                "resource_type": "upload",
                "resource_id": "evil.exe",
                "details": {
                    "claimed_type": "image/png",
                    "detected_type": "application/x-ms",
                    "upload_filename": "evil.exe",
                },
                "request": req,
                "status": AuditStatus.FAILURE,
            },
        )
        assert cap.msgs() == [
            "Audit: File magic rejected: claimed image/png, detected application/x-ms"
        ]
        rec = cap.one("Audit: File magic rejected: claimed image/png, detected application/x-ms")
        assert rec.levelno == logging.INFO
        assert extras(
            rec, ["audit_action", "claimed_type", "detected_type", "upload_filename"]
        ) == {
            "audit_action": "file_magic_rejected",
            "claimed_type": "image/png",
            "detected_type": "application/x-ms",
            "upload_filename": "evil.exe",
        }

    run(go())


def test_file_magic_no_filename_round() -> None:
    async def go() -> None:
        with spy_logger() as log, logcap() as cap:
            await log.log_file_magic_rejected(
                DB, None, claimed_type="image/png", detected_type=None
            )
        pin_call(
            log._audit_service,
            {
                "db": DB,
                "action": AuditAction.FILE_MAGIC_REJECTED,
                "resource_type": "upload",
                "resource_id": None,
                "details": {
                    "claimed_type": "image/png",
                    "detected_type": None,
                    "upload_filename": None,
                },
                "request": None,
                "status": AuditStatus.FAILURE,
            },
        )
        assert cap.msgs() == ["Audit: File magic rejected: claimed image/png, detected None"]

    run(go())


def test_file_magic_failure_round() -> None:
    async def go() -> None:
        with spy_logger(raises=RuntimeError("boom")) as log, logcap() as cap:
            await log.log_file_magic_rejected(
                DB,
                None,
                claimed_type="image/png",
                detected_type=None,
                filename="evil.exe",
            )
        assert cap.msgs() == [
            "Audit log write failed",
            "Audit: File magic rejected: claimed image/png, detected None",
        ]
        rec = cap.one("Audit log write failed")
        assert rec.levelno == logging.WARNING
        assert extras(
            rec,
            ["action", "resource_id", "resource_type", "error_type", "error_message"],
        ) == {
            "action": "file_magic_rejected",
            "resource_id": "evil.exe",
            "resource_type": "upload",
            "error_type": "RuntimeError",
            "error_message": "boom",
        }

    run(go())


# ---------------------------------------------------------------------------
# log_config_change
# ---------------------------------------------------------------------------


def test_config_change_round() -> None:
    async def go() -> None:
        req = make_request()
        with spy_logger() as log, logcap() as cap:
            await log.log_config_change(
                DB,
                req,
                setting_name="batch_window_seconds",
                old_value=90,
                new_value=120,
                resource_id="cam-1",
            )
        pin_call(
            log._audit_service,
            {
                "db": DB,
                "action": AuditAction.CONFIG_UPDATED,
                "resource_type": "settings",
                "resource_id": "cam-1",
                "details": {
                    "setting": "batch_window_seconds",
                    "old_value": 90,  # _serialize_value passthrough
                    "new_value": 120,
                    "timestamp": STAMP,  # name censused; tz-aware ISO polarity
                },
                "request": req,
                "status": AuditStatus.SUCCESS,
            },
        )
        assert cap.msgs() == ["Audit: Config change: batch_window_seconds"]
        rec = cap.one("Audit: Config change: batch_window_seconds")
        assert rec.levelno == logging.INFO
        assert extras(rec, ["audit_action", "setting_name", "old_value", "new_value"]) == {
            "audit_action": "config_updated",
            "setting_name": "batch_window_seconds",
            "old_value": "90",  # info-side str(); str(None) -> "None" arms die
            "new_value": "120",
        }

    run(go())


def test_config_change_failure_round() -> None:
    async def go() -> None:
        with spy_logger(raises=RuntimeError("boom")) as log, logcap() as cap:
            await log.log_config_change(
                DB, None, setting_name="s", old_value=1, new_value=2, resource_id="cam-9"
            )
        assert cap.msgs() == ["Audit log write failed", "Audit: Config change: s"]
        rec = cap.one("Audit log write failed")
        assert rec.levelno == logging.WARNING
        assert extras(
            rec,
            ["action", "resource_id", "resource_type", "error_type", "error_message"],
        ) == {
            "action": "config_updated",
            "resource_id": "cam-9",
            "resource_type": "settings",
            "error_type": "RuntimeError",
            "error_message": "boom",
        }

    run(go())


# ---------------------------------------------------------------------------
# log_security_alert
# ---------------------------------------------------------------------------


def test_security_alert_default_severity_round() -> None:
    async def go() -> None:
        req = make_request()
        with spy_logger() as log, logcap() as cap:
            await log.log_security_alert(DB, req, alert_type="port_scan", details={"host": "h1"})
        pin_call(
            log._audit_service,
            {
                "db": DB,
                "action": AuditAction.SECURITY_ALERT,
                "resource_type": "security",
                "resource_id": None,
                "details": {
                    "alert_type": "port_scan",
                    "severity": "medium",  # default arm; XXmediumXX/MEDIUM die
                    "host": "h1",  # the **details spread is pinned too
                },
                "request": req,
                "status": AuditStatus.FAILURE,
            },
        )
        assert cap.msgs() == ["Audit: Security alert: port_scan"]
        rec = cap.one("Audit: Security alert: port_scan")
        assert rec.levelno == logging.WARNING  # the ONLY warning tail
        assert extras(rec, ["audit_action", "alert_type", "severity", "host"]) == {
            "audit_action": "security_alert",
            "alert_type": "port_scan",
            "severity": "medium",
            "host": "h1",
        }

    run(go())


def test_security_alert_explicit_severity_round() -> None:
    async def go() -> None:
        with spy_logger() as log, logcap():
            await log.log_security_alert(
                DB, None, alert_type="intrusion", details={}, severity="critical"
            )
        pin_call(
            log._audit_service,
            {
                "db": DB,
                "action": AuditAction.SECURITY_ALERT,
                "resource_type": "security",
                "resource_id": None,
                "details": {"alert_type": "intrusion", "severity": "critical"},
                "request": None,
                "status": AuditStatus.FAILURE,
            },
        )

    run(go())


def test_security_alert_failure_round() -> None:
    async def go() -> None:
        with spy_logger(raises=RuntimeError("boom")) as log, logcap() as cap:
            await log.log_security_alert(DB, None, alert_type="a", details={})
        assert cap.msgs() == ["Audit log write failed", "Audit: Security alert: a"]
        rec = cap.one("Audit log write failed")
        assert rec.levelno == logging.WARNING
        assert extras(
            rec,
            ["action", "resource_id", "resource_type", "error_type", "error_message"],
        ) == {
            "action": "security_alert",
            "resource_id": None,
            "resource_type": "security",
            "error_type": "RuntimeError",
            "error_message": "boom",
        }

    run(go())


# ---------------------------------------------------------------------------
# log_bulk_export
# ---------------------------------------------------------------------------


def test_bulk_export_round() -> None:
    async def go() -> None:
        req = make_request()
        with spy_logger() as log, logcap() as cap:
            await log.log_bulk_export(
                DB, req, export_type="events", record_count=1500, filters={"days": 7}
            )
        pin_call(
            log._audit_service,
            {
                "db": DB,
                "action": AuditAction.BULK_EXPORT_COMPLETED,
                "resource_type": "events",  # export_type flows into resource_type
                "resource_id": None,  # deletion -> missing key, census kills
                "details": {
                    "record_count": 1500,
                    "filters": {"days": 7},
                    "timestamp": STAMP,
                },
                "request": req,
                "status": AuditStatus.SUCCESS,  # deletion refills SUCCESS at
                # the callee - the RAW kwargs census sees the MISSING KEY
            },
        )
        assert cap.msgs() == ["Audit: Bulk export completed: 1500 events records"]
        rec = cap.one("Audit: Bulk export completed: 1500 events records")
        assert rec.levelno == logging.INFO
        assert extras(rec, ["audit_action", "export_type", "record_count"]) == {
            "audit_action": "bulk_export_completed",
            "export_type": "events",
            "record_count": 1500,
        }

    run(go())


def test_bulk_export_no_filters_round() -> None:
    async def go() -> None:
        with spy_logger() as log, logcap():
            await log.log_bulk_export(DB, None, export_type="detections", record_count=3)
        k = log._audit_service.calls[0]
        assert k["details"]["filters"] == {}  # `or {}` polarity
        assert k["request"] is None

    run(go())


def test_bulk_export_failure_round() -> None:
    async def go() -> None:
        with spy_logger(raises=RuntimeError("boom")) as log, logcap() as cap:
            await log.log_bulk_export(DB, None, export_type="events", record_count=1)
        assert cap.msgs() == [
            "Audit log write failed",
            "Audit: Bulk export completed: 1 events records",
        ]
        rec = cap.one("Audit log write failed")
        assert rec.levelno == logging.WARNING
        assert extras(
            rec,
            ["action", "resource_id", "resource_type", "error_type", "error_message"],
        ) == {
            "action": "bulk_export_completed",
            "resource_id": None,
            "resource_type": "events",
            "error_type": "RuntimeError",
            "error_message": "boom",
        }

    run(go())


# ---------------------------------------------------------------------------
# log_cleanup_executed
# ---------------------------------------------------------------------------


def test_cleanup_round() -> None:
    async def go() -> None:
        req = make_request()
        with spy_logger() as log, logcap() as cap:
            await log.log_cleanup_executed(
                DB, req, dry_run=True, deleted_counts={"events": 4}, freed_bytes=8192
            )
        pin_call(
            log._audit_service,
            {
                "db": DB,
                "action": AuditAction.CLEANUP_EXECUTED,
                "resource_type": "system",
                "resource_id": None,  # deletion -> census
                "details": {
                    "dry_run": True,
                    "deleted_counts": {"events": 4},
                    "freed_bytes": 8192,
                    "timestamp": STAMP,
                },
                "request": req,
                "status": AuditStatus.SUCCESS,
            },
        )
        assert cap.msgs() == ["Audit: Cleanup executed (dry_run=True)"]
        rec = cap.one("Audit: Cleanup executed (dry_run=True)")
        assert rec.levelno == logging.INFO
        assert extras(rec, ["audit_action", "dry_run", "deleted_counts", "freed_bytes"]) == {
            "audit_action": "cleanup_executed",
            "dry_run": True,
            "deleted_counts": {"events": 4},
            "freed_bytes": 8192,
        }

    run(go())


def test_cleanup_dry_run_false_round() -> None:
    async def go() -> None:
        with spy_logger() as log, logcap() as cap:
            await log.log_cleanup_executed(
                DB, None, dry_run=False, deleted_counts={}, freed_bytes=None
            )
        assert cap.msgs() == ["Audit: Cleanup executed (dry_run=False)"]
        k = log._audit_service.calls[0]
        assert k["details"]["dry_run"] is False
        assert k["details"]["freed_bytes"] is None

    run(go())


def test_cleanup_failure_round() -> None:
    async def go() -> None:
        with spy_logger(raises=RuntimeError("boom")) as log, logcap() as cap:
            await log.log_cleanup_executed(DB, None, dry_run=True, deleted_counts={})
        assert cap.msgs() == [
            "Audit log write failed",
            "Audit: Cleanup executed (dry_run=True)",
        ]
        rec = cap.one("Audit log write failed")
        assert rec.levelno == logging.WARNING
        assert extras(
            rec,
            ["action", "resource_id", "resource_type", "error_type", "error_message"],
        ) == {
            "action": "cleanup_executed",
            "resource_id": None,
            "resource_type": "system",
            "error_type": "RuntimeError",
            "error_message": "boom",
        }

    run(go())
