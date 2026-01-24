"""Integration tests for Prometheus alert rule trigger verification.

These tests verify that Prometheus alert rules actually fire when thresholds
are exceeded. The tests parse alerting-rules.yml and prometheus_rules.yml
and verify that the PromQL expressions evaluate correctly under various
metric conditions.

Key test categories:
1. Pipeline health alerts (HSIPipelineDown, HSIPipelineUnhealthy)
2. Database alerts (HSIDatabaseUnhealthy, HSIDatabaseConnectionPoolLow)
3. Threshold-based alerts with edge cases
4. Alert severity level verification

Note: These tests use PromQL expression parsing and simulation rather than
a live Prometheus instance. For full end-to-end testing with Prometheus,
see tests/smoke/test_monitoring_smoke.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import pytest
import yaml

# Path to the monitoring directory (relative to project root)
MONITORING_DIR = Path(__file__).parent.parent.parent.parent / "monitoring"
ALERTING_RULES_PATH = MONITORING_DIR / "alerting-rules.yml"
PROMETHEUS_RULES_PATH = MONITORING_DIR / "prometheus_rules.yml"

# Mark all tests as integration tests
pytestmark = [pytest.mark.integration]


# =============================================================================
# Alert Rule Data Classes
# =============================================================================


@dataclass
class AlertRule:
    """Represents a parsed Prometheus alert rule."""

    name: str
    expr: str
    severity: str
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    for_duration: str | None = None

    @property
    def component(self) -> str | None:
        """Get the component label if present."""
        return self.labels.get("component")


@dataclass
class MetricCondition:
    """Represents a set of metric values for testing alert conditions."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)


# =============================================================================
# PromQL Expression Evaluator
# =============================================================================


class PromQLEvaluator:
    """Simple PromQL expression evaluator for alert rule testing.

    This evaluator handles basic PromQL expressions found in alerting rules,
    including comparisons, arithmetic operations, and basic functions.

    Note: This is a simplified evaluator for testing purposes. It does not
    implement the full PromQL specification. Complex expressions with
    rate(), histogram_quantile(), or multi-metric operations return
    the provided sample values directly for threshold testing.
    """

    # Regex pattern for metric names (including recording rule names with colons)
    METRIC_NAME_PATTERN = r"[\w:]+"

    def __init__(self, metrics: dict[str, float]) -> None:
        """Initialize the evaluator with metric values.

        Args:
            metrics: Dictionary mapping metric names to their values.
                     For labeled metrics, use format "metric_name{label=value}".
        """
        self.metrics = metrics

    def evaluate(self, expr: str) -> bool | None:  # noqa: PLR0911
        """Evaluate a PromQL expression and return whether it would fire.

        Args:
            expr: PromQL expression from an alert rule

        Returns:
            True if the expression evaluates to true (alert fires),
            False if it evaluates to false,
            None if the expression cannot be evaluated (missing metrics/complex).

        Note:
            This method intentionally has many branches and return statements
            to handle the various PromQL expression patterns found in alerting rules.
        """
        # Clean up the expression
        expr = expr.strip()

        # Handle simple comparison expressions: metric_name == value
        # Metric names can include colons for recording rules (e.g., hsi:gpu:memory_utilization)
        simple_eq_match = re.match(
            rf"^({self.METRIC_NAME_PATTERN})(?:\{{[^}}]*\}})?\s*==\s*(\d+(?:\.\d+)?)$", expr
        )
        if simple_eq_match:
            metric_name = simple_eq_match.group(1)
            threshold = float(simple_eq_match.group(2))
            metric_value = self._get_metric_value(metric_name)
            if metric_value is None:
                return None
            return metric_value == threshold

        # Handle != comparisons
        simple_neq_match = re.match(
            rf"^({self.METRIC_NAME_PATTERN})(?:\{{[^}}]*\}})?\s*!=\s*(\d+(?:\.\d+)?)$", expr
        )
        if simple_neq_match:
            metric_name = simple_neq_match.group(1)
            threshold = float(simple_neq_match.group(2))
            metric_value = self._get_metric_value(metric_name)
            if metric_value is None:
                return None
            return metric_value != threshold

        # Handle > comparisons
        simple_gt_match = re.match(
            rf"^({self.METRIC_NAME_PATTERN})(?:\{{[^}}]*\}})?\s*>\s*(\d+(?:\.\d+)?)$", expr
        )
        if simple_gt_match:
            metric_name = simple_gt_match.group(1)
            threshold = float(simple_gt_match.group(2))
            metric_value = self._get_metric_value(metric_name)
            if metric_value is None:
                return None
            return metric_value > threshold

        # Handle < comparisons
        simple_lt_match = re.match(
            rf"^({self.METRIC_NAME_PATTERN})(?:\{{[^}}]*\}})?\s*<\s*(\d+(?:\.\d+)?)$", expr
        )
        if simple_lt_match:
            metric_name = simple_lt_match.group(1)
            threshold = float(simple_lt_match.group(2))
            metric_value = self._get_metric_value(metric_name)
            if metric_value is None:
                return None
            return metric_value < threshold

        # Handle >= comparisons
        simple_gte_match = re.match(
            rf"^({self.METRIC_NAME_PATTERN})(?:\{{[^}}]*\}})?\s*>=\s*(\d+(?:\.\d+)?)$", expr
        )
        if simple_gte_match:
            metric_name = simple_gte_match.group(1)
            threshold = float(simple_gte_match.group(2))
            metric_value = self._get_metric_value(metric_name)
            if metric_value is None:
                return None
            return metric_value >= threshold

        # Handle <= comparisons
        simple_lte_match = re.match(
            rf"^({self.METRIC_NAME_PATTERN})(?:\{{[^}}]*\}})?\s*<=\s*(\d+(?:\.\d+)?)$", expr
        )
        if simple_lte_match:
            metric_name = simple_lte_match.group(1)
            threshold = float(simple_lte_match.group(2))
            metric_value = self._get_metric_value(metric_name)
            if metric_value is None:
                return None
            return metric_value <= threshold

        # Handle expressions with 'or' (e.g., "metric1 > 500 or metric2 > 200")
        if " or " in expr:
            parts = expr.split(" or ")
            results = [self.evaluate(part.strip()) for part in parts]
            if None in results:
                # If any part can't be evaluated, try if any True parts exist
                return any(r for r in results if r is True)
            return any(results)

        # Handle expressions with 'and' (e.g., "metric1 > 10 and metric2 > 0")
        if " and " in expr:
            parts = expr.split(" and ")
            results = [self.evaluate(part.strip()) for part in parts]
            if None in results:
                return None
            return all(results)

        # Handle division expressions for ratio calculations
        # e.g., (hsi_gpu_memory_used_mb / hsi_gpu_memory_total_mb) * 100 > 95
        ratio_match = re.search(
            rf"\(\s*({self.METRIC_NAME_PATTERN})\s*/\s*({self.METRIC_NAME_PATTERN})\s*\)"
            rf"\s*\*?\s*(\d+)?\s*([><=]+)\s*(\d+(?:\.\d+)?)",
            expr,
        )
        if ratio_match:
            numerator = ratio_match.group(1)
            denominator = ratio_match.group(2)
            multiplier_str = ratio_match.group(3)
            multiplier = float(multiplier_str) if multiplier_str else 1.0
            operator = ratio_match.group(4)
            threshold = float(ratio_match.group(5))

            num_val = self._get_metric_value(numerator)
            denom_val = self._get_metric_value(denominator)

            if num_val is None or denom_val is None or denom_val == 0:
                return None

            ratio = (num_val / denom_val) * multiplier
            return self._compare(ratio, operator, threshold)

        # Handle simple division without parentheses
        # e.g., metric1 / metric2 < 0.2
        simple_div_match = re.search(
            rf"({self.METRIC_NAME_PATTERN})\s*/\s*({self.METRIC_NAME_PATTERN})\s*([><=]+)\s*(\d+(?:\.\d+)?)",
            expr,
        )
        if simple_div_match:
            numerator = simple_div_match.group(1)
            denominator = simple_div_match.group(2)
            operator = simple_div_match.group(3)
            threshold = float(simple_div_match.group(4))

            num_val = self._get_metric_value(numerator)
            denom_val = self._get_metric_value(denominator)

            if num_val is None or denom_val is None or denom_val == 0:
                return None

            ratio = num_val / denom_val
            return self._compare(ratio, operator, threshold)

        # Handle expressions with up{job="..."} == 0
        up_match = re.match(r'up\{job="([^"]+)"\}\s*==\s*(\d+)', expr)
        if up_match:
            job = up_match.group(1)
            expected = int(up_match.group(2))
            metric_key = f'up{{job="{job}"}}'
            metric_value = self.metrics.get(metric_key)
            if metric_value is None:
                # Try without the label
                metric_value = self.metrics.get("up")
            if metric_value is None:
                return None
            return metric_value == expected

        # For complex expressions (rate, histogram_quantile, etc.),
        # check if we have a pre-computed result value
        # These would be provided by the test case
        if "_result" in self.metrics:
            result = self.metrics["_result"]
            # Extract threshold from expression
            threshold_match = re.search(r"([><=!]+)\s*(\d+(?:\.\d+)?)\s*$", expr)
            if threshold_match:
                operator = threshold_match.group(1)
                threshold = float(threshold_match.group(2))
                return self._compare(result, operator, threshold)

        # Cannot evaluate
        return None

    def _get_metric_value(self, metric_name: str) -> float | None:
        """Get the value of a metric by name.

        Args:
            metric_name: The metric name to look up

        Returns:
            The metric value, or None if not found
        """
        # Direct lookup
        if metric_name in self.metrics:
            return self.metrics[metric_name]

        # Try with any labels
        for key, value in self.metrics.items():
            if key.startswith(metric_name + "{") or key == metric_name:
                return value

        return None

    def _compare(self, value: float, operator: str, threshold: float) -> bool:  # noqa: PLR0911
        """Compare a value against a threshold.

        Args:
            value: The computed value
            operator: Comparison operator (>, <, ==, !=, >=, <=)
            threshold: The threshold to compare against

        Returns:
            Result of the comparison
        """
        if operator == ">":
            return value > threshold
        if operator == "<":
            return value < threshold
        if operator == "==":
            return value == threshold
        if operator == "!=":
            return value != threshold
        if operator == ">=":
            return value >= threshold
        if operator == "<=":
            return value <= threshold
        return False


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def alerting_rules_data() -> dict[str, Any]:
    """Load and parse alerting-rules.yml."""
    if not ALERTING_RULES_PATH.exists():
        pytest.skip(f"Alerting rules file not found: {ALERTING_RULES_PATH}")
    return yaml.safe_load(ALERTING_RULES_PATH.read_text())


@pytest.fixture
def prometheus_rules_data() -> dict[str, Any]:
    """Load and parse prometheus_rules.yml."""
    if not PROMETHEUS_RULES_PATH.exists():
        pytest.skip(f"Prometheus rules file not found: {PROMETHEUS_RULES_PATH}")
    return yaml.safe_load(PROMETHEUS_RULES_PATH.read_text())


@pytest.fixture
def all_alert_rules(
    alerting_rules_data: dict[str, Any],
    prometheus_rules_data: dict[str, Any],
) -> list[AlertRule]:
    """Extract all alert rules from both rule files."""
    rules = []

    for data in [alerting_rules_data, prometheus_rules_data]:
        for group in data.get("groups", []):
            for rule in group.get("rules", []):
                if "alert" in rule:
                    rules.append(
                        AlertRule(
                            name=rule["alert"],
                            expr=rule["expr"],
                            severity=rule.get("labels", {}).get("severity", "unknown"),
                            labels=rule.get("labels", {}),
                            annotations=rule.get("annotations", {}),
                            for_duration=rule.get("for"),
                        )
                    )

    return rules


def get_alert_by_name(
    rules: list[AlertRule],
    name: str,
) -> AlertRule | None:
    """Get an alert rule by name."""
    for rule in rules:
        if rule.name == name:
            return rule
    return None


# =============================================================================
# Test Classes - Pipeline Health Alerts
# =============================================================================


class TestHSIPipelineDownAlert:
    """Tests for HSIPipelineDown alert rule firing."""

    def test_fires_when_backend_down(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSIPipelineDown fires when up{job='backend-liveness'} == 0."""
        rule = get_alert_by_name(all_alert_rules, "HSIPipelineDown")
        assert rule is not None, "HSIPipelineDown rule not found"

        # Simulate backend being down
        evaluator = PromQLEvaluator(
            {
                'up{job="backend-liveness"}': 0,
                "up": 0,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is True, "Alert should fire when backend is down"

    def test_does_not_fire_when_backend_up(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSIPipelineDown does not fire when backend is healthy."""
        rule = get_alert_by_name(all_alert_rules, "HSIPipelineDown")
        assert rule is not None

        # Simulate backend being up
        evaluator = PromQLEvaluator(
            {
                'up{job="backend-liveness"}': 1,
                "up": 1,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is False, "Alert should not fire when backend is up"

    def test_severity_is_critical(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSIPipelineDown has critical severity."""
        rule = get_alert_by_name(all_alert_rules, "HSIPipelineDown")
        assert rule is not None
        assert rule.severity == "critical", "HSIPipelineDown must be critical severity"


class TestHSIPipelineUnhealthyAlert:
    """Tests for HSIPipelineUnhealthy alert rule firing."""

    def test_fires_when_health_status_not_one(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSIPipelineUnhealthy fires when hsi_health_status != 1."""
        rule = get_alert_by_name(all_alert_rules, "HSIPipelineUnhealthy")
        assert rule is not None, "HSIPipelineUnhealthy rule not found"

        # Test with health status = 0 (unhealthy)
        evaluator = PromQLEvaluator({"hsi_health_status": 0})
        result = evaluator.evaluate(rule.expr)
        assert result is True, "Alert should fire when health status is 0"

        # Test with health status = 0.5 (degraded)
        evaluator = PromQLEvaluator({"hsi_health_status": 0.5})
        result = evaluator.evaluate(rule.expr)
        assert result is True, "Alert should fire when health status is degraded"

    def test_does_not_fire_when_healthy(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSIPipelineUnhealthy does not fire when health status is 1."""
        rule = get_alert_by_name(all_alert_rules, "HSIPipelineUnhealthy")
        assert rule is not None

        evaluator = PromQLEvaluator({"hsi_health_status": 1})
        result = evaluator.evaluate(rule.expr)
        assert result is False, "Alert should not fire when health status is 1"


# =============================================================================
# Test Classes - Database Alerts
# =============================================================================


class TestHSIDatabaseUnhealthyAlert:
    """Tests for HSIDatabaseUnhealthy alert rule firing."""

    def test_fires_when_connection_pool_exhausted(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSIDatabaseUnhealthy fires when connection pool is empty."""
        rule = get_alert_by_name(all_alert_rules, "HSIDatabaseUnhealthy")
        assert rule is not None, "HSIDatabaseUnhealthy rule not found"

        # Simulate exhausted connection pool
        evaluator = PromQLEvaluator(
            {
                "hsi_database_connection_pool_available": 0,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is True, "Alert should fire when connection pool is exhausted"

    def test_does_not_fire_with_available_connections(
        self, all_alert_rules: list[AlertRule]
    ) -> None:
        """Test HSIDatabaseUnhealthy does not fire with available connections."""
        rule = get_alert_by_name(all_alert_rules, "HSIDatabaseUnhealthy")
        assert rule is not None

        evaluator = PromQLEvaluator(
            {
                "hsi_database_connection_pool_available": 5,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is False, "Alert should not fire with available connections"

    def test_severity_is_critical(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSIDatabaseUnhealthy has critical severity."""
        rule = get_alert_by_name(all_alert_rules, "HSIDatabaseUnhealthy")
        assert rule is not None
        assert rule.severity == "critical"


class TestHSIDatabaseConnectionPoolLowAlert:
    """Tests for HSIDatabaseConnectionPoolLow alert rule firing."""

    def test_fires_when_pool_below_20_percent(self, all_alert_rules: list[AlertRule]) -> None:
        """Test alert fires when available connections < 20% of pool size."""
        rule = get_alert_by_name(all_alert_rules, "HSIDatabaseConnectionPoolLow")
        assert rule is not None, "HSIDatabaseConnectionPoolLow rule not found"

        # 10% available (2 of 20)
        evaluator = PromQLEvaluator(
            {
                "hsi_database_connection_pool_available": 2,
                "hsi_database_connection_pool_size": 20,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is True, "Alert should fire when pool is below 20%"

    def test_does_not_fire_above_20_percent(self, all_alert_rules: list[AlertRule]) -> None:
        """Test alert does not fire when available connections >= 20%."""
        rule = get_alert_by_name(all_alert_rules, "HSIDatabaseConnectionPoolLow")
        assert rule is not None

        # 25% available (5 of 20)
        evaluator = PromQLEvaluator(
            {
                "hsi_database_connection_pool_available": 5,
                "hsi_database_connection_pool_size": 20,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is False, "Alert should not fire when pool is above 20%"

    def test_edge_case_exactly_20_percent(self, all_alert_rules: list[AlertRule]) -> None:
        """Test edge case when available connections are exactly 20%."""
        rule = get_alert_by_name(all_alert_rules, "HSIDatabaseConnectionPoolLow")
        assert rule is not None

        # Exactly 20% available (4 of 20)
        evaluator = PromQLEvaluator(
            {
                "hsi_database_connection_pool_available": 4,
                "hsi_database_connection_pool_size": 20,
            }
        )
        result = evaluator.evaluate(rule.expr)
        # 4/20 = 0.2, which is NOT < 0.2
        assert result is False, "Alert should not fire at exactly 20%"

    def test_severity_is_warning(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSIDatabaseConnectionPoolLow has warning severity."""
        rule = get_alert_by_name(all_alert_rules, "HSIDatabaseConnectionPoolLow")
        assert rule is not None
        assert rule.severity == "warning"


# =============================================================================
# Test Classes - Redis Alerts
# =============================================================================


class TestHSIRedisUnhealthyAlert:
    """Tests for HSIRedisUnhealthy alert rule firing."""

    def test_fires_when_redis_down(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSIRedisUnhealthy fires when Redis is unreachable."""
        rule = get_alert_by_name(all_alert_rules, "HSIRedisUnhealthy")
        assert rule is not None, "HSIRedisUnhealthy rule not found"

        evaluator = PromQLEvaluator(
            {
                'up{job="redis"}': 0,
                "up": 0,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is True, "Alert should fire when Redis is down"

    def test_severity_is_critical(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSIRedisUnhealthy has critical severity."""
        rule = get_alert_by_name(all_alert_rules, "HSIRedisUnhealthy")
        assert rule is not None
        assert rule.severity == "critical"


class TestHSIRedisMemoryHighAlert:
    """Tests for HSIRedisMemoryHigh alert rule firing."""

    def test_fires_when_memory_above_80_percent(self, all_alert_rules: list[AlertRule]) -> None:
        """Test alert fires when Redis memory usage exceeds 80%."""
        rule = get_alert_by_name(all_alert_rules, "HSIRedisMemoryHigh")
        assert rule is not None, "HSIRedisMemoryHigh rule not found"

        # 85% memory usage
        evaluator = PromQLEvaluator(
            {
                "redis_memory_used_bytes": 850_000_000,
                "redis_memory_max_bytes": 1_000_000_000,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is True, "Alert should fire when Redis memory > 80%"

    def test_does_not_fire_below_80_percent(self, all_alert_rules: list[AlertRule]) -> None:
        """Test alert does not fire when Redis memory usage is below 80%."""
        rule = get_alert_by_name(all_alert_rules, "HSIRedisMemoryHigh")
        assert rule is not None

        # 70% memory usage
        evaluator = PromQLEvaluator(
            {
                "redis_memory_used_bytes": 700_000_000,
                "redis_memory_max_bytes": 1_000_000_000,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is False, "Alert should not fire when Redis memory < 80%"


# =============================================================================
# Test Classes - GPU Alerts
# =============================================================================


class TestHSIGPUMemoryHighAlert:
    """Tests for HSIGPUMemoryHigh alert rule firing."""

    def test_fires_when_gpu_memory_above_90_percent(self, all_alert_rules: list[AlertRule]) -> None:
        """Test alert fires when GPU memory utilization exceeds 90%."""
        rule = get_alert_by_name(all_alert_rules, "HSIGPUMemoryHigh")
        assert rule is not None, "HSIGPUMemoryHigh rule not found"

        evaluator = PromQLEvaluator(
            {
                "hsi:gpu:memory_utilization": 0.95,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is True, "Alert should fire when GPU memory > 90%"

    def test_does_not_fire_at_89_percent(self, all_alert_rules: list[AlertRule]) -> None:
        """Test alert does not fire when GPU memory is at 89%."""
        rule = get_alert_by_name(all_alert_rules, "HSIGPUMemoryHigh")
        assert rule is not None

        evaluator = PromQLEvaluator(
            {
                "hsi:gpu:memory_utilization": 0.89,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is False, "Alert should not fire when GPU memory < 90%"

    def test_severity_is_critical(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSIGPUMemoryHigh has critical severity."""
        rule = get_alert_by_name(all_alert_rules, "HSIGPUMemoryHigh")
        assert rule is not None
        assert rule.severity == "critical"


class TestHSIGPUMemoryElevatedAlert:
    """Tests for HSIGPUMemoryElevated alert rule firing."""

    def test_fires_when_gpu_memory_above_75_percent(self, all_alert_rules: list[AlertRule]) -> None:
        """Test alert fires when GPU memory utilization exceeds 75%."""
        rule = get_alert_by_name(all_alert_rules, "HSIGPUMemoryElevated")
        assert rule is not None, "HSIGPUMemoryElevated rule not found"

        evaluator = PromQLEvaluator(
            {
                "hsi:gpu:memory_utilization": 0.80,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is True, "Alert should fire when GPU memory > 75%"

    def test_severity_is_warning(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSIGPUMemoryElevated has warning severity."""
        rule = get_alert_by_name(all_alert_rules, "HSIGPUMemoryElevated")
        assert rule is not None
        assert rule.severity == "warning"


# =============================================================================
# Test Classes - Queue Alerts
# =============================================================================


class TestHSIDetectionQueueHighAlert:
    """Tests for HSIDetectionQueueHigh alert rule firing."""

    def test_fires_when_queue_above_100(self, all_alert_rules: list[AlertRule]) -> None:
        """Test alert fires when detection queue exceeds 100 items."""
        rule = get_alert_by_name(all_alert_rules, "HSIDetectionQueueHigh")
        assert rule is not None, "HSIDetectionQueueHigh rule not found"

        evaluator = PromQLEvaluator(
            {
                "hsi_detection_queue_size": 150,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is True, "Alert should fire when queue > 100"

    def test_does_not_fire_at_100(self, all_alert_rules: list[AlertRule]) -> None:
        """Test alert does not fire when queue is exactly 100."""
        rule = get_alert_by_name(all_alert_rules, "HSIDetectionQueueHigh")
        assert rule is not None

        evaluator = PromQLEvaluator(
            {
                "hsi_detection_queue_size": 100,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is False, "Alert should not fire when queue == 100"


class TestHSIQueueCriticalAlert:
    """Tests for HSIQueueCritical alert rule firing."""

    def test_fires_when_detection_queue_above_500(self, all_alert_rules: list[AlertRule]) -> None:
        """Test alert fires when detection queue exceeds 500."""
        rule = get_alert_by_name(all_alert_rules, "HSIQueueCritical")
        assert rule is not None, "HSIQueueCritical rule not found"

        evaluator = PromQLEvaluator(
            {
                "hsi_detection_queue_size": 600,
                "hsi_analysis_queue_size": 0,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is True, "Alert should fire when detection queue > 500"

    def test_fires_when_analysis_queue_above_200(self, all_alert_rules: list[AlertRule]) -> None:
        """Test alert fires when analysis queue exceeds 200."""
        rule = get_alert_by_name(all_alert_rules, "HSIQueueCritical")
        assert rule is not None

        evaluator = PromQLEvaluator(
            {
                "hsi_detection_queue_size": 0,
                "hsi_analysis_queue_size": 250,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is True, "Alert should fire when analysis queue > 200"

    def test_severity_is_critical(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSIQueueCritical has critical severity."""
        rule = get_alert_by_name(all_alert_rules, "HSIQueueCritical")
        assert rule is not None
        assert rule.severity == "critical"


# =============================================================================
# Test Classes - WebSocket Alerts
# =============================================================================


class TestHSIWebSocketDownAlert:
    """Tests for HSIWebSocketDown alert rule firing."""

    def test_fires_when_success_rate_below_50_percent(
        self, all_alert_rules: list[AlertRule]
    ) -> None:
        """Test alert fires when WebSocket success rate drops below 50%."""
        rule = get_alert_by_name(all_alert_rules, "HSIWebSocketDown")
        assert rule is not None, "HSIWebSocketDown rule not found"

        evaluator = PromQLEvaluator(
            {
                "hsi:websocket:connection_success_rate_5m": 0.40,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is True, "Alert should fire when success rate < 50%"

    def test_severity_is_critical(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSIWebSocketDown has critical severity."""
        rule = get_alert_by_name(all_alert_rules, "HSIWebSocketDown")
        assert rule is not None
        assert rule.severity == "critical"


class TestHSINoWebSocketConnectionsAlert:
    """Tests for HSINoWebSocketConnections alert rule firing."""

    def test_fires_when_no_connections(self, all_alert_rules: list[AlertRule]) -> None:
        """Test alert fires when there are no active WebSocket connections."""
        rule = get_alert_by_name(all_alert_rules, "HSINoWebSocketConnections")
        assert rule is not None, "HSINoWebSocketConnections rule not found"

        evaluator = PromQLEvaluator(
            {
                "hsi:websocket:active_connections": 0,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is True, "Alert should fire when no active connections"

    def test_does_not_fire_with_connections(self, all_alert_rules: list[AlertRule]) -> None:
        """Test alert does not fire when there are active connections."""
        rule = get_alert_by_name(all_alert_rules, "HSINoWebSocketConnections")
        assert rule is not None

        evaluator = PromQLEvaluator(
            {
                "hsi:websocket:active_connections": 5,
            }
        )
        result = evaluator.evaluate(rule.expr)
        assert result is False, "Alert should not fire with active connections"

    def test_severity_is_info(self, all_alert_rules: list[AlertRule]) -> None:
        """Test HSINoWebSocketConnections has info severity."""
        rule = get_alert_by_name(all_alert_rules, "HSINoWebSocketConnections")
        assert rule is not None
        assert rule.severity == "info"


# =============================================================================
# Test Classes - prometheus_rules.yml Alerts
# =============================================================================


class TestAIDetectorUnavailableAlert:
    """Tests for AIDetectorUnavailable alert rule firing."""

    def test_fires_when_ai_unhealthy(self, prometheus_rules_data: dict) -> None:
        """Test alert fires when hsi_ai_healthy == 0."""
        rules = []
        for group in prometheus_rules_data.get("groups", []):
            for rule in group.get("rules", []):
                if rule.get("alert") == "AIDetectorUnavailable":
                    rules.append(rule)

        assert len(rules) == 1, "AIDetectorUnavailable rule should exist"
        rule = rules[0]

        evaluator = PromQLEvaluator({"hsi_ai_healthy": 0})
        result = evaluator.evaluate(rule["expr"])
        assert result is True, "Alert should fire when AI is unhealthy"

    def test_does_not_fire_when_ai_healthy(self, prometheus_rules_data: dict) -> None:
        """Test alert does not fire when hsi_ai_healthy == 1."""
        rule = None
        for group in prometheus_rules_data.get("groups", []):
            for r in group.get("rules", []):
                if r.get("alert") == "AIDetectorUnavailable":
                    rule = r
                    break

        assert rule is not None
        evaluator = PromQLEvaluator({"hsi_ai_healthy": 1})
        result = evaluator.evaluate(rule["expr"])
        assert result is False, "Alert should not fire when AI is healthy"


class TestDatabaseUnhealthyAlert:
    """Tests for DatabaseUnhealthy alert in prometheus_rules.yml."""

    def test_fires_when_database_unhealthy(self, prometheus_rules_data: dict) -> None:
        """Test alert fires when hsi_database_healthy == 0."""
        rule = None
        for group in prometheus_rules_data.get("groups", []):
            for r in group.get("rules", []):
                if r.get("alert") == "DatabaseUnhealthy":
                    rule = r
                    break

        assert rule is not None, "DatabaseUnhealthy rule should exist"

        evaluator = PromQLEvaluator({"hsi_database_healthy": 0})
        result = evaluator.evaluate(rule["expr"])
        assert result is True, "Alert should fire when database is unhealthy"

    def test_does_not_fire_when_database_healthy(self, prometheus_rules_data: dict) -> None:
        """Test alert does not fire when hsi_database_healthy == 1."""
        rule = None
        for group in prometheus_rules_data.get("groups", []):
            for r in group.get("rules", []):
                if r.get("alert") == "DatabaseUnhealthy":
                    rule = r
                    break

        assert rule is not None
        evaluator = PromQLEvaluator({"hsi_database_healthy": 1})
        result = evaluator.evaluate(rule["expr"])
        assert result is False, "Alert should not fire when database is healthy"


class TestAIGPUOverheatingAlert:
    """Tests for AIGPUOverheating alert rule firing."""

    def test_fires_when_temperature_above_85(self, prometheus_rules_data: dict) -> None:
        """Test alert fires when GPU temperature exceeds 85C."""
        rule = None
        for group in prometheus_rules_data.get("groups", []):
            for r in group.get("rules", []):
                if r.get("alert") == "AIGPUOverheating":
                    rule = r
                    break

        assert rule is not None, "AIGPUOverheating rule should exist"

        evaluator = PromQLEvaluator({"hsi_gpu_temperature": 90})
        result = evaluator.evaluate(rule["expr"])
        assert result is True, "Alert should fire when temperature > 85C"

    def test_does_not_fire_at_85(self, prometheus_rules_data: dict) -> None:
        """Test alert does not fire when GPU temperature is exactly 85C."""
        rule = None
        for group in prometheus_rules_data.get("groups", []):
            for r in group.get("rules", []):
                if r.get("alert") == "AIGPUOverheating":
                    rule = r
                    break

        assert rule is not None

        evaluator = PromQLEvaluator({"hsi_gpu_temperature": 85})
        result = evaluator.evaluate(rule["expr"])
        assert result is False, "Alert should not fire when temperature == 85C"


class TestAIGPUMemoryCriticalAlert:
    """Tests for AIGPUMemoryCritical alert rule firing."""

    def test_fires_when_vram_above_95_percent(self, prometheus_rules_data: dict) -> None:
        """Test alert fires when GPU VRAM usage exceeds 95%."""
        rule = None
        for group in prometheus_rules_data.get("groups", []):
            for r in group.get("rules", []):
                if r.get("alert") == "AIGPUMemoryCritical":
                    rule = r
                    break

        assert rule is not None, "AIGPUMemoryCritical rule should exist"

        # 96% VRAM usage (23040 of 24000 MB)
        evaluator = PromQLEvaluator(
            {
                "hsi_gpu_memory_used_mb": 23040,
                "hsi_gpu_memory_total_mb": 24000,
            }
        )
        result = evaluator.evaluate(rule["expr"])
        assert result is True, "Alert should fire when VRAM > 95%"

    def test_does_not_fire_at_90_percent(self, prometheus_rules_data: dict) -> None:
        """Test alert does not fire when GPU VRAM is at 90%."""
        rule = None
        for group in prometheus_rules_data.get("groups", []):
            for r in group.get("rules", []):
                if r.get("alert") == "AIGPUMemoryCritical":
                    rule = r
                    break

        assert rule is not None

        # 90% VRAM usage
        evaluator = PromQLEvaluator(
            {
                "hsi_gpu_memory_used_mb": 21600,
                "hsi_gpu_memory_total_mb": 24000,
            }
        )
        result = evaluator.evaluate(rule["expr"])
        assert result is False, "Alert should not fire when VRAM at 90%"


# =============================================================================
# Test Classes - Threshold Edge Cases
# =============================================================================


class TestThresholdEdgeCases:
    """Tests for edge cases around alert thresholds."""

    def test_detection_queue_boundary_values(self, all_alert_rules: list[AlertRule]) -> None:
        """Test detection queue threshold at boundary values."""
        rule = get_alert_by_name(all_alert_rules, "HSIDetectionQueueHigh")
        assert rule is not None

        # Test values around the threshold (100)
        test_cases = [
            (99, False, "Should not fire at 99"),
            (100, False, "Should not fire at exactly 100"),
            (101, True, "Should fire at 101"),
            (1000, True, "Should fire at 1000"),
        ]

        for value, expected, msg in test_cases:
            evaluator = PromQLEvaluator({"hsi_detection_queue_size": value})
            result = evaluator.evaluate(rule.expr)
            assert result is expected, msg

    def test_gpu_utilization_boundary_values(self, all_alert_rules: list[AlertRule]) -> None:
        """Test GPU utilization thresholds at boundary values."""
        rule_elevated = get_alert_by_name(all_alert_rules, "HSIGPUMemoryElevated")
        rule_high = get_alert_by_name(all_alert_rules, "HSIGPUMemoryHigh")

        assert rule_elevated is not None
        assert rule_high is not None

        # Test elevated threshold (75%)
        test_cases_elevated = [
            (0.74, False, "Should not fire at 74%"),
            (0.75, False, "Should not fire at exactly 75%"),
            (0.76, True, "Should fire at 76%"),
        ]

        for value, expected, msg in test_cases_elevated:
            evaluator = PromQLEvaluator({"hsi:gpu:memory_utilization": value})
            result = evaluator.evaluate(rule_elevated.expr)
            assert result is expected, msg

        # Test high/critical threshold (90%)
        test_cases_high = [
            (0.89, False, "Should not fire at 89%"),
            (0.90, False, "Should not fire at exactly 90%"),
            (0.91, True, "Should fire at 91%"),
        ]

        for value, expected, msg in test_cases_high:
            evaluator = PromQLEvaluator({"hsi:gpu:memory_utilization": value})
            result = evaluator.evaluate(rule_high.expr)
            assert result is expected, msg


# =============================================================================
# Test Classes - Severity Level Verification
# =============================================================================


class TestAlertSeverityLevels:
    """Tests to verify alert severity levels are correctly assigned."""

    # Expected severity levels for key alerts
    CRITICAL_ALERTS: ClassVar[list[str]] = [
        "HSIPipelineDown",
        "HSIPipelineUnhealthy",
        "HSIDatabaseUnhealthy",
        "HSIRedisUnhealthy",
        "HSIGPUMemoryHigh",
        "HSIQueueCritical",
        "HSIExtremeLatency",
        "HSICriticalErrorRate",
        "HSIWebSocketDown",
        "HSIAPIAvailabilityFastBurn",
        # prometheus_rules.yml
        "AIDetectorUnavailable",
        "AIBackendDown",
        "AIGPUOverheating",
        "AIGPUMemoryCritical",
        "AISystemUnhealthy",
        "DatabaseUnhealthy",
        "RedisUnhealthy",
    ]

    WARNING_ALERTS: ClassVar[list[str]] = [
        "HSIDatabaseConnectionPoolLow",
        "HSIRedisMemoryHigh",
        "HSIGPUMemoryElevated",
        "HSIGPUUtilizationLow",
        "HSIDetectionQueueHigh",
        "HSIAnalysisQueueHigh",
        "HSISlowDetection",
        "HSISlowAnalysis",
        "HSIHighErrorRate",
        "HSIDetectionFailureRate",
        "HSIAnalysisFailureRate",
        "HSIWebSocketConnectionFailures",
        "HSIAPIAvailabilitySlowBurn",
        # prometheus_rules.yml
        "AINemotronTimeout",
        "AIDetectorSlow",
        "AIHighErrorRate",
        "AIPipelineErrorSpike",
        "AIGPUTemperatureWarning",
        "AIGPUMemoryWarning",
        "AIDetectionQueueBacklog",
        "AIAnalysisQueueBacklog",
        "AISystemDegraded",
        "PrometheusTargetDown",
    ]

    INFO_ALERTS: ClassVar[list[str]] = [
        "HSINoWebSocketConnections",
    ]

    def test_critical_alerts_have_critical_severity(self, all_alert_rules: list[AlertRule]) -> None:
        """Verify all expected critical alerts have critical severity."""
        for alert_name in self.CRITICAL_ALERTS:
            rule = get_alert_by_name(all_alert_rules, alert_name)
            if rule is not None:
                assert rule.severity == "critical", (
                    f"Alert '{alert_name}' should have critical severity, but has '{rule.severity}'"
                )

    def test_warning_alerts_have_warning_severity(self, all_alert_rules: list[AlertRule]) -> None:
        """Verify all expected warning alerts have warning severity."""
        for alert_name in self.WARNING_ALERTS:
            rule = get_alert_by_name(all_alert_rules, alert_name)
            if rule is not None:
                assert rule.severity == "warning", (
                    f"Alert '{alert_name}' should have warning severity, but has '{rule.severity}'"
                )

    def test_info_alerts_have_info_severity(self, all_alert_rules: list[AlertRule]) -> None:
        """Verify all expected info alerts have info severity."""
        for alert_name in self.INFO_ALERTS:
            rule = get_alert_by_name(all_alert_rules, alert_name)
            if rule is not None:
                assert rule.severity == "info", (
                    f"Alert '{alert_name}' should have info severity, but has '{rule.severity}'"
                )

    def test_no_unknown_severity_levels(self, all_alert_rules: list[AlertRule]) -> None:
        """Verify all alerts have valid severity levels."""
        valid_severities = {"critical", "warning", "info"}
        for rule in all_alert_rules:
            assert rule.severity in valid_severities, (
                f"Alert '{rule.name}' has invalid severity '{rule.severity}'. "
                f"Valid values: {valid_severities}"
            )


# =============================================================================
# Test Classes - Alert Component Labels
# =============================================================================


class TestAlertComponentLabels:
    """Tests to verify alert rules have appropriate component labels."""

    def test_database_alerts_have_database_component(
        self, all_alert_rules: list[AlertRule]
    ) -> None:
        """Verify database-related alerts have correct component label."""
        database_alerts = [
            "HSIDatabaseUnhealthy",
            "HSIDatabaseConnectionPoolLow",
            "DatabaseUnhealthy",
        ]
        for alert_name in database_alerts:
            rule = get_alert_by_name(all_alert_rules, alert_name)
            if rule is not None:
                assert rule.component in {"database", "db"}, (
                    f"Alert '{alert_name}' should have database component"
                )

    def test_redis_alerts_have_redis_component(self, all_alert_rules: list[AlertRule]) -> None:
        """Verify Redis-related alerts have correct component label."""
        redis_alerts = [
            "HSIRedisUnhealthy",
            "HSIRedisMemoryHigh",
            "RedisUnhealthy",
        ]
        for alert_name in redis_alerts:
            rule = get_alert_by_name(all_alert_rules, alert_name)
            if rule is not None:
                assert rule.component in {"redis", "cache"}, (
                    f"Alert '{alert_name}' should have redis/cache component"
                )

    def test_gpu_alerts_have_gpu_component(self, all_alert_rules: list[AlertRule]) -> None:
        """Verify GPU-related alerts have correct component label."""
        gpu_alerts = [
            "HSIGPUMemoryHigh",
            "HSIGPUMemoryElevated",
            "HSIGPUUtilizationLow",
            "AIGPUOverheating",
            "AIGPUTemperatureWarning",
            "AIGPUMemoryCritical",
            "AIGPUMemoryWarning",
        ]
        for alert_name in gpu_alerts:
            rule = get_alert_by_name(all_alert_rules, alert_name)
            if rule is not None:
                assert rule.component == "gpu", f"Alert '{alert_name}' should have gpu component"
