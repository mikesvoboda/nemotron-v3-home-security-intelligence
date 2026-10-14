/**
 * Uplevel F2.3 batch FE-4 — Camera Protocols: RTSP Test, ONVIF Discovery, Live Preview, PTZ
 * (`F-204`, `F-205`, `F-206`, `F-207`, `/settings/cameras`).
 *
 * Inventory rows covered:
 * - F-204: Cameras › RTSP Test Connection (`/settings/cameras`, `POST /api/cameras/rtsp/test`)
 * - F-205: Cameras › ONVIF discovery panel (`/settings/cameras`, `POST /api/cameras/onvif/discover`)
 * - F-206: Cameras › Live Preview modal (`/settings/cameras`,
 *          `POST /api/cameras/preview/start`, `DELETE /api/cameras/preview/{stream_id}/stop`)
 * - F-207: Cameras › PTZ controls and presets (`/settings/cameras`,
 *          `GET /api/cameras/{id}/onvif/presets`, `POST /api/cameras/{id}/onvif/ptz`,
 *          `POST /api/cameras/{id}/onvif/presets/{preset_token}`)
 *
 * Architectural & code findings documented and pinned here:
 * 1. F-204 (`POST /api/cameras/rtsp/test`, `backend/api/routes/cameras.py:312-349`,
 *    `backend/services/rtsp_test_service.py:87-182`): Stateless probe via `cv2.VideoCapture`.
 *    Against a refused loopback stream (`rtsp://127.0.0.1:1/live`), returns HTTP 200 with
 *    `{ success: false, capabilities: null, error_message: "Failed to connect to RTSP stream" }`,
 *    which `ConnectionStatusCard.tsx:29-46` renders in `data-testid="error-container"`.
 *    Editing `camera-rtsp-url-input` resets the status card (`CamerasSettings.tsx:148-153`).
 * 2. F-205 (`POST /api/cameras/onvif/discover`, `backend/api/routes/cameras.py:494-535`,
 *    `backend/services/onvif_service.py:101-302`): Runs WS-Discovery over the requested CIDR
 *    and returns `{ devices: [], count: 0 }` on the container network, rendered in
 *    `ONVIFDiscoveryPanel.tsx:235-270` (`data-testid="onvif-results"`).
 *    Note: `OnvifDiscoveryResult` (`backend/api/schemas/onvif.py:81-118`) omits `ip`, `port`,
 *    `rtsp_urls`, and `capabilities` that `OnvifService.discover_devices` builds (`:166-180`).
 * 3. F-206 (`POST /api/cameras/preview/start`, `backend/api/routes/cameras.py:373-449`,
 *    `DELETE /api/cameras/preview/{stream_id}/stop`, `:452-484`):
 *    - `go2rtc` is not in `docker-compose.ci.yml` or `docker-compose.fake-ai.yml`, so
 *      `client.health_check()` (`cameras.py:395-399`) fails and returns HTTP 503
 *      `{"detail": "go2rtc service is unavailable"}`.
 *    - `RTSPPreviewPlayer.tsx:218-235` renders `data-testid="error-overlay"` displaying
 *      `"Connection Failed"` and `"go2rtc service is unavailable"` with `data-testid="retry-button"`.
 *    - `DELETE /api/cameras/preview/{stream_id}/stop` catches `ConnectError` in
 *      `Go2RTCClient.unregister_stream` (`backend/services/go2rtc_client.py:155-182`) and
 *      returns HTTP 204 idempotently.
 *    - Additionally, `start_preview_direct` (`cameras.py:419`) hardcodes `sdp=None` while
 *      `go2rtcClient.ts:65-68` expects `data.sdp` in the HTTP response.
 * 4. F-207 (`PTZControls.tsx:170-408`, `backend/api/routes/onvif.py:276-474`):
 *    - `_validate_folder_path` (`backend/api/schemas/camera.py:64-67`) forbids `:` in
 *      `folder_path`, rejecting `http://...` URLs with HTTP 422, while `_get_onvif_device_url`
 *      (`backend/services/onvif_service.py:59-67`) requires `camera.folder_path.startswith("http")`
 *      or raises `ValueError("Camera ... is not an ONVIF camera")` -> HTTP 409 Conflict
 *      (`backend/api/routes/onvif.py:67-71`).
 *    - Creating an ONVIF camera with `ingestion_mode: 'onvif'` and `folder_path: '/cameras/...'`
 *      mounts `<PTZControls>` in the Edit Camera modal (`CamerasSettings.tsx:1120-1133`),
 *      loads `GET /api/cameras/{id}/onvif/presets` (`No presets`), and dispatches
 *      `POST /api/cameras/{id}/onvif/ptz` when D-pad/zoom buttons are clicked.
 */
import { expect, test } from '../guard';
import {
  apiPath,
  assertGuardSurvives,
  listCameras,
  readHarness,
  settledGoto,
  signIn,
  type Harness,
} from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

const REFUSED_RTSP_URL = 'rtsp://127.0.0.1:1/live';

test.describe('FE-4 camera protocols golden path (F-204, F-205, F-206, F-207)', () => {
  test.setTimeout(120_000);

  test('F-204: RTSP Test Connection probes POST /api/cameras/rtsp/test and renders ConnectionStatusCard', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. API-first check: POST /api/cameras/rtsp/test (backend/api/routes/cameras.py:312-349)
    const unauthProbe = await api.send('/api/cameras/rtsp/test', 'POST', {
      rtsp_url: REFUSED_RTSP_URL,
    });
    expect(unauthProbe.status, 'POST /api/cameras/rtsp/test answers 200').toBe(200);
    expect(unauthProbe.body?.success).toBe(false);
    expect(unauthProbe.body?.capabilities).toBeNull();
    expect(unauthProbe.body?.error_message).toBe('Failed to connect to RTSP stream');

    // Schema validation check: non-rtsp URL rejected with 422 (schemas/camera.py:573-592)
    const invalidProbe = await api.send('/api/cameras/rtsp/test', 'POST', {
      rtsp_url: 'http://127.0.0.1:1/not-rtsp',
    });
    expect(invalidProbe.status, 'non-RTSP URL rejected with 422').toBe(422);

    // 2. UI leg: open Add Camera modal, switch to RTSP mode, run Test Connection
    const cameras = await listCameras(api);
    expect(cameras.length).toBeGreaterThan(0);
    await settledGoto(page, h, '/settings/cameras', (p) =>
      p.getByTestId(`edit-camera-${cameras[0].id}`)
    );

    await page.getByRole('button', { name: 'Add Camera' }).first().click();
    await page.getByTestId('camera-ingestion-mode-select').selectOption('rtsp');

    const rtspInput = page.getByTestId('camera-rtsp-url-input');
    const testBtn = page.getByTestId('test-connection-button');
    await expect(rtspInput).toBeVisible();
    await expect(testBtn).toBeDisabled();

    await rtspInput.fill(REFUSED_RTSP_URL);
    await expect(testBtn).toBeEnabled();

    const testResPromise = page.waitForResponse(
      (res) => apiPath(res.url()) === '/api/cameras/rtsp/test' && res.request().method() === 'POST'
    );
    await testBtn.click();
    const testRes = await testResPromise;
    expect(testRes.status()).toBe(200);

    // ConnectionStatusCard renders error-container (ConnectionStatusCard.tsx:29-46)
    const errCard = page.getByTestId('error-container');
    await expect(errCard).toBeVisible();
    await expect(errCard).toContainText('Connection Failed');
    await expect(errCard).toContainText('Failed to connect to RTSP stream');

    // Changing rtsp_url resets testConnection state (CamerasSettings.tsx:148-153)
    await rtspInput.fill('rtsp://127.0.0.1:1/live2');
    await expect(errCard).toHaveCount(0);

    await page.getByRole('button', { name: 'Cancel' }).click();
    await assertGuardSurvives(page, h);
  });

  test('F-205: ONVIF discovery panel validates CIDR and scans via POST /api/cameras/onvif/discover', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. API-first check: POST /api/cameras/onvif/discover (backend/api/routes/cameras.py:494-535)
    const invalidCidr = await api.send('/api/cameras/onvif/discover', 'POST', {
      subnet: 'not-a-valid-cidr',
      timeout: 1,
    });
    expect(invalidCidr.status, 'invalid CIDR rejected with 422').toBe(422);

    const apiScan = await api.send('/api/cameras/onvif/discover', 'POST', {
      subnet: '192.168.1.0/24',
      timeout: 1,
    });
    expect(apiScan.status, 'POST /api/cameras/onvif/discover answers 200').toBe(200);
    expect(Array.isArray(apiScan.body?.devices)).toBe(true);
    expect(apiScan.body?.count).toBe(0);

    // 2. UI leg: open Add Camera -> switch to ONVIF -> click Discover (CamerasSettings.tsx:921-969)
    const cameras = await listCameras(api);
    await settledGoto(page, h, '/settings/cameras', (p) =>
      p.getByTestId(`edit-camera-${cameras[0].id}`)
    );

    await page.getByRole('button', { name: 'Add Camera' }).first().click();
    await page.getByTestId('camera-ingestion-mode-select').selectOption('onvif');
    await page.getByTestId('discover-cameras-button').click();

    // ONVIFDiscoveryPanel modal (ONVIFDiscoveryPanel.tsx:126-270)
    await expect(page.getByText('Discover ONVIF Cameras')).toBeVisible();
    const subnetInput = page.getByTestId('onvif-subnet-input');
    const timeoutSlider = page.getByTestId('onvif-timeout-slider');
    const scanBtn = page.getByTestId('onvif-scan-button');
    await expect(subnetInput).toHaveValue('192.168.1.0/24');

    // Client-side CIDR validation error on invalid input (ONVIFDiscoveryPanel.tsx:65-75, 167)
    await subnetInput.fill('invalid-subnet');
    await scanBtn.click();
    await expect(
      page.getByText('Invalid subnet format. Use CIDR notation (e.g., 192.168.1.0/24)')
    ).toBeVisible();

    // Restore valid CIDR, set timeout slider to minimum (5s, ONVIFDiscoveryPanel.tsx:181), and scan
    await subnetInput.fill('192.168.1.0/24');
    await timeoutSlider.focus();
    await page.keyboard.press('ArrowLeft');
    await expect(timeoutSlider).toHaveValue('5');

    const discoverPromise = page.waitForResponse(
      (res) =>
        apiPath(res.url()) === '/api/cameras/onvif/discover' && res.request().method() === 'POST',
      { timeout: 20_000 }
    );
    await scanBtn.click();
    const discoverRes = await discoverPromise;
    expect(discoverRes.status()).toBe(200);

    const resultsBox = page.getByTestId('onvif-results');
    await expect(resultsBox).toBeVisible();
    await expect(resultsBox).toContainText('0 found');
    await expect(resultsBox).toContainText('No ONVIF cameras found on this network.');

    await assertGuardSurvives(page, h);
  });

  test('F-206: Live Preview modal calls POST /api/cameras/preview/start and surfaces go2rtc 503 in RTSPPreviewPlayer', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. API-first check: POST /api/cameras/preview/start & DELETE /api/cameras/preview/{id}/stop
    // (backend/api/routes/cameras.py:373-484)
    const startRes = await api.send('/api/cameras/preview/start', 'POST', {
      rtsp_url: REFUSED_RTSP_URL,
    });
    expect(
      startRes.status,
      'POST /api/cameras/preview/start answers 503 when go2rtc is absent from CI compose'
    ).toBe(503);
    expect(startRes.body?.detail).toBe('go2rtc service is unavailable');

    const stopRes = await api.send('/api/cameras/preview/preview_golden_fe4/stop', 'DELETE');
    expect(
      stopRes.status,
      'DELETE /api/cameras/preview/{stream_id}/stop answers 204 idempotently'
    ).toBe(204);

    // 2. UI leg: open Add Camera -> select RTSP -> enter URL -> click Live Preview
    const cameras = await listCameras(api);
    await settledGoto(page, h, '/settings/cameras', (p) =>
      p.getByTestId(`edit-camera-${cameras[0].id}`)
    );

    await page.getByRole('button', { name: 'Add Camera' }).first().click();
    await page.getByTestId('camera-ingestion-mode-select').selectOption('rtsp');

    const previewBtn = page.getByTestId('live-preview-button');
    await expect(previewBtn).toBeDisabled();
    await page.getByTestId('camera-rtsp-url-input').fill(REFUSED_RTSP_URL);
    await expect(previewBtn).toBeEnabled();

    const previewStartPromise = page.waitForResponse(
      (res) =>
        apiPath(res.url()) === '/api/cameras/preview/start' && res.request().method() === 'POST'
    );
    await previewBtn.click();
    const previewStartRes = await previewStartPromise;
    expect(previewStartRes.status()).toBe(503);

    // RTSPPreviewPlayer mounts and surfaces the backend error in error-overlay (RTSPPreviewPlayer.tsx:218-235)
    const player = page.getByTestId('rtsp-preview-player');
    await expect(player).toBeVisible();
    const errorOverlay = page.getByTestId('error-overlay');
    await expect(errorOverlay).toBeVisible();
    await expect(errorOverlay).toContainText('Connection Failed');
    await expect(errorOverlay).toContainText('go2rtc service is unavailable');
    await expect(page.getByTestId('retry-button')).toBeVisible();

    await page.getByTestId('close-preview-modal').click();
    await expect(player).toHaveCount(0);

    await assertGuardSurvives(page, h);
  });

  test('F-207: PTZ controls and presets mount in Edit Camera modal for ONVIF camera and dispatch PTZ commands', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. Document & verify schema conflict: http:// in folder_path is rejected with 422
    // by _validate_folder_path (backend/api/schemas/camera.py:64-67)
    const runTag = Date.now().toString(36);
    const colonFolderRes = await api.send('/api/cameras', 'POST', {
      name: `Golden FE4 Colon ${runTag}`,
      folder_path: 'http://127.0.0.1:80/onvif/device_service',
      status: 'online',
      ingestion_mode: 'onvif',
      rtsp_url: REFUSED_RTSP_URL,
    });
    expect(
      colonFolderRes.status,
      '_validate_folder_path rejects colons in folder_path with 422'
    ).toBe(422);

    // 2. Use an existing seeded camera to verify the 3 PTZ backend endpoints and mount
    // <PTZControls> in the Edit Camera modal by switching ingestion_mode to 'onvif'
    // (CamerasSettings.tsx:921-943, 1120-1133) without saving
    const cameras = await listCameras(api);
    expect(cameras.length).toBeGreaterThan(0);
    const camId = cameras[0].id;

    // 3. API-first check of all 3 PTZ endpoints (backend/api/routes/onvif.py:276-474):
    // Because _get_onvif_device_url (backend/services/onvif_service.py:59-67) checks
    // camera.folder_path.startswith("http"), all 3 endpoints return 409 Conflict.
    const presetsRes = await api.getJson(`/api/cameras/${camId}/onvif/presets`);
    expect(presetsRes.status).toBe(409);
    expect(String(presetsRes.body?.detail ?? '')).toContain('Camera is not an ONVIF device');

    const ptzRes = await api.send(`/api/cameras/${camId}/onvif/ptz`, 'POST', {
      command: 'pan',
      value: 1.0,
      speed: 1.0,
    });
    expect(ptzRes.status).toBe(409);

    const gotoPresetRes = await api.send(`/api/cameras/${camId}/onvif/presets/preset_1`, 'POST');
    expect(gotoPresetRes.status).toBe(409);

    // 4. UI leg: open Edit Camera modal and switch ingestion_mode to 'onvif' (CamerasSettings.tsx:1120-1133)
    await settledGoto(page, h, '/settings/cameras', (p) => p.getByTestId(`edit-camera-${camId}`));
    await page.getByTestId(`edit-camera-${camId}`).click();

    const presetsFetchPromise = page.waitForResponse(
      (res) =>
        apiPath(res.url()) === `/api/cameras/${camId}/onvif/presets` &&
        res.request().method() === 'GET'
    );
    await page.getByTestId('camera-ingestion-mode-select').selectOption('onvif');
    await presetsFetchPromise;

    const ptzControls = page.getByTestId('ptz-controls');
    await expect(ptzControls).toBeVisible();
    await expect(ptzControls).toHaveAttribute('aria-label', 'PTZ camera controls');

    // Directional & zoom buttons + preset selector (PTZControls.tsx:305-408)
    const presetSelector = page.getByTestId('ptz-preset-selector');
    await expect(presetSelector).toBeVisible();
    await expect(presetSelector).toBeDisabled();
    await expect(presetSelector).toContainText('No presets');
    await expect(page.getByTestId('ptz-stop')).toBeDisabled();

    // Clicking Tilt Up dispatches POST /api/cameras/{id}/onvif/ptz with { command: 'tilt', value: 1 }
    const tiltUpPromise = page.waitForResponse(
      (res) =>
        apiPath(res.url()) === `/api/cameras/${camId}/onvif/ptz` &&
        res.request().method() === 'POST'
    );
    await page.getByTestId('ptz-up').click();
    const tiltUpRes = await tiltUpPromise;
    expect(tiltUpRes.request().postDataJSON()).toEqual({ command: 'tilt', value: 1 });

    // Clicking Zoom In dispatches POST /api/cameras/{id}/onvif/ptz with { command: 'zoom', value: 1 }
    const zoomInPromise = page.waitForResponse(
      (res) =>
        apiPath(res.url()) === `/api/cameras/${camId}/onvif/ptz` &&
        res.request().method() === 'POST'
    );
    await page.getByTestId('ptz-zoom-in').click();
    const zoomInRes = await zoomInPromise;
    expect(zoomInRes.request().postDataJSON()).toEqual({ command: 'zoom', value: 1 });

    await page.getByRole('button', { name: 'Cancel' }).click();
    await assertGuardSurvives(page, h);
  });
});
