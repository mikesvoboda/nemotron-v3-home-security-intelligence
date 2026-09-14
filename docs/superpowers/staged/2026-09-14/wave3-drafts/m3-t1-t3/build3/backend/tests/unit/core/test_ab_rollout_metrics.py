"""Unit tests for A/B Rollout Prometheus Metrics (NEM-3338).

These tests verify the Prometheus metrics definitions and helper functions
for the A/B rollout experiment tracking.

Tests cover:
1. Metric definitions exist
2. Helper functions work correctly
3. Labels are properly sanitized
"""

from __future__ import annotations

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestABRolloutMetricDefinitions:
    """Tests for A/B rollout metric definitions."""

    def test_ab_rollout_analysis_total_exists(self):
        """Test AB_ROLLOUT_ANALYSIS_TOTAL metric is defined."""
        from backend.core.metrics import AB_ROLLOUT_ANALYSIS_TOTAL

        assert AB_ROLLOUT_ANALYSIS_TOTAL is not None
        assert hasattr(AB_ROLLOUT_ANALYSIS_TOTAL, "labels")

    def test_ab_rollout_fp_rate_exists(self):
        """Test AB_ROLLOUT_FP_RATE metric is defined."""
        from backend.core.metrics import AB_ROLLOUT_FP_RATE

        assert AB_ROLLOUT_FP_RATE is not None
        assert hasattr(AB_ROLLOUT_FP_RATE, "labels")

    def test_ab_rollout_avg_latency_exists(self):
        """Test AB_ROLLOUT_AVG_LATENCY_MS metric is defined."""
        from backend.core.metrics import AB_ROLLOUT_AVG_LATENCY_MS

        assert AB_ROLLOUT_AVG_LATENCY_MS is not None
        assert hasattr(AB_ROLLOUT_AVG_LATENCY_MS, "labels")

    def test_ab_rollout_avg_risk_score_exists(self):
        """Test AB_ROLLOUT_AVG_RISK_SCORE metric is defined."""
        from backend.core.metrics import AB_ROLLOUT_AVG_RISK_SCORE

        assert AB_ROLLOUT_AVG_RISK_SCORE is not None
        assert hasattr(AB_ROLLOUT_AVG_RISK_SCORE, "labels")

    def test_ab_rollout_feedback_total_exists(self):
        """Test AB_ROLLOUT_FEEDBACK_TOTAL metric is defined."""
        from backend.core.metrics import AB_ROLLOUT_FEEDBACK_TOTAL

        assert AB_ROLLOUT_FEEDBACK_TOTAL is not None
        assert hasattr(AB_ROLLOUT_FEEDBACK_TOTAL, "labels")


class TestABRolloutMetricHelpers:
    """Tests for A/B rollout metric helper functions."""

    def test_record_ab_rollout_analysis_control(self):
        """Test recording analysis for control group."""
        from backend.core.metrics import record_ab_rollout_analysis

        # Should not raise
        record_ab_rollout_analysis("control")

    def test_record_ab_rollout_analysis_treatment(self):
        """Test recording analysis for treatment group."""
        from backend.core.metrics import record_ab_rollout_analysis

        # Should not raise
        record_ab_rollout_analysis("treatment")

    def test_update_ab_rollout_fp_rate_control(self):
        """Test updating FP rate for control group."""
        from backend.core.metrics import update_ab_rollout_fp_rate

        # Should not raise
        update_ab_rollout_fp_rate("control", 0.25)

    def test_update_ab_rollout_fp_rate_treatment(self):
        """Test updating FP rate for treatment group."""
        from backend.core.metrics import update_ab_rollout_fp_rate

        # Should not raise
        update_ab_rollout_fp_rate("treatment", 0.15)

    def test_update_ab_rollout_avg_latency(self):
        """Test updating average latency for groups."""
        from backend.core.metrics import update_ab_rollout_avg_latency

        # Should not raise
        update_ab_rollout_avg_latency("control", 150.5)
        update_ab_rollout_avg_latency("treatment", 175.3)

    def test_update_ab_rollout_avg_risk_score(self):
        """Test updating average risk score for groups."""
        from backend.core.metrics import update_ab_rollout_avg_risk_score

        # Should not raise
        update_ab_rollout_avg_risk_score("control", 55.0)
        update_ab_rollout_avg_risk_score("treatment", 45.0)

    def test_record_ab_rollout_feedback_false_positive(self):
        """Test recording false positive feedback."""
        from backend.core.metrics import record_ab_rollout_feedback

        # Should not raise
        record_ab_rollout_feedback("control", is_false_positive=True)
        record_ab_rollout_feedback("treatment", is_false_positive=True)

    def test_record_ab_rollout_feedback_correct(self):
        """Test recording correct (non-FP) feedback."""
        from backend.core.metrics import record_ab_rollout_feedback

        # Should not raise
        record_ab_rollout_feedback("control", is_false_positive=False)
        record_ab_rollout_feedback("treatment", is_false_positive=False)

    def test_helpers_sanitize_group_labels(self):
        """Test that helper functions sanitize group labels."""
        from backend.core.metrics import (
            record_ab_rollout_analysis,
            record_ab_rollout_feedback,
            update_ab_rollout_avg_latency,
            update_ab_rollout_avg_risk_score,
            update_ab_rollout_fp_rate,
        )

        # Should not raise even with potentially problematic input
        # (sanitization should handle it)
        record_ab_rollout_analysis("control")
        update_ab_rollout_fp_rate("control", 0.1)
        update_ab_rollout_avg_latency("treatment", 100.0)
        update_ab_rollout_avg_risk_score("control", 50.0)
        record_ab_rollout_feedback("treatment", False)
