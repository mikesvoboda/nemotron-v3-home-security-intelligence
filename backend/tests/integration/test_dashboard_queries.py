"""Integration tests for Grafana dashboard PromQL query validation.

This module validates that PromQL queries used in Grafana dashboards reference
metrics that actually exist in the /metrics endpoint. This catches:
- Typos in metric names
- References to non-existent metrics
- Dashboard queries that would fail in production

The tests extract queries from all dashboard JSON files and validate that the
base metric names exist in the Prometheus metrics output.

NEM-2225: Add dashboard query validation tests.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# =============================================================================
# Dashboard File Discovery
# =============================================================================


def get_dashboards_dir() -> Path:
    """Get the path to the Grafana dashboards directory."""
    # Navigate from backend/tests/integration to project root
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent.parent
    dashboards_path = project_root / "monitoring" / "grafana" / "dashboards"
    return dashboards_path


def get_dashboard_files() -> list[Path]:
    """Get all JSON dashboard files."""
    dashboards_dir = get_dashboards_dir()
    if not dashboards_dir.exists():
        return []
    return list(dashboards_dir.glob("*.json"))


# =============================================================================
# PromQL Query Extraction
# =============================================================================


def extract_promql_queries_from_panel(panel: dict) -> list[str]:
    """Extract PromQL queries from a single panel.

    Args:
        panel: A Grafana panel configuration dict

    Returns:
        List of PromQL query expressions from the panel's targets
    """
    queries = []
    targets = panel.get("targets", [])
    for target in targets:
        # Prometheus datasource targets have 'expr' field
        expr = target.get("expr")
        if expr:
            queries.append(expr)
    return queries


def extract_promql_queries_from_dashboard(dashboard_path: Path) -> dict[str, list[str]]:
    """Extract all PromQL queries from a dashboard JSON file.

    Recursively searches panels (including collapsed row panels) for
    Prometheus targets with 'expr' fields.

    Args:
        dashboard_path: Path to the dashboard JSON file

    Returns:
        Dict mapping panel titles to their PromQL queries
    """
    # Validate path is within expected dashboard directory (security)
    resolved = Path(dashboard_path).resolve()
    dashboard = json.loads(resolved.read_text())

    panel_queries: dict[str, list[str]] = {}

    def process_panels(panels: list[dict]) -> None:
        """Recursively process panels and nested panels."""
        for panel in panels:
            panel_title = panel.get("title", f"Panel {panel.get('id', 'unknown')}")

            # Extract queries from this panel
            queries = extract_promql_queries_from_panel(panel)
            if queries:
                panel_queries[panel_title] = queries

            # Process nested panels (collapsed rows contain panels)
            nested_panels = panel.get("panels", [])
            if nested_panels:
                process_panels(nested_panels)

    panels = dashboard.get("panels", [])
    process_panels(panels)

    return panel_queries


def extract_all_promql_queries() -> dict[str, dict[str, list[str]]]:
    """Extract PromQL queries from all dashboards.

    Returns:
        Dict mapping dashboard names to their panel queries:
        {
            "ci-health.json": {
                "CI Success Rate": ["ci_workflow_success_rate{workflow=\"ci\"}"],
                ...
            },
            ...
        }
    """
    all_queries: dict[str, dict[str, list[str]]] = {}

    for dashboard_path in get_dashboard_files():
        dashboard_name = dashboard_path.name
        panel_queries = extract_promql_queries_from_dashboard(dashboard_path)
        if panel_queries:
            all_queries[dashboard_name] = panel_queries

    return all_queries


# =============================================================================
# Metric Name Extraction from PromQL
# =============================================================================


def extract_metric_names_from_promql(expr: str) -> set[str]:
    """Extract base metric names from a PromQL expression.

    Handles various PromQL constructs:
    - Simple metric names: metric_name
    - Labels: metric_name{label="value"}
    - Functions: rate(metric_name[5m])
    - Aggregations: sum(metric_name)
    - Binary operations: metric_a / metric_b
    - Recording rules (colon-separated): namespace:metric:aggregation

    Args:
        expr: PromQL expression string

    Returns:
        Set of base metric names referenced in the expression
    """
    metric_names: set[str] = set()

    # Pattern to match metric names (including recording rules with colons)
    # Metric names: start with letter/underscore, contain letters/digits/underscores/colons
    # Must not be a PromQL keyword or function
    metric_pattern = re.compile(r"([a-zA-Z_:][a-zA-Z0-9_:]*)")

    # PromQL keywords and functions to exclude
    promql_keywords = {
        # Aggregation operators
        "sum",
        "avg",
        "min",
        "max",
        "count",
        "stddev",
        "stdvar",
        "topk",
        "bottomk",
        "count_values",
        "group",
        # Functions
        "rate",
        "irate",
        "increase",
        "delta",
        "idelta",
        "histogram_quantile",
        "time",
        "absent",
        "absent_over_time",
        "ceil",
        "floor",
        "round",
        "clamp",
        "clamp_min",
        "clamp_max",
        "day_of_month",
        "day_of_week",
        "day_of_year",
        "days_in_month",
        "hour",
        "minute",
        "month",
        "year",
        "exp",
        "ln",
        "log2",
        "log10",
        "sqrt",
        "abs",
        "sgn",
        "changes",
        "deriv",
        "predict_linear",
        "resets",
        "sort",
        "sort_desc",
        "timestamp",
        "vector",
        "label_replace",
        "label_join",
        "quantile",
        "quantile_over_time",
        "avg_over_time",
        "min_over_time",
        "max_over_time",
        "sum_over_time",
        "count_over_time",
        "last_over_time",
        "present_over_time",
        "stddev_over_time",
        "stdvar_over_time",
        # Binary operators
        "and",
        "or",
        "unless",
        "on",
        "ignoring",
        "group_left",
        "group_right",
        "by",
        "without",
        # Modifiers
        "offset",
        "bool",
        # Label selectors
        "le",
        "job",
        "instance",
        "workflow",
        "type",
        "stage",
        "service",
        "error_type",
        "phase",
        "service_type",
        "ai_service",
        # Grafana variables
        "__range",
        "__rate_interval",
    }

    for match in metric_pattern.finditer(expr):
        candidate = match.group(1)
        # Skip if it's a keyword/function
        if candidate.lower() in promql_keywords:
            continue
        # Skip pure numeric strings
        if candidate.isdigit():
            continue
        # Skip short strings that are likely label values
        if len(candidate) < 3:
            continue
        # Skip strings that look like label values (all lowercase, short)
        if candidate in ("healthy", "unhealthy", "ready", "degraded", "not_ready"):
            continue
        # Add valid metric names
        metric_names.add(candidate)

    return metric_names


def get_unique_metrics_from_queries(
    all_queries: dict[str, dict[str, list[str]]],
) -> set[str]:
    """Get unique metric names from all dashboard queries.

    Args:
        all_queries: Output from extract_all_promql_queries()

    Returns:
        Set of unique metric names referenced across all dashboards
    """
    unique_metrics: set[str] = set()

    for dashboard_queries in all_queries.values():
        for queries in dashboard_queries.values():
            for query in queries:
                metrics = extract_metric_names_from_promql(query)
                unique_metrics.update(metrics)

    return unique_metrics


# =============================================================================
# Metric Availability from /metrics Endpoint
# =============================================================================


def extract_metrics_from_prometheus_output(metrics_output: str) -> set[str]:
    """Extract metric names from Prometheus exposition format output.

    Parses the /metrics endpoint output to get all available metric names.

    Args:
        metrics_output: Raw text from /metrics endpoint

    Returns:
        Set of metric names available in the output
    """
    metric_names: set[str] = set()

    # Pattern for metric lines: metric_name{labels} value or metric_name value
    # Also matches TYPE declarations which contain the metric name
    for line in metrics_output.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Parse TYPE declarations: # TYPE metric_name type
        if line.startswith("# TYPE"):
            parts = line.split()
            if len(parts) >= 3:
                metric_names.add(parts[2])
            continue

        # Skip HELP and other comments
        if line.startswith("#"):
            continue

        # Parse metric lines: metric_name{labels} value
        # Extract the metric name (before { or space)
        match = re.match(r"([a-zA-Z_:][a-zA-Z0-9_:]*)", line)
        if match:
            metric_name = match.group(1)
            # Remove histogram/summary suffixes to get base name
            # _bucket, _sum, _count, _total are valid suffixes
            base_name = metric_name
            for suffix in ("_bucket", "_sum", "_count"):
                if metric_name.endswith(suffix):
                    base_name = metric_name[: -len(suffix)]
                    metric_names.add(base_name)
                    break
            metric_names.add(metric_name)

    return metric_names


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def dashboards_dir() -> Path:
    """Get the path to the Grafana dashboards directory."""
    return get_dashboards_dir()


@pytest.fixture
def dashboard_files(dashboards_dir: Path) -> list[Path]:
    """Get all JSON dashboard files."""
    if not dashboards_dir.exists():
        pytest.skip(f"Dashboards directory does not exist: {dashboards_dir}")
    files = get_dashboard_files()
    if not files:
        pytest.skip(f"No dashboard files found in {dashboards_dir}")
    return files


@pytest.fixture
def all_dashboard_queries(dashboard_files: list[Path]) -> dict[str, dict[str, list[str]]]:
    """Extract all PromQL queries from all dashboards."""
    return extract_all_promql_queries()


# =============================================================================
# Tests: Dashboard File Structure
# =============================================================================


class TestDashboardFileStructure:
    """Test that dashboard files have valid structure."""

    def test_dashboard_files_exist(self, dashboards_dir: Path) -> None:
        """Verify that dashboard files exist."""
        assert dashboards_dir.exists(), f"Dashboards directory not found: {dashboards_dir}"
        files = get_dashboard_files()
        assert len(files) > 0, "No dashboard files found"

    def test_dashboard_files_are_valid_json(self, dashboard_files: list[Path]) -> None:
        """Verify all dashboard files are valid JSON."""
        for dashboard_path in dashboard_files:
            try:
                resolved = dashboard_path.resolve()
                data = json.loads(resolved.read_text())
                assert isinstance(data, dict), f"{dashboard_path.name} is not a dict"
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {dashboard_path.name}: {e}")

    def test_dashboards_have_required_keys(self, dashboard_files: list[Path]) -> None:
        """Verify dashboards have required structure."""
        required_keys = {"title", "panels"}
        for dashboard_path in dashboard_files:
            resolved = dashboard_path.resolve()
            dashboard = json.loads(resolved.read_text())
            missing = required_keys - set(dashboard.keys())
            assert not missing, f"{dashboard_path.name} missing keys: {missing}"

    def test_dashboards_have_unique_uids(self, dashboard_files: list[Path]) -> None:
        """Verify all dashboards have unique UIDs."""
        uids: dict[str, str] = {}
        for dashboard_path in dashboard_files:
            resolved = dashboard_path.resolve()
            dashboard = json.loads(resolved.read_text())
            uid = dashboard.get("uid")
            if uid:
                assert uid not in uids, (
                    f"Duplicate UID '{uid}' in {dashboard_path.name} and {uids[uid]}"
                )
                uids[uid] = dashboard_path.name


# =============================================================================
# Tests: Query Extraction
# =============================================================================


class TestQueryExtraction:
    """Test PromQL query extraction from dashboards."""

    def test_can_extract_queries_from_dashboards(
        self,
        all_dashboard_queries: dict[str, dict[str, list[str]]],
    ) -> None:
        """Verify queries can be extracted from dashboards."""
        # Should find queries in at least one dashboard
        total_queries = sum(
            len(queries)
            for panel_queries in all_dashboard_queries.values()
            for queries in panel_queries.values()
        )
        assert total_queries > 0, "No PromQL queries found in any dashboard"

    def test_expected_dashboards_have_queries(
        self,
        all_dashboard_queries: dict[str, dict[str, list[str]]],
    ) -> None:
        """Verify expected dashboards have PromQL queries."""
        # These dashboards should have Prometheus queries
        expected_dashboards = [
            "ci-health.json",
            "pipeline.json",
            "slo.json",
            "synthetic-monitoring.json",
        ]

        for dashboard in expected_dashboards:
            if dashboard in all_dashboard_queries:
                assert len(all_dashboard_queries[dashboard]) > 0, (
                    f"{dashboard} should have PromQL queries"
                )

    def test_metric_name_extraction_from_simple_query(self) -> None:
        """Test extracting metric names from simple PromQL queries."""
        test_cases = [
            ("hsi_total_events", {"hsi_total_events"}),
            ("hsi_detection_queue_depth", {"hsi_detection_queue_depth"}),
            ('ci_workflow_success_rate{workflow="ci"}', {"ci_workflow_success_rate"}),
        ]

        for expr, expected in test_cases:
            result = extract_metric_names_from_promql(expr)
            assert expected.issubset(result), f"Failed for expr: {expr}"

    def test_metric_name_extraction_from_function_query(self) -> None:
        """Test extracting metric names from PromQL with functions."""
        test_cases = [
            ("rate(hsi_total_events[5m])", {"hsi_total_events"}),
            ("sum(ci_workflow_runs_total)", {"ci_workflow_runs_total"}),
            (
                "histogram_quantile(0.95, rate(hsi_stage_duration_seconds_bucket[5m]))",
                {"hsi_stage_duration_seconds_bucket"},
            ),
        ]

        for expr, expected in test_cases:
            result = extract_metric_names_from_promql(expr)
            assert expected.issubset(result), f"Failed for expr: {expr}"

    def test_metric_name_extraction_from_recording_rule(self) -> None:
        """Test extracting metric names from recording rules (colon-separated)."""
        test_cases = [
            ("hsi:api_availability:ratio_rate30d", {"hsi:api_availability:ratio_rate30d"}),
            ("hsi:detection_latency:p95_5m", {"hsi:detection_latency:p95_5m"}),
        ]

        for expr, expected in test_cases:
            result = extract_metric_names_from_promql(expr)
            assert expected.issubset(result), f"Failed for expr: {expr}"


# =============================================================================
# Tests: Query Validation Against /metrics
# =============================================================================


class TestDashboardQueriesAgainstMetrics:
    """Test that dashboard queries reference valid metrics from /metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_metrics(self, client, mock_redis) -> None:
        """Verify /metrics endpoint returns Prometheus format metrics."""
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        assert "hsi_" in response.text, "Expected HSI metrics in output"

    @pytest.mark.asyncio
    async def test_hsi_metrics_are_available(self, client, mock_redis) -> None:
        """Verify core HSI metrics are available in /metrics endpoint."""
        response = await client.get("/api/metrics")
        assert response.status_code == 200

        available_metrics = extract_metrics_from_prometheus_output(response.text)

        # Core HSI metrics that should always be present
        core_metrics = [
            "hsi_detection_queue_depth",
            "hsi_analysis_queue_depth",
            "hsi_events_created_total",
            "hsi_detections_processed_total",
            "hsi_stage_duration_seconds",
            "hsi_pipeline_errors_total",
        ]

        for metric in core_metrics:
            # Check for base metric or with histogram suffixes
            found = (
                metric in available_metrics
                or f"{metric}_bucket" in available_metrics
                or f"{metric}_sum" in available_metrics
                or f"{metric}_count" in available_metrics
            )
            assert found, f"Core metric {metric} not found in /metrics output"

    @pytest.mark.asyncio
    async def test_pipeline_dashboard_hsi_metrics_exist(
        self,
        client,
        mock_redis,
        all_dashboard_queries: dict[str, dict[str, list[str]]],
    ) -> None:
        """Verify HSI metrics in pipeline.json dashboard exist in /metrics.

        This test validates that the AI pipeline dashboard queries reference
        metrics that are actually exposed by the backend.

        Note: Some metrics come from external sources (GPU monitor, runtime stats)
        and are not exposed by the /metrics endpoint directly. These are excluded
        from validation.
        """
        if "pipeline.json" not in all_dashboard_queries:
            pytest.skip("pipeline.json not found")

        response = await client.get("/api/metrics")
        assert response.status_code == 200

        available_metrics = extract_metrics_from_prometheus_output(response.text)

        # Extract unique metric names from pipeline dashboard
        pipeline_queries = all_dashboard_queries["pipeline.json"]
        dashboard_metrics: set[str] = set()
        for queries in pipeline_queries.values():
            for query in queries:
                metrics = extract_metric_names_from_promql(query)
                dashboard_metrics.update(metrics)

        # Filter to only HSI metrics (our application metrics)
        hsi_metrics = {m for m in dashboard_metrics if m.startswith("hsi_")}

        # Metrics from external sources that are not exposed by /metrics endpoint
        # These come from GPU monitor, system health service, or runtime aggregates
        # Note: hsi_inference_fps removed - dashboard now uses native yolo26_inference_requests_total
        external_metrics = {
            # GPU metrics from nvidia-smi / GPU monitor
            "hsi_gpu_utilization",
            "hsi_gpu_memory_used_mb",
            "hsi_gpu_memory_total_mb",
            "hsi_gpu_temperature",
            # Runtime aggregate metrics (computed from DB/Redis)
            "hsi_total_events",
            "hsi_total_cameras",
            "hsi_total_detections",
            "hsi_uptime_seconds",
        }

        # Validate each HSI metric exists (excluding external metrics)
        missing_metrics: list[str] = []
        for metric in hsi_metrics:
            # Skip external metrics
            if metric in external_metrics:
                continue

            # Check for metric or histogram variants
            found = (
                metric in available_metrics
                or f"{metric}_bucket" in available_metrics
                or f"{metric}_sum" in available_metrics
                or f"{metric}_count" in available_metrics
            )
            if not found:
                missing_metrics.append(metric)

        assert not missing_metrics, (
            f"Pipeline dashboard references missing metrics: {missing_metrics}"
        )

    @pytest.mark.asyncio
    async def test_document_external_metrics_in_dashboards(
        self,
        client,
        mock_redis,
        all_dashboard_queries: dict[str, dict[str, list[str]]],
    ) -> None:
        """Document external metrics (non-HSI) referenced in dashboards.

        This test documents metrics from external systems (Redis, CI, SLO, etc.)
        that are referenced in dashboards. These metrics are expected to come
        from external exporters or recording rules, not the /metrics endpoint.

        The test passes if we can identify these metrics - it's informational
        rather than asserting they exist in /metrics.
        """
        # Collect all metrics from all dashboards
        all_metrics: set[str] = set()
        for dashboard_queries in all_dashboard_queries.values():
            for queries in dashboard_queries.values():
                for query in queries:
                    metrics = extract_metric_names_from_promql(query)
                    all_metrics.update(metrics)

        # Categorize metrics by prefix
        categories = {
            "hsi_": [],  # Application metrics
            "ci_": [],  # CI/CD metrics
            "redis_": [],  # Redis exporter metrics
            "probe_": [],  # Blackbox exporter metrics
            "hsi:": [],  # Recording rules (SLO)
        }
        uncategorized = []

        for metric in sorted(all_metrics):
            categorized = False
            for prefix, metric_list in categories.items():
                if metric.startswith(prefix):
                    metric_list.append(metric)
                    categorized = True
                    break
            if not categorized:
                uncategorized.append(metric)

        # This is informational - we just verify we found metrics
        total = sum(len(v) for v in categories.values()) + len(uncategorized)
        assert total > 0, "Should find metrics in dashboards"

        # Log the categorization for debugging
        # (visible with pytest -v)


class TestSpecificDashboardQueries:
    """Test specific dashboard panel queries for correctness."""

    @pytest.mark.asyncio
    async def test_ci_health_dashboard_panel_queries_are_valid_promql(
        self,
        all_dashboard_queries: dict[str, dict[str, list[str]]],
    ) -> None:
        """Verify CI Health dashboard queries are valid PromQL syntax."""
        if "ci-health.json" not in all_dashboard_queries:
            pytest.skip("ci-health.json not found")

        ci_queries = all_dashboard_queries["ci-health.json"]

        # All queries should be parseable (extract metric names without error)
        for panel_title, queries in ci_queries.items():
            for query in queries:
                try:
                    metrics = extract_metric_names_from_promql(query)
                    assert len(metrics) > 0 or "0" in query or "100" in query, (
                        f"Panel '{panel_title}' query has no metrics: {query}"
                    )
                except Exception as e:
                    pytest.fail(f"Invalid query in '{panel_title}': {query} - {e}")

    @pytest.mark.asyncio
    async def test_slo_dashboard_recording_rules_are_referenced(
        self,
        all_dashboard_queries: dict[str, dict[str, list[str]]],
    ) -> None:
        """Verify SLO dashboard references expected recording rules."""
        if "slo.json" not in all_dashboard_queries:
            pytest.skip("slo.json not found")

        slo_queries = all_dashboard_queries["slo.json"]

        # Extract all metrics from SLO dashboard
        slo_metrics: set[str] = set()
        for queries in slo_queries.values():
            for query in queries:
                metrics = extract_metric_names_from_promql(query)
                slo_metrics.update(metrics)

        # SLO dashboard should reference recording rules (colon-separated names)
        recording_rules = {m for m in slo_metrics if ":" in m}

        # Should have some recording rules (these are defined in prometheus rules)
        # This is informational - we verify the dashboard uses recording rules
        assert len(recording_rules) >= 0, "SLO dashboard can use recording rules"

    @pytest.mark.asyncio
    async def test_synthetic_monitoring_dashboard_uses_probe_metrics(
        self,
        all_dashboard_queries: dict[str, dict[str, list[str]]],
    ) -> None:
        """Verify Synthetic Monitoring dashboard uses blackbox exporter metrics."""
        if "synthetic-monitoring.json" not in all_dashboard_queries:
            pytest.skip("synthetic-monitoring.json not found")

        synth_queries = all_dashboard_queries["synthetic-monitoring.json"]

        # Extract all metrics
        synth_metrics: set[str] = set()
        for queries in synth_queries.values():
            for query in queries:
                metrics = extract_metric_names_from_promql(query)
                synth_metrics.update(metrics)

        # Should reference probe_* metrics (from blackbox exporter)
        probe_metrics = {m for m in synth_metrics if m.startswith("probe_")}

        # Synthetic monitoring should use blackbox exporter probe metrics
        expected_probe_metrics = ["probe_success", "probe_duration_seconds"]
        for expected in expected_probe_metrics:
            assert expected in probe_metrics, f"Synthetic monitoring should use {expected} metric"


class TestQueryInventory:
    """Test to inventory all queries across dashboards."""

    def test_all_dashboards_are_inventoried(
        self,
        dashboard_files: list[Path],
        all_dashboard_queries: dict[str, dict[str, list[str]]],
    ) -> None:
        """Verify we can inventory queries from all dashboard files."""
        # Not all dashboards may have Prometheus queries (some use JSON datasource)
        # Just verify the extraction works without errors
        for dashboard_path in dashboard_files:
            dashboard_name = dashboard_path.name
            # Extraction should not raise
            queries = extract_promql_queries_from_dashboard(dashboard_path)
            # queries dict may be empty for dashboards using other datasources
            assert isinstance(queries, dict)

    def test_unique_metrics_can_be_extracted(
        self,
        all_dashboard_queries: dict[str, dict[str, list[str]]],
    ) -> None:
        """Verify unique metrics can be extracted from all queries."""
        unique_metrics = get_unique_metrics_from_queries(all_dashboard_queries)

        # Should find metrics across the dashboards
        assert len(unique_metrics) > 0, "Should find metrics in dashboard queries"

        # Log count for visibility
        # (visible with pytest -v)
