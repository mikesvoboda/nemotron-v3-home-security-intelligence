# TARGET-MODULE: backend.services.notification
"""Battery U — campaign #19 of the ladder (batch-38): kill-real coverage for
``backend/services/notification.py`` (272 survivors at 55.4828% entering).

Harness-compatible by design (batch-30 single-process sweep): every test is a
module-level sync ``test_*()`` with no fixtures and no parametrize; coroutines
run through ``asyncio.run`` inside. The file is also collected by normal
pytest in the repo tree, so every seam swap restores in ``finally``.

Why the shipped battery leaves 272 survivors, and what kills them:
* RENDERED STRING — the ``_build_email_body`` pool (XX/case flips, the
  severity-color dict, the ``.get`` default family, ``and False``/``or True``
  ternaries) dies to FULL STRING EQUALITY against a plain-code mirror
  captured while nothing is mutated; the sweep runs severities LOW/MEDIUM/
  CRITICAL plus an UNMAPPED one (dict-key mutants bite only on their own
  severity; default mutants bite only when the lookup MISSES) and a no-kwarg
  polarity — the trampoline re-dispatches with caller-bound args, so the
  three ``is_high_priority: bool = False -> = True`` DEF-DEFAULT mutants are
  observable ONLY when the kwarg is omitted.
* SMTP WIRE ARGS — a call-recording fake ``smtplib`` with whole-tuple
  equality: SecretStr/plain-str/absent passwords (kills the hasattr-name and
  ``or True`` families), login on/off polarities (``and -> or`` dies with
  user-set/pw-absent), both TLS branches, falsy host/from (the ``or "XXXX"``
  flips are invisible on truthy settings — the falsy polarity runs through
  DIRECT ``_send_email_sync`` calls, which also pins the trailing-comma ARG-
  DELETION family through tuple length; the fake msg survives the whole
  with-block so a mid-block raise cannot let the spy skip sendmail).
* MESSAGE BUILDING — fake ``MIMEMultipart``/``MIMEText`` whose ``as_string``
  serializes (subtype, headers-dict, parts) into the sendmail spy:
  Subject/From/To header NAME and VALUE flips, the ``", "`` join (two
  recipients), ``MIMEText("html")`` arg-swap, subtype family, and the hp-
  kwarg None/deletion flips (the [URGENT] marker rides the subject).
* HTTP CALL SHAPE — whole ``(url, kwargs)`` equality on ``client.post``:
  json payload pinned against the payload mirror (stamped by a fake clock
  whose ``now(None)`` RAISES — killing the ``datetime.now(UTC) -> now(None)``
  family), exact ``{"Content-Type": "application/json"}`` headers (name-
  case/value flips), boundary polarities 201/300/301 for the ``>=/>/</<=``
  gate, a >250-char response body for ``text[:200] -> [:201]``.
* LOG RECORDS — a fake logger recording ``(level, msg, args)`` compared as a
  WHOLE LIST across send_email (success + 3 arms), send_webhook (success,
  error-status, SSRF, timeout, request-error, generic), deliver_alert,
  _resolve_channels, _log_delivery_result (mixed needs 2-of-3 failures so
  ``sum(2…)`` and the ``if d.success`` flip both diverge) and send_push.
* DELIVERY FIELDS — every failure arm runs with ``is_high_priority=True`` so
  the ``=None`` mutants AND the kwarg-DELETION mutants (which fall back to
  the False def-default) diverge under whole ``to_dict()`` equality; a
  150-char SSRF message makes the ``[:100] -> [:101]`` slice bite; an alert
  WITHOUT ``is_high_priority`` kills the ``getattr`` True/None-default
  family through the result and dispatch flags.
* DISPATCH — per-channel spy stubs pin ``(name, alert, arg, hp)`` for the
  three handler-lambda families; the PUSH arm gets a default-kwarg call
  (m16 ``lambda: None`` -> await-None TypeError; m17 ``send_push(None)`` ->
  AttributeError); ``get_notification_service`` dies on ``svc.settings is
  s`` (m3 constructs with None).

Honesty ledger — dispositions registered EQUIVALENT (the sweep must show
GREEN on exactly these unless the sweep proves otherwise; anything else
GREEN is a test gap). Each is a BODY proof, not a diff shape:

* _build_email_body m16/m18 EQUIVALENT — ``metadata.get("matched_conditions",
  [])`` -> ``None`` (m18 = trailing-comma = the None default via arg
  deletion): the only consumer is ``if matched_conditions:`` — None and []
  are both falsy, and any truthy value comes from the metadata itself (the
  default never fires on a truthy path).
* _build_email_body m21/m22 EQUIVALENT — ``conditions_html = ""`` -> ``None``
  / ``"XXXX"``: DEAD assignment — the if/else below rebinds conditions_html
  on every path, so the mutated initial value never reaches the f-string.
* deliver_alert m7/m21 EQUIVALENT — ``DeliveryResult(alert_id=…, deliveries
  =[], all_successful=True)`` with the ``deliveries=[]`` ARG DELETED (m7 on
  the disabled path, m21 on the no-channels path): the field is
  ``field(default_factory=list)`` — deletion reconstructs exactly ``[]``.

(run-1 sweep: RED=261 GREEN=11 of 272 — the 6 keys above plus
``_send_email_sync`` m41-m44 (else-branch login family: every non-TLS test
had ``smtp_user=None``, so no non-TLS-with-login polarity existed) and
``send_email`` m48 (``msg["From"] = smtp_from_address or "XXXX"``, inert on
truthy settings; my falsy-from polarity called ``_send_email_sync`` DIRECTLY
and bypassed the msg-building line). All 5 were KILLABLE, not equivalent:
added a non-TLS-with-login polarity (SecretStr + plain-str) and a falsy-from
polarity that patches the configured-gate on the instance so it travels the
real ``send_email`` path. ``deliver_alert`` m31 was ledgered as EQUIVALENT on
a two-arg-getattr def-default argument and came back RED — with the default
DELETED the two-arg getattr RAISES on the attribute-less alert, so it is
killed, not equivalent; ledger row removed.)

All other survivor keys have an explicit kill polarity in this battery;
the run-1 sweep result against this ledger is disclosed here when known.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from backend.core.url_validation import SSRFValidationError
from backend.services.notification import (
    NotificationChannel,
    NotificationService,
    get_notification_service,
    reset_notification_service,
)

_ALERT_ID = "a-1"
_EVENT_ID = "e-2"
_RULE_ID = "r-3"
_DEDUP_KEY = "dk-4"
_CREATED = datetime(2026, 6, 15, 9, 30, tzinfo=UTC)
_ISO_CREATED = _CREATED.isoformat()
_STAMP = "2026-06-15T10:00:00+00:00"
_COND1 = "motion_zone_north"
_COND2 = "door_forced_open"
_WH = "https://hook.test"


def _globals_of(fn: Any) -> dict[str, Any]:
    """Module globals of the REAL function (mutant-tree wrappers delegate)."""
    f = fn
    while hasattr(f, "__wrapped__"):
        f = f.__wrapped__
    return f.__globals__


_G = _globals_of(NotificationService.send_email)


def _swap(key: str, value: Any) -> Any:
    old = _G[key]

    def restore() -> None:
        _G[key] = old

    _G[key] = value
    return restore


class _Env:
    """A bundle of seam swaps with one finally-friendly close()."""

    def __init__(self) -> None:
        self._restores: list = []

    def swap(self, key: str, value: Any) -> None:
        self._restores.append(_swap(key, value))

    def close(self) -> None:
        for r in self._restores:
            r()


class _Obj:
    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


class _EnumVal:
    def __init__(self, val: str) -> None:
        self.value = val


class _Alert:
    def __init__(
        self,
        with_priority: bool = True,
        metadata: dict | None = None,
        channels: list | None = None,
        severity: str = "high",
        created_at: Any = _CREATED,
    ) -> None:
        self.id = _ALERT_ID
        self.event_id = _EVENT_ID
        self.rule_id = _RULE_ID
        self.severity = _EnumVal(severity)
        self.status = _EnumVal("new")
        self.dedup_key = _DEDUP_KEY
        self.created_at = created_at
        self.channels = channels if channels is not None else []
        self.alert_metadata = {} if metadata is None else metadata
        if with_priority:
            self.is_high_priority = True


class _Settings:
    smtp_host = "smtp.test"
    smtp_from_address = "from@test"
    default_email_recipients: list = []  # noqa: RUF012
    smtp_password = None
    smtp_user = None
    smtp_port = 587
    smtp_use_tls = True
    default_webhook_url = ""
    webhook_timeout_seconds = 5
    notification_enabled = True


class _Secret:
    def __init__(self, val: str) -> None:
        self.val = val

    def get_secret_value(self) -> str:
        return self.val


class _Logger:
    """Records (level, msg, args) — whole-LIST equality is the assertion."""

    def __init__(self, sink: list) -> None:
        self.sink = sink

    def _level(self, lvl: str) -> Any:
        def log(msg: Any = None, *args: Any) -> None:
            self.sink.append((lvl, msg, args))

        return log

    def __getattr__(self, lvl: str) -> Any:
        return self._level(lvl)


def _fake_dt_raises_naive() -> Any:
    """datetime replacement: now(None) raises; now(UTC) stamps a fixed iso str."""

    class _DT:
        @staticmethod
        def now(tz: Any = None) -> Any:
            if tz is None:
                msg = "naive clock not allowed"
                raise TypeError(msg)
            return _Obj(isoformat=lambda: _STAMP)

    return _DT


class _FixedNow:
    """datetime stand-in: now(UTC) yields a stamping object, now(None) raises."""

    @staticmethod
    def now(tz: Any = None) -> Any:
        if tz is None:
            msg = "naive clock not allowed"
            raise TypeError(msg)
        return _Obj(isoformat=lambda: _STAMP)


class _Timeout:
    def __init__(self, val: Any = None) -> None:
        self.val = val


class _HttpxMod:
    Timeout = _Timeout
    AsyncClient: Any = None

    class TimeoutException(Exception):
        pass

    class RequestError(Exception):
        pass


def _mk_httpx(fac: Any) -> Any:
    hx = _HttpxMod()
    hx.AsyncClient = fac
    return hx


class _Client:
    def __init__(self, calls: list, behavior: Any) -> None:
        self.calls = calls
        self.behavior = behavior

    async def post(self, url: Any, **kw: Any) -> Any:
        self.calls.append((url, kw))
        return self.behavior()

    async def aclose(self) -> None:
        pass


def _resp(code: int, text: str = "ok") -> Any:
    return _Obj(status_code=code, text=text)


def _raise(exc: BaseException) -> Any:
    raise exc


class _FakeSmtplib:
    SMTPAuthenticationError = type("SMTPAuthenticationError", (Exception,), {})
    SMTPException = type("SMTPException", (Exception,), {})

    def __init__(self) -> None:
        self.calls: list = []

    def SMTP(self, *args: Any) -> _FakeSmtplib:
        self.calls.append(("SMTP", *tuple(args)))
        return self

    def __enter__(self) -> _FakeSmtplib:
        return self

    def __exit__(self, *a: Any) -> bool:
        return False

    def starttls(self, **kw: Any) -> None:
        self.calls.append(("starttls", kw))

    def login(self, *a: Any) -> None:
        self.calls.append(("login", *tuple(a)))

    def sendmail(self, *a: Any) -> None:
        self.calls.append(("sendmail", *tuple(a)))


class _FakeSsl:
    def __init__(self) -> None:
        self.count = 0

    def create_default_context(self) -> tuple:
        self.count += 1
        return ("ctx", self.count)


class _FakeMIME:
    """Minimal email.Message stand-in: REAL __setitem__ (special methods are
    looked up on the TYPE), attach, and an as_string that serializes."""

    def __init__(self, sub: Any) -> None:
        self.sub = sub
        self.headers: dict = {}
        self.parts: list = []

    def __setitem__(self, k: str, v: Any) -> None:
        self.headers[k] = v

    def attach(self, part: Any) -> None:
        self.parts.append(part)

    def as_string(self) -> str:
        parts = [[p.body, p.subtype] for p in self.parts]
        return "MSG::" + json.dumps([self.sub, self.headers, parts], sort_keys=True)


def _mimemultipart(sub: Any = None) -> _FakeMIME:
    return _FakeMIME(sub)


def _mimetext(body: Any, subtype: Any = None) -> Any:
    return _Obj(body=body, subtype=subtype)


def _svc(**attrs: Any) -> NotificationService:
    s = _Settings()
    for k, v in attrs.items():
        setattr(s, k, v)
    return NotificationService(s)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _delivery_dict(
    ch: Any,
    ok: bool,
    err: Any = None,
    recip: Any = None,
    hp: Any = False,
    at: Any = None,
) -> dict:
    return {
        "channel": ch,
        "success": ok,
        "error": err,
        "delivered_at": at,
        "recipient": recip,
        "is_high_priority": hp,
    }


def _result_dict(alert_id: Any, deliveries: list, ok: bool, hp: Any) -> dict:
    return {
        "alert_id": alert_id,
        "deliveries": deliveries,
        "all_successful": ok,
        "successful_count": sum(1 for d in deliveries if d["success"]),
        "failed_count": sum(1 for d in deliveries if not d["success"]),
        "is_high_priority": hp,
    }


# ------------------------------------------------------------------ mirrors


def _expected_subject(hp: bool) -> str:
    if hp:
        return "[URGENT] [HIGH] Security Alert - Home Security Intelligence"
    return "[HIGH] Security Alert - Home Security Intelligence"


def _expected_body(alert: Any, hp: bool) -> str:
    """Plain-code mirror of _build_email_body (runs with NO mutant active)."""
    metadata = alert.alert_metadata or {}
    rule_name = metadata.get("rule_name", "Unknown Rule")
    matched_conditions = metadata.get("matched_conditions", [])
    conditions_html = ""
    if matched_conditions:
        conditions_html = (
            "<ul>" + "".join(f"<li>{cond}</li>" for cond in matched_conditions) + "</ul>"
        )
    else:
        conditions_html = "<p>No specific conditions recorded.</p>"
    severity_colors = {
        "low": "#28a745",
        "medium": "#ffc107",
        "high": "#fd7e14",
        "critical": "#dc3545",
    }
    severity_color = severity_colors.get(alert.severity.value, "#6c757d")
    urgent_notice = ""
    if hp:
        urgent_notice = """
        <div style="background-color: #dc3545; color: white; padding: 10px; margin-bottom: 15px; border-radius: 5px;">
            <strong>URGENT: IMMEDIATE ATTENTION REQUIRED</strong>
            <p style="margin: 5px 0 0 0;">This is a high-priority security alert that requires immediate review.</p>
        </div>"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
        .header {{ background-color: {severity_color}; color: white; padding: 15px; border-radius: 5px 5px 0 0; }}
        .content {{ border: 1px solid #ddd; border-top: none; padding: 20px; border-radius: 0 0 5px 5px; }}
        .label {{ font-weight: bold; color: #555; }}
        .value {{ margin-bottom: 15px; }}
        .footer {{ margin-top: 20px; font-size: 12px; color: #888; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>Security Alert: {alert.severity.value.upper()}</h2>
    </div>
    <div class="content">
        {urgent_notice}
        <p class="label">Alert ID:</p>
        <p class="value">{alert.id}</p>

        <p class="label">Rule:</p>
        <p class="value">{rule_name}</p>

        <p class="label">Event ID:</p>
        <p class="value">{alert.event_id}</p>

        <p class="label">Status:</p>
        <p class="value">{alert.status.value}</p>

        <p class="label">Created:</p>
        <p class="value">{alert.created_at.isoformat() if alert.created_at else "Unknown"}</p>

        <p class="label">Matched Conditions:</p>
        {conditions_html}

        <div class="footer">
            <p>This is an automated message from Home Security Intelligence.</p>
        </div>
    </div>
</body>
</html>
"""


def _expected_payload(alert: Any, hp: bool, stamp: str = _STAMP) -> dict:
    """Plain-code mirror of _build_webhook_payload."""
    metadata = alert.alert_metadata or {}
    payload = {
        "type": "security_alert",
        "alert": {
            "id": alert.id,
            "event_id": alert.event_id,
            "rule_id": alert.rule_id,
            "severity": alert.severity.value,
            "status": alert.status.value,
            "dedup_key": alert.dedup_key,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "channels": alert.channels or [],
        },
        "metadata": {
            "rule_name": metadata.get("rule_name"),
            "matched_conditions": metadata.get("matched_conditions", []),
        },
        "is_high_priority": hp,
        "source": "home_security_intelligence",
        "timestamp": stamp,
    }
    if "smoke_fire_type" in metadata:
        payload["smoke_fire_type"] = metadata["smoke_fire_type"]
    return payload


def _rich_alert() -> _Alert:
    return _Alert(metadata={"rule_name": "Smoke Pattern", "matched_conditions": [_COND1, _COND2]})


# ------------------------------------------------------------------ builders


def test_email_subject_exact_polarity() -> None:
    s = _svc()
    a = _Alert()
    assert s._build_email_subject(a, is_high_priority=True) == _expected_subject(True)
    assert s._build_email_subject(a, is_high_priority=False) == _expected_subject(False)


def test_email_subject_default_kwarg() -> None:
    # DEF-DEFAULT m1 (False->True) is observable ONLY via an omitted kwarg.
    s = _svc()
    assert s._build_email_subject(_Alert()) == _expected_subject(False)


def test_email_body_rich_both_hp() -> None:
    s = _svc()
    a = _rich_alert()
    for hp in (True, False):
        assert s._build_email_body(a, is_high_priority=hp) == _expected_body(a, hp)


def test_email_body_defaults_no_conditions() -> None:
    s = _svc()
    for meta in (None, {}, {"rule_name": "", "matched_conditions": []}):
        a = _Alert(metadata=meta)
        for hp in (True, False):
            assert s._build_email_body(a, is_high_priority=hp) == _expected_body(a, hp)


def test_email_body_no_created_at() -> None:
    s = _svc()
    a = _Alert(created_at=None)
    for hp in (True, False):
        assert s._build_email_body(a, is_high_priority=hp) == _expected_body(a, hp)


def test_email_body_severity_sweep() -> None:
    s = _svc()
    for sev in ("low", "medium", "critical", "urgent"):
        a = _Alert(severity=sev)
        for hp in (True, False):
            assert s._build_email_body(a, is_high_priority=hp) == _expected_body(a, hp)


def test_email_body_default_kwarg() -> None:
    s = _svc()
    a = _rich_alert()
    assert s._build_email_body(a) == _expected_body(a, False)


def test_webhook_payload_rich() -> None:
    s = _svc()
    a = _Alert(
        metadata={
            "rule_name": "Smoke",
            "matched_conditions": [_COND1],
            "smoke_fire_type": "smoldering",
        },
        channels=["email", "webhook"],
    )
    env = _Env()
    env.swap("datetime", _fake_dt_raises_naive())
    try:
        for hp in (True, False):
            assert s._build_webhook_payload(a, is_high_priority=hp) == _expected_payload(a, hp)
    finally:
        env.close()


def test_webhook_payload_minimal() -> None:
    s = _svc()
    a = _Alert()
    env = _Env()
    env.swap("datetime", _fake_dt_raises_naive())
    try:
        for hp in (True, False):
            assert s._build_webhook_payload(a, is_high_priority=hp) == _expected_payload(a, hp)
    finally:
        env.close()


def test_webhook_payload_no_created_at() -> None:
    s = _svc()
    a = _Alert(created_at=None)
    env = _Env()
    env.swap("datetime", _fake_dt_raises_naive())
    try:
        for hp in (True, False):
            assert s._build_webhook_payload(a, is_high_priority=hp) == _expected_payload(a, hp)
    finally:
        env.close()


def test_webhook_payload_default_kwarg() -> None:
    s = _svc()
    a = _Alert()
    env = _Env()
    env.swap("datetime", _fake_dt_raises_naive())
    try:
        assert s._build_webhook_payload(a) == _expected_payload(a, False)
    finally:
        env.close()


# ------------------------------------------------------------------ config / client / close


def test_email_configured_polarity() -> None:
    s = _svc(smtp_host="", smtp_from_address="from@test")
    assert s.is_email_configured() is False
    s.settings.smtp_host = "smtp.test"
    s.settings.smtp_from_address = ""
    assert s.is_email_configured() is False
    s.settings.smtp_from_address = "from@test"
    assert s.is_email_configured() is True


def test_available_channels_matrix() -> None:
    s = _svc(smtp_host="", smtp_from_address="", default_webhook_url="")
    assert s.get_available_channels() == []
    s.settings.smtp_host = "smtp.test"
    s.settings.smtp_from_address = "from@test"
    assert s.get_available_channels() == [NotificationChannel.EMAIL]
    s.settings.default_webhook_url = _WH
    assert s.get_available_channels() == [NotificationChannel.EMAIL, NotificationChannel.WEBHOOK]
    s.settings.smtp_host = ""
    assert s.get_available_channels() == [NotificationChannel.WEBHOOK]
    s.settings.smtp_host = "smtp.test"
    s.settings.default_webhook_url = ""
    assert s.get_available_channels() == [NotificationChannel.EMAIL]
    assert s.is_push_configured() is False


def test_http_client_lazy_and_timeout_sentinel() -> None:
    s = _svc()
    made: list = []
    env = _Env()

    def fac(**kw: Any) -> _Client:
        made.append(kw)
        return _Client([], lambda: None)

    env.swap("httpx", _mk_httpx(fac))
    try:
        assert s._http_client is None
        c1 = _run(s._get_http_client())
        assert isinstance(c1, _Client)
        assert len(made) == 1
        assert isinstance(made[0]["timeout"], _Timeout)
        assert made[0]["timeout"].val == 5
        c2 = _run(s._get_http_client())
        assert c2 is c1
        assert len(made) == 1
    finally:
        env.close()


def test_close_resets_client_to_none() -> None:
    s = _svc()
    closed: list = []

    class _C:
        async def aclose(self) -> None:
            closed.append(1)

    s._http_client = _C()
    _run(s.close())
    assert closed == [1]
    assert s._http_client is None


def test_close_noop_when_absent() -> None:
    s = _svc()
    s._http_client = None
    _run(s.close())
    assert s._http_client is None


# ------------------------------------------------------------------ send_email


def test_send_email_not_configured() -> None:
    s = _svc(smtp_host="")
    d = _run(s.send_email(_Alert()))
    assert d.to_dict() == _delivery_dict(
        "email", False, "Email is not configured (missing SMTP settings)"
    )


def test_send_email_no_recipients() -> None:
    s = _svc()
    d = _run(s.send_email(_Alert()))
    assert d.to_dict() == _delivery_dict(
        "email", False, "No email recipients configured or provided"
    )


def _email_seams(s: NotificationService, logs: list, hp: bool, recipients: list) -> tuple:
    """Swap the send_email seams; also compute the as_string the ORIGINAL
    send_email would hand to sendmail (plain-code mirror, no mutant active)."""
    env = _Env()
    sm = _FakeSmtplib()
    env.swap("smtplib", sm)
    env.swap("ssl", _FakeSsl())
    env.swap("httpx", _mk_httpx(lambda **_kw: _Client([], lambda: None)))
    env.swap("MIMEMultipart", _mimemultipart)
    env.swap("MIMEText", _mimetext)
    env.swap("logger", _Logger(logs))
    env.swap("datetime", _FixedNow)
    alert = _Alert(with_priority=True)
    headers = {
        "Subject": _expected_subject(hp),
        "From": s.settings.smtp_from_address or "",
        "To": ", ".join(recipients),
    }
    parts = [[_expected_body(alert, hp), "html"]]
    expected_msg = "MSG::" + json.dumps(["alternative", headers, parts], sort_keys=True)
    return env, sm, alert, expected_msg


def test_send_email_success_tls_auth_secretstr() -> None:
    logs: list = []
    s = _svc(smtp_password=_Secret("sekret"), smtp_user="u1")  # pragma: allowlist secret
    rec = ["ops@x.com", "sec@x.com"]
    env, sm, a, expected_msg = _email_seams(s, logs, True, rec)
    try:
        d = _run(s.send_email(a, rec, is_high_priority=True))
    finally:
        env.close()
    assert d.to_dict() == _delivery_dict(
        "email", True, recip="ops@x.com, sec@x.com", hp=True, at=_STAMP
    )
    assert sm.calls == [
        ("SMTP", "smtp.test", 587),
        ("starttls", {"context": ("ctx", 1)}),
        ("login", "u1", "sekret"),
        ("sendmail", "from@test", rec, expected_msg),
    ]
    assert logs == [("info", "Email notification sent for alert a-1 to 2 recipients", ())]


def test_send_email_success_noauth_notls_plainpw() -> None:
    logs: list = []
    s = _svc(
        smtp_use_tls=False,
        smtp_password="plainpw",  # pragma: allowlist secret
        smtp_user=None,
    )
    rec = ["ops@x.com", "sec@x.com"]
    env, sm, a, expected_msg = _email_seams(s, logs, False, rec)
    try:
        d = _run(s.send_email(a, rec))
    finally:
        env.close()
    assert d.to_dict() == _delivery_dict(
        "email", True, recip="ops@x.com, sec@x.com", hp=False, at=_STAMP
    )
    assert sm.calls == [
        ("SMTP", "smtp.test", 587),
        ("sendmail", "from@test", rec, expected_msg),
    ]


def test_send_email_recipients_fallback_settings() -> None:
    logs: list = []
    s = _svc(smtp_use_tls=False, default_email_recipients=["dflt@x.com"])
    env, sm, a, expected_msg = _email_seams(s, logs, False, ["dflt@x.com"])
    try:
        d = _run(s.send_email(a))
    finally:
        env.close()
    assert d.to_dict() == _delivery_dict("email", True, recip="dflt@x.com", hp=False, at=_STAMP)
    assert sm.calls[-1] == ("sendmail", "from@test", ["dflt@x.com"], expected_msg)


def _email_failing_seams(s: NotificationService, logs: list, boom: str) -> tuple:
    env, sm, a, _msg = _email_seams(s, logs, True, ["ops@x.com"])

    def sendmail(*args: Any) -> None:
        sm.calls.append(("sendmail", *tuple(args)))
        if boom == "auth":
            raise _FakeSmtplib.SMTPAuthenticationError("bad creds")
        if boom == "smtp":
            raise _FakeSmtplib.SMTPException("smtp broke")
        raise ValueError("kaboom")

    sm.sendmail = sendmail  # type: ignore[method-assign]
    return env, sm, a


def test_send_email_auth_arm_whole_dict_and_log() -> None:
    logs: list = []
    s = _svc(smtp_use_tls=False)
    env, _sm, a = _email_failing_seams(s, logs, "auth")
    try:
        d = _run(s.send_email(a, ["ops@x.com"], is_high_priority=True))
    finally:
        env.close()
    assert d.to_dict() == _delivery_dict(
        "email", False, "SMTP authentication failed: bad creds", hp=True
    )
    assert logs == [("error", "SMTP authentication failed: bad creds", ())]


def test_send_email_smtpexception_arm_whole_dict_and_log() -> None:
    logs: list = []
    s = _svc(smtp_use_tls=False)
    env, _sm, a = _email_failing_seams(s, logs, "smtp")
    try:
        d = _run(s.send_email(a, ["ops@x.com"], is_high_priority=True))
    finally:
        env.close()
    assert d.to_dict() == _delivery_dict("email", False, "SMTP error: smtp broke", hp=True)
    assert logs == [("error", "SMTP error: smtp broke", ())]


def test_send_email_generic_arm_whole_dict_and_log() -> None:
    logs: list = []
    s = _svc(smtp_use_tls=False)
    env, _sm, a = _email_failing_seams(s, logs, "other")
    try:
        d = _run(s.send_email(a, ["ops@x.com"], is_high_priority=True))
    finally:
        env.close()
    assert d.to_dict() == _delivery_dict("email", False, "Email delivery failed: kaboom", hp=True)
    assert logs == [("exception", "Email delivery failed: kaboom", ())]


# ------------------------------------------------------------------ _send_email_sync polarities


def _sync_direct(s: NotificationService) -> list:
    env = _Env()
    sm = _FakeSmtplib()
    env.swap("smtplib", sm)
    env.swap("ssl", _FakeSsl())
    try:
        s._send_email_sync(_Obj(as_string=lambda: "MSGSTR"), ["r1@x.com"])
    finally:
        env.close()
    return sm.calls


def test_sync_password_secret_str_and_absent() -> None:
    s = _svc(smtp_password=_Secret("sekret"), smtp_user="u1")  # pragma: allowlist secret
    assert _sync_direct(s) == [
        ("SMTP", "smtp.test", 587),
        ("starttls", {"context": ("ctx", 1)}),
        ("login", "u1", "sekret"),
        ("sendmail", "from@test", ["r1@x.com"], "MSGSTR"),
    ]
    s.settings.smtp_password = "plainpw"  # pragma: allowlist secret
    assert _sync_direct(s) == [
        ("SMTP", "smtp.test", 587),
        ("starttls", {"context": ("ctx", 1)}),
        ("login", "u1", "plainpw"),
        ("sendmail", "from@test", ["r1@x.com"], "MSGSTR"),
    ]
    s.settings.smtp_password = None
    assert _sync_direct(s) == [
        ("SMTP", "smtp.test", 587),
        ("starttls", {"context": ("ctx", 1)}),
        ("sendmail", "from@test", ["r1@x.com"], "MSGSTR"),
    ]


def test_sync_nontls_login_secret_and_plain() -> None:
    # The ELSE-branch login mutants (m41 None-user / m42 None-pw / m43 dropped
    # user / m44 dropped pw — trailing-comma ARG DELETION -> 1-arg login) live
    # in the non-TLS with-block: needs non-TLS WITH login firing.
    s = _svc(
        smtp_use_tls=False,
        smtp_password=_Secret("sekret"),  # pragma: allowlist secret
        smtp_user="u1",
    )
    assert _sync_direct(s) == [
        ("SMTP", "smtp.test", 587),
        ("login", "u1", "sekret"),
        ("sendmail", "from@test", ["r1@x.com"], "MSGSTR"),
    ]
    s.settings.smtp_password = "plainpw"  # pragma: allowlist secret
    assert _sync_direct(s) == [
        ("SMTP", "smtp.test", 587),
        ("login", "u1", "plainpw"),
        ("sendmail", "from@test", ["r1@x.com"], "MSGSTR"),
    ]


def test_send_email_from_empty_msg_header() -> None:
    # m48 (`msg["From"] = smtp_from_address or "XXXX"`) is inert on truthy
    # settings — the falsy-from polarity must run through SEND_EMAIL (the
    # msg-building path), which the configured-gate would short-circuit:
    # patch the gate on the instance.
    logs: list = []
    s = _svc(smtp_use_tls=False, smtp_from_address="")
    s.is_email_configured = lambda: True  # type: ignore[method-assign]
    rec = ["ops@x.com"]
    env, sm, a, expected_msg = _email_seams(s, logs, False, rec)
    try:
        d = _run(s.send_email(a, rec))
    finally:
        env.close()
    assert d.to_dict() == _delivery_dict("email", True, recip="ops@x.com", hp=False, at=_STAMP)
    assert sm.calls[-1] == ("sendmail", "", rec, expected_msg)


def test_sync_user_absent_skips_login_both_branches() -> None:
    for tls in (True, False):
        s = _svc(smtp_use_tls=tls, smtp_password="pw", smtp_user=None)
        calls = _sync_direct(s)
        assert not any(c[0] == "login" for c in calls), tls
        assert calls[0] == ("SMTP", "smtp.test", 587), tls
        assert calls[-1] == ("sendmail", "from@test", ["r1@x.com"], "MSGSTR"), tls


def test_sync_from_empty_sendmail_first_arg_both_branches() -> None:
    for tls in (True, False):
        s = _svc(smtp_use_tls=tls, smtp_from_address="")
        calls = _sync_direct(s)
        assert calls[-1] == ("sendmail", "", ["r1@x.com"], "MSGSTR"), tls


def test_sync_host_empty_smtp_args_both_branches() -> None:
    for tls in (True, False):
        s = _svc(smtp_use_tls=tls, smtp_host="")
        calls = _sync_direct(s)
        assert calls[0] == ("SMTP", "", 587), tls


# ------------------------------------------------------------------ send_webhook


def _run_webhook(
    s: NotificationService,
    a: Any,
    kw: dict,
    logs: list,
    calls: list,
    behavior: Any,
    validator: Any = None,
) -> Any:
    env = _Env()
    env.swap("httpx", _mk_httpx(lambda **_ckw: _Client(calls, behavior)))
    env.swap(
        "validate_webhook_url_for_request",
        validator if validator is not None else (lambda url, **_inner: url),
    )
    env.swap("logger", _Logger(logs))
    env.swap("datetime", _fake_dt_raises_naive())
    try:
        return _run(s.send_webhook(a, **kw))
    finally:
        env.close()


def _post_kwargs(hp: bool) -> dict:
    a = _Alert(with_priority=True)
    return {"json": _expected_payload(a, hp), "headers": {"Content-Type": "application/json"}}


def test_send_webhook_no_url() -> None:
    s = _svc(default_webhook_url="")
    d = _run(s.send_webhook(_Alert()))
    assert d.to_dict() == _delivery_dict("webhook", False, "No webhook URL configured or provided")


def test_send_webhook_success_pincall() -> None:
    logs: list = []
    calls: list = []
    seen: list = []
    s = _svc(default_webhook_url=_WH)

    def validator(url: Any, **inner: Any) -> Any:
        seen.append((url, inner))
        return url

    d = _run_webhook(
        s,
        _Alert(with_priority=True),
        {"is_high_priority": True},
        logs,
        calls,
        lambda: _resp(200, "fine"),
        validator=validator,
    )
    assert d.to_dict() == _delivery_dict("webhook", True, recip=_WH, hp=True, at=_STAMP)
    assert calls == [(_WH, _post_kwargs(True))]
    assert logs == [("info", "Webhook notification sent successfully for alert %s", ("a-1",))]
    assert seen == [(_WH, {"is_development": False})]


def test_send_webhook_url_arg_wins_299() -> None:
    logs: list = []
    calls: list = []
    s = _svc(default_webhook_url="https://other.test")
    d = _run_webhook(
        s,
        _Alert(with_priority=True),
        {"webhook_url": "https://explicit.test", "is_high_priority": True},
        logs,
        calls,
        lambda: _resp(299, "x"),
    )
    assert d.to_dict() == _delivery_dict(
        "webhook", True, recip="https://explicit.test", hp=True, at=_STAMP
    )
    assert calls[0][0] == "https://explicit.test"


def test_send_webhook_status_boundaries_201_300_301() -> None:
    # 201 kills `>= -> >`; 300 (orig FAILS, `<= 300`/`< 301` mutants pass) is
    # the boundary discriminator; 301 pins the error-message path.
    for code, ok in ((201, True), (300, False), (301, False)):
        logs: list = []
        calls: list = []
        s = _svc(default_webhook_url=_WH)
        d = _run_webhook(
            s,
            _Alert(with_priority=True),
            {"is_high_priority": True},
            logs,
            calls,
            lambda code=code: _resp(code, "b"),
        )
        dd = d.to_dict()
        assert dd["success"] is ok, code
        assert dd["recipient"] == _WH, code
        assert dd["is_high_priority"] is True, code
        if ok:
            assert dd["error"] is None, code
            assert dd["delivered_at"] == _STAMP, code
        else:
            assert dd["error"] == f"Webhook returned status {code}: b", code
            assert dd["delivered_at"] is None, code
            assert logs == [("warning", "Webhook returned error status %s", (code,))], code


def test_send_webhook_error_status_truncates_200() -> None:
    body = "".join(f"t{i}" for i in range(400))  # >250 chars, no repeat period
    logs: list = []
    s = _svc(default_webhook_url=_WH)
    d = _run_webhook(
        s,
        _Alert(with_priority=True),
        {"is_high_priority": True},
        logs,
        [],
        lambda: _resp(500, body),
    )
    assert d.to_dict() == _delivery_dict(
        "webhook", False, f"Webhook returned status 500: {body[:200]}", recip=_WH, hp=True
    )
    assert logs == [("warning", "Webhook returned error status %s", (500,))]


def test_send_webhook_isdevelopment_true_passthrough() -> None:
    logs: list = []
    calls: list = []
    seen: list = []
    s = _svc(default_webhook_url=_WH, is_development=True)

    def validator(url: Any, **inner: Any) -> Any:
        seen.append((url, inner))
        return url

    _run_webhook(
        s,
        _Alert(with_priority=True),
        {"is_high_priority": True},
        logs,
        calls,
        lambda: _resp(200, "x"),
        validator=validator,
    )
    assert seen == [(_WH, {"is_development": True})]


def test_send_webhook_ssrf_failure_whole_dict_and_log() -> None:
    logs: list = []
    calls: list = []
    msg = "private ip literal " + "z" + "y" * 126  # 150 chars, unique tail
    s = _svc(default_webhook_url=_WH)

    def boom(url: Any, **inner: Any) -> Any:
        raise SSRFValidationError(msg)

    d = _run_webhook(
        s,
        _Alert(with_priority=True),
        {"is_high_priority": True},
        logs,
        calls,
        lambda: _resp(200, "x"),
        validator=boom,
    )
    assert d.to_dict() == _delivery_dict(
        "webhook", False, f"Invalid webhook URL: {msg}", recip=_WH, hp=True
    )
    assert logs == [("warning", "SSRF validation failed for webhook URL: %s", (msg[:100],))]
    assert calls == []


def test_send_webhook_timeout_arm_whole_dict_and_log() -> None:
    logs: list = []
    s = _svc(default_webhook_url=_WH)

    def fac(**kw: Any) -> _Client:
        hx = _G["httpx"]
        return _Client([], lambda: _raise(hx.TimeoutException("slow")))

    env = _Env()
    env.swap("httpx", _mk_httpx(fac))
    env.swap("validate_webhook_url_for_request", lambda url, **_inner: url)
    env.swap("logger", _Logger(logs))
    env.swap("datetime", _fake_dt_raises_naive())
    try:
        d = _run(s.send_webhook(_Alert(with_priority=True), is_high_priority=True))
    finally:
        env.close()
    assert d.to_dict() == _delivery_dict(
        "webhook", False, "Webhook request timed out after 5s", recip=_WH, hp=True
    )
    assert logs == [("error", "Webhook request timed out after 5s", ())]


def test_send_webhook_requesterror_arm_whole_dict_and_log() -> None:
    logs: list = []
    s = _svc(default_webhook_url=_WH)

    def fac(**kw: Any) -> _Client:
        hx = _G["httpx"]
        return _Client([], lambda: _raise(hx.RequestError("boom")))

    env = _Env()
    env.swap("httpx", _mk_httpx(fac))
    env.swap("validate_webhook_url_for_request", lambda url, **_inner: url)
    env.swap("logger", _Logger(logs))
    env.swap("datetime", _fake_dt_raises_naive())
    try:
        d = _run(s.send_webhook(_Alert(with_priority=True), is_high_priority=True))
    finally:
        env.close()
    assert d.to_dict() == _delivery_dict(
        "webhook", False, "Webhook request failed: boom", recip=_WH, hp=True
    )
    assert logs == [("error", "Webhook request failed: boom", ())]


def test_send_webhook_generic_arm_whole_dict_and_log() -> None:
    logs: list = []
    s = _svc(default_webhook_url=_WH)
    d = _run_webhook(
        s,
        _Alert(with_priority=True),
        {"is_high_priority": True},
        logs,
        [],
        lambda: _raise(ValueError("bad gateway brain")),
    )
    assert d.to_dict() == _delivery_dict(
        "webhook",
        False,
        "Webhook delivery failed: bad gateway brain",
        recip=_WH,
        hp=True,
    )
    assert logs == [("exception", "Webhook delivery failed: bad gateway brain", ())]


# ------------------------------------------------------------------ push / resolve / dispatch


def test_send_push_stub_whole_dict_and_log() -> None:
    logs: list = []
    s = _svc()
    env = _Env()
    env.swap("logger", _Logger(logs))
    try:
        d = _run(s.send_push(_Alert()))
    finally:
        env.close()
    assert d.to_dict() == _delivery_dict(
        "push", False, "Push notifications are not yet implemented"
    )
    assert logs == [("debug", "Push notification requested for alert a-1 (not implemented)", ())]


def test_resolve_channels_explicit_wins_including_empty() -> None:
    s = _svc()
    a = _Alert(channels=["email"])
    assert s._resolve_channels(a, [NotificationChannel.WEBHOOK]) == [NotificationChannel.WEBHOOK]
    assert s._resolve_channels(a, []) == []


def test_resolve_channels_alert_channels_parse() -> None:
    s = _svc(default_webhook_url="")
    a = _Alert(channels=["email", "WEBHOOK"])
    assert s._resolve_channels(a, None) == [NotificationChannel.EMAIL, NotificationChannel.WEBHOOK]


def test_resolve_channels_fallback_to_available() -> None:
    s = _svc(smtp_host="", smtp_from_address="", default_webhook_url=_WH)
    assert s._resolve_channels(_Alert(), None) == [NotificationChannel.WEBHOOK]


def test_resolve_channels_unknown_warns_and_skips() -> None:
    logs: list = []
    s = _svc()
    env = _Env()
    env.swap("logger", _Logger(logs))
    try:
        only_bad = s._resolve_channels(_Alert(channels=["carrier-pigeon"]), None)
        mixed = s._resolve_channels(_Alert(channels=["carrier-pigeon", "email"]), None)
    finally:
        env.close()
    assert only_bad == []
    assert mixed == [NotificationChannel.EMAIL]
    assert logs == [
        ("warning", "Unknown notification channel: carrier-pigeon", ()),
        ("warning", "Unknown notification channel: carrier-pigeon", ()),
    ]


def _stub_channel(
    s: NotificationService, sink: list, channel: NotificationChannel, ok: bool, pos: int
) -> None:
    def build() -> Any:
        return _Obj(
            channel=channel,
            success=ok,
            error=None if ok else "stub-fail",
            delivered_at=None,
            recipient=None,
            is_high_priority=False,
            to_dict=lambda: _delivery_dict(channel.value, ok, err=None if ok else "stub-fail"),
        )

    if channel is NotificationChannel.PUSH:

        async def push(alert: Any) -> Any:
            sink.append(("push", alert))
            if pos == 1:
                raise AttributeError("'NoneType' object has no attribute 'id'")
            return build()

        s.send_push = push  # type: ignore[method-assign]
        return

    async def generic(alert: Any, arg: Any = None, is_high_priority: bool = False) -> Any:
        sink.append((channel.value, alert, arg, is_high_priority))
        return build()

    if channel is NotificationChannel.EMAIL:
        s.send_email = generic  # type: ignore[method-assign]
    else:
        s.send_webhook = generic  # type: ignore[method-assign]


def test_send_to_channel_email_forwards_all_args() -> None:
    s = _svc()
    seen: list = []
    _stub_channel(s, seen, NotificationChannel.EMAIL, True, 0)
    a = _Alert()
    d = _run(
        s._send_to_channel(NotificationChannel.EMAIL, a, ["ops@x.com"], None, is_high_priority=True)
    )
    assert seen == [("email", a, ["ops@x.com"], True)]
    assert d.to_dict() == _delivery_dict("email", True)


def test_send_to_channel_webhook_forwards_all_args() -> None:
    s = _svc()
    seen: list = []
    _stub_channel(s, seen, NotificationChannel.WEBHOOK, True, 0)
    a = _Alert()
    d = _run(
        s._send_to_channel(NotificationChannel.WEBHOOK, a, None, "https://h", is_high_priority=True)
    )
    assert seen == [("webhook", a, "https://h", True)]
    assert d.to_dict() == _delivery_dict("webhook", True)


def test_send_to_channel_push_forwards_alert() -> None:
    s = _svc()
    seen: list = []
    _stub_channel(s, seen, NotificationChannel.PUSH, True, 0)
    a = _Alert()
    d = _run(s._send_to_channel(NotificationChannel.PUSH, a, None, None, is_high_priority=True))
    assert seen == [("push", a)]
    assert d.to_dict() == _delivery_dict("push", True)


def test_send_to_channel_push_default_kwarg_kills_none_lambda() -> None:
    # m16 (`lambda: None`) -> await None TypeError; m17 (`send_push(None)`) ->
    # the REAL send_push logs on None.id -> AttributeError -> RED. Both are
    # caught by calling WITHOUT is_high_priority (orig reaches the real stub).
    s = _svc()
    a = _Alert(with_priority=True)
    d = _run(s._send_to_channel(NotificationChannel.PUSH, a, None, None))
    assert d.to_dict() == _delivery_dict(
        "push", False, "Push notifications are not yet implemented"
    )


def test_send_to_channel_unknown_channel() -> None:
    s = _svc()
    d = _run(
        s._send_to_channel(
            "smoke-signal",  # type: ignore[arg-type]
            _Alert(),
            None,
            None,
            is_high_priority=True,
        )
    )
    assert d.channel == "smoke-signal"
    assert d.success is False
    assert d.error == "Unknown channel: smoke-signal"
    assert d.is_high_priority is True


# ------------------------------------------------------------------ deliver_alert


def _stubbed_service(**attrs: Any) -> tuple[NotificationService, list]:
    s = _svc(**attrs)
    sink: list = []
    _stub_channel(s, sink, NotificationChannel.EMAIL, True, 0)
    _stub_channel(s, sink, NotificationChannel.WEBHOOK, True, 0)
    _stub_channel(s, sink, NotificationChannel.PUSH, False, 0)
    return s, sink


def _deliver_logged(s: NotificationService, a: Any, kw: dict) -> tuple[dict, list]:
    logs: list = []
    env = _Env()
    env.swap("logger", _Logger(logs))
    try:
        r = _run(s.deliver_alert(a, **kw))
    finally:
        env.close()
    return r.to_dict(), logs


def test_deliver_disabled_short_circuit() -> None:
    s, sink = _stubbed_service(notification_enabled=False)
    dd, logs = _deliver_logged(s, _Alert(), {"channels": [NotificationChannel.EMAIL]})
    assert dd == _result_dict(_ALERT_ID, [], True, False)
    assert sink == []
    assert logs == [("info", "Notifications disabled, skipping delivery for alert a-1", ())]


def test_deliver_no_channels_resolved() -> None:
    s, sink = _stubbed_service(smtp_host="", smtp_from_address="", default_webhook_url="")
    dd, logs = _deliver_logged(s, _Alert(), {})
    assert dd == _result_dict(_ALERT_ID, [], True, False)
    assert sink == []
    assert logs == [("info", "No notification channels configured for alert a-1", ())]


def test_deliver_all_successful_logs_and_passthrough() -> None:
    s, sink = _stubbed_service()
    a = _Alert()
    dd, logs = _deliver_logged(
        s,
        a,
        {
            "channels": [NotificationChannel.EMAIL],
            "email_recipients": ["ops@x.com"],
            "webhook_url": "https://hook.test",
        },
    )
    assert dd == _result_dict(_ALERT_ID, [_delivery_dict("email", True)], True, True)
    assert sink == [("email", a, ["ops@x.com"], True)]
    assert logs == [
        ("info", "Delivering alert a-1 via channels: ['email']", ()),
        ("info", "All 1 notifications delivered for alert a-1", ()),
    ]


def test_deliver_mixed_two_failed_of_three() -> None:
    s = _svc()
    sink: list = []
    _stub_channel(s, sink, NotificationChannel.EMAIL, False, 0)
    _stub_channel(s, sink, NotificationChannel.WEBHOOK, True, 0)
    _stub_channel(s, sink, NotificationChannel.PUSH, False, 0)
    a = _Alert()
    dd, logs = _deliver_logged(
        s,
        a,
        {
            "channels": [
                NotificationChannel.EMAIL,
                NotificationChannel.WEBHOOK,
                NotificationChannel.PUSH,
            ],
            "email_recipients": ["ops@x.com"],
            "webhook_url": "https://hook.test",
        },
    )
    assert dd == _result_dict(
        _ALERT_ID,
        [
            _delivery_dict("email", False, err="stub-fail"),
            _delivery_dict("webhook", True),
            _delivery_dict("push", False, err="stub-fail"),
        ],
        False,
        True,
    )
    assert sink == [
        ("email", a, ["ops@x.com"], True),
        ("webhook", a, "https://hook.test", True),
        ("push", a),
    ]
    assert logs == [
        ("info", "Delivering alert a-1 via channels: ['email', 'webhook', 'push']", ()),
        ("warning", "2/3 notifications failed for alert a-1", ()),
    ]


def test_deliver_alert_without_priority_attribute() -> None:
    # getattr default family: False -> None (m28) or True (m34) both leak into
    # the result dict and the dispatch flags; m31 (default deleted = False) is
    # ledger-EQUIVALENT.
    s, sink = _stubbed_service()
    dd, _logs = _deliver_logged(
        s, _Alert(with_priority=False), {"channels": [NotificationChannel.EMAIL]}
    )
    assert dd == _result_dict(_ALERT_ID, [_delivery_dict("email", True)], True, False)
    assert sink[0][3] is False


# ------------------------------------------------------------------ singleton


def test_singleton_identity_and_reset() -> None:
    reset_notification_service()
    try:
        s = _svc()
        svc = get_notification_service(s)
        assert isinstance(svc, NotificationService)
        assert svc.settings is s
        assert get_notification_service(s) is svc
        reset_notification_service()
        s2 = _svc(smtp_host="smtp2.test")
        svc2 = get_notification_service(s2)
        assert svc2 is not svc
        assert svc2.settings is s2
    finally:
        reset_notification_service()
