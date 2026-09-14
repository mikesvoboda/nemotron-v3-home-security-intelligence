"""Integration tests for Home Assistant MQTT Discovery Service.

Tests the HADiscoveryManager class which publishes MQTT discovery payloads
for Home Assistant auto-configuration. Tests cover discovery publishing,
entity registration, error handling, and integration with MQTT client.

Related Issues:
    - NEM-5146: [Implement] Phase 4: HA MQTT Discovery + Entity Types
    - NEM-5032: Epic 3: Ecosystem Integration
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.ha_discovery import (
    ComponentType,
    DeviceClass,
    HADeviceInfo,
    HADiscoveryManager,
    HADiscoveryPayload,
    HADiscoverySettings,
)
from backend.tests.integration.conftest import unique_id

# Mark all tests as integration
pytestmark = [pytest.mark.integration]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_mqtt_client() -> MagicMock:
    """Create a mock MQTT client for testing discovery publishing."""
    client = MagicMock()
    # Make publish method async
    client.publish = AsyncMock()
    return client


@pytest.fixture
def ha_settings_enabled() -> HADiscoverySettings:
    """Create HA Discovery settings with discovery enabled."""
    return HADiscoverySettings(
        enabled=True,
        discovery_prefix="homeassistant",
        publish_cameras=True,
        publish_alerts=True,
        publish_events=True,
        device_name_prefix="HSI",
    )


@pytest.fixture
def ha_settings_disabled() -> HADiscoverySettings:
    """Create HA Discovery settings with discovery disabled."""
    return HADiscoverySettings(enabled=False)


@pytest.fixture
def ha_manager(
    mock_mqtt_client: MagicMock,
    ha_settings_enabled: HADiscoverySettings,
) -> HADiscoveryManager:
    """Create HADiscoveryManager with mock MQTT client and enabled settings."""
    return HADiscoveryManager(
        mqtt_client=mock_mqtt_client,
        settings=ha_settings_enabled,
    )


@pytest.fixture
def ha_manager_disabled(
    mock_mqtt_client: MagicMock,
    ha_settings_disabled: HADiscoverySettings,
) -> HADiscoveryManager:
    """Create HADiscoveryManager with discovery disabled."""
    return HADiscoveryManager(
        mqtt_client=mock_mqtt_client,
        settings=ha_settings_disabled,
    )


# =============================================================================
# Test HADeviceInfo Schema
# =============================================================================


class TestHADeviceInfo:
    """Tests for HADeviceInfo model."""

    def test_device_info_minimal(self) -> None:
        """Test creating device info with minimal required fields."""
        device = HADeviceInfo(
            identifiers=["hsi_cam1"],
            name="Front Door Camera",
            model="Security Camera",
        )

        assert device.identifiers == ["hsi_cam1"]
        assert device.name == "Front Door Camera"
        assert device.manufacturer == "HSI"
        assert device.model == "Security Camera"
        assert device.sw_version is None
        assert device.hw_version is None
        assert device.via_device == "hsi_hub"

    def test_device_info_full(self) -> None:
        """Test creating device info with all optional fields."""
        device = HADeviceInfo(
            identifiers=["hsi_cam1", "cam1"],
            name="Front Door Camera",
            manufacturer="Custom Manufacturer",
            model="HD Camera v2",
            sw_version="1.2.3",
            hw_version="2.0",
            via_device="custom_hub",
        )

        assert len(device.identifiers) == 2
        assert device.manufacturer == "Custom Manufacturer"
        assert device.sw_version == "1.2.3"
        assert device.hw_version == "2.0"
        assert device.via_device == "custom_hub"


# =============================================================================
# Test HADiscoveryPayload Schema
# =============================================================================


class TestHADiscoveryPayload:
    """Tests for HADiscoveryPayload model."""

    def test_binary_sensor_payload(self) -> None:
        """Test creating a binary sensor discovery payload."""
        device = HADeviceInfo(
            identifiers=["hsi_cam1"],
            name="Front Door Camera",
            model="Security Camera",
        )

        payload = HADiscoveryPayload(
            component=ComponentType.BINARY_SENSOR,
            object_id="hsi_cam1_motion",
            unique_id="hsi_cam1_motion",
            name="Front Door Motion",
            state_topic="hsi/detections/cam1/person",
            device_class=DeviceClass.MOTION,
            device=device,
        )

        assert payload.component == ComponentType.BINARY_SENSOR
        assert payload.object_id == "hsi_cam1_motion"
        assert payload.device_class == DeviceClass.MOTION
        assert payload.payload_on == "ON"
        assert payload.payload_off == "OFF"
        assert payload.retain is True
        assert payload.qos == 1

    def test_sensor_payload(self) -> None:
        """Test creating a sensor discovery payload."""
        device = HADeviceInfo(
            identifiers=["hsi_cam1"],
            name="Front Door Camera",
            model="Security Camera",
        )

        payload = HADiscoveryPayload(
            component=ComponentType.SENSOR,
            object_id="hsi_cam1_risk_score",
            unique_id="hsi_cam1_risk_score",
            name="Front Door Risk Score",
            state_topic="hsi/events/cam1",
            unit_of_measurement="%",
            icon="mdi:alert-circle",
            value_template="{{ value_json.risk_score }}",
            device=device,
        )

        assert payload.component == ComponentType.SENSOR
        assert payload.unit_of_measurement == "%"
        assert payload.icon == "mdi:alert-circle"
        assert payload.value_template == "{{ value_json.risk_score }}"

    def test_payload_to_discovery_dict_minimal(self) -> None:
        """Test converting minimal payload to discovery dictionary."""
        device = HADeviceInfo(
            identifiers=["hsi_cam1"],
            name="Test Camera",
            model="Camera",
        )

        payload = HADiscoveryPayload(
            component=ComponentType.SENSOR,
            object_id="test_sensor",
            unique_id="test_sensor_unique",
            state_topic="hsi/test",
            device=device,
        )

        result = payload.to_discovery_dict()

        # Verify required fields
        assert result["unique_id"] == "test_sensor_unique"
        assert result["object_id"] == "test_sensor"
        assert result["state_topic"] == "hsi/test"
        assert result["qos"] == 1

        # Verify device info
        assert result["device"]["identifiers"] == ["hsi_cam1"]
        assert result["device"]["name"] == "Test Camera"
        assert result["device"]["manufacturer"] == "HSI"
        assert result["device"]["model"] == "Camera"
        assert result["device"]["via_device"] == "hsi_hub"

    def test_payload_to_discovery_dict_full(self) -> None:
        """Test converting full payload to discovery dictionary."""
        device = HADeviceInfo(
            identifiers=["hsi_cam1"],
            name="Test Camera",
            model="Camera",
            sw_version="1.0.0",
            hw_version="2.0",
        )

        payload = HADiscoveryPayload(
            component=ComponentType.BINARY_SENSOR,
            object_id="test_sensor",
            unique_id="test_sensor_unique",
            name="Test Sensor",
            state_topic="hsi/test",
            command_topic="hsi/test/set",
            device_class=DeviceClass.MOTION,
            icon="mdi:test",
            value_template="{{ value }}",
            availability_topic="hsi/test/status",
            payload_available="online",
            payload_not_available="offline",
            payload_on="detected",
            payload_off="clear",
            qos=2,
            retain=False,
            device=device,
        )

        result = payload.to_discovery_dict()

        # Verify all optional fields are included
        assert result["name"] == "Test Sensor"
        assert result["command_topic"] == "hsi/test/set"
        assert result["device_class"] == "motion"
        assert result["icon"] == "mdi:test"
        assert result["value_template"] == "{{ value }}"
        assert result["availability_topic"] == "hsi/test/status"
        assert result["payload_available"] == "online"
        assert result["payload_not_available"] == "offline"
        assert result["payload_on"] == "detected"
        assert result["payload_off"] == "clear"
        assert result["qos"] == 2

        # Verify device optional fields
        assert result["device"]["sw_version"] == "1.0.0"
        assert result["device"]["hw_version"] == "2.0"

    def test_payload_to_discovery_dict_sensor_no_binary_fields(self) -> None:
        """Test that sensor payload doesn't include binary sensor fields."""
        device = HADeviceInfo(
            identifiers=["hsi_cam1"],
            name="Test Camera",
            model="Camera",
        )

        payload = HADiscoveryPayload(
            component=ComponentType.SENSOR,  # Not binary sensor
            object_id="test_sensor",
            unique_id="test_sensor_unique",
            state_topic="hsi/test",
            device=device,
        )

        result = payload.to_discovery_dict()

        # Binary sensor fields should not be present for regular sensors
        assert "payload_on" not in result
        assert "payload_off" not in result


# =============================================================================
# Test HADiscoveryManager Initialization
# =============================================================================


class TestHADiscoveryManagerInit:
    """Tests for HADiscoveryManager initialization."""

    def test_init_with_settings(
        self,
        mock_mqtt_client: MagicMock,
        ha_settings_enabled: HADiscoverySettings,
    ) -> None:
        """Test initialization with explicit settings."""
        manager = HADiscoveryManager(
            mqtt_client=mock_mqtt_client,
            settings=ha_settings_enabled,
        )

        assert manager._client is mock_mqtt_client
        assert manager._settings.enabled is True
        assert manager._settings.discovery_prefix == "homeassistant"
        assert len(manager._published_entities) == 0

    def test_init_without_settings(self, mock_mqtt_client: MagicMock) -> None:
        """Test initialization with default settings."""
        manager = HADiscoveryManager(mqtt_client=mock_mqtt_client)

        assert manager._client is mock_mqtt_client
        assert manager._settings.enabled is False  # Default is disabled
        assert manager._settings.discovery_prefix == "homeassistant"

    def test_init_custom_prefix(self, mock_mqtt_client: MagicMock) -> None:
        """Test initialization with custom discovery prefix."""
        settings = HADiscoverySettings(
            enabled=True,
            discovery_prefix="custom_ha",
        )
        manager = HADiscoveryManager(
            mqtt_client=mock_mqtt_client,
            settings=settings,
        )

        assert manager._settings.discovery_prefix == "custom_ha"


# =============================================================================
# Test Camera Discovery Publishing
# =============================================================================


class TestPublishCameraDiscovery:
    """Tests for publish_camera_discovery method."""

    @pytest.mark.asyncio
    async def test_publish_camera_discovery_enabled(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test publishing camera discovery when enabled."""
        camera_id = unique_id("cam")
        camera_name = "Front Door Camera"

        await ha_manager.publish_camera_discovery(camera_id, camera_name)

        # Should publish 3 discovery messages: connectivity, motion, risk_score
        assert mock_mqtt_client.publish.call_count == 3

        # Verify topics and payloads
        calls = mock_mqtt_client.publish.call_args_list

        # First call: connectivity binary sensor
        connectivity_call = calls[0]
        assert "binary_sensor" in connectivity_call.kwargs["topic"]
        assert f"hsi_{camera_id}_connectivity" in connectivity_call.kwargs["topic"]
        payload = connectivity_call.kwargs["payload"]
        assert payload["unique_id"] == f"hsi_{camera_id}_connectivity"
        assert payload["state_topic"] == f"hsi/health/cameras/{camera_id}"
        assert payload["device_class"] == "connectivity"
        assert payload["payload_on"] == "online"
        assert payload["payload_off"] == "offline"

        # Second call: motion binary sensor
        motion_call = calls[1]
        assert "binary_sensor" in motion_call.kwargs["topic"]
        assert f"hsi_{camera_id}_motion" in motion_call.kwargs["topic"]
        motion_payload = motion_call.kwargs["payload"]
        assert motion_payload["unique_id"] == f"hsi_{camera_id}_motion"
        assert motion_payload["state_topic"] == f"hsi/detections/{camera_id}/person"
        assert motion_payload["device_class"] == "motion"

        # Third call: risk score sensor
        risk_call = calls[2]
        assert "sensor" in risk_call.kwargs["topic"]
        assert f"hsi_{camera_id}_risk_score" in risk_call.kwargs["topic"]
        risk_payload = risk_call.kwargs["payload"]
        assert risk_payload["unique_id"] == f"hsi_{camera_id}_risk_score"
        assert risk_payload["unit_of_measurement"] == "%"
        assert risk_payload["icon"] == "mdi:alert-circle"

    @pytest.mark.asyncio
    async def test_publish_camera_discovery_disabled(
        self,
        ha_manager_disabled: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test that discovery is not published when disabled."""
        camera_id = unique_id("cam")
        camera_name = "Front Door Camera"

        await ha_manager_disabled.publish_camera_discovery(camera_id, camera_name)

        # Should not publish anything
        mock_mqtt_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_camera_discovery_cameras_disabled(
        self,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test that camera discovery is not published when publish_cameras is False."""
        settings = HADiscoverySettings(
            enabled=True,
            publish_cameras=False,  # Cameras disabled
        )
        manager = HADiscoveryManager(
            mqtt_client=mock_mqtt_client,
            settings=settings,
        )

        camera_id = unique_id("cam")
        await manager.publish_camera_discovery(camera_id, "Test Camera")

        mock_mqtt_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_camera_discovery_custom_prefix(
        self,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test camera discovery with custom device name prefix."""
        settings = HADiscoverySettings(
            enabled=True,
            device_name_prefix="CustomHSI",
        )
        manager = HADiscoveryManager(
            mqtt_client=mock_mqtt_client,
            settings=settings,
        )

        camera_id = unique_id("cam")
        await manager.publish_camera_discovery(camera_id, "Front Door")

        # Verify device name includes custom prefix
        call_args = mock_mqtt_client.publish.call_args_list[0]
        payload = call_args.kwargs["payload"]
        assert payload["device"]["name"] == "CustomHSI Front Door"

    @pytest.mark.asyncio
    async def test_publish_camera_discovery_tracks_entities(
        self,
        ha_manager: HADiscoveryManager,
    ) -> None:
        """Test that published entities are tracked."""
        camera_id = unique_id("cam")
        camera_name = "Front Door Camera"

        assert len(ha_manager._published_entities) == 0

        await ha_manager.publish_camera_discovery(camera_id, camera_name)

        # Should track 3 entities
        assert len(ha_manager._published_entities) == 3
        assert f"hsi_{camera_id}_connectivity" in ha_manager._published_entities
        assert f"hsi_{camera_id}_motion" in ha_manager._published_entities
        assert f"hsi_{camera_id}_risk_score" in ha_manager._published_entities

    @pytest.mark.asyncio
    async def test_publish_camera_discovery_qos_and_retain(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test that discovery messages use correct QoS and retain settings."""
        camera_id = unique_id("cam")
        await ha_manager.publish_camera_discovery(camera_id, "Test Camera")

        # All calls should have QoS 1 and retain=True
        for call_args in mock_mqtt_client.publish.call_args_list:
            assert call_args.kwargs["qos"] == 1
            assert call_args.kwargs["retain"] is True


# =============================================================================
# Test Alert Discovery Publishing
# =============================================================================


class TestPublishAlertDiscovery:
    """Tests for publish_alert_discovery method."""

    @pytest.mark.asyncio
    async def test_publish_alert_discovery_enabled(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test publishing alert discovery when enabled."""
        await ha_manager.publish_alert_discovery(severity="high")

        # Should publish 1 discovery message
        assert mock_mqtt_client.publish.call_count == 1

        call_args = mock_mqtt_client.publish.call_args
        assert "binary_sensor" in call_args.kwargs["topic"]
        assert "hsi_alert_high_active" in call_args.kwargs["topic"]

        payload = call_args.kwargs["payload"]
        assert payload["unique_id"] == "hsi_alert_high_active"
        assert payload["name"] == "High Severity Alert"
        assert payload["state_topic"] == "hsi/alerts/high"
        assert payload["device_class"] == "safety"
        assert payload["payload_on"] == "active"
        assert payload["payload_off"] == "resolved"
        assert payload["device"]["identifiers"] == ["hsi_alerts"]
        assert payload["device"]["model"] == "Alert Engine"

    @pytest.mark.asyncio
    async def test_publish_alert_discovery_disabled(
        self,
        ha_manager_disabled: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test that alert discovery is not published when disabled."""
        await ha_manager_disabled.publish_alert_discovery(severity="high")

        mock_mqtt_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_alert_discovery_alerts_disabled(
        self,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test that alert discovery is not published when publish_alerts is False."""
        settings = HADiscoverySettings(
            enabled=True,
            publish_alerts=False,  # Alerts disabled
        )
        manager = HADiscoveryManager(
            mqtt_client=mock_mqtt_client,
            settings=settings,
        )

        await manager.publish_alert_discovery(severity="high")

        mock_mqtt_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_alert_discovery_different_severities(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test publishing alert discovery for different severity levels."""
        severities = ["low", "medium", "high", "critical"]

        for severity in severities:
            mock_mqtt_client.reset_mock()
            await ha_manager.publish_alert_discovery(severity=severity)

            call_args = mock_mqtt_client.publish.call_args
            payload = call_args.kwargs["payload"]
            assert payload["name"] == f"{severity.title()} Severity Alert"
            assert payload["state_topic"] == f"hsi/alerts/{severity}"
            assert payload["unique_id"] == f"hsi_alert_{severity}_active"


# =============================================================================
# Test System Discovery Publishing
# =============================================================================


class TestPublishSystemDiscovery:
    """Tests for publish_system_discovery method."""

    @pytest.mark.asyncio
    async def test_publish_system_discovery_enabled(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test publishing system discovery when enabled."""
        await ha_manager.publish_system_discovery()

        # Should publish 1 discovery message
        assert mock_mqtt_client.publish.call_count == 1

        call_args = mock_mqtt_client.publish.call_args
        assert "sensor" in call_args.kwargs["topic"]
        assert "hsi_system_health" in call_args.kwargs["topic"]

        payload = call_args.kwargs["payload"]
        assert payload["unique_id"] == "hsi_system_health"
        assert payload["name"] == "System Health"
        assert payload["state_topic"] == "hsi/health/system"
        assert payload["icon"] == "mdi:heart-pulse"
        assert payload["device"]["identifiers"] == ["hsi_hub"]
        assert payload["device"]["model"] == "Home Security Intelligence"

    @pytest.mark.asyncio
    async def test_publish_system_discovery_disabled(
        self,
        ha_manager_disabled: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test that system discovery is not published when disabled."""
        await ha_manager_disabled.publish_system_discovery()

        mock_mqtt_client.publish.assert_not_called()


# =============================================================================
# Test Entity Unpublishing
# =============================================================================


class TestUnpublishEntity:
    """Tests for unpublish_entity method."""

    @pytest.mark.asyncio
    async def test_unpublish_entity_enabled(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test unpublishing an entity sends empty payload."""
        # Add entity to published set
        object_id = "hsi_cam1_motion"
        ha_manager._published_entities.add(object_id)

        await ha_manager.unpublish_entity(
            component=ComponentType.BINARY_SENSOR,
            object_id=object_id,
        )

        # Should publish empty payload to remove entity
        mock_mqtt_client.publish.assert_called_once_with(
            f"homeassistant/binary_sensor/{object_id}/config",
            {},
            qos=1,
            retain=True,
        )

        # Should remove from published entities
        assert object_id not in ha_manager._published_entities

    @pytest.mark.asyncio
    async def test_unpublish_entity_disabled(
        self,
        ha_manager_disabled: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test that unpublish does nothing when discovery is disabled."""
        await ha_manager_disabled.unpublish_entity(
            component=ComponentType.SENSOR,
            object_id="test_sensor",
        )

        mock_mqtt_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_unpublish_entity_custom_prefix(
        self,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test unpublishing entity with custom discovery prefix."""
        settings = HADiscoverySettings(
            enabled=True,
            discovery_prefix="custom_ha",
        )
        manager = HADiscoveryManager(
            mqtt_client=mock_mqtt_client,
            settings=settings,
        )

        await manager.unpublish_entity(
            component=ComponentType.SENSOR,
            object_id="test_sensor",
        )

        # Verify custom prefix is used
        call_args = mock_mqtt_client.publish.call_args
        assert call_args[0][0] == "custom_ha/sensor/test_sensor/config"

    @pytest.mark.asyncio
    async def test_unpublish_nonexistent_entity(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test unpublishing an entity that was never published."""
        object_id = "nonexistent_sensor"

        # Entity not in published set
        assert object_id not in ha_manager._published_entities

        # Should still publish empty config (idempotent)
        await ha_manager.unpublish_entity(
            component=ComponentType.SENSOR,
            object_id=object_id,
        )

        mock_mqtt_client.publish.assert_called_once()


# =============================================================================
# Test MQTT Error Handling
# =============================================================================


class TestMQTTErrorHandling:
    """Tests for error handling during MQTT operations."""

    @pytest.mark.asyncio
    async def test_publish_camera_discovery_mqtt_error(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test handling of MQTT publish errors during camera discovery."""
        # Make publish raise an exception
        mock_mqtt_client.publish.side_effect = Exception("MQTT connection lost")

        camera_id = unique_id("cam")

        # Should raise the exception (no error suppression)
        with pytest.raises(Exception, match="MQTT connection lost"):
            await ha_manager.publish_camera_discovery(camera_id, "Test Camera")

    @pytest.mark.asyncio
    async def test_publish_alert_discovery_mqtt_error(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test handling of MQTT publish errors during alert discovery."""
        mock_mqtt_client.publish.side_effect = Exception("MQTT timeout")

        with pytest.raises(Exception, match="MQTT timeout"):
            await ha_manager.publish_alert_discovery(severity="high")

    @pytest.mark.asyncio
    async def test_unpublish_entity_mqtt_error(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test handling of MQTT publish errors during entity unpublish."""
        mock_mqtt_client.publish.side_effect = Exception("MQTT broker unavailable")

        with pytest.raises(Exception, match="MQTT broker unavailable"):
            await ha_manager.unpublish_entity(
                component=ComponentType.SENSOR,
                object_id="test_sensor",
            )


# =============================================================================
# Test Discovery Topic Construction
# =============================================================================


class TestDiscoveryTopicConstruction:
    """Tests for MQTT discovery topic construction."""

    @pytest.mark.asyncio
    async def test_default_discovery_prefix(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test discovery topics use default homeassistant prefix."""
        camera_id = unique_id("cam")
        await ha_manager.publish_camera_discovery(camera_id, "Test Camera")

        # All topics should start with homeassistant/
        for call_args in mock_mqtt_client.publish.call_args_list:
            topic = call_args.kwargs["topic"]
            assert topic.startswith("homeassistant/")

    @pytest.mark.asyncio
    async def test_custom_discovery_prefix(
        self,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test discovery topics use custom prefix when configured."""
        settings = HADiscoverySettings(
            enabled=True,
            discovery_prefix="my_custom_ha",
        )
        manager = HADiscoveryManager(
            mqtt_client=mock_mqtt_client,
            settings=settings,
        )

        camera_id = unique_id("cam")
        await manager.publish_camera_discovery(camera_id, "Test Camera")

        # All topics should start with custom prefix
        for call_args in mock_mqtt_client.publish.call_args_list:
            topic = call_args.kwargs["topic"]
            assert topic.startswith("my_custom_ha/")

    @pytest.mark.asyncio
    async def test_topic_structure(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test discovery topic follows HA format: prefix/component/object_id/config."""
        camera_id = unique_id("cam")
        await ha_manager.publish_camera_discovery(camera_id, "Test Camera")

        # Check connectivity sensor topic structure
        connectivity_topic = mock_mqtt_client.publish.call_args_list[0].kwargs["topic"]
        parts = connectivity_topic.split("/")
        assert len(parts) == 4
        assert parts[0] == "homeassistant"
        assert parts[1] == "binary_sensor"
        assert parts[2] == f"hsi_{camera_id}_connectivity"
        assert parts[3] == "config"


# =============================================================================
# Test Integration Scenarios
# =============================================================================


class TestIntegrationScenarios:
    """Tests for realistic integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_camera_setup(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test complete camera setup with multiple cameras."""
        cameras = [
            (unique_id("cam1"), "Front Door"),
            (unique_id("cam2"), "Back Yard"),
            (unique_id("cam3"), "Driveway"),
        ]

        for camera_id, camera_name in cameras:
            await ha_manager.publish_camera_discovery(camera_id, camera_name)

        # Should publish 3 entities per camera (3 cameras * 3 entities = 9 total)
        assert mock_mqtt_client.publish.call_count == 9
        assert len(ha_manager._published_entities) == 9

    @pytest.mark.asyncio
    async def test_full_alert_setup(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test complete alert setup with all severity levels."""
        severities = ["low", "medium", "high", "critical"]

        for severity in severities:
            await ha_manager.publish_alert_discovery(severity=severity)

        # Should publish 4 alert entities
        assert mock_mqtt_client.publish.call_count == 4
        assert len(ha_manager._published_entities) == 4

    @pytest.mark.asyncio
    async def test_mixed_entity_types(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test publishing different entity types together."""
        camera_id = unique_id("cam")

        # Publish camera, alert, and system discovery
        await ha_manager.publish_camera_discovery(camera_id, "Front Door")
        await ha_manager.publish_alert_discovery(severity="high")
        await ha_manager.publish_system_discovery()

        # Camera: 3, Alert: 1, System: 1 = 5 total
        assert mock_mqtt_client.publish.call_count == 5

    @pytest.mark.asyncio
    async def test_republish_same_entity(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test republishing the same entity updates configuration."""
        camera_id = unique_id("cam")

        # Publish twice
        await ha_manager.publish_camera_discovery(camera_id, "Front Door")
        initial_count = mock_mqtt_client.publish.call_count

        await ha_manager.publish_camera_discovery(camera_id, "Front Door Updated")

        # Should publish again (update)
        assert mock_mqtt_client.publish.call_count == initial_count * 2

        # Entity tracking should not duplicate
        assert len(ha_manager._published_entities) == 3

    @pytest.mark.asyncio
    async def test_camera_removal_workflow(
        self,
        ha_manager: HADiscoveryManager,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test complete workflow of adding and removing a camera."""
        camera_id = unique_id("cam")
        camera_name = "Front Door"

        # Add camera
        await ha_manager.publish_camera_discovery(camera_id, camera_name)
        assert len(ha_manager._published_entities) == 3

        mock_mqtt_client.reset_mock()

        # Remove all camera entities
        await ha_manager.unpublish_entity(
            ComponentType.BINARY_SENSOR,
            f"hsi_{camera_id}_connectivity",
        )
        await ha_manager.unpublish_entity(
            ComponentType.BINARY_SENSOR,
            f"hsi_{camera_id}_motion",
        )
        await ha_manager.unpublish_entity(
            ComponentType.SENSOR,
            f"hsi_{camera_id}_risk_score",
        )

        # Should send 3 empty configs
        assert mock_mqtt_client.publish.call_count == 3
        assert len(ha_manager._published_entities) == 0
