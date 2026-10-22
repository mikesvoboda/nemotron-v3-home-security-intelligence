"""Unit tests for the inbound webhook route module (B4.7 / docs/uplevel/4n-arming.md)."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import HTTPException, status
from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from backend.api.middleware.auth import require_api_key
from backend.api.routes.inbound_webhooks import (
    InboundAlertPayload,
    InboundArmPayload,
    InboundDisarmPayload,
    InboundModePayload,
    arm_zones,
    create_alert,
    disarm_zones,
    router,
    set_system_mode,
    verify_hmac_signature,
)
from backend.models.alert import (
    ActivitySnooze,
    Alert,
    AlertEvent,
    AlertRule,
)
from backend.models.arming import (
    ArmingChange,
    ArmingModeExclusion,
    ArmingScheduleEntry,
    ArmingState,
)
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.enrichment import ThreatDetection
from backend.models.event import Event
from backend.models.event_detection import EventDetection
from backend.models.event_notify import EventNotifyDecision
from backend.models.event_verification import EventVerification
from backend.models.face_identity import (
    EnrollmentCandidate,
    FaceDetectionEvent,
    KnownPerson,
)
from backend.models.household_org import Household
from backend.models.notification_preferences import (
    CameraNotificationSetting,
    NotificationPreferences,
)
from backend.models.property import Property
from backend.services.alerting.pipeline import AlertPipeline
from backend.services.arming import get_arming_status, key_fingerprint, set_mode

pytestmark = pytest.mark.unit

ROUTES = (
    "/api/webhooks/inbound/alert",
    "/api/webhooks/inbound/arm",
    "/api/webhooks/inbound/disarm",
    "/api/webhooks/inbound/mode",
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
    return "VARCHAR(36)"


@compiles(TSVECTOR, "sqlite")
def _compile_tsvector_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
    return "TEXT"


@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
    return "JSON"


class _AsyncSQLiteSession:
    def __init__(self, sync_session: Session) -> None:
        self._s = sync_session

    def add(self, instance: Any) -> None:
        self._s.add(instance)

    def add_all(self, instances: Any) -> None:
        self._s.add_all(instances)

    def get_bind(self) -> Any:
        return self._s.get_bind()

    async def execute(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        return self._s.execute(statement, params=params, **kwargs)

    async def scalars(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        return self._s.scalars(statement, params=params, **kwargs)

    async def get(self, entity: Any, ident: Any, **kwargs: Any) -> Any:
        return self._s.get(entity, ident, **kwargs)

    async def flush(self) -> None:
        self._s.flush()

    async def commit(self) -> None:
        self._s.commit()

    async def rollback(self) -> None:
        self._s.rollback()


@pytest.fixture
def db_session(tmp_path: Path):
    db_file = tmp_path / "inbound_webhooks_unit.db"
    engine = create_engine(f"sqlite:///{db_file}", future=True)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    for tbl in (
        Household.__table__,
        Property.__table__,
        Camera.__table__,
        Event.__table__,
        EventVerification.__table__,
        EventNotifyDecision.__table__,
        Detection.__table__,
        ThreatDetection.__table__,
        EventDetection.__table__,
        KnownPerson.__table__,
        FaceDetectionEvent.__table__,
        EnrollmentCandidate.__table__,
        NotificationPreferences.__table__,
        CameraNotificationSetting.__table__,
        AlertRule.__table__,
        Alert.__table__,
        AlertEvent.__table__,
        ActivitySnooze.__table__,
        ArmingState.__table__,
        ArmingModeExclusion.__table__,
        ArmingScheduleEntry.__table__,
        ArmingChange.__table__,
    ):
        with engine.begin() as conn:
            tbl.create(conn, checkfirst=True)

    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as sync_sess:
        sync_sess.add(
            Camera(
                id="front_door",
                name="Front Door",
                folder_path="/export/foscam/front_door",
                status="online",
            )
        )
        sync_sess.commit()
        yield _AsyncSQLiteSession(sync_sess)

    engine.dispose()


def _guard_request(
    method: str = "POST", path: str = "/api/webhooks/inbound/arm"
) -> SimpleNamespace:
    return SimpleNamespace(scope={"type": "http", "method": method, "path": path})


def _request(host: str | None = "203.0.113.7") -> SimpleNamespace:
    client = SimpleNamespace(host=host) if host is not None else None
    return SimpleNamespace(
        client=client,
        headers={"X-API-Key": "SECRET-NEVER-LOGGED", "User-Agent": "ifttt"},
    )


class TestRequireApiKey:
    """The guard the four routes depend on (backend/api/middleware/auth.py)."""

    def test_missing_header_is_401(self):
        with pytest.raises(HTTPException) as excinfo:
            require_api_key(_guard_request(), None)
        assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing X-API-Key" in excinfo.value.detail

    def test_empty_header_is_401(self):
        with pytest.raises(HTTPException) as excinfo:
            require_api_key(_guard_request(), "")
        assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unregistered_key_is_401(self):
        settings = SimpleNamespace(api_keys=["some-other-key"], api_key_enabled=True)
        with (
            patch(
                "backend.api.middleware.auth.get_settings",
                autospec=True,
                return_value=settings,
            ),
            pytest.raises(HTTPException) as excinfo,
        ):
            require_api_key(_guard_request(), "abcdefghijklmn0p")
        assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid API key" in excinfo.value.detail

    def test_registered_key_is_returned_unchanged(self):
        settings = SimpleNamespace(api_keys=["registered-key-value"], api_key_enabled=True)
        with patch(
            "backend.api.middleware.auth.get_settings",
            autospec=True,
            return_value=settings,
        ):
            assert (
                require_api_key(_guard_request(), "registered-key-value") == "registered-key-value"
            )

    def test_no_keys_configured_refuses_everything(self):
        shipped_default = SimpleNamespace(api_keys=[], api_key_enabled=False)
        with (
            patch(
                "backend.api.middleware.auth.get_settings",
                autospec=True,
                return_value=shipped_default,
            ),
            pytest.raises(HTTPException) as excinfo,
        ):
            require_api_key(_guard_request(), "any-length-key-at-all")
        assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_comparison_uses_digest_not_the_plain_key(self):
        key = "digest-compare-key"
        settings = SimpleNamespace(api_keys=[key], api_key_enabled=True)
        digest = hashlib.sha256(key.encode()).hexdigest()
        with (
            patch(
                "backend.api.middleware.auth.get_settings",
                autospec=True,
                return_value=settings,
            ),
            patch(
                "backend.api.middleware.auth._validate_key_hash_constant_time",
                autospec=True,
            ) as compare,
        ):
            compare.return_value = True
            require_api_key(_guard_request(), key)
        compared_hash, valid_hashes = compare.call_args.args
        assert compared_hash == digest
        assert valid_hashes == {digest}


class TestInboundWebhookModesAndVocabulary:
    """Tests for /mode, /arm, /disarm vocabulary, 422s, and key fingerprint auditing (4n-arming.md)."""

    @pytest.mark.asyncio
    async def test_mode_arm_and_disarm_switch_household_mode_with_key_fingerprint(
        self, db_session: _AsyncSQLiteSession
    ) -> None:
        raw_key = "secret-webhook-api-key"  # pragma: allowlist secret
        expected_fp = key_fingerprint(raw_key)
        assert raw_key not in expected_fp

        # /arm with no mode defaults to 'away'
        res_arm = await arm_zones(
            InboundArmPayload(),
            _request(),  # type: ignore[arg-type]
            api_key=raw_key,
            db=db_session,  # type: ignore[arg-type]
        )
        assert res_arm.mode == "away"
        assert res_arm.source_name == expected_fp

        # /mode switches to 'night'
        res_mode = await set_system_mode(
            InboundModePayload(mode="night"),
            _request(),  # type: ignore[arg-type]
            api_key=raw_key,
            db=db_session,  # type: ignore[arg-type]
        )
        assert res_mode.mode == "night"

        # /disarm switches to 'disarmed'
        res_disarm = await disarm_zones(
            InboundDisarmPayload(reason="arriving home"),
            _request(),  # type: ignore[arg-type]
            api_key=raw_key,
            db=db_session,  # type: ignore[arg-type]
        )
        assert res_disarm.mode == "disarmed"
        st = await get_arming_status(db_session)  # type: ignore[arg-type]
        assert st["mode"] == "disarmed"
        assert st["source_kind"] == "webhook"
        assert st["source_name"] == expected_fp

    @pytest.mark.asyncio
    @pytest.mark.parametrize("legacy_mode", ["full", "perimeter", "instant", "bogus"])
    async def test_legacy_or_unknown_modes_and_zone_ids_return_422_naming_the_four_modes(
        self, db_session: _AsyncSQLiteSession, legacy_mode: str
    ) -> None:
        key_val = "k1"
        with pytest.raises(HTTPException) as exc1:
            await arm_zones(
                InboundArmPayload(mode=legacy_mode),
                _request(),  # type: ignore[arg-type]
                api_key=key_val,
                db=db_session,  # type: ignore[arg-type]
            )
        assert exc1.value.status_code == 422
        for m in ("home", "away", "night", "disarmed"):
            assert m in exc1.value.detail

        with pytest.raises(HTTPException) as exc2:
            await set_system_mode(
                InboundModePayload(mode=legacy_mode),
                _request(),  # type: ignore[arg-type]
                api_key=key_val,
                db=db_session,  # type: ignore[arg-type]
            )
        assert exc2.value.status_code == 422

        with pytest.raises(HTTPException) as exc3:
            await arm_zones(
                InboundArmPayload(zone_ids=["front_yard"]),
                _request(),  # type: ignore[arg-type]
                api_key=key_val,
                db=db_session,  # type: ignore[arg-type]
            )
        assert exc3.value.status_code == 422
        assert "home, away, night, disarmed" in exc3.value.detail

        with pytest.raises(HTTPException) as exc4:
            await disarm_zones(
                InboundDisarmPayload(zone_ids=["front_yard"]),
                _request(),  # type: ignore[arg-type]
                api_key=key_val,
                db=db_session,  # type: ignore[arg-type]
            )
        assert exc4.value.status_code == 422


class TestInboundAlertWebhookAndIdempotency:
    """Tests for /alert external event creation, pipeline execution, idempotency, and sweep recovery (A4, A5)."""

    @pytest.mark.asyncio
    async def test_alert_validation_422s_for_missing_or_unknown_camera_and_bad_severity(
        self, db_session: _AsyncSQLiteSession
    ) -> None:
        key_val = "k1"
        # Missing camera_id -> 422
        with pytest.raises(HTTPException) as exc_no_cam:
            await create_alert(
                InboundAlertPayload(source="ifttt", message="door open"),
                _request(),  # type: ignore[arg-type]
                api_key=key_val,
                db=db_session,  # type: ignore[arg-type]
            )
        assert exc_no_cam.value.status_code == 422

        # Unknown camera_id -> 422
        with pytest.raises(HTTPException) as exc_bad_cam:
            await create_alert(
                InboundAlertPayload(
                    camera_id="nonexistent_cam",
                    source="ifttt",
                    message="door open",
                ),
                _request(),  # type: ignore[arg-type]
                api_key=key_val,
                db=db_session,  # type: ignore[arg-type]
            )
        assert exc_bad_cam.value.status_code == 422

        # Invalid severity -> 422
        with pytest.raises(HTTPException) as exc_bad_sev:
            await create_alert(
                InboundAlertPayload(
                    camera_id="front_door",
                    source="ifttt",
                    message="door open",
                    severity="extreme",
                ),
                _request(),  # type: ignore[arg-type]
                api_key=key_val,
                db=db_session,  # type: ignore[arg-type]
            )
        assert exc_bad_sev.value.status_code == 422

    @pytest.mark.asyncio
    async def test_alert_creates_external_event_alerts_and_handles_idempotency_and_sweep(
        self, db_session: _AsyncSQLiteSession
    ) -> None:
        await set_mode(
            db_session,  # type: ignore[arg-type]
            "away",
            source_kind="user",
            source_name="admin",
        )
        await db_session.commit()

        # 1. Repeated idempotency_key under same API key gives one event and one alert
        payload = InboundAlertPayload(
            camera_id="front_door",
            source="door_sensor",
            message="Front door opened while away",
            severity="medium",
            idempotency_key="sensor-seq-42",
        )
        key_alpha = "key-alpha"
        key_beta = "key-beta"
        r1 = await create_alert(
            payload,
            _request(),  # type: ignore[arg-type]
            api_key=key_alpha,
            db=db_session,  # type: ignore[arg-type]
        )
        r2 = await create_alert(
            payload,
            _request(),  # type: ignore[arg-type]
            api_key=key_alpha,
            db=db_session,  # type: ignore[arg-type]
        )
        assert r1.event_id == r2.event_id
        assert r1.notify is True
        assert len(r1.alert_ids) == 1

        # 2. Same idempotency_key under a SECOND API key gives a second event
        r_other_key = await create_alert(
            payload,
            _request(),  # type: ignore[arg-type]
            api_key=key_beta,
            db=db_session,  # type: ignore[arg-type]
        )
        assert r_other_key.event_id != r1.event_id

        # 3. Crash between external event commit and pipeline: sweep finds it and alerts
        now = datetime.now(UTC)
        crashed_ev = Event(
            batch_id="external:crashed:1",
            camera_id="front_door",
            started_at=now,
            ended_at=now,
            risk_score=59,
            risk_level="medium",
            summary="Crashed external event",
            source="external",
            external_source="zigbee",
        )
        db_session.add(crashed_ev)
        await db_session.commit()

        pipeline = AlertPipeline()
        swept = await pipeline.sweep_unprocessed(
            session=db_session,  # type: ignore[arg-type]
            now=now,
            upgrade_applied_at=now.replace(year=2025),
        )
        await db_session.commit()
        assert any(res.event_id == crashed_ev.id for res in swept)
        alerts_for_crashed = (
            (await db_session.execute(select(Alert).where(Alert.last_event_id == crashed_ev.id)))
            .scalars()
            .all()
        )
        assert len(alerts_for_crashed) == 1
        assert alerts_for_crashed[0].verdict_source == "external"


class TestRouterDeclarationsAndHmac:
    """Router guard declarations and verify_hmac_signature tests."""

    @pytest.mark.parametrize("path", ROUTES)
    def test_every_route_depends_on_require_api_key(self, path):
        route = next(r for r in router.routes if r.path == path)
        guards = {d.call.__name__ for d in route.dependant.dependencies}
        assert "require_api_key" in guards

    def test_valid_and_invalid_hmac_signatures(self):
        body = b'{"source":"ifttt"}'
        secret = "webhook-secret"  # pragma: allowlist secret  # nosemgrep: hardcoded-password
        signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_hmac_signature(body, signature, secret) is True
        assert verify_hmac_signature(body, "sha256=" + "0" * 64, secret) is False
        assert verify_hmac_signature(body, "sha512=" + "0" * 128, secret) is False
