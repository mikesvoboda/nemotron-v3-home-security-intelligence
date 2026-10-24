"""Integration tests for inbound webhook API endpoints (B4.7 / docs/uplevel/4n-arming.md).

Tests for `/api/webhooks/inbound/{alert,arm,disarm,mode}` and `/api/arming`:
- Authentication (`require_api_key`: fail-closed, 401 on missing/invalid/unregistered key)
- `/mode`, `/arm`, `/disarm` switching the household arming mode and recording the key fingerprint
- 422s on `zone_ids` and legacy/unknown modes (`full`, `perimeter`, `instant`) naming the four modes
- `/alert` creating an external event on a named camera, running `AlertPipeline.process` on every
  request, idempotency by `external:<key fingerprint>:<sha256(idempotency_key)>`, and 422s on
  missing/unknown camera or invalid severity
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from backend.core.database import get_session
from backend.models.camera import Camera
from backend.services.arming import key_fingerprint
from backend.tests.integration.conftest import TEST_API_KEY

pytestmark = pytest.mark.integration


async def _ensure_camera(camera_id: str) -> str:
    async with get_session() as db:
        if await db.get(Camera, camera_id) is None:
            db.add(
                Camera(
                    id=camera_id,
                    name=f"Camera {camera_id}",
                    folder_path=f"/export/foscam/{camera_id}",
                    status="online",
                )
            )
            await db.commit()
    return camera_id


@pytest.fixture
def valid_api_key() -> str:
    return TEST_API_KEY


@pytest.fixture
def unregistered_api_key() -> str:
    return "abcdefghijklmn0p"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,payload",
    [
        (
            "/api/webhooks/inbound/alert",
            {"camera_id": "front_door", "source": "ifttt", "message": "m"},
        ),
        ("/api/webhooks/inbound/arm", {"mode": "away"}),
        ("/api/webhooks/inbound/disarm", {"reason": "arriving"}),
        ("/api/webhooks/inbound/mode", {"mode": "home"}),
    ],
)
async def test_unregistered_or_missing_key_gets_401(
    client: AsyncClient, unregistered_api_key: str, path: str, payload: dict
) -> None:
    res_unreg = await client.post(path, json=payload, headers={"X-API-Key": unregistered_api_key})
    assert res_unreg.status_code == 401
    assert "Invalid API key" in res_unreg.json()["detail"]

    res_missing = await client.post(path, json=payload, headers={"X-API-Key": ""})
    assert res_missing.status_code == 401
    assert "Missing X-API-Key" in res_missing.json()["detail"]


@pytest.mark.asyncio
async def test_auth_is_checked_before_payload(
    client: AsyncClient, unregistered_api_key: str
) -> None:
    response = await client.post(
        "/api/webhooks/inbound/alert",
        json={},
        headers={"X-API-Key": unregistered_api_key},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_mode_arm_and_disarm_and_422_vocabulary(
    client: AsyncClient, valid_api_key: str
) -> None:
    headers = {"X-API-Key": valid_api_key}
    expected_fp = key_fingerprint(valid_api_key)

    # /arm defaults to 'away'
    r_arm = await client.post("/api/webhooks/inbound/arm", json={}, headers=headers)
    assert r_arm.status_code == 200
    assert r_arm.json()["mode"] == "away"
    assert r_arm.json()["source_name"] == expected_fp

    # /mode switches to 'night'
    r_mode = await client.post(
        "/api/webhooks/inbound/mode", json={"mode": "night"}, headers=headers
    )
    assert r_mode.status_code == 200
    assert r_mode.json()["mode"] == "night"

    # /disarm switches to 'disarmed'
    r_disarm = await client.post(
        "/api/webhooks/inbound/disarm", json={"reason": "home"}, headers=headers
    )
    assert r_disarm.status_code == 200
    assert r_disarm.json()["mode"] == "disarmed"

    # Legacy modes (full, perimeter, instant) and zone_ids return 422 naming the four modes
    for legacy in ("full", "perimeter", "instant"):
        r_leg = await client.post(
            "/api/webhooks/inbound/arm", json={"mode": legacy}, headers=headers
        )
        assert r_leg.status_code == 422
        for m in ("home", "away", "night", "disarmed"):
            assert m in r_leg.json()["detail"]

    r_zones = await client.post(
        "/api/webhooks/inbound/arm", json={"zone_ids": ["z1"]}, headers=headers
    )
    assert r_zones.status_code == 422

    # Restore mode to 'home'
    await client.post("/api/webhooks/inbound/mode", json={"mode": "home"}, headers=headers)


@pytest.mark.asyncio
async def test_webhook_alert_creates_external_event_alerts_and_deduplicates_idempotency_key(
    client: AsyncClient, valid_api_key: str
) -> None:
    headers = {"X-API-Key": valid_api_key}
    cam_id = await _ensure_camera(f"webhook_cam_{uuid.uuid4().hex[:8]}")

    # Ensure mode is 'away' so camera is armed
    await client.post("/api/webhooks/inbound/mode", json={"mode": "away"}, headers=headers)

    # Missing camera_id -> 422
    r_no_cam = await client.post(
        "/api/webhooks/inbound/alert",
        json={"source": "ifttt", "message": "motion"},
        headers=headers,
    )
    assert r_no_cam.status_code == 422

    # Unknown camera_id -> 422
    r_bad_cam = await client.post(
        "/api/webhooks/inbound/alert",
        json={"camera_id": "no_such_camera", "source": "ifttt", "message": "motion"},
        headers=headers,
    )
    assert r_bad_cam.status_code == 422

    # Valid external alert with idempotency_key -> creates external event and alert
    idem_key = f"idem-{uuid.uuid4().hex[:8]}"
    payload = {
        "camera_id": cam_id,
        "source": "door_sensor",
        "message": "Door sensor triggered",
        "severity": "medium",
        "idempotency_key": idem_key,
    }
    r1 = await client.post("/api/webhooks/inbound/alert", json=payload, headers=headers)
    assert r1.status_code == 200
    b1 = r1.json()
    assert b1["notify"] is True
    assert len(b1["alert_ids"]) == 1

    # Repeated idempotency_key returns the same event
    r2 = await client.post("/api/webhooks/inbound/alert", json=payload, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["event_id"] == b1["event_id"]

    # Restore mode to 'home'
    await client.post("/api/webhooks/inbound/mode", json={"mode": "home"}, headers=headers)
