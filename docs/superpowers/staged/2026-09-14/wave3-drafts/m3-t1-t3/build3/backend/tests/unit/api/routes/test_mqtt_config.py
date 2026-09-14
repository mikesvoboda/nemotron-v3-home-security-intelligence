"""Unit tests for MQTT Configuration UI API.

Tests the REST API endpoints for managing MQTT broker connections,
publisher settings, and integration options.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from backend.api.routes.mqtt_config import router
from backend.api.schemas.mqtt_config import (
    MqttBrokerConfig,
    MqttBrokerConfigUpdate,
    MqttConfigUpdate,
    MqttIntegrationConfigUpdate,
    MqttPublisherConfig,
    MqttQoS,
)
from backend.tests.unit.conftest import get_auth_headers


def create_test_app() -> FastAPI:
    """Create a test FastAPI app with the MQTT config router."""
    app = FastAPI()
    app.include_router(router)
    return app


# =============================================================================
# Schema Tests
# =============================================================================


class TestMqttBrokerConfigSchema:
    """Tests for MqttBrokerConfig Pydantic schema."""

    def test_valid_broker_config(self):
        """Test valid broker config parses correctly."""
        config = MqttBrokerConfig(
            host="mqtt.example.com",
            port=1883,
            username="user",
            password="secret",  # pragma: allowlist secret
            use_tls=False,
            client_id="test-client",
        )
        assert config.host == "mqtt.example.com"
        assert config.port == 1883
        assert config.username == "user"
        assert config.password == "secret"  # pragma: allowlist secret

    def test_default_values(self):
        """Test default values are applied."""
        config = MqttBrokerConfig()
        assert config.host == "localhost"
        assert config.port == 1883
        assert config.username is None
        assert config.password is None
        assert config.use_tls is False
        assert config.client_id == "home-security-backend"

    def test_invalid_port_too_low(self):
        """Test port validation rejects port below 1."""
        with pytest.raises(ValidationError) as exc_info:
            MqttBrokerConfig(port=0)
        assert "port" in str(exc_info.value)

    def test_invalid_port_too_high(self):
        """Test port validation rejects port above 65535."""
        with pytest.raises(ValidationError) as exc_info:
            MqttBrokerConfig(port=65536)
        assert "port" in str(exc_info.value)

    def test_empty_host_rejected(self):
        """Test empty host is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MqttBrokerConfig(host="")
        assert "host" in str(exc_info.value)


class TestMqttPublisherConfigSchema:
    """Tests for MqttPublisherConfig Pydantic schema."""

    def test_valid_publisher_config(self):
        """Test valid publisher config parses correctly."""
        config = MqttPublisherConfig(
            topic_prefix="home-security",
            qos=1,
            retain=True,
        )
        assert config.topic_prefix == "home-security"
        assert config.qos == 1
        assert config.retain is True

    def test_default_values(self):
        """Test default values are applied."""
        config = MqttPublisherConfig()
        assert config.topic_prefix == "home-security"
        assert config.qos == 1
        assert config.retain is False

    def test_invalid_qos_value(self):
        """Test QoS validation rejects invalid values."""
        with pytest.raises(ValidationError) as exc_info:
            MqttPublisherConfig(qos=3)
        assert "qos" in str(exc_info.value).lower()

    def test_qos_enum_values(self):
        """Test QoS enum values."""
        assert MqttQoS.AT_MOST_ONCE == 0
        assert MqttQoS.AT_LEAST_ONCE == 1
        assert MqttQoS.EXACTLY_ONCE == 2


class TestMqttConfigUpdateSchema:
    """Tests for MqttConfigUpdate Pydantic schema."""

    def test_partial_update_broker_only(self):
        """Test partial update with only broker settings."""
        update = MqttConfigUpdate(
            broker=MqttBrokerConfigUpdate(host="new-host.com", port=8883),
        )
        assert update.broker is not None
        assert update.broker.host == "new-host.com"
        assert update.publisher is None
        assert update.integration is None

    def test_partial_update_integration_only(self):
        """Test partial update with only integration settings."""
        update = MqttConfigUpdate(
            integration=MqttIntegrationConfigUpdate(enabled=True),
        )
        assert update.broker is None
        assert update.publisher is None
        assert update.integration is not None
        assert update.integration.enabled is True

    def test_empty_update_is_valid(self):
        """Test empty update is valid."""
        update = MqttConfigUpdate()
        assert update.broker is None
        assert update.publisher is None
        assert update.integration is None


# =============================================================================
# GET /api/mqtt-config Tests
# =============================================================================


class TestGetMqttConfigEndpoint:
    """Tests for GET /api/mqtt-config endpoint."""

    @pytest.mark.asyncio
    async def test_get_config_returns_defaults(self):
        """Test getting config with no saved settings returns defaults."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=get_auth_headers(),
        ) as client:
            response = await client.get("/api/mqtt-config")

        assert response.status_code == 200
        data = response.json()
        assert data["broker"]["host"] == "localhost"
        assert data["broker"]["port"] == 1883
        assert data["broker"]["password"] is None
        assert data["integration"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_get_config_password_not_returned(self):
        """Test that password is never returned in GET response."""
        from backend.core.database import get_db

        app = create_test_app()

        now = datetime.now(UTC)
        mock_setting = MagicMock(
            key="mqtt_config",
            value={
                "broker": {
                    "host": "mqtt.example.com",
                    "port": 1883,
                    "password": "super-secret-password",  # pragma: allowlist secret
                },
            },
            updated_at=now,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_setting
        mock_db.execute.return_value = mock_result

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=get_auth_headers(),
        ) as client:
            response = await client.get("/api/mqtt-config")

        assert response.status_code == 200
        data = response.json()
        assert data["broker"]["password"] is None

    @pytest.mark.asyncio
    async def test_get_config_returns_saved_settings(self):
        """Test getting config returns saved settings."""
        from backend.core.database import get_db

        app = create_test_app()

        now = datetime.now(UTC)
        mock_setting = MagicMock(
            key="mqtt_config",
            value={
                "broker": {
                    "host": "custom-host.com",
                    "port": 8883,
                    "use_tls": True,
                },
                "publisher": {
                    "topic_prefix": "custom-prefix",
                    "qos": 2,
                },
                "integration": {
                    "enabled": True,
                    "publish_events": True,
                },
            },
            updated_at=now,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_setting
        mock_db.execute.return_value = mock_result

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=get_auth_headers(),
        ) as client:
            response = await client.get("/api/mqtt-config")

        assert response.status_code == 200
        data = response.json()
        assert data["broker"]["host"] == "custom-host.com"
        assert data["broker"]["port"] == 8883
        assert data["broker"]["use_tls"] is True
        assert data["publisher"]["topic_prefix"] == "custom-prefix"
        assert data["publisher"]["qos"] == 2
        assert data["integration"]["enabled"] is True


# =============================================================================
# PUT /api/mqtt-config Tests
# =============================================================================


class TestUpdateMqttConfigEndpoint:
    """Tests for PUT /api/mqtt-config endpoint."""

    @pytest.mark.asyncio
    async def test_update_broker_settings(self):
        """Test updating broker settings."""
        from backend.core.database import get_db

        app = create_test_app()

        now = datetime.now(UTC)
        mock_setting = MagicMock(
            key="mqtt_config",
            value={
                "broker": {"host": "old-host.com"},
            },
            updated_at=now,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_setting
        mock_db.execute.return_value = mock_result

        async def mock_refresh(obj):
            obj.updated_at = datetime.now(UTC)

        mock_db.refresh = mock_refresh

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=get_auth_headers(),
        ) as client:
            response = await client.put(
                "/api/mqtt-config",
                json={"broker": {"host": "new-host.com", "port": 8883}},
            )

        assert response.status_code == 200
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_publisher_settings(self):
        """Test updating publisher settings."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_setting = MagicMock(
            key="mqtt_config",
            value={},
            updated_at=datetime.now(UTC),
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_setting
        mock_db.execute.return_value = mock_result

        async def mock_refresh(obj):
            obj.updated_at = datetime.now(UTC)

        mock_db.refresh = mock_refresh

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=get_auth_headers(),
        ) as client:
            response = await client.put(
                "/api/mqtt-config",
                json={"publisher": {"topic_prefix": "new-prefix", "qos": 2}},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["publisher"]["topic_prefix"] == "new-prefix"
        assert data["publisher"]["qos"] == 2

    @pytest.mark.asyncio
    async def test_update_integration_settings(self):
        """Test updating integration settings."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_setting = MagicMock(
            key="mqtt_config",
            value={},
            updated_at=datetime.now(UTC),
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_setting
        mock_db.execute.return_value = mock_result

        async def mock_refresh(obj):
            obj.updated_at = datetime.now(UTC)

        mock_db.refresh = mock_refresh

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=get_auth_headers(),
        ) as client:
            response = await client.put(
                "/api/mqtt-config",
                json={"integration": {"enabled": True, "publish_detections": True}},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["integration"]["enabled"] is True
        assert data["integration"]["publish_detections"] is True

    @pytest.mark.asyncio
    async def test_update_invalid_port_returns_422(self):
        """Test updating with invalid port returns 422."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_db = AsyncMock()

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=get_auth_headers(),
        ) as client:
            response = await client.put(
                "/api/mqtt-config",
                json={"broker": {"port": 99999}},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_invalid_qos_returns_422(self):
        """Test updating with invalid QoS returns 422."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_db = AsyncMock()

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=get_auth_headers(),
        ) as client:
            response = await client.put(
                "/api/mqtt-config",
                json={"publisher": {"qos": 5}},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_empty_host_returns_422(self):
        """Test updating with empty host returns 422."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_db = AsyncMock()

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=get_auth_headers(),
        ) as client:
            response = await client.put(
                "/api/mqtt-config",
                json={"broker": {"host": ""}},
            )

        assert response.status_code == 422


# =============================================================================
# GET /api/mqtt-config/status Tests
# =============================================================================


class TestGetMqttStatusEndpoint:
    """Tests for GET /api/mqtt-config/status endpoint."""

    @pytest.mark.asyncio
    async def test_get_status_returns_connection_state(self):
        """Test getting status returns connection state."""
        from backend.api.routes import mqtt_config as mqtt_module
        from backend.core.database import get_db

        app = create_test_app()

        # Set up mock connection state
        mqtt_module._mqtt_connection_state = {
            "connected": True,
            "last_connected_at": datetime.now(UTC),
            "last_error": None,
            "last_error_at": None,
            "messages_published": 100,
        }

        mock_setting = MagicMock(
            value={"broker": {"host": "mqtt.test.com", "port": 1883}},
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_setting
        mock_db.execute.return_value = mock_result

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=get_auth_headers(),
        ) as client:
            response = await client.get("/api/mqtt-config/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["messages_published"] == 100
        assert data["broker_host"] == "mqtt.test.com"
        assert data["broker_port"] == 1883


# =============================================================================
# POST /api/mqtt-config/test Tests
# =============================================================================


class TestMqttTestEndpoint:
    """Tests for POST /api/mqtt-config/test endpoint."""

    @pytest.mark.asyncio
    async def test_test_connection_with_saved_config(self):
        """Test connection test using saved configuration."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_setting = MagicMock(
            value={"broker": {"host": "localhost", "port": 1883}},
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_setting
        mock_db.execute.return_value = mock_result

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        with patch("socket.socket") as mock_socket:
            mock_sock_instance = MagicMock()
            mock_socket.return_value = mock_sock_instance

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers=get_auth_headers(),
            ) as client:
                response = await client.post(
                    "/api/mqtt-config/test",
                    json={"use_saved_config": True},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "localhost:1883" in data["message"]

    @pytest.mark.asyncio
    async def test_test_connection_with_override(self):
        """Test connection test with configuration override."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_db = AsyncMock()

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        with patch("socket.socket") as mock_socket:
            mock_sock_instance = MagicMock()
            mock_socket.return_value = mock_sock_instance

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers=get_auth_headers(),
            ) as client:
                response = await client.post(
                    "/api/mqtt-config/test",
                    json={
                        "use_saved_config": False,
                        "broker_override": {
                            "host": "test-broker.com",
                            "port": 8883,
                        },
                    },
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "test-broker.com:8883" in data["message"]

    @pytest.mark.asyncio
    async def test_test_connection_override_required(self):
        """Test that broker_override is required when use_saved_config is False."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_db = AsyncMock()

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=get_auth_headers(),
        ) as client:
            response = await client.post(
                "/api/mqtt-config/test",
                json={"use_saved_config": False},
            )

        assert response.status_code == 400
        assert "broker_override is required" in response.json()["detail"]


# =============================================================================
# POST /api/mqtt-config/reconnect Tests
# =============================================================================


class TestMqttReconnectEndpoint:
    """Tests for POST /api/mqtt-config/reconnect endpoint."""

    @pytest.mark.asyncio
    async def test_reconnect_success(self):
        """Test successful reconnection."""
        from backend.api.routes import mqtt_config as mqtt_module
        from backend.core.database import get_db

        app = create_test_app()

        mqtt_module._mqtt_connection_state = {
            "connected": False,
            "last_connected_at": None,
            "last_error": None,
            "last_error_at": None,
            "messages_published": 0,
        }

        mock_setting = MagicMock(
            value={
                "broker": {"host": "localhost", "port": 1883},
                "integration": {"enabled": True},
            },
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_setting
        mock_db.execute.return_value = mock_result

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        with patch("socket.socket") as mock_socket:
            mock_sock_instance = MagicMock()
            mock_socket.return_value = mock_sock_instance

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers=get_auth_headers(),
            ) as client:
                response = await client.post("/api/mqtt-config/reconnect")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["previous_state"] == "disconnected"
        assert data["new_state"] == "connected"

    @pytest.mark.asyncio
    async def test_reconnect_when_disabled(self):
        """Test reconnect when MQTT is disabled."""
        from backend.api.routes import mqtt_config as mqtt_module
        from backend.core.database import get_db

        app = create_test_app()

        mqtt_module._mqtt_connection_state = {"connected": False}

        mock_setting = MagicMock(
            value={
                "broker": {"host": "localhost", "port": 1883},
                "integration": {"enabled": False},
            },
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_setting
        mock_db.execute.return_value = mock_result

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=get_auth_headers(),
        ) as client:
            response = await client.post("/api/mqtt-config/reconnect")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "disabled" in data["message"]


# =============================================================================
# POST /api/mqtt-config/disconnect Tests
# =============================================================================


class TestMqttDisconnectEndpoint:
    """Tests for POST /api/mqtt-config/disconnect endpoint."""

    @pytest.mark.asyncio
    async def test_disconnect_when_connected(self):
        """Test disconnecting when connected."""
        from backend.api.routes import mqtt_config as mqtt_module

        app = create_test_app()

        mqtt_module._mqtt_connection_state = {
            "connected": True,
            "last_connected_at": datetime.now(UTC),
            "last_error": None,
            "last_error_at": None,
            "messages_published": 50,
        }

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=get_auth_headers(),
        ) as client:
            response = await client.post("/api/mqtt-config/disconnect")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["was_connected"] is True
        assert mqtt_module._mqtt_connection_state["connected"] is False

    @pytest.mark.asyncio
    async def test_disconnect_when_already_disconnected(self):
        """Test disconnecting when already disconnected."""
        from backend.api.routes import mqtt_config as mqtt_module

        app = create_test_app()

        mqtt_module._mqtt_connection_state = {
            "connected": False,
            "last_connected_at": None,
            "last_error": None,
            "last_error_at": None,
            "messages_published": 0,
        }

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=get_auth_headers(),
        ) as client:
            response = await client.post("/api/mqtt-config/disconnect")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["was_connected"] is False
        assert "Already disconnected" in data["message"]
