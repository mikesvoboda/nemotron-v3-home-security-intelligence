"""Pydantic schemas for webhook endpoints.

This module defines schemas for receiving webhooks from external systems,
primarily Alertmanager (Prometheus alerting).

Alertmanager Webhook Format:
    https://prometheus.io/docs/alerting/latest/configuration/#webhook_config
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AlertmanagerStatus(StrEnum):
    """Alertmanager alert status values."""

    FIRING = "firing"
    RESOLVED = "resolved"


class WebhookAlert(BaseModel):
    """Schema for a single alert in webhook payload.

    Represents one alert instance with its labels, annotations, and timing.
    This is the legacy webhook schema - prefer AlertmanagerAlert from alertmanager.py.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "firing",
                "labels": {
                    "alertname": "HSIGPUMemoryHigh",
                    "severity": "warning",
                    "component": "gpu",
                },
                "annotations": {
                    "summary": "GPU memory usage is high",
                    "description": "GPU memory usage is above 90% for 5 minutes",
                },
                "startsAt": "2026-01-17T12:22:56.068Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://prometheus:9090/graph?...",
                "fingerprint": "abc123def456",  # pragma: allowlist secret
            }
        }
    )

    status: AlertmanagerStatus = Field(..., description="Alert status (firing or resolved)")
    labels: dict[str, str] = Field(
        default_factory=dict, description="Alert labels (alertname, severity, etc.)"
    )
    annotations: dict[str, str] = Field(
        default_factory=dict, description="Alert annotations (summary, description)"
    )
    startsAt: datetime = Field(..., description="When the alert started firing")
    endsAt: datetime | None = Field(None, description="When the alert was resolved")
    generatorURL: str | None = Field(None, description="URL to the Prometheus graph")
    fingerprint: str = Field(..., description="Unique identifier for deduplication")


class AlertmanagerWebhookPayload(BaseModel):
    """Schema for Alertmanager webhook payload.

    This is the format Alertmanager sends when configured with a webhook receiver.
    See: https://prometheus.io/docs/alerting/latest/configuration/#webhook_config
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": "4",
                "groupKey": '{}:{alertname="HSIGPUMemoryHigh"}',
                "truncatedAlerts": 0,
                "status": "firing",
                "receiver": "critical-receiver",
                "groupLabels": {"alertname": "HSIGPUMemoryHigh"},
                "commonLabels": {
                    "alertname": "HSIGPUMemoryHigh",
                    "severity": "warning",
                },
                "commonAnnotations": {"summary": "GPU memory usage is high"},
                "externalURL": "http://alertmanager:9093",
                "alerts": [
                    {
                        "status": "firing",
                        "labels": {"alertname": "HSIGPUMemoryHigh", "severity": "warning"},
                        "annotations": {"description": "GPU memory at 96%"},
                        "startsAt": "2026-01-17T12:22:56.068Z",
                        "endsAt": "0001-01-01T00:00:00Z",
                        "fingerprint": "abc123",
                    }
                ],
            }
        }
    )

    version: str = Field("4", description="Alertmanager webhook version")
    groupKey: str = Field(..., description="Key identifying the alert group")
    truncatedAlerts: int = Field(0, description="Number of truncated alerts")
    status: AlertmanagerStatus = Field(..., description="Overall group status")
    receiver: str = Field(..., description="Name of the receiver that matched")
    groupLabels: dict[str, str] = Field(
        default_factory=dict, description="Labels used for grouping"
    )
    commonLabels: dict[str, str] = Field(
        default_factory=dict, description="Labels common to all alerts"
    )
    commonAnnotations: dict[str, str] = Field(
        default_factory=dict, description="Annotations common to all alerts"
    )
    externalURL: str | None = Field(None, description="Alertmanager external URL")
    alerts: list[WebhookAlert] = Field(..., description="List of alerts in this group")


class WebhookProcessingResponse(BaseModel):
    """Schema for webhook processing response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "received": 1,
                "processed": 1,
                "message": "Processed 1 alert(s)",
            }
        }
    )

    status: str = Field(..., description="Processing status (ok or error)")
    received: int = Field(..., description="Number of alerts received")
    processed: int = Field(..., description="Number of alerts processed")
    message: str = Field(..., description="Human-readable status message")
