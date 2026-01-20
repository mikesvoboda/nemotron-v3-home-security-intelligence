"""Pydantic schemas for Alertmanager webhook endpoint.

This module defines schemas for receiving alerts from Prometheus Alertmanager
and storing them in the database for history tracking.

Alertmanager Webhook Format:
    https://prometheus.io/docs/alerting/latest/configuration/#webhook_config

NEM-3122: Phase 3.1 - Alertmanager webhook receiver for Prometheus alerts.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class PrometheusAlertStatus(StrEnum):
    """Prometheus alert status values."""

    FIRING = "firing"
    RESOLVED = "resolved"


class AlertmanagerAlert(BaseModel):
    """Schema for a single alert in Alertmanager webhook payload.

    Represents one alert instance with its labels, annotations, and timing.
    This schema matches the Alertmanager webhook format.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fingerprint": "abc123def456",  # pragma: allowlist secret
                "status": "firing",
                "labels": {
                    "alertname": "HighCPU",
                    "severity": "warning",
                    "instance": "localhost:9090",
                },
                "annotations": {
                    "summary": "CPU usage is high",
                    "description": "CPU usage is above 80% for 5 minutes",
                },
                "startsAt": "2026-01-20T12:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://prometheus:9090/graph?...",
            }
        }
    )

    fingerprint: str = Field(..., description="Unique identifier for alert deduplication")
    status: PrometheusAlertStatus = Field(..., description="Alert status (firing or resolved)")
    labels: dict[str, str] = Field(
        default_factory=dict, description="Alert labels (alertname, severity, etc.)"
    )
    annotations: dict[str, str] = Field(
        default_factory=dict, description="Alert annotations (summary, description)"
    )
    startsAt: datetime = Field(..., description="When the alert started firing")
    endsAt: datetime | None = Field(None, description="When the alert was resolved")
    generatorURL: str | None = Field(None, description="URL to the Prometheus graph")


class AlertmanagerWebhook(BaseModel):
    """Schema for Alertmanager webhook payload.

    This is the format Alertmanager sends when configured with a webhook receiver.
    See: https://prometheus.io/docs/alerting/latest/configuration/#webhook_config
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": "4",
                "groupKey": '{}:{alertname="HighCPU"}',
                "truncatedAlerts": 0,
                "status": "firing",
                "receiver": "webhook-receiver",
                "groupLabels": {"alertname": "HighCPU"},
                "commonLabels": {
                    "alertname": "HighCPU",
                    "severity": "warning",
                },
                "commonAnnotations": {"summary": "CPU usage is high"},
                "externalURL": "http://alertmanager:9093",
                "alerts": [
                    {
                        "fingerprint": "abc123",
                        "status": "firing",
                        "labels": {"alertname": "HighCPU", "severity": "warning"},
                        "annotations": {"description": "CPU at 85%"},
                        "startsAt": "2026-01-20T12:00:00Z",
                        "endsAt": "0001-01-01T00:00:00Z",
                    }
                ],
            }
        }
    )

    version: str = Field("4", description="Alertmanager webhook version")
    groupKey: str = Field(..., description="Key identifying the alert group")
    truncatedAlerts: int = Field(0, description="Number of truncated alerts")
    status: PrometheusAlertStatus = Field(..., description="Overall group status")
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
    alerts: list[AlertmanagerAlert] = Field(..., description="List of alerts in this group")


class AlertmanagerWebhookResponse(BaseModel):
    """Response schema for the alertmanager webhook endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "received": 2,
                "stored": 2,
                "broadcast": 2,
                "message": "Processed 2 alert(s)",
            }
        }
    )

    status: str = Field(..., description="Processing status (ok or error)")
    received: int = Field(..., description="Number of alerts received")
    stored: int = Field(..., description="Number of alerts stored in database")
    broadcast: int = Field(..., description="Number of alerts broadcast via WebSocket")
    message: str = Field(..., description="Human-readable status message")


class PrometheusAlertResponse(BaseModel):
    """Response schema for individual Prometheus alert details."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "fingerprint": "abc123def456",  # pragma: allowlist secret
                "status": "firing",
                "labels": {
                    "alertname": "HighCPU",
                    "severity": "warning",
                },
                "annotations": {
                    "summary": "CPU usage is high",
                    "description": "CPU usage is above 80%",
                },
                "starts_at": "2026-01-20T12:00:00Z",
                "ends_at": None,
                "received_at": "2026-01-20T12:00:05Z",
            }
        },
    )

    id: int = Field(..., description="Database ID")
    fingerprint: str = Field(..., description="Alert fingerprint")
    status: str = Field(..., description="Alert status")
    labels: dict[str, str] = Field(..., description="Alert labels")
    annotations: dict[str, str] = Field(..., description="Alert annotations")
    starts_at: datetime = Field(..., description="When the alert started")
    ends_at: datetime | None = Field(None, description="When the alert resolved")
    received_at: datetime = Field(..., description="When the alert was received by backend")
