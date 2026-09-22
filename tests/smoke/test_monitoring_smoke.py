"""
Monitoring Stack Smoke Tests

Verifies that the monitoring stack (Prometheus, Grafana, Tempo) is operational.
These tests are optional for deployments without monitoring enabled.

Test Scope:
- Prometheus metrics collection
- Grafana dashboard availability
- Tempo trace collection (replaced Jaeger + Elasticsearch under NEM-5545)
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
        try:
            response = http_client.get("http://localhost:9090/metrics", timeout=10.0)

            # Might not be available in all deployments
            if response.status_code == 404:
                pytest.skip("Prometheus not available in this deployment")

            assert response.status_code == 200, f"Prometheus metrics failed: {response.status_code}"
            assert len(response.text) > 0, "Prometheus metrics should return data"
        except httpx.RequestError:
            pytest.skip("Prometheus not available in this deployment")

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


class TestTempo:
    """
    Grafana Tempo tracing endpoint tests.

    Tempo replaced Jaeger + Elasticsearch under NEM-5545: traces are exported to
    Alloy (:4317), forwarded to Tempo (:4317), stored under Tempo's own `local`
    backend (no Elasticsearch) and queried over Tempo's HTTP querier API on :3200.
    Tempo ships no UI of its own - traces are viewed through Grafana Explore or the
    dashboard's Tracing page - so these tests probe the query API directly.
    """

    @pytest.mark.monitoring
    @pytest.mark.slow
    def test_tempo_ready_endpoint(self, http_client: httpx.Client):
        """
        Tempo /ready readiness endpoint reports ready.

        This is the same probe the compose healthcheck and
        scripts/platform-healthcheck.py use (GET /ready, body "ready").

        Note: Requires Tempo to be running on localhost:3200
        """
        try:
            response = http_client.get("http://localhost:3200/ready", timeout=10.0)

            if response.status_code == 404:
                pytest.skip("Tempo not available in this deployment")

            assert response.status_code == 200, f"Tempo readiness failed: {response.status_code}"
            assert "ready" in response.text.lower(), (
                f"Tempo /ready should report ready, got: {response.text!r}"
            )
        except httpx.RequestError:
            pytest.skip("Tempo not available in this deployment")

    @pytest.mark.monitoring
    def test_tempo_api_responds(self, http_client: httpx.Client):
        """
        Tempo querier HTTP API is mounted and answering (GET /api/echo).

        /api/echo is the querier's connectivity route - it answers 200 with the
        plain-text body "echo" (text/plain, verified against tempo:2.7.1), which
        proves the query frontend is serving, independent of stored data.

        Note: Requires Tempo to be running on localhost:3200
        """
        try:
            response = http_client.get("http://localhost:3200/api/echo", timeout=10.0)

            if response.status_code == 404:
                pytest.skip("Tempo not available in this deployment")

            assert response.status_code == 200, f"Tempo API failed: {response.status_code}"
            assert "echo" in response.text.lower(), "Tempo /api/echo should echo back"
        except httpx.RequestError:
            pytest.skip("Tempo not available in this deployment")

    @pytest.mark.monitoring
    def test_tempo_search_endpoint(self, http_client: httpx.Client):
        """
        Tempo /api/search answers a TraceQL query.

        Tempo's search API requires at least one tag matcher, so {duration>0}
        is used to match every span - the same probe as
        scripts/verify-observability.sh.

        Note: Requires Tempo to be running on localhost:3200
        """
        try:
            response = http_client.get(
                "http://localhost:3200/api/search?q={duration>0}&limit=20",
                timeout=10.0,
            )

            if response.status_code == 404:
                pytest.skip("Tempo not available in this deployment")

            assert response.status_code == 200, f"Tempo search failed: {response.status_code}"

            data = response.json()
            assert "traces" in data, "Tempo search response should have a traces field"
            assert isinstance(data["traces"], list), "Tempo traces should be an array"
            # An empty list is acceptable - it just means no traces have landed yet.
        except httpx.RequestError:
            pytest.skip("Tempo not available in this deployment")

    @pytest.mark.monitoring
    def test_tempo_search_tags_endpoint(self, http_client: httpx.Client):
        """
        Tempo /api/search/tags enumerates the tags of stored spans.

        Replaces the old Jaeger /api/services check: this exercises the same
        read path (querier -> ingesters -> block store) that Grafana's trace
        search uses, without needing a known trace ID.

        Note: Requires Tempo to be running on localhost:3200
        """
        try:
            response = http_client.get("http://localhost:3200/api/search/tags", timeout=10.0)

            if response.status_code == 404:
                pytest.skip("Tempo not available in this deployment")

            assert response.status_code == 200, f"Tempo search tags failed: {response.status_code}"

            data = response.json()
            assert "tagNames" in data, "Tempo search tags response should have tagNames"
            assert isinstance(data["tagNames"], list), "Tempo tagNames should be an array"
            # Note: tagNames may be empty if no traces have been ingested yet -
            # that is acceptable, we are verifying the query path is wired up.
        except httpx.RequestError:
            pytest.skip("Tempo not available in this deployment")


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
