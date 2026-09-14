#!/bin/bash
# Architecture Documentation Image Generation Script
# Generates ~250 images across 14 architecture hubs (95 documents)
# Rate limited to 40 requests/minute (1.5s delay between requests)

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
IMAGE_BASE="$PROJECT_ROOT/docs/images/architecture"
SKILL_SCRIPT="$HOME/.claude/skills/nvidia-image-gen/scripts/generate_image.py"
RATE_LIMIT_DELAY=1.5
LOG_FILE="$PROJECT_ROOT/image_generation.log"

# Style constants
STYLE="dark background hex 1a1a2e, clean lines, subtle grid pattern, professional architectural diagram style, modern infographic aesthetic, no text labels, blue accent 4a90d9, green accent 50c878, orange accent ff9f43"

# Check for API key
if [[ -z "${NVIDIA_API_KEY:-}" ]] && [[ -z "${NVAPIKEY:-}" ]]; then
    echo "Error: NVIDIA_API_KEY or NVAPIKEY environment variable not set"
    echo "Run: source ~/.bashrc"
    exit 1
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# Create all hub directories
create_directories() {
    log "Creating image directories..."
    for hub in system-overview detection-pipeline ai-orchestration realtime-system \
               data-model api-reference resilience-patterns observability \
               background-services middleware frontend testing security dataflows; do
        mkdir -p "$IMAGE_BASE/$hub"
    done
}

# Generate a single image
generate_image() {
    local output_path="$1"
    local prompt="$2"
    local name=$(basename "$output_path")

    if [[ -f "$output_path" ]]; then
        warn "Skip (exists): $name"
        return 0
    fi

    info "Generating: $name"

    if uv run "$SKILL_SCRIPT" "$prompt" --output "$output_path" 2>>"$LOG_FILE"; then
        log "✓ $name"
        return 0
    else
        error "✗ $name"
        return 1
    fi
}

# Counter
COUNT=0
gen() {
    generate_image "$1" "$2"
    COUNT=$((COUNT + 1))
    sleep $RATE_LIMIT_DELAY
}

# Main image generation
generate_all() {
    # =========================================================================
    # SYSTEM OVERVIEW HUB (4 docs, ~18 images)
    # =========================================================================
    log "=== System Overview Hub (4 docs) ==="

    # README.md - Hero + conceptual
    gen "$IMAGE_BASE/system-overview/hero-system-overview.png" \
        "Technical illustration of home security AI system architecture, showing layered architecture with frontend dashboard at top, backend API server in middle, AI detection services cluster, database and Redis storage at bottom, connection lines between components, $STYLE, 1920x1080"
    gen "$IMAGE_BASE/system-overview/concept-three-tier.png" \
        "Infographic showing three tier architecture, presentation tier with React dashboard, application tier with FastAPI and workers, data tier with PostgreSQL and Redis, vertical layers, $STYLE"
    gen "$IMAGE_BASE/system-overview/concept-technology-stack.png" \
        "Infographic showing technology stack layers as horizontal bands, React TypeScript frontend layer, FastAPI Python backend layer, PostgreSQL Redis data layer, YOLO26 Nemotron AI layer at bottom, $STYLE"

    # deployment-topology.md
    gen "$IMAGE_BASE/system-overview/technical-deployment-topology.png" \
        "Technical diagram of Docker deployment, container boxes for each service, GPU passthrough arrow to AI containers, shared volumes, network connections, $STYLE"
    gen "$IMAGE_BASE/system-overview/flow-container-startup.png" \
        "Sequence diagram of container startup order, PostgreSQL first, Redis second, backend third, AI services fourth, frontend last, dependency arrows, $STYLE"
    gen "$IMAGE_BASE/system-overview/concept-gpu-passthrough.png" \
        "Conceptual diagram of GPU passthrough, host GPU connected through container runtime to AI container, CUDA libraries, model execution, $STYLE"

    # design-decisions.md
    gen "$IMAGE_BASE/system-overview/concept-llm-risk-scoring.png" \
        "Infographic explaining LLM-based risk scoring, detection batch as input, Nemotron brain analyzing, risk score 0-100 gauge output, $STYLE"
    gen "$IMAGE_BASE/system-overview/concept-batch-vs-realtime.png" \
        "Comparison diagram, real-time processing timeline on top, batch processing with 90s windows on bottom, tradeoffs listed, $STYLE"
    gen "$IMAGE_BASE/system-overview/concept-single-user-local.png" \
        "Simple diagram showing single home with security system, no cloud dependency, local processing emphasis, $STYLE"

    # configuration.md
    gen "$IMAGE_BASE/system-overview/technical-config-hierarchy.png" \
        "Configuration hierarchy diagram, environment variables at top, config files middle, defaults at bottom, override arrows, $STYLE"
    gen "$IMAGE_BASE/system-overview/flow-config-loading.png" \
        "Flow diagram of config loading, read env vars, load yaml files, merge with defaults, validate schema, application config object, $STYLE"

    # =========================================================================
    # DETECTION PIPELINE HUB (6 docs, ~22 images)
    # =========================================================================
    log "=== Detection Pipeline Hub (6 docs) ==="

    # README.md - Hero + conceptual
    gen "$IMAGE_BASE/detection-pipeline/hero-detection-pipeline.png" \
        "Technical illustration of AI detection pipeline, camera icons on left, images flowing into YOLO26 model box, detection records emerging, flowing into batch aggregation funnel, $STYLE, 1920x1080"
    gen "$IMAGE_BASE/detection-pipeline/concept-pipeline-stages.png" \
        "Infographic showing pipeline stages, Ingest from cameras, Detect with YOLO26, Aggregate into batches, Analyze with LLM, Broadcast events, $STYLE"
    gen "$IMAGE_BASE/detection-pipeline/flow-end-to-end.png" \
        "Horizontal flow from camera upload through all pipeline stages to event broadcast, numbered steps, timing annotations, $STYLE"

    # file-watcher.md
    gen "$IMAGE_BASE/detection-pipeline/technical-file-watcher.png" \
        "Technical diagram of file watcher internals, watchdog observer watching folders, event debouncer with timer, file validator, Redis queue submitter, $STYLE"
    gen "$IMAGE_BASE/detection-pipeline/concept-debouncing.png" \
        "Timeline showing rapid file events coalesced into single trigger after debounce period, before and after visualization, $STYLE"
    gen "$IMAGE_BASE/detection-pipeline/flow-file-event-handling.png" \
        "Flow diagram from filesystem event through debounce through validation through queue submission, decision diamonds for invalid files, $STYLE"

    # detection-queue.md
    gen "$IMAGE_BASE/detection-pipeline/technical-detection-queue.png" \
        "Technical diagram of Redis queue as horizontal pipe, LPUSH arrow entering left, BRPOP arrow exiting right, depth gauge showing queue size, $STYLE"
    gen "$IMAGE_BASE/detection-pipeline/concept-queue-backpressure.png" \
        "Diagram showing queue filling up, backpressure signal to producers, producer slowdown, queue draining, $STYLE"
    gen "$IMAGE_BASE/detection-pipeline/flow-queue-consumer.png" \
        "Flow diagram of queue consumer loop, BRPOP wait, process item, acknowledge or retry on failure, loop back, $STYLE"

    # batch-aggregator.md
    gen "$IMAGE_BASE/detection-pipeline/concept-batch-windows.png" \
        "Timeline showing 90 second window with detection dots accumulating, 30 second idle timeout trigger, batch closure event, $STYLE"
    gen "$IMAGE_BASE/detection-pipeline/technical-batch-state.png" \
        "State diagram for batch, Created state, Active receiving detections, Closed on timeout or size limit, Queued for analysis, $STYLE"
    gen "$IMAGE_BASE/detection-pipeline/flow-batch-lifecycle.png" \
        "Flow diagram of batch lifecycle, first detection creates batch, timer starts, detections accumulate, timeout or limit triggers close, $STYLE"

    # analysis-queue.md
    gen "$IMAGE_BASE/detection-pipeline/technical-analysis-queue.png" \
        "Technical diagram of analysis queue, batch objects waiting, Nemotron consumer processing, event objects output, $STYLE"
    gen "$IMAGE_BASE/detection-pipeline/flow-analysis-processing.png" \
        "Flow diagram from batch dequeue through prompt construction through LLM call through event creation, $STYLE"

    # critical-paths.md
    gen "$IMAGE_BASE/detection-pipeline/concept-critical-paths.png" \
        "Diagram highlighting critical paths in red, file watcher to detection the most critical, secondary paths in yellow, $STYLE"
    gen "$IMAGE_BASE/detection-pipeline/technical-timeout-budgets.png" \
        "Budget allocation diagram, 500ms detection inference, 2s LLM analysis, 50ms database write, total budget breakdown, $STYLE"

    # =========================================================================
    # AI ORCHESTRATION HUB (6 docs, ~22 images)
    # =========================================================================
    log "=== AI Orchestration Hub (6 docs) ==="

    # README.md - Hero + conceptual
    gen "$IMAGE_BASE/ai-orchestration/hero-ai-orchestration.png" \
        "Technical illustration of AI orchestration, Nemotron brain icon in center analyzing detection batches on left, generating risk scores and event cards on right, neural network aesthetic, $STYLE, 1920x1080"
    gen "$IMAGE_BASE/ai-orchestration/concept-batch-to-event.png" \
        "Infographic showing detections as small squares grouping into larger batch rectangle, arrow to LLM brain, arrow to event card with risk score, $STYLE"
    gen "$IMAGE_BASE/ai-orchestration/flow-orchestration-overview.png" \
        "Overview flow from detection batches through model selection through inference through event creation, $STYLE"

    # nemotron-analyzer.md
    gen "$IMAGE_BASE/ai-orchestration/technical-nemotron-pipeline.png" \
        "Technical pipeline diagram, prompt construction box, API call arrow to Nemotron server, response parsing box, event creation box, sequential flow, $STYLE"
    gen "$IMAGE_BASE/ai-orchestration/concept-prompt-template.png" \
        "Infographic showing prompt template structure, system context section, detection data section, analysis instructions section, $STYLE"
    gen "$IMAGE_BASE/ai-orchestration/flow-llm-request-response.png" \
        "Flow diagram from prompt assembly through HTTP call to inference server through response parsing to structured output, $STYLE"
    gen "$IMAGE_BASE/ai-orchestration/concept-risk-scoring.png" \
        "Risk score gauge from 0-100, color gradient from green to red, example scenarios at different levels, $STYLE"

    # yolo26-client.md
    gen "$IMAGE_BASE/ai-orchestration/technical-yolo26-client.png" \
        "Technical diagram of YOLO26 client, connection pool, request formatting, image preprocessing, inference call, response parsing, $STYLE"
    gen "$IMAGE_BASE/ai-orchestration/flow-detection-inference.png" \
        "Flow diagram from image input through preprocessing through model inference through bbox extraction through detection record creation, $STYLE"
    gen "$IMAGE_BASE/ai-orchestration/concept-detection-outputs.png" \
        "Conceptual diagram showing detection outputs, bounding boxes overlaid on image, confidence scores, class labels, $STYLE"

    # model-zoo.md
    gen "$IMAGE_BASE/ai-orchestration/concept-model-zoo.png" \
        "Conceptual diagram of model zoo as collection of AI model boxes, license plate reader, face detector, OCR engine, connected to central router, $STYLE"
    gen "$IMAGE_BASE/ai-orchestration/technical-model-registry.png" \
        "Technical diagram of model registry, model metadata, version tracking, endpoint mapping, health status, $STYLE"

    # enrichment-pipeline.md
    gen "$IMAGE_BASE/ai-orchestration/flow-enrichment-pipeline.png" \
        "Flow diagram of enrichment, detection enters, type check, route to appropriate enricher, LPR or OCR or Face, merge enrichments back, $STYLE"
    gen "$IMAGE_BASE/ai-orchestration/concept-enrichment-types.png" \
        "Infographic showing enrichment types, license plate extraction, text recognition, face detection, metadata extraction, $STYLE"
    gen "$IMAGE_BASE/ai-orchestration/technical-enrichment-routing.png" \
        "Technical routing diagram, detection type as input, decision tree to enricher selection, enrichment result output, $STYLE"

    # fallback-strategies.md
    gen "$IMAGE_BASE/ai-orchestration/concept-fallback-chain.png" \
        "Chain diagram showing primary model, fallback model 1, fallback model 2, rule-based fallback, each with availability indicator, $STYLE"
    gen "$IMAGE_BASE/ai-orchestration/flow-fallback-execution.png" \
        "Flow diagram, try primary, on failure try fallback, cascade through fallbacks, final rule-based if all fail, $STYLE"
    gen "$IMAGE_BASE/ai-orchestration/technical-model-health.png" \
        "Dashboard-style diagram showing model health indicators, latency, error rate, availability, switching thresholds, $STYLE"

    # =========================================================================
    # REALTIME SYSTEM HUB (6 docs, ~20 images)
    # =========================================================================
    log "=== Realtime System Hub (6 docs) ==="

    # README.md - Hero + conceptual
    gen "$IMAGE_BASE/realtime-system/hero-realtime-system.png" \
        "Technical illustration of WebSocket system, central server hub radiating connection lines to multiple browser dashboard icons, pulsing data stream animations, $STYLE, 1920x1080"
    gen "$IMAGE_BASE/realtime-system/concept-pubsub-pattern.png" \
        "Infographic of pub sub pattern, publisher box on left, channel pipe in middle, multiple subscriber boxes on right receiving same message, fan-out arrows, $STYLE"
    gen "$IMAGE_BASE/realtime-system/flow-event-broadcast.png" \
        "Horizontal flow from event creation through Redis publish through WebSocket broadcaster to multiple connected client browsers, $STYLE"

    # websocket-server.md
    gen "$IMAGE_BASE/realtime-system/technical-websocket-server.png" \
        "Technical diagram of WebSocket server internals, connection manager tracking clients, message router, subscription registry, health checker, $STYLE"
    gen "$IMAGE_BASE/realtime-system/concept-connection-lifecycle.png" \
        "State diagram of connection lifecycle, handshake, connected, authenticated, subscribed, disconnected, states with transitions, $STYLE"
    gen "$IMAGE_BASE/realtime-system/flow-connection-handling.png" \
        "Flow diagram of new connection, upgrade request, accept connection, add to pool, send welcome, wait for messages, $STYLE"

    # event-broadcaster.md
    gen "$IMAGE_BASE/realtime-system/technical-broadcaster.png" \
        "Technical diagram of broadcaster, event input, subscription filter, connection lookup, parallel message dispatch, $STYLE"
    gen "$IMAGE_BASE/realtime-system/flow-broadcast-process.png" \
        "Flow diagram from event received through filter subscriptions through format message through send to each client, $STYLE"

    # subscription-manager.md
    gen "$IMAGE_BASE/realtime-system/technical-subscription-manager.png" \
        "Technical diagram of subscription manager, subscription registry data structure, add/remove operations, filter matching logic, $STYLE"
    gen "$IMAGE_BASE/realtime-system/concept-subscription-filters.png" \
        "Conceptual diagram showing subscription filters, by event type, by camera, by risk level, filter composition, $STYLE"

    # message-formats.md
    gen "$IMAGE_BASE/realtime-system/concept-message-types.png" \
        "Infographic of message types, event notification, connection control, heartbeat, error, each with JSON structure icon, $STYLE"
    gen "$IMAGE_BASE/realtime-system/technical-message-envelope.png" \
        "Technical diagram of message envelope structure, type field, timestamp, payload, metadata fields, $STYLE"

    # client-integration.md
    gen "$IMAGE_BASE/realtime-system/concept-reconnection.png" \
        "Conceptual diagram showing WebSocket connection states, connected active idle disconnected, exponential backoff curve for retry timing, message buffer cylinder, $STYLE"
    gen "$IMAGE_BASE/realtime-system/flow-client-reconnection.png" \
        "Flow diagram of client reconnection, detect disconnect, wait with backoff, attempt reconnect, on fail increase backoff, on success restore subscriptions, $STYLE"
    gen "$IMAGE_BASE/realtime-system/technical-client-state.png" \
        "State machine diagram for client connection, connecting connected disconnected reconnecting states, event triggers, $STYLE"

    # =========================================================================
    # DATA MODEL HUB (6 docs, ~20 images)
    # =========================================================================
    log "=== Data Model Hub (6 docs) ==="

    # README.md - Hero + conceptual
    gen "$IMAGE_BASE/data-model/hero-data-model.png" \
        "Technical illustration of dual storage architecture, PostgreSQL elephant icon on left, Redis diamond icon on right, data flowing between them, table schemas and key value structures, $STYLE, 1920x1080"
    gen "$IMAGE_BASE/data-model/concept-dual-storage.png" \
        "Infographic comparing PostgreSQL for persistent storage and Redis for ephemeral state, use cases for each, $STYLE"
    gen "$IMAGE_BASE/data-model/flow-data-routing.png" \
        "Flow diagram showing data routing decisions, persistent data to PostgreSQL, transient state to Redis, decision criteria, $STYLE"

    # core-entities.md
    gen "$IMAGE_BASE/data-model/technical-entity-relationships.png" \
        "Entity relationship diagram, Camera box connected to Detection box connected to Event box, junction tables, crow foot notation, $STYLE"
    gen "$IMAGE_BASE/data-model/technical-camera-table.png" \
        "Table schema diagram for cameras, columns with types, primary key, indexes, JSONB config column expansion, $STYLE"
    gen "$IMAGE_BASE/data-model/technical-detection-table.png" \
        "Table schema diagram for detections, columns, foreign key to camera, index on timestamp, JSONB metadata, $STYLE"
    gen "$IMAGE_BASE/data-model/technical-event-table.png" \
        "Table schema diagram for events, columns, risk score, related detections array, timestamps, $STYLE"

    # auxiliary-tables.md
    gen "$IMAGE_BASE/data-model/technical-auxiliary-tables.png" \
        "Diagram showing auxiliary tables, batch tracking, processing status, audit log, their relationships, $STYLE"

    # redis-data-structures.md
    gen "$IMAGE_BASE/data-model/concept-redis-structures.png" \
        "Conceptual diagram of Redis data structures, list for queues, hash for batch state, pub sub channels, with icons for each type, $STYLE"
    gen "$IMAGE_BASE/data-model/technical-redis-keys.png" \
        "Technical diagram showing Redis key namespace, queue keys, state keys, channel keys, key naming conventions, $STYLE"
    gen "$IMAGE_BASE/data-model/flow-redis-queue-operations.png" \
        "Flow diagram of queue operations, LPUSH to add, BRPOP to consume, LLEN to check depth, $STYLE"

    # indexes-and-performance.md
    gen "$IMAGE_BASE/data-model/technical-index-strategy.png" \
        "Technical diagram of indexing strategy, primary key index, timestamp range index, foreign key index, composite indexes, $STYLE"
    gen "$IMAGE_BASE/data-model/concept-query-patterns.png" \
        "Infographic showing common query patterns, by time range, by camera, by risk score, indexes that support each, $STYLE"

    # migrations.md
    gen "$IMAGE_BASE/data-model/flow-migration-lifecycle.png" \
        "Flow diagram of migration lifecycle, create migration, test locally, review, apply to staging, apply to production, $STYLE"
    gen "$IMAGE_BASE/data-model/concept-migration-safety.png" \
        "Infographic showing migration safety practices, backwards compatibility, rollback plan, zero downtime, $STYLE"

    # =========================================================================
    # API REFERENCE HUB (7 docs, ~22 images)
    # =========================================================================
    log "=== API Reference Hub (7 docs) ==="

    # README.md - Hero + conceptual
    gen "$IMAGE_BASE/api-reference/hero-api-reference.png" \
        "Technical illustration of REST API, central API gateway hub with endpoint groups radiating outward, Events Cameras Detections System domains, HTTP method badges, $STYLE, 1920x1080"
    gen "$IMAGE_BASE/api-reference/concept-api-domains.png" \
        "Infographic of four API domains as quadrants, Events with timeline icon, Cameras with video icon, Detections with AI icon, System with gear icon, CRUD operations listed, $STYLE"
    gen "$IMAGE_BASE/api-reference/flow-request-lifecycle.png" \
        "Flow diagram of API request lifecycle, client request, middleware processing, route handler, database query, response formatting, client response, $STYLE"

    # events-api.md
    gen "$IMAGE_BASE/api-reference/technical-events-endpoints.png" \
        "Technical diagram of events API endpoints, GET list, GET detail, POST create, PUT update, DELETE, with paths, $STYLE"
    gen "$IMAGE_BASE/api-reference/flow-event-query.png" \
        "Flow diagram of event query, parse filters, build query, execute with pagination, format response, return, $STYLE"

    # cameras-api.md
    gen "$IMAGE_BASE/api-reference/technical-cameras-endpoints.png" \
        "Technical diagram of cameras API endpoints, CRUD operations, configuration sub-endpoints, status endpoints, $STYLE"
    gen "$IMAGE_BASE/api-reference/flow-camera-registration.png" \
        "Flow diagram of camera registration, validate input, create record, setup watch directory, return camera object, $STYLE"

    # detections-api.md
    gen "$IMAGE_BASE/api-reference/technical-detections-endpoints.png" \
        "Technical diagram of detections API endpoints, list by camera, list by time range, get detail with image, $STYLE"
    gen "$IMAGE_BASE/api-reference/concept-detection-response.png" \
        "Infographic showing detection response structure, detection metadata, bounding box data, thumbnail URL, enrichments, $STYLE"

    # system-api.md
    gen "$IMAGE_BASE/api-reference/technical-system-endpoints.png" \
        "Technical diagram of system API endpoints, health check, GPU status, configuration, metrics export, $STYLE"
    gen "$IMAGE_BASE/api-reference/flow-health-check.png" \
        "Flow diagram of health check, check database, check Redis, check AI services, aggregate status, return health, $STYLE"

    # request-response-schemas.md
    gen "$IMAGE_BASE/api-reference/technical-schema-validation.png" \
        "Technical diagram of schema validation, Pydantic model, request parsing, validation rules, error response on fail, $STYLE"
    gen "$IMAGE_BASE/api-reference/concept-pagination.png" \
        "Conceptual diagram of cursor pagination, page boxes with prev next cursors, arrows showing navigation direction, total count display, $STYLE"
    gen "$IMAGE_BASE/api-reference/concept-response-envelope.png" \
        "Infographic showing response envelope structure, data field, metadata, pagination info, links section, $STYLE"

    # error-handling.md
    gen "$IMAGE_BASE/api-reference/technical-error-codes.png" \
        "Technical diagram mapping error types to HTTP status codes, 400 validation, 404 not found, 500 internal, error response structure, $STYLE"
    gen "$IMAGE_BASE/api-reference/flow-error-response.png" \
        "Flow diagram of error handling, exception caught, map to error response, log with context, return formatted error, $STYLE"

    # =========================================================================
    # RESILIENCE PATTERNS HUB (6 docs, ~22 images)
    # =========================================================================
    log "=== Resilience Patterns Hub (6 docs) ==="

    # README.md - Hero + conceptual
    gen "$IMAGE_BASE/resilience-patterns/hero-resilience-patterns.png" \
        "Technical illustration of resilience architecture, circuit breaker as shield, retry handler as spring, dead letter queue as safety net, protecting central service core, $STYLE, 1920x1080"
    gen "$IMAGE_BASE/resilience-patterns/concept-defense-layers.png" \
        "Concentric circles showing defense layers, retry at outer, circuit breaker middle, timeout inner, graceful degradation core, $STYLE"
    gen "$IMAGE_BASE/resilience-patterns/flow-failure-cascade.png" \
        "Flow diagram showing failure cascade prevention, failure occurs, retry absorbs transient, circuit prevents cascade, degradation maintains function, $STYLE"

    # circuit-breaker.md
    gen "$IMAGE_BASE/resilience-patterns/concept-circuit-breaker.png" \
        "State machine diagram for circuit breaker, Closed state green allowing traffic, Open state red blocking, Half Open state yellow testing, transition arrows with conditions, $STYLE"
    gen "$IMAGE_BASE/resilience-patterns/flow-circuit-states.png" \
        "Flow diagram of circuit state transitions, failures increment counter, threshold triggers open, timeout triggers half-open, success resets to closed, $STYLE"
    gen "$IMAGE_BASE/resilience-patterns/technical-circuit-config.png" \
        "Technical diagram showing circuit configuration, failure threshold, timeout duration, half-open test count, success threshold, $STYLE"

    # retry-handler.md
    gen "$IMAGE_BASE/resilience-patterns/technical-retry-backoff.png" \
        "Technical chart of exponential backoff, x axis time y axis delay, curve showing 1s 2s 4s 8s 16s progression, jitter variation bands, max cap line, $STYLE"
    gen "$IMAGE_BASE/resilience-patterns/flow-retry-logic.png" \
        "Flow diagram of retry logic, attempt operation, on failure check retryable, wait with backoff, retry or propagate, $STYLE"
    gen "$IMAGE_BASE/resilience-patterns/concept-jitter.png" \
        "Infographic explaining jitter, multiple clients without jitter synchronizing retries causing thundering herd, with jitter spreading retries, $STYLE"

    # dead-letter-queue.md
    gen "$IMAGE_BASE/resilience-patterns/technical-dlq-architecture.png" \
        "Technical diagram of dead letter queue, failed jobs stored with error context, manual retry interface, monitoring dashboard, $STYLE"
    gen "$IMAGE_BASE/resilience-patterns/flow-dlq-processing.png" \
        "Flow diagram from failed message through retry exhaustion through DLQ storage through manual review through reprocessing or discard, $STYLE"
    gen "$IMAGE_BASE/resilience-patterns/concept-dlq-monitoring.png" \
        "Infographic showing DLQ monitoring, queue depth metric, age of oldest message, failure categorization chart, $STYLE"

    # graceful-degradation.md
    gen "$IMAGE_BASE/resilience-patterns/concept-graceful-degradation.png" \
        "Stacked bar diagram showing degradation modes, Normal full features, Degraded reduced features, Minimal core only, Offline cached data, feature availability per mode, $STYLE"
    gen "$IMAGE_BASE/resilience-patterns/flow-degradation-decision.png" \
        "Flow diagram of degradation decision, health check, determine available services, select degradation level, configure feature flags, $STYLE"
    gen "$IMAGE_BASE/resilience-patterns/technical-feature-toggles.png" \
        "Technical diagram of feature toggles by degradation level, matrix of features vs levels, enabled disabled indicators, $STYLE"

    # health-monitoring.md
    gen "$IMAGE_BASE/resilience-patterns/technical-health-checks.png" \
        "Technical diagram of health check types, liveness probe, readiness probe, startup probe, check intervals and timeouts, $STYLE"
    gen "$IMAGE_BASE/resilience-patterns/flow-health-aggregation.png" \
        "Flow diagram of health aggregation, individual component checks, status aggregation logic, overall health determination, $STYLE"

    # =========================================================================
    # OBSERVABILITY HUB (6 docs, ~20 images)
    # =========================================================================
    log "=== Observability Hub (6 docs) ==="

    # README.md - Hero + conceptual
    gen "$IMAGE_BASE/observability/hero-observability.png" \
        "Technical illustration of observability stack, four pillars as columns, logging with document icon, metrics with chart icon, tracing with timeline icon, alerting with bell icon, Grafana dashboard at top, $STYLE, 1920x1080"
    gen "$IMAGE_BASE/observability/concept-four-pillars.png" \
        "Infographic of observability pillars, structured logging JSON format, Prometheus metrics counters histograms, distributed tracing spans, alerting notifications, interconnected, $STYLE"
    gen "$IMAGE_BASE/observability/flow-observability-data.png" \
        "Flow diagram showing observability data flow, application emits logs metrics traces, collectors aggregate, storage backends, visualization in Grafana, $STYLE"

    # structured-logging.md
    gen "$IMAGE_BASE/observability/technical-log-pipeline.png" \
        "Pipeline diagram of log flow, application code to context filter to JSON formatter to handlers to Loki aggregation to Grafana query, $STYLE"
    gen "$IMAGE_BASE/observability/concept-log-levels.png" \
        "Infographic of log levels pyramid, DEBUG verbose at base, INFO normal, WARNING attention, ERROR problem, CRITICAL urgent at top, $STYLE"
    gen "$IMAGE_BASE/observability/technical-log-context.png" \
        "Technical diagram showing log context enrichment, request ID, user context, operation name, timing data, added to each log entry, $STYLE"

    # prometheus-metrics.md
    gen "$IMAGE_BASE/observability/technical-metrics-collection.png" \
        "Technical diagram of Prometheus scraping, application exposes metrics endpoint, Prometheus scrapes at interval, stores in TSDB, $STYLE"
    gen "$IMAGE_BASE/observability/concept-metrics-types.png" \
        "Infographic of metric types, counter as incrementing number, gauge as speedometer, histogram as bar distribution, with example use cases, $STYLE"
    gen "$IMAGE_BASE/observability/technical-custom-metrics.png" \
        "Technical diagram showing custom metrics, detection count counter, queue depth gauge, inference duration histogram, $STYLE"

    # distributed-tracing.md
    gen "$IMAGE_BASE/observability/flow-trace-propagation.png" \
        "Flow diagram of trace context, parent span containing child spans, trace ID flowing across service boundaries, span hierarchy visualization, $STYLE"
    gen "$IMAGE_BASE/observability/technical-span-structure.png" \
        "Technical diagram of span structure, trace ID, span ID, parent span ID, start time, duration, tags, logs, $STYLE"
    gen "$IMAGE_BASE/observability/concept-trace-visualization.png" \
        "Conceptual visualization of trace as waterfall, nested spans showing call hierarchy, timing bars, service colors, $STYLE"

    # grafana-dashboards.md
    gen "$IMAGE_BASE/observability/technical-dashboard-layout.png" \
        "Technical wireframe of Grafana dashboard layout, panels for metrics, logs, traces, arranged in grid, $STYLE"
    gen "$IMAGE_BASE/observability/concept-dashboard-types.png" \
        "Infographic of dashboard types, service health overview, detection pipeline metrics, AI model performance, system resources, $STYLE"

    # alertmanager.md
    gen "$IMAGE_BASE/observability/flow-alert-lifecycle.png" \
        "Flow diagram of alert lifecycle, metric crosses threshold, alert fires, grouping and routing, notification sent, resolution, $STYLE"
    gen "$IMAGE_BASE/observability/technical-alert-routing.png" \
        "Technical diagram of alert routing, severity labels, team routing rules, escalation paths, notification channels, $STYLE"

    # =========================================================================
    # BACKGROUND SERVICES HUB (6 docs, ~18 images)
    # =========================================================================
    log "=== Background Services Hub (6 docs) ==="

    # README.md - Hero + conceptual
    gen "$IMAGE_BASE/background-services/hero-background-services.png" \
        "Technical illustration of background workers, FileWatcher BatchAggregator GPUMonitor CleanupService HealthMonitor as gear icons in circular arrangement, FastAPI lifespan manager in center, $STYLE, 1920x1080"
    gen "$IMAGE_BASE/background-services/concept-service-lifecycle.png" \
        "Timeline diagram of service lifecycle, startup phase with ordered initialization, running phase with periodic tasks, shutdown phase with reverse order cleanup, $STYLE"
    gen "$IMAGE_BASE/background-services/flow-lifespan-management.png" \
        "Flow diagram of FastAPI lifespan, startup event, initialize services in order, yield to application, shutdown event, cleanup in reverse order, $STYLE"

    # file-watcher.md
    gen "$IMAGE_BASE/background-services/technical-file-watcher.png" \
        "Technical diagram of file watcher internals, watchdog observer, event debouncer with timer, file validator, Redis queue submitter, connected in sequence, $STYLE"
    gen "$IMAGE_BASE/background-services/flow-file-event.png" \
        "Flow diagram from file system event through debounce through validation through queue submission, $STYLE"

    # batch-aggregator.md
    gen "$IMAGE_BASE/background-services/technical-batch-aggregator.png" \
        "Technical diagram of batch aggregator, detection input, batch manager, timer manager, batch output when closed, $STYLE"
    gen "$IMAGE_BASE/background-services/flow-batch-lifecycle.png" \
        "State flow of batch, Created on first detection, Active accumulating detections, timer showing 90s window 30s idle, Closed on trigger, Queued for analysis, $STYLE"

    # gpu-monitor.md
    gen "$IMAGE_BASE/background-services/technical-gpu-monitor.png" \
        "Technical diagram of GPU monitor, NVML interface, polling loop, metrics collection, Prometheus export, $STYLE"
    gen "$IMAGE_BASE/background-services/concept-gpu-metrics.png" \
        "Infographic of GPU metrics, utilization percentage, memory usage, temperature, power draw, with gauge visualizations, $STYLE"

    # health-check-worker.md
    gen "$IMAGE_BASE/background-services/technical-health-worker.png" \
        "Technical diagram of health worker, component registry, check scheduler, result aggregator, status endpoint, $STYLE"
    gen "$IMAGE_BASE/background-services/flow-health-check-loop.png" \
        "Flow diagram of health check loop, wait interval, run all checks, aggregate results, update status, publish if changed, loop, $STYLE"

    # retention-cleanup.md
    gen "$IMAGE_BASE/background-services/concept-cleanup-retention.png" \
        "Timeline showing retention policy, 30 day event retention window, 7 day log retention, cleanup service sweeping old data, database size staying bounded, $STYLE"
    gen "$IMAGE_BASE/background-services/flow-cleanup-process.png" \
        "Flow diagram of cleanup process, identify expired records, batch delete with limit, update statistics, schedule next run, $STYLE"

    # =========================================================================
    # MIDDLEWARE HUB (6 docs, ~18 images)
    # =========================================================================
    log "=== Middleware Hub (6 docs) ==="

    # README.md - Hero + conceptual
    gen "$IMAGE_BASE/middleware/hero-middleware.png" \
        "Technical illustration of middleware architecture, HTTP request entering stack of filter layers from top, processed request exiting to handler at bottom, response returning up through layers, $STYLE, 1920x1080"
    gen "$IMAGE_BASE/middleware/concept-middleware-stack.png" \
        "Vertical stack diagram, Request ID at top, Request Timing, Request Logging, Error Handling, CORS at bottom, request arrow passing through each layer, $STYLE"
    gen "$IMAGE_BASE/middleware/flow-request-response.png" \
        "Flow diagram showing request entering middleware stack, processing down through layers, handler execution, response going back up through layers, $STYLE"

    # request-logging.md
    gen "$IMAGE_BASE/middleware/technical-request-logging.png" \
        "Technical diagram of request logging middleware, capture request details, add context, process request, capture response, log complete record, $STYLE"
    gen "$IMAGE_BASE/middleware/concept-log-fields.png" \
        "Infographic showing log fields captured, method, path, status, duration, request ID, client IP, response size, $STYLE"

    # request-validation.md
    gen "$IMAGE_BASE/middleware/technical-validation-middleware.png" \
        "Technical diagram of validation middleware, parse body, validate against schema, return 400 on failure, pass to handler on success, $STYLE"
    gen "$IMAGE_BASE/middleware/flow-validation-process.png" \
        "Flow diagram of validation, receive request, extract body, apply Pydantic model, on error format response, on success continue, $STYLE"

    # error-handling.md
    gen "$IMAGE_BASE/middleware/technical-error-handling.png" \
        "Technical diagram of error middleware, try catch block, exception type router, error response formatter, status code mapper, logging hook, $STYLE"
    gen "$IMAGE_BASE/middleware/concept-error-types.png" \
        "Infographic mapping exception types to responses, ValidationError to 400, NotFoundError to 404, generic Exception to 500, $STYLE"

    # rate-limiting.md
    gen "$IMAGE_BASE/middleware/technical-rate-limiter.png" \
        "Technical diagram of rate limiter, request counter in Redis, check limit, increment if allowed, return 429 if exceeded, $STYLE"
    gen "$IMAGE_BASE/middleware/concept-rate-limit-window.png" \
        "Timeline showing sliding window rate limiting, request dots, window moving over time, requests counted within window, $STYLE"

    # cors-configuration.md
    gen "$IMAGE_BASE/middleware/technical-cors-middleware.png" \
        "Technical diagram of CORS middleware, preflight check, origin validation, header injection, $STYLE"
    gen "$IMAGE_BASE/middleware/flow-cors-preflight.png" \
        "Flow diagram of CORS preflight, receive OPTIONS, check origin, check method, add headers, return 200 or 403, $STYLE"

    # =========================================================================
    # FRONTEND HUB (6 docs, ~18 images)
    # =========================================================================
    log "=== Frontend Hub (6 docs) ==="

    # README.md - Hero + conceptual
    gen "$IMAGE_BASE/frontend/hero-frontend.png" \
        "Technical illustration of React frontend, component tree structure, state management flows, API hooks, WebSocket connection, modern dashboard aesthetic, $STYLE, 1920x1080"
    gen "$IMAGE_BASE/frontend/concept-architecture-overview.png" \
        "Infographic of frontend architecture, React components, Tanstack Query for data, WebSocket for realtime, Tailwind for styling, $STYLE"
    gen "$IMAGE_BASE/frontend/flow-data-flow.png" \
        "Flow diagram showing data flow, user interaction, hook call, API request, response, state update, re-render, $STYLE"

    # component-hierarchy.md
    gen "$IMAGE_BASE/frontend/technical-component-hierarchy.png" \
        "Tree diagram of component hierarchy, App at root, Layout children, Page components, UI components at leaves, data props flowing down events bubbling up, $STYLE"
    gen "$IMAGE_BASE/frontend/concept-component-types.png" \
        "Infographic of component types, page components, layout components, feature components, shared UI components, with examples, $STYLE"

    # custom-hooks.md
    gen "$IMAGE_BASE/frontend/technical-hook-dependencies.png" \
        "Dependency graph of custom hooks, useEvents useWebSocket useApi useAuth, showing which hooks depend on which, shared state connections, $STYLE"
    gen "$IMAGE_BASE/frontend/concept-hook-patterns.png" \
        "Infographic of hook patterns, data fetching hook, mutation hook, subscription hook, composing hooks together, $STYLE"

    # state-management.md
    gen "$IMAGE_BASE/frontend/flow-state-management.png" \
        "Flow diagram of state update cycle, user action triggers dispatch, reducer processes action, state updates, React re-renders affected components, $STYLE"
    gen "$IMAGE_BASE/frontend/technical-state-structure.png" \
        "Technical diagram of state structure, server state in Tanstack Query, local UI state in React, WebSocket state for realtime, $STYLE"

    # styling-patterns.md
    gen "$IMAGE_BASE/frontend/concept-styling-system.png" \
        "Infographic of styling system, Tailwind utilities, component variants, dark mode theming, responsive breakpoints, $STYLE"
    gen "$IMAGE_BASE/frontend/technical-design-tokens.png" \
        "Technical diagram of design tokens, color palette, spacing scale, typography scale, used by components, $STYLE"

    # testing-patterns.md
    gen "$IMAGE_BASE/frontend/concept-testing-strategy.png" \
        "Infographic of frontend testing strategy, unit tests for hooks, component tests with Testing Library, e2e tests with Playwright, $STYLE"
    gen "$IMAGE_BASE/frontend/flow-test-execution.png" \
        "Flow diagram of test execution, vitest runner, component render, interaction simulation, assertion verification, $STYLE"

    # =========================================================================
    # TESTING HUB (6 docs, ~18 images)
    # =========================================================================
    log "=== Testing Hub (6 docs) ==="

    # README.md - Hero + conceptual
    gen "$IMAGE_BASE/testing/hero-testing.png" \
        "Technical illustration of test architecture, pyramid shape with unit tests as wide base, integration tests middle, e2e tests at narrow top, pytest vitest playwright logos, $STYLE, 1920x1080"
    gen "$IMAGE_BASE/testing/concept-test-pyramid.png" \
        "Test pyramid diagram, large unit test base fast and many, medium integration layer, small e2e top slow and few, speed and quantity gradients, $STYLE"
    gen "$IMAGE_BASE/testing/flow-test-execution.png" \
        "Flow diagram of test execution, developer runs tests, unit tests parallel, integration tests serial, e2e tests browser, results aggregated, $STYLE"

    # unit-testing.md
    gen "$IMAGE_BASE/testing/technical-unit-test-structure.png" \
        "Technical diagram of unit test structure, arrange setup mocks, act call function, assert verify results, $STYLE"
    gen "$IMAGE_BASE/testing/concept-mock-strategies.png" \
        "Infographic of mock strategies, mock external services, fixture data, dependency injection, mock vs stub vs spy, $STYLE"

    # integration-testing.md
    gen "$IMAGE_BASE/testing/technical-integration-setup.png" \
        "Technical diagram of integration test setup, test database, test Redis, service under test, test fixtures, $STYLE"
    gen "$IMAGE_BASE/testing/flow-integration-test.png" \
        "Flow diagram of integration test, setup test database, seed data, call API endpoint, verify database state, cleanup, $STYLE"

    # e2e-testing.md
    gen "$IMAGE_BASE/testing/technical-e2e-architecture.png" \
        "Technical diagram of e2e test architecture, Playwright browser, test server, database, assertions on UI state, $STYLE"
    gen "$IMAGE_BASE/testing/flow-e2e-test.png" \
        "Flow diagram of e2e test, launch browser, navigate to page, interact with elements, wait for results, assert UI state, $STYLE"

    # test-fixtures.md
    gen "$IMAGE_BASE/testing/technical-fixture-hierarchy.png" \
        "Fixture scope diagram, session scope fixtures at top shared across all tests, module scope shared within file, function scope per test, dependency arrows, $STYLE"
    gen "$IMAGE_BASE/testing/concept-fixture-patterns.png" \
        "Infographic of fixture patterns, factory fixtures, database fixtures, mock fixtures, async fixtures, $STYLE"

    # coverage-requirements.md
    gen "$IMAGE_BASE/testing/concept-coverage-layers.png" \
        "Stacked bar chart showing coverage requirements per layer, 85 percent unit, 95 percent combined, frontend branches lines, $STYLE"
    gen "$IMAGE_BASE/testing/flow-tdd-cycle.png" \
        "Circular flow diagram of TDD, Red phase write failing test, Green phase minimal code to pass, Refactor phase improve code, arrows connecting in cycle, $STYLE"

    # =========================================================================
    # SECURITY HUB (6 docs, ~18 images)
    # =========================================================================
    log "=== Security Hub (6 docs) ==="

    # README.md - Hero + conceptual
    gen "$IMAGE_BASE/security/hero-security.png" \
        "Technical illustration of security architecture, layered shields around central data core, defense in depth visualization, lock icons, validation checkpoints, $STYLE, 1920x1080"
    gen "$IMAGE_BASE/security/concept-security-layers.png" \
        "Concentric rings diagram, input validation outer ring, authentication next, authorization inner, data protection at core, threat arrows being blocked at each layer, $STYLE"
    gen "$IMAGE_BASE/security/flow-security-request.png" \
        "Flow diagram of secured request, enter system, validation check, auth check, authz check, access data, each with pass fail paths, $STYLE"

    # input-validation.md
    gen "$IMAGE_BASE/security/technical-input-validation.png" \
        "Technical diagram of validation points, Pydantic schema validator, SQL injection filter, path traversal blocker, XSS sanitizer, as sequential gates, $STYLE"
    gen "$IMAGE_BASE/security/concept-validation-rules.png" \
        "Infographic of validation rules, type checking, range validation, format validation, sanitization, injection prevention, $STYLE"

    # authentication-roadmap.md
    gen "$IMAGE_BASE/security/flow-authentication.png" \
        "Flow diagram of auth process, API key submitted, validation check, user context loaded, request authorized, protected resource accessed, $STYLE"
    gen "$IMAGE_BASE/security/concept-auth-evolution.png" \
        "Timeline showing auth evolution roadmap, current API key, future OAuth support, JWT tokens, session management, $STYLE"

    # data-protection.md
    gen "$IMAGE_BASE/security/technical-data-protection.png" \
        "Technical diagram of data protection, encryption at rest, encryption in transit, sensitive field masking, retention policies, $STYLE"
    gen "$IMAGE_BASE/security/concept-data-classification.png" \
        "Infographic of data classification, public, internal, confidential, restricted, handling requirements for each, $STYLE"

    # network-security.md
    gen "$IMAGE_BASE/security/technical-network-security.png" \
        "Technical diagram of network security, container network isolation, firewall rules, internal vs external traffic, TLS termination, $STYLE"
    gen "$IMAGE_BASE/security/concept-network-zones.png" \
        "Infographic of network zones, public facing, internal services, data layer, each with access controls, $STYLE"

    # security-headers.md
    gen "$IMAGE_BASE/security/technical-security-headers.png" \
        "Technical diagram of security headers, CSP, HSTS, X-Frame-Options, X-Content-Type-Options, applied to responses, $STYLE"
    gen "$IMAGE_BASE/security/flow-header-application.png" \
        "Flow diagram of header application, response generated, security middleware adds headers, response sent with protection, $STYLE"

    # =========================================================================
    # DATAFLOWS HUB (10 docs, ~30 images)
    # =========================================================================
    log "=== Dataflows Hub (10 docs) ==="

    # README.md - Hero + conceptual
    gen "$IMAGE_BASE/dataflows/hero-dataflows.png" \
        "Technical illustration of complete data journey, camera on left, processing pipeline in middle with multiple stages, alert notification on right, end to end flow visualization, $STYLE, 1920x1080"
    gen "$IMAGE_BASE/dataflows/concept-dataflow-overview.png" \
        "High level infographic of all data flows, ingest flow, detection flow, analysis flow, broadcast flow, interconnections, $STYLE"

    # image-to-event.md
    gen "$IMAGE_BASE/dataflows/flow-image-to-event.png" \
        "Complete horizontal flow, camera upload, file watcher, detection queue, YOLO26, batch aggregator, Nemotron analysis, event creation, WebSocket broadcast, numbered stages, $STYLE"
    gen "$IMAGE_BASE/dataflows/technical-image-to-event-timing.png" \
        "Technical timeline showing image to event, ingestion 100ms, detection 500ms, aggregation 90s max, analysis 2s, broadcast 50ms, $STYLE"

    # batch-aggregation-flow.md
    gen "$IMAGE_BASE/dataflows/flow-batch-aggregation.png" \
        "Flow diagram of batch aggregation, detections arrive, group by camera, apply time windows, close batches on trigger, queue for analysis, $STYLE"
    gen "$IMAGE_BASE/dataflows/concept-aggregation-rules.png" \
        "Infographic of aggregation rules, 90 second maximum window, 30 second idle timeout, max detections per batch, $STYLE"

    # llm-analysis-flow.md
    gen "$IMAGE_BASE/dataflows/flow-llm-analysis.png" \
        "Flow diagram of LLM analysis, receive batch, construct prompt, call Nemotron, parse response, create event, handle errors, $STYLE"
    gen "$IMAGE_BASE/dataflows/technical-prompt-response.png" \
        "Technical diagram showing prompt structure sent to LLM and response structure received, field mappings, $STYLE"

    # websocket-message-flow.md
    gen "$IMAGE_BASE/dataflows/flow-websocket-message.png" \
        "Flow diagram of WebSocket message, event created, publish to Redis channel, broadcaster receives, format message, send to subscribed clients, $STYLE"
    gen "$IMAGE_BASE/dataflows/technical-message-routing.png" \
        "Technical diagram of message routing, event type routing, subscription matching, client filtering, delivery, $STYLE"

    # api-request-flow.md
    gen "$IMAGE_BASE/dataflows/flow-api-request.png" \
        "Flow diagram of API request, receive HTTP, middleware chain, route to handler, query database, format response, return, $STYLE"
    gen "$IMAGE_BASE/dataflows/technical-request-timing.png" \
        "Technical timing breakdown, middleware 5ms, handler 10ms, database 50ms, response 5ms, total 70ms example, $STYLE"

    # event-lifecycle.md
    gen "$IMAGE_BASE/dataflows/flow-event-lifecycle.png" \
        "Lifecycle diagram of event, created, active in timeline, viewed by user, acknowledged, archived after 30 days, $STYLE"
    gen "$IMAGE_BASE/dataflows/concept-event-states.png" \
        "State diagram of event states, new, viewed, acknowledged, archived, transitions with triggers, $STYLE"

    # enrichment-pipeline.md
    gen "$IMAGE_BASE/dataflows/flow-enrichment-detail.png" \
        "Detailed flow of enrichment, detection received, type identified, routed to enricher, enrichment performed, results merged, $STYLE"
    gen "$IMAGE_BASE/dataflows/concept-enrichment-routing.png" \
        "Routing diagram, detection type as input, vehicle to LPR, person to face, text to OCR, results back to detection, $STYLE"

    # error-recovery-flow.md
    gen "$IMAGE_BASE/dataflows/flow-error-recovery.png" \
        "Error handling flow, failure detection, retry attempt loop, max retries exceeded, dead letter queue storage, manual recovery option, alert notification, $STYLE"
    gen "$IMAGE_BASE/dataflows/concept-recovery-strategies.png" \
        "Infographic of recovery strategies, automatic retry, circuit breaker, DLQ for inspection, manual intervention, $STYLE"

    # startup-shutdown-flow.md
    gen "$IMAGE_BASE/dataflows/flow-startup.png" \
        "Flow diagram of startup sequence, load config, connect database, connect Redis, start background services, start API server, health check, $STYLE"
    gen "$IMAGE_BASE/dataflows/flow-shutdown.png" \
        "Flow diagram of shutdown sequence, stop accepting requests, drain queues, stop background services, close connections, exit, $STYLE"

    log "=== Generation Complete ==="
    log "Total images processed: $COUNT"
}

# Main
main() {
    echo ""
    echo "=============================================="
    echo "  Architecture Documentation Image Generator"
    echo "  ~250 images across 14 hubs"
    echo "=============================================="
    echo ""

    # Initialize log
    echo "=== Image Generation Started $(date) ===" > "$LOG_FILE"

    # Verify dependencies
    if ! command -v uv &> /dev/null; then
        error "uv is required but not installed"
        exit 1
    fi

    if [[ ! -f "$SKILL_SCRIPT" ]]; then
        error "nvidia-image-gen skill not found"
        exit 1
    fi

    create_directories

    info "Rate limit: 40 req/min (${RATE_LIMIT_DELAY}s delay)"
    info "Log file: $LOG_FILE"
    info "Estimated time: ~6-7 minutes for ~250 images"
    echo ""

    generate_all

    # Count results
    local total=$(find "$IMAGE_BASE" -name "*.png" -type f | wc -l | tr -d ' ')
    echo ""
    log "Total images in directory: $total"
    log "See $LOG_FILE for details"
}

main "$@"
