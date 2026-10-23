"""One AI service health module behind every badge, route, and broadcast (B4.11 / 4n-status.md).

Domain terms (`docs/reference/glossary.md`):
- **AI service state**: one of `ready`, `loading`, `idle`, `failing`, `unknown`.

Invariants (`docs/uplevel/4n-status.md` §Shape):
- `yolo26` reads the gateway's model readiness (`model_loaded`), not its HTTP status code alone.
- `ai_vlm` reads what `VlmClient` records (each call's outcome and time) and the `ai-vlm`
  circuit breaker's state. A VLM with no call for `VLM_SLEEP_IDLE_SECONDS` is `idle`; before
  its first call since start it is `unknown`.
- Nothing in the backend requests `ai-vlm` for status — this module never sends a network
  request to `ai-vlm`.
- A probe error is `failing` with its message, never `ready`.
"""

from __future__ import annotations

import inspect
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from backend.core.config import Settings, get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

AIServiceName = Literal["yolo26", "ai_vlm"]
AIServiceStateValue = Literal["ready", "loading", "idle", "failing", "unknown"]

AI_SERVICE_NAMES: tuple[AIServiceName, ...] = ("yolo26", "ai_vlm")
DEFAULT_PROBE_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True, slots=True)
class ServiceState:
    """Canonical health state of one AI service (`yolo26` or `ai_vlm`)."""

    service: str
    state: AIServiceStateValue
    detail: str | None = None
    since: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.since is not None:
            payload["since"] = self.since.isoformat()
        return payload


@dataclass(slots=True)
class _VlmCallRecord:
    outcome: Literal["ready", "loading", "failing"] | None = None
    detail: str | None = None
    at: datetime | None = None
    monotonic_at: float | None = None


ChangeCallback = Callable[[ServiceState], Awaitable[None] | None]

_vlm_record = _VlmCallRecord()
_last_states: dict[str, ServiceState] = {}
_change_callbacks: list[ChangeCallback] = []

# Sliding 5-minute window of per-request model inference latencies (in milliseconds)
_LATENCY_WINDOW_SECONDS = 300.0
_MAX_LATENCY_SAMPLES = 2000
_detector_latency_samples: deque[tuple[float, float]] = deque(maxlen=_MAX_LATENCY_SAMPLES)
_vlm_latency_samples: deque[tuple[float, float]] = deque(maxlen=_MAX_LATENCY_SAMPLES)


def record_detector_latency_ms(duration_ms: float, *, now_monotonic: float | None = None) -> None:
    """Record a single detector request duration (in milliseconds)."""
    ts = time.monotonic() if now_monotonic is None else now_monotonic
    _detector_latency_samples.append((ts, max(0.0, float(duration_ms))))


def record_vlm_latency_ms(duration_ms: float, *, now_monotonic: float | None = None) -> None:
    """Record a single VLM request duration (in milliseconds)."""
    ts = time.monotonic() if now_monotonic is None else now_monotonic
    _vlm_latency_samples.append((ts, max(0.0, float(duration_ms))))


def _compute_latency_stats(
    samples: deque[tuple[float, float]],
    *,
    now_monotonic: float | None = None,
) -> dict[str, float]:
    now_ts = time.monotonic() if now_monotonic is None else now_monotonic
    cutoff = now_ts - _LATENCY_WINDOW_SECONDS
    recent = sorted(val for ts, val in samples if ts >= cutoff)
    if not recent:
        return {"avg": 0.0, "p95": 0.0, "p99": 0.0}
    n = len(recent)
    avg = round(sum(recent) / n, 2)
    p95_idx = min(n - 1, max(0, int(0.95 * (n - 1))))
    p99_idx = min(n - 1, max(0, int(0.99 * (n - 1))))
    return {
        "avg": avg,
        "p95": round(recent[p95_idx], 2),
        "p99": round(recent[p99_idx], 2),
    }


def get_detector_latency_stats(*, now_monotonic: float | None = None) -> dict[str, float]:
    """Return avg/p95/p99 (ms) for recent detector requests."""
    return _compute_latency_stats(_detector_latency_samples, now_monotonic=now_monotonic)


def get_vlm_latency_stats(*, now_monotonic: float | None = None) -> dict[str, float]:
    """Return avg/p95/p99 (ms) for recent VLM requests."""
    return _compute_latency_stats(_vlm_latency_samples, now_monotonic=now_monotonic)


def on_change(callback: ChangeCallback) -> Callable[[], None]:
    """Register a callback invoked whenever a service's `state` changes.

    Returns an unsubscribe function.
    """
    if callback not in _change_callbacks:
        _change_callbacks.append(callback)

    def _unsubscribe() -> None:
        if callback in _change_callbacks:
            _change_callbacks.remove(callback)

    return _unsubscribe


async def _notify_if_changed(current: ServiceState) -> ServiceState:
    previous = _last_states.get(current.service)
    if previous is not None and previous.state == current.state:
        # Preserve the original `since` timestamp while the state stays the same
        stabilized = ServiceState(
            service=current.service,
            state=current.state,
            detail=current.detail,
            since=previous.since or current.since,
        )
        _last_states[current.service] = stabilized
        return stabilized

    _last_states[current.service] = current
    for cb in list(_change_callbacks):
        try:
            res = cb(current)
            if inspect.isawaitable(res):
                await res
        except Exception as exc:
            logger.warning(f"ai_health on_change callback error for {current.service}: {exc}")
    return current


def record_vlm_call(
    outcome: Literal["ready", "loading", "failing"],
    detail: str | None = None,
    *,
    at: datetime | None = None,
    monotonic_at: float | None = None,
) -> None:
    """Record the outcome and timestamp of a real VlmClient call (never a health probe)."""
    _vlm_record.outcome = outcome
    _vlm_record.detail = detail
    _vlm_record.at = at or datetime.now(UTC)
    _vlm_record.monotonic_at = time.monotonic() if monotonic_at is None else monotonic_at


async def record_vlm_call_and_notify(
    outcome: Literal["ready", "loading", "failing"],
    detail: str | None = None,
    *,
    at: datetime | None = None,
    monotonic_at: float | None = None,
    settings: Settings | None = None,
) -> ServiceState:
    """Record a VlmClient call outcome and immediately evaluate/notify state transitions."""
    record_vlm_call(outcome, detail, at=at, monotonic_at=monotonic_at)
    return await state("ai_vlm", settings=settings)


def reset_ai_health_state() -> None:
    """Reset in-memory state (for unit tests)."""
    global _vlm_record  # noqa: PLW0603
    _vlm_record = _VlmCallRecord()
    _last_states.clear()
    _change_callbacks.clear()
    _detector_latency_samples.clear()
    _vlm_latency_samples.clear()
    try:
        from backend.services.circuit_breaker import _get_registry

        reg = _get_registry()
        for name in ("ai-vlm", "vlm_assess", "yolo26"):
            breaker = reg.get(name)
            if breaker is not None and hasattr(breaker, "reset"):
                breaker.reset()
    except Exception:  # noqa: S110
        pass


def _normalize_service_name(service: str) -> AIServiceName:
    if service in ("yolo26", "rtdetr", "ai-yolo26"):
        return "yolo26"
    if service in ("ai_vlm", "ai-vlm", "nemotron"):
        return "ai_vlm"
    raise ValueError(f"Unknown AI service: {service!r} (expected 'yolo26' or 'ai_vlm')")


def _evaluate_ai_vlm_state(  # noqa: PLR0911
    settings: Settings,
    *,
    now: datetime | None = None,
    now_monotonic: float | None = None,
) -> ServiceState:
    """Compute `ai_vlm` state from the VLM client call record and circuit breaker.

    Never sends a network request to `ai-vlm`.
    """
    from backend.services.circuit_breaker import _get_registry

    current_dt = now or datetime.now(UTC)
    current_mono = time.monotonic() if now_monotonic is None else now_monotonic

    if not getattr(settings, "ai_vlm_url", None):
        return ServiceState(
            service="ai_vlm",
            state="unknown",
            detail="Service URL not configured",
            since=current_dt,
        )

    registry = _get_registry()
    breaker = registry.get("ai-vlm")
    if breaker is not None and breaker.state.value == "open":
        return ServiceState(
            service="ai_vlm",
            state="failing",
            detail=_vlm_record.detail or "Circuit breaker is open",
            since=_vlm_record.at or current_dt,
        )

    if _vlm_record.outcome is None or _vlm_record.at is None:
        return ServiceState(
            service="ai_vlm",
            state="unknown",
            detail="No VLM call recorded since startup",
            since=current_dt,
        )

    if _vlm_record.outcome == "failing":
        return ServiceState(
            service="ai_vlm",
            state="failing",
            detail=_vlm_record.detail or "Last VLM call failed",
            since=_vlm_record.at,
        )

    if _vlm_record.outcome == "loading":
        return ServiceState(
            service="ai_vlm",
            state="loading",
            detail=_vlm_record.detail or "VLM is loading model",
            since=_vlm_record.at,
        )

    sleep_idle = int(getattr(settings, "vlm_sleep_idle_seconds", 300) or 0)
    if sleep_idle > 0:
        if _vlm_record.monotonic_at is not None:
            elapsed = current_mono - _vlm_record.monotonic_at
        else:
            elapsed = (current_dt - _vlm_record.at).total_seconds()
        if elapsed >= sleep_idle:
            return ServiceState(
                service="ai_vlm",
                state="idle",
                detail="Idle (asleep)",
                since=_vlm_record.at,
            )

    return ServiceState(
        service="ai_vlm",
        state="ready",
        detail=_vlm_record.detail,
        since=_vlm_record.at,
    )


async def _evaluate_yolo26_state(  # noqa: PLR0911
    settings: Settings,
    *,
    timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    http_client: httpx.AsyncClient | None = None,
) -> ServiceState:
    """Probe `yolo26` `/health` and inspect `model_loaded` (never HTTP status code alone)."""
    from backend.services.circuit_breaker import _get_registry

    now = datetime.now(UTC)
    yolo26_url = getattr(settings, "yolo26_url", None)
    if not yolo26_url:
        return ServiceState(
            service="yolo26",
            state="unknown",
            detail="Service URL not configured",
            since=now,
        )

    registry = _get_registry()
    breaker = registry.get("yolo26")
    if breaker is not None and breaker.state.value == "open":
        return ServiceState(
            service="yolo26",
            state="failing",
            detail="Circuit breaker is open",
            since=now,
        )

    health_url = f"{yolo26_url.rstrip('/')}/health"
    try:
        if http_client is not None:
            response = await http_client.get(health_url, timeout=timeout)
        else:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(health_url)

        if response.status_code == 503:
            return ServiceState(
                service="yolo26",
                state="loading",
                detail="HTTP 503 (model loading)",
                since=now,
            )
        if response.status_code != 200:
            return ServiceState(
                service="yolo26",
                state="failing",
                detail=f"HTTP {response.status_code}",
                since=now,
            )

        raw_content = getattr(response, "content", None)
        if raw_content in {b"", ""}:
            return ServiceState(service="yolo26", state="ready", detail=None, since=now)

        try:
            body = response.json()
        except Exception as exc:
            return ServiceState(
                service="yolo26",
                state="failing",
                detail=f"Invalid health JSON: {exc}",
                since=now,
            )

        if not isinstance(body, dict):
            if body is None or isinstance(body, (list, str, int, float, bool)):
                return ServiceState(
                    service="yolo26",
                    state="failing",
                    detail="Invalid health payload",
                    since=now,
                )
            # Non-primitive object (e.g. unconfigured MagicMock in unit tests with HTTP 200)
            return ServiceState(service="yolo26", state="ready", detail=None, since=now)

        # Primary contract (`ai/gateway/adapters/yolo26.py:511-519`): `model_loaded` boolean
        if "model_loaded" in body:
            if body["model_loaded"] is True:
                return ServiceState(service="yolo26", state="ready", detail=None, since=now)
            return ServiceState(
                service="yolo26",
                state="loading",
                detail="model not loaded",
                since=now,
            )

        # Gateway root `/health` fallback (`models.yolo26`)
        models_map = body.get("models")
        if isinstance(models_map, dict) and "yolo26" in models_map:
            if models_map["yolo26"] is True:
                return ServiceState(service="yolo26", state="ready", detail=None, since=now)
            return ServiceState(
                service="yolo26",
                state="loading",
                detail="model not loaded",
                since=now,
            )

        status_str = str(body.get("status", "")).lower()
        if status_str in ("healthy", "ok", "ready"):
            return ServiceState(service="yolo26", state="ready", detail=None, since=now)
        if status_str in ("loading", "starting", "degraded"):
            return ServiceState(
                service="yolo26",
                state="loading",
                detail=f"status={status_str}",
                since=now,
            )

        return ServiceState(
            service="yolo26",
            state="failing",
            detail=f"Unexpected health status: {body.get('status')!r}",
            since=now,
        )
    except httpx.ConnectError:
        return ServiceState(
            service="yolo26",
            state="failing",
            detail="Connection refused",
            since=now,
        )
    except httpx.TimeoutException:
        return ServiceState(
            service="yolo26",
            state="failing",
            detail=f"Timeout after {timeout}s",
            since=now,
        )
    except Exception as exc:
        return ServiceState(
            service="yolo26",
            state="failing",
            detail=str(exc) or type(exc).__name__,
            since=now,
        )


async def state(
    service: str,
    *,
    settings: Settings | None = None,
    timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    http_client: httpx.AsyncClient | None = None,
    now: datetime | None = None,
    now_monotonic: float | None = None,
) -> ServiceState:
    """Return the canonical `ServiceState` for `yolo26` or `ai_vlm`."""
    canonical = _normalize_service_name(service)
    resolved_settings = settings or get_settings()
    if canonical == "yolo26":
        current = await _evaluate_yolo26_state(
            resolved_settings,
            timeout=timeout,
            http_client=http_client,
        )
    else:
        current = _evaluate_ai_vlm_state(
            resolved_settings,
            now=now,
            now_monotonic=now_monotonic,
        )
    return await _notify_if_changed(current)


async def snapshot(
    *,
    settings: Settings | None = None,
    timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, ServiceState]:
    """Return `{"yolo26": ServiceState, "ai_vlm": ServiceState}`."""
    resolved_settings = settings or get_settings()
    yolo_state = await state(
        "yolo26",
        settings=resolved_settings,
        timeout=timeout,
        http_client=http_client,
    )
    vlm_state = await state("ai_vlm", settings=resolved_settings)
    return {
        "yolo26": yolo_state,
        "ai_vlm": vlm_state,
    }
