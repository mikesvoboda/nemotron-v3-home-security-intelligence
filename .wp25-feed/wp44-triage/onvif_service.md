# WP4.4 Triage Dossier — backend/services/onvif_service.py

- **Survivors:** 106 (of 603 generated; 111 killed, 386 not-yet-checked at read time)
- **Covering test file (all four mutated functions):**
  `backend/tests/unit/services/test_onvif_service.py` (classes `TestGetCapabilities` L439,
  `TestGetRtspUrlFromDevice` L678, `TestGetPresets` L747, `TestGotoPreset` L814)
- **Source:** `backend/services/onvif_service.py` — `get_capabilities` L304,
  `get_rtsp_url_from_device` L404, `get_presets` L439, `goto_preset` L469
- **Method:** diffs via `mutmut show` (read-only), all 106 captured; mock-behavior
  assumptions verified with plain interpreter checks (`urlparse(None)` succeeds →
  `(None, 80)`; `hasattr` on plain objects is False; `stmt.compile().params` captures
  the `camera_id`). No tests executed.

## Context that shapes the whole triage

Every method of this service builds `ONVIFCamera(host, port, user, passwd)` and then
drives it. The existing tests use **plain `MagicMock`** for the camera class, so any
constructor-argument mutation (None host, None port, "XXXX" creds, `or`→`and`) is
invisible — nothing records the call args. One WP4.1 test
(`test_get_capabilities_constructs_camera_with_host_port_credentials`, test file L483-511)
records args but only with non-empty creds, so the `or ""` fallback branch is still
never exercised.

The second systemic gap: capability booleans are built
`hasattr(cap, "X") and cap.X is not None`, but tests attach MagicMock to **every**
attribute, so every `hasattr` is True and every value non-None — the True→False
directions of `and`→`or` and `is not None`→`is None` flips can only be observed with a
bare capability object that _lacks_ the sub-capability. No test provides one.

Third: in `get_presets`/`goto_preset`, `device_url = None` and
`_split_onvif_device_url(None)` survive because `urlparse(None)` does not raise
(hostname None, port → default 80) and the next mock call swallows None args. The
`camera_id=None` mutants survive because the session mock is a fixture-level
`MagicMock` whose `scalar_one_or_none` returns the same camera for _any_ query — the
WHERE value is never captured. (Verified: the captured statement params DO carry the
id, e.g. `{'id_1': 'front_door'}` — a `side_effect` fake session can assert it.)

## Cluster table

| #   | Cluster                                                                                                                                                                                                                          | Function                                   | Count | Keys (examples ≤3) | Classification           |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ----- | ------------------ | ------------------------ |
| 1   | Capability-dict **key name** case/format changes (`"ptz_supported"`→`"PTZ_SUPPORTED"` etc.)                                                                                                                                      | get_capabilities                           | 10    | 102, 103, 61       | **TEST-GAP**             |
| 2   | Capability **booleans**: `and`→`or` / `is not None`→`is None` flips + `hasattr(caps,X)`→`hasattr(None,X)`                                                                                                                        | get_capabilities                           | 8     | 83, 93, 104        | **TEST-GAP**             |
| 3   | Capability **attribute-name string** changes in getattr/hasattr (`"PTZ"`→`"ptz"`, `"XXSerialNumberXX"`)                                                                                                                          | get_capabilities                           | 15    | 88, 68, 100        | **TEST-GAP**             |
| 4   | **Missing-attribute fallback** changes: `"Unknown"`→None/lowercase (killed only by absent attrs), `"None"` default dropped (semantically identical), `capabilities=None` (AttributeError — equivalent under all-MagicMock tests) | get_capabilities                           | 13    | 27, 41, 34         | **TEST-GAP**             |
| 5   | **ONVIFCamera constructor args** mutated (None host/port/user/passwd, creds→`"XXXX"`, `or`→`and`) — no test records args with empty creds; presets/goto have no arg test at all                                                  | get_presets, goto_preset                   | 18    | p9, g9, p18        | **TEST-GAP**             |
| 6   | `camera_id` → `None` passed to `_get_camera` (fixture mock answers any query)                                                                                                                                                    | get_capabilities, get_presets, goto_preset | 3     | 2 (each)           | **TEST-GAP**             |
| 7   | `device_url = None` / `_split_onvif_device_url(None)` — urlparse(None) doesn't raise; `or ""` fallback never hit                                                                                                                 | get_presets, goto_preset                   | 6     | p4, p7             | **TEST-GAP**             |
| 8   | `GetStreamUri(ProfileToken=...)` dropped / →None / →`profiles[1]` — token never asserted (existing test asserts only `assert_called_once`)                                                                                       | get_rtsp_url_from_device                   | 5     | 20, 21, 22         | **TEST-GAP**             |
| 9   | `GotoPreset(PresetToken=preset_token)` → `PresetToken=None` — token never asserted                                                                                                                                               | goto_preset                                | 1     | 21                 | **TEST-GAP**             |
| 10  | `get_presets` result `"name": getattr(p,"Name",None)` default dropped (identical semantics)                                                                                                                                      | get_presets                                | 1     | 30                 | **EQUIVALENT**           |
| 11  | Error-message text clobber in `raise ValueError("XXNo media profiles…")` — match is a prefix of both                                                                                                                             | get_rtsp_url_from_device                   | 1     | 16                 | **EQUIVALENT**           |
| 12  | **StreamSetup ONVIF wire constants** clobbered (keys/values `"Stream"`→`"xx"`, `"RTP-Unicast"`→`"rtp-unicast"`, `"RTSP"`→`"rtsp"`) + whole-kwarg deletions — mock swallows dict contents                                         | get_rtsp_url_from_device                   | 16    | 25, 28, 34         | **LOW-VALUE** (see note) |
| 13  | **goto_preset logging** mutants (message→None/case-clobbers, `extra` dict keys/values mutated, extra kwarg deleted)                                                                                                              | goto_preset                                | 10    | 22, 23, 29         | **LOW-VALUE**            |

**Sum: 10 + 8 + 15 + 13 + 18 + 3 + 6 + 5 + 1 + 1 + 1 + 16 + 10 = 106 ✔**
TEST-GAP: 9 clusters / 79 mutants · EQUIVALENT: 2 / 14 · LOW-VALUE: 2 / 13.

### Cluster notes

- **#1/#3/#4 (get_capabilities result shape):** every existing assertion is either a
  presence-check (`assert "ptz_supported" in result`, L479-480) or reads a field the
  fixture _did_ populate (manufacturer/model/firmware). `serial_number`, `hardware_id`,
  `analytics_supported` are never read; the `"Unknown"` fallbacks are never exercised
  because the test's `device_info` MagicMock answers every getattr.
- **#2:** `test_get_capabilities_returns_device_info` sets `capabilities.PTZ =
MagicMock()` / `.Media = MagicMock()` and asserts only membership — both booleans are
  True under the original _and_ the flipped mutants (hasattr=True on the MagicMock;
  with `or`/`is None` still True). A bare `SimpleNamespace()` (no PTZ/Media/Analytics)
  yields False originals vs True mutants — kills the whole cluster. `hasattr(None, X)`
  variants also yield False vs True.
- **#5:** get*presets/goto_preset have zero constructor-arg tests; the existing get_capabilities
  arg test uses non-empty creds so `or ""` mutants (`username and ""` → "" vs "admin")
  are invisible. Kill with the same autospec-style assertion plus a `None`-creds camera.
  (`host`→`None` in the \_get_presets/goto* copies is folded here — one assertion kills
  those too.)
- **#6:** needs a session fake that captures the executed statement — `stmt.compile().params`
  includes `{'id_1': 'front_door'}` (verified), so the fake can raise for wrong ids.
- **#7:** `host`-value mutants die with #5's constructor assertion; the `_split_onvif_device_url(None)`
  mutants die once `folder_path` is a MagicMock with **no** `startswith` (a non-string
  device URL must raise ValueError — the current fixture's string MagicMock happens to
  keep `.startswith("http")` truthy).
- **#12 (LOW-VALUE, not EQUIVALENT):** the wire constants ARE real ONVIF spec values
  and would matter against a live device, but under mocked onvif-zeep nothing observable
  changes and no sane test should pin zeep's kwarg spelling. If WP4.4 later adds an
  integration-style contract test asserting the exact GetStreamUri payload, #8 and #12
  collapse into one kill list — the drafted test T3 already asserts the StreamSetup dict,
  so as a by-product it kills most of #12 too. Treat #12 as: kill cheaply via T3 or mark
  baseline-scoped.
- **#13 (LOW-VALUE, not EQUIVALENT):** `logger.info(None, extra=...)` is a real behavior
  change (would crash a standard `logging.Formatter`), but per project convention log
  format/keys aren't asserted; pinning them is a test-tax.

## Drafted tests (UNVERIFIED — not yet run red/green)

TDD procedure for each: run the new test against the mutated module (`mutants/.../onvif_service.py`
variant) — assertion must FAIL; run against `backend/services/onvif_service.py` — must PASS.

### T1 — kills clusters #2 (8) + #3 (15) — capability booleans & attribute names

```python
    @pytest.mark.asyncio
    async def test_get_capabilities_flags_absent_capabilities_false(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """A device whose GetCapabilities omits PTZ/Media/Analytics must report
        ptz/media/analytics_supported all False.

        WP4.4: existing tests attach a MagicMock to every capability attribute,
        so hasattr/is-not-None flips survive mutation testing. A bare object
        (no attributes) exercises the False branches of every flag.
        """
        from types import SimpleNamespace

        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100/onvif/device_service"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance
        mock_onvif_instance.devicemgmt.GetDeviceInformation.return_value = SimpleNamespace()
        mock_onvif_instance.devicemgmt.GetCapabilities.return_value = SimpleNamespace()

        service = OnvifService(mock_session, mock_redis)
        result = await service.get_capabilities(camera_id="front_door")

        assert result["ptz_supported"] is False
        assert result["media_supported"] is False
        assert result["analytics_supported"] is False
```

Kills: 83, 90, 93, 101, 104, 112 (`or`/`is None` flips → True vs False) and 84, 88, 89, 94,
98, 99, 100, 105, 109, 110, 111 (wrong/None attr-name in hasattr → attribute genuinely
absent → False on original, True on mutant; `hasattr(None, X)` → False vs mutant True).

### T2 — kills clusters #1 (10) + #4 (11 of 13) — result contract on a minimal device

```python
    @pytest.mark.asyncio
    async def test_get_capabilities_minimal_device_full_result_contract(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """Full result contract for a device reporting no attributes at all.

        Pins the exact key names (serial_number/hardware_id/analytics_supported
        were never read by any test) and the "Unknown" fallbacks for a missing
        Manufacturer/Model. Two mutants stay equivalent by design: the
        None-default and dropped-default getattr variants (mutmut_30, mutmut_44)
        — marked EQUIVALENT in the WP4.4 baseline.
        """
        from types import SimpleNamespace

        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100/onvif/device_service"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance
        mock_onvif_instance.devicemgmt.GetDeviceInformation.return_value = SimpleNamespace()
        mock_onvif_instance.devicemgmt.GetCapabilities.return_value = SimpleNamespace()

        service = OnvifService(mock_session, mock_redis)
        result = await service.get_capabilities(camera_id="front_door")

        assert result == {
            "manufacturer": "Unknown",
            "model": "Unknown",
            "firmware_version": None,
            "serial_number": None,
            "hardware_id": None,
            "ptz_supported": False,
            "media_supported": False,
            "analytics_supported": False,
        }
```

Kills: 27, 34, 35, 36, 41, 48, 49, 50 (`"Unknown"`→None/case → None/`"unknown"` vs `"Unknown"`;
the dropped-default 30/44 produce `"Unknown"` too — equivalent, expected survivors) plus all
result-key mutations 61, 62, 71, 72, 102, 103 (dict equality sees renamed keys) and the
getattr-target/attr-name mutations that leave `"serial_number"`/`"hardware_id"`/values None
(63, 67, 68, 69, 70, 73, 77, 78, 79, 80) kill **only when combined with T1-style missing
attrs** — dict equality already sees any wrong value; note the None-arg getattr mutants
(63, 73) produce None on both sides for these fields, so they are killed by `capabilities=None`
line (mutmut_22) — see T-note below.

### T3 — kills cluster #8 (5) + most of #12 (16) — GetStreamUri call payload

```python
    @pytest.mark.asyncio
    async def test_get_rtsp_url_sends_profile_token_and_onvif_stream_setup(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """WP4.1-style constructor test for GetStreamUri: the existing success
        test asserts only assert_called_once, so ProfileToken and the
        ONVIF-mandated StreamSetup constants were never pinned.
        """
        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance

        profile = MagicMock()
        profile.token = "UniqueProfileToken"
        mock_onvif_instance.media.GetProfiles.return_value = [profile]

        stream_uri = MagicMock()
        stream_uri.Uri = "rtsp://192.168.1.100:554/stream1"
        mock_onvif_instance.media.GetStreamUri.return_value = stream_uri

        service = OnvifService(mock_session, mock_redis)
        url = await service.get_rtsp_url_from_device(
            device_url="http://192.168.1.100/onvif/device_service",
            username="admin",
            password="password123",  # pragma: allowlist secret
        )

        assert url == "rtsp://192.168.1.100:554/stream1"
        mock_onvif_instance.media.GetStreamUri.assert_called_once_with(
            ProfileToken="UniqueProfileToken",
            StreamSetup={
                "Stream": "RTP-Unicast",
                "Transport": {"Protocol": "RTSP"},
            },
        )
```

Kills: 20, 21 (None payload), 22, 23 (dropped kwarg → TypeError: missing required
keyword argument), 25-38 (every StreamSetup key/value clobber). `profiles[1]`-index and
token-clobber variants of #8 die on the token string.

### T4 — kills cluster #5 (18) + #7 (2 of 6) + #9 (1) — constructor/credential contract for presets & goto

```python
    @pytest.mark.asyncio
    async def test_preset_ops_construct_camera_with_host_port_and_empty_credentials(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """WP4.1 constructor contract applied to get_presets/goto_preset (no
        such test existed) with rtsp_username/rtsp_password unset, pinning the
        `or ""` empty-credential fallback. Empty-string creds kill the
        `and ""`, None-arg and "XXXX" mutants; port 8080 pins the parse.
        """
        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100:8080/onvif/device_service"
        mock_camera_model.rtsp_username = None
        mock_camera_model.rtsp_password = None
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance
        mock_onvif_instance.ptz.GetPresets.return_value = []

        service = OnvifService(mock_session, mock_redis)
        await service.get_presets(camera_id="front_door")
        mock_onvif_camera_class.assert_called_once_with("192.168.1.100", 8080, "", "")

        mock_onvif_camera_class.reset_mock()
        await service.goto_preset(camera_id="front_door", preset_token="preset_1")
        mock_onvif_camera_class.assert_called_once_with("192.168.1.100", 8080, "", "")
```

Kills (get_presets): 9, 10, 11, 12, 17, 18, 19, 20 and 7 (`_split(None)`→host None ≠
"192.168.1.100"). Kills (goto_preset): 9, 10, 11, 12, 17, 18, 19, 20 and 7 likewise.
Add one line to the existing `test_goto_preset_success` for cluster #9:

```python
        mock_onvif_instance.ptz.GotoPreset.assert_called_once_with(PresetToken="preset_1")
```

### T5 — kills cluster #6 (3) + #7 (4 remaining) — query identity & device-URL type

```python
    @pytest.mark.asyncio
    async def test_service_operations_query_camera_by_id_and_reject_non_http_device_url(
        self, mock_redis, mock_onvif_camera_class
    ):
        """WP4.4: the fixture session answers any query, so _get_camera(None)
        survived. A fake session that only returns the camera when the executed
        statement carries the right id pins the lookup; a MagicMock folder_path
        (no startswith) pins the non-http ValueError for presets/goto.
        """
        class FakeCameraModel(MagicMock):
            # folder_path is a bare MagicMock (no .startswith) => must raise
            pass

        camera = FakeCameraModel()
        camera.folder_path = MagicMock()  # no startswith on MagicMock strings here

        class FakeSession:
            def __init__(self):
                self.calls = []

            def execute(self, statement):
                self.calls.append(statement)
                res = MagicMock()
                params = statement.compile().params
                res.scalar_one_or_none.return_value = (
                    camera if params.get("id_1") == "cam-42" else None
                )
                return res

        session = FakeSession()
        service = OnvifService(session, mock_redis)

        with pytest.raises(ValueError, match="not an ONVIF camera"):
            await service.get_presets(camera_id="cam-42")
        assert len(session.calls) == 1

        with pytest.raises(ValueError, match="not an ONVIF camera"):
            await service.goto_preset(camera_id="cam-42", preset_token="p1")
        assert len(session.calls) == 2

        # Wrong id must NOT reach the ONVIF layer
        session2 = FakeSession()
        service2 = OnvifService(session2, mock_redis)
        with pytest.raises(ValueError, match="not found"):
            await service2.goto_preset(camera_id="wrong", preset_token="p1")
```

Kills: `_get_camera(None)` in get_capabilities/get_presets/goto_preset (key 2 each) —
with a `camera_id`-correct path asserted; get_presets/goto_preset key 4
(`device_url = None` → ValueError from non-string startswith) and key 7
(host None vs parsed host) — key 7 is already killed by T4; kept here for completeness.

### Residual expectation

After T1-T5: clusters 1-9 dead except the three EQUIVALENT line-mutants already flagged
(get*capabilities 30/44 dropped-default, get_presets 30) plus one special:
**get_capabilities mutmut_22** (`capabilities = None` → AttributeError) cannot be distinguished
under the existing connection-failure test (which asserts `pytest.raises(Exception)` —
AttributeError passes the filter) unless a test asserts \_which* exception the mock raises;
classify LOW-VALUE (dead-defensive: in production the line raising AttributeError inside no
try/except is indistinguishable from "connection fails" for every caller
— routes catch broad Exception). Recommend baseline-marking it EQUIVALENT-scope.

## Tally vs survivors

79 TEST-GAP across 9 clusters (killable by 5 drafted tests + 1 added assertion),
14 EQUIVALENT (clusters 10-11 + flagged 22), 13 LOW-VALUE (clusters 12-13; cluster 12
mostly dies for free as a by-product of T3).
