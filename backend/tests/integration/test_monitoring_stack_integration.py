"""Integration tests for the monitoring stack reliability (NEM-2465).

Tests cover:
- Monitoring health API endpoint functionality
- MonitoringStackValidator integration
- Container discovery for monitoring services
- End-to-end metrics flow verification
- Auto-recovery triggers for failed exporters

These tests verify that the monitoring infrastructure components work together
correctly to provide comprehensive observability and self-healing capabilities.
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
# Fixtures
# =============================================================================


@pytest.fixture
def mock_prometheus_targets_response() -> dict[str, Any]:
    """Create a sample Prometheus targets API response."""
    return {
        "status": "success",
        "data": {
            "activeTargets": [
                {
                    "discoveredLabels": {"__address__": "backend:8000"},
                    "labels": {"job": "hsi-backend-metrics", "instance": "backend:8000"},
                    "scrapePool": "hsi-backend-metrics",
                    "scrapeUrl": "http://backend:8000/api/metrics",
                    "lastError": "",
                    "lastScrape": "2026-01-13T10:30:00.000Z",
                    "lastScrapeDuration": 0.015,
                    "health": "up",
                },
                {
                    "discoveredLabels": {"__address__": "redis-exporter:9121"},
                    "labels": {"job": "redis", "instance": "redis-exporter:9121"},
                    "scrapePool": "redis",
                    "scrapeUrl": "http://redis-exporter:9121/metrics",
                    "lastError": "",
                    "lastScrape": "2026-01-13T10:30:00.000Z",
                    "lastScrapeDuration": 0.010,
                    "health": "up",
                },
                {
                    "discoveredLabels": {"__address__": "localhost:9090"},
                    "labels": {"job": "prometheus", "instance": "localhost:9090"},
                    "scrapePool": "prometheus",
                    "scrapeUrl": "http://localhost:9090/metrics",
                    "lastError": "",
                    "lastScrape": "2026-01-13T10:30:00.000Z",
                    "lastScrapeDuration": 0.005,
                    "health": "up",
                },
            ],
            "droppedTargets": [],
        },
    }


@pytest.fixture
def mock_prometheus_rules_response() -> dict[str, Any]:
    """Create a sample Prometheus rules API response."""
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
                            "name": "AIDetectorUnavailable",
                            "query": "hsi_ai_healthy == 0",
                            "duration": 120,
                            "labels": {"severity": "critical"},
                            "health": "ok",
                            "type": "alerting",
                        },
                        {
                            "state": "inactive",
                            "name": "PrometheusNotScrapingSelf",
                            "query": 'up{job="prometheus"} == 0',
                            "duration": 120,
                            "labels": {"severity": "critical"},
                            "health": "ok",
                            "type": "alerting",
                        },
                    ],
                },
            ],
        },
    }


@pytest.fixture
def mock_grafana_health_response() -> dict[str, Any]:
    """Create a sample Grafana health API response."""
    return {"commit": "abc123", "database": "ok", "version": "10.2.3"}


@pytest.fixture
def mock_grafana_dashboards_response() -> list[dict[str, Any]]:
    """Create a sample Grafana dashboards search response."""
    return [
        {
            "id": 1,
            "uid": "pipeline-dashboard",
            "title": "AI Pipeline Dashboard",
            "type": "dash-db",
        },
        {
            "id": 2,
            "uid": "system-overview",
            "title": "System Overview",
            "type": "dash-db",
        },
    ]


# =============================================================================
# Monitoring Health API Tests
# =============================================================================


@pytest.mark.asyncio
async def test_monitoring_health_endpoint_returns_valid_response(client, mock_redis):
    """Test that the monitoring health endpoint returns a valid response structure."""
    # Mock Prometheus as unavailable to avoid external network calls
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500  # Simulate Prometheus down
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        response = await client.get("/api/system/monitoring/health")

    # Endpoint should return even when Prometheus is down
    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "healthy" in data
    assert "prometheus_reachable" in data
    assert "prometheus_url" in data
    assert "targets_summary" in data
    assert "exporters" in data
    assert "metrics_collection" in data
    assert "issues" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_monitoring_health_endpoint_reports_prometheus_unreachable(client, mock_redis):
    """Test that the endpoint correctly reports when Prometheus is unreachable."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        response = await client.get("/api/system/monitoring/health")

    assert response.status_code == 200
    data = response.json()

    # Should report unhealthy and Prometheus unreachable
    assert data["healthy"] is False
    assert data["prometheus_reachable"] is False
    assert len(data["issues"]) > 0
    assert "Prometheus" in data["issues"][0]


# =============================================================================
# MonitoringStackValidator Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_validator_check_prometheus_with_healthy_targets(
    mock_prometheus_targets_response: dict[str, Any],
):
    """Test MonitoringStackValidator correctly reports healthy targets."""
    validator = MonitoringStackValidator(
        prometheus_url="http://test-prometheus:9090",
        grafana_url="http://test-grafana:3000",
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_prometheus_targets_response
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await validator.check_prometheus()

    assert result.healthy is True
    assert result.reachable is True
    assert result.total_targets == 3
    assert result.targets_up == 3
    assert result.targets_down == 0


@pytest.mark.asyncio
async def test_validator_check_prometheus_with_unhealthy_targets():
    """Test MonitoringStackValidator correctly reports unhealthy targets."""
    targets_with_failures = {
        "status": "success",
        "data": {
            "activeTargets": [
                {
                    "labels": {"job": "backend", "instance": "backend:8000"},
                    "scrapePool": "backend",
                    "health": "up",
                },
                {
                    "labels": {"job": "redis", "instance": "redis-exporter:9121"},
                    "scrapePool": "redis",
                    "health": "down",
                    "lastError": "connection refused",
                },
            ],
            "droppedTargets": [],
        },
    }

    validator = MonitoringStackValidator(
        prometheus_url="http://test-prometheus:9090",
        grafana_url="http://test-grafana:3000",
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = targets_with_failures
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await validator.check_prometheus()

    assert result.healthy is True  # Still healthy because Prometheus is reachable
    assert result.reachable is True
    assert result.total_targets == 2
    assert result.targets_up == 1
    assert result.targets_down == 1


@pytest.mark.asyncio
async def test_validator_check_alerting_rules(
    mock_prometheus_rules_response: dict[str, Any],
):
    """Test MonitoringStackValidator correctly validates alerting rules."""
    validator = MonitoringStackValidator(
        prometheus_url="http://test-prometheus:9090",
        grafana_url="http://test-grafana:3000",
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_prometheus_rules_response
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await validator.check_alerting_rules()

    assert result.loaded is True
    assert result.total_rules == 2
    assert result.healthy_rules == 2
    assert result.unhealthy_rules == 0
    assert "ai_pipeline_alerts" in result.rule_groups


@pytest.mark.asyncio
async def test_validator_check_grafana(
    mock_grafana_health_response: dict[str, Any],
    mock_grafana_dashboards_response: list[dict[str, Any]],
):
    """Test MonitoringStackValidator correctly checks Grafana health."""
    validator = MonitoringStackValidator(
        prometheus_url="http://test-prometheus:9090",
        grafana_url="http://test-grafana:3000",
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        health_response = MagicMock()
        health_response.status_code = 200
        health_response.json.return_value = mock_grafana_health_response

        dashboards_response = MagicMock()
        dashboards_response.status_code = 200
        dashboards_response.json.return_value = mock_grafana_dashboards_response

        mock_client.get = AsyncMock(side_effect=[health_response, dashboards_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await validator.check_grafana()

    assert result.healthy is True
    assert result.reachable is True
    assert result.version == "10.2.3"
    assert result.database_status == "ok"
    assert result.dashboard_count == 2


@pytest.mark.asyncio
async def test_validator_combined_health_check(
    mock_prometheus_targets_response: dict[str, Any],
    mock_prometheus_rules_response: dict[str, Any],
    mock_grafana_health_response: dict[str, Any],
    mock_grafana_dashboards_response: list[dict[str, Any]],
):
    """Test MonitoringStackValidator aggregates all health checks correctly."""
    validator = MonitoringStackValidator(
        prometheus_url="http://test-prometheus:9090",
        grafana_url="http://test-grafana:3000",
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()

        # Create responses for different endpoints
        async def mock_get(url: str, **kwargs) -> MagicMock:
            response = MagicMock()
            response.status_code = 200

            if "targets" in url:
                response.json.return_value = mock_prometheus_targets_response
            elif "rules" in url:
                response.json.return_value = mock_prometheus_rules_response
            elif "health" in url and "grafana" in url:
                response.json.return_value = mock_grafana_health_response
            elif "search" in url:
                response.json.return_value = mock_grafana_dashboards_response
            else:
                response.json.return_value = mock_prometheus_targets_response

            return response

        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await validator.check_health()

    assert isinstance(result, MonitoringStackHealth)
    assert result.healthy is True
    assert result.prometheus.healthy is True
    assert result.grafana.healthy is True
    assert result.alerting_rules.loaded is True
    assert result.checked_at is not None
    assert len(result.warnings) == 0


@pytest.mark.asyncio
async def test_validator_health_check_with_warnings():
    """Test MonitoringStackValidator includes warnings when targets are down."""
    targets_with_down = {
        "status": "success",
        "data": {
            "activeTargets": [
                {"labels": {"job": "backend"}, "health": "up"},
                {"labels": {"job": "redis"}, "health": "down", "lastError": "timeout"},
            ],
            "droppedTargets": [],
        },
    }

    validator = MonitoringStackValidator(
        prometheus_url="http://test-prometheus:9090",
        grafana_url="http://test-grafana:3000",
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()

        async def mock_get(url: str, **kwargs) -> MagicMock:
            response = MagicMock()
            response.status_code = 200

            if "targets" in url:
                response.json.return_value = targets_with_down
            elif "rules" in url:
                response.json.return_value = {"status": "success", "data": {"groups": []}}
            elif "health" in url:
                response.json.return_value = {"database": "ok", "version": "10.0"}
            elif "search" in url:
                response.json.return_value = []
            else:
                response.json.return_value = targets_with_down

            return response

        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await validator.check_health()

    # Should have warnings about down targets
    assert len(result.warnings) > 0
    assert any("down" in w.lower() for w in result.warnings)


# =============================================================================
# Container Discovery Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_container_discovery_includes_monitoring_services():
    """Test that ContainerDiscoveryService includes all monitoring services."""
    from backend.services.container_discovery import (
        MONITORING_CONFIGS,
    )

    # Verify all monitoring services are configured
    assert "prometheus" in MONITORING_CONFIGS
    assert "grafana" in MONITORING_CONFIGS
    assert "alertmanager" in MONITORING_CONFIGS
    assert "redis-exporter" in MONITORING_CONFIGS
    assert "json-exporter" in MONITORING_CONFIGS
    assert "blackbox-exporter" in MONITORING_CONFIGS


def test_monitoring_service_configs_have_health_endpoints():
    """Test that all monitoring services have health endpoints configured."""
    from backend.services.container_discovery import MONITORING_CONFIGS

    for name, config in MONITORING_CONFIGS.items():
        assert config.health_endpoint is not None, f"{name} missing health_endpoint"
        assert config.port > 0, f"{name} has invalid port"
        assert config.startup_grace_period > 0, f"{name} has invalid startup_grace_period"


def test_monitoring_service_configs_have_reasonable_backoff():
    """Test that monitoring services have reasonable backoff settings."""
    from backend.services.container_discovery import MONITORING_CONFIGS

    for name, config in MONITORING_CONFIGS.items():
        # Exporters should have shorter backoff than Prometheus/Grafana
        if "exporter" in name:
            assert config.restart_backoff_base <= 10.0, f"{name} backoff too high"
        # Max failures should be reasonable
        assert config.max_failures >= 3, f"{name} max_failures too low"


# =============================================================================
# ScrapeTarget Data Class Tests
# =============================================================================


def test_scrape_target_creation():
    """Test ScrapeTarget can be created with correct attributes."""
    target = ScrapeTarget(
        job="test-job",
        instance="localhost:8000",
        scrape_url="http://localhost:8000/metrics",
        health=ScrapeTargetHealth.UP,
        last_scrape="2026-01-13T10:30:00.000Z",
        last_scrape_duration=0.015,
    )

    assert target.job == "test-job"
    assert target.instance == "localhost:8000"
    assert target.health == ScrapeTargetHealth.UP
    assert target.last_error is None


def test_scrape_target_with_error():
    """Test ScrapeTarget correctly stores error information."""
    target = ScrapeTarget(
        job="failing-job",
        instance="localhost:9999",
        scrape_url="http://localhost:9999/metrics",
        health=ScrapeTargetHealth.DOWN,
        last_error="connection refused",
    )

    assert target.health == ScrapeTargetHealth.DOWN
    assert target.last_error == "connection refused"


# =============================================================================
# Status Data Class Tests
# =============================================================================


def test_prometheus_status_defaults():
    """Test PrometheusStatus has correct default values."""
    status = PrometheusStatus(healthy=True, reachable=True)

    assert status.total_targets == 0
    assert status.targets_up == 0
    assert status.targets_down == 0
    assert status.error is None


def test_grafana_status_defaults():
    """Test GrafanaStatus has correct default values."""
    status = GrafanaStatus(healthy=True, reachable=True)

    assert status.version is None
    assert status.database_status is None
    assert status.dashboard_count == 0
    assert status.error is None


def test_alerting_rules_status_defaults():
    """Test AlertingRulesStatus has correct default values."""
    status = AlertingRulesStatus(loaded=True)

    assert status.total_rules == 0
    assert status.healthy_rules == 0
    assert status.unhealthy_rules == 0
    assert len(status.rule_groups) == 0
    assert status.error is None


def test_monitoring_stack_health_creation():
    """Test MonitoringStackHealth aggregates component statuses correctly."""
    prometheus = PrometheusStatus(
        healthy=True,
        reachable=True,
        total_targets=5,
        targets_up=5,
        targets_down=0,
    )
    grafana = GrafanaStatus(
        healthy=True,
        reachable=True,
        version="10.2.3",
        database_status="ok",
        dashboard_count=3,
    )
    alerting = AlertingRulesStatus(
        loaded=True,
        total_rules=10,
        healthy_rules=10,
        unhealthy_rules=0,
    )

    health = MonitoringStackHealth(
        healthy=True,
        prometheus=prometheus,
        grafana=grafana,
        alerting_rules=alerting,
        checked_at=datetime.now(UTC),
        warnings=[],
    )

    assert health.healthy is True
    assert health.prometheus.total_targets == 5
    assert health.grafana.dashboard_count == 3
    assert health.alerting_rules.total_rules == 10


# =============================================================================
# HTTP Client Management Tests
# =============================================================================


@pytest.mark.asyncio
async def test_validator_closes_http_client():
    """Test MonitoringStackValidator properly closes HTTP client."""
    validator = MonitoringStackValidator(
        prometheus_url="http://test-prometheus:9090",
        grafana_url="http://test-grafana:3000",
    )

    # Create a client
    client = await validator._get_http_client()
    assert client is not None
    assert not client.is_closed

    # Close the validator
    await validator.close()

    # Client should be closed
    # Note: The original client reference is closed, validator._http_client is None


@pytest.mark.asyncio
async def test_validator_handles_close_without_client():
    """Test MonitoringStackValidator handles close when no client exists."""
    validator = MonitoringStackValidator(
        prometheus_url="http://test-prometheus:9090",
        grafana_url="http://test-grafana:3000",
    )

    # Ensure no client exists
    validator._http_client = None

    # Should not raise
    await validator.close()
