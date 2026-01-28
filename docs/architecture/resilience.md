---
title: Resilience Architecture
description: Circuit breakers, retry logic, dead-letter queues, health monitoring, and graceful degradation patterns
last_updated: 2026-01-18
source_refs:
  - backend/services/circuit_breaker.py:CircuitBreaker:270
  - backend/services/circuit_breaker.py:CircuitBreakerConfig:139
  - backend/services/circuit_breaker.py:CircuitBreakerRegistry:1018
  - backend/services/circuit_breaker.py:CircuitState:130
  - backend/core/websocket_circuit_breaker.py:WebSocketCircuitBreaker:96
  - backend/core/websocket_circuit_breaker.py:WebSocketCircuitState:39
  - backend/core/websocket_circuit_breaker.py:WebSocketCircuitBreakerMetrics:47
  - backend/services/system_broadcaster.py:SystemBroadcaster:66
  - backend/services/event_broadcaster.py:EventBroadcaster:330
  - backend/services/retry_handler.py:RetryHandler:184
  - backend/services/retry_handler.py:RetryConfig:64
  - backend/services/retry_handler.py:DLQStats:175
  - backend/services/health_monitor.py:ServiceHealthMonitor:44
  - backend/services/degradation_manager.py:DegradationManager
  - backend/services/service_managers.py:ServiceManager
  - frontend/src/hooks/useWebSocket.ts:useWebSocket:56
  - frontend/src/hooks/useWebSocket.ts:WebSocketOptions:13
  - frontend/src/hooks/useWebSocket.ts:UseWebSocketReturn:40
  - frontend/src/hooks/webSocketManager.ts:WebSocketManager:187
  - frontend/src/hooks/webSocketManager.ts:calculateBackoffDelay:150
---

# Resilience Architecture

This document details the resilience patterns implemented in the Home Security Intelligence system to ensure reliable operation even when external services (YOLO26, Nemotron LLM, Redis) experience failures.

---

## Table of Contents

1. [Resilience Overview](#resilience-overview)
2. [Circuit Breaker Pattern](#circuit-breaker-pattern)
3. [Retry Handler with Exponential Backoff](#retry-handler-with-exponential-backoff)
4. [Dead-Letter Queue (DLQ) Management](#dead-letter-queue-dlq-management)
5. [Service Health Monitoring](#service-health-monitoring)
6. [Graceful Degradation](#graceful-degradation)
7. [Recovery Strategies](#recovery-strategies)
8. [Configuration Reference](#configuration-reference)
9. [Image Generation Prompts](#image-generation-prompts)
10. [WebSocket Circuit Breaker and Degraded Mode](#websocket-circuit-breaker-and-degraded-mode)

---

## Resilience Overview

The system implements multiple layers of resilience to handle failures gracefully:

![Resilience Architecture Overview](../images/resilience/resilience-overview.svg)

_Layered resilience architecture showing circuit breakers, retry logic with exponential backoff, dead-letter queues, and health monitoring._

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
flowchart TB
    subgraph Input["Incoming Request"]
        REQ[Service Call]
    end

    subgraph CircuitBreaker["Circuit Breaker Layer"]
        CB{Circuit<br/>State?}
        CLOSED[CLOSED<br/>Normal Operation]
        OPEN[OPEN<br/>Fast Fail]
        HALF[HALF_OPEN<br/>Test Recovery]
    end

    subgraph Retry["Retry Layer"]
        RT{Retry<br/>Attempt?}
        BACKOFF[Exponential<br/>Backoff]
        EXEC[Execute<br/>Operation]
    end

    subgraph Outcome["Outcome Handling"]
        SUCCESS[Success<br/>Reset Counters]
        FAIL[Failure<br/>Increment Counter]
        DLQ[Dead Letter<br/>Queue]
    end

    subgraph Recovery["Recovery Services"]
        HM[Health<br/>Monitor]
        AUTO[Auto<br/>Restart]
    end

    REQ --> CB
    CB -->|Closed| CLOSED --> RT
    CB -->|Open| OPEN --> FAIL
    CB -->|Half-Open| HALF --> RT

    RT -->|Yes| BACKOFF --> EXEC
    RT -->|Max Retries| DLQ

    EXEC -->|OK| SUCCESS
    EXEC -->|Error| FAIL

    FAIL -->|Threshold Met| OPEN
    SUCCESS --> CLOSED

    HM -->|Unhealthy| AUTO
    AUTO -->|Restart| HM

    style OPEN fill:#E74856,color:#fff
    style SUCCESS fill:#76B900,color:#fff
    style DLQ fill:#A855F7,color:#fff
    style HALF fill:#FFB800,color:#000
```

</details>

### Resilience Components

| Component                                                        | Location                                  | Responsibility                              |
| ---------------------------------------------------------------- | ----------------------------------------- | ------------------------------------------- |
| [CircuitBreaker](../../backend/services/circuit_breaker.py)      | `backend/services/circuit_breaker.py:270` | Prevents cascading failures by failing fast |
| [RetryHandler](../../backend/services/retry_handler.py)          | `backend/services/retry_handler.py:184`   | Exponential backoff with DLQ support        |
| [ServiceHealthMonitor](../../backend/services/health_monitor.py) | `backend/services/health_monitor.py:44`   | Periodic health checks and auto-recovery    |
| DegradationManager                                               | `backend/services/degradation_manager.py` | Graceful degradation during outages         |

---

## Circuit Breaker Pattern

The circuit breaker protects external services from cascading failures by monitoring failure rates and temporarily blocking calls to unhealthy services.

### Circuit Breaker States

![Circuit Breaker State Machine](../images/resilience/circuit-breaker-states.svg)

_State machine showing transitions between CLOSED (normal), OPEN (tripped), and HALF_OPEN (testing) states._

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
stateDiagram-v2
    [*] --> CLOSED: Initial State

    CLOSED --> OPEN: failures >= threshold
    OPEN --> HALF_OPEN: recovery_timeout elapsed
    HALF_OPEN --> CLOSED: success_threshold met
    HALF_OPEN --> OPEN: any failure

    CLOSED: Normal Operation
    CLOSED: Calls pass through
    CLOSED: Track failures

    OPEN: Circuit Tripped
    OPEN: Calls rejected immediately
    OPEN: CircuitBreakerError raised

    HALF_OPEN: Recovery Testing
    HALF_OPEN: Limited calls allowed
    HALF_OPEN: Track successes
```

</details>

### Implementation Details

The [CircuitBreaker](../../backend/services/circuit_breaker.py) class at line 270 implements the pattern:

```python
# backend/services/circuit_breaker.py:270
class CircuitBreaker:
    """Circuit breaker for protecting external service calls.

    Implements the circuit breaker pattern with three states:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Service failing, calls rejected immediately
    - HALF_OPEN: Testing recovery, limited calls allowed
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        self._name = name
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        # ...
```

### Circuit Breaker Configuration

The [CircuitBreakerConfig](../../backend/services/circuit_breaker.py) at line 139 defines behavior:

| Parameter             | Default | Description                                  |
| --------------------- | ------- | -------------------------------------------- |
| `failure_threshold`   | 5       | Failures before opening circuit              |
| `recovery_timeout`    | 30.0s   | Wait time before testing recovery            |
| `half_open_max_calls` | 3       | Max calls allowed in half-open state         |
| `success_threshold`   | 2       | Successes needed to close circuit            |
| `excluded_exceptions` | ()      | Exception types that don't count as failures |

### Usage Pattern

```python
from backend.services.circuit_breaker import get_circuit_breaker, CircuitBreakerConfig

# Get or create circuit breaker for a service
breaker = get_circuit_breaker(
    "yolo26",
    CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=30.0,
    )
)

# Execute through circuit breaker
try:
    result = await breaker.call(detector_client.detect_objects, image_path)
except CircuitBreakerError:
    # Service unavailable, use fallback
    result = []
```

### Circuit Breaker Registry

The [CircuitBreakerRegistry](../../backend/services/circuit_breaker.py) at line 1018 manages multiple breakers:

![Circuit Breaker Registry](../images/resilience/circuit-breaker-registry.svg)

_Global registry managing circuit breakers for yolo26, nemotron, and redis services._

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
flowchart TB
    subgraph Registry["CircuitBreakerRegistry"]
        R[Global Registry]
    end

    subgraph Breakers["Individual Circuit Breakers"]
        B1[yolo26<br/>breaker]
        B2[nemotron<br/>breaker]
        B3[redis<br/>breaker]
    end

    subgraph Services["Protected Services"]
        S1[YOLO26<br/>:8090]
        S2[Nemotron LLM<br/>:8091]
        S3[Redis<br/>:6379]
    end

    R --> B1
    R --> B2
    R --> B3

    B1 --> S1
    B2 --> S2
    B3 --> S3

    style S1 fill:#3B82F6,color:#fff
    style S2 fill:#3B82F6,color:#fff
    style S3 fill:#A855F7,color:#fff
```

</details>

---

## Retry Handler with Exponential Backoff

The [RetryHandler](../../backend/services/retry_handler.py) at line 184 provides automatic retries with exponential backoff for transient failures.

### Retry Flow

![Retry Handler Flow](../images/resilience/retry-handler-flow.svg)

_Retry flow showing exponential backoff calculation, jitter application, cap enforcement, and dead-letter queue handling._

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
flowchart TB
    subgraph Input["Job Processing"]
        JOB[Detection/Analysis Job]
    end

    subgraph RetryLoop["Retry Handler"]
        ATT{Attempt<br/>N of Max?}
        EXEC[Execute<br/>Operation]
        CHK{Success?}
        CALC[Calculate<br/>Backoff Delay]
        WAIT[Wait with<br/>Jitter]
    end

    subgraph Outcomes["Final Outcome"]
        OK[Success<br/>Return Result]
        DLQ[Move to DLQ<br/>dlq:queue_name]
    end

    JOB --> ATT
    ATT -->|Attempt N| EXEC
    ATT -->|Max Exceeded| DLQ

    EXEC --> CHK
    CHK -->|Yes| OK
    CHK -->|No| CALC

    CALC --> WAIT
    WAIT --> ATT

    style OK fill:#76B900,color:#fff
    style DLQ fill:#E74856,color:#fff
```

</details>

### Exponential Backoff Algorithm

The [RetryConfig](../../backend/services/retry_handler.py) at line 64 configures backoff behavior:

```python
# backend/services/retry_handler.py:64
@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True

    def get_delay(self, attempt: int) -> float:
        """Calculate delay: base * (exponential_base ^ (attempt - 1))"""
        delay = self.base_delay_seconds * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay_seconds)
        if self.jitter:
            jitter_amount = delay * 0.25 * random.random()
            delay = delay + jitter_amount
        return delay
```

### Backoff Timing Example

| Attempt | Base Delay  | With Jitter (0-25%) |
| ------- | ----------- | ------------------- |
| 1       | 1.0s        | 1.0s - 1.25s        |
| 2       | 2.0s        | 2.0s - 2.5s         |
| 3       | 4.0s        | 4.0s - 5.0s         |
| 4       | 8.0s        | 8.0s - 10.0s        |
| 5       | 16.0s       | 16.0s - 20.0s       |
| 6+      | 30.0s (max) | 30.0s - 37.5s       |

---

## Dead-Letter Queue (DLQ) Management

Jobs that exhaust all retry attempts are moved to dead-letter queues for manual inspection and reprocessing.

### DLQ Architecture

![Dead-letter queue architecture showing processing queues (detection_queue, analysis_queue) flowing through workers to the retry handler, with failed jobs moving to DLQ storage (dlq:detection_queue, dlq:analysis_queue) and the DLQ management API providing inspection, requeue, and clear operations](../images/resilience/dlq-architecture.svg)

_DLQ system architecture with queue workers, retry handling, and management API for failed job recovery._

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
flowchart TB
    subgraph ProcessingQueues["Processing Queues"]
        DQ[detection_queue]
        AQ[analysis_queue]
    end

    subgraph Workers["Queue Workers"]
        DW[DetectionQueueWorker]
        AW[AnalysisQueueWorker]
    end

    subgraph RetryLayer["Retry Handler"]
        RH[RetryHandler<br/>max_retries=3]
    end

    subgraph DLQs["Dead Letter Queues"]
        DLQ1[dlq:detection_queue]
        DLQ2[dlq:analysis_queue]
    end

    subgraph Management["DLQ Management API"]
        API[/api/dlq/*]
        INSPECT[Inspect Jobs]
        REQUEUE[Requeue Jobs]
        CLEAR[Clear Queue]
    end

    DQ --> DW
    AQ --> AW
    DW --> RH
    AW --> RH

    RH -->|Exhausted| DLQ1
    RH -->|Exhausted| DLQ2

    API --> INSPECT
    API --> REQUEUE
    API --> CLEAR

    DLQ1 -.->|Manual| REQUEUE
    DLQ2 -.->|Manual| REQUEUE
    REQUEUE -.->|Return to| DQ
    REQUEUE -.->|Return to| AQ

    style DLQ1 fill:#E74856,color:#fff
    style DLQ2 fill:#E74856,color:#fff
    style API fill:#3B82F6,color:#fff
```

</details>

### DLQ Job Format

Jobs in the DLQ include failure metadata:

```json
{
  "original_job": {
    "camera_id": "front_door",
    "file_path": "/export/foscam/front_door/image_001.jpg",
    "timestamp": "2024-01-15T10:30:00.000000"
  },
  "error": "Connection refused: YOLO26 service unavailable",
  "attempt_count": 3,
  "first_failed_at": "2024-01-15T10:30:01.000000",
  "last_failed_at": "2024-01-15T10:30:15.000000",
  "queue_name": "detection_queue"
}
```

### DLQ Statistics

The [DLQStats](../../backend/services/retry_handler.py) dataclass at line 175:

```python
# backend/services/retry_handler.py:175
@dataclass
class DLQStats:
    """Statistics about dead-letter queues."""

    detection_queue_count: int = 0
    analysis_queue_count: int = 0
    total_count: int = 0
```

### DLQ API Endpoints

| Endpoint                        | Method | Description                 |
| ------------------------------- | ------ | --------------------------- |
| `/api/dlq/stats`                | GET    | Get DLQ statistics          |
| `/api/dlq/{queue_name}`         | GET    | List jobs in a DLQ          |
| `/api/dlq/{queue_name}/requeue` | POST   | Move job back to processing |
| `/api/dlq/{queue_name}`         | DELETE | Clear all jobs in DLQ       |

---

## Service Health Monitoring

The [ServiceHealthMonitor](../../backend/services/health_monitor.py) at line 44 continuously monitors external services and orchestrates automatic recovery.

### Health Check Flow

![Health Check Flow](../images/resilience/health-check-flow.svg)

_Service health monitoring flow showing monitored services, state transitions, and recovery actions._

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
flowchart TB
    subgraph Monitor["ServiceHealthMonitor"]
        LOOP[Health Check Loop<br/>Every 15s]
    end

    subgraph Services["Monitored Services"]
        S1[YOLO26<br/>GET /health]
        S2[Nemotron<br/>GET /health]
        S3[Redis<br/>PING]
    end

    subgraph States["Service States"]
        HEALTHY[healthy<br/>Normal operation]
        UNHEALTHY[unhealthy<br/>Health check failed]
        RESTARTING[restarting<br/>Restart in progress]
        FAILED[failed<br/>Max retries exceeded]
    end

    subgraph Recovery["Recovery Actions"]
        BACKOFF[Exponential<br/>Backoff]
        RESTART[Restart<br/>Service]
        BROADCAST[WebSocket<br/>Broadcast]
    end

    LOOP --> S1
    LOOP --> S2
    LOOP --> S3

    S1 & S2 & S3 -->|OK| HEALTHY
    S1 & S2 & S3 -->|Fail| UNHEALTHY

    UNHEALTHY --> BACKOFF
    BACKOFF --> RESTART
    RESTART -->|Success| HEALTHY
    RESTART -->|Fail| RESTARTING
    RESTARTING -->|Max Retries| FAILED

    HEALTHY --> BROADCAST
    UNHEALTHY --> BROADCAST
    FAILED --> BROADCAST

    style HEALTHY fill:#76B900,color:#fff
    style UNHEALTHY fill:#FFB800,color:#000
    style FAILED fill:#E74856,color:#fff
    style RESTARTING fill:#3B82F6,color:#fff
```

</details>

### Health Monitor Implementation

```python
# backend/services/health_monitor.py:44
class ServiceHealthMonitor:
    """Monitors service health and orchestrates automatic recovery.

    Status values:
        - healthy: Service responding normally
        - unhealthy: Health check failed
        - restarting: Restart in progress
        - restart_failed: Restart attempt failed
        - failed: Max retries exceeded, giving up
    """

    def __init__(
        self,
        manager: ServiceManager,
        services: list[ServiceConfig],
        broadcaster: EventBroadcaster | None = None,
        check_interval: float = 15.0,
    ) -> None:
        self._manager = manager
        self._services = services
        self._broadcaster = broadcaster
        self._check_interval = check_interval
        # ...
```

### Recovery Backoff Strategy

Recovery attempts use exponential backoff to avoid overwhelming recovering services:

| Attempt | Backoff Delay | Formula              |
| ------- | ------------- | -------------------- |
| 1       | 5s            | `backoff_base * 2^0` |
| 2       | 10s           | `backoff_base * 2^1` |
| 3       | 20s           | `backoff_base * 2^2` |
| 4       | 40s           | `backoff_base * 2^3` |
| 5       | (Give up)     | Max retries exceeded |

---

## Graceful Degradation

When services are unavailable, the system degrades gracefully rather than failing completely.

### Degradation Modes

![Graceful Degradation](../images/resilience/graceful-degradation.svg)

_Graceful degradation modes showing normal operation, failure scenarios, and degraded behaviors._

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
flowchart TB
    subgraph Normal["Normal Operation"]
        N1[Full AI Pipeline]
        N2[Real-time Events]
        N3[Risk Scoring]
    end

    subgraph Degraded["Degraded Modes"]
        D1[Detection Only<br/>No LLM Analysis]
        D2[Queue Buffering<br/>Service Recovery]
        D3[Fallback Risk<br/>Score: 50, Medium]
    end

    subgraph Failed["Failure Scenarios"]
        F1[YOLO26<br/>Unavailable]
        F2[Nemotron<br/>Unavailable]
        F3[Redis<br/>Unavailable]
    end

    F1 -->|Skip Detection| D2
    F2 -->|Use Fallback| D3
    F3 -->|Fail Open| D1

    N1 --> F1
    N1 --> F2
    N1 --> F3

    style Normal fill:#76B900,color:#fff
    style Degraded fill:#FFB800,color:#000
    style Failed fill:#E74856,color:#fff
```

</details>

### Degradation Behavior by Component

| Component      | Failure Mode | Degradation Behavior                                 |
| -------------- | ------------ | ---------------------------------------------------- |
| **YOLO26**     | Unreachable  | DetectorClient returns empty list, detection skipped |
| **Nemotron**   | Unreachable  | NemotronAnalyzer returns default risk (50, medium)   |
| **Redis**      | Unreachable  | Deduplication fails open (allows processing)         |
| **Redis**      | Pub/sub down | WebSocket updates unavailable                        |
| **PostgreSQL** | Unreachable  | Full system failure (critical dependency)            |

### Fallback Risk Assessment

When Nemotron is unavailable, the system uses a fallback risk assessment:

```python
# backend/services/nemotron_analyzer.py (within analyze_batch)
# Create fallback risk data when LLM is unavailable
risk_data = {
    "risk_score": 50,
    "risk_level": "medium",
    "summary": "Analysis unavailable - LLM service error",
    "reasoning": "Failed to analyze detections due to service error",
}
```

---

## Recovery Strategies

### Automatic Recovery Sequence

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
sequenceDiagram
    participant HM as HealthMonitor
    participant SVC as External Service
    participant SM as ServiceManager
    participant WS as WebSocket

    Note over HM: Check interval: 15s
    HM->>SVC: Health check
    SVC--xHM: Timeout/Error

    HM->>WS: Broadcast "unhealthy"

    loop Retry with backoff
        HM->>HM: Calculate backoff (5s * 2^n)
        HM->>HM: Wait backoff period
        HM->>WS: Broadcast "restarting"
        HM->>SM: Restart service
        SM->>SVC: docker restart / systemctl restart
        HM->>HM: Wait 2s for startup
        HM->>SVC: Health check
        alt Healthy
            SVC-->>HM: OK
            HM->>WS: Broadcast "healthy"
        else Still Unhealthy
            SVC--xHM: Error
            Note over HM: Increment retry count
        end
    end

    alt Max retries exceeded
        HM->>WS: Broadcast "failed"
        Note over HM: Manual intervention required
    end
```

</details>

### Service Manager Strategies

The system supports different restart strategies via the ServiceManager interface:

| Strategy               | Implementation                        | Use Case                     |
| ---------------------- | ------------------------------------- | ---------------------------- |
| `ShellServiceManager`  | Shell commands (`systemctl`, scripts) | Development, native services |
| `DockerServiceManager` | Docker CLI (`docker restart`)         | Production containers        |
| `PodmanServiceManager` | Podman CLI (`podman restart`)         | Podman deployments           |

---

## Configuration Reference

### Circuit Breaker Settings

| Environment Variable                  | Default | Description              |
| ------------------------------------- | ------- | ------------------------ |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD`   | 5       | Failures before opening  |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT`    | 30      | Seconds before half-open |
| `CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS` | 3       | Max test calls           |
| `CIRCUIT_BREAKER_SUCCESS_THRESHOLD`   | 2       | Successes to close       |

### Retry Handler Settings

| Environment Variable     | Default | Description             |
| ------------------------ | ------- | ----------------------- |
| `RETRY_MAX_RETRIES`      | 3       | Maximum retry attempts  |
| `RETRY_BASE_DELAY`       | 1.0     | Initial delay (seconds) |
| `RETRY_MAX_DELAY`        | 30.0    | Maximum delay (seconds) |
| `RETRY_EXPONENTIAL_BASE` | 2.0     | Backoff multiplier      |

### Health Monitor Settings

| Environment Variable    | Default | Description              |
| ----------------------- | ------- | ------------------------ |
| `HEALTH_CHECK_INTERVAL` | 15.0    | Check interval (seconds) |
| `SERVICE_MAX_RETRIES`   | 5       | Max restart attempts     |
| `SERVICE_BACKOFF_BASE`  | 5.0     | Initial restart backoff  |

---

## Image Generation Prompts

### Prompt: Resilience Architecture Overview

**Dimensions:** 800x1200 (vertical 2:3)

```
Technical illustration of a resilience system architecture,
showing layered defense with circuit breakers, retry logic, and health monitoring.

Visual elements:
- Top layer: incoming requests represented as flowing data streams
- Middle layer: circuit breaker icons (open/closed switches) with state indicators
- Retry layer: circular arrows with backoff timing indicators
- Bottom layer: dead-letter queue as a secure vault/buffer
- Side panel: health monitor with heartbeat line and status indicators

Color scheme:
- Dark background #121212
- NVIDIA green #76B900 for healthy/success states
- Red #E74856 for failures and DLQ
- Yellow #FFB800 for warning/half-open states
- Blue #3B82F6 for external services

Style: Isometric technical diagram, clean lines, glowing data paths, vertical orientation
No text overlays
```

### Prompt: Circuit Breaker State Machine

**Dimensions:** 800x1000 (vertical)

```
Technical illustration of a circuit breaker state machine,
showing three states: Closed, Open, and Half-Open.

Visual elements:
- Three interconnected circular nodes representing states
- Arrows showing state transitions with trigger conditions
- CLOSED state: green glow, electricity flowing through
- OPEN state: red glow, broken connection, barrier
- HALF_OPEN state: yellow glow, partial connection, testing probe

Background: Dark #121212 with subtle grid pattern
Accent lighting: State-appropriate colors (green/red/yellow)
Style: Modern technical diagram, glowing circuit aesthetic, vertical layout
No text overlays
```

---

## WebSocket Circuit Breaker and Degraded Mode

The system includes a dedicated WebSocket circuit breaker pattern for real-time connection resilience. This provides automatic recovery when Redis pub/sub experiences failures and graceful degradation when recovery fails.

### Architecture Overview

![WebSocket Circuit Breaker Architecture](../images/resilience/websocket-circuit-breaker.svg)

_WebSocket circuit breaker architecture showing backend services, Redis pub/sub, and frontend clients._

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
flowchart TB
    subgraph Backend["Backend Services"]
        SB[SystemBroadcaster<br/>Port: /ws/system]
        EB[EventBroadcaster<br/>Port: /ws/events]
        CB1[WebSocketCircuitBreaker<br/>system_broadcaster]
        CB2[WebSocketCircuitBreaker<br/>event_broadcaster]
    end

    subgraph Redis["Redis Pub/Sub"]
        CH1[system_status channel]
        CH2[security_events channel]
    end

    subgraph Frontend["Frontend Clients"]
        WS[useWebSocket Hook]
        WSM[WebSocketManager<br/>Connection Deduplication]
    end

    SB --> CB1
    EB --> CB2
    CB1 --> CH1
    CB2 --> CH2
    CH1 -.->|Subscribe| SB
    CH2 -.->|Subscribe| EB

    SB -->|Broadcast| WS
    EB -->|Broadcast| WS
    WS --> WSM

    style CB1 fill:#FFB800,color:#000
    style CB2 fill:#FFB800,color:#000
    style WSM fill:#3B82F6,color:#fff
```

</details>

### WebSocket Circuit Breaker States

The [WebSocketCircuitBreaker](../../backend/core/websocket_circuit_breaker.py) implements the circuit breaker pattern specifically for WebSocket broadcaster services.

| State         | Description                                             | Behavior                                         |
| ------------- | ------------------------------------------------------- | ------------------------------------------------ |
| **CLOSED**    | Normal operation, WebSocket operations proceed normally | All broadcasts pass through                      |
| **OPEN**      | Too many failures, operations blocked to allow recovery | Broadcasts are rejected immediately              |
| **HALF_OPEN** | Testing recovery, limited operations allowed            | Single test operation allowed per recovery cycle |

### State Diagram

_Note: The WebSocket circuit breaker state diagram is included in the architecture overview diagram above._

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
stateDiagram-v2
    [*] --> CLOSED: Initial State

    CLOSED --> OPEN: failures >= threshold (5)
    OPEN --> HALF_OPEN: recovery_timeout (30s) elapsed
    HALF_OPEN --> CLOSED: success_threshold (1) met
    HALF_OPEN --> OPEN: any failure

    CLOSED: Normal Operation
    CLOSED: WebSocket broadcasts pass through
    CLOSED: Track consecutive failures
    CLOSED: Reset failure count on success

    OPEN: Circuit Tripped
    OPEN: Broadcasts rejected immediately
    OPEN: Waiting for recovery timeout
    OPEN: Degraded mode notification sent

    HALF_OPEN: Recovery Testing
    HALF_OPEN: Single test operation allowed
    HALF_OPEN: Track success/failure
    HALF_OPEN: Careful service probing
```

</details>

### Configuration

Both [SystemBroadcaster](../../backend/services/system_broadcaster.py) and [EventBroadcaster](../../backend/services/event_broadcaster.py) use the following circuit breaker configuration:

| Parameter             | Default                   | Description                                    |
| --------------------- | ------------------------- | ---------------------------------------------- |
| `failure_threshold`   | 5 (MAX_RECOVERY_ATTEMPTS) | Consecutive failures before opening circuit    |
| `recovery_timeout`    | 30.0s                     | Wait time before transitioning to HALF_OPEN    |
| `half_open_max_calls` | 1                         | Max calls allowed in HALF_OPEN state           |
| `success_threshold`   | 1                         | Successes needed in HALF_OPEN to close circuit |

### Backend: Broadcaster Integration

Both EventBroadcaster and SystemBroadcaster integrate the WebSocketCircuitBreaker for pub/sub listener resilience:

```python
# backend/services/system_broadcaster.py
from backend.core.websocket_circuit_breaker import WebSocketCircuitBreaker

class SystemBroadcaster:
    MAX_RECOVERY_ATTEMPTS = 5

    def __init__(self, ...):
        self._circuit_breaker = WebSocketCircuitBreaker(
            failure_threshold=self.MAX_RECOVERY_ATTEMPTS,
            recovery_timeout=30.0,
            half_open_max_calls=1,
            success_threshold=1,
            name="system_broadcaster",
        )
        self._is_degraded = False

    def is_degraded(self) -> bool:
        """Check if the broadcaster is in degraded mode."""
        return self._is_degraded

    def get_circuit_state(self) -> WebSocketCircuitState:
        """Get current circuit breaker state."""
        return self._circuit_breaker.get_state()
```

### Degraded Mode

When the circuit breaker opens and recovery fails, the broadcaster enters **degraded mode**:

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
sequenceDiagram
    participant Redis as Redis Pub/Sub
    participant CB as Circuit Breaker
    participant SB as SystemBroadcaster
    participant WS as WebSocket Clients

    Note over Redis: Redis connection fails

    loop Recovery Attempts (1-5)
        SB->>Redis: Attempt reconnect
        Redis--xSB: Connection failed
        SB->>CB: record_failure()
        CB->>CB: failure_count++
    end

    CB->>CB: failure_count >= 5
    CB->>SB: is_call_permitted() = false
    SB->>SB: Enter degraded mode
    SB->>WS: Broadcast service_status: degraded

    Note over SB: Manual restart required
```

</details>

#### Degraded Mode Behavior

1. **`is_degraded()` method** - Returns `True` when all recovery attempts are exhausted
2. **Client notification** - Connected clients receive a `service_status` message:
   ```json
   {
     "type": "service_status",
     "data": {
       "service": "system_broadcaster",
       "status": "degraded",
       "message": "System status broadcasting is degraded. Updates may be delayed or unavailable.",
       "circuit_state": "open"
     }
   }
   ```
3. **Graceful handling** - WebSocket connections are still accepted, but real-time broadcasts may be delayed or unavailable
4. **CRITICAL logging** - Operator alert logged for manual intervention

### Recovery Sequence

The broadcaster attempts automatic recovery with exponential backoff:

![Recovery Flow](../images/resilience/recovery-flow.svg)

_Broadcaster recovery flow showing failure detection, recovery attempts, circuit breaker check, and outcomes._

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
flowchart TB
    subgraph Failure["Failure Detection"]
        F1[Redis Connection Error]
        F2[Pub/Sub Listener Dies]
    end

    subgraph Recovery["Recovery Attempts"]
        R1{Attempt < 5?}
        R2[Record Failure]
        R3[Exponential Backoff<br/>1s, 2s, 4s, 8s...]
        R4[Reset Pub/Sub Connection]
        R5[Restart Listener Task]
    end

    subgraph CircuitBreaker["Circuit Breaker Check"]
        CB{is_call_permitted?}
        CB_BLOCK[Block Recovery<br/>Circuit OPEN]
    end

    subgraph Outcome["Outcome"]
        SUCCESS[Recovery Success<br/>Reset Counters]
        DEGRADED[Enter Degraded Mode<br/>Broadcast Status]
    end

    F1 --> R2
    F2 --> R2
    R2 --> CB

    CB -->|Yes| R1
    CB -->|No| CB_BLOCK --> DEGRADED

    R1 -->|Yes| R3 --> R4 --> R5
    R1 -->|No| DEGRADED

    R5 -->|Success| SUCCESS
    R5 -->|Failure| R2

    style DEGRADED fill:#E74856,color:#fff
    style SUCCESS fill:#76B900,color:#fff
    style CB_BLOCK fill:#FFB800,color:#000
```

</details>

### Frontend: Client-Side Circuit Breaker Pattern

The frontend implements its own circuit breaker-like behavior through the reconnection logic in `webSocketManager.ts`. While not a traditional circuit breaker class, the `maxReconnectAttempts` mechanism provides equivalent protection:

- **Closed State (equivalent):** Normal connection, reset on successful open
- **Open State (equivalent):** `hasExhaustedRetries = true`, no more connection attempts
- **Half-Open State (equivalent):** Each reconnection attempt tests if the server is available

This approach is more appropriate for client-side WebSocket connections where:

1. The client cannot "block" operations like a backend service can
2. The primary failure mode is disconnection, not request failures
3. User feedback (connection status) is more important than request throttling

#### Frontend Circuit Breaker State Machine

![Frontend State Machine](../images/resilience/frontend-state-machine.svg)

_Frontend circuit breaker state machine showing Connected, Reconnecting, and Exhausted states._

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
stateDiagram-v2
    [*] --> Connected: Initial connect()

    Connected --> Reconnecting: onClose event
    Connected: isConnected = true
    Connected: hasExhaustedRetries = false
    Connected: reconnectAttempts = 0

    Reconnecting --> Connected: onOpen event
    Reconnecting --> Reconnecting: attempt < maxReconnectAttempts
    Reconnecting --> Exhausted: attempt >= maxReconnectAttempts
    Reconnecting: isConnected = false
    Reconnecting: Exponential backoff + jitter
    Reconnecting: reconnectAttempts++

    Exhausted --> Connected: Manual connect() call
    Exhausted: hasExhaustedRetries = true
    Exhausted: onMaxRetriesExhausted() called
    Exhausted: No automatic reconnection
```

</details>

#### WebSocket Manager Architecture

The [WebSocketManager](../../frontend/src/hooks/webSocketManager.ts) provides connection deduplication and automatic reconnection:

![WebSocket Manager Architecture](../images/resilience/websocket-manager.svg)

_WebSocket Manager architecture showing React components, hook, manager singleton, and managed connection._

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
flowchart TB
    subgraph Components["React Components"]
        C1[Dashboard]
        C2[EventFeed]
        C3[SystemStatus]
    end

    subgraph Hook["useWebSocket Hook"]
        H[useWebSocket<br/>Options & Callbacks]
    end

    subgraph Manager["WebSocketManager Singleton"]
        M[Connection Pool]
        SUB[Subscribers Map<br/>Reference Counting]
    end

    subgraph Connection["Managed Connection"]
        WS[WebSocket Instance]
        RT[Reconnect Logic<br/>Exponential Backoff]
        HB[Heartbeat Handler<br/>Ping/Pong]
    end

    C1 & C2 & C3 --> H
    H --> M
    M --> SUB --> WS
    WS --> RT
    WS --> HB

    style M fill:#3B82F6,color:#fff
```

</details>

#### Client Reconnection Configuration

```typescript
// frontend/src/hooks/useWebSocket.ts
export interface WebSocketOptions {
  url: string;
  reconnect?: boolean; // Default: true
  reconnectInterval?: number; // Default: 1000ms (base interval)
  reconnectAttempts?: number; // Default: 5 (max attempts)
  connectionTimeout?: number; // Default: 10000ms
  autoRespondToHeartbeat?: boolean; // Default: true
  onMaxRetriesExhausted?: () => void; // Called when max attempts reached
}
```

#### Exponential Backoff with Jitter

```typescript
// frontend/src/hooks/webSocketManager.ts
function calculateBackoffDelay(
  attempt: number,
  baseInterval: number,
  maxInterval: number = 30000
): number {
  const exponentialDelay = baseInterval * Math.pow(2, attempt);
  const cappedDelay = Math.min(exponentialDelay, maxInterval);
  const jitter = Math.random() * 0.25 * cappedDelay;
  return Math.floor(cappedDelay + jitter);
}
```

| Attempt | Base Delay | Exponential | Capped  | With Jitter (0-25%) |
| ------- | ---------- | ----------- | ------- | ------------------- |
| 0       | 1000ms     | 1000ms      | 1000ms  | 1000-1250ms         |
| 1       | 1000ms     | 2000ms      | 2000ms  | 2000-2500ms         |
| 2       | 1000ms     | 4000ms      | 4000ms  | 4000-5000ms         |
| 3       | 1000ms     | 8000ms      | 8000ms  | 8000-10000ms        |
| 4       | 1000ms     | 16000ms     | 16000ms | 16000-20000ms       |
| 5+      | 1000ms     | 32000ms+    | 30000ms | 30000-37500ms       |

#### Client State Tracking

The `useWebSocket` hook exposes reconnection state:

```typescript
export interface UseWebSocketReturn {
  isConnected: boolean; // Current connection status
  hasExhaustedRetries: boolean; // True if max attempts reached
  reconnectCount: number; // Current retry attempt count
  lastHeartbeat: Date | null; // Timestamp of last server heartbeat
  connect: () => void; // Manual reconnect trigger
  disconnect: () => void; // Manual disconnect
}
```

### End-to-End Resilience Flow

<details>
<summary>Mermaid source (click to expand)</summary>

```mermaid
sequenceDiagram
    participant Client as Frontend Client
    participant WSM as WebSocketManager
    participant Backend as Backend (FastAPI)
    participant SB as SystemBroadcaster
    participant CB as Circuit Breaker
    participant Redis as Redis

    Note over Redis: Redis goes offline

    SB->>Redis: Pub/Sub subscribe
    Redis--xSB: Connection lost
    SB->>CB: record_failure()

    loop Recovery (up to 5 attempts)
        SB->>Redis: Reconnect attempt
        Redis--xSB: Still unavailable
        SB->>CB: record_failure()
    end

    CB->>SB: is_call_permitted() = false
    SB->>SB: _is_degraded = true
    SB->>Backend: Broadcast degraded status
    Backend->>Client: service_status: degraded

    Note over Client: Client shows degraded banner

    Client->>WSM: Connection lost
    WSM->>WSM: Start reconnection

    loop Client Reconnection (up to 5 attempts)
        WSM->>Backend: WebSocket connect
        Backend-->>WSM: Connection established
        Note over WSM: onClose triggered (backend may drop)
        WSM->>WSM: Exponential backoff
    end

    alt Max Retries Exceeded
        WSM->>Client: onMaxRetriesExhausted()
        Note over Client: Show "Connection lost" UI
    else Redis Recovers
        Redis->>SB: Connection restored
        SB->>CB: record_success()
        CB->>SB: is_call_permitted() = true
        SB->>SB: _is_degraded = false
        SB->>Backend: Resume broadcasting
        Backend->>Client: service_status: healthy
    end
```

</details>

### Monitoring and Observability

#### Backend Metrics

The circuit breaker tracks metrics via `get_metrics()` and `get_status()`:

| Metric              | Description                              | API Endpoint                    |
| ------------------- | ---------------------------------------- | ------------------------------- |
| `failure_count`     | Consecutive failures since last success  | `GET /api/system/health/ready`  |
| `success_count`     | Consecutive successes in HALF_OPEN state | Internal monitoring             |
| `total_failures`    | Total failures recorded                  | Prometheus metrics (if enabled) |
| `total_successes`   | Total successes recorded                 | Prometheus metrics (if enabled) |
| `last_failure_time` | Timestamp of last failure (monotonic)    | Circuit breaker status          |
| `last_state_change` | Timestamp of last state transition       | Circuit breaker status          |
| `opened_at`         | Timestamp when circuit was last opened   | Circuit breaker status          |

#### Health Check Integration

```python
# Check broadcaster health in health endpoints
broadcaster = get_system_broadcaster_sync()
if broadcaster.is_degraded():
    return {"status": "degraded", "reason": "WebSocket broadcasting unavailable"}
```

#### Client-Side Monitoring

```typescript
// React component monitoring example
const { isConnected, hasExhaustedRetries, reconnectCount, lastHeartbeat } = useWebSocket({
  url: '/ws/system',
  onMaxRetriesExhausted: () => {
    console.error('WebSocket connection failed after max retries');
    showConnectionErrorBanner();
  },
  onHeartbeat: () => {
    updateLastHeartbeatIndicator();
  },
});
```

### Supervisor Task (EventBroadcaster)

The EventBroadcaster includes an additional supervision layer that monitors listener health:

```python
# backend/services/event_broadcaster.py
async def _supervise_listener(self) -> None:
    """Supervision task that monitors listener health and restarts if needed."""
    while self._is_listening:
        await asyncio.sleep(self.SUPERVISION_INTERVAL)  # 30 seconds

        listener_alive = self._listener_task is not None and not self._listener_task.done()

        if listener_alive:
            self._circuit_breaker.record_success()
            self._recovery_attempts = 0
        elif self._is_listening:
            # Listener died - attempt recovery
            if self._circuit_breaker.is_call_permitted():
                await self._restart_listener()
            else:
                self._enter_degraded_mode()
```

### Backend vs Frontend Circuit Breaker Comparison

| Aspect                  | Backend (WebSocketCircuitBreaker)               | Frontend (WebSocketManager)                 |
| ----------------------- | ----------------------------------------------- | ------------------------------------------- |
| **Implementation**      | Dedicated class with explicit states            | Reconnection logic with attempt counter     |
| **State Tracking**      | `WebSocketCircuitState` enum (CLOSED/OPEN/HALF) | Derived from `reconnectAttempts` counter    |
| **Failure Detection**   | Explicit `record_failure()` calls               | `onClose` event triggers attempt increment  |
| **Recovery Testing**    | HALF_OPEN state with limited calls              | Each reconnect attempt is a recovery test   |
| **Blocking Behavior**   | Rejects operations when OPEN                    | Stops automatic reconnection when exhausted |
| **User Notification**   | `service_status` WebSocket message              | `onMaxRetriesExhausted` callback            |
| **Manual Reset**        | `reset()` method                                | `connect()` method resets attempt counter   |
| **Timeout-based Reset** | Yes (`recovery_timeout` triggers HALF_OPEN)     | No (manual `connect()` required)            |
| **Thread Safety**       | `asyncio.Lock` for async contexts               | Single-threaded JavaScript (not needed)     |
| **Metrics**             | `get_metrics()` with counters and timestamps    | `getConnectionState()` with basic state     |

### Configuration Summary

| Component      | Setting                 | Default | Description                      |
| -------------- | ----------------------- | ------- | -------------------------------- |
| **Backend CB** | `failure_threshold`     | 5       | Failures before circuit opens    |
| **Backend CB** | `recovery_timeout`      | 30s     | Wait before HALF_OPEN transition |
| **Backend**    | `SUPERVISION_INTERVAL`  | 30s     | Listener health check interval   |
| **Frontend**   | `reconnectAttempts`     | 5       | Max client reconnection attempts |
| **Frontend**   | `reconnectInterval`     | 1000ms  | Base backoff interval            |
| **Frontend**   | `connectionTimeout`     | 10000ms | Connection establishment timeout |
| **Frontend**   | `maxInterval` (backoff) | 30000ms | Maximum backoff delay            |

### Manual Recovery

When the system enters degraded mode, manual intervention is required:

```bash
# Check container health
docker compose -f docker-compose.prod.yml ps

# Check Redis connectivity
docker compose -f docker-compose.prod.yml exec redis redis-cli ping

# Restart the backend service
docker compose -f docker-compose.prod.yml restart backend

# View broadcaster logs
docker compose -f docker-compose.prod.yml logs backend | grep -i "broadcaster\|circuit"
```

Look for these log patterns:

| Log Level    | Pattern                                        | Meaning                             |
| ------------ | ---------------------------------------------- | ----------------------------------- |
| **CRITICAL** | `EventBroadcaster has entered DEGRADED MODE`   | Requires manual restart             |
| **WARNING**  | `Circuit breaker is OPEN`                      | Recovery blocked, waiting for reset |
| **INFO**     | `Restarting pub/sub listener (attempt N/5)`    | Auto-recovery in progress           |
| **INFO**     | `transitioned HALF_OPEN -> CLOSED (recovered)` | Service successfully recovered      |

---

## Related Documentation

| Document                                                         | Purpose                                                                                               |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| [Resilience Patterns Guide](../developer/resilience-patterns.md) | Developer guide with code examples for circuit breakers, retry logic, and prompt injection prevention |
| [AI Pipeline](ai-pipeline.md)                                    | Detection and analysis flow                                                                           |
| [Real-Time](real-time.md)                                        | WebSocket and pub/sub architecture                                                                    |
| [Data Model](data-model.md)                                      | Database schema and relationships                                                                     |
| [Backend AGENTS.md](../../backend/services/AGENTS.md)            | Service implementation details                                                                        |
| [Frontend Hooks](frontend-hooks.md)                              | React hooks including useWebSocket                                                                    |
| [Backend Core](../../backend/core/AGENTS.md)                     | Core infrastructure including Redis                                                                   |

---

_This document describes the resilience architecture for the Home Security Intelligence system. For implementation details, see the source files referenced in the frontmatter._
