"""Unit tests for MonitoringStackValidator service.

Tests cover:
- Prometheus connectivity validation
- Prometheus scrape target health checks
- Grafana connectivity and health checks
- Dashboard availability verification
- Alerting rules validation
- Combined health check endpoint
- Error handling and edge cases

TDD: These tests are written FIRST, before implementing the MonitoringStackValidator.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.monitoring_stack_validator import (
    AlertingRulesStatus,
    GrafanaStatus,
    MonitoringStackHealth,
    MonitoringStackValidator,
    PrometheusStatus,
    ScrapeTarget,
    ScrapeTargetHealth,
)

# =============================================================================
# Test Configuration and Fixtures
# =============================================================================


@pytest.fixture
def mock_http_client() -> MagicMock:
    """Create a mock HTTP client."""
    client = MagicMock()
    client.get = AsyncMock()
    client.is_closed = False
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings with monitoring URLs."""
    settings = MagicMock()
    settings.prometheus_url = "http://prometheus:9090"
    settings.grafana_url = "http://grafana:3000"
    return settings


@pytest.fixture
def validator(mock_settings: MagicMock) -> MonitoringStackValidator:
    """Create a MonitoringStackValidator with mocked settings."""
    with patch(
        "backend.services.monitoring_stack_validator.get_settings",
        return_value=mock_settings,
    ):
        return MonitoringStackValidator()


@pytest.fixture
def prometheus_targets_response() -> dict[str, Any]:
    """Create a sample Prometheus /api/v1/targets response."""
    return {
        "status": "success",
        "data": {
            "activeTargets": [
                {
                    "discoveredLabels": {"__address__": "backend:8000"},
                    "labels": {"job": "hsi-backend-metrics", "instance": "backend:8000"},
                    "scrapePool": "hsi-backend-metrics",
                    "scrapeUrl": "http://backend:8000/api/metrics",
                    "globalUrl": "http://backend:8000/api/metrics",
                    "lastError": "",
                    "lastScrape": "2024-01-15T10:30:00.000Z",
                    "lastScrapeDuration": 0.015,
                    "health": "up",
                    "scrapeInterval": "15s",
                    "scrapeTimeout": "10s",
                },
                {
                    "discoveredLabels": {"__address__": "redis-exporter:9121"},
                    "labels": {"job": "redis", "instance": "redis-exporter:9121"},
                    "scrapePool": "redis",
                    "scrapeUrl": "http://redis-exporter:9121/metrics",
                    "globalUrl": "http://redis-exporter:9121/metrics",
                    "lastError": "connection refused",
                    "lastScrape": "2024-01-15T10:29:45.000Z",
                    "lastScrapeDuration": 0.0,
                    "health": "down",
                    "scrapeInterval": "15s",
                    "scrapeTimeout": "10s",
                },
            ],
            "droppedTargets": [],
        },
    }


@pytest.fixture
def prometheus_rules_response() -> dict[str, Any]:
    """Create a sample Prometheus /api/v1/rules response."""
    return {
        "status": "success",
        "data": {
            "groups": [
                {
                    "name": "ai_pipeline_alerts",
                    "file": "/etc/prometheus/prometheus_rules.yml",
                    "rules": [
                        {
                            "state": "inactive",
                            "name": "DetectionQueueHigh",
                            "query": "detection_queue_depth > 100",
                            "duration": 300,
                            "labels": {"severity": "warning"},
                            "annotations": {"summary": "Detection queue is high"},
                            "alerts": [],
                            "health": "ok",
                            "type": "alerting",
                        },
                        {
                            "state": "inactive",
                            "name": "NemotronUnhealthy",
                            "query": 'up{job="nemotron"} == 0',
                            "duration": 60,
                            "labels": {"severity": "critical"},
                            "annotations": {"summary": "Nemotron service is down"},
                            "alerts": [],
                            "health": "ok",
                            "type": "alerting",
                        },
                    ],
                    "interval": 15,
                    "evaluationTime": 0.001,
                    "lastEvaluation": "2024-01-15T10:30:00.000Z",
                },
            ],
        },
    }


@pytest.fixture
def grafana_health_response() -> dict[str, Any]:
    """Create a sample Grafana /api/health response."""
    return {"commit": "abc123", "database": "ok", "version": "10.2.3"}


@pytest.fixture
def grafana_dashboards_response() -> list[dict[str, Any]]:
    """Create a sample Grafana /api/search response for dashboards."""
    return [
        {
            "id": 1,
            "uid": "ai-pipeline-dashboard",
            "title": "AI Pipeline Dashboard",
            "type": "dash-db",
            "folderTitle": "Home Security",
        },
        {
            "id": 2,
            "uid": "system-overview",
            "title": "System Overview",
            "type": "dash-db",
            "folderTitle": "Home Security",
        },
    ]


# =============================================================================
# Helper for async mock setup
# =============================================================================


def create_mock_response(status_code: int, json_data: Any) -> MagicMock:
    """Create a mock HTTP response with the given status code and JSON data."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_data
    return mock_response


# =============================================================================
# MonitoringStackValidator.__init__() Tests
# =============================================================================


class TestMonitoringStackValidatorInit:
    """Tests for MonitoringStackValidator initialization."""

    def test_init_creates_instance(self, validator: MonitoringStackValidator) -> None:
        """Test initialization creates a valid instance."""
        assert validator is not None
        assert isinstance(validator, MonitoringStackValidator)

    def test_init_loads_settings(self, mock_settings: MagicMock) -> None:
        """Test initialization loads settings."""
        with patch(
            "backend.services.monitoring_stack_validator.get_settings",
            return_value=mock_settings,
        ):
            validator = MonitoringStackValidator()
            assert validator._prometheus_url == "http://prometheus:9090"
            assert validator._grafana_url == "http://grafana:3000"

    def test_init_with_custom_urls(self) -> None:
        """Test initialization with custom URLs."""
        validator = MonitoringStackValidator(
            prometheus_url="http://custom-prom:9090",
            grafana_url="http://custom-grafana:3000",
        )
        assert validator._prometheus_url == "http://custom-prom:9090"
        assert validator._grafana_url == "http://custom-grafana:3000"


# =============================================================================
# Prometheus Validation Tests
# =============================================================================


class TestPrometheusValidation:
    """Tests for Prometheus connectivity and health validation."""

    @pytest.mark.asyncio
    async def test_check_prometheus_healthy(
        self,
        validator: MonitoringStackValidator,
        mock_http_client: MagicMock,
        prometheus_targets_response: dict[str, Any],
    ) -> None:
        """Test check_prometheus returns healthy status when Prometheus is up."""
        mock_response = create_mock_response(200, prometheus_targets_response)
        mock_http_client.get = AsyncMock(return_value=mock_response)

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            result = await validator.check_prometheus()

        assert result.healthy is True
        assert result.reachable is True
        assert result.total_targets == 2
        assert result.targets_up == 1
        assert result.targets_down == 1

    @pytest.mark.asyncio
    async def test_check_prometheus_unreachable(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """Test check_prometheus returns unhealthy when Prometheus is unreachable."""
        mock_http_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            result = await validator.check_prometheus()

        assert result.healthy is False
        assert result.reachable is False
        assert result.error is not None
        assert "Connection refused" in result.error

    @pytest.mark.asyncio
    async def test_check_prometheus_non_200_response(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """Test check_prometheus handles non-200 response."""
        mock_response = create_mock_response(503, {})
        mock_http_client.get = AsyncMock(return_value=mock_response)

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            result = await validator.check_prometheus()

        assert result.healthy is False
        assert result.reachable is False
        assert result.error is not None


class TestScrapeTargetsValidation:
    """Tests for Prometheus scrape targets validation."""

    @pytest.mark.asyncio
    async def test_get_scrape_targets(
        self,
        validator: MonitoringStackValidator,
        mock_http_client: MagicMock,
        prometheus_targets_response: dict[str, Any],
    ) -> None:
        """Test get_scrape_targets returns target list."""
        mock_response = create_mock_response(200, prometheus_targets_response)
        mock_http_client.get = AsyncMock(return_value=mock_response)

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            targets = await validator.get_scrape_targets()

        assert len(targets) == 2
        assert targets[0].job == "hsi-backend-metrics"
        assert targets[0].health == ScrapeTargetHealth.UP
        assert targets[1].job == "redis"
        assert targets[1].health == ScrapeTargetHealth.DOWN
        assert targets[1].last_error == "connection refused"

    @pytest.mark.asyncio
    async def test_get_scrape_targets_empty(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """Test get_scrape_targets handles empty target list."""
        mock_response = create_mock_response(
            200,
            {"status": "success", "data": {"activeTargets": [], "droppedTargets": []}},
        )
        mock_http_client.get = AsyncMock(return_value=mock_response)

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            targets = await validator.get_scrape_targets()

        assert len(targets) == 0

    @pytest.mark.asyncio
    async def test_get_scrape_targets_error(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """Test get_scrape_targets handles errors gracefully."""
        mock_http_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            targets = await validator.get_scrape_targets()

        assert len(targets) == 0


# =============================================================================
# Alerting Rules Validation Tests
# =============================================================================


class TestAlertingRulesValidation:
    """Tests for Prometheus alerting rules validation."""

    @pytest.mark.asyncio
    async def test_check_alerting_rules_loaded(
        self,
        validator: MonitoringStackValidator,
        mock_http_client: MagicMock,
        prometheus_rules_response: dict[str, Any],
    ) -> None:
        """Test check_alerting_rules returns healthy when rules are loaded."""
        mock_response = create_mock_response(200, prometheus_rules_response)
        mock_http_client.get = AsyncMock(return_value=mock_response)

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            result = await validator.check_alerting_rules()

        assert result.loaded is True
        assert result.total_rules == 2
        assert result.healthy_rules == 2
        assert result.unhealthy_rules == 0
        assert len(result.rule_groups) == 1

    @pytest.mark.asyncio
    async def test_check_alerting_rules_no_rules(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """Test check_alerting_rules handles no rules."""
        mock_response = create_mock_response(200, {"status": "success", "data": {"groups": []}})
        mock_http_client.get = AsyncMock(return_value=mock_response)

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            result = await validator.check_alerting_rules()

        assert result.loaded is True
        assert result.total_rules == 0

    @pytest.mark.asyncio
    async def test_check_alerting_rules_error(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """Test check_alerting_rules handles errors."""
        mock_http_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            result = await validator.check_alerting_rules()

        assert result.loaded is False
        assert result.error is not None


# =============================================================================
# Grafana Validation Tests
# =============================================================================


class TestGrafanaValidation:
    """Tests for Grafana connectivity and health validation."""

    @pytest.mark.asyncio
    async def test_check_grafana_healthy(
        self,
        validator: MonitoringStackValidator,
        mock_http_client: MagicMock,
        grafana_health_response: dict[str, Any],
        grafana_dashboards_response: list[dict[str, Any]],
    ) -> None:
        """Test check_grafana returns healthy status."""
        health_response = create_mock_response(200, grafana_health_response)
        dashboards_response = create_mock_response(200, grafana_dashboards_response)

        # Mock get to return different responses based on call order
        mock_http_client.get = AsyncMock(side_effect=[health_response, dashboards_response])

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            result = await validator.check_grafana()

        assert result.healthy is True
        assert result.reachable is True
        assert result.version == "10.2.3"
        assert result.database_status == "ok"
        assert result.dashboard_count == 2

    @pytest.mark.asyncio
    async def test_check_grafana_unreachable(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """Test check_grafana returns unhealthy when Grafana is unreachable."""
        mock_http_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            result = await validator.check_grafana()

        assert result.healthy is False
        assert result.reachable is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_check_grafana_database_unhealthy(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """Test check_grafana reports unhealthy when database is not ok."""
        health_response = create_mock_response(200, {"database": "error", "version": "10.2.3"})
        dashboards_response = create_mock_response(200, [])

        mock_http_client.get = AsyncMock(side_effect=[health_response, dashboards_response])

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            result = await validator.check_grafana()

        assert result.healthy is False
        assert result.reachable is True
        assert result.database_status == "error"


class TestDashboardValidation:
    """Tests for Grafana dashboard availability validation."""

    @pytest.mark.asyncio
    async def test_get_dashboards(
        self,
        validator: MonitoringStackValidator,
        mock_http_client: MagicMock,
        grafana_dashboards_response: list[dict[str, Any]],
    ) -> None:
        """Test get_dashboards returns dashboard list."""
        mock_response = create_mock_response(200, grafana_dashboards_response)
        mock_http_client.get = AsyncMock(return_value=mock_response)

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            dashboards = await validator.get_dashboards()

        assert len(dashboards) == 2
        assert dashboards[0]["title"] == "AI Pipeline Dashboard"
        assert dashboards[1]["title"] == "System Overview"

    @pytest.mark.asyncio
    async def test_get_dashboards_empty(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """Test get_dashboards handles no dashboards."""
        mock_response = create_mock_response(200, [])
        mock_http_client.get = AsyncMock(return_value=mock_response)

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            dashboards = await validator.get_dashboards()

        assert len(dashboards) == 0

    @pytest.mark.asyncio
    async def test_get_dashboards_error(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """Test get_dashboards handles errors gracefully."""
        mock_http_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            dashboards = await validator.get_dashboards()

        assert len(dashboards) == 0


# =============================================================================
# Combined Health Check Tests
# =============================================================================


class TestCombinedHealthCheck:
    """Tests for combined monitoring stack health check."""

    @pytest.mark.asyncio
    async def test_check_health_all_healthy(self, validator: MonitoringStackValidator) -> None:
        """Test check_health returns healthy when all components are healthy."""
        prometheus_status = PrometheusStatus(
            healthy=True,
            reachable=True,
            total_targets=5,
            targets_up=5,
            targets_down=0,
        )
        grafana_status = GrafanaStatus(
            healthy=True,
            reachable=True,
            version="10.2.3",
            database_status="ok",
            dashboard_count=3,
        )
        alerting_status = AlertingRulesStatus(
            loaded=True,
            total_rules=10,
            healthy_rules=10,
            unhealthy_rules=0,
            rule_groups=["alerts"],
        )

        with (
            patch.object(validator, "check_prometheus", return_value=prometheus_status),
            patch.object(validator, "check_grafana", return_value=grafana_status),
            patch.object(validator, "check_alerting_rules", return_value=alerting_status),
        ):
            result = await validator.check_health()

        assert result.healthy is True
        assert result.prometheus.healthy is True
        assert result.grafana.healthy is True
        assert result.alerting_rules.loaded is True

    @pytest.mark.asyncio
    async def test_check_health_prometheus_unhealthy(
        self, validator: MonitoringStackValidator
    ) -> None:
        """Test check_health returns unhealthy when Prometheus is unhealthy."""
        prometheus_status = PrometheusStatus(
            healthy=False,
            reachable=False,
            error="Connection refused",
        )
        grafana_status = GrafanaStatus(
            healthy=True,
            reachable=True,
            version="10.2.3",
            database_status="ok",
            dashboard_count=3,
        )
        alerting_status = AlertingRulesStatus(
            loaded=True,
            total_rules=10,
            healthy_rules=10,
            unhealthy_rules=0,
            rule_groups=["alerts"],
        )

        with (
            patch.object(validator, "check_prometheus", return_value=prometheus_status),
            patch.object(validator, "check_grafana", return_value=grafana_status),
            patch.object(validator, "check_alerting_rules", return_value=alerting_status),
        ):
            result = await validator.check_health()

        assert result.healthy is False

    @pytest.mark.asyncio
    async def test_check_health_grafana_unhealthy(
        self, validator: MonitoringStackValidator
    ) -> None:
        """Test check_health returns unhealthy when Grafana is unhealthy."""
        prometheus_status = PrometheusStatus(
            healthy=True,
            reachable=True,
            total_targets=5,
            targets_up=5,
            targets_down=0,
        )
        grafana_status = GrafanaStatus(
            healthy=False,
            reachable=False,
            error="Connection refused",
        )
        alerting_status = AlertingRulesStatus(
            loaded=True,
            total_rules=10,
            healthy_rules=10,
            unhealthy_rules=0,
            rule_groups=["alerts"],
        )

        with (
            patch.object(validator, "check_prometheus", return_value=prometheus_status),
            patch.object(validator, "check_grafana", return_value=grafana_status),
            patch.object(validator, "check_alerting_rules", return_value=alerting_status),
        ):
            result = await validator.check_health()

        assert result.healthy is False

    @pytest.mark.asyncio
    async def test_check_health_targets_down(self, validator: MonitoringStackValidator) -> None:
        """Test check_health reports warning when targets are down."""
        prometheus_status = PrometheusStatus(
            healthy=True,
            reachable=True,
            total_targets=5,
            targets_up=3,
            targets_down=2,
        )
        grafana_status = GrafanaStatus(
            healthy=True,
            reachable=True,
            version="10.2.3",
            database_status="ok",
            dashboard_count=3,
        )
        alerting_status = AlertingRulesStatus(
            loaded=True,
            total_rules=10,
            healthy_rules=10,
            unhealthy_rules=0,
            rule_groups=["alerts"],
        )

        with (
            patch.object(validator, "check_prometheus", return_value=prometheus_status),
            patch.object(validator, "check_grafana", return_value=grafana_status),
            patch.object(validator, "check_alerting_rules", return_value=alerting_status),
        ):
            result = await validator.check_health()

        # Prometheus is still considered healthy if reachable
        # but there should be a warning about down targets
        assert result.healthy is True
        assert result.prometheus.targets_down == 2
        assert len(result.warnings) > 0


# =============================================================================
# Data Class Tests
# =============================================================================


class TestDataClasses:
    """Tests for data classes."""

    def test_scrape_target_creation(self) -> None:
        """Test ScrapeTarget can be created."""
        target = ScrapeTarget(
            job="test-job",
            instance="localhost:8000",
            scrape_url="http://localhost:8000/metrics",
            health=ScrapeTargetHealth.UP,
            last_scrape="2024-01-15T10:30:00.000Z",
            last_scrape_duration=0.015,
            last_error=None,
        )
        assert target.job == "test-job"
        assert target.health == ScrapeTargetHealth.UP

    def test_prometheus_status_creation(self) -> None:
        """Test PrometheusStatus can be created."""
        status = PrometheusStatus(
            healthy=True,
            reachable=True,
            total_targets=5,
            targets_up=5,
            targets_down=0,
        )
        assert status.healthy is True
        assert status.total_targets == 5

    def test_grafana_status_creation(self) -> None:
        """Test GrafanaStatus can be created."""
        status = GrafanaStatus(
            healthy=True,
            reachable=True,
            version="10.2.3",
            database_status="ok",
            dashboard_count=3,
        )
        assert status.healthy is True
        assert status.version == "10.2.3"

    def test_alerting_rules_status_creation(self) -> None:
        """Test AlertingRulesStatus can be created."""
        status = AlertingRulesStatus(
            loaded=True,
            total_rules=10,
            healthy_rules=10,
            unhealthy_rules=0,
            rule_groups=["ai_pipeline_alerts"],
        )
        assert status.loaded is True
        assert status.total_rules == 10

    def test_monitoring_stack_health_creation(self) -> None:
        """Test MonitoringStackHealth can be created."""
        prometheus = PrometheusStatus(healthy=True, reachable=True)
        grafana = GrafanaStatus(healthy=True, reachable=True)
        alerting = AlertingRulesStatus(loaded=True)

        health = MonitoringStackHealth(
            healthy=True,
            prometheus=prometheus,
            grafana=grafana,
            alerting_rules=alerting,
            checked_at=datetime.now(UTC),
            warnings=[],
        )
        assert health.healthy is True


# =============================================================================
# ScrapeTargetHealth Enum Tests
# =============================================================================


class TestScrapeTargetHealthEnum:
    """Tests for ScrapeTargetHealth enum."""

    def test_health_up_value(self) -> None:
        """Test UP enum value."""
        assert ScrapeTargetHealth.UP.value == "up"

    def test_health_down_value(self) -> None:
        """Test DOWN enum value."""
        assert ScrapeTargetHealth.DOWN.value == "down"

    def test_health_unknown_value(self) -> None:
        """Test UNKNOWN enum value."""
        assert ScrapeTargetHealth.UNKNOWN.value == "unknown"


# =============================================================================
# HTTP Client Management Tests
# =============================================================================


class TestHttpClientManagement:
    """Tests for HTTP client lifecycle management."""

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self, validator: MonitoringStackValidator) -> None:
        """Test close() closes the HTTP client."""
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        validator._http_client = mock_client

        await validator.close()

        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_no_client(self, validator: MonitoringStackValidator) -> None:
        """Test close() handles case when no client exists."""
        validator._http_client = None

        # Should not raise
        await validator.close()

    @pytest.mark.asyncio
    async def test_get_http_client_creates_client_if_needed(
        self, validator: MonitoringStackValidator
    ) -> None:
        """Test _get_http_client creates client when needed."""
        validator._http_client = None

        # This will create a real httpx client, which we verify exists
        client = await validator._get_http_client()

        assert client is not None
        assert not client.is_closed

        # Clean up
        await client.aclose()


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_check_prometheus_timeout(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """Test check_prometheus handles timeout errors."""
        import httpx

        mock_http_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            result = await validator.check_prometheus()

        assert result.healthy is False
        assert result.reachable is False
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_check_grafana_timeout(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """Test check_grafana handles timeout errors."""
        import httpx

        mock_http_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            result = await validator.check_grafana()

        assert result.healthy is False
        assert result.reachable is False
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_check_prometheus_invalid_json(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """Test check_prometheus handles invalid JSON response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_http_client.get = AsyncMock(return_value=mock_response)

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            result = await validator.check_prometheus()

        assert result.healthy is False
        assert result.error is not None


# =============================================================================
# Integration-like Tests
# =============================================================================


class TestIntegrationLike:
    """Integration-like tests that verify the full workflow."""

    @pytest.mark.asyncio
    async def test_full_health_check_workflow(
        self,
        validator: MonitoringStackValidator,
        mock_http_client: MagicMock,
        prometheus_targets_response: dict[str, Any],
        prometheus_rules_response: dict[str, Any],
        grafana_health_response: dict[str, Any],
        grafana_dashboards_response: list[dict[str, Any]],
    ) -> None:
        """Test complete health check workflow."""
        # Set up mock responses for all endpoints
        prom_targets_resp = create_mock_response(200, prometheus_targets_response)
        prom_rules_resp = create_mock_response(200, prometheus_rules_response)
        grafana_health_resp = create_mock_response(200, grafana_health_response)
        grafana_dash_resp = create_mock_response(200, grafana_dashboards_response)

        # Configure mock to return different responses based on URL
        async def mock_get(url: str, **kwargs: Any) -> MagicMock:
            if "targets" in url:
                return prom_targets_resp
            elif "rules" in url:
                return prom_rules_resp
            elif "health" in url:
                return grafana_health_resp
            elif "search" in url:
                return grafana_dash_resp
            return prom_targets_resp

        mock_http_client.get = mock_get

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(validator, "_get_http_client", side_effect=get_mock_client):
            result = await validator.check_health()

        # Verify result structure
        assert result.prometheus is not None
        assert result.grafana is not None
        assert result.alerting_rules is not None
        assert result.checked_at is not None
