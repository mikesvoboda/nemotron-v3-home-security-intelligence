#!/bin/bash
set -e

# Generate Architecture Documentation Images - Security & Dataflows Hubs
# Estimated: 40-50 images

SCRIPT_DIR="$HOME/.claude/skills/nvidia-image-gen/scripts"
IMAGE_BASE="docs/images/architecture"
RATE_LIMIT_DELAY=1.5  # 40 req/min = 1.5s between requests

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counter
COUNT=0
TOTAL=45

log() {
    echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"
}

generate_image() {
    local prompt="$1"
    local output_path="$2"

    if [[ -f "$output_path" ]]; then
        echo -e "${YELLOW}[$(date +%H:%M:%S)]${NC} Skip (exists): $(basename $output_path)"
        return 0
    fi

    echo -e "${BLUE}[$COUNT/$TOTAL]${NC} Generating: $(basename $output_path)"

    uv run python "$SCRIPT_DIR/generate_image.py" \
        "$prompt" \
        --output "$output_path" 2>/dev/null || {
        echo -e "${YELLOW}Failed:${NC} $(basename $output_path)"
        return 1
    }
}

gen() {
    generate_image "$1" "$2"
    COUNT=$((COUNT + 1))
    sleep $RATE_LIMIT_DELAY
}

# Common style prefix
STYLE="Dark tech aesthetic with #1a1a2e background, neon blue (#4a90d9) and green (#50c878) accents, clean lines, professional technical documentation style."

echo "=============================================="
echo "  Security & Dataflows Image Generator"
echo "  ~45 images across 2 hubs"
echo "=============================================="
echo ""
log "Creating image directories..."
mkdir -p "$IMAGE_BASE/security"
mkdir -p "$IMAGE_BASE/dataflows"

log "Rate limit: 40 req/min (${RATE_LIMIT_DELAY}s delay)"
log "Estimated time: ~2 minutes"
echo ""

# ==========================================
# SECURITY HUB (~18 images)
# ==========================================
log "=== Security Hub (6 docs, ~18 images) ==="

# Hero image
gen "$STYLE Security architecture hero image showing defense-in-depth layers. Central shield icon with multiple concentric protection rings. Outer ring labeled 'Network Boundary', middle ring 'Application Layer', inner ring 'Data Layer'. Icons for authentication, encryption, validation at each layer. Professional cybersecurity aesthetic with lock and shield motifs." \
    "$IMAGE_BASE/security/hero-security.png"

# README.md - Security Architecture
gen "$STYLE Security middleware stack visualization. Vertical flow showing request passing through security layers: AuthMiddleware (key icon) -> CORSMiddleware (globe icon) -> SecurityHeadersMiddleware (shield icon) -> BodySizeLimitMiddleware (size icon) -> RateLimiter (speedometer icon). Show request entering from browser at top, reaching API routes at bottom. Each middleware as a distinct horizontal bar." \
    "$IMAGE_BASE/security/flow-security-middleware.png"

gen "$STYLE OWASP Top 10 coverage visualization as a checklist or shield diagram. Show 10 security categories with status indicators: A01 Access Control (green check), A02 Crypto (yellow partial), A03 Injection (green check), A04 Insecure Design (blue by-design), A05 Misconfiguration (green), A06 Components (green), A07 Auth (orange optional), A08 Integrity (green), A09 Logging (green), A10 SSRF (green). Professional security audit style." \
    "$IMAGE_BASE/security/concept-owasp-coverage.png"

# input-validation.md
gen "$STYLE Input validation pipeline flowchart. Show data flow: Raw Input -> Pydantic Schema Validation -> Field Validators -> Type Coercion -> Sanitization -> Clean Output. Include rejection path showing ValidationError response. Highlight SQL injection prevention and XSS sanitization steps. Use shield icons for protection points." \
    "$IMAGE_BASE/security/flow-input-validation.png"

gen "$STYLE Pydantic validation architecture diagram. Central Pydantic logo/icon with spokes connecting to different validation types: String validators (length, pattern), Numeric validators (range, bounds), URL validators (protocol, host), Path validators (traversal check), Custom validators (business rules). Show example field constraints." \
    "$IMAGE_BASE/security/technical-pydantic-validation.png"

gen "$STYLE SQL injection prevention visualization. LEFT: Dangerous pattern showing raw SQL with user input injection point (red X). RIGHT: Safe pattern showing SQLAlchemy ORM with parameterized queries (green check). Show query transformation from unsafe to safe. Include database icon and query examples." \
    "$IMAGE_BASE/security/concept-sql-injection-prevention.png"

# data-protection.md
gen "$STYLE Data protection boundaries diagram. Show three zones: Untrusted Zone (external cameras, browser), Protected Zone (application services with encryption), Secure Zone (database, file storage). Arrows showing data flow with encryption/decryption points marked. Include data classification labels: Public, Internal, Sensitive." \
    "$IMAGE_BASE/security/concept-data-protection-zones.png"

gen "$STYLE Sensitive data handling flow. Show: Image Upload -> Path Validation -> Secure Storage -> Access Control -> Served with Headers. Highlight log sanitization (redacting sensitive fields), error message sanitization, and secure file path generation. Use lock icons at protection points." \
    "$IMAGE_BASE/security/flow-sensitive-data-handling.png"

gen "$STYLE Log sanitization visualization. LEFT: Raw log with sensitive data (API keys, paths, IPs highlighted in red). RIGHT: Sanitized log with redacted fields (shown as [REDACTED] or ***). Show transformation arrow between them. Professional audit log aesthetic." \
    "$IMAGE_BASE/security/concept-log-sanitization.png"

# network-security.md
gen "$STYLE Network security boundary diagram. Show local network perimeter with firewall icon. Inside: Home Security System components (backend, frontend, AI services). Outside: blocked internet traffic (red X). Camera FTP connection shown as internal trusted flow. Browser accessing via local IP only." \
    "$IMAGE_BASE/security/concept-network-boundary.png"

gen "$STYLE CORS configuration visualization. Show browser making cross-origin request, CORS middleware checking origin against allowlist, preflight OPTIONS request flow, and response with Access-Control headers. Include allowed origins list and blocked origin example." \
    "$IMAGE_BASE/security/technical-cors-configuration.png"

gen "$STYLE Trusted network assumption diagram. Central home icon with local network bubble. Inside bubble: all system components communicating freely. Show 'No Auth Required' label for internal traffic. Outside bubble: internet with lock/block icon. Single-user deployment model visualization." \
    "$IMAGE_BASE/security/concept-trusted-network.png"

# security-headers.md
gen "$STYLE HTTP security headers visualization as a response envelope. Show HTTP response with headers highlighted: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Strict-Transport-Security, Content-Security-Policy, Referrer-Policy. Each header with brief purpose annotation. Professional HTTP protocol style." \
    "$IMAGE_BASE/security/technical-security-headers.png"

gen "$STYLE Content Security Policy (CSP) diagram. Show browser with CSP enforcement. Blocked resources: inline scripts (red X), external scripts from untrusted domains (red X). Allowed resources: same-origin scripts (green check), trusted CDN (green check). Violation reporting arrow to backend." \
    "$IMAGE_BASE/security/concept-csp-policy.png"

# authentication-roadmap.md
gen "$STYLE Authentication roadmap timeline. Show progression: Current State (API Key Optional) -> Phase 1 (API Key Required) -> Phase 2 (JWT Tokens) -> Phase 3 (OAuth2/OIDC). Each phase as a milestone on horizontal timeline with key features listed. Future phases shown with dashed lines." \
    "$IMAGE_BASE/security/flow-auth-roadmap.png"

gen "$STYLE API key authentication flow. Show: Client sends X-API-Key header -> AuthMiddleware extracts key -> SHA-256 hash comparison -> Allow/Deny decision. Include secure key storage (hashed) and timing-safe comparison note. Professional authentication flow style." \
    "$IMAGE_BASE/security/flow-api-key-auth.png"

gen "$STYLE SSRF protection visualization. Show URL validation pipeline: Input URL -> Protocol Check (http/https only) -> Host Resolution -> IP Range Check (block private ranges) -> Allow/Block decision. Show blocked ranges: 10.x.x.x, 172.16.x.x, 192.168.x.x, 127.x.x.x. Red X for blocked, green check for allowed." \
    "$IMAGE_BASE/security/technical-ssrf-protection.png"

gen "$STYLE Path traversal protection diagram. Show: User input '../../../etc/passwd' -> Path validation -> Normalized path check -> Allowlist directory check -> Block/Allow. Highlight the dangerous traversal attempt being blocked. Show safe path resolution to allowed media directory." \
    "$IMAGE_BASE/security/concept-path-traversal-protection.png"

# ==========================================
# DATAFLOWS HUB (~27 images)
# ==========================================
log "=== Dataflows Hub (10 docs, ~27 images) ==="

# Hero image
gen "$STYLE Dataflows hero image showing end-to-end data journey. Camera icon on left, flowing through pipeline stages (detection, batching, analysis, events), to dashboard on right. Use flowing lines/arrows with data particles moving through the system. Professional data pipeline aesthetic." \
    "$IMAGE_BASE/dataflows/hero-dataflows.png"

# README.md - End-to-end flow
gen "$STYLE Complete system dataflow overview. Vertical flow: Camera Upload -> File Watcher -> Detection Queue -> YOLO26 -> Batch Aggregator -> Analysis Queue -> Nemotron LLM -> Event Creation -> WebSocket Broadcast. Each stage as a labeled box with timing annotations (debounce 0.5s, batch 90s, etc.)." \
    "$IMAGE_BASE/dataflows/flow-end-to-end-overview.png"

gen "$STYLE Key timing parameters visualization as a timeline or table. Show: File debounce (0.5s), File stability (2s), Batch window (90s), Batch idle (30s), YOLO26 timeout (60s), Nemotron timeout (120s), WebSocket idle (300s), Heartbeat (30s). Use clock icons and duration bars." \
    "$IMAGE_BASE/dataflows/concept-timing-parameters.png"

# image-to-event.md
gen "$STYLE Image to event complete pipeline flow. Detailed horizontal flow: Camera Image -> FTP Upload -> File Watcher (debounce) -> Validation -> Detection Queue -> YOLO26 (bboxes) -> Batch Aggregator -> Analysis Queue -> Enrichment -> Nemotron (risk score) -> Event DB -> WebSocket. Show data transformation at each stage." \
    "$IMAGE_BASE/dataflows/flow-image-to-event.png"

gen "$STYLE Detection data transformation visualization. Show image being processed: Original Image -> YOLO26 -> Bounding Boxes with labels (person, vehicle, animal) -> Detection Records with metadata (class, confidence, bbox coordinates). Include sample JSON output structure." \
    "$IMAGE_BASE/dataflows/concept-detection-transformation.png"

gen "$STYLE Event creation data model. Show Detection Batch being analyzed by Nemotron LLM, outputting: Event record with risk_score (0-100 gauge), summary text, detection links. Show database INSERT and WebSocket broadcast as final outputs." \
    "$IMAGE_BASE/dataflows/technical-event-creation.png"

# event-lifecycle.md
gen "$STYLE Event lifecycle state diagram. States: CREATED -> ACTIVE -> (optional: ACKNOWLEDGED) -> ARCHIVED. Show transitions with trigger labels: time-based archival (30 days), user acknowledgment, system cleanup. Include state duration annotations." \
    "$IMAGE_BASE/dataflows/flow-event-lifecycle.png"

gen "$STYLE Event states visualization with examples. Four panels showing event in each state: NEW (highlighted, unread indicator), ACTIVE (normal display), ACKNOWLEDGED (checkmark, dimmed), ARCHIVED (grayed out, in history). Dashboard-style presentation." \
    "$IMAGE_BASE/dataflows/concept-event-states.png"

# websocket-message-flow.md
gen "$STYLE WebSocket message flow diagram. Show: Event Created -> Redis Pub/Sub -> Event Broadcaster -> Connected WebSocket Clients (multiple). Include message envelope structure (type, data, seq, timestamp). Show fan-out pattern from one event to many clients." \
    "$IMAGE_BASE/dataflows/flow-websocket-broadcast.png"

gen "$STYLE WebSocket connection lifecycle flow. Show: Client Connect -> Handshake -> Subscribe to channels -> Receive events -> Heartbeat loop -> Disconnect/Reconnect. Include sequence numbers and message acknowledgment. Professional real-time communication diagram." \
    "$IMAGE_BASE/dataflows/flow-websocket-lifecycle.png"

gen "$STYLE WebSocket message types visualization. Show different message categories: EVENT (new detection event), HEARTBEAT (keep-alive ping/pong), SUBSCRIBE (channel subscription), UNSUBSCRIBE, ERROR, RECONNECT. Each with icon and brief description." \
    "$IMAGE_BASE/dataflows/concept-websocket-message-types.png"

# api-request-flow.md
gen "$STYLE REST API request processing flow. Show: HTTP Request -> Middleware Stack (auth, CORS, rate limit, validation) -> Route Handler -> Service Layer -> Database/Cache -> Response serialization -> HTTP Response. Include timing annotations at each stage." \
    "$IMAGE_BASE/dataflows/flow-api-request.png"

gen "$STYLE API response lifecycle. Show request entering, processing stages (validation, business logic, data access), and response construction. Include error handling branch showing how exceptions become HTTP error responses. Success and error paths clearly distinguished." \
    "$IMAGE_BASE/dataflows/flow-api-response.png"

# batch-aggregation-flow.md
gen "$STYLE Batch aggregation timing diagram. Show timeline with: Detection 1 arrives -> Start 90s window -> Detections 2,3,4 arrive -> Either: Window expires OR 30s idle timeout OR Max size reached -> Batch closes -> Sent to analysis. Use Gantt-chart style with time axis." \
    "$IMAGE_BASE/dataflows/flow-batch-timing.png"

gen "$STYLE Batch window mechanics visualization. Show camera generating detections over time, batch aggregator collecting them into groups. Highlight: 90-second maximum window, 30-second idle timeout trigger, per-camera batching. Use bucket/container metaphor for batches." \
    "$IMAGE_BASE/dataflows/concept-batch-window.png"

gen "$STYLE Batch state machine. States: EMPTY -> COLLECTING (detections arriving) -> READY (timeout or full) -> PROCESSING -> COMPLETE. Show transitions with triggers: first detection, timeout, max size, analysis complete. Include batch metadata (camera_id, detection_count, start_time)." \
    "$IMAGE_BASE/dataflows/technical-batch-states.png"

# llm-analysis-flow.md
gen "$STYLE Nemotron LLM analysis flow. Show: Detection Batch -> Context Building (zone info, baselines, history) -> Prompt Template -> LLM API Request -> Response Parsing -> Risk Score + Summary extraction -> Event Creation. Include timeout (120s) and retry annotations." \
    "$IMAGE_BASE/dataflows/flow-llm-analysis.png"

gen "$STYLE LLM prompt construction visualization. Show inputs flowing into prompt template: Detection data, Zone context, Activity baseline, Cross-camera correlation, Time context. Output: Structured prompt for Nemotron. Template structure visible with placeholders." \
    "$IMAGE_BASE/dataflows/concept-prompt-construction.png"

gen "$STYLE LLM response parsing flow. Show: Raw LLM Response -> JSON Extraction -> Schema Validation -> Risk Score (0-100 gauge) + Summary Text + Reasoning extraction -> Structured Event Data. Include error handling for malformed responses." \
    "$IMAGE_BASE/dataflows/technical-response-parsing.png"

# enrichment-pipeline.md
gen "$STYLE Enrichment pipeline flow. Show detection passing through optional enrichment stages: Florence-2 (captioning) -> CLIP (embedding) -> Depth Estimation -> Pose Detection. Each stage as optional module that can be enabled/disabled. Show enriched detection output with additional metadata." \
    "$IMAGE_BASE/dataflows/flow-enrichment-pipeline.png"

gen "$STYLE Enrichment model selection logic. Decision tree: Detection Type? -> Person: enable pose, clothing, threat models -> Vehicle: enable plate reader, classifier -> Animal: enable pet classifier. Show OnDemandModelManager routing detections to appropriate models." \
    "$IMAGE_BASE/dataflows/technical-enrichment-routing.png"

# error-recovery-flow.md
gen "$STYLE Error recovery flow with circuit breaker. Show: Request -> Circuit Breaker Check (CLOSED/OPEN/HALF-OPEN) -> If CLOSED: proceed to service -> On failure: increment counter -> If threshold reached: OPEN circuit. Include recovery timeout and half-open test request." \
    "$IMAGE_BASE/dataflows/flow-circuit-breaker.png"

gen "$STYLE Retry strategy visualization. Show exponential backoff: Attempt 1 (immediate) -> Fail -> Wait 1s -> Attempt 2 -> Fail -> Wait 2s -> Attempt 3 -> Fail -> Wait 4s -> Max retries -> DLQ/Error. Include jitter visualization for thundering herd prevention." \
    "$IMAGE_BASE/dataflows/concept-retry-strategy.png"

gen "$STYLE Error categories and handling decision tree. Show error classification: SERVICE_UNAVAILABLE, TIMEOUT, RATE_LIMITED -> Retry with backoff. CLIENT_ERROR, VALIDATION_ERROR, PARSE_ERROR -> No retry, return error. UNEXPECTED -> Retry with logging. Color-coded paths (green=retry, red=fail)." \
    "$IMAGE_BASE/dataflows/technical-error-categories.png"

# startup-shutdown-flow.md
gen "$STYLE Application startup sequence flow. Show ordered initialization: 1. Database connection -> 2. Redis connection -> 3. AI service health checks -> 4. Background workers start -> 5. API server ready -> 6. WebSocket server ready. Include health check indicators and dependency arrows." \
    "$IMAGE_BASE/dataflows/flow-startup-sequence.png"

gen "$STYLE Application shutdown sequence flow. Show graceful shutdown: 1. Stop accepting requests -> 2. Drain active connections (30s timeout) -> 3. Stop background workers -> 4. Flush queues -> 5. Close database connections -> 6. Exit. Include SIGTERM/SIGINT trigger and timeout annotations." \
    "$IMAGE_BASE/dataflows/flow-shutdown-sequence.png"

gen "$STYLE Lifespan management overview. Three phases: STARTUP (green, services initializing), RUNTIME (blue, normal operation with health checks), SHUTDOWN (orange, graceful termination). Show service health indicators and dependency graph for each phase." \
    "$IMAGE_BASE/dataflows/concept-lifespan-phases.png"

echo ""
echo "=============================================="
log "Generation complete: $COUNT/$TOTAL images"
echo "=============================================="
