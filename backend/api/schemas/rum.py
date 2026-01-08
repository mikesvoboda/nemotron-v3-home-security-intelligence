"""Pydantic schemas for Real User Monitoring (RUM) - Core Web Vitals tracking.

This module defines schemas for the RUM data ingestion endpoint that receives
Core Web Vitals metrics from the frontend. These metrics are collected using
the web-vitals library and sent to the backend for storage and analysis.

Core Web Vitals metrics:
- LCP (Largest Contentful Paint): Loading performance
- FID (First Input Delay): Interactivity (legacy)
- INP (Interaction to Next Paint): Interactivity (new)
- CLS (Cumulative Layout Shift): Visual stability
- TTFB (Time to First Byte): Server response time
- FCP (First Contentful Paint): First content render
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WebVitalName(str, Enum):
    """Supported Core Web Vitals metric names.

    These correspond to the metrics collected by the web-vitals library.
    """

    LCP = "LCP"  # Largest Contentful Paint (milliseconds)
    FID = "FID"  # First Input Delay (milliseconds, legacy)
    INP = "INP"  # Interaction to Next Paint (milliseconds)
    CLS = "CLS"  # Cumulative Layout Shift (dimensionless)
    TTFB = "TTFB"  # Time to First Byte (milliseconds)
    FCP = "FCP"  # First Contentful Paint (milliseconds)


# Rating values used by web-vitals library
RatingType = Literal["good", "needs-improvement", "poor"]


class WebVitalMetric(BaseModel):
    """A single Core Web Vital metric measurement from the frontend.

    This schema matches the structure returned by the web-vitals library's
    onLCP, onFID, onINP, onCLS, onTTFB, and onFCP functions.

    Attributes:
        name: The Core Web Vital metric name (LCP, FID, INP, CLS, TTFB, FCP)
        value: The metric value (milliseconds for most, dimensionless for CLS)
        rating: Performance rating based on thresholds (good, needs-improvement, poor)
        delta: The delta since the last report (for CLS this accumulates)
        id: Unique identifier for this metric instance
        navigationType: The type of navigation (navigate, reload, back_forward, prerender)
        path: The page path where the metric was measured
    """

    name: WebVitalName = Field(..., description="Core Web Vital metric name")
    value: float = Field(..., description="Metric value (ms for most, dimensionless for CLS)")
    rating: RatingType = Field(..., description="Performance rating")
    delta: float = Field(..., description="Delta since last report")
    id: str = Field(..., description="Unique metric identifier from web-vitals")
    navigationType: str | None = Field(
        None, description="Navigation type (navigate, reload, back_forward, prerender)"
    )
    path: str | None = Field(None, description="Page path where metric was measured")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "LCP",
                "value": 2500.0,
                "rating": "good",
                "delta": 2500.0,
                "id": "v1-1234567890123-1234567890123",
                "navigationType": "navigate",
                "path": "/dashboard",
            }
        }
    )


class RUMBatchRequest(BaseModel):
    """Batch request for multiple Core Web Vitals metrics.

    The frontend batches metrics to reduce API calls. Each batch may contain
    metrics from different pages or navigation events.

    Attributes:
        metrics: List of Core Web Vital metrics to ingest
        session_id: Optional session identifier for correlating metrics
        user_agent: Optional user agent string for device/browser analysis
    """

    metrics: list[WebVitalMetric] = Field(
        ..., min_length=1, description="List of metrics to ingest (non-empty)"
    )
    session_id: str | None = Field(None, description="Optional session identifier")
    user_agent: str | None = Field(None, description="Optional user agent string")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metrics": [
                    {
                        "name": "LCP",
                        "value": 2500.0,
                        "rating": "good",
                        "delta": 2500.0,
                        "id": "v1-1234567890123-1234567890123",
                    },
                    {
                        "name": "CLS",
                        "value": 0.05,
                        "rating": "good",
                        "delta": 0.02,
                        "id": "v1-1234567890123-1234567890124",
                    },
                ],
                "session_id": "sess-12345",
            }
        }
    )


class RUMIngestResponse(BaseModel):
    """Response from the RUM metrics ingestion endpoint.

    Attributes:
        success: Whether the ingestion was successful
        metrics_count: Number of metrics successfully ingested
        message: Human-readable status message
        errors: List of any errors encountered during ingestion
    """

    success: bool = Field(..., description="Whether ingestion was successful")
    metrics_count: int = Field(..., ge=0, description="Number of metrics successfully ingested")
    message: str = Field(..., description="Human-readable status message")
    errors: list[str] = Field(default_factory=list, description="List of any errors encountered")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "metrics_count": 5,
                "message": "Successfully ingested 5 metrics",
                "errors": [],
            }
        }
    )
