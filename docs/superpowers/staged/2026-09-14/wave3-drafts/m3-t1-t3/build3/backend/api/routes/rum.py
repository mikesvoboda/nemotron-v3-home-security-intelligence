"""Real User Monitoring (RUM) API routes for Core Web Vitals tracking.

This module provides the endpoint for receiving Core Web Vitals metrics
from the frontend. Metrics are recorded to Prometheus histograms for
analysis and alerting.

Core Web Vitals collected:
- LCP (Largest Contentful Paint): Loading performance
- FID (First Input Delay): Interactivity (legacy)
- INP (Interaction to Next Paint): Interactivity (new standard)
- CLS (Cumulative Layout Shift): Visual stability
- TTFB (Time to First Byte): Server response time
- FCP (First Contentful Paint): First content render
- PAGE_LOAD_TIME: Full page load duration from Navigation Timing API

Usage:
    POST /api/rum
    {
        "metrics": [
            {
                "name": "LCP",
                "value": 2500.0,
                "rating": "good",
                "delta": 2500.0,
                "id": "v1-1234567890123-1234567890123",
                "path": "/dashboard"
            }
        ],
        "session_id": "optional-session-id"
    }
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.schemas.rum import RUMBatchRequest, RUMIngestResponse, WebVitalName
from backend.core.logging import get_logger
from backend.core.metrics import (
    observe_rum_cls,
    observe_rum_fcp,
    observe_rum_fid,
    observe_rum_inp,
    observe_rum_lcp,
    observe_rum_page_load_time,
    observe_rum_ttfb,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/rum", tags=["rum"])


@router.post(
    "",
    response_model=RUMIngestResponse,
    summary="Ingest RUM metrics",
    description="Receive Core Web Vitals metrics from the frontend for Real User Monitoring.",
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def ingest_rum_metrics(request: RUMBatchRequest) -> RUMIngestResponse:
    """Ingest Core Web Vitals metrics from the frontend.

    Records each metric to the appropriate Prometheus histogram based on
    the metric name. Metrics are tagged with the page path and rating
    for breakdown analysis.

    Args:
        request: Batch of Core Web Vitals metrics to ingest

    Returns:
        RUMIngestResponse with ingestion status and count
    """
    errors: list[str] = []
    processed_count = 0

    for metric in request.metrics:
        try:
            path = metric.path or "/"
            rating = metric.rating

            # Record to appropriate Prometheus histogram based on metric name
            if metric.name == WebVitalName.LCP:
                observe_rum_lcp(metric.value, path=path, rating=rating)
            elif metric.name == WebVitalName.FID:
                observe_rum_fid(metric.value, path=path, rating=rating)
            elif metric.name == WebVitalName.INP:
                observe_rum_inp(metric.value, path=path, rating=rating)
            elif metric.name == WebVitalName.CLS:
                observe_rum_cls(metric.value, path=path, rating=rating)
            elif metric.name == WebVitalName.TTFB:
                observe_rum_ttfb(metric.value, path=path, rating=rating)
            elif metric.name == WebVitalName.FCP:
                observe_rum_fcp(metric.value, path=path, rating=rating)
            elif metric.name == WebVitalName.PAGE_LOAD_TIME:
                observe_rum_page_load_time(metric.value, path=path, rating=rating)
            else:
                errors.append(f"Unknown metric name: {metric.name}")
                continue

            processed_count += 1

        except Exception as e:
            error_msg = f"Error processing metric {metric.name}: {e!s}"
            logger.warning(error_msg)
            errors.append(error_msg)

    # Log summary if we have a session ID
    if request.session_id:
        logger.debug(
            f"RUM metrics ingested for session {request.session_id}: "
            f"{processed_count} processed, {len(errors)} errors"
        )

    return RUMIngestResponse(
        success=processed_count > 0 or len(errors) == 0,
        metrics_count=processed_count,
        message=f"Successfully ingested {processed_count} metric(s)"
        if processed_count > 0
        else "No metrics processed",
        errors=errors,
    )
