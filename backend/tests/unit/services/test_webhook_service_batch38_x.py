# TARGET-MODULE: backend.services.webhook_service
"""Battery X — campaign #22 of the ladder (batch-38): kill-real coverage for
``backend/services.webhook_service.py`` (262 survivors at 75.7183% entering).

Harness-compatible by design (batch-30 single-process sweep): every test is a
module-level sync ``test_*()`` with no fixtures and no parametrize; coroutines
run through ``asyncio.run`` inside. The file is also collected by normal
pytest in the repo tree, and every seam swap is restored on context exit.

What kills what (each polarity MEASURED against the shipped code before the
assert was written):

* COMPILED-SQL MIRRORS — the fake session records every executed statement
  as ``str(stmt.compile(literal_binds))`` and tests assert the whole list
  against plain-code mirrors built from the real expressions. ``select(X) ->
  select(None)`` renders ``SELECT NULL AS anon_1``, ``.where(clause) ->
  .where(None)`` and ``and_(a, None)`` render ``NULL``, ``and_(a, b) ->
  and_(a)`` drops the conjunct, ``is_(True) -> is_(None)/(False)`` render
  ``IS NULL``/``IS false``, ``any(v) -> any(None)`` renders ``NULL = ANY``,
  ``== -> !=`` renders ``!=``, and a call-arg flip ``get_webhook(db, None)``
  renders ``id = NULL``. ``db.execute(None)`` cannot compile and is recorded
  as ``<unrenderable AttributeError>``. Every flip becomes a string.
* NON-ENUM POLARITIES — for a real ``StrEnum`` the
  ``x.value if hasattr(x, "value") else str(x)`` family is invisible
  (``str(enum) == enum.value``), so each site ALSO runs with (a) ``_Event``
  whose ``.value`` differs from its ``str()`` — the and-False,
  ``hasattr(None, ...)`` and ``"value" -> XX/VALUE`` flips take the
  str-branch there and diverge — and (b) a plain ``str`` entry with NO
  ``.value``, which kills the ``or True`` flips (forced ``.value`` ->
  ``AttributeError``) and the ``str(None)`` else-branch flips; the
  ``hasattr(x, None)`` / one-arg / trailing-comma flips raise ``TypeError``
  at every polarity.
* LOG RECORD LISTS — a fake logger records ``(level, msg, kwargs)`` tuples
  compared as whole lists: msg->None, ``extra=None``, ``extra`` deletion
  (kwargs become ``{}``), every extra-key XX/upper flip, and the
  ``exc_info`` kwarg in the unexpected-error arm.
* WHOLE-CALL SPIES — ``_send_request`` and ``_handle_delivery_failure`` are
  swapped on the CLASS and record the whole call tuple, which kills the
  arg-swap / arg-None / ARG-DELETION families at all three call sites (the
  trailing-comma form leaves one positional argument -> ``TypeError``, which
  ``retry_delivery`` PROPAGATES and a test asserts, interim state included).
* STRICT JINJA SPIES — a fake ``_jinja_env`` asserts the EXACT render
  context ``{event_type, timestamp, webhook_id, data, **event_data}``; the
  resulting ``AssertionError`` is outside the module's
  ``except (TemplateSyntaxError, UndefinedError, JSONDecodeError)`` tuple so
  kwarg-None and kwarg-deletion mutants propagate instead of falling back.
* AUTH MATRIX — thirteen ``auth_config`` shapes through a fake module
  ``httpx`` whose ``AsyncClient`` wraps the real client on a recording
  transport, asserted as whole header dicts. The absent-key rows are what
  make the ``.get(key, default)`` family observable: on the key-absent
  polarity a swapped default becomes the consumed value, and
  ``get("header_name", None)`` -> ``headers[x] = None`` raises
  ``TypeError`` inside httpx's ``Headers`` (measured; an empty-string value
  is accepted). Note ``get(k, )`` (trailing comma = default deleted) is
  ONE-ARG ``get`` -> ``None``, never a KeyError.
* REAL-MODEL INSPECTION — ``create_webhook`` returns a real
  ``OutboundWebhook`` the fake session captured (every construction-kwarg
  None/deletion flip is an attribute difference; the models' defaults are
  all ``None``, measured) and ``deliver``/``retry`` assert every post-send
  mutation, with the webhook entering on non-zero/non-one counters so the
  ``+= 1 -> = 1 / -= 1 / += 2`` twins diverge.
* EXACT BOUNDARIES — statuses 200/299/300/404/500 (success-window flips),
  a 2001-char body for the ``[:2000]`` store cap, 600-char exception
  messages for the ``[:500] -> [:501]`` twins, a fixed clock
  (``utc_now`` -> ``2026-12-15T10:30Z``, module ``datetime`` -> a constant
  ``now()``) so backoff/cutoff/timestamp/response_time are exact, and
  backoff cases where ``attempt - 1 -> + 1``, ``* 2 -> * 3`` and ``min ->
  max`` all diverge.

Honesty ledger — dispositions registered EQUIVALENT. The sweep must show
GREEN on exactly these 12 keys; any other GREEN is a test gap, and a RED
here is a battery bug. Each was decided BY CONSTRUCTION this session —
orig-vs-mutant equality on every polarity the module itself can reach:

* ``__init__`` m1 — ``self._http_client = http_client -> None``: the
  attribute is stored and read nowhere in the module (every send builds its
  own client), so the store is unreachable. Measured: attribute-only
  divergence.
* ``create_webhook`` m2 — ``secrets.token_hex(32) -> token_hex(None)``:
  measured both produce a 64-char hex string (``token_hex(None)`` defaults
  to 32 bytes), and the value is only stored and logged, never compared.
* ``deliver_webhook`` m12/m18 — ``status=WebhookDeliveryStatus.PENDING ->
  None`` (m18 deletes the kwarg, whose model default is ``None``, measured):
  every reachable arm overwrites ``delivery.status`` (SUCCESS, RETRYING or
  FAILED) before the object is observed, and the fake session records the
  same object either way.
* ``_format_discord_payload`` m9 — ``.get("event_type", "event") ->
  "EVENT"``: the default is consumed only when the payload lacks the key,
  and both spellings pass through ``.replace("_", " ").title()`` which
  measured identically (``"Event"``); the reachable callers always set the
  key.
* ``_sign_payload`` m13 — ``encode("utf-8") -> encode("UTF-8")``: codec
  names are case-insensitive; digest measured identical.
* ``_send_request`` m16/m18/m21/m22 — ``.get("type", "none") -> None /
  (default deleted) / "XXnoneXX" / "NONE"``: the default is consumed only
  when ``auth_config`` is truthy but carries no ``type`` key (that row IS in
  the matrix), and the value's ONLY consumer is the
  ``bearer``/``basic``/``header`` equality chain. ``None``, ``"none"``,
  ``"XXnoneXX"`` and ``"NONE"`` all match none of the three arms (the
  trailing-comma m18 is one-arg ``get`` -> ``None``, NOT a KeyError —
  measured on the shipped tree), so the auth section is skipped
  identically. Measured equal on the no-type row.
* ``_send_request`` m68/m70 — ``.get("header_name", "") -> None / (default
  deleted)``: the default is only ever consumed on the key-absent polarity,
  and its use is ``if header_name:`` — ``""`` and ``None`` are both falsy,
  so no header is written either way.

All other 250 survivor keys carry an explicit kill polarity above; the
run-1 sweep result against this ledger is disclosed here when known.
"""

from __future__ import annotations

import asyncio
import base64
import datetime
import hashlib
import hmac
import json
from types import ModuleType, SimpleNamespace
from typing import Any

import httpx
from sqlalchemy import and_, func, select

from backend.api.schemas.outbound_webhook import (
    IntegrationType,
    WebhookAuthConfig,
    WebhookCreate,
    WebhookDeliveryStatus,
    WebhookEventType,
    WebhookHealthSummary,
    WebhookTestResponse,
    WebhookUpdate,
)
from backend.models.outbound_webhook import OutboundWebhook, WebhookDelivery
from backend.services.webhook_service import WebhookService


def _globals_of(obj: Any) -> dict[str, Any]:
    """Module globals of the REAL function (mutant wrappers delegate)."""
    fn = obj
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn.__globals__


_G = _globals_of(WebhookService.create_webhook)
assert _G.get("WebhookService") is WebhookService

# --------------------------------------------------------------------------
# fixed clock
# --------------------------------------------------------------------------

_FIXED = datetime.datetime(2026, 12, 15, 10, 30, tzinfo=datetime.UTC)
_FIXED_ISO = _FIXED.isoformat()


def _fixed_now() -> datetime.datetime:
    return _FIXED


class _FixedDT:
    """Module-global ``datetime`` swap: ``_send_request`` only calls now()."""

    @staticmethod
    def now(_tz: Any = None) -> datetime.datetime:
        return _FIXED


class _Env:
    """Swap module globals for one test; restore on exit."""

    def __init__(self, **kw: Any) -> None:
        self._old: dict[str, Any] = {}
        for key, value in kw.items():
            self._old[key] = _G[key]
            _G[key] = value

    def __enter__(self) -> _Env:
        return self

    def __exit__(self, *_exc: Any) -> None:
        for key, value in self._old.items():
            _G[key] = value


# --------------------------------------------------------------------------
# fake logger
# --------------------------------------------------------------------------


class _Logger:
    """Records ``(level, msg, merged)`` — the ``extra`` payload merged with
    any sibling kwargs (``exc_info``). ``extra=None`` / extra-deletion /
    extra-key mutants all change the recorded dict."""

    def __init__(self) -> None:
        self.recs: list[Any] = []

    def _rec(self, level: str, msg: Any, **kw: Any) -> None:
        extra = kw.pop("extra", None)
        merged: dict[str, Any] = dict(extra) if isinstance(extra, dict) else {}
        merged.update(kw)
        self.recs.append((level, msg, merged))

    def debug(self, msg: Any, **kw: Any) -> None:
        self._rec("DEBUG", msg, **kw)

    def info(self, msg: Any, **kw: Any) -> None:
        self._rec("INFO", msg, **kw)

    def warning(self, msg: Any, **kw: Any) -> None:
        self._rec("WARNING", msg, **kw)

    def error(self, msg: Any, **kw: Any) -> None:
        self._rec("ERROR", msg, **kw)


# --------------------------------------------------------------------------
# fake DB session with compiled-SQL recording
# --------------------------------------------------------------------------


def _sql(stmt: Any) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


def _rendered(stmt: Any) -> str:
    try:
        return _sql(stmt)
    except Exception as e:
        return f"<unrenderable {type(e).__name__}>"


class _Res:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> _Res:
        return self

    def all(self) -> list[Any]:
        return list(self._value)

    def scalar(self) -> Any:
        return self._value


class _Scripted:
    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self._pos = 0

    def __call__(self) -> Any:
        pos = self._pos
        self._pos += 1
        if pos >= len(self._results):
            raise AssertionError("scripted db results exhausted")
        return _Res(self._results[pos])


class _DB:
    def __init__(self, results: list[Any]) -> None:
        self.executed: list[str] = []
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.flushes = 0
        self.refreshed: list[Any] = []
        self._script = _Scripted(results)

    async def execute(self, statement: Any, *args: Any, **kw: Any) -> Any:
        self.executed.append(_rendered(statement))
        return self._script()

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def flush(self) -> None:
        self.flushes += 1

    async def refresh(self, obj: Any) -> None:
        if obj is None:
            raise ValueError("Refresh of a None instance")
        self.refreshed.append(obj)


# --------------------------------------------------------------------------
# non-enum polarity objects: .value deliberately differs from str()
# --------------------------------------------------------------------------


class _Event:
    """Has ``.value`` but ``str(obj) != obj.value`` (kills the branch flips)."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return "S"


class _RawIT:
    """integration_type without ``.value`` whose str() is not a literal."""

    def __init__(self, v: str) -> None:
        self.v = v

    def __str__(self) -> str:
        return "IT:" + self.v


_WID = "w1"
_URL = "https://x.test/p"
_SIG_SECRET = "ff" * 32  # pragma: allowlist secret
_GET_SQL = _sql(select(OutboundWebhook).where(OutboundWebhook.id == _WID))


def _trigger_sql(value: Any) -> str:
    return _sql(
        select(OutboundWebhook).where(
            and_(
                OutboundWebhook.enabled.is_(True),
                OutboundWebhook.event_types.any(value),
            )
        )
    )


def _delivery_select_sql(did: str) -> str:
    return _sql(select(WebhookDelivery).where(WebhookDelivery.id == did))


def _webhook(**over: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "id": _WID,
        "url": _URL,
        "event_types": ["alert_fired"],
        "integration_type": IntegrationType.GENERIC,
        "enabled": True,
        "auth_config": None,
        "custom_headers": {},
        "payload_template": None,
        "max_retries": 4,
        "retry_delay_seconds": 10,
        "signing_secret": None,
        "total_deliveries": 0,
        "successful_deliveries": 0,
        "last_delivery_at": None,
        "last_delivery_status": None,
    }
    base.update(over)
    return SimpleNamespace(**base)


def _std_payload(event_type: Any, data: Any, wid: str = _WID) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "timestamp": _FIXED_ISO,
        "webhook_id": wid,
        "data": data,
    }


def _hmac_sig(payload: dict[str, Any], secret: str) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(bytes.fromhex(secret), body, hashlib.sha256).hexdigest()


# --------------------------------------------------------------------------
# class-level spies
# --------------------------------------------------------------------------


class _SendSpy:
    """Records the whole ``(webhook, payload)`` call tuple."""

    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.calls: list[Any] = []
        self._result = result
        self._error = error
        self._old: Any = None

    async def _send_request(self, webhook: Any, payload: dict[str, Any]) -> tuple[int, str, int]:
        self.calls.append((webhook, payload))
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result

    def __enter__(self) -> _SendSpy:
        self._old = WebhookService._send_request
        WebhookService._send_request = self._send_request  # type: ignore[method-assign]
        return self

    def __exit__(self, *_exc: Any) -> None:
        WebhookService._send_request = self._old


class _FailSpy:
    """Records the whole ``(db, webhook, delivery)`` tuple and reproduces the
    real tail bookkeeping so the stats keys still diverge where they should."""

    def __init__(self) -> None:
        self.calls: list[Any] = []
        self._old: Any = None

    async def _handle(self, db: Any, webhook: Any, delivery: Any) -> None:
        self.calls.append((db, webhook, delivery))
        webhook.total_deliveries += 1
        webhook.last_delivery_at = _FIXED
        webhook.last_delivery_status = "spied"

    def __enter__(self) -> _FailSpy:
        self._old = WebhookService._handle_delivery_failure
        WebhookService._handle_delivery_failure = self._handle  # type: ignore[method-assign]
        return self

    def __exit__(self, *_exc: Any) -> None:
        WebhookService._handle_delivery_failure = self._old


# ==========================================================================
# singleton + background trigger
# ==========================================================================


def test_get_webhook_service_singleton() -> None:
    holder = _G["_WebhookServiceHolder"]
    old = holder.instance
    holder.instance = None
    try:
        first = _G["get_webhook_service"]()
        assert isinstance(first, WebhookService)
        assert holder.instance is first
        assert holder.instance is not None
        assert _G["get_webhook_service"]() is first
    finally:
        holder.instance = old


def test_trigger_webhook_background_ok() -> None:
    svc = WebhookService()
    calls: list[Any] = []

    async def _trigger(db: Any, event_type: Any, event_data: Any, event_id: Any = None) -> None:
        calls.append((db, event_type, event_data, event_id))

    svc.trigger_webhooks_for_event = _trigger  # type: ignore[method-assign]
    log = _Logger()
    with _Env(get_webhook_service=lambda: svc, logger=log):
        asyncio.run(
            _G["trigger_webhook_background"](
                "DB", WebhookEventType.ALERT_FIRED, {"a": 1}, event_id="e7"
            )
        )
    assert calls == [("DB", WebhookEventType.ALERT_FIRED, {"a": 1}, "e7")]
    assert log.recs == []


def test_trigger_webhook_background_swallows() -> None:
    svc = WebhookService()

    async def _boom(_db: Any, _event_type: Any, _event_data: Any, event_id: Any = None) -> None:
        raise RuntimeError("kaput")

    svc.trigger_webhooks_for_event = _boom  # type: ignore[method-assign]
    log = _Logger()
    with _Env(get_webhook_service=lambda: svc, logger=log):
        asyncio.run(
            _G["trigger_webhook_background"](
                "DB", WebhookEventType.ALERT_FIRED, {"a": 1}, event_id="e7"
            )
        )
    assert log.recs == [
        (
            "WARNING",
            "Background webhook trigger failed for alert_fired: kaput",
            {"event_type": "alert_fired", "event_id": "e7"},
        )
    ]


# ==========================================================================
# CRUD
# ==========================================================================


def test_get_webhook() -> None:
    svc = WebhookService()
    row = SimpleNamespace(id=_WID)
    db = _DB([row])
    with _Env(utc_now=_fixed_now):
        got = asyncio.run(svc.get_webhook(db, _WID))
    assert got is row
    assert db.executed == [_GET_SQL]


_MIXED_EVENTS: list[Any] = [WebhookEventType.ALERT_FIRED, _Event("alert_fired"), "plain_entry"]


def test_create_webhook() -> None:
    svc = WebhookService()
    data = WebhookCreate.model_construct(
        name="Hooks",
        url="https://x.test/hooks",
        event_types=list(_MIXED_EVENTS),
        integration_type=IntegrationType.SLACK,
        enabled=True,
        auth=None,
        custom_headers=None,
        payload_template="tmpl",
        max_retries=3,
        retry_delay_seconds=20,
    )
    db = _DB([])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        w = asyncio.run(svc.create_webhook(db, data))
    assert isinstance(w, OutboundWebhook)
    assert db.added == [w]
    assert w.name == "Hooks"
    assert w.url == "https://x.test/hooks"
    assert w.event_types == ["alert_fired", "alert_fired", "plain_entry"]
    assert w.integration_type is IntegrationType.SLACK
    assert w.enabled is True
    assert w.auth_config is None
    assert w.custom_headers == {}
    assert w.payload_template == "tmpl"
    assert w.max_retries == 3
    assert w.retry_delay_seconds == 20
    assert w.signing_secret is not None
    assert len(w.signing_secret) == 64
    assert db.executed == []
    assert db.flushes == 1
    assert db.refreshed == [w]
    assert log.recs == [
        (
            "INFO",
            "Created webhook 'Hooks' (id=None)",
            {
                "webhook_id": None,
                "webhook_name": "Hooks",
                "event_types": ["alert_fired", "alert_fired", "plain_entry"],
            },
        )
    ]


def test_create_webhook_auth_dump_and_custom_headers() -> None:
    svc = WebhookService()
    data = WebhookCreate.model_construct(
        name="Auth",
        url="https://x.test/auth",
        event_types=[WebhookEventType.ALERT_FIRED],
        integration_type=IntegrationType.GENERIC,
        enabled=False,
        auth=WebhookAuthConfig(type="bearer", token="t"),
        custom_headers={"X-A": "1"},
        payload_template=None,
        max_retries=0,
        retry_delay_seconds=1,
    )
    db = _DB([])
    with _Env(logger=_Logger(), utc_now=_fixed_now):
        w = asyncio.run(svc.create_webhook(db, data))
    assert w.auth_config == {
        "type": "bearer",
        "token": "t",
        "username": None,
        "password": None,
        "header_name": None,
        "header_value": None,
    }
    assert w.custom_headers == {"X-A": "1"}
    assert w.enabled is False
    assert w.max_retries == 0
    assert w.retry_delay_seconds == 1
    data2 = WebhookCreate.model_construct(
        name="Auth2",
        url="https://x.test/auth2",
        event_types=[WebhookEventType.ALERT_FIRED],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        auth=None,
        custom_headers={},
        payload_template=None,
        max_retries=4,
        retry_delay_seconds=10,
    )
    db2 = _DB([])
    with _Env(logger=_Logger(), utc_now=_fixed_now):
        w2 = asyncio.run(svc.create_webhook(db2, data2))
    assert w2.auth_config is None
    assert w2.custom_headers == {}


def _full_update() -> WebhookUpdate:
    return WebhookUpdate.model_construct(
        name="New",
        url="https://x.test/new",
        event_types=list(_MIXED_EVENTS),
        integration_type=IntegrationType.DISCORD,
        enabled=False,
        auth=WebhookAuthConfig(type="basic", username="u", password="p"),
        custom_headers={"H": "1"},
        payload_template="pt",
        max_retries=2,
        retry_delay_seconds=30,
    )


def test_update_webhook_full() -> None:
    svc = WebhookService()
    hook = _webhook()
    db = _DB([hook])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        got = asyncio.run(svc.update_webhook(db, _WID, _full_update()))
    assert got is hook
    assert hook.name == "New"
    assert hook.url == "https://x.test/new"
    assert hook.event_types == ["alert_fired", "alert_fired", "plain_entry"]
    assert hook.integration_type is IntegrationType.DISCORD
    assert hook.enabled is False
    assert hook.auth_config == {
        "type": "basic",
        "token": None,
        "username": "u",
        "password": "p",
        "header_name": None,
        "header_value": None,
    }
    assert hook.custom_headers == {"H": "1"}
    assert hook.payload_template == "pt"
    assert hook.max_retries == 2
    assert hook.retry_delay_seconds == 30
    assert db.executed == [_GET_SQL]
    assert db.flushes == 1
    assert db.refreshed == [hook]
    assert log.recs == [
        (
            "DEBUG",
            "Updated webhook w1",
            {
                "webhook_id": _WID,
                "updated_fields": [
                    "name",
                    "url",
                    "event_types",
                    "integration_type",
                    "enabled",
                    "auth_config",
                    "custom_headers",
                    "payload_template",
                    "max_retries",
                    "retry_delay_seconds",
                ],
            },
        )
    ]


def test_update_webhook_partial_enabled() -> None:
    svc = WebhookService()
    hook = _webhook(name="Old", enabled=True)
    db = _DB([hook])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        got = asyncio.run(svc.update_webhook(db, _WID, WebhookUpdate(enabled=False)))
    assert got is hook
    assert hook.enabled is False
    assert hook.name == "Old"
    assert db.executed == [_GET_SQL]
    assert db.flushes == 1
    assert db.refreshed == [hook]
    assert log.recs == [
        (
            "DEBUG",
            "Updated webhook w1",
            {"webhook_id": _WID, "updated_fields": ["enabled"]},
        )
    ]


def test_update_webhook_missing_returns_none() -> None:
    svc = WebhookService()
    db = _DB([None])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        assert asyncio.run(svc.update_webhook(db, _WID, WebhookUpdate(name="X"))) is None
    assert db.flushes == 0
    assert log.recs == []


def test_update_webhook_noop_skips_flush_and_log() -> None:
    svc = WebhookService()
    hook = _webhook(name="Old", enabled=True)
    db = _DB([hook])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        got = asyncio.run(svc.update_webhook(db, _WID, WebhookUpdate()))
    assert got is hook
    assert hook.name == "Old"
    assert hook.enabled is True
    assert db.flushes == 0
    assert db.refreshed == []
    assert log.recs == []


def test_delete_webhook() -> None:
    svc = WebhookService()
    hook = _webhook()
    db = _DB([hook])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        assert asyncio.run(svc.delete_webhook(db, _WID)) is True
    assert db.deleted == [hook]
    assert db.executed == [_GET_SQL]
    assert db.flushes == 1
    assert log.recs == [("INFO", "Deleted webhook w1", {"webhook_id": _WID})]


def test_delete_webhook_missing() -> None:
    svc = WebhookService()
    db = _DB([None])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        assert asyncio.run(svc.delete_webhook(db, "missing")) is False
    assert db.deleted == []
    assert db.flushes == 0
    assert log.recs == []


# ==========================================================================
# deliver_webhook
# ==========================================================================


def test_deliver_success() -> None:
    svc = WebhookService()
    w = _webhook(total_deliveries=2, successful_deliveries=1)
    payload = _std_payload("alert_fired", {"k": 1})
    log = _Logger()
    fake = _SendSpy(result=(200, "body-x", 42))
    db = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "evt-9"))
    assert isinstance(d, WebhookDelivery)
    assert db.added == [d]
    assert d.webhook_id == _WID
    assert d.event_type == "alert_fired"
    assert d.event_id == "evt-9"
    assert d.status == WebhookDeliveryStatus.SUCCESS
    assert d.request_payload == payload
    assert d.attempt_count == 1
    assert d.status_code == 200
    assert d.response_body == "body-x"
    assert d.response_time_ms == 42
    assert d.delivered_at == _FIXED
    assert d.error_message is None
    assert fake.calls == [(w, payload)]
    assert w.total_deliveries == 3
    assert w.successful_deliveries == 2
    assert w.last_delivery_at == _FIXED
    assert w.last_delivery_status == "success"
    assert db.flushes == 2
    assert db.refreshed == [d]
    assert log.recs == [
        (
            "DEBUG",
            "Webhook delivered successfully: w1 -> https://x.test/p",
            {
                "webhook_id": _WID,
                "delivery_id": None,
                "status_code": 200,
                "response_time_ms": 42,
            },
        )
    ]


def test_deliver_string_event_and_upper_bound() -> None:
    # an event_type with no .value takes the str-branch; 299 is the last
    # success status
    svc = WebhookService()
    w = _webhook()
    log = _Logger()
    fake = _SendSpy(result=(299, "b", 1))
    db = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d = asyncio.run(svc.deliver_webhook(db, w, "x", {"k": 1}, "evt-9"))
    assert d.event_type == "x"
    assert d.status == WebhookDeliveryStatus.SUCCESS
    assert fake.calls == [(w, _std_payload("x", {"k": 1}))]
    assert log.recs[0][2]["status_code"] == 299


def test_deliver_boundary_300_is_failure() -> None:
    svc = WebhookService()
    w = _webhook()
    log = _Logger()
    fake = _SendSpy(result=(300, "b", 1))
    fail = _FailSpy()
    db = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake, fail:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert d.status_code == 300
    assert d.error_message == "HTTP 300"
    assert fake.calls == [(w, _std_payload("alert_fired", {"k": 1}))]
    assert fail.calls == [(db, w, d)]


def test_deliver_response_body_cap() -> None:
    svc = WebhookService()
    w = _webhook()
    log = _Logger()
    fake = _SendSpy(result=(200, "x" * 2001, 1))
    db = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert d.response_body == "x" * 2000
    fake2 = _SendSpy(result=(500, "y" * 2001, 1))
    fail = _FailSpy()
    db2 = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake2, fail:
        d2 = asyncio.run(svc.deliver_webhook(db2, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert d2.response_body == "y" * 2000


def test_deliver_http_error_schedules_retry() -> None:
    svc = WebhookService()
    w = _webhook(total_deliveries=2)
    log = _Logger()
    fake = _SendSpy(result=(500, "oops", 7))
    db = _DB([])
    retry_at = _FIXED + datetime.timedelta(seconds=10)
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert d.status == WebhookDeliveryStatus.RETRYING
    assert d.status_code == 500
    assert d.response_body == "oops"
    assert d.response_time_ms == 7
    assert d.error_message == "HTTP 500"
    assert d.next_retry_at == retry_at
    assert d.delivered_at is None
    assert w.total_deliveries == 3
    assert w.successful_deliveries == 0
    assert w.last_delivery_at == _FIXED
    assert w.last_delivery_status == "retrying"
    assert db.flushes == 2
    assert log.recs == [
        (
            "WARNING",
            "Webhook delivery failed, scheduling retry 2/4",
            {
                "webhook_id": _WID,
                "delivery_id": None,
                "next_retry_at": retry_at.isoformat(),
                "error": "HTTP 500",
            },
        )
    ]


def test_deliver_http_error_exhausts_retries() -> None:
    svc = WebhookService()
    w = _webhook(max_retries=1)
    log = _Logger()
    fake = _SendSpy(result=(500, "oops", 7))
    db = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert d.status == WebhookDeliveryStatus.FAILED
    assert d.next_retry_at is None
    assert d.delivered_at is None
    assert w.total_deliveries == 1
    assert w.last_delivery_at == _FIXED
    assert w.last_delivery_status == "failed"
    assert log.recs == [
        (
            "ERROR",
            "Webhook delivery failed after 1 attempts",
            {"webhook_id": _WID, "delivery_id": None, "error": "HTTP 500"},
        )
    ]


def test_deliver_network_error() -> None:
    svc = WebhookService()
    w = _webhook(total_deliveries=2)
    log = _Logger()
    fake = _SendSpy(error=httpx.RequestError("net-boom"))
    db = _DB([])
    retry_at = _FIXED + datetime.timedelta(seconds=10)
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert d.status == WebhookDeliveryStatus.RETRYING
    assert d.error_message == "net-boom"
    assert d.status_code is None
    assert d.response_body is None
    assert d.response_time_ms is None
    assert d.next_retry_at == retry_at
    assert w.total_deliveries == 3
    assert w.last_delivery_status == "retrying"
    assert db.flushes == 2
    assert log.recs == [
        (
            "WARNING",
            "Webhook delivery failed, scheduling retry 2/4",
            {
                "webhook_id": _WID,
                "delivery_id": None,
                "next_retry_at": retry_at.isoformat(),
                "error": "net-boom",
            },
        )
    ]


def test_deliver_network_failure_call_shape() -> None:
    # the RequestError arm's call-site db argument: the spy sees the WHOLE
    # tuple, so db -> None diverges even though the callee ignores db
    svc = WebhookService()
    w = _webhook()
    log = _Logger()
    fake = _SendSpy(error=httpx.RequestError("dns"))
    fail = _FailSpy()
    db = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake, fail:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert fail.calls == [(db, w, d)]
    assert d.error_message == "dns"


def test_deliver_error_message_truncation() -> None:
    # kills the ``[:500] -> [:501]`` twins on both error arms
    svc = WebhookService()
    log = _Logger()
    w1 = _webhook()
    fake = _SendSpy(error=httpx.RequestError("y" * 600))
    db1 = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d1 = asyncio.run(svc.deliver_webhook(db1, w1, _Event("alert_fired"), {"k": 1}, "e"))
    assert d1.error_message == "y" * 500
    w2 = _webhook()
    fake2 = _SendSpy(error=ValueError("z" * 600))
    db2 = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake2:
        d2 = asyncio.run(svc.deliver_webhook(db2, w2, _Event("alert_fired"), {"k": 1}, "e"))
    assert d2.error_message == "z" * 500


def test_deliver_unexpected_error() -> None:
    svc = WebhookService()
    w = _webhook(total_deliveries=2)
    log = _Logger()
    fake = _SendSpy(error=ValueError("kapow"))
    db = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert d.status == WebhookDeliveryStatus.FAILED
    assert d.error_message == "kapow"
    assert d.delivered_at is None
    assert w.total_deliveries == 3
    assert w.last_delivery_at == _FIXED
    assert w.last_delivery_status == "failed"
    assert db.flushes == 2
    assert log.recs == [
        (
            "ERROR",
            "Webhook delivery failed unexpectedly: kapow",
            {"webhook_id": _WID, "delivery_id": None, "exc_info": True},
        )
    ]


# ==========================================================================
# trigger_webhooks_for_event
# ==========================================================================


def test_trigger_webhooks_empty() -> None:
    svc = WebhookService()
    db = _DB([[]])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        out = asyncio.run(svc.trigger_webhooks_for_event(db, _Event("alert_fired"), {"d": 1}, "e1"))
    assert out == []
    assert db.executed == [_trigger_sql("alert_fired")]
    assert log.recs == [
        (
            "DEBUG",
            "No webhooks subscribed to event type: alert_fired",
            {"event_type": "alert_fired"},
        )
    ]


def test_trigger_webhooks_string_event() -> None:
    svc = WebhookService()
    db = _DB([[]])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        out = asyncio.run(svc.trigger_webhooks_for_event(db, "x", {"d": 1}, "e1"))
    assert out == []
    assert db.executed == [_trigger_sql("x")]
    assert log.recs == [("DEBUG", "No webhooks subscribed to event type: x", {"event_type": "x"})]


def test_trigger_webhooks_delivers_each() -> None:
    svc = WebhookService()
    w1 = _webhook(id="h1")
    w2 = _webhook(id="h2")
    db = _DB([[w1, w2]])
    log = _Logger()
    seen: list[Any] = []

    async def _deliver(
        db_: Any, hook: Any, event_type: Any, event_data: Any, event_id: Any = None
    ) -> str:
        seen.append((db_, hook, event_type, event_data, event_id))
        return "d-" + str(hook.id)

    svc.deliver_webhook = _deliver  # type: ignore[method-assign]
    ev = _Event("alert_fired")
    with _Env(logger=log, utc_now=_fixed_now):
        out = asyncio.run(svc.trigger_webhooks_for_event(db, ev, {"d": 1}, "e1"))
    assert out == ["d-h1", "d-h2"]
    assert seen == [
        (db, w1, ev, {"d": 1}, "e1"),
        (db, w2, ev, {"d": 1}, "e1"),
    ]
    assert db.executed == [_trigger_sql("alert_fired")]
    assert log.recs == [
        (
            "INFO",
            "Triggering 2 webhooks for event type: alert_fired",
            {"event_type": "alert_fired", "webhook_count": 2},
        )
    ]


# ==========================================================================
# test_webhook + _build_test_event_data
# ==========================================================================


_TEST_DATA: dict[str, dict[str, Any]] = {
    "alert_fired": {
        "alert_id": "test-alert-001",
        "severity": "high",
        "camera_id": "front_door",
        "description": "Test alert triggered",
    },
    "alert_dismissed": {"alert_id": "test-alert-001"},
    "alert_acknowledged": {"alert_id": "test-alert-001"},
    "event_created": {
        "event_id": "test-event-001",
        "camera_id": "front_door",
        "event_type": "motion_detected",
    },
    "event_enriched": {
        "event_id": "test-event-001",
        "enrichment_type": "person_detection",
        "confidence": 0.95,
    },
    "entity_discovered": {
        "entity_id": "test-entity-001",
        "entity_type": "person",
        "label": "Unknown Person",
    },
    "anomaly_detected": {
        "anomaly_id": "test-anomaly-001",
        "zone_id": "driveway",
        "anomaly_type": "unusual_activity",
        "score": 0.87,
    },
    "system_health_changed": {
        "component": "ai-yolo26",
        "status": "degraded",
        "message": "High latency detected",
    },
    "batch_analysis_started": {},
    "batch_analysis_completed": {},
    "batch_analysis_failed": {},
}


def _test_data(event_type: Any) -> dict[str, Any]:
    spec = _TEST_DATA.get(str(getattr(event_type, "value", event_type)), {})
    return {"test": True, "timestamp": _FIXED_ISO, **spec}


def test_test_webhook_success() -> None:
    svc = WebhookService()
    hook = _webhook()
    db = _DB([hook])
    fake = _SendSpy(result=(204, "yay", 5))
    with _Env(utc_now=_fixed_now), fake:
        r = asyncio.run(svc.test_webhook(db, _WID, WebhookEventType.ALERT_FIRED))
    assert isinstance(r, WebhookTestResponse)
    assert r.model_dump() == {
        "success": True,
        "status_code": 204,
        "response_time_ms": 5,
        "response_body": "yay",
        "error_message": None,
    }
    assert fake.calls == [(hook, _std_payload("alert_fired", _test_data("alert_fired")))]


def test_test_webhook_matrix() -> None:
    svc = WebhookService()
    for key in _TEST_DATA:
        hook = _webhook()
        db = _DB([hook])
        fake = _SendSpy(result=(200, "y", 5))
        with _Env(utc_now=_fixed_now), fake:
            asyncio.run(svc.test_webhook(db, _WID, WebhookEventType(key)))
        assert fake.calls[0][1] == _std_payload(key, _test_data(key)), key


def test_build_test_event_data_polarities() -> None:
    # direct private calls with NON-StrEnum event objects: the value-branch
    # must be taken (kills the branch-flip family), and a no-.value object
    # must fall back to str (kills the or-True family)
    svc = WebhookService()
    with _Env(utc_now=_fixed_now):
        via_value = svc._build_test_event_data(_Event("alert_fired"))
        via_str = svc._build_test_event_data("alert_fired")
    assert via_value == _test_data("alert_fired")
    assert via_str == _test_data("alert_fired")


def test_test_webhook_missing() -> None:
    svc = WebhookService()
    db = _DB([None])
    with _Env(utc_now=_fixed_now):
        r = asyncio.run(svc.test_webhook(db, _WID, WebhookEventType.ALERT_FIRED))
    assert r.model_dump() == {
        "success": False,
        "status_code": None,
        "response_time_ms": None,
        "response_body": None,
        "error_message": "Webhook not found",
    }
    # the lookup must carry the REAL id (get_webhook(db, None) renders
    # ``id IS NULL`` -- the compiled mirror catches the call-arg flip)
    assert db.executed == [_GET_SQL]


def test_test_webhook_error_arms() -> None:
    svc = WebhookService()
    hook = _webhook()
    et = WebhookEventType.ALERT_FIRED
    db = _DB([hook])
    fake = _SendSpy(result=(404, "nope", 5))
    with _Env(utc_now=_fixed_now), fake:
        r = asyncio.run(svc.test_webhook(db, _WID, et))
    assert r.model_dump() == {
        "success": False,
        "status_code": 404,
        "response_time_ms": 5,
        "response_body": "nope",
        "error_message": "HTTP 404",
    }
    db2 = _DB([hook])
    fake2 = _SendSpy(error=httpx.RequestError("b" * 600))
    with _Env(utc_now=_fixed_now), fake2:
        r2 = asyncio.run(svc.test_webhook(db2, _WID, et))
    assert r2.model_dump() == {
        "success": False,
        "status_code": None,
        "response_time_ms": None,
        "response_body": None,
        "error_message": "b" * 500,
    }
    db3 = _DB([hook])
    fake3 = _SendSpy(error=RuntimeError("kaboom"))
    with _Env(utc_now=_fixed_now), fake3:
        r3 = asyncio.run(svc.test_webhook(db3, _WID, et))
    assert r3.error_message == "Unexpected error: kaboom"
    db4 = _DB([hook])
    fake4 = _SendSpy(result=(200, "", 5))
    with _Env(utc_now=_fixed_now), fake4:
        r4 = asyncio.run(svc.test_webhook(db4, _WID, et))
    assert r4.response_body is None
    db5 = _DB([hook])
    fake5 = _SendSpy(result=(200, "x" * 2001, 5))
    with _Env(utc_now=_fixed_now), fake5:
        r5 = asyncio.run(svc.test_webhook(db5, _WID, et))
    assert r5.response_body == "x" * 2000


# ==========================================================================
# retry_delivery
# ==========================================================================


def _retryable(**over: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "webhook_id": _WID,
        "request_payload": {"old": True},
        "attempt_count": 1,
        "status": "stale",
        "error_message": "boom",
        "next_retry_at": "stale",
        "status_code": None,
        "response_body": None,
        "response_time_ms": None,
        "delivered_at": None,
    }
    base.update(over)
    return SimpleNamespace(**base)


def test_retry_delivery_success() -> None:
    svc = WebhookService()
    delivery = _retryable()
    hook = _webhook(total_deliveries=5, successful_deliveries=2)
    db = _DB([delivery, hook])
    fake = _SendSpy(result=(200, "ok-2", 9))
    with _Env(utc_now=_fixed_now), fake:
        out = asyncio.run(svc.retry_delivery(db, "d1"))
    assert out is delivery
    assert db.executed == [_delivery_select_sql("d1"), _GET_SQL]
    assert delivery.attempt_count == 2
    assert delivery.status == WebhookDeliveryStatus.SUCCESS
    assert delivery.error_message is None
    assert delivery.next_retry_at is None
    assert delivery.status_code == 200
    assert delivery.response_body == "ok-2"
    assert delivery.response_time_ms == 9
    assert delivery.delivered_at == _FIXED
    assert fake.calls == [(hook, {"old": True})]
    assert hook.total_deliveries == 6
    assert hook.successful_deliveries == 3
    assert hook.last_delivery_at == _FIXED
    assert hook.last_delivery_status == "success"
    assert db.flushes == 1
    assert db.refreshed == [delivery]


def test_retry_delivery_http_error() -> None:
    svc = WebhookService()
    delivery = _retryable()
    hook = _webhook(total_deliveries=5, successful_deliveries=2)
    db = _DB([delivery, hook])
    fake = _SendSpy(result=(503, "later", 9))
    with _Env(utc_now=_fixed_now), fake:
        out = asyncio.run(svc.retry_delivery(db, "d1"))
    assert out is delivery
    assert delivery.status == WebhookDeliveryStatus.FAILED
    assert delivery.status_code == 503
    assert delivery.response_body == "later"
    assert delivery.response_time_ms == 9
    assert delivery.error_message == "HTTP 503"
    assert delivery.delivered_at is None
    assert hook.total_deliveries == 6
    assert hook.successful_deliveries == 2
    assert hook.last_delivery_status == "failed"


def test_retry_delivery_network_error() -> None:
    svc = WebhookService()
    delivery = _retryable()
    hook = _webhook(total_deliveries=5, successful_deliveries=2)
    db = _DB([delivery, hook])
    fake = _SendSpy(error=httpx.RequestError("dns"))
    with _Env(utc_now=_fixed_now), fake:
        out = asyncio.run(svc.retry_delivery(db, "d1"))
    assert out is delivery
    assert delivery.status == WebhookDeliveryStatus.FAILED
    assert delivery.error_message == "dns"
    assert delivery.delivered_at is None
    assert hook.total_deliveries == 6
    assert hook.successful_deliveries == 2
    assert hook.last_delivery_status == "failed"


def test_retry_delivery_missing_rows() -> None:
    svc = WebhookService()
    db0 = _DB([None])
    with _Env(utc_now=_fixed_now):
        assert asyncio.run(svc.retry_delivery(db0, "d1")) is None
    assert db0.executed == [_delivery_select_sql("d1")]
    db1 = _DB([SimpleNamespace(webhook_id=_WID), None])
    with _Env(utc_now=_fixed_now):
        assert asyncio.run(svc.retry_delivery(db1, "d1")) is None
    assert db1.executed == [_delivery_select_sql("d1"), _GET_SQL]


def test_retry_delivery_falsy_payload() -> None:
    svc = WebhookService()
    delivery = _retryable(request_payload=None)
    hook = _webhook()
    db = _DB([delivery, hook])
    fake = _SendSpy(result=(200, "ok", 1))
    with _Env(utc_now=_fixed_now), fake:
        asyncio.run(svc.retry_delivery(db, "d1"))
    assert fake.calls == [(hook, {})]


def test_retry_delivery_propagates_and_resets() -> None:
    # retry_delivery has NO generic except: an unexpected error propagates
    # after the reset block, so the interim state is observable
    svc = WebhookService()
    delivery = _retryable()
    hook = _webhook()
    db = _DB([delivery, hook])
    fake = _SendSpy(error=RuntimeError("nope"))
    raised = False
    try:
        with _Env(utc_now=_fixed_now), fake:
            asyncio.run(svc.retry_delivery(db, "d1"))
    except RuntimeError as e:
        raised = str(e) == "nope"
    assert raised
    assert delivery.attempt_count == 2
    assert delivery.status == WebhookDeliveryStatus.PENDING
    assert delivery.error_message is None
    assert delivery.next_retry_at is None
    assert fake.calls == [(hook, {"old": True})]
    assert db.flushes == 0


# ==========================================================================
# _build_payload + templates
# ==========================================================================


def test_build_payload_polarities() -> None:
    svc = WebhookService()
    w = _webhook()
    with _Env(utc_now=_fixed_now):
        via_enum = svc._build_payload(w, WebhookEventType.ALERT_FIRED, {"z": 1})
        via_value = svc._build_payload(w, _Event("alert_fired"), {"z": 1})
        via_str = svc._build_payload(w, "x", {"z": 1})
    assert via_enum == _std_payload("alert_fired", {"z": 1})
    assert via_value == _std_payload("alert_fired", {"z": 1})
    assert via_str == _std_payload("x", {"z": 1})


_TEMPLATE = (
    '{"t": {{ event_type|tojson }}, "b": {{ data|tojson }},'
    ' "c": {{ alert_id|tojson }}, "d": {{ webhook_id|tojson }},'
    ' "e": {{ timestamp|tojson }}}'
)


def test_build_payload_template_renders() -> None:
    svc = WebhookService()
    w = _webhook(payload_template=_TEMPLATE)
    with _Env(utc_now=_fixed_now):
        p = svc._build_payload(w, _Event("alert_fired"), {"alert_id": "A"})
    assert p == {
        "t": "alert_fired",
        "b": {"alert_id": "A"},
        "c": "A",
        "d": _WID,
        "e": _FIXED_ISO,
    }


class _StrictEnv:
    """Fake ``_jinja_env`` asserting the EXACT render kwargs."""

    def __init__(self, expected: dict[str, Any], crash: bool = False) -> None:
        self._expected = expected
        self._crash = crash

    def from_string(self, _src: str) -> _StrictEnv:
        return self

    def render(self, **kw: Any) -> str:
        if self._crash:
            raise ValueError("renderer exploded off the caught list")
        assert kw == self._expected, f"render context drifted: {sorted(kw)}"
        return '{"ok": 1}'


class _BoomEnv:
    def from_string(self, _src: str) -> Any:
        raise ValueError("from_string exploded off the caught list")


def test_build_payload_template_render_context() -> None:
    svc = WebhookService()
    w = _webhook(payload_template="whatever")
    expected = {
        "event_type": "alert_fired",
        "timestamp": _FIXED_ISO,
        "webhook_id": _WID,
        "data": {"alert_id": "A"},
        "alert_id": "A",
    }
    with _Env(_jinja_env=_StrictEnv(expected), utc_now=_fixed_now):
        p = svc._build_payload(w, _Event("alert_fired"), {"alert_id": "A"})
    assert p == {"ok": 1}


def test_build_payload_template_uncrashed_paths_propagate() -> None:
    svc = WebhookService()
    w = _webhook(payload_template="whatever")
    raised = False
    try:
        with _Env(_jinja_env=_StrictEnv({}, crash=True), utc_now=_fixed_now):
            svc._build_payload(w, _Event("alert_fired"), {"alert_id": "A"})
    except ValueError as e:
        raised = str(e).startswith("renderer exploded")
    assert raised
    # a drifted render context raises AssertionError, also outside the
    # module's except tuple -> propagates rather than falling back
    raised_assert = False
    try:
        with _Env(_jinja_env=_StrictEnv({"bogus": 1}), utc_now=_fixed_now):
            svc._build_payload(w, _Event("alert_fired"), {"alert_id": "A"})
    except AssertionError:
        raised_assert = True
    assert raised_assert
    raised2 = False
    try:
        with _Env(_jinja_env=_BoomEnv(), utc_now=_fixed_now):
            svc._build_payload(w, _Event("alert_fired"), {"alert_id": "A"})
    except ValueError as e:
        raised2 = str(e).startswith("from_string exploded")
    assert raised2


def test_build_payload_template_json_failure() -> None:
    svc = WebhookService()
    w = _webhook(payload_template='{"not json"}')
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        p = svc._build_payload(w, _Event("alert_fired"), {"k": 1})
    assert p == _std_payload("alert_fired", {"k": 1})
    assert log.recs == [
        (
            "WARNING",
            "Failed to render payload template, using standard payload: "
            "Expecting ':' delimiter: line 1 column 12 (char 11)",
            {"webhook_id": _WID},
        )
    ]


def test_build_payload_template_undefined() -> None:
    svc = WebhookService()
    w = _webhook(payload_template="{{ nope.x }}")
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        p = svc._build_payload(w, _Event("alert_fired"), {"k": 1})
    assert p == _std_payload("alert_fired", {"k": 1})
    assert log.recs == [
        (
            "WARNING",
            "Failed to render payload template, using standard payload: 'nope' is undefined",
            {"webhook_id": _WID},
        )
    ]


def test_build_payload_template_syntax_error() -> None:
    svc = WebhookService()
    w = _webhook(payload_template="{{ ")
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        p = svc._build_payload(w, _Event("alert_fired"), {"k": 1})
    assert p == _std_payload("alert_fired", {"k": 1})
    assert log.recs == [
        (
            "WARNING",
            "Failed to render payload template, using standard payload: "
            "unexpected 'end of template'",
            {"webhook_id": _WID},
        )
    ]


# ==========================================================================
# _format_for_integration + formatters
# ==========================================================================


def test_format_for_integration_routing() -> None:
    svc = WebhookService()
    payload = _std_payload("alert_fired", {"k": 1})
    # _Event has .value but str() != .value: the value-branch must be taken
    slack = svc._format_for_integration(_webhook(integration_type=_Event("slack")), payload)
    assert slack["text"] == "*alert_fired*\n- k: 1\n"
    discord = svc._format_for_integration(_webhook(integration_type=_Event("discord")), payload)
    assert discord["embeds"][0]["title"] == "Alert Fired"
    teams = svc._format_for_integration(_webhook(integration_type=_Event("teams")), payload)
    assert teams["title"] == "Alert Fired"
    assert teams["summary"] == "alert_fired"
    # a real StrEnum routes by .value
    enum_slack = svc._format_for_integration(
        _webhook(integration_type=IntegrationType.SLACK), payload
    )
    assert enum_slack["text"] == "*alert_fired*\n- k: 1\n"
    # an integration whose resolved name is not a literal falls through
    assert (
        svc._format_for_integration(_webhook(integration_type=_RawIT("nope")), payload) == payload
    )
    assert (
        svc._format_for_integration(_webhook(integration_type=IntegrationType.TELEGRAM), payload)
        == payload
    )


def test_format_slack_payload() -> None:
    svc = WebhookService()
    out = svc._format_slack_payload(
        {
            "event_type": "e2",
            "data": {
                "s": "str",
                "i": 7,
                "f": 2.5,
                "b": False,
                "d": {"x": 1},
                "li": [1],
                "n": None,
            },
        }
    )
    text = "*e2*\n- s: str\n- i: 7\n- f: 2.5\n- b: False\n"
    assert out == {
        "text": text,
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
    }


def test_format_discord_payload() -> None:
    svc = WebhookService()
    data = {f"k{i}": i for i in range(30)}
    d = svc._format_discord_payload({"event_type": "alert_fired", "timestamp": "TS", "data": data})
    assert d == {
        "embeds": [
            {
                "title": "Alert Fired",
                "timestamp": "TS",
                "fields": [
                    {"name": "K" + str(i), "value": str(i), "inline": True} for i in range(25)
                ],
            }
        ]
    }
    with _Env(utc_now=_fixed_now):
        mixed = svc._format_discord_payload(
            {
                "event_type": "e",
                "data": {"s": "v", "i": 1, "f": 2.0, "b": True, "x": {}, "y": []},
            }
        )
    assert mixed["embeds"][0]["fields"] == [
        {"name": "S", "value": "v", "inline": True},
        {"name": "I", "value": "1", "inline": True},
        {"name": "F", "value": "2.0", "inline": True},
        {"name": "B", "value": "True", "inline": True},
    ]
    assert mixed["embeds"][0]["timestamp"] == _FIXED_ISO


def test_format_teams_payload() -> None:
    svc = WebhookService()
    data = {f"k{i}": i for i in range(30)}
    t = svc._format_teams_payload({"event_type": "alert_fired", "data": data})
    assert t == {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": "alert_fired",
        "themeColor": "0076D7",
        "title": "Alert Fired",
        "sections": [{"facts": [{"title": "K" + str(i), "value": str(i)} for i in range(10)]}],
    }
    mixed = svc._format_teams_payload(
        {"event_type": "e", "data": {"s": "v", "i": 1, "f": 2.0, "b": True, "x": {}}}
    )
    assert mixed["sections"][0]["facts"] == [
        {"title": "S", "value": "v"},
        {"title": "I", "value": "1"},
        {"title": "F", "value": "2.0"},
        {"title": "B", "value": "True"},
    ]


# ==========================================================================
# _sign_payload
# ==========================================================================


def test_sign_payload_exact() -> None:
    svc = WebhookService()
    payload = {"b": 2, "a": 1}
    want = _hmac_sig(payload, _SIG_SECRET)
    assert svc._sign_payload(payload, _SIG_SECRET) == want
    assert svc._sign_payload({"a": 1, "b": 2}, _SIG_SECRET) == want


# ==========================================================================
# _send_request (real httpx over a recording transport)
# ==========================================================================


class _CaptureTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.seen: list[Any] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(
            (
                request.method,
                str(request.url),
                dict(request.headers),
                request.content.decode(),
            )
        )
        return httpx.Response(200, text="R")


def _fake_httpx(transport: _CaptureTransport) -> ModuleType:
    fake = ModuleType("httpx")

    class Client(httpx.AsyncClient):
        def __init__(self, *args: Any, **kw: Any) -> None:
            kw["transport"] = transport
            super().__init__(*args, **kw)

    fake.AsyncClient = Client
    fake.RequestError = httpx.RequestError
    return fake


_BASIC_ABSENT = base64.b64encode(b":").decode()

_MATRIX: list[tuple[str, dict[str, Any], dict[str, str]]] = [
    ("none", {"type": "none"}, {}),
    ("bearer-full", {"type": "bearer", "token": "tk"}, {"authorization": "Bearer tk"}),
    (
        "basic-full",
        {"type": "basic", "username": "u1", "password": "p1"},  # pragma: allowlist secret
        {"authorization": "Basic " + base64.b64encode(b"u1:p1").decode()},
    ),
    (
        "header-full",
        {"type": "header", "header_name": "X-Key", "header_value": "hv"},
        {"x-key": "hv"},
    ),
    ("unknown", {"type": "weird"}, {}),
    ("empty", {}, {}),
    ("no-type-key", {"token": "tk"}, {}),
    ("bearer-absent-token", {"type": "bearer"}, {"authorization": "Bearer "}),
    ("basic-absent", {"type": "basic"}, {"authorization": "Basic " + _BASIC_ABSENT}),
    ("header-absent-name", {"type": "header"}, {}),
    ("header-empty-name", {"type": "header", "header_name": "", "header_value": "hv"}, {}),
    ("header-name-only", {"type": "header", "header_name": "X-Key"}, {"x-key": ""}),
    ("header-empty-both", {"type": "header", "header_name": "", "header_value": ""}, {}),
]


def test_send_request_auth_matrix() -> None:
    svc = WebhookService()
    payload = {"b": 2, "a": 1}
    sig = _hmac_sig(payload, _SIG_SECRET)
    for label, auth, auth_hdrs in _MATRIX:
        transport = _CaptureTransport()
        w = _webhook(
            auth_config=auth,
            custom_headers={"X-C": "c1"},
            signing_secret=_SIG_SECRET,
        )
        with _Env(httpx=_fake_httpx(transport), utc_now=_fixed_now, datetime=_FixedDT):
            out = asyncio.run(svc._send_request(w, payload))
        assert out == (200, "R", 0), label
        method, url, headers, content = transport.seen[-1]
        assert method == "POST", label
        assert url == _URL, label
        assert json.loads(content) == payload, label
        expected = {
            # httpx defaults (measured on the pinned version)
            "host": "x.test",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate",
            "connection": "keep-alive",
            # set by the module under test
            "content-type": "application/json",
            "user-agent": "NemotronWebhook/1.0",
            "content-length": str(len(content)),
            "x-c": "c1",
            "x-webhook-signature": "sha256=" + sig,
            "x-webhook-signature-256": sig,
        }
        expected.update(auth_hdrs)
        assert headers == expected, label


def test_send_request_bare_request() -> None:
    svc = WebhookService()
    payload = {"x": "y"}
    transport = _CaptureTransport()
    w = _webhook(auth_config=None, custom_headers=None, signing_secret=None)
    with _Env(httpx=_fake_httpx(transport), utc_now=_fixed_now, datetime=_FixedDT):
        out = asyncio.run(svc._send_request(w, payload))
    assert out == (200, "R", 0)
    _method, _url, headers, content = transport.seen[-1]
    assert headers == {
        "host": "x.test",
        "accept": "*/*",
        "accept-encoding": "gzip, deflate",
        "connection": "keep-alive",
        "content-type": "application/json",
        "user-agent": "NemotronWebhook/1.0",
        "content-length": str(len(content)),
    }


# ==========================================================================
# _calculate_next_retry
# ==========================================================================


def test_calculate_next_retry_backoff() -> None:
    svc = WebhookService()
    cases = [
        (1, 10, 10),
        (2, 10, 20),
        (3, 10, 40),
        (6, 10, 320),
        (30, 10, 3600),
        (1, 3600, 3600),
        (4, 1, 8),
    ]
    for attempt, base, delay in cases:
        with _Env(utc_now=_fixed_now):
            got = svc._calculate_next_retry(attempt, base)
        assert got == _FIXED + datetime.timedelta(seconds=delay), (attempt, base)


# ==========================================================================
# get_health_summary
# ==========================================================================


def _health_mirrors() -> list[str]:
    cutoff = _FIXED - datetime.timedelta(hours=24)
    return [
        _sql(select(func.count()).select_from(OutboundWebhook)),
        _sql(
            select(func.count())
            .select_from(OutboundWebhook)
            .where(OutboundWebhook.enabled.is_(True))
        ),
        _sql(
            select(func.count())
            .select_from(WebhookDelivery)
            .where(WebhookDelivery.created_at >= cutoff)
        ),
        _sql(
            select(func.count())
            .select_from(WebhookDelivery)
            .where(
                and_(
                    WebhookDelivery.created_at >= cutoff,
                    WebhookDelivery.status == WebhookDeliveryStatus.SUCCESS,
                )
            )
        ),
        _sql(
            select(func.count())
            .select_from(WebhookDelivery)
            .where(
                and_(
                    WebhookDelivery.created_at >= cutoff,
                    WebhookDelivery.status == WebhookDeliveryStatus.FAILED,
                )
            )
        ),
        _sql(
            select(func.avg(WebhookDelivery.response_time_ms)).where(
                and_(
                    WebhookDelivery.created_at >= cutoff,
                    WebhookDelivery.response_time_ms.is_not(None),
                )
            )
        ),
        _sql(select(OutboundWebhook).order_by(OutboundWebhook.created_at.desc())),
    ]


def _run_health(rows: list[Any], results: list[Any]) -> tuple[Any, _DB]:
    db = _DB(results)
    svc = WebhookService()
    with _Env(utc_now=_fixed_now):
        h = asyncio.run(svc.get_health_summary(db))
    return h, db


def test_get_health_summary_exact() -> None:
    rows = [
        _webhook(total_deliveries=10, successful_deliveries=9),
        _webhook(total_deliveries=10, successful_deliveries=8),
        _webhook(total_deliveries=10, successful_deliveries=5),
        _webhook(total_deliveries=10, successful_deliveries=4),
        _webhook(total_deliveries=1, successful_deliveries=0),
        _webhook(total_deliveries=0, successful_deliveries=0),
        _webhook(total_deliveries=20, successful_deliveries=20),
    ]
    h, db = _run_health(rows, [7, 3, 11, 8, 2, 42.5, rows])
    assert h == WebhookHealthSummary(
        total_webhooks=7,
        enabled_webhooks=3,
        healthy_webhooks=2,
        unhealthy_webhooks=2,
        total_deliveries_24h=11,
        successful_deliveries_24h=8,
        failed_deliveries_24h=2,
        average_response_time_ms=42.5,
    )
    assert db.executed == _health_mirrors()
    assert db.flushes == 0


def test_get_health_summary_zero_counts_and_none_avg() -> None:
    rows = [_webhook(total_deliveries=10, successful_deliveries=9)]
    h, db = _run_health(rows, [0, 0, 0, 0, 0, None, rows])
    assert h == WebhookHealthSummary(
        total_webhooks=0,
        enabled_webhooks=0,
        healthy_webhooks=1,
        unhealthy_webhooks=0,
        total_deliveries_24h=0,
        successful_deliveries_24h=0,
        failed_deliveries_24h=0,
        average_response_time_ms=None,
    )
    assert db.executed == _health_mirrors()
