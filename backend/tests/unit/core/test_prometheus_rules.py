"""Unit tests for Prometheus alerting rules syntax and structure validation.

These tests validate that the Prometheus alerting rules file:
1. Is valid YAML syntax
2. Contains required fields for alerting rules (alert, expr, labels, annotations)
3. Has valid severity levels
4. References metrics that exist in the system
5. Has reasonable 'for' durations

Validation can also be done with promtool:
    promtool check rules monitoring/prometheus_rules.yml
"""

from pathlib import Path
from typing import ClassVar

import pytest
import yaml

# Path to the monitoring directory (relative to project root)
MONITORING_DIR = Path(__file__).parent.parent.parent.parent.parent / "monitoring"
PROMETHEUS_RULES_PATH = MONITORING_DIR / "prometheus_rules.yml"
PROMETHEUS_CONFIG_PATH = MONITORING_DIR / "prometheus.yml"


@pytest.fixture
def rules_content() -> str:
    """Load the Prometheus rules file content."""
    if not PROMETHEUS_RULES_PATH.exists():
        pytest.skip(f"Rules file not found: {PROMETHEUS_RULES_PATH}")
    return PROMETHEUS_RULES_PATH.read_text()


@pytest.fixture
def rules_data(rules_content: str) -> dict:
    """Parse the Prometheus rules file as YAML."""
    return yaml.safe_load(rules_content)


@pytest.fixture
def prometheus_config() -> dict:
    """Load the main Prometheus configuration."""
    if not PROMETHEUS_CONFIG_PATH.exists():
        pytest.skip(f"Prometheus config not found: {PROMETHEUS_CONFIG_PATH}")
    return yaml.safe_load(PROMETHEUS_CONFIG_PATH.read_text())


class TestPrometheusRulesYAMLSyntax:
    """Test YAML syntax validity of Prometheus rules file."""

    def test_rules_file_exists(self):
        """Verify the rules file exists in the monitoring directory."""
        assert PROMETHEUS_RULES_PATH.exists(), (
            f"Prometheus rules file not found at {PROMETHEUS_RULES_PATH}"
        )

    def test_rules_file_is_valid_yaml(self, rules_content: str):
        """Verify the rules file is valid YAML syntax."""
        try:
            yaml.safe_load(rules_content)
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML syntax in rules file: {e}")

    def test_rules_file_is_not_empty(self, rules_data: dict):
        """Verify the rules file is not empty."""
        assert rules_data is not None, "Rules file is empty"
        assert isinstance(rules_data, dict), "Rules file root must be a dictionary"


class TestPrometheusRulesStructure:
    """Test the structure of Prometheus alerting rules."""

    def test_groups_key_exists(self, rules_data: dict):
        """Verify 'groups' key exists at the root level."""
        assert "groups" in rules_data, "Rules file must have 'groups' key"
        assert isinstance(rules_data["groups"], list), "'groups' must be a list"

    def test_each_group_has_name_and_rules(self, rules_data: dict):
        """Verify each group has a name and rules list."""
        for i, group in enumerate(rules_data["groups"]):
            assert "name" in group, f"Group {i} is missing 'name'"
            assert "rules" in group, f"Group {group.get('name', i)} is missing 'rules'"
            assert isinstance(group["rules"], list), f"Group {group['name']} 'rules' must be a list"

    def test_each_group_has_unique_name(self, rules_data: dict):
        """Verify each group has a unique name."""
        names = [group["name"] for group in rules_data["groups"]]
        assert len(names) == len(set(names)), "Group names must be unique"

    def test_group_interval_is_valid_duration(self, rules_data: dict):
        """Verify group intervals are valid Prometheus duration strings."""
        valid_duration_pattern = r"^\d+[smhd]$"
        import re

        for group in rules_data["groups"]:
            if "interval" in group:
                assert re.match(valid_duration_pattern, group["interval"]), (
                    f"Invalid interval '{group['interval']}' in group {group['name']}"
                )


class TestAlertingRulesRequired:
    """Test required fields for alerting rules."""

    REQUIRED_ALERT_FIELDS: ClassVar[list[str]] = ["alert", "expr", "labels", "annotations"]
    REQUIRED_LABELS: ClassVar[list[str]] = ["severity"]
    REQUIRED_ANNOTATIONS: ClassVar[list[str]] = ["summary", "description"]

    def get_all_alerts(self, rules_data: dict) -> list[tuple[str, dict]]:
        """Extract all alert rules from the rules data."""
        alerts = []
        for group in rules_data["groups"]:
            for rule in group.get("rules", []):
                if "alert" in rule:
                    alerts.append((group["name"], rule))
        return alerts

    def test_at_least_one_alert_exists(self, rules_data: dict):
        """Verify at least one alerting rule exists."""
        alerts = self.get_all_alerts(rules_data)
        assert len(alerts) > 0, "No alerting rules found"

    def test_alerts_have_required_fields(self, rules_data: dict):
        """Verify each alert has all required fields."""
        alerts = self.get_all_alerts(rules_data)
        for group_name, alert in alerts:
            alert_name = alert.get("alert", "unknown")
            for field in self.REQUIRED_ALERT_FIELDS:
                assert field in alert, (
                    f"Alert '{alert_name}' in group '{group_name}' "
                    f"is missing required field '{field}'"
                )

    def test_alerts_have_severity_label(self, rules_data: dict):
        """Verify each alert has a severity label."""
        alerts = self.get_all_alerts(rules_data)
        for group_name, alert in alerts:
            alert_name = alert["alert"]
            labels = alert.get("labels", {})
            for label in self.REQUIRED_LABELS:
                assert label in labels, (
                    f"Alert '{alert_name}' in group '{group_name}' "
                    f"is missing required label '{label}'"
                )

    def test_alerts_have_summary_and_description(self, rules_data: dict):
        """Verify each alert has summary and description annotations."""
        alerts = self.get_all_alerts(rules_data)
        for group_name, alert in alerts:
            alert_name = alert["alert"]
            annotations = alert.get("annotations", {})
            for annotation in self.REQUIRED_ANNOTATIONS:
                assert annotation in annotations, (
                    f"Alert '{alert_name}' in group '{group_name}' "
                    f"is missing required annotation '{annotation}'"
                )

    def test_alerts_have_unique_names_within_group(self, rules_data: dict):
        """Verify alert names are unique within each group."""
        for group in rules_data["groups"]:
            alert_names = [rule["alert"] for rule in group.get("rules", []) if "alert" in rule]
            assert len(alert_names) == len(set(alert_names)), (
                f"Duplicate alert names found in group '{group['name']}'"
            )


class TestAlertingSeverityLevels:
    """Test severity levels in alerting rules."""

    VALID_SEVERITIES: ClassVar[list[str]] = ["critical", "warning", "info"]

    def get_all_alerts(self, rules_data: dict) -> list[tuple[str, dict]]:
        """Extract all alert rules from the rules data."""
        alerts = []
        for group in rules_data["groups"]:
            for rule in group.get("rules", []):
                if "alert" in rule:
                    alerts.append((group["name"], rule))
        return alerts

    def test_severity_is_valid(self, rules_data: dict):
        """Verify all severity labels use valid values."""
        alerts = self.get_all_alerts(rules_data)
        for group_name, alert in alerts:
            alert_name = alert["alert"]
            severity = alert.get("labels", {}).get("severity")
            assert severity in self.VALID_SEVERITIES, (
                f"Alert '{alert_name}' has invalid severity '{severity}'. "
                f"Valid values: {self.VALID_SEVERITIES}"
            )

    def test_critical_alerts_exist(self, rules_data: dict):
        """Verify at least one critical severity alert exists."""
        alerts = self.get_all_alerts(rules_data)
        critical_alerts = [
            alert["alert"]
            for _, alert in alerts
            if alert.get("labels", {}).get("severity") == "critical"
        ]
        assert len(critical_alerts) > 0, "No critical severity alerts found"

    def test_warning_alerts_exist(self, rules_data: dict):
        """Verify at least one warning severity alert exists."""
        alerts = self.get_all_alerts(rules_data)
        warning_alerts = [
            alert["alert"]
            for _, alert in alerts
            if alert.get("labels", {}).get("severity") == "warning"
        ]
        assert len(warning_alerts) > 0, "No warning severity alerts found"


class TestAlertingRulesForDuration:
    """Test 'for' duration field in alerting rules."""

    def get_all_alerts(self, rules_data: dict) -> list[tuple[str, dict]]:
        """Extract all alert rules from the rules data."""
        alerts = []
        for group in rules_data["groups"]:
            for rule in group.get("rules", []):
                if "alert" in rule:
                    alerts.append((group["name"], rule))
        return alerts

    def test_for_duration_format_is_valid(self, rules_data: dict):
        """Verify 'for' duration uses valid Prometheus format."""
        import re

        valid_duration_pattern = r"^\d+[smhd]$"
        alerts = self.get_all_alerts(rules_data)
        for group_name, alert in alerts:
            alert_name = alert["alert"]
            if "for" in alert:
                duration = alert["for"]
                assert re.match(valid_duration_pattern, duration), (
                    f"Alert '{alert_name}' has invalid 'for' duration '{duration}'. "
                    f"Expected format: <number>[s|m|h|d]"
                )

    def test_critical_alerts_have_short_for_duration(self, rules_data: dict):
        """Verify critical alerts don't have excessively long 'for' durations."""
        alerts = self.get_all_alerts(rules_data)
        for group_name, alert in alerts:
            if alert.get("labels", {}).get("severity") == "critical":
                alert_name = alert["alert"]
                if "for" in alert:
                    duration_str = alert["for"]
                    # Parse duration to minutes
                    minutes = self._duration_to_minutes(duration_str)
                    assert minutes <= 5, (
                        f"Critical alert '{alert_name}' has 'for' duration "
                        f"of {duration_str} ({minutes}m). Critical alerts "
                        "should fire within 5 minutes."
                    )

    def _duration_to_minutes(self, duration: str) -> float:
        """Convert Prometheus duration string to minutes."""
        import re

        match = re.match(r"^(\d+)([smhd])$", duration)
        if not match:
            return 0
        value = int(match.group(1))
        unit = match.group(2)
        multipliers = {"s": 1 / 60, "m": 1, "h": 60, "d": 1440}
        return value * multipliers.get(unit, 0)


class TestAlertingRulesExpressions:
    """Test PromQL expressions in alerting rules."""

    # Known HSI metrics (from metrics.py and json-exporter-config.yml)
    KNOWN_METRICS: ClassVar[list[str]] = [
        # From json-exporter-config.yml
        "hsi_system_healthy",
        "hsi_database_healthy",
        "hsi_redis_healthy",
        "hsi_ai_healthy",
        "hsi_detection_queue_depth",
        "hsi_analysis_queue_depth",
        "hsi_gpu_utilization",
        "hsi_gpu_memory_used_mb",
        "hsi_gpu_memory_total_mb",
        "hsi_gpu_temperature",
        "hsi_inference_fps",
        # From metrics.py
        "hsi_ai_request_duration_seconds",
        "hsi_pipeline_errors_total",
        "hsi_detections_processed_total",
        "hsi_events_created_total",
        "hsi_stage_duration_seconds",
        # DLQ monitoring (NEM-3891)
        "hsi_dlq_depth",
        # Process memory monitoring (NEM-3890)
        "hsi_process_memory_rss_bytes",
        "hsi_process_memory_container_limit_bytes",
        "hsi_process_memory_container_usage_ratio",
        # Prometheus built-in
        "up",
        # Blackbox exporter metrics
        "probe_success",
    ]

    def get_all_alerts(self, rules_data: dict) -> list[tuple[str, dict]]:
        """Extract all alert rules from the rules data."""
        alerts = []
        for group in rules_data["groups"]:
            for rule in group.get("rules", []):
                if "alert" in rule:
                    alerts.append((group["name"], rule))
        return alerts

    def test_expressions_are_not_empty(self, rules_data: dict):
        """Verify all expression fields are non-empty."""
        alerts = self.get_all_alerts(rules_data)
        for group_name, alert in alerts:
            alert_name = alert["alert"]
            expr = alert.get("expr", "")
            assert expr.strip(), f"Alert '{alert_name}' has empty expression"

    def test_expressions_reference_known_metrics(self, rules_data: dict):
        """Verify expressions reference at least one known metric."""

        alerts = self.get_all_alerts(rules_data)
        for group_name, alert in alerts:
            alert_name = alert["alert"]
            expr = alert.get("expr", "")
            # Check if any known metric is in the expression
            found = any(metric in expr for metric in self.KNOWN_METRICS)
            assert found, (
                f"Alert '{alert_name}' expression doesn't reference any "
                f"known HSI metrics. Expression: {expr}"
            )


class TestPrometheusConfigIncludesRules:
    """Test that prometheus.yml includes the rules file."""

    def test_prometheus_config_has_rule_files(self, prometheus_config: dict):
        """Verify prometheus.yml has rule_files section."""
        assert "rule_files" in prometheus_config, "prometheus.yml must have 'rule_files' section"
        assert isinstance(prometheus_config["rule_files"], list), "'rule_files' must be a list"

    def test_prometheus_config_includes_alerting_rules(self, prometheus_config: dict):
        """Verify prometheus.yml includes prometheus_rules.yml."""
        rule_files = prometheus_config.get("rule_files", [])
        assert "prometheus_rules.yml" in rule_files, (
            "prometheus.yml must include 'prometheus_rules.yml' in rule_files"
        )


class TestExpectedAlerts:
    """Test that expected alerts are defined as per NEM-1731."""

    # NOTE: AINemotronTimeout removed - depends on unimplemented hsi_ai_request_duration_seconds metric
    EXPECTED_ALERTS: ClassVar[list[str]] = [
        "AIDetectorUnavailable",
        "AIHighErrorRate",
        "AIGPUOverheating",
        "AIGPUMemoryCritical",
    ]

    def get_all_alert_names(self, rules_data: dict) -> list[str]:
        """Extract all alert names from the rules data."""
        names = []
        for group in rules_data["groups"]:
            for rule in group.get("rules", []):
                if "alert" in rule:
                    names.append(rule["alert"])
        return names

    def test_required_alerts_are_defined(self, rules_data: dict):
        """Verify all required alerts from NEM-1731 are defined."""
        alert_names = self.get_all_alert_names(rules_data)
        for expected in self.EXPECTED_ALERTS:
            assert expected in alert_names, f"Required alert '{expected}' is not defined (NEM-1731)"

    def test_aidetectorunavailable_is_critical(self, rules_data: dict):
        """Verify AIDetectorUnavailable has critical severity."""
        for group in rules_data["groups"]:
            for rule in group.get("rules", []):
                if rule.get("alert") == "AIDetectorUnavailable":
                    severity = rule.get("labels", {}).get("severity")
                    assert severity == "critical", (
                        "AIDetectorUnavailable must have critical severity"
                    )
                    return
        pytest.fail("AIDetectorUnavailable alert not found")

    def test_aigpuoverheating_is_critical(self, rules_data: dict):
        """Verify AIGPUOverheating has critical severity."""
        for group in rules_data["groups"]:
            for rule in group.get("rules", []):
                if rule.get("alert") == "AIGPUOverheating":
                    severity = rule.get("labels", {}).get("severity")
                    assert severity == "critical", "AIGPUOverheating must have critical severity"
                    return
        pytest.fail("AIGPUOverheating alert not found")

    def test_aigpumemorycritical_is_critical(self, rules_data: dict):
        """Verify AIGPUMemoryCritical has critical severity."""
        for group in rules_data["groups"]:
            for rule in group.get("rules", []):
                if rule.get("alert") == "AIGPUMemoryCritical":
                    severity = rule.get("labels", {}).get("severity")
                    assert severity == "critical", "AIGPUMemoryCritical must have critical severity"
                    return
        pytest.fail("AIGPUMemoryCritical alert not found")

    # NOTE: test_ainemotrontimeout_has_for_duration removed - alert disabled (depends on unimplemented metric)

    def test_aihigherrorrate_expression_checks_rate(self, rules_data: dict):
        """Verify AIHighErrorRate uses rate() function in expression."""
        for group in rules_data["groups"]:
            for rule in group.get("rules", []):
                if rule.get("alert") == "AIHighErrorRate":
                    expr = rule.get("expr", "")
                    assert "rate(" in expr, (
                        "AIHighErrorRate must use rate() function for error rate calculation"
                    )
                    return
        pytest.fail("AIHighErrorRate alert not found")
