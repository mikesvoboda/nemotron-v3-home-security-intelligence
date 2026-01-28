# Fallback Strategies

The AI fallback system provides graceful degradation when AI services become unavailable. It integrates with circuit breakers and the degradation manager to maintain service continuity.

## Source File

`backend/services/ai_fallback.py`

## Architecture Overview

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'primaryColor': '#3B82F6',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#60A5FA',
    'secondaryColor': '#A855F7',
    'tertiaryColor': '#009688',
    'background': '#121212',
    'mainBkg': '#1a1a2e',
    'lineColor': '#666666'
  }
}}%%
flowchart LR
    subgraph Input
        ASC["AI Service Call<br/>(Failed)"]
    end

    subgraph Fallback["AIFallbackService"]
        CA[Check Availability]
        GF[Get Fallback Value]
        CR[Cache Risk Scores]
    end

    subgraph Status["Service Status"]
        HEALTHY
        DEGRADED
        UNAVAILABLE
    end

    subgraph Levels["Degradation Level"]
        NORMAL
        DEG[DEGRADED]
        MINIMAL
        OFFLINE
    end

    ASC --> Fallback
    Fallback --> Status
    Status --> Levels
```

## AI Service Identifiers

```python
class AIService(StrEnum):
    """AI service identifiers."""
    YOLO26 = "yolo26"
    NEMOTRON = "nemotron"
    FLORENCE = "florence"
    CLIP = "clip"
```

## Degradation Levels

```python
class DegradationLevel(StrEnum):
    """System degradation levels based on AI service availability."""
    NORMAL = "normal"      # All services healthy
    DEGRADED = "degraded"  # Non-critical services down
    MINIMAL = "minimal"    # Critical services partially available
    OFFLINE = "offline"    # All AI services down
```

### Level Determination

```python
# Critical services
CRITICAL_SERVICES = {AIService.YOLO26, AIService.NEMOTRON}

def get_degradation_level(self) -> DegradationLevel:
    """Get current system degradation level."""
    critical_unavailable = 0
    non_critical_unavailable = 0

    for service, state in self._service_states.items():
        if state.status == ServiceStatus.UNAVAILABLE:
            if service in CRITICAL_SERVICES:
                critical_unavailable += 1
            else:
                non_critical_unavailable += 1

    # All critical down -> OFFLINE
    if critical_unavailable == len(CRITICAL_SERVICES):
        return DegradationLevel.OFFLINE

    # Some critical down -> MINIMAL
    elif critical_unavailable > 0:
        return DegradationLevel.MINIMAL

    # Only non-critical down -> DEGRADED
    elif non_critical_unavailable > 0:
        return DegradationLevel.DEGRADED

    # All healthy -> NORMAL
    return DegradationLevel.NORMAL
```

## Service Status Tracking

```python
class ServiceStatus(StrEnum):
    """Individual service status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"

@dataclass(slots=True)
class ServiceState:
    """State information for a single AI service."""
    service: AIService
    status: ServiceStatus = ServiceStatus.HEALTHY
    circuit_state: CircuitState = CircuitState.CLOSED
    last_success: datetime | None = None
    failure_count: int = 0
    error_message: str | None = None
    last_check: datetime | None = None
```

## Circuit Breaker Integration

Status is derived from circuit breaker state:

```python
async def _check_service_health(self, service: AIService) -> None:
    """Check health of a specific service."""
    state = self._service_states[service]
    state.last_check = datetime.now(UTC)

    # Get circuit breaker state if registered
    cb = self._circuit_breakers.get(service)
    if cb is not None:
        state.circuit_state = cb.get_state()
        state.failure_count = cb.failure_count

        # Map circuit state to service status
        if state.circuit_state == CircuitState.OPEN:
            state.status = ServiceStatus.UNAVAILABLE
        elif state.circuit_state == CircuitState.HALF_OPEN:
            state.status = ServiceStatus.DEGRADED
        else:  # CLOSED
            state.status = ServiceStatus.HEALTHY
```

### Default Circuit Breaker Configurations

```python
DEFAULT_CB_CONFIGS = {
    AIService.YOLO26: CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=60.0,
        half_open_max_calls=2,
        success_threshold=2,
    ),
    AIService.NEMOTRON: CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=90.0,
        half_open_max_calls=3,
        success_threshold=2,
    ),
    AIService.FLORENCE: CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60.0,
        half_open_max_calls=3,
        success_threshold=2,
    ),
    AIService.CLIP: CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60.0,
        half_open_max_calls=3,
        success_threshold=2,
    ),
}
```

## Fallback Risk Analysis

When Nemotron is unavailable, provide fallback risk scores:

```python
@dataclass(slots=True)
class FallbackRiskAnalysis:
    """Fallback risk analysis when Nemotron unavailable."""
    risk_score: int           # Default or cached score (0-100)
    reasoning: str            # Explanation of fallback
    is_fallback: bool = True  # Always True
    source: str = "default"   # "cache", "object_type_estimate", "default"

def get_fallback_risk_analysis(
    self,
    camera_name: str | None = None,
    object_types: list[str] | None = None,
) -> FallbackRiskAnalysis:
    """Get fallback risk analysis when Nemotron unavailable."""

    # 1. Try cached value first
    if camera_name:
        cached = self._risk_cache.get_cached_score(camera_name)
        if cached is not None:
            return FallbackRiskAnalysis(
                risk_score=cached,
                reasoning=f"Using cached risk score from '{camera_name}'",
                source="cache",
            )

    # 2. Calculate from object types
    if object_types:
        scores = [self._risk_cache.get_object_type_score(obj) for obj in object_types]
        avg_score = int(sum(scores) / len(scores))
        return FallbackRiskAnalysis(
            risk_score=avg_score,
            reasoning=f"Estimated from detected objects: {', '.join(object_types)}",
            source="object_type_estimate",
        )

    # 3. Default fallback
    return FallbackRiskAnalysis(
        risk_score=50,
        reasoning="Using default medium risk score",
        source="default",
    )
```

### Default Object Type Scores

```python
@dataclass(slots=True)
class RiskScoreCache:
    """Cache for risk score patterns."""

    object_type_scores: dict[str, int] = field(
        default_factory=lambda: {
            "person": 60,
            "vehicle": 50,
            "car": 50,
            "truck": 55,
            "motorcycle": 45,
            "bicycle": 30,
            "dog": 25,
            "cat": 20,
            "bird": 10,
            "unknown": 50,
        }
    )
    ttl_seconds: int = 300  # 5 minute cache TTL
```

## Fallback Methods by Service

### Detection (YOLO26)

```python
def should_skip_detection(self) -> bool:
    """Check if detection should be skipped."""
    return not self.is_service_available(AIService.YOLO26)

# When skipped: No detections created, event skipped entirely
```

### Risk Analysis (Nemotron)

```python
def should_use_default_risk(self) -> bool:
    """Check if default risk score should be used."""
    return not self.is_service_available(AIService.NEMOTRON)

# Fallback: Use get_fallback_risk_analysis()
```

### Captions (Florence-2)

```python
def should_skip_captions(self) -> bool:
    """Check if caption generation should be skipped."""
    return not self.is_service_available(AIService.FLORENCE)

def get_fallback_caption(
    self,
    object_types: list[str] | None = None,
    camera_name: str | None = None,
) -> str:
    """Get fallback caption when Florence unavailable."""
    if not object_types:
        if camera_name:
            return f"Activity detected at {camera_name}"
        return "Activity detected"

    objects_str = ", ".join(object_types)
    if camera_name:
        return f"{objects_str.capitalize()} detected at {camera_name}"
    return f"{objects_str.capitalize()} detected"
```

### Re-identification (CLIP)

```python
def should_skip_reid(self) -> bool:
    """Check if re-identification should be skipped."""
    return not self.is_service_available(AIService.CLIP)

def get_fallback_embedding(self) -> list[float]:
    """Get fallback embedding when CLIP unavailable.

    Returns a zero vector that will not match any existing embeddings.
    """
    return [0.0] * 768  # 768-dimensional zero vector
```

## Available Features by Degradation Level

```python
def get_available_features(self) -> list[str]:
    """Get list of currently available features."""
    features = []

    # Detection features (requires YOLO26)
    if self.is_service_available(AIService.YOLO26):
        features.extend(["object_detection", "detection_alerts"])

    # Risk analysis features (requires Nemotron)
    if self.is_service_available(AIService.NEMOTRON):
        features.extend(["risk_analysis", "llm_reasoning"])

    # Caption features (requires Florence-2)
    if self.is_service_available(AIService.FLORENCE):
        features.extend(["image_captioning", "ocr", "dense_captioning"])

    # Re-identification features (requires CLIP)
    if self.is_service_available(AIService.CLIP):
        features.extend(["entity_tracking", "re_identification", "anomaly_detection"])

    # Basic features always available
    features.extend(["event_history", "camera_feeds", "system_monitoring"])

    return features
```

## Health Check Loop

Background health checks run continuously:

```python
class AIFallbackService:
    def __init__(self, ..., health_check_interval: float = 15.0):
        self._health_check_interval = health_check_interval

    async def start(self) -> None:
        """Start the health check background task."""
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self) -> None:
        """Background loop for health checks."""
        while self._running:
            await self._check_all_services()
            await asyncio.sleep(self._health_check_interval)
```

## Status Change Notifications

Register callbacks for WebSocket broadcasting:

```python
def register_status_callback(self, callback: Any) -> None:
    """Register callback for status changes."""
    self._status_callbacks.append(callback)

async def _notify_status_change(self) -> None:
    """Notify all registered callbacks of status change."""
    status = self.get_degradation_status()

    for callback in self._status_callbacks:
        try:
            await callback(status)
        except Exception as e:
            logger.error(f"Status callback error: {e}")
```

## Degradation Status API

```python
def get_degradation_status(self) -> dict[str, Any]:
    """Get comprehensive degradation status."""
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "degradation_mode": self.get_degradation_level().value,
        "services": {
            service.value: state.to_dict()
            for service, state in self._service_states.items()
        },
        "available_features": self.get_available_features(),
    }
```

### Example Response

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "degradation_mode": "degraded",
  "services": {
    "yolo26": {
      "service": "yolo26",
      "status": "healthy",
      "circuit_state": "closed",
      "last_success": "2024-01-15T10:29:55Z",
      "failure_count": 0,
      "error_message": null,
      "last_check": "2024-01-15T10:30:00Z"
    },
    "nemotron": {
      "service": "nemotron",
      "status": "healthy",
      "circuit_state": "closed",
      "last_success": "2024-01-15T10:29:50Z",
      "failure_count": 0,
      "error_message": null,
      "last_check": "2024-01-15T10:30:00Z"
    },
    "florence": {
      "service": "florence",
      "status": "unavailable",
      "circuit_state": "open",
      "last_success": "2024-01-15T10:15:00Z",
      "failure_count": 5,
      "error_message": "Connection refused",
      "last_check": "2024-01-15T10:30:00Z"
    },
    "clip": {
      "service": "clip",
      "status": "healthy",
      "circuit_state": "closed",
      "last_success": "2024-01-15T10:29:58Z",
      "failure_count": 0,
      "error_message": null,
      "last_check": "2024-01-15T10:30:00Z"
    }
  },
  "available_features": [
    "object_detection",
    "detection_alerts",
    "risk_analysis",
    "llm_reasoning",
    "entity_tracking",
    "re_identification",
    "anomaly_detection",
    "event_history",
    "camera_feeds",
    "system_monitoring"
  ]
}
```

## Risk Score Caching

Cache successful risk scores for fallback:

```python
def cache_risk_score(self, camera_name: str, risk_score: int) -> None:
    """Cache a successful risk score for fallback use."""
    self._risk_cache.set_cached_score(camera_name, risk_score)

# In NemotronAnalyzer after successful analysis:
if event.risk_score is not None:
    fallback_service.cache_risk_score(camera_name, event.risk_score)
```

## Usage Example

```python
from backend.services.ai_fallback import get_ai_fallback_service, AIService

# Get singleton instance
fallback = get_ai_fallback_service()

# Start health checks
await fallback.start()

# Check service availability
if fallback.is_service_available(AIService.NEMOTRON):
    # Full analysis
    result = await analyzer.analyze(detection)
else:
    # Fallback analysis
    result = fallback.get_fallback_risk_analysis(
        camera_name="Front Door",
        object_types=["person"],
    )

# Get overall status
status = fallback.get_degradation_status()
print(f"Degradation level: {status['degradation_mode']}")

# Cache successful scores for later fallback
fallback.cache_risk_score("Front Door", result.risk_score)

# Stop health checks on shutdown
await fallback.stop()
```

## Recovery Behavior

When services recover:

1. **Half-Open State**: Circuit breaker allows limited test calls
2. **Success Threshold**: After N successful calls, circuit closes
3. **Status Update**: Service status changes from UNAVAILABLE to HEALTHY
4. **Callback Notification**: All registered callbacks receive status update
5. **Feature Restoration**: get_available_features() includes restored capabilities

The system automatically recovers without manual intervention when services become healthy again.
