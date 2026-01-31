# RTSP Camera Configuration UI with Live Preview

**Date:** 2025-01-30
**Status:** Approved
**Epic:** TBD (follow-on to NEM-4189)

## Overview

Add comprehensive UI for configuring RTSP/ONVIF cameras including:

- Username, password, and URL configuration
- Connection testing with capability detection
- Live video preview via WebRTC
- ONVIF device discovery and auto-configuration
- Stream settings control (resolution, bitrate, codec)

## Design Decisions

| Decision                | Choice                       | Rationale                                      |
| ----------------------- | ---------------------------- | ---------------------------------------------- |
| Live preview technology | go2rtc (WebRTC)              | Sub-250ms latency, no transcoding, lightweight |
| UI approach             | Enhanced camera modal        | Progressive disclosure, least disruptive       |
| Discovery flow          | Button opens discovery panel | Matches "Add Camera" workflow naturally        |
| Credential storage      | Fernet encryption at rest    | Secure without external dependencies           |
| Stream settings         | Read + write via ONVIF       | Full control without camera's web UI           |
| go2rtc deployment       | Sidecar container            | Fits containerized architecture                |
| ONVIF compatibility     | Graceful degradation         | Runtime feature detection, no static matrix    |
| Implementation          | 4-phase rollout              | Incremental value delivery                     |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                   │
├─────────────────────────────────────────────────────────────────────┤
│  CamerasSettings.tsx (Enhanced Modal)                               │
│  ├── Basic Info Section (name, status)                              │
│  ├── Connection Section (URL, credentials, test, preview)          │
│  └── Stream Settings Section (resolution, bitrate, codec)          │
│                                                                      │
│  RTSPPreviewPlayer.tsx (WebRTC video player component)              │
│  ONVIFDiscoveryPanel.tsx (network scanner UI)                       │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ REST API
┌──────────────────────────▼──────────────────────────────────────────┐
│                           BACKEND                                    │
├─────────────────────────────────────────────────────────────────────┤
│  /api/cameras/rtsp/test          - Test connection, return caps     │
│  /api/cameras/onvif/discover     - WS-Discovery scan (existing)     │
│  /api/cameras/{id}/stream-config - Get/set stream settings          │
│  /api/cameras/{id}/preview       - Register stream with go2rtc      │
│                                                                      │
│  Services:                                                           │
│  ├── credential_service.py   - Fernet encrypt/decrypt               │
│  ├── onvif_service.py        - ONVIF operations (existing)          │
│  ├── rtsp_test_service.py    - Connection testing + cap detection   │
│  └── go2rtc_client.py        - go2rtc API integration               │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP API
┌──────────────────────────▼──────────────────────────────────────────┐
│                         go2rtc (Sidecar)                            │
├─────────────────────────────────────────────────────────────────────┤
│  - Receives RTSP stream URL from backend                            │
│  - Converts RTSP → WebRTC (no transcoding)                          │
│  - Frontend connects directly for live preview                      │
│  - Port 1984 (API) + 8555 (WebRTC)                                  │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Model

### Camera Model Additions

```python
# Existing fields from NEM-4189
rtsp_url: str | None           # rtsp://host:554/stream
rtsp_username: str | None      # Stored plain
rtsp_password: str | None      # Encrypted with Fernet
stream_profile: str | None     # "main", "sub", "both"
motion_sensitivity: float      # 0.0-1.0
ingestion_mode: str            # "ftp", "rtsp", "onvif"

# New fields
onvif_port: int | None         # Default 80, some cameras use 8080
stream_capabilities: JSON      # Cached capabilities from camera
last_connection_test: datetime # When connection was last verified
connection_status: str         # "untested", "success", "failed", "timeout"
```

### Credential Encryption

```python
# backend/services/credential_service.py
from cryptography.fernet import Fernet

class CredentialService:
    def __init__(self, encryption_key: str):
        self._fernet = Fernet(encryption_key.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()
```

Environment variable: `RTSP_CREDENTIAL_KEY=<fernet-key>`

## API Endpoints

### Connection Testing

```
POST /api/cameras/rtsp/test
Request:
{
    "rtsp_url": "rtsp://192.168.1.100:554/stream1",
    "username": "admin",
    "password": "secret123"  # pragma: allowlist secret
}
Response:
{
    "success": true,
    "latency_ms": 145,
    "capabilities": {
        "video": true,
        "audio": true,
        "ptz": false,
        "resolution": "1920x1080",
        "codec": "H.264",
        "fps": 25
    },
    "snapshot_url": "/api/cameras/rtsp/snapshot/<token>"
}
```

### ONVIF Discovery

```
POST /api/cameras/onvif/discover
Response:
{
    "devices": [
        {
            "ip": "192.168.1.100",
            "port": 80,
            "manufacturer": "Hikvision",
            "model": "DS-2CD2385G1",
            "rtsp_urls": [
                {"profile": "main", "url": "rtsp://..."},
                {"profile": "sub", "url": "rtsp://..."}
            ],
            "requires_auth": true,
            "capabilities": ["video", "ptz", "events"]
        }
    ],
    "count": 1
}
```

### Stream Configuration

```
GET /api/cameras/{id}/stream-config
Response:
{
    "profiles": [
        {
            "token": "Profile_1",
            "name": "mainStream",
            "resolution": {"width": 1920, "height": 1080},
            "codec": "H264",
            "bitrate": 4096,
            "fps": 25,
            "gop": 50
        }
    ],
    "available_resolutions": ["1920x1080", "1280x720", "640x480"],
    "available_codecs": ["H264", "H265"],
    "read_only": false
}

PUT /api/cameras/{id}/stream-config
Request:
{
    "profile_token": "Profile_1",
    "resolution": {"width": 1280, "height": 720},
    "bitrate": 2048,
    "fps": 15
}
```

### Live Preview

```
POST /api/cameras/{id}/preview/start
Response:
{
    "webrtc_url": "http://localhost:8555/api/ws?src=camera_abc123",
    "stream_id": "camera_abc123",
    "expires_in": 300
}

DELETE /api/cameras/{id}/preview/stop
```

## Frontend Components

### Enhanced Camera Modal Structure

```tsx
<Dialog.Panel>
  {/* Section 1: Basic Info */}
  <BasicInfoSection>
    <Input label="Camera Name" />
    <Select label="Status" />
  </BasicInfoSection>

  {/* Section 2: Connection Type */}
  <ConnectionTypeSection>
    <RadioGroup label="Ingestion Mode" options={['ftp', 'rtsp', 'onvif']} />
  </ConnectionTypeSection>

  {/* Section 3: RTSP/ONVIF Config (shown when mode != ftp) */}
  {mode !== 'ftp' && (
    <StreamConfigSection>
      <Input label="RTSP URL" />
      <Input label="Username" />
      <PasswordInput label="Password" showReveal />
      <Button onClick={testConnection}>Test Connection</Button>
      <Button onClick={discoverDevices}>Discover Cameras</Button>
      {testResult?.success && <LivePreviewPanel />}
    </StreamConfigSection>
  )}

  {/* Section 4: Stream Settings (ONVIF with write access) */}
  {mode === 'onvif' && !streamConfig.read_only && (
    <StreamSettingsSection>
      <Select label="Resolution" />
      <Select label="Codec" />
      <Slider label="Bitrate" />
      <Slider label="Frame Rate" />
    </StreamSettingsSection>
  )}

  {/* Section 5: Motion Sensitivity */}
  {mode !== 'ftp' && <MotionSensitivitySection />}
</Dialog.Panel>
```

### New Components

| Component                  | Purpose                           |
| -------------------------- | --------------------------------- |
| `RTSPConfigSection.tsx`    | URL, credentials, test button     |
| `ConnectionStatusCard.tsx` | Test result with capability icons |
| `LivePreviewPanel.tsx`     | WebRTC video player               |
| `ONVIFDiscoveryPanel.tsx`  | Discovered devices modal          |
| `StreamSettingsForm.tsx`   | Resolution/bitrate/codec controls |
| `PasswordInput.tsx`        | Input with show/hide toggle       |

## go2rtc Integration

### Docker Compose

```yaml
services:
  go2rtc:
    image: alexxit/go2rtc:latest
    container_name: hsi-go2rtc
    restart: unless-stopped
    ports:
      - '1984:1984' # API
      - '8555:8555' # WebRTC
    environment:
      - GO2RTC_API_ORIGIN=*
    volumes:
      - ./config/go2rtc.yaml:/config/go2rtc.yaml:ro
    networks:
      - hsi-network
```

### go2rtc Config

```yaml
# config/go2rtc.yaml
api:
  listen: ':1984'
  origin: '*'

webrtc:
  listen: ':8555'
  candidates:
    - stun:stun.l.google.com:19302

streams: {} # Managed dynamically via API
```

### Backend Client

```python
# backend/services/go2rtc_client.py
class Go2RTCClient:
    async def register_stream(self, stream_id: str, rtsp_url: str,
                              username: str = None, password: str = None) -> str:
        """Register RTSP stream, return WebRTC URL."""

    async def unregister_stream(self, stream_id: str) -> None:
        """Remove stream from go2rtc."""

    async def health_check(self) -> bool:
        """Check if go2rtc is reachable."""
```

## Implementation Phases

### Phase 1: RTSP Configuration UI (Foundation)

- Add UI fields (URL, username, password) in camera modal
- Implement CredentialService with Fernet encryption
- Create `/api/cameras/rtsp/test` endpoint
- JPEG snapshot preview after successful test
- Capability detection (resolution, codec, fps)
- Database migration for new fields + encrypt existing passwords

**Deliverable:** Configure RTSP cameras with credentials, test connection, see snapshot.

### Phase 2: ONVIF Discovery + Auto-Configuration

- Discovery panel UI (modal with found devices)
- Enhanced discovery endpoint (manufacturer, model, URLs)
- Auto-fill form from discovered device
- Cache capabilities in `stream_capabilities` JSON
- Feature detection UI (✅ Video ✅ PTZ ❌ Events)

**Deliverable:** Scan network, click camera, auto-populate fields.

### Phase 3: Stream Settings Control

- GET/PUT `/api/cameras/{id}/stream-config` endpoints
- ONVIF MediaService integration for encoder settings
- Settings UI (resolution, bitrate, codec, fps)
- Graceful degradation to read-only mode
- Validation against camera's reported ranges

**Deliverable:** View and modify camera stream settings from UI.

### Phase 4: go2rtc Live Preview

- Add go2rtc to docker-compose
- Implement Go2RTCClient service
- Create RTSPPreviewPlayer.tsx (WebRTC)
- Preview session management (5 min expiry)
- Health monitoring with snapshot fallback

**Deliverable:** Real-time low-latency video preview.

## Error Handling

### Connection Testing

| Scenario         | Message                               | Action           |
| ---------------- | ------------------------------------- | ---------------- |
| Invalid URL      | "Must start with rtsp:// or rtsps://" | Block test       |
| Timeout          | "Camera unreachable"                  | Retry button     |
| Auth failed      | "Check username/password"             | Highlight fields |
| Stream not found | "Verify URL path"                     | Show hints       |

### ONVIF Discovery

| Scenario   | Message                        | Action                   |
| ---------- | ------------------------------ | ------------------------ |
| No devices | "No cameras found on network"  | Troubleshooting tips     |
| Partial    | "Found 3 cameras, 1 timed out" | Show found, note timeout |

### go2rtc

| Scenario       | Message                    | Action              |
| -------------- | -------------------------- | ------------------- |
| Unavailable    | "Showing snapshot instead" | Fallback to JPEG    |
| WebRTC failed  | "Try refreshing"           | Retry button        |
| Stream dropped | "Reconnecting..."          | Auto-reconnect (3x) |

## Graceful Degradation

```
Full ONVIF      → All features
ONVIF read-only → Settings visible, not editable
RTSP only       → Manual config, MOG2 motion detection
go2rtc down     → Snapshot preview
Invalid creds   → Clear error message
```

## Security

- Passwords never logged (use `***` placeholder)
- Passwords never in API responses (write-only)
- Preview sessions expire after 5 minutes
- Future: `/api/admin/rotate-credential-key` for key rotation

## ONVIF Compatibility Notes

ONVIF implementations vary significantly across manufacturers:

| Feature          | Reliability                  |
| ---------------- | ---------------------------- |
| Video streaming  | ✅ 95%+ works                |
| PTZ control      | ⚠️ Works, presets may differ |
| Motion detection | ❌ Rarely works via ONVIF    |
| Camera settings  | ⚠️ Hit or miss               |
| H.265            | ⚠️ May need vendor software  |

**Approach:** Runtime feature detection, not static compatibility matrix. Show users exactly what works for their camera.

## Estimated Scope

| Phase     | New Files | Modified Files | Tests    |
| --------- | --------- | -------------- | -------- |
| 1         | ~5        | ~8             | ~40      |
| 2         | ~3        | ~5             | ~25      |
| 3         | ~2        | ~4             | ~20      |
| 4         | ~4        | ~6             | ~30      |
| **Total** | **~14**   | **~23**        | **~115** |
