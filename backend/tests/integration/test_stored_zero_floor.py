"""ISS-103's pinning tests (OD-30 ruled (c), 2026-10-05): what a stored 0 does, pinned.

OD-29 shipped `DEFAULT_CAMERA_RISK_THRESHOLD = 60` with "saved values win", and OD-30 was ruled
(c): restate the shipped pair as fresh-install-only, no code — the owner states no real install
has ever saved camera settings, so the pre-merge row that stores 0 cannot exist. Ruling (c)
ACCEPTS a consequence, and these two tests pin exactly that consequence, which is otherwise true
only by accident of arithmetic:

  a stored 0 is a saved value, and it wins — the effective gate is the 40/60/80 level map against
  the default risk_filters, NOT the shipped 60 floor. Score 45 alerts.

Test 1 inserts the pre-merge row shape directly (`risk_threshold=0`, `enabled=true`) the way the
acceptance words it — the row pre-`c0191f4d` code created on a first save. Test 2 saves a 0
DELIBERATELY through the PUT route (which still accepts `ge=0`) and asserts identical behavior:
under (c) the two meanings are inseparable BY DESIGN, and that parity is the documented behavior
the ruling accepts, not a defect these tests argue against.

These are pinning tests, not red-first tests. OD-30(c) ruled "no code change", so a correct pin
passes on first run — the acceptance's "red-first" wording predates the ruling by hours, and the
block's ruling update frames the remaining work as pinning documented behavior.

Order-safety for the ISS-018 band fix riding inside the same slice: score 45 is `medium` under
BOTH the filter's 40/60/80 (`NotificationFilterService._risk_score_to_level`) and the bands of
record 29/59/84 (`SeverityService.risk_score_to_severity`), so collapsing those bands cannot flip
either assertion. That is why the pin scores 45 and not something that only one spelling likes.

Register: docs/vss-integration/17-action-plan.md — ISS-103 (Acceptance, as ruled), and the Intake
log entries "the OD-29 verification pass" and "OD-30 ruled (c)".
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from backend.core.database import get_session
from backend.models.camera import Camera
from backend.models.notification_preferences import (
    CameraNotificationSetting,
    NotificationPreferences,
)
from backend.services.notification_filter import NotificationFilterService

if TYPE_CHECKING:
    from httpx import AsyncClient

# 45 is `medium` under the filter's 40/60/80 AND under the bands of record 29/59/84, and it is the
# score the acceptance names. The shipped 60 floor would withhold it; a stored 0 admits it through
# the level map. A score every band spelling calls medium keeps the pin immune to ISS-018.
SCORE = 45


async def _seed_prefs() -> NotificationPreferences:
    """The singleton global preferences at model defaults.

    `risk_filters` defaults to [critical, high, medium] and `enabled` to True in
    NotificationPreferences.__init__ — the acceptance's "default risk_filters" is the model's own
    default, so the test never hand-picks a band that flatters the assertion.
    """
    async with get_session() as db:
        prefs = NotificationPreferences()
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)
        return prefs


def _assert_alerts(prefs: NotificationPreferences, setting: CameraNotificationSetting) -> None:
    """The pinned behavior, written once so both tests pin the SAME call."""
    decision = NotificationFilterService().should_notify(
        risk_score=SCORE,
        camera_id=setting.camera_id,
        timestamp=datetime.now(UTC),
        global_prefs=prefs,
        camera_setting=setting,
    )
    assert decision is True, (
        f"a stored risk_threshold=0 must stay a saved value that wins: with the default "
        f"risk_filters [critical, high, medium], score {SCORE} (medium under both band spellings) "
        f"must alert through the level map — OD-30 (c) accepts exactly this"
    )


@pytest.mark.asyncio
async def test_stored_zero_row_alerts_at_the_40_level_gate(integration_db: str) -> None:
    """The pre-merge row shape, inserted directly: `risk_threshold=0`, `enabled=true`.

    Current code cannot produce this row — the get-or-create branch now creates at 60 (OD-29) — so
    it is inserted, as the acceptance words it, to pin what such a row does if a database older
    than the merge ever surfaces. The register's ISS-103 evidence pins the commit that used to
    write it.
    """
    prefs = await _seed_prefs()
    async with get_session() as db:
        camera = Camera(
            id="iss103-direct",
            name="ISS-103 direct insert",
            folder_path="/export/foscam/iss103-direct",
            status="online",
        )
        db.add(camera)
        await db.commit()

        setting = CameraNotificationSetting(
            camera_id=camera.id,
            enabled=True,
            risk_threshold=0,
        )
        db.add(setting)
        await db.commit()
        await db.refresh(setting)

        assert setting.risk_threshold == 0, (
            "the seeded row is the saved-0 shape, not the 60 default"
        )
        _assert_alerts(prefs, setting)


@pytest.mark.asyncio
async def test_deliberately_saved_zero_behaves_identically(
    client: AsyncClient, integration_db: str
) -> None:
    """A 0 a human saves through the API is indistinguishable from the leftover 0 — by design.

    The PUT route accepts `ge=0` (the schema and the table's CheckConstraint both allow it), so
    "unset leftover" and "user chose 0" cannot be told apart by value alone. OD-30 (c) accepted
    that collision rather than building an explicit 'unset' representation — option (d) stays the
    deferred durable fix. This test goes through the real route so the pin covers the route's
    saves-wins path, not only the service's reading of it.
    """
    camera_id = "iss103-deliberate"
    async with get_session() as db:
        db.add(
            Camera(
                id=camera_id,
                name="ISS-103 deliberate save",
                folder_path="/export/foscam/iss103-deliberate",
                status="online",
            )
        )
        await db.commit()

    response = await client.put(
        f"/api/notification-preferences/cameras/{camera_id}",
        json={"risk_threshold": 0, "enabled": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["risk_threshold"] == 0, (
        "the PUT saves 0 rather than coercing to the default"
    )

    # The client fixture sweeps every table before the test, so prefs are seeded after the route
    # ran — the route under test is the camera-setting PUT, not the prefs singleton.
    prefs = await _seed_prefs()

    async with get_session() as db:
        setting = (
            await db.execute(
                select(CameraNotificationSetting).where(
                    CameraNotificationSetting.camera_id == camera_id
                )
            )
        ).scalar_one()
        assert setting.risk_threshold == 0, "the saved value survived the route at 0"
        assert setting.enabled is True
        _assert_alerts(prefs, setting)
