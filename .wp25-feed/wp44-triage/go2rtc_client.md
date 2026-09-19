# WP4.4 Triage Dossier — backend/services/go2rtc_client.py

**Source file:** `backend/services/go2rtc_client.py` (205 lines: `__init__`, `health_check`, `register_stream`, `unregister_stream`, `_validate_rtsp_url`)
**Meta:** `mutants/backend/services/go2rtc_client.py.meta` — 101 keys total, 40 survivors (exit_code 0), 0 unchecked.
**Sole covering test file:** `backend/tests/unit/services/test_go2rtc_client.py` (553 lines). All functions' `tests_by_mangled_function_name` entries point only there.
**Raw diffs:** `/tmp/wp25/wp44-triage/go2rtc_diffs.txt` (dumped via `mutmut show`, all 40 succeeded).

Key prefix `backend.services.go2rtc_client.xǁGo2RTCClientǁ` abbreviated as `…` below.

## Why tests let so much through — structural diagnosis of the covering file

The file's register/unregister tests mock `httpx.AsyncClient.post/delete` with `autospec=True` but **never assert the request URL** (only `mock_post.call_args.kwargs["json"]`, lines 186-188, 247-252, 282-284; unregister only checks `stream_id in str(call_args)`, line 407) and **never assert `timeout`** for post/delete (health_check does, line 86 — which is why health's timeout mutants died and register/unregister's survived). Mocked responses **always contain `stream_id` and `url`**, so the `data.get(..., fallback)` branches on lines 137-138 never execute their fallbacks. `caplog` is used only negatively (`password not in log_text`, line 515) — never to assert a warning *was* emitted with *which* args, so every warning-path mutation is invisible. Validation tests exercise only the scheme branch of `_validate_rtsp_url`; the whitespace regex (line 187) and host check (line 201) have no positive-test coverage.

## Verified mutant semantics (checked read-only against CPython 3.14)

- `urlparse(None)` does **not** raise; returns `ParseResultBytes` with `b''` fields → mutated `source_url` becomes `"b''://admin:test_password@b''b''"`, which still *contains* `admin:test_password`, so the substring assertion at line 250 passes → genuine survivor.
- `token_hex(None)` → 64 hex chars; `token_hex(7)` → 14; original → 12. Not observable through the mocked response, but *is* observable via the fallback path if a test ever asserts suffix format.
- `"http://h/testX/".rstrip("XX/XX")` → `"http://h/test"` and `.rstrip(None)` → unchanged (trailing `/` is not whitespace) and `.lstrip("/")` → unchanged — all differ from `rstrip("/")` → all `__init__` mutants observable via a plain attribute assertion.
- `re.search(r"XX\sXX", " rtsp://…")` → `None` (mutant disables the space guard); `urlparse` tolerates spaces, so with the guard broken the URL sails through validation into the POST.
- `urlparse("rtsp://:554/p")` → `netloc=":554"`, `hostname=None` → the `or`→`and` mutant of line 201 wrongly **accepts** it (netloc truthy makes `not netloc and not hostname` False), while original rejects.

## Cluster table (40 survivors, counts sum exactly)

| # | Pattern | Keys | n | Class | Covering test (file:line) | Note |
|---|---------|------|---|-------|---------------------------|------|
| C1 | `__init__`: URL normalization `rstrip("/")` → None / `rstrip(None)` / `lstrip("/")` / `rstrip("XX/XX")` on both api_url and webrtc_url | `…__init____mutmut_1…8` (1,2,3,4,5,6,7,8) | 8 | **TEST-GAP** | no test ever reads `client.api_url` / `client.webrtc_url` (fixture lines 33-37 constructs but never asserts attributes) | All 8 observable with one attribute assertion on input `"http://h/testX/"` (see T1); `rstrip(None)` members (2,6) need the `/`-terminated case only (trailing `/` is not stripped by `rstrip(None)`). |
| C2 | register/unregister HTTP call: request URL → `None`, and `timeout=self.timeout` → `None` or kwarg dropped | `…register_stream__mutmut_23,25,28`, `…unregister_stream__mutmut_3,5` | 6 | **TEST-GAP** | test_go2rtc_client.py lines 181-188 (post kwargs checked, URL never), 404-407 (delete: only `stream_id in str(call_args)`); docstring lines 157-159 / 391 state the endpoints as expected behavior | Autospec mocks swallow the bogus URL/timeout. The endpoint path is the documented API contract. |
| C3 | `register_stream` response-map: `data.get("stream_id"/"url", <fallback>)` default → `None` or removed (2-arg→1-arg `.get`) | `…register_stream__mutmut_37,39,45,47` | 4 | **TEST-GAP** | lines 175-176, 215-217 assert the fields but every mock response *supplies* `stream_id`+`url` — fallback branch (source lines 137-138) never executes | Fallback is real behavior: client-generated stream id + `webrtc_url` template must be well-formed when go2rtc omits fields. |
| C4 | `unregister_stream` acceptable-status whitelist: `not in`→`in`; 200→201; 204→205; 404→405 | `…unregister_stream__mutmut_6,7,8,9` | 4 | **TEST-GAP** | lines 385-429 exercise 200/404 but never assert the warning (or its absence); the HTTP-warning branch is entirely unobserved | Kill needs warning-emitted on 500 AND no-warning on both 200 and 204. |
| C5 | `unregister_stream` ConnectError-warning logger args → `None` (stream_id / exception) | `…unregister_stream__mutmut_11,12` | 2 | LOW-VALUE | lines 432-449 assert only "does not raise"; log content never checked (caplog used negatively at 515) | Real change (diagnostics lose the stream id) but debug-log arg fidelity is not spec'd; T4's stream_id-in-warning assert kills 11 as a side effect. |
| C6 | `unregister_stream` ConnectError-warning message text (`XX…XX` wrap / lowercased) | `…unregister_stream__mutmut_16,17` | 2 | EQUIVALENT | same | Pure log-message text; nothing asserts warning text. |
| C7 | `register_stream` debug-log message text (`XX…XX` wrap / lowercased) | `…register_stream__mutmut_19,20` | 2 | EQUIVALENT | test_register_stream_password_not_logged (486-519) only asserts password absence | Pure log text. |
| C8 | `register_stream` debug-log logger args → `None` (camera_id / stream_id) | `…register_stream__mutmut_14,15` | 2 | LOW-VALUE | same | Debug-log arg fidelity; nobody should assert debug log contents. |
| C9 | stream-id suffix length: `token_hex(6)`→`token_hex(7)` / `token_hex(None)` | `…register_stream__mutmut_10,11` | 2 | LOW-VALUE | test at 354-379 asserts prefix only | Uniqueness/prefix behavior unchanged; suffix *length* is not a spec. T3's 12-hex suffix assert would kill them incidentally. |
| C10 | stream-id suffix → `None` (stream_id becomes `camera_front_door_None`) | `…register_stream__mutmut_9` | 1 | LOW-VALUE | test at 354-379 passes because response echoes its own `stream_id`; the generated id only leaks via mock POST `name` key (unchecked) | Degraded uniqueness but only observable incidentally; T3 kills it via fallback format assert. |
| C11 | POST payload key casing: `"name"` → `"XXnameXX"` / `"NAME"` | `…register_stream__mutmut_29,30` | 2 | EQUIVALENT | tests read `json["source"]` only (186-188, 247-252) | go2rtc's actual wire contract was not asserted; classified EQUIVALENT per baseline rule (payload key casing tweaks). If a contract test is ever wanted, assert `set(json) == {"name","source"}`. |
| C12 | `register_stream` credential gate `username and password` → `username or password` | `…register_stream__mutmut_5` | 1 | **TEST-GAP** | test_register_stream_no_credentials (255-284) passes *neither* credential — no single-credential case exists | Real behavior change: username-only sends malformed `rtsp://admin:None@host…` auth header. |
| C13 | `register_stream` `parsed = urlparse(rtsp_url)` → `urlparse(None)` | `…register_stream__mutmut_7` | 1 | **TEST-GAP** | credential tests use substring `in` asserts (249-252) — mutant source `b''://admin:test_password@b''b''` still passes them | Verified semantics above. Killable only by exact source equality. |
| C14 | `_validate_rtsp_url` space regex `r"\s"` → `r"XX\sXX"` (guard disabled) | `…_validate_rtsp_url__mutmut_5` | 1 | **TEST-GAP** | test_register_stream_invalid_rtsp_url (335-350) tests only the wrong-scheme branch; spaced URL never fed | With guard disabled, spaced URLs sail past validation (urlparse tolerates spaces — verified). |
| C15 | `_validate_rtsp_url` host check `not netloc or not hostname` → `…and…` | `…_validate_rtsp_url__mutmut_11` | 1 | **TEST-GAP** | no test for host-less URL; verified `rtsp://:554/p` (netloc=`:554`, hostname=None) is accepted by mutant, rejected by original | |
| C16 | `health_check` request URL → `None` (docstring of test says "GET request to /api/ endpoint") | `…health_check__mutmut_2` | 1 | **TEST-GAP** | test_health_check_success (66-86) asserts timeout kwarg (line 86) but not the URL positional arg | Same root cause as C2; the endpoint is stated in the test's own docstring (line 71). |

**Classification totals: TEST-GAP 27 / LOW-VALUE 7 / EQUIVALENT 6 = 40.**

## Drafted tests (target: `backend/tests/unit/services/test_go2rtc_client.py`)

All six are **UNVERIFIED — not yet run red/green** (per constraint, no test execution in this run). TDD procedure for each: apply the mutant copy over the module (or `mutmut run` on those keys), run the new test — it must FAIL (red) on each cluster mutant; run against original — must PASS (green).

### T1 — kills C1 (8 mutants)

```python
def test_client_strips_trailing_slash_from_urls():
    """UNVERIFIED - not yet run red/green.
    Attribute-level coverage of __init__ URL normalization; kills
    rstrip->None/None-attr, rstrip(None), lstrip("/"), rstrip("XX/XX") mutants."""
    client = Go2RTCClient(api_url="http://localhost:1984/", webrtc_url="http://localhost:8555/")
    assert client.api_url == "http://localhost:1984"
    assert client.webrtc_url == "http://localhost:8555"

    # The decisive case: trailing slash must go, but 'X' must not be
    # stripped (kills rstrip("XX/XX")), a leading-slash-free string must be
    # left otherwise intact (kills lstrip("/")), and rstrip(None) keeps the
    # trailing "/" (kills rstrip(None)).
    client2 = Go2RTCClient(api_url="http://h/testX/", webrtc_url="http://h/testX/")
    assert client2.api_url == "http://h/testX"
    assert client2.webrtc_url == "http://h/testX"
```

### T2 — kills C2 + C16 (7 mutants)

```python
@pytest.mark.asyncio
async def test_requests_use_configured_urls_and_timeout(go2rtc_client):
    """UNVERIFIED - not yet run red/green.
    Mirrors the timeout assert already made for health_check (line 86)
    onto register/unregister, and asserts the documented endpoint URLs."""
    with patch("httpx.AsyncClient.get", autospec=True) as mock_get:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        await go2rtc_client.health_check()
        assert mock_get.call_args.args[1] == "http://localhost:1984/api/"
        assert mock_get.call_args.kwargs["timeout"] == 2.0

    with patch("httpx.AsyncClient.post", autospec=True) as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"stream_id": "s", "url": "http://u"}
        mock_post.return_value = mock_response
        await go2rtc_client.register_stream(
            camera_id="front_door",
            rtsp_url="rtsp://192.168.1.100:554/stream1",
        )
        assert mock_post.call_args.args[1] == "http://localhost:1984/api/streams"
        assert mock_post.call_args.kwargs["timeout"] == 2.0

    with patch("httpx.AsyncClient.delete", autospec=True) as mock_delete:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_delete.return_value = mock_response
        await go2rtc_client.unregister_stream("camera_test_1")
        assert mock_delete.call_args.args[1] == "http://localhost:1984/api/streams/camera_test_1"
        assert mock_delete.call_args.kwargs["timeout"] == 2.0
```

(URL is positional at the call sites, so under `autospec` it is `call_args.args[1]`; the timeout-dropped mutants die on `KeyError: 'timeout'`.)

### T3 — kills C3 (4 mutants; incidentally C9+C10)

```python
@pytest.mark.asyncio
async def test_register_stream_falls_back_to_generated_stream_id(go2rtc_client, sample_camera_config):
    """UNVERIFIED - not yet run red/green.
    Exercises the fallback branch (response omits stream_id/url) that every
    existing mock bypasses; asserts fallback values are well-formed strings."""
    with patch("httpx.AsyncClient.post", autospec=True) as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # go2rtc echoed nothing
        mock_post.return_value = mock_response

        result = await go2rtc_client.register_stream(
            camera_id=sample_camera_config["camera_id"],
            rtsp_url=sample_camera_config["rtsp_url"],
        )

        stream_id = result["stream_id"]
        assert isinstance(stream_id, str)
        assert stream_id.startswith("camera_front_door_")
        suffix = stream_id[len("camera_front_door_") :]
        assert len(suffix) == 12  # secrets.token_hex(6)
        int(suffix, 16)  # suffix is hex
        assert result["webrtc_url"] == f"http://localhost:8555/api/ws?src={stream_id}"
```

### T4 — kills C4 (4 mutants; incidentally C5's mutmut_11)

```python
@pytest.mark.asyncio
async def test_unregister_stream_warning_log_matches_status_whitelist(go2rtc_client, caplog):
    """UNVERIFIED - not yet run red/green.
    Pins the (200, 204, 404) acceptance whitelist via warning presence —
    currently no test asserts the warning branch at all."""
    stream_id = "camera_test_12345"
    with patch("httpx.AsyncClient.delete", autospec=True) as mock_delete:
        mock_response = MagicMock(spec=httpx.Response)
        mock_delete.return_value = mock_response

        with caplog.at_level("WARNING"):
            # Error status: must warn, naming the stream
            mock_response.status_code = 500
            await go2rtc_client.unregister_stream(stream_id)
            assert "Failed to unregister stream" in caplog.text
            assert stream_id in caplog.text

            # Success codes: must NOT warn (kills not-in->in, 200->201, 204->205)
            caplog.clear()
            mock_response.status_code = 200
            await go2rtc_client.unregister_stream(stream_id)
            mock_response.status_code = 204
            await go2rtc_client.unregister_stream(stream_id)
            assert "Failed to unregister stream" not in caplog.text
```

### T5 — kills C12 + C13 (2 mutants)

```python
@pytest.mark.asyncio
async def test_register_stream_credential_matrix_sends_exact_source(go2rtc_client, sample_camera_config):
    """UNVERIFIED - not yet run red/green.
    Exact-equality (not substring) on the source kills urlparse(None) (mutant
    yields "b''://admin:test_password@b''b''" which passes substring asserts),
    and the single-credential cases kill the and->or gate mutant."""
    rtsp_url = sample_camera_config["rtsp_url"]
    with patch("httpx.AsyncClient.post", autospec=True) as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"stream_id": "s", "url": "http://u"}
        mock_post.return_value = mock_response

        await go2rtc_client.register_stream(
            camera_id=sample_camera_config["camera_id"],
            rtsp_url=rtsp_url,
            username="admin",
            password="test_password",  # pragma: allowlist secret
        )
        assert mock_post.call_args.kwargs["json"]["source"] == (
            "rtsp://admin:test_password@192.168.1.100:554/stream1"
        )

        # Only a username: must be treated as unauthenticated (and->or kills)
        await go2rtc_client.register_stream(
            camera_id=sample_camera_config["camera_id"], rtsp_url=rtsp_url, username="admin"
        )
        assert mock_post.call_args.kwargs["json"]["source"] == rtsp_url

        # Only a password: same
        await go2rtc_client.register_stream(
            camera_id=sample_camera_config["camera_id"],
            rtsp_url=rtsp_url,
            password="test_password",  # pragma: allowlist secret
        )
        assert mock_post.call_args.kwargs["json"]["source"] == rtsp_url
```

### T6 — kills C14 + C15 (2 mutants)

```python
@pytest.mark.asyncio
async def test_register_stream_rejects_malformed_rtsp_urls(go2rtc_client):
    """UNVERIFIED - not yet run red/green.
    Covers the two validation branches with no positive coverage today:
    space guard (regex mutant disables it; urlparse tolerates spaces so the
    URL otherwise slips through) and host check (netloc ':554' is truthy,
    hostname None — the and-mutant accepts it)."""
    with patch("httpx.AsyncClient.post", autospec=True) as mock_post:
        with pytest.raises(StreamRegistrationError) as exc_info:
            await go2rtc_client.register_stream(
                camera_id="front_door",
                rtsp_url="rtsp://192.168.1.100:554/stream 1",  # embedded space
            )
        assert "spaces" in str(exc_info.value).lower()

        with pytest.raises(StreamRegistrationError) as exc_info:
            await go2rtc_client.register_stream(
                camera_id="front_door",
                rtsp_url="rtsp://:554/stream1",  # port but no host
            )
        assert "host" in str(exc_info.value).lower()

        mock_post.assert_not_called()
```

(The post patch keeps the mutant path hermetic: if a mutant lets the URL through validation, the mocked POST returns without raising and `pytest.raises` fails immediately — no real network attempt.)

## Kill projection

T1-T6 collectively target all 27 TEST-GAP survivors (C1 8 + C2 6 + C3 4 + C4 4 + C12/C13 2 + C14/C15 2 + C16 1) and incidentally also kill C5-mutmut_11, C9, C10 — projected 31/40 after the batch. Residual 9: C6 (2), C7 (2), C8 (2), C11 (2), C5-mutmut_12 (1) — all log-text/log-arg/payload-casing, classified EQUIVALENT/LOW-VALUE and intentionally left unkilled.

## Not drafted (lower value, per cluster classification)

- C11 payload-key casing: could pin `set(json.keys()) == {"name","source"}` if the go2rtc wire contract test is wanted — deprioritized as EQUIVALENT-classified per baseline payload-key rule.
- C8 debug-log args: would require asserting debug log content — asserting debug output is not behavior worth pinning.
