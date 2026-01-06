"""Prometheus metrics endpoint for observability.

This module exposes the /api/metrics endpoint for Prometheus scraping.
The endpoint returns all registered metrics in Prometheus exposition format.

The endpoint does not require authentication to allow Prometheus to
scrape metrics without additional configuration.

Usage with Prometheus:
    scrape_configs:
      - job_name: 'home-security-intelligence'
        static_configs:
          - targets: ['localhost:8000']
        metrics_path: '/api/metrics'
"""

from fastapi import APIRouter
from fastapi.responses import Response

from backend.core.metrics import get_metrics_response

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics")
async def metrics() -> Response:
    """Return Prometheus metrics in exposition format.

    This endpoint returns all registered metrics in the standard
    Prometheus exposition format for scraping.

    Returns:
        Response with text/plain content type containing metrics
    """
    metrics_data = get_metrics_response()
    return Response(
        content=metrics_data,
        media_type="text/plain; charset=utf-8",
    )
