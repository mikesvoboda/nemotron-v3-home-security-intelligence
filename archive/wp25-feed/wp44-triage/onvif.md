# WP4.4 Triage Dossier — `backend/api/routes/onvif.py`

- **Module:** `backend/api/routes/onvif.py`
- **Surviving mutants:** 57 (of 167 tracked; 110 killed)
- **Covering test file (only one):** `backend/tests/unit/api/routes/test_onvif_routes.py`
- **Test style:** direct helper calls (NOT HTTP client), `@pytest.mark.asyncio`, `MagicMock()` service fixtures, `assert_called_once_with` on the onvif_service.
- **Verdict totals:** TEST-GAP 18 · LOW-VALUE 39 · EQUIVALENT 0 (sums to 57)

The 57 survivors split cleanly: **39 are pure `logger.error(...)` / `operation`-string argument clobbers** (log-only, cannot change any HTTP response — LOW-VALUE), and **18 are real behavior changes in error-mapping / response-field / argument-forwarding paths that the tests run but never assert** (TEST-GAP).

---

## Why the log-only mutants dominate (LOW-VALUE, do not assert)

`test_onvif_routes.py` contains **zero** `caplog`/log assertions (verified: `grep -c caplog` → 0). Every clobber of a `logger.error` argument, the `extra={...}` dict, `exc_info`, or the `operation` message string leaves the returned `HTTPException` byte-identical, so the 503/500 tests still pass. Nobody should assert log-record internals → LOW-VALUE by the task's own definition ("behavior nobody should assert"). These are NOT EQUIVALENT — the log record really does change (`extra=None`, key `"XXcamera_idXX"`, `exc_info=False`) — they're just not worth a test.

---

## Per-cluster table

| # | Cluster | Count | Class | What changes / why it matters |
|---|---------|-------|-------|-------------------------------|
| 1 | `_verify_camera_exists` called with `None` instead of `camera_id` | 5 | **TEST-GAP** | 4 public helpers forward `camera_id=None` into the existence check; `_verify_camera_exists` internally calls `get_camera(None)`. In prod this looks up the wrong camera → false 404. Tests pass because `get_camera` is a permissive AsyncMock and its call-args are never asserted. |
| 2 | `_handle_onvif_value_error` second OR-clause `"ptz value"` clobbered | 2 | **TEST-GAP** | `"ptz value"` → `"XXptz valueXX"` / `"PTZ VALUE"`. Service raises `ValueError("PTZ value must be between -1.0 and 1.0")` (onvif_service.py:373) which contains "ptz value" but NOT "invalid ptz command" → original maps to **400**, mutant falls through to **404**. Path never exercised. |
| 3 | 404 detail from `_verify_camera_exists` dropped | 2 | **TEST-GAP** | `detail=str(e)` → `detail=None` / detail arg dropped. Starlette replaces `None` with `HTTPStatus(404).phrase` = "Not Found". Existing test asserts `"not found" in detail.lower()` which "Not Found" STILL satisfies — so the assertion is fooled and the real error text is lost. |
| 4 | general-Exception "invalid preset token" → 400 branch | 4 | **TEST-GAP** | `_handle_onvif_error` `error_msg=str(e)`→`str(None)`, and the `"invalid preset token" in error_msg.lower()` needle/case clobbered (×3). A non-ValueError whose message says "Invalid preset token" must map to **400**; every mutant returns **503** instead. The guard's true-branch is never taken by any test (the "invalid token" test uses `ValueError`, which routes through `_handle_onvif_value_error`, not here). |
| 5 | `except Exception as e: raise _handle_onvif_error(e,…)` → `e` replaced by `None` | 3 | **TEST-GAP** | `error_msg`/`detail` become "…unreachable: None". Existing test asserts only `"unreachable" in detail.lower()` (still true), so the loss of the actual error message is unchecked. |
| 6 | `return PTZCommandResponse(... value=value, speed=speed)` — arg dropped | 2 | **TEST-GAP** | `value=` or `speed=` removed → Pydantic default `0.0`. Existing PTZ success tests assert `result.success`/`result.command`/service-call-args but never `result.value`/`result.speed`, so an echo-back of 0.0 instead of the caller's value survives. |
| 7 | `_handle_onvif_error` `logger.error(...)` argument clobbers | 10 | LOW-VALUE | 7:`msg=None` 8/11:`extra` dropped/None 9/12/17:`exc_info` None/removed/False 13/14:`camera_id` key clobbered 15/16:`error` key clobbered. Log-only, HTTPException unchanged. |
| 8 | `discover_onvif_devices` `logger.error(...)` argument clobbers | 14 | LOW-VALUE | 10/16/17/18:msg None/case 11/14:extra dropped/None 12/15/24:exc_info 19/20:`subnet` key 21/22/23:`error` key + `str(None)`. Log-only. |
| 9 | `_handle_onvif_error(e, camera_id=None, …)` — camera_id → None | 3 | LOW-VALUE | get_device_capabilities_11, execute_ptz_command_24, goto_ptz_preset_16. `camera_id` only feeds the log record, not the returned HTTPException. (Contrast cluster 5 where `e`→None DOES change detail.) |
| 10 | `_handle_onvif_error(e, camera_id, operation)` — operation string clobbered | 12 | LOW-VALUE | get_device_capabilities 12/16/17/18, execute_ptz_command 25/29/30/31, goto_ptz_preset 17/21/22/23. `operation` only feeds the logger message text. |

**Sum:** 5+2+2+4+3+2 (TEST-GAP=18) + 10+14+3+12 (LOW-VALUE=39) = **57**. ✓

---

## Key example mutant keys per TEST-GAP cluster

1. `backend.api.routes.onvif.x__verify_camera_exists__mutmut_1` (internal `get_camera(camera_id)`→`get_camera(None)`) · `...x_execute_ptz_command__mutmut_1` (`_verify_camera_exists(None,...)`) · `...x_goto_ptz_preset__mutmut_1`
2. `...x__handle_onvif_value_error__mutmut_9` (`"XXptz valueXX"`) · `...mutmut_10` (`"PTZ VALUE"`)
3. `...x__verify_camera_exists__mutmut_3` (`detail=None`) · `...mutmut_5` (detail arg dropped)
4. `...x__handle_onvif_error__mutmut_2` (`str(None)`) · `...mutmut_3` (`"XXinvalid preset tokenXX"`) · `...mutmut_6` (`.upper()` needle)
5. `...x_get_device_capabilities__mutmut_10` · `...x_execute_ptz_command__mutmut_23` · `...x_goto_ptz_preset__mutmut_15` (all `e`→`None` in the general-except)
6. `...x_execute_ptz_command__mutmut_20` (speed dropped) · `...mutmut_21` (value dropped)

---

## Drafted tests (highest-value TEST-GAP clusters)

All UNVERIFIED — not yet run red/green. TDD procedure for each: **assert fails on the mutant diff, passes on the original.** Paste into the named class of `backend/tests/unit/api/routes/test_onvif_routes.py`; they reuse the existing `mock_onvif_service` / `mock_camera_service` fixtures and `@pytest.mark.asyncio` style already imported at the top of that file.

// UNVERIFIED - not yet run red/green

### T1 — kills cluster 1 (`_verify_camera_exists(None,…)`)
Target: `TestExecutePTZCommand` in `test_onvif_routes.py`
```python
    @pytest.mark.asyncio
    async def test_execute_ptz_forwards_camera_id_to_verification(
        self, mock_onvif_service, mock_camera_service
    ):
        """The existence check must be called with the real camera_id, not None.

        Guards _verify_camera_exists(camera_id, camera_service): passing None
        here would look up the wrong camera and 404 a valid one in production.
        """
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera
        mock_onvif_service.execute_ptz_command.return_value = True

        await execute_ptz_command(
            camera_id="front_door",
            command="pan",
            value=0.5,
            speed=1.0,
            onvif_service=mock_onvif_service,
            camera_service=mock_camera_service,
        )

        # Kills x__verify_camera_exists__1 (get_camera(None)) and the four
        # per-endpoint x_...__mutmut_1 mutants (_verify_camera_exists(None, ...)).
        mock_camera_service.get_camera.assert_called_once_with("front_door")
```
One mirror of the `assert_called_once_with("front_door")` line added to each success test (`TestGetDeviceCapabilities`, `TestGetPTZPresets`, `TestGotoPTZPreset`, `TestExecutePTZCommand`) kills all 5 members of cluster 1.

### T2 — kills cluster 2 (`"ptz value"` matcher)
Target: `TestExecutePTZCommand`
```python
    @pytest.mark.asyncio
    async def test_execute_ptz_value_out_of_range_maps_to_400(
        self, mock_onvif_service, mock_camera_service
    ):
        """'PTZ value must be between...' must be a 400, not a 404.

        onvif_service raises this message (onvif_service.py:373); it contains
        "ptz value" but not "invalid ptz command", so only the second OR-clause
        of _handle_onvif_value_error catches it.
        """
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera
        mock_onvif_service.execute_ptz_command.side_effect = ValueError(
            "PTZ value must be between -1.0 and 1.0"
        )

        with pytest.raises(HTTPException) as exc_info:
            await execute_ptz_command(
                camera_id="front_door",
                command="pan",
                value=5.0,  # out of range
                speed=1.0,
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 400
        assert "Invalid PTZ command" in str(exc_info.value.detail)
```
Original hits the `"ptz value"` clause → 400; both mutants fall through to the final `return HTTPException(404, …)` → status 404, so the assertion fails.

### T3 — kills cluster 3 (404 detail dropped)
Target: `TestGetDeviceCapabilities`
```python
    @pytest.mark.asyncio
    async def test_get_capabilities_not_found_preserves_error_detail(
        self, mock_onvif_service, mock_camera_service
    ):
        """The 404 must carry the real camera-service message, not the bare
        HTTPStatus phrase. Starlette turns detail=None into 'Not Found', which
        the looser existing assertion ('not found' in detail) happily passes."""
        mock_camera_service.get_camera.side_effect = ValueError("Camera not found")

        with pytest.raises(HTTPException) as exc_info:
            await get_device_capabilities(
                camera_id="nonexistent",
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 404
        assert "Camera not found" in str(exc_info.value.detail)
```
Original detail == "Camera not found" (passes). Mutant detail == "Not Found" → "Camera not found" not present, assertion fails.

### T4 — kills cluster 4 (general Exception "invalid preset token" → 400)
Target: `TestGotoPTZPreset`
```python
    @pytest.mark.asyncio
    async def test_goto_preset_device_error_invalid_token_maps_to_400(
        self, mock_onvif_service, mock_camera_service
    ):
        """A non-ValueError whose text mentions an invalid preset token must
        be a 400 (via the guard at the top of _handle_onvif_error), not 503.
        The existing 'invalid token' test uses ValueError, so this guard's
        true-branch is otherwise never taken."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera
        # plain Exception (NOT ValueError) routes to _handle_onvif_error
        mock_onvif_service.goto_preset.side_effect = Exception("Invalid preset token")

        with pytest.raises(HTTPException) as exc_info:
            await goto_ptz_preset(
                camera_id="front_door",
                preset_token="bogus",
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 400
```
Original returns 400. Mutant `str(None)`/needle/case variants skip the guard → 503, assertion fails.

### T5 — kills cluster 5 (`e`→`None` in general-except, 503 detail)
Target: `TestGotoPTZPreset` (add to the existing unreachable test, or as its own)
```python
    @pytest.mark.asyncio
    async def test_goto_preset_device_unreachable_detail_names_error(
        self, mock_onvif_service, mock_camera_service
    ):
        """The 503 detail must echo the underlying error, not 'None'."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera
        mock_onvif_service.goto_preset.side_effect = Exception("Connection refused")

        with pytest.raises(HTTPException) as exc_info:
            await goto_ptz_preset(
                camera_id="front_door",
                preset_token="preset_1",
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 503
        assert "Connection refused" in str(exc_info.value.detail)
```
Original detail "Device unreachable: Connection refused" (passes). Mutant `e`→`None` detail "Device unreachable: None" → fails. Mirroring the last assertion in the capabilities/PTZ unreachable tests kills the other two cluster-5 members.

### T6 — kills cluster 6 (response value/speed dropped)
Target: `TestExecutePTZCommand`
```python
    @pytest.mark.asyncio
    async def test_execute_ptz_response_echoes_value_and_speed(
        self, mock_onvif_service, mock_camera_service
    ):
        """PTZCommandResponse must echo the caller's value/speed, not the
        Pydantic defaults (0.0) that appear if the field is dropped."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera
        mock_onvif_service.execute_ptz_command.return_value = True

        result = await execute_ptz_command(
            camera_id="front_door",
            command="pan",
            value=0.5,
            speed=1.0,
            onvif_service=mock_onvif_service,
            camera_service=mock_camera_service,
        )

        assert result.value == 0.5
        assert result.speed == 1.0
```
Original echoes 0.5/1.0. Dropping `speed=` yields speed=0.0 (mutant 20 fails); dropping `value=` yields value=0.0 (mutant 21 fails).

---

## Recommended strengthening of EXISTING tests (no new functions)
If minimizing new functions is preferred, these single-line additions achieve the same kills:
- `test_execute_ptz_pan_command` (line ~251): add `mock_camera_service.get_camera.assert_called_once_with("front_door")` and `assert result.value == 0.5 and result.speed == 1.0` (kills clusters 1 + 6).
- `test_get_capabilities_camera_not_found` (line ~186): tighten to `assert "Camera not found" in str(exc_info.value.detail)` (kills cluster 3).
- `test_get_capabilities_device_unreachable` / `test_goto_preset_device_unreachable` / `test_execute_ptz_device_unreachable`: add `assert "Connection refused" in str(exc_info.value.detail)` (kills cluster 5).
