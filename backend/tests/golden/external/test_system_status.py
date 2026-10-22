"""Golden path for B4.11 — System status (expand).

Covers inventory rows:
- F-011, F-015, F-173: Unified AI health (`yolo26` `model_loaded` check and passive `ai_vlm`
  state across `/api/system/health`, `/api/system/health/full`, `/api/health/ai-services`,
  and `/api/system/performance`).
- F-037, F-126, F-139, F-140: Admin-session-guarded container and worker restart with
  two-step `AuditLog` recording and `RESTARTABLE_SERVICES` allowlist.
- F-009, F-292, F-293: Infrastructure alerts webhook (`POST /api/webhooks/alerts`),
  active alerts proxy (`GET /api/system/infrastructure-alerts`), and retirement of
  `/api/v1/alertmanager/webhook` (404).
- F-019, F-168, F-193: Mode-aware `POST /api/admin/maintenance/flush-queues`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest

pytestmark = [
    pytest.mark.network,
    pytest.mark.timeout(120),
]


def test_f011_f015_f173_ai_health_and_vlm_sleep_idle(
    api: httpx.Client,
    logged_in_api: httpx.Client,
) -> None:
    """All health readers agree on yolo26 and passive ai_vlm state, and VLM idles without probes."""
    health_resp = api.get("/api/system/health")
    assert health_resp.status_code in (200, 503), health_resp.text
    health_body = health_resp.json()
    assert "ai" in health_body["services"]
    ai_details = health_body["services"]["ai"]["details"]
    assert "yolo26" in ai_details
    assert "ai-vlm" in ai_details

    full_resp = logged_in_api.get("/api/system/health/full")
    assert full_resp.status_code in (200, 503), full_resp.text
    full_body = full_resp.json()
    ai_names = {svc["name"] for svc in full_body["ai_services"]}
    assert ai_names == {"yolo26", "ai-vlm"}

    ai_svc_resp = logged_in_api.get("/api/health/ai-services")
    assert ai_svc_resp.status_code in (200, 503), ai_svc_resp.text
    ai_svc_body = ai_svc_resp.json()
    assert set(ai_svc_body["services"]) == {"yolo26", "ai-vlm"}
    assert ai_svc_body["services"]["ai-vlm"]["state"] in (
        "ready",
        "idle",
        "loading",
        "failing",
        "unknown",
    )

    # Passive state check: repeated calls never HTTP-probe ai-vlm or mark it failing
    ai_svc_after = logged_in_api.get("/api/health/ai-services")
    assert ai_svc_after.status_code in (200, 503), ai_svc_after.text
    vlm_after = ai_svc_after.json()["services"]["ai-vlm"]
    assert vlm_after["state"] in ("idle", "unknown", "ready")
    assert vlm_after["status"] == "healthy"

    perf_resp = logged_in_api.get("/api/system/performance")
    assert perf_resp.status_code == 200, perf_resp.text
    perf_body = perf_resp.json()
    if perf_body.get("inference") is not None:
        assert "yolo26_latency_ms" in perf_body["inference"]
        assert "rtdetr_latency_ms" in perf_body["inference"]
        assert "nemotron_latency_ms" in perf_body["inference"]
        assert "ai_vlm_latency_ms" in perf_body["inference"]


def test_f037_f126_f139_f140_service_and_worker_restart_auth_and_audit(
    api: httpx.Client,
    logged_in_api: httpx.Client,
    admin_credentials: dict[str, str],
) -> None:
    """Service and worker restarts require an admin session, reject API keys, and write AuditLog rows."""
    # 1. Unauthenticated requests are rejected with 401
    anon_svc = api.post("/api/system/services/ai-vlm/restart")
    assert anon_svc.status_code == 401, anon_svc.text

    anon_worker = api.post("/api/system/supervisor/workers/file_watcher/restart")
    assert anon_worker.status_code == 401, anon_worker.text

    # 2. API-key-only requests are rejected with 403
    key_svc = api.post(
        "/api/system/services/ai-vlm/restart",
        headers={"X-API-Key": "test-api-key"},
    )
    assert key_svc.status_code in (401, 403), key_svc.text

    key_worker = api.post(
        "/api/system/supervisor/workers/file_watcher/restart",
        headers={"X-API-Key": "test-api-key"},
    )
    assert key_worker.status_code in (401, 403), key_worker.text

    # 3. Non-restartable service returns 404 or 503 (when orchestrator is disabled in CI)
    non_restartable = logged_in_api.post("/api/system/services/grafana/restart")
    assert non_restartable.status_code in (404, 503), non_restartable.text

    # 4. Restartable service with admin session returns 200 (when engine available) or 503 (in CI without socket)
    svc_restart = logged_in_api.post("/api/system/services/ai-vlm/restart")
    assert svc_restart.status_code in (200, 503), svc_restart.text

    # 5. Supervised worker restart with admin session writes AuditLog rows
    sup_status = logged_in_api.get("/api/system/supervisor/status")
    assert sup_status.status_code == 200, sup_status.text
    workers = sup_status.json().get("workers", [])
    if workers:
        worker_name = workers[0]["name"]
        worker_restart = logged_in_api.post(f"/api/system/supervisor/workers/{worker_name}/restart")
        assert worker_restart.status_code == 200, worker_restart.text
        assert worker_restart.json()["success"] is True

        audit_resp = logged_in_api.get("/api/audit?action=worker_restart&limit=10")
        assert audit_resp.status_code == 200, audit_resp.text
        audit_items = audit_resp.json().get("items", [])
        assert any(
            item.get("action") == "worker_restart"
            and item.get("actor") == admin_credentials["username"]
            for item in audit_items
        ), audit_items


def test_f009_f292_f293_infrastructure_alerts_webhook_and_retired_alertmanager(
    logged_in_api: httpx.Client,
) -> None:
    """POST /api/webhooks/alerts records firing alerts visible on GET /api/system/infrastructure-alerts; /api/v1/alertmanager/webhook is 404."""
    # F-293 retired route answers 404
    retired = logged_in_api.post("/api/v1/alertmanager/webhook", json={})
    assert retired.status_code == 404, retired.text

    fingerprint = f"b411-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(UTC).isoformat()
    firing_payload = {
        "version": "4",
        "groupKey": f"{{}}:{{alertname='B411SyntheticAlert-{fingerprint}'}}",
        "status": "firing",
        "receiver": "b411-golden",
        "groupLabels": {"alertname": "B411SyntheticAlert"},
        "commonLabels": {
            "alertname": "B411SyntheticAlert",
            "severity": "warning",
            "component": "ai-vlm",
        },
        "commonAnnotations": {
            "summary": "Synthetic B4.11 infrastructure alert",
            "description": "Testing webhook to infrastructure-alerts roundtrip",
        },
        "externalURL": "http://alertmanager:9093",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "B411SyntheticAlert",
                    "severity": "warning",
                    "component": "ai-vlm",
                },
                "annotations": {
                    "summary": "Synthetic B4.11 infrastructure alert",
                    "description": "Testing webhook to infrastructure-alerts roundtrip",
                },
                "startsAt": now_iso,
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://prometheus:9090/graph",
                "fingerprint": fingerprint,
            }
        ],
    }

    post_firing = logged_in_api.post("/api/webhooks/alerts", json=firing_payload)
    assert post_firing.status_code == 200, post_firing.text

    active_resp = logged_in_api.get("/api/system/infrastructure-alerts")
    assert active_resp.status_code == 200, active_resp.text
    active_alerts = active_resp.json()["alerts"]
    matching = [a for a in active_alerts if a["fingerprint"] == fingerprint]
    assert len(matching) == 1, active_alerts
    assert matching[0]["alertname"] == "B411SyntheticAlert"
    assert matching[0]["severity"] == "warning"
    assert matching[0]["status"] == "firing"

    # Resolve the synthetic alert so the stack stays clean
    resolved_payload = dict(firing_payload, status="resolved")
    resolved_payload["alerts"] = [
        dict(firing_payload["alerts"][0], status="resolved", endsAt=datetime.now(UTC).isoformat())
    ]
    post_resolved = logged_in_api.post("/api/webhooks/alerts", json=resolved_payload)
    assert post_resolved.status_code == 200, post_resolved.text

    after_resp = logged_in_api.get("/api/system/infrastructure-alerts")
    assert after_resp.status_code == 200, after_resp.text
    assert not [a for a in after_resp.json()["alerts"] if a["fingerprint"] == fingerprint]


def test_f019_f168_f193_flush_queues_streams_mode(
    logged_in_api: httpx.Client,
) -> None:
    """POST /api/admin/maintenance/flush-queues clears streams/lists by active mode."""
    resp = logged_in_api.post("/api/admin/maintenance/flush-queues")
    assert resp.status_code in (200, 403), resp.text
    if resp.status_code == 200:
        body = resp.json()
        assert "items_cleared" in body
        cleared_keys = set(body["items_cleared"])
        assert {"detections:stream", "analysis:stream"} <= cleared_keys or {
            "detection_queue",
            "analysis_queue",
        } <= cleared_keys, cleared_keys
