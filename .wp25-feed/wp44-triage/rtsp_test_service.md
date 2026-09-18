# WP4.4 Triage Dossier — backend/services/rtsp_test_service.py

- **Survivors:** 46 of 137 mutants (exit_code 0). Meta: `mutants/backend/services/rtsp_test_service.py.meta`.
- **Covering test file (sole):** `backend/tests/unit/services/test_rtsp_test_service.py` (class `TestRTSPTestService` line 26; message-case tests: `test_invalid_url_format` :142, `test_connection_timeout` :79, `test_authentication_failure` :110, `test_network_unreachable` :251, `test_stream_not_found` :272, `test_capability_detection` :165, `test_latency_measurement` :289, `test_credentials_in_url` :331).
- **Mutant source keys shape:** `backend.services.rtsp_test_service.xǁRTSPTestServiceǁ<fn>__mutmut_N`; 4 functions: `_validate_url`, `_check_url_components`, `test_connection`, `_test_capture`.
- All diffs obtained via read-only `uv run mutmut show <key>` (all 46; one initial fetch dropped a key in the batch loop, re-fetched individually — accounted).

## Why survivors look the way they do (root causes in the existing suite)

1. **Case-insensitive, substring error-message assertions.** `test_invalid_url_format` (:162) checks only `"url" in msg.lower() or "format" in msg.lower()`; `test_connection_timeout` (:106) `"timeout" in msg.lower()`; `test_authentication_failure` (:136-139) `"authentication"/"credentials" in msg.lower()`. No test asserts *which* error string a branch produced — so both case-clobber mutants and **wrong-branch message swaps** survive.
2. **No test ever looks at what URL is handed to `cv2.VideoCapture`.** `test_credentials_in_url` (:331) never passes credentials as args, and every mock accepts any URL, so the entire credential-injection pipeline (`bool(username and password)`, `"://" in`, `split("://",1)`, the f-string rebuild) is unasserted.
3. **Capability assertions are partial.** Existing tests assert `video`, `resolution`, `codec`, `fps` but never `audio`, `ptz`, and never the `None` fallbacks when width/height/fps come back as 0 (all mocks feed non-zero values).
4. **Latency assertion band is wide** (`0 < latency_ms < 5000`, :310) — floor/scale tweaks stay in-band.

## Cluster table (counts sum to 46)

| # | Pattern (function / concern) | Count | Keys (≤3 ex.) | Class | Note |
|---|---|---|---|---|---|
| 1 | Wrong validation message text clobbers a *different* validation branch (`_validate_url` spaces-msg XX/lower/upper; `_check_url_components` missing-protocol XX/lower/upper; missing-host XX/lower/upper) | 9 | `_validate_url__mutmut_6`, `_check_url_components__mutmut_2`, `_check_url_components__mutmut_10` | TEST-GAP | Full keys: vu 6,7,8; cuc 2,3,4,10,11,12. Tests only do case-insensitive substring checks, so they can't tell "missing host" from "missing protocol" from "contains spaces" — the *specific diagnostic* each branch returns is unasserted. A wrong-branch swap is indistinguishable today. |
| 2 | `or`→`and` in missing-host guard: `if not parsed.netloc or not parsed.hostname` → `and` (`_check_url_components`) | 1 | `_check_url_components__mutmut_7` | TEST-GAP | Mutant lets `rtsp://admin@/stream` (netloc set, hostname None) validate as OK. Test fixture `"rtsp://"` has BOTH empty, so or/and behave identically on every tested input — the discriminating input is missing from the suite. |
| 3 | Credential-injection pipeline mutated in `test_connection`: `bool(username and password)`→`or`; `"://" in`→XX / `not in`; `split("://",1)`→no-maxsplit / `rsplit` / maxsplit=2; rebuilt URL→`None` | 7 | `test_connection__mutmut_10`, `test_connection__mutmut_17`, `test_connection__mutmut_21` | TEST-GAP | Full keys: tc 10,11,12,17,18,20,21. No test asserts the URL argument passed to `cv2.VideoCapture`, so nulled/inverted guards, ValueError-prone splits (swallowed by the broad `except Exception` into a generic "Connection failed"), and the `rtsp_url=None` assignment all pass. |
| 4 | URL argument to capture nulled: `cv2.VideoCapture(rtsp_url)`→`(None)` (`_test_capture`), `run_in_executor(..., rtsp_url, ...)`→`(..., None, ...)` (`test_connection`) | 2 | `_test_capture__mutmut_3`, `test_connection__mutmut_30` | TEST-GAP | Mocks return `mock_instance` for any argument, so the success path never notices the URL is None. Same blind spot as #3 (call args unchecked). |
| 5 | `RTSPCapabilities(...)` construction fields: `audio=False`→None/True, `ptz=False`→None/True, `video=True`/`audio=`/`ptz=`/`codec="H.264"` args deleted (fall to dataclass defaults) (`_test_capture`) | 8 | `_test_capture__mutmut_32`, `_test_capture__mutmut_37`, `_test_capture__mutmut_44` | TEST-GAP | Full keys: tc( capture ) 32,33,37,38,39,41,44,45. Suite asserts video/resolution/fps but never `audio is False`, `ptz is False`, or that the constructor sets codec explicitly. audio=True/ptz=True is a *false capability report* to the UI. |
| 6 | Detection-condition guards: `resolution=... if width and height else None` → `or True` / `width or height`; `fps=fps if fps > 0 else None` → `or True` / `>= 0` / `> 1` (`_test_capture`) | 5 | `_test_capture__mutmut_47`, `_test_capture__mutmut_48`, `_test_capture__mutmut_53` | TEST-GAP | Every mock feeds non-zero width/height/fps, so the None-fallbacks and the exact `> 0` boundary (fps 0 → None, fps 1 → 1) are never exercised. Mutants report `"0x0"` resolution / `fps=0` as real values. |
| 7 | Capture-failure error messages: auth-fail msg XX/lower/upper; connect-fail msg XX/lower/upper; `success=False` kwarg removed from connect-fail return (`_test_capture`) | 7 | `_test_capture__mutmut_10`, `_test_capture__mutmut_15`, `_test_capture__mutmut_18` | TEST-GAP | Full keys: 10,11,12,15,18,19,20. `success=False` removal turns the no-credentials failure into `success=None` + a TypeError-flavored "Connection failed: ..." message that still contains "connect" — `test_network_unreachable`'s disjunctive lowercase check passes it. Auth-vs-connect message misattribution (the user-facing "check username and password" hint) is unasserted. |
| 8 | Timeout error message text clobber (XX/lower/upper) (`test_connection` TimeoutError branch) | 3 | `test_connection__mutmut_52` | LOW-VALUE | Timeout behavior (success=False, "timeout" substring, capabilities None) is asserted at :104-107; only the exact display casing/decoration of the sentence survives as unasserted. Pinning exact UX prose is brittle; case-insensitive contract already exists. |
| 9 | Latency formula tweaks: `max(1,...)`→`max(2,...)`, `*1000`→`/1000`, `*1001` (`test_connection`) | 3 | `test_connection__mutmut_43` | LOW-VALUE | `/1000` still floors to 1 in fast mocked runs; `max(2)`/`*1001` stay inside the asserted `0 < ms < 5000` band. Exact latency arithmetic is wall-clock noise under mocks — no stable, meaningful assertion exists; only a flake-prone frozen-time test would chase these. |
| 10 | Unused default swap: `_test_capture(self, rtsp_url, has_credentials: bool = False)` → `= True` | 1 | `_test_capture__mutmut_1` | LOW-VALUE | Sole caller (`test_connection`) always passes the arg explicitly; the default is dead code. No behavior reachable through any public entry point changes. |

**Totals:** 9+1+7+2+8+5+7+3+3+1 = **46**. TEST-GAP clusters 1–7 (39 mutants), LOW-VALUE clusters 8–10 (7 mutants). No true EQUIVALENTs: every string clobber in clusters 1 and 7 sits on a branch whose *diagnostic identity* is real contract (setup-wizard surfaces the exact message), distinguished from cluster 8 (behavior already pinned, only prose cosmetics left) by whether any surviving assertion can tell branches apart.

## Drafted tests (6 functions; target file `backend/tests/unit/services/test_rtsp_test_service.py`, add to `TestRTSPTestService`)

// UNVERIFIED - not yet run red/green. TDD procedure: add each test, run against the MUTANT source copy — the new assertion must FAIL on the cluster's mutant diff; run against `backend/services/rtsp_test_service.py` original — it must PASS.

```python
    # Kills cluster 1 (9 mutants): each validation branch's exact diagnostic message.
    @pytest.mark.asyncio
    async def test_validation_error_identifies_the_specific_problem(
        self, service: RTSPTestService
    ) -> None:
        """Each invalid URL must get ITS OWN error text, case-exact.

        The existing test_invalid_url_format only checks a lowercase substring,
        so any branch can return any other branch's message and survive.
        """
        SPACES = "Invalid URL format - URL contains spaces or invalid characters"
        NO_PROTO = "Invalid URL format - missing protocol (expected rtsp:// or rtsps://)"
        BAD_PROTO = (
            "Invalid URL format - unsupported protocol 'http' "
            "(expected rtsp:// or rtsps://)"
        )
        NO_HOST = "Invalid URL format - missing host"

        cases = [
            ("rtsp://192.168.1.100:554/stream 1", SPACES, ["protocol", "missing host"]),
            ("192.168.1.100:554/stream", NO_PROTO, ["unsupported protocol", "missing host"]),
            ("http://192.168.1.100:80/stream", BAD_PROTO, ["missing protocol", "missing host"]),
            ("rtsp://", NO_HOST, ["protocol"]),
        ]
        for url, expected, forbidden in cases:
            result = await service.test_connection(rtsp_url=url)
            assert result.success is False
            assert result.error_message == expected  # case-exact: kills XX/lower/upper
            low = result.error_message.lower()
            for frag in forbidden:
                assert frag not in low, f"{url!r} got wrong diagnostic: {result.error_message}"

    # Kills cluster 2 (1 mutant): hostname missing while netloc non-empty.
    @pytest.mark.asyncio
    async def test_url_with_userinfo_but_no_host_is_rejected(self, service: RTSPTestService) -> None:
        """rtsp://admin@/stream has netloc 'admin@' but hostname None.

        or→and in the host guard survives because every existing invalid URL
        leaves netloc AND hostname empty simultaneously.
        """
        result = await service.test_connection(rtsp_url="rtsp://admin@/stream")
        assert result.success is False
        assert result.error_message == "Invalid URL format - missing host"

    # Kills clusters 3 (7 mutants) AND 4 (2 mutants): the URL OpenCV receives.
    @pytest.mark.asyncio
    async def test_url_passed_to_videocapture_is_the_credentialed_url(
        self, service: RTSPTestService
    ) -> None:
        """Assert the exact string handed to cv2.VideoCapture, not just success.

        Kills: username-or-password injection, inverted/absent '://' guard,
        split-maxsplit variants (ValueError → generic failure), rebuilt-URL=None,
        and VideoCapture(None) / run_in_executor(None, ...).
        """
        def opened_cap(*args, **kwargs):
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = True
            mock_instance.get.side_effect = lambda prop: {3: 1920, 4: 1080, 5: 25.0}.get(prop, 0)
            return mock_instance

        url = "rtsp://192.168.1.100:554/stream1"
        with patch(
            "backend.services.rtsp_test_service.cv2.VideoCapture",
            side_effect=opened_cap,
            autospec=True,
        ) as mock_cap:
            # full credentials: exactly one injection, protocol split left-to-right
            result = await service.test_connection(
                rtsp_url=url, username="admin", password="secret123"  # nosemgrep: hardcoded-password # pragma: allowlist secret
            )
            assert result.success is True
            assert mock_cap.call_args.args[0] == (
                "rtsp://admin:secret123@192.168.1.100:554/stream1"
            )

            # password=None: username alone must NOT trigger injection
            mock_cap.reset_mock()
            await service.test_connection(rtsp_url=url, username="admin", password=None)
            assert mock_cap.call_args.args[0] == url

            # multi-scheme URL: first '://' splits, rest preserved verbatim
            mock_cap.reset_mock()
            result = await service.test_connection(
                rtsp_url="rtsp://host/a://b",  # pragma: allowlist secret
                username="admin",
                password="secret123",  # nosemgrep: hardcoded-password # pragma: allowlist secret
            )
            assert result.success is True  # split(None|2) ValueError → False here
            assert mock_cap.call_args.args[0] == "rtsp://admin:secret123@host/a://b"

    # Kills cluster 5 (8 mutants): audio/ptz/codec set explicitly by detection.
    @pytest.mark.asyncio
    async def test_detected_capabilities_fix_audio_and_ptz_false(
        self, service: RTSPTestService
    ) -> None:
        """Detection must report audio=False and ptz=False explicitly (identity, not falsy)."""
        url = "rtsp://192.168.1.100:554/stream1"
        with patch(
            "backend.services.rtsp_test_service.cv2.VideoCapture", autospec=True
        ) as mock_cap:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = True
            mock_instance.get.side_effect = lambda prop: {3: 1920, 4: 1080, 5: 25.0}.get(prop, 0)
            mock_cap.return_value = mock_instance

            result = await service.test_connection(rtsp_url=url)
            assert result.success is True
            caps = result.capabilities
            assert caps.video is True
            assert caps.audio is False  # identity: kills None and True
            assert caps.ptz is False    # identity: kills None and True
            assert caps.codec == "H.264"

    # Kills cluster 6 (5 mutants): 0-dimension and 0-fps fall back to None.
    @pytest.mark.asyncio
    async def test_zero_stream_properties_report_none_not_zero(
        self, service: RTSPTestService
    ) -> None:
        """width/height/fps of 0 must yield resolution=None / fps=None, and fps=1 survives."""
        def cap_with(props):
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = True
            mock_instance.get.side_effect = lambda prop: props.get(prop, 0)
            return mock_instance

        url = "rtsp://192.168.1.100:554/stream1"
        with patch(
            "backend.services.rtsp_test_service.cv2.VideoCapture", autospec=True
        ) as mock_cap:
            # all-zero stream: no fake "0x0" resolution, no fake fps=0
            mock_cap.return_value = cap_with({3: 0, 4: 0, 5: 0})
            result = await service.test_connection(rtsp_url=url)
            assert result.capabilities.resolution is None
            assert result.capabilities.fps is None

            # only height zero: still no resolution (and-must-both-set guard)
            mock_cap.return_value = cap_with({3: 1920, 4: 0, 5: 25.0})
            result = await service.test_connection(rtsp_url=url)
            assert result.capabilities.resolution is None
            assert result.capabilities.fps == 25

            # boundary: fps of exactly 1 is a real value (kills fps > 1)
            mock_cap.return_value = cap_with({3: 1920, 4: 1080, 5: 1.0})
            result = await service.test_connection(rtsp_url=url)
            assert result.capabilities.fps == 1

    # Kills cluster 7 (7 mutants): auth-vs-connect failure prose, case-exact.
    @pytest.mark.asyncio
    async def test_failed_open_message_distinguishes_auth_from_connect(
        self, service: RTSPTestService
    ) -> None:
        """isOpened()=False: credentials → auth hint; no credentials → connect failure.

        Case-exact equality kills XX/lower/upper clobbers AND the success=False
        removal (mutant degrades to 'Connection failed: <TypeError text>' there).
        """
        url = "rtsp://192.168.1.100:554/stream1"
        with patch(
            "backend.services.rtsp_test_service.cv2.VideoCapture", autospec=True
        ) as mock_cap:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = False
            mock_cap.return_value = mock_instance

            result = await service.test_connection(rtsp_url=url)
            assert result.success is False
            assert result.error_message == "Failed to connect to RTSP stream"
            assert result.capabilities is None

            mock_instance.reset_mock()
            result = await service.test_connection(
                rtsp_url=url, username="wrong_user", password="wrong_password"  # nosemgrep: hardcoded-password # pragma: allowlist secret
            )
            assert result.success is False
            assert result.error_message == "Authentication failed - check username and password"
```

## Covering test file references

- `backend/tests/unit/services/test_rtsp_test_service.py:142` `test_invalid_url_format` — substring-only URL checks (gap for cluster 1).
- `backend/tests/unit/services/test_rtsp_test_service.py:110` `test_authentication_failure` / `:251` `test_network_unreachable` — disjunctive lowercase message checks (gap for cluster 7).
- `backend/tests/unit/services/test_rtsp_test_service.py:331` `test_credentials_in_url` — name suggests URL construction coverage but passes no credentials and never inspects call args (gap for clusters 3/4).
- `backend/tests/unit/services/test_rtsp_test_service.py:165` `test_capability_detection` — asserts only video/resolution/fps on non-zero mocks (gap for clusters 5/6).
- `backend/tests/unit/services/test_rtsp_test_service.py:79` `test_connection_timeout`, `:289` `test_latency_measurement` — behavior pinned; only cosmetics/arithmetic survive (clusters 8/9 → LOW-VALUE).
