#!/bin/bash
set -e

# Regenerate Architecture Documentation Images - Subpar Images Only
# Based on validation agent recommendations
# 30 images identified for improvement

SCRIPT_DIR="$HOME/.claude/skills/nvidia-image-gen/scripts"
IMAGE_BASE="docs/images/architecture"
RATE_LIMIT_DELAY=1.5  # 40 req/min = 1.5s between requests

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Counter
COUNT=0
TOTAL=30

log() {
    echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +%H:%M:%S)]${NC} $1"
}

generate_image() {
    local prompt="$1"
    local output_path="$2"

    # Remove existing image to force regeneration
    rm -f "$output_path"

    echo -e "${BLUE}[$COUNT/$TOTAL]${NC} Regenerating: $(basename $output_path)"

    uv run python "$SCRIPT_DIR/generate_image.py" \
        "$prompt" \
        --output "$output_path" 2>/dev/null || {
        echo -e "${RED}Failed:${NC} $(basename $output_path)"
        return 1
    }
}

gen() {
    generate_image "$1" "$2"
    COUNT=$((COUNT + 1))
    sleep $RATE_LIMIT_DELAY
}

# Common style prefix for consistency
STYLE="Dark tech aesthetic with #1a1a2e background, neon blue (#4a90d9) and green (#50c878) accents, clean lines, professional technical documentation style."

echo "=============================================="
echo "  Regenerating Subpar Architecture Images"
echo "  30 images based on validation feedback"
echo "=============================================="
echo ""
log "Rate limit: 40 req/min (${RATE_LIMIT_DELAY}s delay)"
log "Estimated time: ~1 minute"
echo ""

# ==========================================
# SYSTEM OVERVIEW HUB (5 images)
# ==========================================
log "=== System Overview Hub (5 images) ==="

gen "$STYLE Create a comprehensive technology stack visualization organized by layer. TOP ROW: Frontend layer with React 18.2 logo, TypeScript 5.3 logo, Tailwind CSS 3.4 logo, Tremor 3.17, Vite 5.0 logos in blue section. SECOND ROW: Backend layer with Python 3.14 logo, FastAPI 0.104 logo, SQLAlchemy 2.0 logo, Pydantic 2.0 logo in green section. THIRD ROW: AI/ML layer with PyTorch 2.x logo, YOLO26 icon, Nemotron-3-Nano icon, llama.cpp logo in orange section. BOTTOM ROW: Infrastructure with Docker/Podman logo, NVIDIA Container Toolkit logo, Prometheus logo, Grafana logo in purple section. Each technology clearly labeled with name and version. 16:9 aspect ratio." \
    "$IMAGE_BASE/system-overview/concept-technology-stack.png"

gen "$STYLE Technical deployment topology diagram showing containerized services on security-net bridge network. LEFT SIDE: Core Services group with frontend:8080 and backend:8000 containers in blue. CENTER: Data Layer with postgres and redis containers in orange. RIGHT SIDE: AI Services (GPU-enabled) group with ai-yolo26:8095, ai-llm:8091, ai-enrichment:8092 in green with GPU icon. TOP: Monitoring stack with prometheus and grafana in purple. Show NVIDIA GPU device with arrow connecting to all AI service containers. Label the security-net bridge network connecting all containers. Include port numbers on each container." \
    "$IMAGE_BASE/system-overview/technical-deployment-topology.png"

gen "$STYLE Service startup sequence flowchart showing container dependency order with timing. Stage 1 (parallel): postgres (10s start period) and redis starting simultaneously. Stage 2: ai-yolo26 (60s start period) with arrow from Stage 1. Stage 3: ai-llm (120s start period) with health check dependency. Stage 4: ai-enrichment (180s start period) with health check dependency. Stage 5: backend service depending on all above with service_healthy conditions. Stage 6: frontend as final stage. Show timing annotations on each stage. Use horizontal swim lanes for parallel vs sequential startup." \
    "$IMAGE_BASE/system-overview/flow-container-startup.png"

gen "$STYLE Pydantic Settings configuration hierarchy as three descending layers. TOP LAYER: '.env file' box with file icon showing application root location. MIDDLE LAYER: 'Environment Variables' box with OS level icon. BOTTOM LAYER: 'Field Defaults' box with code icon showing Pydantic default values. Show @cache decorator annotation on Settings class indicating singleton pattern. RIGHT SIDE: Show nested settings examples - OrchestratorSettings, TranscodeCacheSettings. Arrows showing override priority flowing downward. Include example categories: Database, Redis, AI Services, Batch Processing." \
    "$IMAGE_BASE/system-overview/technical-config-hierarchy.png"

gen "$STYLE Configuration loading flow diagram with three phases. LEFT: Two input sources - '.env file' icon and 'Environment Variables' icon with arrows pointing right. CENTER: Large box labeled 'Pydantic BaseSettings Validation' with validator icons showing URL validation and SSRF protection checks. RIGHT: Output box labeled 'Settings Singleton' with @cache decorator symbol. Show get_settings() function pattern as dependency injection arrow. Include validation arrows between stages." \
    "$IMAGE_BASE/system-overview/flow-config-loading.png"

# ==========================================
# AI ORCHESTRATION HUB (3 images)
# ==========================================
log "=== AI Orchestration Hub (3 images) ==="

gen "$STYLE Clean detection output visualization. LEFT SIDE: Simple outdoor scene with clear person silhouette and car shape. CENTER: 2-3 large, clearly visible bounding boxes with thick borders - blue box around person labeled 'person 0.92', green box around car labeled 'vehicle 0.87'. RIGHT SIDE: JSON code block showing response structure: { 'class': 'person', 'confidence': 0.92, 'bbox': { 'x': 100, 'y': 150, 'width': 50, 'height': 120 } }. All text large and readable. Professional documentation style." \
    "$IMAGE_BASE/ai-orchestration/concept-detection-outputs.png"

gen "$STYLE Model Zoo architecture visualization. TOP: VRAM budget bar showing 6.8GB total with colored segments for loaded models. CENTER: Five model category sections - Detection (YOLO26, YOLO), Pose (vitpose-small), Classification (fashionclip), Embedding (clip-vit), OCR (license plate reader). Each category shows 2-3 model cards. BOTTOM: LRU cache visualization showing models entering and exiting 'loaded' state. RIGHT SIDE: Priority level legend - CRITICAL (red), HIGH (orange), MEDIUM (yellow), LOW (blue). Show model cards with priority indicators." \
    "$IMAGE_BASE/ai-orchestration/concept-model-zoo.png"

gen "$STYLE Enrichment routing decision tree flowchart. TOP: 'Detection Input' box. FIRST DECISION: 'Detection Type?' diamond. THREE BRANCHES: 'person' path leading to model boxes [threat detection, pose estimation, clothing classification, re-identification, action recognition]. 'vehicle' path leading to [vehicle classifier, license plate reader, depth estimation]. 'animal' path leading to [pet classifier]. CENTER: 'OnDemandModelManager' as central hub connecting all branches. CONDITIONAL LOGIC BOX: 'if suspicious + multiple frames -> add action recognition'. All paths and decision points clearly labeled." \
    "$IMAGE_BASE/ai-orchestration/technical-enrichment-routing.png"

# ==========================================
# DETECTION PIPELINE HUB (5 images)
# ==========================================
log "=== Detection Pipeline Hub (5 images) ==="

gen "$STYLE File event handling flow with explicit labeled steps. LEFT TO RIGHT: 'File Event' icon -> 'Stability Check' box (1s wait) -> 'SHA256 Deduplication' box with hash icon -> 'Validation' box showing three checks (size check, header verify, full load) -> 'Camera ID Extraction' box -> 'Queue Submission' output. BOTTOM: Rejection path with red arrow showing 'skip + log warning' for failed validation. All steps labeled clearly with icons." \
    "$IMAGE_BASE/detection-pipeline/flow-file-event-handling.png"

gen "$STYLE Detection queue architecture diagram (2D, not 3D). LEFT: FIFO queue visualization with items stacked, labeled 'Detection Queue'. CENTER: Processing section showing 'BLPOP Operation' label, 'DetectionQueueWorker' box with internal components - 'Retry Handler' with backoff icon and 'DLQ Router' with error path. RIGHT: 'YOLO26 Detector' connection. Show three paths: successful processing (green), retry path (yellow), DLQ routing (red) for max retries exceeded. Clear labels on all components." \
    "$IMAGE_BASE/detection-pipeline/technical-detection-queue.png"

gen "$STYLE Analysis queue pipeline as 2D flow diagram (not 3D isometric). Horizontal flow: 'Batch Queue' -> 'Batch Fetch' -> 'Context Enrichment' box (showing zones, baselines, cross-camera sub-items) -> 'Semaphore Acquire' with concurrency control icon -> 'LLM Request' box labeled 'Nemotron/llama.cpp' -> 'Response Parsing' -> 'Event Creation' -> 'WebSocket Broadcast'. Include retry logic branch and error handling path below main flow. All labels visible." \
    "$IMAGE_BASE/detection-pipeline/technical-analysis-queue.png"

gen "$STYLE Critical paths comparison as 2D side-by-side diagram. LEFT HALF labeled 'NORMAL PATH': Detection icon -> Batch Window box (30-90s wait time clearly marked) -> Analysis output. RIGHT HALF labeled 'FAST PATH': High-confidence Person Detection icon -> Immediate Analysis (<5s total latency). CENTER: Decision diamond showing 'confidence >= 0.9 AND person type?' gate connecting both paths. Clear latency target annotations: Normal path '30-90s batch wait', Fast path '<5s end-to-end'." \
    "$IMAGE_BASE/detection-pipeline/concept-critical-paths.png"

gen "$STYLE Detection pipeline hero image showing multi-stage processing. LEFT: Camera/file watcher inputs feeding into system. CENTER: Three-stage pipeline visualization - Stage 1 'Detection' with YOLO26 icon, Stage 2 'Batching' with aggregator icon, Stage 3 'Analysis' with Nemotron brain icon. RIGHT: Event outputs and WebSocket broadcast. Show GPU acceleration indicator on detection stage. Professional tech aesthetic with clear flow arrows between stages." \
    "$IMAGE_BASE/detection-pipeline/hero-detection-pipeline.png"

# ==========================================
# REALTIME SYSTEM HUB (4 images)
# ==========================================
log "=== Realtime System Hub (4 images) ==="

gen "$STYLE WebSocket connection lifecycle state machine diagram. Six states as distinct colored boxes: CONNECTING (blue) -> AUTHENTICATING (yellow) with success/failure branches -> ACTIVE (green) -> bidirectional arrow to IDLE (gray) -> TIMEOUT (orange) -> DISCONNECTING (red). Show transition labels: 'auth success', 'auth failure -> rejected', 'no activity', 'activity resumed', 'timeout exceeded', 'close requested'. Include recovery path from TIMEOUT back to CONNECTING." \
    "$IMAGE_BASE/realtime-system/concept-connection-lifecycle.png"

gen "$STYLE Connection handling flow with labeled steps. Vertical flow: Step 1 'Rate Limit Check' with decision diamond (returns 1008 code if exceeded). Step 2 'Authentication Validation' with decision diamond (reject if invalid). Step 3 'Connection Registration' box. Step 4 'Start Heartbeat Task' with parallel indicator. Step 5 'Enter Message Loop' box. Show success path in green, rejection paths in red with specific error codes. Include timing indicators for each step." \
    "$IMAGE_BASE/realtime-system/flow-connection-handling.png"

gen "$STYLE WebSocket message envelope structure visualization. LEFT: JSON structure clearly showing five fields with descriptions: { 'type': 'event' (message type), 'data': {...} (payload object), 'seq': 123 (sequence number), 'timestamp': '2026-01-24T...' (ISO timestamp), 'requires_ack': true (acknowledgment flag) }. RIGHT: Sample complete message example with actual values. Use code block styling with syntax highlighting. All text readable at documentation size." \
    "$IMAGE_BASE/realtime-system/technical-message-envelope.png"

gen "$STYLE Client reconnection protocol flow. TOP: 'Connection Drop Detected' event. LOOP STRUCTURE: 'Exponential Backoff Timer' with attempt counter (1, 2, 3...). 'Reconnection Attempt' box. SUCCESS PATH: 'Send Resync Request' with last_sequence number -> 'Receive Message Replay' (marked with replay:true flag) -> 'CONNECTED' state. FAILURE PATH: 'Max Attempts Exceeded?' decision -> 'FAILED' state. Show retry loop structure clearly with attempt count visualization." \
    "$IMAGE_BASE/realtime-system/flow-client-reconnection.png"

# ==========================================
# DATA MODEL HUB (3 images)
# ==========================================
log "=== Data Model Hub (3 images) ==="

gen "$STYLE Entity relationship diagram with crow's foot notation. Four tables: CAMERAS table (left) with one-to-many arrow to DETECTIONS table. DETECTIONS table connected via many-to-many through EVENT_DETECTIONS junction table (highlighted with special border) to EVENTS table (right). Show cardinality symbols: ||--o{ for one-to-many, }o--o{ for many-to-many. Include key fields in each table box. Highlight event_detections junction table as key architectural decision." \
    "$IMAGE_BASE/data-model/technical-entity-relationships.png"

gen "$STYLE Events table detailed visualization. CENTER: EVENTS table card showing columns (id, risk_score, search_vector with tsvector type, timestamps, etc.). SURROUNDING: Clear relationship lines to connected tables - ALERTS table (top), EVENT_DETECTIONS junction table (right), EVENT_FEEDBACK table (bottom). Annotation box showing 'GIN index on search_vector' with index icon. All connecting lines labeled with relationship type. Emphasis on many-to-many through junction table." \
    "$IMAGE_BASE/data-model/technical-event-table.png"

gen "$STYLE Redis key patterns visualization with readable text examples. Five category sections: (1) QUEUE KEYS - 'batch:{camera_id}:current', 'analysis_queue' with list icon. (2) DEDUP KEYS - 'dedupe:{sha256_hash}' with TTL indicator. (3) STATE KEYS - 'batch_state:{id}' with hash icon. (4) PUB/SUB - 'events:{camera_id}' channel with broadcast icon. (5) CACHES - with TTL patterns. Use color-coded sections with actual key pattern examples as readable text, not abstract shapes." \
    "$IMAGE_BASE/data-model/technical-redis-keys.png"

# ==========================================
# API REFERENCE HUB (2 images)
# ==========================================
log "=== API Reference Hub (2 images) ==="

gen "$STYLE API response envelope visualization with actual JSON structure. LEFT HALF: Abstract envelope concept with items array and pagination sections. RIGHT HALF: Actual JSON code block: { 'items': [...array of data...], 'pagination': { 'total': 1000, 'limit': 50, 'offset': 0, 'next_cursor': 'abc123', 'has_more': true } }. Show both the conceptual view and literal structure side by side. Labels pointing to each section explaining purpose." \
    "$IMAGE_BASE/api-reference/concept-response-envelope.png"

gen "$STYLE Comprehensive error handling flow diagram. TOP: 'Request Received' input. FIVE ERROR PATHS branching from validation: (1) Validation Error 400/422 path, (2) Not Found 404 path, (3) Auth Error 401/403 path, (4) Rate Limit 429 path with 'retry_after' annotation, (5) Service Error 500/502/503 path. BOTTOM: Error response structure box showing fields: error_code, message, details, request_id. Show both flat format and RFC 7807 Problem Details format options." \
    "$IMAGE_BASE/api-reference/flow-error-response.png"

# ==========================================
# RESILIENCE PATTERNS HUB (2 images)
# ==========================================
log "=== Resilience Patterns Hub (2 images) ==="

gen "$STYLE Exponential backoff visualization with clear chart. X-AXIS labeled 'Attempt Number' (1 through 6). Y-AXIS labeled 'Delay (seconds)' (0 to 35). Show discrete step points: Attempt 1 = 1s, Attempt 2 = 2s, Attempt 3 = 4s, Attempt 4 = 8s, Attempt 5 = 16s, Attempt 6 = 30s (capped). RED HORIZONTAL LINE at y=30 labeled 'max_delay_seconds cap'. Data points clearly labeled with values. Legend explaining exponential growth formula. Grid lines for readability." \
    "$IMAGE_BASE/resilience-patterns/technical-retry-backoff.png"

gen "$STYLE Dead Letter Queue processing flow with labels. LEFT: 'Failed Job' input with error icon. STEP 1: 'Inspect & Categorize' box with metadata (attempt count, error type). DECISION DIAMOND: 'Recoverable?' BRANCH YES: 'Requeue to Processing Queue' with green arrow. BRANCH NO: 'Archive/Discard' with gray arrow. SEPARATE BRANCH: 'Manual Review Required' path for special cases. All steps labeled clearly with descriptive text. Include processing metadata visualization." \
    "$IMAGE_BASE/resilience-patterns/flow-dlq-processing.png"

# ==========================================
# OBSERVABILITY HUB (1 image)
# ==========================================
log "=== Observability Hub (1 image) ==="

gen "$STYLE Log context injection flow diagram, left-to-right. LEFT SECTION (three source boxes): 'Request ID Middleware' box, 'OpenTelemetry' box, 'log_context manager' box. CENTER: 'ContextFilter' processing component with arrows from all sources. RIGHT: 'Enriched Log Record' output showing all context fields: connection_id, task_id, job_id, request_id, trace_id. BOTTOM: Before/after comparison - 'Basic Log' vs 'Enriched Log with Context'. Clear flow arrows, no overlapping elements." \
    "$IMAGE_BASE/observability/technical-log-context.png"

# ==========================================
# BACKGROUND SERVICES HUB (2 images)
# ==========================================
log "=== Background Services Hub (2 images) ==="

gen "$STYLE Application lifespan management with three labeled phases. PHASE 1 'STARTUP SEQUENCE': Numbered services starting - 1. FileWatcher, 2. GPUMonitor, 3. HealthWorker with arrows showing order. PHASE 2 'RUNTIME OPERATION': All services shown running in parallel with heartbeat indicators. PHASE 3 'SHUTDOWN SEQUENCE': Reverse order (LIFO) with '30s drain timeout' annotation on each service. Clear phase labels at top of each section. Reverse arrow from shutdown to startup showing LIFO order." \
    "$IMAGE_BASE/background-services/flow-lifespan-management.png"

gen "$STYLE Batch lifecycle flow with timeout annotations. INPUT: 'Detection Input' stream. BATCH CREATED box with counter icon. TWO TIMEOUT PATHS clearly labeled: PATH 1 '90s Window Timeout' with clock showing 90 seconds, PATH 2 '30s Idle Timeout' with idle indicator. Both paths lead to 'Batch Close Triggered' box. OUTPUT: 'Analysis Queue' destination. Include detection count visualization showing 'max size = 100 detections' as third trigger. All timeout values prominently displayed." \
    "$IMAGE_BASE/background-services/flow-batch-lifecycle.png"

# ==========================================
# MIDDLEWARE HUB (2 images)
# ==========================================
log "=== Middleware Hub (2 images) ==="

gen "$STYLE Error handling middleware flowchart using standard notation. START: 'Exception Raised' event. DECISION DIAMOND: 'Exception Type?' with five branches. HANDLER BOXES (color-coded): CircuitBreakerError (red) -> 503, RateLimitError (orange) -> 429, ValidationError (yellow) -> 400/422, NotFoundError (blue) -> 404, ServerError (purple) -> 500. Each handler leads to 'Response Generation' with appropriate status code. Show handler registration order with numbered priority." \
    "$IMAGE_BASE/middleware/technical-error-handling.png"

gen "$STYLE Sliding window rate limiting visualization. TIMELINE: Horizontal time axis with markers at 0s, 30s, 60s, 90s, 120s. WINDOW BOX: 60-second span window clearly bounded, labeled 'Current Window (60s)'. REQUEST DOTS: Show request markers within window being counted. ANIMATION CONCEPT: Three frames showing window sliding right over time - Frame 1 (0-60s), Frame 2 (30-90s), Frame 3 (60-120s). Labels: 'Window Start', 'Window End', 'Request Count: 45/100'. Show old requests falling off left edge as window moves." \
    "$IMAGE_BASE/middleware/concept-rate-limit-window.png"

# ==========================================
# FRONTEND HUB (1 image)
# ==========================================
log "=== Frontend Hub (1 image) ==="

gen "$STYLE React hooks patterns visualization with four large panels. PANEL 1 'Data Fetching': useQuery hook showing loading -> data -> error states with React Query logo. PANEL 2 'Mutations': useMutation hook showing request -> success/error flow with optimistic updates. PANEL 3 'Subscriptions': WebSocket hook showing connection -> message handling -> reconnection. PANEL 4 'Composition': Diagram showing hooks composing together (useQuery + useMutation + custom logic). Include React Query terminology: useQuery, useMutation, useInfiniteQuery. Large readable labels." \
    "$IMAGE_BASE/frontend/concept-hook-patterns.png"

# ==========================================
# TESTING HUB (1 image)
# ==========================================
log "=== Testing Hub (1 image) ==="

gen "$STYLE Mock strategies visualization with three distinct sections and readable text. LEFT SECTION 'MOCKS' (blue): 'Verify Behavior' header, example mock_db_session showing .assert_called_with() usage. CENTER SECTION 'STUBS' (green): 'Provide Canned Responses' header, example showing mock_http_client.return_value = {...}. RIGHT SECTION 'SPIES' (orange): 'Record Calls' header, example showing call_args_list inspection. BOTTOM: 'External Service Mocking' section showing HTTP client mock and Redis client mock patterns. All text large and legible, no duplicate content." \
    "$IMAGE_BASE/testing/concept-mock-strategies.png"

echo ""
echo "=============================================="
log "Regeneration complete: $COUNT/$TOTAL images"
echo "=============================================="
