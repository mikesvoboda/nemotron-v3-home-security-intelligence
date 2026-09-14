"""Unit tests for RUM (Real User Monitoring) schemas.

Tests for the Pydantic schemas used to validate Core Web Vitals
metrics sent from the frontend for Real User Monitoring.

RED Phase: These tests define the expected behavior for RUM schemas.
"""

import pytest
from pydantic import ValidationError

# Import will fail until we implement the schemas (RED phase)
from api.schemas.rum import (
    RUMBatchRequest,
    RUMIngestResponse,
    WebVitalMetric,
    WebVitalName,
)


class TestWebVitalName:
    """Tests for WebVitalName enum."""

    def test_lcp_value(self):
        """Test LCP (Largest Contentful Paint) enum value."""
        assert WebVitalName.LCP.value == "LCP"

    def test_fid_value(self):
        """Test FID (First Input Delay) enum value."""
        assert WebVitalName.FID.value == "FID"

    def test_inp_value(self):
        """Test INP (Interaction to Next Paint) enum value."""
        assert WebVitalName.INP.value == "INP"

    def test_cls_value(self):
        """Test CLS (Cumulative Layout Shift) enum value."""
        assert WebVitalName.CLS.value == "CLS"

    def test_ttfb_value(self):
        """Test TTFB (Time to First Byte) enum value."""
        assert WebVitalName.TTFB.value == "TTFB"

    def test_fcp_value(self):
        """Test FCP (First Contentful Paint) enum value."""
        assert WebVitalName.FCP.value == "FCP"

    def test_page_load_time_value(self):
        """Test PAGE_LOAD_TIME (full page load duration) enum value."""
        assert WebVitalName.PAGE_LOAD_TIME.value == "PAGE_LOAD_TIME"


class TestWebVitalMetric:
    """Tests for WebVitalMetric schema."""

    def test_valid_lcp_metric(self):
        """Test creating a valid LCP metric."""
        metric = WebVitalMetric(
            name=WebVitalName.LCP,
            value=2500.0,
            rating="good",
            delta=2500.0,
            id="v1-1234567890123-1234567890123",
            navigationType="navigate",
        )
        assert metric.name == WebVitalName.LCP
        assert metric.value == 2500.0
        assert metric.rating == "good"
        assert metric.delta == 2500.0

    def test_valid_cls_metric(self):
        """Test creating a valid CLS metric (dimensionless value)."""
        metric = WebVitalMetric(
            name=WebVitalName.CLS,
            value=0.05,
            rating="good",
            delta=0.02,
            id="v1-1234567890123-1234567890123",
        )
        assert metric.name == WebVitalName.CLS
        assert metric.value == 0.05
        assert metric.rating == "good"

    def test_valid_inp_metric(self):
        """Test creating a valid INP metric."""
        metric = WebVitalMetric(
            name=WebVitalName.INP,
            value=200.0,
            rating="needs-improvement",
            delta=200.0,
            id="v1-1234567890123-1234567890123",
        )
        assert metric.name == WebVitalName.INP
        assert metric.rating == "needs-improvement"

    def test_valid_ttfb_metric(self):
        """Test creating a valid TTFB metric."""
        metric = WebVitalMetric(
            name=WebVitalName.TTFB,
            value=100.0,
            rating="good",
            delta=100.0,
            id="v1-1234567890123-1234567890123",
        )
        assert metric.name == WebVitalName.TTFB
        assert metric.value == 100.0

    def test_valid_fcp_metric(self):
        """Test creating a valid FCP metric."""
        metric = WebVitalMetric(
            name=WebVitalName.FCP,
            value=1800.0,
            rating="good",
            delta=1800.0,
            id="v1-1234567890123-1234567890123",
        )
        assert metric.name == WebVitalName.FCP
        assert metric.value == 1800.0

    def test_valid_fid_metric(self):
        """Test creating a valid FID metric (legacy)."""
        metric = WebVitalMetric(
            name=WebVitalName.FID,
            value=50.0,
            rating="good",
            delta=50.0,
            id="v1-1234567890123-1234567890123",
        )
        assert metric.name == WebVitalName.FID
        assert metric.value == 50.0

    def test_valid_page_load_time_metric(self):
        """Test creating a valid PAGE_LOAD_TIME metric."""
        metric = WebVitalMetric(
            name=WebVitalName.PAGE_LOAD_TIME,
            value=2500.0,
            rating="good",
            delta=2500.0,
            id="plt-1234567890123-abc1234",
        )
        assert metric.name == WebVitalName.PAGE_LOAD_TIME
        assert metric.value == 2500.0

    def test_rating_poor(self):
        """Test metric with poor rating."""
        metric = WebVitalMetric(
            name=WebVitalName.LCP,
            value=4500.0,
            rating="poor",
            delta=4500.0,
            id="v1-1234567890123-1234567890123",
        )
        assert metric.rating == "poor"

    def test_optional_navigation_type(self):
        """Test that navigationType is optional."""
        metric = WebVitalMetric(
            name=WebVitalName.LCP,
            value=2500.0,
            rating="good",
            delta=2500.0,
            id="v1-1234567890123-1234567890123",
        )
        assert metric.navigationType is None

    def test_optional_path(self):
        """Test that path is optional with default."""
        metric = WebVitalMetric(
            name=WebVitalName.LCP,
            value=2500.0,
            rating="good",
            delta=2500.0,
            id="v1-1234567890123-1234567890123",
        )
        # Path should have a default or be optional
        assert metric.path is None or isinstance(metric.path, str)

    def test_with_path(self):
        """Test metric with explicit path."""
        metric = WebVitalMetric(
            name=WebVitalName.LCP,
            value=2500.0,
            rating="good",
            delta=2500.0,
            id="v1-1234567890123-1234567890123",
            path="/dashboard",
        )
        assert metric.path == "/dashboard"

    def test_with_navigation_type(self):
        """Test metric with navigationType."""
        metric = WebVitalMetric(
            name=WebVitalName.LCP,
            value=2500.0,
            rating="good",
            delta=2500.0,
            id="v1-1234567890123-1234567890123",
            navigationType="reload",
        )
        assert metric.navigationType == "reload"

    def test_invalid_rating_rejected(self):
        """Test that invalid rating values are rejected."""
        with pytest.raises(ValidationError):
            WebVitalMetric(
                name=WebVitalName.LCP,
                value=2500.0,
                rating="invalid_rating",
                delta=2500.0,
                id="v1-1234567890123-1234567890123",
            )

    def test_negative_value_allowed(self):
        """Test that negative delta values are allowed (for CLS improvements)."""
        metric = WebVitalMetric(
            name=WebVitalName.CLS,
            value=0.05,
            rating="good",
            delta=-0.02,
            id="v1-1234567890123-1234567890123",
        )
        assert metric.delta == -0.02

    def test_missing_required_field(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            WebVitalMetric(
                name=WebVitalName.LCP,
                # Missing value, rating, delta, id
            )


class TestRUMBatchRequest:
    """Tests for RUMBatchRequest schema."""

    def test_valid_batch_with_single_metric(self):
        """Test batch request with a single metric."""
        batch = RUMBatchRequest(
            metrics=[
                WebVitalMetric(
                    name=WebVitalName.LCP,
                    value=2500.0,
                    rating="good",
                    delta=2500.0,
                    id="v1-1234567890123-1234567890123",
                )
            ]
        )
        assert len(batch.metrics) == 1
        assert batch.metrics[0].name == WebVitalName.LCP

    def test_valid_batch_with_multiple_metrics(self):
        """Test batch request with multiple metrics."""
        batch = RUMBatchRequest(
            metrics=[
                WebVitalMetric(
                    name=WebVitalName.LCP,
                    value=2500.0,
                    rating="good",
                    delta=2500.0,
                    id="v1-1234567890123-1234567890123",
                ),
                WebVitalMetric(
                    name=WebVitalName.CLS,
                    value=0.05,
                    rating="good",
                    delta=0.02,
                    id="v1-1234567890123-1234567890124",
                ),
                WebVitalMetric(
                    name=WebVitalName.INP,
                    value=200.0,
                    rating="needs-improvement",
                    delta=200.0,
                    id="v1-1234567890123-1234567890125",
                ),
            ]
        )
        assert len(batch.metrics) == 3
        assert batch.metrics[0].name == WebVitalName.LCP
        assert batch.metrics[1].name == WebVitalName.CLS
        assert batch.metrics[2].name == WebVitalName.INP

    def test_empty_batch_rejected(self):
        """Test that empty batch is rejected."""
        with pytest.raises(ValidationError):
            RUMBatchRequest(metrics=[])

    def test_batch_with_optional_session_id(self):
        """Test batch with optional session ID."""
        batch = RUMBatchRequest(
            metrics=[
                WebVitalMetric(
                    name=WebVitalName.LCP,
                    value=2500.0,
                    rating="good",
                    delta=2500.0,
                    id="v1-1234567890123-1234567890123",
                )
            ],
            session_id="sess-12345",
        )
        assert batch.session_id == "sess-12345"

    def test_batch_without_session_id(self):
        """Test batch without session ID defaults to None."""
        batch = RUMBatchRequest(
            metrics=[
                WebVitalMetric(
                    name=WebVitalName.LCP,
                    value=2500.0,
                    rating="good",
                    delta=2500.0,
                    id="v1-1234567890123-1234567890123",
                )
            ]
        )
        assert batch.session_id is None

    def test_batch_with_user_agent(self):
        """Test batch with user agent string."""
        batch = RUMBatchRequest(
            metrics=[
                WebVitalMetric(
                    name=WebVitalName.LCP,
                    value=2500.0,
                    rating="good",
                    delta=2500.0,
                    id="v1-1234567890123-1234567890123",
                )
            ],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        )
        assert batch.user_agent == "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"


class TestRUMIngestResponse:
    """Tests for RUMIngestResponse schema."""

    def test_success_response(self):
        """Test successful ingest response."""
        response = RUMIngestResponse(
            success=True,
            metrics_count=5,
            message="Successfully ingested 5 metrics",
        )
        assert response.success is True
        assert response.metrics_count == 5
        assert "5 metrics" in response.message

    def test_partial_success_response(self):
        """Test partial success ingest response."""
        response = RUMIngestResponse(
            success=True,
            metrics_count=3,
            message="Successfully ingested 3 of 5 metrics",
            errors=["Invalid metric: unknown name"],
        )
        assert response.success is True
        assert response.metrics_count == 3
        assert len(response.errors) == 1

    def test_failure_response(self):
        """Test failed ingest response."""
        response = RUMIngestResponse(
            success=False,
            metrics_count=0,
            message="Failed to ingest metrics",
            errors=["Validation error"],
        )
        assert response.success is False
        assert response.metrics_count == 0

    def test_response_without_errors(self):
        """Test response without errors defaults to empty list."""
        response = RUMIngestResponse(
            success=True,
            metrics_count=5,
            message="Success",
        )
        assert response.errors == []


class TestSchemaJsonExamples:
    """Tests for JSON schema examples and serialization."""

    def test_web_vital_metric_json_schema_example(self):
        """Test that WebVitalMetric has valid JSON schema example."""
        # Create from example data similar to what frontend would send
        example_data = {
            "name": "LCP",
            "value": 2500.0,
            "rating": "good",
            "delta": 2500.0,
            "id": "v1-1234567890123-1234567890123",
            "navigationType": "navigate",
            "path": "/dashboard",
        }
        metric = WebVitalMetric(**example_data)
        assert metric.name == WebVitalName.LCP
        assert metric.value == 2500.0

    def test_batch_request_json_serialization(self):
        """Test batch request serializes to JSON correctly."""
        batch = RUMBatchRequest(
            metrics=[
                WebVitalMetric(
                    name=WebVitalName.LCP,
                    value=2500.0,
                    rating="good",
                    delta=2500.0,
                    id="v1-1234567890123-1234567890123",
                )
            ],
            session_id="test-session",
        )
        json_data = batch.model_dump()
        assert json_data["metrics"][0]["name"] == "LCP"
        assert json_data["session_id"] == "test-session"

    def test_response_json_serialization(self):
        """Test response serializes to JSON correctly."""
        response = RUMIngestResponse(
            success=True,
            metrics_count=5,
            message="Success",
        )
        json_data = response.model_dump()
        assert json_data["success"] is True
        assert json_data["metrics_count"] == 5
