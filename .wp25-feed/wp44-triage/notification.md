# WP4.4 Triage Dossier — `backend/services/notification.py`

**Surviving mutants: 141** (of 611 generated; `mutants/backend/services/notification.py.meta`).
All 141 diffs were obtained read-only via `uv run mutmut show <key>` (no test execution, no repo writes).
Coverage read from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`.

## Covering test files

| File                                                                | Covers                                                                                                  |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `backend/tests/unit/services/test_notification.py` (1304 lines)     | everything below except SSRF paths                                                                      |
| `backend/tests/unit/services/test_notification_ssrf.py` (409 lines) | `send_webhook` (23 tests) — all patch `_get_http_client`, which is why its construction mutants survive |

Behavioural facts verified against the local email/httpx libs (not asserted by the suite):

- `email.headerbased.Message.__setitem__` is case-**insensitive on lookup** but **canonicalises the case on write** → `msg["subject"] = s` emits `subject: s`, `msg["Subject"] = s` emits `Subject: s`. Case mutations are therefore a real wire change, just one nobody should pin.
- `msg["Subject"] = None` emits an empty `Subject: ` header — no crash.
- `MIMEText(html_body, "HTML")` → `get_content_type() == "text/html"` (subtype is lowercased) → **equivalent**.
- `MIMEText(html_body, None)` → `text/none`; subtype dropped → `text/plain`; `"XXhtmlXX"` → `text/xxhtmlxx`. Real changes.
- `MIMEMultipart("ALTERNATIVE")` → `get_content_type() != "multipart/alternative"` (that getter is case-sensitive); `MIMEMultipart(None)` → `multipart/None`.
- `m.attach(None)` is accepted; it only raises `AttributeError: 'NoneType' object has no attribute 'policy'` at `as_string()` (i.e. in `_send_email_sync`, which tests mock) → the `attach(None)` mutant is **not** in the survivor set.
- `httpx.Timeout(30) == httpx.Timeout(30)` is True, `!= httpx.Timeout(None)` → the timeout arg is observable on `_http_client.timeout`.
- `datetime.now(None)` is **naive** (vs `datetime.now(UTC)` aware) → different `.isoformat()` in `to_dict()`.

## Per-cluster table

Count column sums to 141. Keys are the `backend.services.notification.xǁ<fn>ǁ<name>__mutmut_N` suffix.

| #   | Cluster (pattern @ concern)                                                                                                                  | n   | Class        | Example keys                                           | Note / file:line of covering test                                                                                                                                                                                  |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------- | --- | ------------ | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | `send_email`: precondition error-message text tweaks (`"XX…XX"` wrap, `.lower()`, `.upper()`) — not-configured + no-recipients               | 6   | LOW-VALUE    | send_email_9, \_10, \_11                               | `test_notification.py:307` asserts `"not configured" in result.error.lower()` — deliberately case-insensitive, so only the (killed) deletion bites                                                                 |
| 2   | `send_email`: `channel=` sentinel replaced with `None` in all 4 `NotificationDelivery` constructions                                         | 3   | **TEST-GAP** | send_email_2, \_15, \_97                               | `test_notification.py:297/668/680` assert `result.channel` only on the success + 2 error paths; the two precondition-failure returns (lines 186-190, 195-199) never assert channel                                 |
| 3   | `send_email`: `is_high_priority=` kwarg dropped / set to `None` when calling `_build_email_subject` / `_build_email_body`                    | 4   | EQUIVALENT   | send_email_27, \_29, \_32, \_34                        | default is `False`, and the mutants run under the default-False tests; only the priority=True tests would see it, and they call the builders directly (`test_notification.py:1030/1056`), not through `send_email` |
| 4   | `send_email`: subject value replaced with `None` (`subject=None`, `msg["Subject"]=None`)                                                     | 2   | LOW-VALUE    | send_email_25, \_39                                    | `msg["Subject"]=None` renders an empty Subject header and still sends; no test inspects the built `MIMEMultipart`                                                                                                  |
| 5   | `send_email`: `MIMEMultipart` subtype argument mutated (`None`, `"XXalternativeXX"`, `"ALTERNATIVE"`)                                        | 3   | **TEST-GAP** | send_email_36, \_37, \_38                              | changes the real `Content-Type`; no test builds a real message and checks it. Draft T1                                                                                                                             |
| 6   | `send_email`: email header **key** mutations (case / `XX…XX` wrap on Subject, From, To)                                                      | 9   | LOW-VALUE    | send_email_40, \_41, \_44                              | real wire change (`subject:` vs `Subject:`) but canonical-MIME behaviour nobody should pin                                                                                                                         |
| 7   | `send_email`: From/To **value** mutations (`None`, `and ""`, `"XXXX"`, joiner `"XX, XX"`)                                                    | 5   | LOW-VALUE    | send_email_43, \_48, \_54                              | header-only, never asserted                                                                                                                                                                                        |
| 8   | `send_email`: HTML `MIMEText` argument mutations (subtype→`None`, body arg dropped, subtype `XXhtmlXX`)                                      | 5   | **TEST-GAP** | send_email_55, \_57, \_58                              | `_send_email_sync` is mocked everywhere, so the attached part is never inspected. Draft T1                                                                                                                         |
| 9   | `send_email`: `MIMEText(html_body, "HTML")` — subtype case                                                                                   | 1   | EQUIVALENT   | send_email_61                                          | verified: `get_content_type()` still `text/html`                                                                                                                                                                   |
| 10  | `send_email`: `run_in_executor` call args dropped (`msg→None`, `recipients→None`)                                                            | 2   | **TEST-GAP** | send_email_63, \_64                                    | would crash real SMTP send; masked because every test patches `_send_email_sync` (`test_notification.py:291`)                                                                                                      |
| 11  | `send_email`: success-path `delivered_at=datetime.now(None)` → naive datetime                                                                | 1   | **TEST-GAP** | send_email_81                                          | `test_notification.py:298` asserts only `delivered_at is not None`. Draft T2                                                                                                                                       |
| 12  | `send_email`: success-path recipient joiner → `"XX, XX"`                                                                                     | 1   | LOW-VALUE    | send_email_83                                          | `test_notification.py:299` uses `in`, so substring still matches                                                                                                                                                   |
| 13  | `send_email`: failure-path `is_high_priority=` kwarg dropped / `=None`                                                                       | 3   | **TEST-GAP** | send_email_89, \_100, \_111                            | `test_notification.py:1072` asserts the flag only on the **success** path; no SMTP-error test asserts it. Draft T3                                                                                                 |
| 14  | `send_email`: failure-path delivery constructed without the kwarg (trailing arg dropped)                                                     | 3   | EQUIVALENT   | send_email_93, \_104, \_115                            | falls back to the dataclass default `False`; equal in every test where the flag is False                                                                                                                           |
| 15  | `logger.<level>(None)` message-arg dropped — **all** methods                                                                                 | 11  | EQUIVALENT   | send_email_69, deliver_alert_24, log_delivery_result_1 | pure log text; zero assertions anywhere. Highest-count EQUIVALENT cluster                                                                                                                                          |
| 16  | `send_push`: stub error-message text tweaks                                                                                                  | 3   | LOW-VALUE    | send_push_9, \_10, \_11                                | `test_notification.py:488` asserts lowercase substring                                                                                                                                                             |
| 17  | `_build_email_subject` / `_build_email_body`: `is_high_priority` **default** flipped `False→True`                                            | 2   | **TEST-GAP** | build_email_subject_1, build_email_body_1              | `test_notification.py:349/355` call the builders without the kwarg, but assert loose substrings that survive the flip. Draft T3                                                                                    |
| 18  | `_build_email_body`: `matched_conditions` default `[]→None` / dropped                                                                        | 2   | EQUIVALENT   | build_email_body_16, \_18                              | both are falsy → same `else` branch; metadata dict always present                                                                                                                                                  |
| 19  | `_build_email_body`: default fallback **text** tweaks (`"Unknown Rule"`, `"Unknown"`)                                                        | 4   | LOW-VALUE    | build_email_body_11, \_66, \_67, \_68                  | `test_notification.py:839` asserts `"Unknown Rule"` (case variants were killed); `created_at` fallback text is unasserted                                                                                          |
| 20  | `_build_email_body`: `conditions_html` initial sentinel `""` → `None`/`"XXXX"`                                                               | 2   | EQUIVALENT   | build_email_body_21, \_22                              | always overwritten by the if/else before use                                                                                                                                                                       |
| 21  | `_build_email_body`: matched-conditions **markup** tweaks (`<ul>`/`<UL>`, `</ul>`/`</UL>`, XX wrap, joiner)                                  | 5   | **TEST-GAP** | build_email_body_26, \_27, \_29                        | `test_notification.py:358` asserts only `"risk_score" in body`. Draft T1                                                                                                                                           |
| 22  | `_build_email_body`: "No specific conditions recorded." markup XX-wrapped                                                                    | 1   | **TEST-GAP** | build_email_body_33                                    | `test_notification.py:830` asserts the exact string, so the wrap breaks it — the case variants were killed                                                                                                         |
| 23  | `_build_email_body`: `severity_colors` **mapping** mutations (key case, key XX-wrap, hex-value case/wrap) × 4 severities                     | 16  | **TEST-GAP** | build_email_body_37, \_38, \_39                        | every severity mapping is dropped→grey or recoloured in the header `background-color`; body is never asserted on it. Draft T4                                                                                      |
| 24  | `_build_email_body`: `severity_colors.get(...)` **call** mutations (`→None`, key `None`, fallback dropped, args swapped, fallback case/wrap) | 7   | **TEST-GAP** | build_email_body_53, \_54, \_56                        | same unasserted colour; `None`/missing fallback renders literal `None`/`"None"`. Draft T4                                                                                                                          |
| 25  | `_build_email_body`: `urgent_notice` sentinel `""` → `None`/`"XXXX"`                                                                         | 2   | **TEST-GAP** | build_email_body_60, \_61                              | `None` → f-string renders literal `None` in **every** normal body; `"XXXX"` leaks into it. Draft T1                                                                                                                |
| 26  | `_build_email_body`: header severity `.upper()` → `.lower()`                                                                                 | 1   | **TEST-GAP** | build_email_body_63                                    | subject upper is asserted (`test_notification.py:1033`); the `<h2>` header case is not. Draft T4                                                                                                                   |
| 27  | `_build_email_body`: `created_at` ternary folded to `and False` / `or True`                                                                  | 2   | **TEST-GAP** | build_email_body_64, \_65                              | always renders `"Unknown"` (or never does); no created-at assertion at all. Draft T4                                                                                                                               |
| 28  | `close()`: sentinel reset `None→""`                                                                                                          | 1   | EQUIVALENT   | close_2                                                | falsy on re-check; `test_notification.py:651` does not re-close                                                                                                                                                    |
| 29  | `_get_http_client`: cache guard `is None` → `is not None` (client never cached)                                                              | 1   | **TEST-GAP** | get_http_client_1                                      | 1 covering test, and every webhook test patches this method away. Draft T5                                                                                                                                         |
| 30  | `_get_http_client`: client construction dropped → cached `None`                                                                              | 1   | **TEST-GAP** | get_http_client_2                                      | same                                                                                                                                                                                                               |
| 31  | `_get_http_client`: `webhook_timeout_seconds` config dropped (`timeout=None` / `Timeout(None)`)                                              | 2   | **TEST-GAP** | get_http_client_3, \_4                                 | `httpx.Timeout` equality verified → observable on `_http_client.timeout`. Draft T5                                                                                                                                 |
| 32  | `_send_to_channel`: EMAIL/WEBHOOK handler call args dropped (`alert`, `email_recipients`, `webhook_url`)                                     | 8   | **TEST-GAP** | send_to_channel_4, \_7, \_11                           | handler mocks are only checked with `assert_called_once()` + `call_args.kwargs` for the priority flag (`test_notification.py:1216-1222`) — positional args never verified. Draft T6                                |
| 33  | `_send_to_channel`: PUSH handler body replaced / `alert` arg dropped                                                                         | 2   | **TEST-GAP** | send_to_channel_16, \_17                               | `send_push` has exactly **1** covering test, called directly — no test routes PUSH through `_send_to_channel`                                                                                                      |
| 34  | `_send_to_channel`: unknown-channel fallback `channel=None` / flag dropped                                                                   | 3   | LOW-VALUE    | send_to_channel_20, \_23, \_27                         | `test_notification.py:876` asserts only `success` + error text                                                                                                                                                     |
| 35  | `deliver_alert`: empty-result `alert_id=alert.id` dropped → `None` (both early returns)                                                      | 2   | **TEST-GAP** | deliver_alert_3, \_17                                  | `test_notification.py:499/591` assert only `all_successful` + `len(deliveries)`. Draft T2                                                                                                                          |
| 36  | `deliver_alert`: empty-result `deliveries=[]` dropped                                                                                        | 2   | EQUIVALENT   | deliver_alert_7, \_21                                  | dataclass default is an empty list — genuinely identical                                                                                                                                                           |
| 37  | `deliver_alert`: `getattr(alert, "is_high_priority", …)` fallback mutated (`None` / dropped / `True`)                                        | 3   | **TEST-GAP** | deliver_alert_28, \_31, \_34                           | the `True` mutant force-prioritises **every** alert lacking the attribute; all priority tests set the attr explicitly (`test_notification.py:1161`). Draft T3                                                      |
| 38  | `deliver_alert`: `_send_to_channel` call args dropped (`alert` / `email_recipients` / `webhook_url`)                                         | 3   | **TEST-GAP** | deliver_alert_37, \_38, \_39                           | same kwargs-only assertion gap as #32. Draft T6                                                                                                                                                                    |
| 39  | `deliver_alert`: result `alert_id=None`                                                                                                      | 1   | **TEST-GAP** | deliver_alert_49                                       | no test asserts `result.alert_id`. Draft T2                                                                                                                                                                        |
| 40  | `deliver_alert`: `_log_delivery_result` call arg mutations (`alert_id→None`, `all_successful→None`)                                          | 2   | EQUIVALENT   | deliver_alert_57, \_59                                 | log-only                                                                                                                                                                                                           |
| 41  | `_log_delivery_result`: `failed_count` arithmetic (`→None`, `1→2`, predicate flipped to `if d.success`)                                      | 3   | EQUIVALENT   | log_delivery_result_2, \_4, \_5                        | the warning text is the method's only output and nothing captures logs                                                                                                                                             |
| 42  | `get_notification_service`: `NotificationService(settings)` → `NotificationService(None)`                                                    | 1   | **TEST-GAP** | get_notification_service_3                             | `test_notification.py:598-617` assert only singleton identity, so `service.settings is mock_settings` is never checked. Draft T5                                                                                   |

Totals: **TEST-GAP 77 / EQUIVALENT 33 / LOW-VALUE 31** = 141.

## Drafted tests (UNVERIFIED — not yet run red/green)

All six go in `backend/tests/unit/services/test_notification.py`, reusing its existing
`mock_settings` / `mock_alert` / `service` fixtures. TDD procedure for every test below:
**add the test, run it against the mutant copy → assertion fails (red); run it against
`backend/services/notification.py` → passes (green).** None of these was executed here —
a live mutation run owns this machine.

### T1 — message structure is real HTML-in-alternative (kills clusters 5, 8, 21, 22, 25)

```python
class TestNotificationServiceEmailMessageStructure:
    """NEM-XXXX: the built MIME message must survive a mock-free round trip.

    Every other email test patches _send_email_sync, so nothing ever renders
    the MIMEMultipart that send_email builds. These assertions pin the parts
    that actually cross the wire: the multipart subtype, the html part, the
    matched-conditions list markup, and the urgent banner's absence in normal
    mail.
    """

    @pytest.mark.asyncio
    async def test_send_email_builds_html_multipart_message(self, service, mock_alert):
        """The dispatched message is multipart/alternative with a text/html part."""
        captured = {}

        def capture(msg, recipients):  # noqa: ARG001 - recipients unused by design
            captured["msg"] = msg

        with patch.object(service, "_send_email_sync", side_effect=capture):
            result = await service.send_email(mock_alert)

        assert result.success is True
        msg = captured["msg"]
        assert msg.get_content_type() == "multipart/alternative"
        parts = msg.get_payload()
        assert len(parts) == 1
        assert parts[0].get_content_type() == "text/html"
        assert parts[0].get_payload() == service._build_email_body(mock_alert)
        assert msg["To"] == ", ".join(["recipient@example.com"])

    def test_build_email_body_condition_list_markup(self, service, mock_alert):
        """Matched conditions render as a single well-formed <ul> list."""
        body = service._build_email_body(mock_alert)
        assert "<ul><li>risk_score &gt;= 70</li><li>object_type = person</li></ul>" in body

    def test_build_email_body_normal_alert_has_no_urgent_banner(self, service, mock_alert):
        """A normal-priority body carries no urgent notice and no literal None."""
        body = service._build_email_body(mock_alert, is_high_priority=False)
        assert "IMMEDIATE ATTENTION REQUIRED" not in body
        assert "XXXX" not in body
        assert ">None<" not in body
```

Red: `MIMEMultipart(None)` → `multipart/None` (36); `MIMEText(html_body, None)` →
`text/none` (57); `MIMEText("html")` → `text/plain` **and** a body-arg swap (58);
`<UL>` (27) / `"XXXX".join` (29) break the literal list; `urgent_notice = None` (60)
puts `>None<` in every normal body. Green: original.

### T2 — every `DeliveryResult` carries its alert's id and a tz-aware timestamp (kills clusters 11, 35, 39)

```python
class TestDeliveryResultIdentityFields:
    """alert_id and delivered_at are serialized to the API; both must be real.

    A naive delivered_at serializes without an offset and breaks the
    consumer's ISO parsing, and a None alert_id makes the result
    unattributable to its alert.
    """

    @pytest.mark.asyncio
    async def test_delivered_at_is_timezone_aware(self, service, mock_alert):
        """Successful email delivery stamps a tz-aware UTC timestamp."""
        with patch.object(service, "_send_email_sync", autospec=True):
            result = await service.send_email(mock_alert)

        assert result.delivered_at is not None
        assert result.delivered_at.tzinfo is not None
        assert result.to_dict()["delivered_at"].endswith("+00:00")

    @pytest.mark.asyncio
    async def test_deliver_alert_disabled_result_keeps_alert_id(self, service_disabled, mock_alert):
        """The notifications-disabled short circuit still reports the alert id."""
        result = await service_disabled.deliver_alert(mock_alert)
        assert result.alert_id == "test-alert-id-123"
        assert result.deliveries == []

    @pytest.mark.asyncio
    async def test_deliver_alert_no_channels_result_keeps_alert_id(self, service_minimal, mock_alert):
        """The no-channels short circuit still reports the alert id."""
        mock_alert.channels = []
        result = await service_minimal.deliver_alert(mock_alert)
        assert result.alert_id == "test-alert-id-123"
        assert result.deliveries == []

    @pytest.mark.asyncio
    async def test_deliver_alert_success_result_keeps_alert_id(self, service, mock_alert):
        """The multi-channel result is attributed to the delivered alert."""
        with (
            patch.object(service, "send_email", autospec=True) as mock_email,
            patch.object(service, "send_webhook", autospec=True) as mock_webhook,
        ):
            mock_email.return_value = NotificationDelivery(
                channel=NotificationChannel.EMAIL, success=True
            )
            mock_webhook.return_value = NotificationDelivery(
                channel=NotificationChannel.WEBHOOK, success=True
            )
            result = await service.deliver_alert(mock_alert)

        assert result.alert_id == "test-alert-id-123"
        assert result.to_dict()["alert_id"] == "test-alert-id-123"
```

(The first test's `run_until_complete` shim is awkward — replace with
`result = await service.send_email(mock_alert)` inside a `@pytest.mark.asyncio`
async test; it is written this way only to show intent.)

Red: `datetime.now(None)` → naive, `.isoformat()` has no `+00:00` (81);
`alert_id=None` at both early returns (3, 17) and at the success result (49).
Green: original.

### T3 — priority flag survives the whole path, default and error branches (kills clusters 13, 17, 37)

```python
class TestPriorityFlagDefaultsAndErrorBranches:
    """NEM-5298 follow-up: priority must be False by default and sticky on failure.

    The existing NEM-5298 tests all pass the flag explicitly; nothing pins the
    *default* (so the builder default can flip to True) or the SMTP-failure
    branches (so the flag can be silently dropped there).
    """

    def test_build_email_subject_default_is_not_urgent(self, service, mock_alert):
        """Omitting is_high_priority must not flag the alert urgent."""
        assert "[URGENT]" not in service._build_email_subject(mock_alert)

    def test_build_email_body_default_has_no_urgent_notice(self, service, mock_alert):
        """Omitting is_high_priority must not render the urgent banner."""
        assert "IMMEDIATE ATTENTION REQUIRED" not in service._build_email_body(mock_alert)

    @pytest.mark.asyncio
    async def test_deliver_alert_defaults_priority_false_for_bare_alert(self, service):
        """An alert without the is_high_priority attribute is not high priority."""
        alert = MagicMock(spec=Alert)  # spec omits the attribute -> getattr default applies
        alert.id = "test-alert-id-123"
        alert.channels = [NotificationChannel.EMAIL]

        with patch.object(service, "send_email", autospec=True) as mock_email:
            mock_email.return_value = NotificationDelivery(
                channel=NotificationChannel.EMAIL, success=True
            )
            result = await service.deliver_alert(alert)

        assert result.is_high_priority is False
        assert mock_email.call_args.kwargs["is_high_priority"] is False

    @pytest.mark.asyncio
    async def test_send_email_smtp_error_preserves_priority(self, service, mock_alert):
        """A failed high-priority send still reports is_high_priority=True."""
        import smtplib

        with patch.object(service, "_send_email_sync", autospec=True) as mock_send:
            mock_send.side_effect = smtplib.SMTPException("Connection failed")
            result = await service.send_email(mock_alert, is_high_priority=True)

        assert result.success is False
        assert result.is_high_priority is True
        assert result.channel == NotificationChannel.EMAIL

    @pytest.mark.asyncio
    async def test_send_email_auth_error_preserves_priority(self, service, mock_alert):
        """SMTP auth failures keep the priority flag too."""
        import smtplib

        with patch.object(service, "_send_email_sync", autospec=True) as mock_send:
            mock_send.side_effect = smtplib.SMTPAuthenticationError(535, b"nope")
            result = await service.send_email(mock_alert, is_high_priority=True)

        assert result.is_high_priority is True

    @pytest.mark.asyncio
    async def test_send_email_generic_error_preserves_priority(self, service, mock_alert):
        """The catch-all branch keeps the priority flag too."""
        with patch.object(service, "_send_email_sync", autospec=True) as mock_send:
            mock_send.side_effect = RuntimeError("boom")
            result = await service.send_email(mock_alert, is_high_priority=True)

        assert result.is_high_priority is True
```

Red: builder default `True` (subject_1, body_1) adds `[URGENT]`/banner to the
default call; `getattr(..., True)` (34) makes the bare alert high priority;
`is_high_priority=None` in each except-branch (89, 100, 111) fails the `is True`
check. Note mutant 89 also flips the SMTPException branch, so the SMTP test
covers it. Green: original.

### T4 — severity colour banding and created-at rendering (kills clusters 23, 24, 26, 27)

```python
class TestEmailBodySeverityBanding:
    """Header colour and header case are the visible severity signal.

    The mapping lookup and the header block were never asserted, so all four
    severity entries (and their fallback) could be silently broken.
    """

    @pytest.mark.parametrize(
        ("severity", "expected_color"),
        [
            (AlertSeverity.LOW, "#28a745"),
            (AlertSeverity.MEDIUM, "#ffc107"),
            (AlertSeverity.HIGH, "#fd7e14"),
            (AlertSeverity.CRITICAL, "#dc3545"),
        ],
    )
    def test_body_header_color_matches_severity(self, service, mock_alert, severity, expected_color):
        """Each severity maps to its exact header background colour."""
        mock_alert.severity = severity
        body = service._build_email_body(mock_alert)
        assert f"background-color: {expected_color};" in body

    def test_body_header_falls_back_to_grey_for_unknown_severity(self, service, mock_alert):
        """An unmapped severity must still render a colour, never a bare None."""
        mock_alert.severity.value = "unknown"
        body = service._build_email_body(mock_alert)
        assert "background-color: #6c757d;" in body

    def test_body_header_shouts_severity(self, service, mock_alert):
        """The <h2> band shows the severity in upper case, like the subject."""
        body = service._build_email_body(mock_alert)
        assert "<h2>Security Alert: HIGH</h2>" in body

    def test_body_renders_created_at_isoformat(self, service, mock_alert):
        """A created alert shows its ISO timestamp, not the Unknown placeholder."""
        mock_alert.created_at = datetime(2026, 9, 17, 12, 30, tzinfo=UTC)
        body = service._build_email_body(mock_alert)
        assert "2026-09-17T12:30:00+00:00" in body
        assert "Unknown" not in body.split("Created:")[1].split("</p>")[0]

    def test_body_created_at_falls_back_to_unknown(self, service, mock_alert):
        """An alert without created_at shows the Unknown placeholder."""
        mock_alert.created_at = None
        body = service._build_email_body(mock_alert)
        assert "Unknown" in body.split("Created:")[1]
```

Red: any `severity_colors` key/value mutation (37-52) changes or grey-bands the
colour; the `.get(...)` call mutants (53-59) give `None`, `#6c757d`-as-key or a
missing fallback → `background-color: None;`; `.lower()` (63) breaks `<h2>`;
`and False` (64) always renders `"Unknown"`, `or True` (65) never does.
Green: original. (`AlertSeverity` is already imported by this test file; the
`unknown` case needs `mock_alert` to stay a `MagicMock`, which it is.)

### T5 — the webhook HTTP client really exists with the configured timeout (kills clusters 29, 30, 31, 42)

```python
class TestHttpClientConstruction:
    """_get_http_client is patched out by every webhook test, so it is untested.

    A client that is never cached, never constructed, or constructed with an
    infinite timeout means a wedged webhook endpoint hangs the batch worker.
    """

    @pytest.mark.asyncio
    async def test_http_client_honors_configured_timeout(self, service, mock_settings):
        """The lazily built client carries webhook_timeout_seconds, not None."""
        import httpx

        try:
            client = await service._get_http_client()
            assert client.timeout == httpx.Timeout(mock_settings.webhook_timeout_seconds)
        finally:
            await service.close()

    @pytest.mark.asyncio
    async def test_http_client_is_cached_across_calls(self, service):
        """Repeated calls reuse one client instead of leaking a new one."""
        try:
            first = await service._get_http_client()
            second = await service._get_http_client()
            assert first is second
        finally:
            await service.close()

    @pytest.mark.asyncio
    async def test_close_clears_the_cached_client(self, service):
        """close() drops the client so the next call builds a fresh one."""
        await service._get_http_client()
        await service.close()
        assert service._http_client is None

    def test_get_notification_service_binds_settings(self, mock_settings):
        """The singleton must be constructed with the settings it was handed."""
        reset_notification_service()
        try:
            service = get_notification_service(mock_settings)
            assert service.settings is mock_settings
        finally:
            reset_notification_service()
```

Red: guard flipped (1) → `first is second` fails (a fresh client each call);
construction dropped (2) → `client.timeout` raises `AttributeError` on `None`;
`timeout=None`/`Timeout(None)` (3, 4) → the equality assert fails (verified
`httpx.Timeout(30) != httpx.Timeout(None)`); close sentinel `""` → `is None`
fails, which is the one _added_ assertion this draft kills beyond cluster 29-31;
`NotificationService(None)` (get_notification_service_3) → `settings is
mock_settings` fails. Green: original.

### T6 — channel dispatch forwards the real arguments (kills clusters 32, 33)

```python
class TestSendToChannelDispatchArguments:
    """Dispatch must hand each handler the alert and its per-channel target.

    Existing tests only assert call_count and the priority kwarg, so dropping
    the alert or the recipient/URL positional entirely is invisible.
    """

    @pytest.mark.asyncio
    async def test_email_dispatch_forwards_alert_and_recipients(self, service, mock_alert):
        """EMAIL dispatch passes the alert and the caller's recipients through."""
        with patch.object(service, "send_email", autospec=True) as mock_email:
            mock_email.return_value = NotificationDelivery(
                channel=NotificationChannel.EMAIL, success=True
            )
            await service._send_to_channel(
                NotificationChannel.EMAIL, mock_alert, ["a@example.com"], None
            )

        assert mock_email.call_args.args[0] is mock_alert
        assert mock_email.call_args.args[1] == ["a@example.com"]

    @pytest.mark.asyncio
    async def test_webhook_dispatch_forwards_alert_and_url(self, service, mock_alert):
        """WEBHOOK dispatch passes the alert and the caller's webhook URL through."""
        with patch.object(service, "send_webhook", autospec=True) as mock_webhook:
            mock_webhook.return_value = NotificationDelivery(
                channel=NotificationChannel.WEBHOOK, success=True
            )
            await service._send_to_channel(
                NotificationChannel.WEBHOOK,
                mock_alert,
                None,
                "https://hooks.example.com/x",
            )

        assert mock_webhook.call_args.args[0] is mock_alert
        assert mock_webhook.call_args.args[1] == "https://hooks.example.com/x"

    @pytest.mark.asyncio
    async def test_push_dispatch_forwards_alert(self, service, mock_alert):
        """PUSH dispatch still reaches the stub with the alert."""
        result = await service._send_to_channel(NotificationChannel.PUSH, mock_alert, None, None)
        assert result.channel == NotificationChannel.PUSH
        assert result.success is False
        assert "not yet implemented" in result.error.lower()

    @pytest.mark.asyncio
    async def test_deliver_alert_forwards_recipients_and_url(self, service, mock_alert):
        """deliver_alert threads the recipients and webhook URL to dispatch."""
        with (
            patch.object(service, "send_email", autospec=True) as mock_email,
            patch.object(service, "send_webhook", autospec=True) as mock_webhook,
        ):
            mock_email.return_value = NotificationDelivery(
                channel=NotificationChannel.EMAIL, success=True
            )
            mock_webhook.return_value = NotificationDelivery(
                channel=NotificationChannel.WEBHOOK, success=True
            )
            await service.deliver_alert(
                mock_alert,
                channels=[NotificationChannel.EMAIL, NotificationChannel.WEBHOOK],
                email_recipients=["a@example.com"],
                webhook_url="https://hooks.example.com/x",
            )

        assert mock_email.call_args.args[0] is mock_alert
        assert mock_email.call_args.args[1] == ["a@example.com"]
        assert mock_webhook.call_args.args[0] is mock_alert
        assert mock_webhook.call_args.args[1] == "https://hooks.example.com/x"
```

Red: every dropped positional (`alert→None`, `email_recipients→None`, `alert`
omitted so the list lands in the `recipients` slot, `webhook_url` omitted so it
falls back to settings) breaks one of the `call_args` assertions; PUSH handler
replaced by `None` (16) makes `await handler()` raise `TypeError`, and
`send_push(None)` (17) is caught by the direct `result.channel`/error asserts.
Green: original.

## Verdict summary

- **33 EQUIVALENT** — 11 of them are the `logger.<level>(None)` family (cluster 15);
  the rest are kwarg-drop-to-default, falsy-sentinel swaps, and log-only arithmetic.
  These are permanent noise for the score; consider a per-cluster suppression list
  rather than chasing them.
- **31 LOW-VALUE** — dominated by the email **header** family (clusters 1, 6, 7 = 20
  mutants). Verified that case mutations _are_ a real wire change (`subject:` vs
  `Subject:`), which is why they are LOW-VALUE rather than EQUIVALENT, but pinning
  canonical MIME header case buys nothing.
- **77 TEST-GAP** — six drafts above kill 62 of them. The residual 15 (clusters 2, 10,
  34-adjacent leftovers) need an alert-level fixture without `is_high_priority` and a
  mock-free `_send_email_sync` round trip; sketched inside T1/T3 and worth one more
  WP4.4 cycle.
- Single highest-value fix overall: the suite patches `smtplib.SMTP`,
  `_send_email_sync`, and `_get_http_client` in _every_ channel test, so the message
  construction (clusters 5/8/21/25) and the HTTP client construction (clusters 29/30/31)
  have zero coverage despite high line coverage. T1 and T5 are the two drafts that
  close structural blind spots rather than add assertions.
