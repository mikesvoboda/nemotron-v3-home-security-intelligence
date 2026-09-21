# Additional imports for the existing file header (27-37):
#   import json
#   import re
#   from datetime import timedelta
#   from unittest.mock import patch
#   from backend.models.alert import AlertRule
#   from backend.api.schemas.outbound_webhook import WebhookEventType
#   import backend.services.threat_monitor_service as tms_module


class TestWp44WireContractAndRuleGaps:
    """WP4.4 drafts: wire-contract, rule-cooldown, persistence-identity mutants.

    UNVERIFIED — not yet run red/green. Each test's docstring names the cluster it kills
    and the red assertion that fires on the mutant.
    """

    @pytest.mark.asyncio
    async def test_broadcast_envelope_channel_and_full_payload_shape(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        gun_threat_detection: ThreatDetection,
    ) -> None:
        """T1 (UNVERIFIED): pins channel, envelope, and every alert_data key AND value.

        Kills _broadcast_alert_created #2-#47 (envelope/channel/publish-args, the full
        alert_data dict incl. KEY renames, id fallback, created_at/updated_at fallback).
        Red on mutant: publish call missing, unpack TypeError, KeyError, or a value
        mismatch below. Green on original.
        """
        from backend.services.threat_monitor_service import ThreatMonitorService

        created = datetime(2024, 1, 1, tzinfo=UTC)
        updated = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
        alert = Alert(
            id="alert-123",
            event_id=sample_event.id,
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.PENDING,
            dedup_key="front_door:gun:threat",
            channels=[],
            created_at=created,
            updated_at=updated,
        )
        service = ThreatMonitorService(mock_session, mock_redis_client)
        await service._broadcast_alert_created(alert, sample_event, gun_threat_detection)

        mock_redis_client.publish.assert_awaited_once()
        channel, raw = mock_redis_client.publish.call_args.args
        assert channel == "websocket:events"
        message = json.loads(raw)
        assert set(message) == {"type", "data"}
        assert message["type"] == "alert.created"
        assert message["data"] == {
            "id": "alert-123",
            "event_id": sample_event.id,
            "rule_id": None,
            "severity": "critical",
            "status": "pending",
            "dedup_key": "front_door:gun:threat",
            "created_at": created.isoformat(),
            "updated_at": updated.isoformat(),
            "camera_id": "front_door",
            "threat_type": "gun",
            "threat_confidence": 0.95,
        }

        # Fallback leg (alerts whose id/timestamps are not yet populated):
        # id must still be a uuid string, timestamps tz-aware ISO — kills the
        # "or -> and" and now_iso -> None/naive mutants.
        mock_redis_client.publish.reset_mock()
        bare = Alert(
            event_id=sample_event.id,
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.PENDING,
            dedup_key="k",
            channels=[],
        )
        await service._broadcast_alert_created(bare, sample_event, gun_threat_detection)
        fallback = json.loads(mock_redis_client.publish.call_args.args[1])["data"]
        uuid.UUID(fallback["id"])  # "None"/None from the and/str(None) mutants raises
        assert datetime.fromisoformat(fallback["created_at"]).tzinfo is not None
        assert datetime.fromisoformat(fallback["updated_at"]).tzinfo is not None

    @pytest.mark.asyncio
    async def test_webhooks_fire_with_alert_fired_type_and_full_payload(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        gun_threat_detection: ThreatDetection,
    ) -> None:
        """T2 (UNVERIFIED): pins the full trigger_webhooks_for_event contract.

        Kills _trigger_webhooks #1-#35 plus process_threat_detection #104 and
        process_multiple_threat_detections #112 (event=None is swallowed by the
        except, so the payload pins below never get a call to inspect).
        Red on mutant: no awaited call (swallowed AttributeError) or the arg/payload
        assertions fail. Green on original.
        """
        from backend.services.threat_monitor_service import ThreatMonitorService

        webhook_service = MagicMock()
        webhook_service.trigger_webhooks_for_event = AsyncMock(return_value=[])
        service = ThreatMonitorService(mock_session, mock_redis_client)

        # Flow: a real process_* run must reach the webhook with live event fields.
        with patch.object(tms_module, "get_webhook_service", return_value=webhook_service):
            await service.process_threat_detection(
                threat_detection=gun_threat_detection, event=sample_event
            )
        webhook_service.trigger_webhooks_for_event.assert_awaited_once()
        flow_payload = webhook_service.trigger_webhooks_for_event.call_args.args[2]
        assert flow_payload["camera_id"] == "front_door"
        assert flow_payload["risk_score"] == 75

        # Direct: fully populated alert pins identity fields + channels contract.
        webhook_service.trigger_webhooks_for_event.reset_mock()
        alert = Alert(
            id="alert-123",
            event_id=7,
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.PENDING,
            dedup_key="front_door:gun:threat",
            channels=["email"],
            alert_metadata={"threat_type": "gun"},
        )
        with patch.object(tms_module, "get_webhook_service", return_value=webhook_service):
            await service._trigger_webhooks(alert, sample_event)

        webhook_service.trigger_webhooks_for_event.assert_awaited_once()
        args, kwargs = webhook_service.trigger_webhooks_for_event.call_args
        assert args[0] is mock_session
        assert args[1] is WebhookEventType.ALERT_FIRED
        assert kwargs == {"event_id": "alert-123"}
        assert args[2] == {
            "alert_id": "alert-123",
            "event_id": 7,
            "rule_id": None,
            "severity": "critical",
            "status": "pending",
            "dedup_key": "front_door:gun:threat",
            "channels": ["email"],
            "matched_conditions": ["threat_detected"],
            "camera_id": "front_door",
            "risk_score": 75,
            "threat_metadata": {"threat_type": "gun"},
        }

    @pytest.mark.asyncio
    async def test_rule_dedup_key_template_and_rule_cooldown_window_are_used(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        gun_threat_detection: ThreatDetection,
    ) -> None:
        """T3 (UNVERIFIED): single-threat path must honor AlertRule template/cooldown/rule_id.

        Kills process_threat_detection #28,#31 (rule dropped from _build_dedup_key),
        #33 (cooldown_seconds short-circuit), #36,#38,#41 (rule dropped from
        _check_cooldown), #53,#60,#66 (Alert(rule_id=...) clobbered).
        Red on mutant: dedup key falls back to the default shape, the compiled
        cooldown SQL loses the rule_id filter, or the cutoff is ~now-300 not ~now-600.
        Green on original.
        """
        from backend.services.threat_monitor_service import ThreatMonitorService

        rule = AlertRule(
            name="Weapon Detection Alert",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            cooldown_seconds=600,
            dedup_key_template="{camera_id}:threat:{rule_id}",
        )
        rule.id = "rule-abc"
        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_threat_detection(
            threat_detection=gun_threat_detection, event=sample_event, rule=rule
        )

        assert alert is not None
        assert alert.dedup_key == "front_door:threat:rule-abc"
        assert alert.rule_id == "rule-abc"

        compiled = str(
            mock_session.execute.call_args.args[0].compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        assert re.search(r"rule_id\s*=\s*'rule-abc'", compiled)
        assert re.search(r"dedup_key\s*=\s*'front_door:threat:rule-abc'", compiled)
        m = re.search(r"created_at\s*>=\s*'([^']+)'", compiled)
        assert m is not None
        cutoff = datetime.fromisoformat(m.group(1))
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=UTC)
        # rule's 600s window, not the service default of 300
        assert abs((datetime.now(UTC) - cutoff).total_seconds() - 600) < 30

    @pytest.mark.asyncio
    async def test_multi_path_uses_rule_dedup_cooldown_and_persists_identity(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        sample_detection: Detection,
    ) -> None:
        """T4 (UNVERIFIED): multi path rule handling + persisted Alert identity + add/refresh args.

        Kills process_multiple_threat_detections #26,#29,#32,#34,#36,#37,#39,#42
        (dedup/cooldown), #58,#59,#61,#62,#63,#65,#66,#68,#69,#70,#72 (Alert identity
        kwargs), #91,#92 (session.add/refresh args), #106,#107 (broadcast call args).
        Red on mutant: dedup/rule SQL asserts fail, an identity field is None, the
        session mocks were called with None, or the broadcast never fires.
        Green on original.
        """
        from backend.services.threat_monitor_service import ThreatMonitorService

        rule = AlertRule(
            name="Weapon Detection Alert",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            cooldown_seconds=600,
            dedup_key_template="{camera_id}:threat:{rule_id}",
        )
        rule.id = "rule-abc"
        gun = ThreatDetection(
            id=30, detection_id=sample_detection.id, threat_type="gun",
            confidence=0.9, severity="critical", bbox=[0, 0, 1, 1],
            created_at=datetime.now(UTC),
        )
        knife = ThreatDetection(
            id=31, detection_id=sample_detection.id, threat_type="knife",
            confidence=0.85, severity="high", bbox=[0, 0, 1, 1],
            created_at=datetime.now(UTC),
        )
        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_multiple_threat_detections(
            threat_detections=[gun, knife], event=sample_event, rule=rule
        )

        assert alert is not None
        assert alert.dedup_key == "front_door:threat:rule-abc"
        assert alert.rule_id == "rule-abc"
        assert alert.event_id == sample_event.id
        assert alert.status == AlertStatus.PENDING
        assert alert.channels == []
        mock_session.add.assert_called_once_with(alert)
        mock_session.refresh.assert_awaited_once_with(alert)

        compiled = str(
            mock_session.execute.call_args.args[0].compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        assert re.search(r"rule_id\s*=\s*'rule-abc'", compiled)
        assert re.search(r"dedup_key\s*=\s*'front_door:threat:rule-abc'", compiled)
        m = re.search(r"created_at\s*>=\s*'([^']+)'", compiled)
        assert m is not None
        cutoff = datetime.fromisoformat(m.group(1))
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=UTC)
        assert abs((datetime.now(UTC) - cutoff).total_seconds() - 600) < 30

        # broadcast wiring ties event/threat args (kills event=None / threat=None call muts)
        mock_redis_client.publish.assert_awaited_once()
        data = json.loads(mock_redis_client.publish.call_args.args[1])["data"]
        assert data["camera_id"] == "front_door"
        assert data["threat_type"] == "gun"

    @pytest.mark.asyncio
    async def test_persisted_alert_identity_flags_and_metadata_shape(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        gun_threat_detection: ThreatDetection,
        sample_detection: Detection,
    ) -> None:
        """T5 (UNVERIFIED): add/refresh argument identity + metadata shape on both paths.

        Kills process_threat_detection #57,#64,#72-#82 and the multi counterparts
        #74-#92 (metadata KEY/VALUE/flag renames, session.add/refresh(None), channels).
        Red on mutant: session.add called with None, or a shape/value assertion below.
        Green on original.
        """
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_threat_detection(
            threat_detection=gun_threat_detection, event=sample_event
        )
        assert alert is not None
        mock_session.add.assert_called_once_with(alert)
        mock_session.refresh.assert_awaited_once_with(alert)
        assert alert.channels == []
        assert alert.rule_id is None
        assert alert.alert_metadata["auto_generated"] is True
        assert alert.alert_metadata["source"] == "threat_monitor_service"
        assert set(alert.alert_metadata) == {
            "threat_type",
            "threat_confidence",
            "threat_detection_id",
            "auto_generated",
            "source",
        }

        mock_session.add.reset_mock()
        mock_session.refresh.reset_mock()
        knife = ThreatDetection(
            id=43, detection_id=sample_detection.id, threat_type="knife",
            confidence=0.85, severity="high", bbox=[0, 0, 1, 1],
            created_at=datetime.now(UTC),
        )
        alert2 = await service.process_multiple_threat_detections(
            threat_detections=[gun_threat_detection, knife], event=sample_event
        )
        assert alert2 is not None
        mock_session.add.assert_called_once_with(alert2)
        mock_session.refresh.assert_awaited_once_with(alert2)
        assert alert2.channels == []
        assert alert2.alert_metadata["auto_generated"] is True
        assert alert2.alert_metadata["source"] == "threat_monitor_service"
        assert set(alert2.alert_metadata) == {
            "threat_type",
            "threat_confidence",
            "threat_detection_id",
            "detected_threats",
            "total_threats",
            "auto_generated",
            "source",
        }
        assert alert2.alert_metadata["total_threats"] == 2
        for entry in alert2.alert_metadata["detected_threats"]:
            assert set(entry) == {"type", "confidence", "severity", "detection_id"}

    @pytest.mark.asyncio
    async def test_hint_ranked_severity_and_threshold_edge_are_respected(
        self,
        mock_session: AsyncMock,
        mock_redis_client: AsyncMock,
        sample_event: Event,
        sample_detection: Detection,
    ) -> None:
        """T6 (UNVERIFIED): severity-hint ranking + >= threshold edge in the multi path.

        Kills process_multiple_threat_detections #3 (>= -> >), #6,#8-#11 and #23,#25
        (hint dropped in severity_key/highest_severity), #52-#54 (hint dropped in
        detected_threats severities).
        Red on mutant: both "weapon" threats tie at the HIGH default so max() keeps the
        MEDIUM-ranked first entry, or the exactly-at-threshold threat is filtered out.
        Green on original.
        """
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)

        # Same (unmapped) threat_type: ONLY the severity hint ranks them.
        medium_hint = ThreatDetection(
            id=40, detection_id=sample_detection.id, threat_type="weapon",
            confidence=0.9, severity="medium", bbox=[0, 0, 1, 1],
            created_at=datetime.now(UTC),
        )
        critical_hint = ThreatDetection(
            id=41, detection_id=sample_detection.id, threat_type="weapon",
            confidence=0.85, severity="critical", bbox=[0, 0, 1, 1],
            created_at=datetime.now(UTC),
        )
        alert = await service.process_multiple_threat_detections(
            threat_detections=[medium_hint, critical_hint], event=sample_event
        )
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.alert_metadata["threat_detection_id"] == critical_hint.id
        severities = {
            e["detection_id"]: e["severity"]
            for e in alert.alert_metadata["detected_threats"]
        }
        assert severities[critical_hint.id] == "critical"
        assert severities[medium_hint.id] == "medium"

        # Exactly-at-threshold detection must still count (>=, not >).
        edge = ThreatDetection(
            id=42, detection_id=sample_detection.id, threat_type="gun",
            confidence=0.70, severity="critical", bbox=[0, 0, 1, 1],
            created_at=datetime.now(UTC),
        )
        assert (
            await service.process_multiple_threat_detections(
                threat_detections=[edge], event=sample_event
            )
            is not None
        )
