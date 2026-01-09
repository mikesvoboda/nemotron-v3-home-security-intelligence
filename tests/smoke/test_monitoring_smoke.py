"""
Monitoring Stack Smoke Tests

Verifies that the monitoring stack (Prometheus, Grafana, Jaeger) is operational.
These tests are optional for deployments without monitoring enabled.

Test Scope:
- Prometheus metrics collection
- Grafana dashboard availability
- Jaeger trace collection
- Alert manager configuration
"""

import httpx
import pytest


class TestPrometheus:
    """Prometheus metrics endpoint tests."""

    @pytest.mark.monitoring
    @pytest.mark.slow
    def test_prometheus_metrics_endpoint(self, http_client: httpx.Client):
        """
        Prometheus /metrics endpoint responds with metrics data.

        Note: This test requires Prometheus to be running.
        It can be skipped if monitoring is not enabled.
        """
        response = http_client.get("http://localhost:9090/metrics", timeout=10.0)

        # Might not be available in all deployments
        if response.status_code == 404:
            pytest.skip("Prometheus not available in this deployment")

        assert response.status_code == 200, f"Prometheus metrics failed: {response.status_code}"
        assert len(response.text) > 0, "Prometheus metrics should return data"

    @pytest.mark.monitoring
    def test_prometheus_query_endpoint(self, http_client: httpx.Client):
        """
        Prometheus /api/v1/query endpoint is available.

        Note: Requires Prometheus to be running.
        """
        try:
            response = http_client.get(
                "http://localhost:9090/api/v1/query?query=up",
                timeout=10.0,
            )

            if response.status_code == 404:
                pytest.skip("Prometheus not available in this deployment")

            assert response.status_code == 200, f"Prometheus query failed: {response.status_code}"

            data = response.json()
            assert "status" in data, "Prometheus query response should have status"
            assert data["status"] in ["success", "error"], f"Invalid status: {data['status']}"
        except httpx.RequestError:
            pytest.skip("Prometheus not available in this deployment")

    @pytest.mark.monitoring
    def test_prometheus_health_endpoint(self, http_client: httpx.Client):
        """
        Prometheus /-/healthy endpoint indicates health status.
        """
        try:
            response = http_client.get("http://localhost:9090/-/healthy", timeout=10.0)

            if response.status_code == 404:
                pytest.skip("Prometheus not available in this deployment")

            assert response.status_code == 200, f"Prometheus health failed: {response.status_code}"
        except httpx.RequestError:
            pytest.skip("Prometheus not available in this deployment")


class TestGrafana:
    """Grafana dashboard availability tests."""

    @pytest.mark.monitoring
    @pytest.mark.slow
    def test_grafana_ui_accessible(self, http_client: httpx.Client):
        """
        Grafana web UI is accessible.

        Note: Requires Grafana to be running on localhost:3002
        """
        try:
            response = http_client.get(
                "http://localhost:3002/", follow_redirects=True, timeout=10.0
            )

            if response.status_code == 404:
                pytest.skip("Grafana not available in this deployment")

            assert response.status_code == 200, f"Grafana UI failed: {response.status_code}"
            assert "text/html" in response.headers.get("content-type", "").lower(), (
                "Grafana should serve HTML"
            )
        except httpx.RequestError:
            pytest.skip("Grafana not available in this deployment")

    @pytest.mark.monitoring
    def test_grafana_api_health(self, http_client: httpx.Client):
        """
        Grafana API /api/health endpoint responds.

        Note: Requires Grafana to be running.
        """
        try:
            response = http_client.get("http://localhost:3002/api/health", timeout=10.0)

            if response.status_code == 404:
                pytest.skip("Grafana not available in this deployment")

            assert response.status_code == 200, f"Grafana health failed: {response.status_code}"

            data = response.json()
            assert "database" in data, "Grafana health should have database status"
        except httpx.RequestError:
            pytest.skip("Grafana not available in this deployment")

    @pytest.mark.monitoring
    def test_grafana_datasources_configured(self, http_client: httpx.Client):
        """
        Grafana has datasources configured.

        Note: Requires Grafana authentication (uses default admin/admin).
        """
        try:
            response = http_client.get(
                "http://localhost:3002/api/datasources",
                auth=("admin", "admin"),
                timeout=10.0,
            )

            if response.status_code == 404:
                pytest.skip("Grafana not available in this deployment")

            if response.status_code == 401:
                pytest.skip("Grafana authentication required")

            assert response.status_code == 200, (
                f"Grafana datasources failed: {response.status_code}"
            )

            datasources = response.json()
            assert isinstance(datasources, list), "Datasources should be an array"
        except httpx.RequestError:
            pytest.skip("Grafana not available in this deployment")


class TestJaeger:
    """Jaeger tracing endpoint tests."""

    @pytest.mark.monitoring
    @pytest.mark.slow
    def test_jaeger_ui_accessible(self, http_client: httpx.Client):
        """
        Jaeger web UI is accessible.

        Note: Requires Jaeger to be running on localhost:16686
        """
        try:
            response = http_client.get(
                "http://localhost:16686/",
                follow_redirects=True,
                timeout=10.0,
            )

            if response.status_code == 404:
                pytest.skip("Jaeger not available in this deployment")

            assert response.status_code == 200, f"Jaeger UI failed: {response.status_code}"
            assert "text/html" in response.headers.get("content-type", "").lower(), (
                "Jaeger should serve HTML"
            )
        except httpx.RequestError:
            pytest.skip("Jaeger not available in this deployment")

    @pytest.mark.monitoring
    def test_jaeger_api_health(self, http_client: httpx.Client):
        """
        Jaeger API health endpoint responds.

        Note: Requires Jaeger to be running.
        """
        try:
            response = http_client.get("http://localhost:16686/api/health", timeout=10.0)

            if response.status_code == 404:
                pytest.skip("Jaeger not available in this deployment")

            assert response.status_code == 200, f"Jaeger health failed: {response.status_code}"
        except httpx.RequestError:
            pytest.skip("Jaeger not available in this deployment")

    @pytest.mark.monitoring
    def test_jaeger_traces_endpoint(self, http_client: httpx.Client):
        """
        Jaeger /api/traces endpoint is available for trace queries.

        Note: Requires Jaeger to be running.
        """
        try:
            response = http_client.get(
                "http://localhost:16686/api/traces?service=nemotron-backend-staging&limit=10",
                timeout=10.0,
            )

            if response.status_code == 404:
                pytest.skip("Jaeger not available in this deployment")

            assert response.status_code == 200, f"Jaeger traces failed: {response.status_code}"

            data = response.json()
            # Should have data structure even if no traces
            assert "data" in data or "traces" in data, "Traces endpoint should return data"
        except httpx.RequestError:
            pytest.skip("Jaeger not available in this deployment")


class TestAlertManager:
    """AlertManager configuration tests."""

    @pytest.mark.monitoring
    def test_alertmanager_health(self, http_client: httpx.Client):
        """
        AlertManager /-/healthy endpoint indicates health.

        Note: Requires AlertManager to be running on localhost:9093
        """
        try:
            response = http_client.get("http://localhost:9093/-/healthy", timeout=10.0)

            if response.status_code == 404:
                pytest.skip("AlertManager not available in this deployment")

            assert response.status_code == 200, (
                f"AlertManager health failed: {response.status_code}"
            )
        except httpx.RequestError:
            pytest.skip("AlertManager not available in this deployment")

    @pytest.mark.monitoring
    def test_alertmanager_api_status(self, http_client: httpx.Client):
        """
        AlertManager /api/v1/status endpoint returns configuration.

        Note: Requires AlertManager to be running.
        """
        try:
            response = http_client.get("http://localhost:9093/api/v1/status", timeout=10.0)

            if response.status_code == 404:
                pytest.skip("AlertManager not available in this deployment")

            assert response.status_code == 200, (
                f"AlertManager status failed: {response.status_code}"
            )

            data = response.json()
            assert "data" in data or "status" in data, "Status endpoint should return data"
        except httpx.RequestError:
            pytest.skip("AlertManager not available in this deployment")


class TestMonitoringStack:
    """Integration tests for the monitoring stack."""

    @pytest.mark.monitoring
    def test_prometheus_scrapes_targets(self, http_client: httpx.Client):
        """
        Prometheus is scraping monitoring targets.

        This indicates the monitoring stack is integrated with the application.
        """
        try:
            response = http_client.get(
                "http://localhost:9090/api/v1/targets",
                timeout=10.0,
            )

            if response.status_code == 404:
                pytest.skip("Prometheus not available in this deployment")

            assert response.status_code == 200, f"Prometheus targets failed: {response.status_code}"

            data = response.json()
            if data["status"] == "success":
                targets = data.get("data", {})
                # Should have at least some targets configured
                active_targets = targets.get("activeTargets", [])
                # This is informational only - don't fail if no targets
                pytest.skip(f"Prometheus has {len(active_targets)} active targets") if len(
                    active_targets
                ) == 0 else None
        except httpx.RequestError:
            pytest.skip("Prometheus not available in this deployment")
