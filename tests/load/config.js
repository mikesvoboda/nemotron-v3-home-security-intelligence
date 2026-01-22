/**
 * k6 Load Test Configuration
 *
 * Shared configuration for all load tests including:
 * - Base URLs and endpoints
 * - Threshold definitions
 * - Load profile stages
 */

// Environment configuration with fallbacks
export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
export const WS_URL = __ENV.WS_URL || 'ws://localhost:8000';

// API key for authenticated endpoints (optional)
export const API_KEY = __ENV.API_KEY || '';

// Admin API key for seeding data (optional)
export const ADMIN_API_KEY = __ENV.ADMIN_API_KEY || '';

// Default HTTP request options
export const defaultOptions = {
    headers: {
        'Content-Type': 'application/json',
        ...(API_KEY && { 'X-API-Key': API_KEY }),
    },
};

// Admin request options (for seeding endpoints)
export const adminOptions = {
    headers: {
        'Content-Type': 'application/json',
        ...(ADMIN_API_KEY && { 'X-Admin-API-Key': ADMIN_API_KEY }),
    },
};

/**
 * Standard threshold definitions for API endpoints
 *
 * These thresholds define acceptable performance levels:
 * - http_req_duration: Response time percentiles
 * - http_req_failed: Error rate limits
 *
 * NOTE: Thresholds are tuned for CI environments (GitHub Actions) which have
 * variable resource availability. The values are more lenient than production
 * targets to avoid false positives from CI resource contention.
 *
 * CI Environment Considerations:
 * - GitHub Actions runners have shared resources and variable performance
 * - Smoke tests run with 1 VU and short duration, limiting throughput
 * - Database/Redis are containerized services with cold-start overhead
 * - AI services (RT-DETR, Nemotron) are NOT available in CI
 * - Some endpoints return 503/500 when AI pipeline is not registered
 * - The /export directory for file watching doesn't exist in CI
 * - Focus on latency performance rather than error rates for CI reliability
 *
 * Production vs CI Error Rates:
 * - Production target: <1% errors (all services available)
 * - CI target: <60% errors (many endpoints depend on unavailable AI services)
 */
export const standardThresholds = {
    // 95% of requests should complete within 2000ms (CI-friendly)
    'http_req_duration{type:api}': ['p(95)<2000', 'p(99)<5000'],
    // 99% of requests should complete within 5000ms, avg under 1000ms (CI-friendly)
    'http_req_duration': ['p(95)<2000', 'p(99)<5000', 'avg<1000'],
    // Error rate threshold relaxed for CI - many endpoints fail without AI services
    // Production should use stricter thresholds (rate<0.05)
    'http_req_failed': ['rate<0.60'],
    // NOTE: Throughput threshold removed - not meaningful with 1 VU smoke tests
    // and think time. Use stress/average profiles for throughput validation.
};

/**
 * WebSocket-specific thresholds
 *
 * NOTE: WebSocket thresholds are relaxed for CI environments where:
 * - Network conditions and resource availability vary
 * - AI services (RT-DETR, Nemotron) are NOT available
 * - WebSocket event streaming may fail without AI pipeline
 * - Resource contention in CI can cause intermittent connection failures
 */
export const wsThresholds = {
    // Connection time should be under 2000ms (CI-friendly)
    'ws_connecting': ['p(95)<2000'],
    // Highly relaxed: WebSocket connections frequently fail in CI without AI services
    // In production with AI services, this should be much stricter (e.g., rate<0.05)
    'ws_sessions{status:failed}': ['rate<0.70'],
    // NOTE: ws_session_duration is intentionally NOT included here because it's
    // a custom metric only defined in websocket.js. Including it here would cause
    // threshold failures in tests like all.js that import wsThresholds but don't
    // define the ws_session_duration metric. The websocket.js test defines its own
    // threshold for ws_session_duration: ['avg>2000'].
};

/**
 * Load Profile: Smoke Test
 *
 * Quick validation with minimal load to verify the system works.
 * Use for: CI/CD pipelines, quick health checks
 */
export const smokeTestStages = [
    { duration: '10s', target: 1 },   // 1 VU for 10 seconds
];

/**
 * Load Profile: Average Load
 *
 * Simulate typical production traffic patterns.
 * Use for: Regular performance validation
 */
export const averageLoadStages = [
    { duration: '30s', target: 10 },  // Ramp up to 10 VUs
    { duration: '1m', target: 10 },   // Stay at 10 VUs for 1 minute
    { duration: '30s', target: 0 },   // Ramp down
];

/**
 * Load Profile: Stress Test
 *
 * Push the system to find breaking points.
 * Use for: Capacity planning, finding bottlenecks
 */
export const stressTestStages = [
    { duration: '30s', target: 20 },  // Ramp up to 20 VUs
    { duration: '1m', target: 50 },   // Increase to 50 VUs
    { duration: '1m', target: 100 },  // Peak at 100 VUs
    { duration: '2m', target: 100 },  // Stay at peak for 2 minutes
    { duration: '30s', target: 0 },   // Ramp down
];

/**
 * Load Profile: Spike Test
 *
 * Sudden traffic spikes to test system resilience.
 * Use for: Testing auto-scaling, circuit breakers
 */
export const spikeTestStages = [
    { duration: '10s', target: 5 },    // Normal load
    { duration: '5s', target: 100 },   // Sudden spike to 100 VUs
    { duration: '30s', target: 100 },  // Hold spike
    { duration: '5s', target: 5 },     // Drop back to normal
    { duration: '30s', target: 5 },    // Recovery period
    { duration: '10s', target: 0 },    // Ramp down
];

/**
 * Load Profile: Soak Test
 *
 * Extended test to find memory leaks and degradation.
 * Use for: Pre-release testing, stability validation
 */
export const soakTestStages = [
    { duration: '1m', target: 30 },    // Ramp up to 30 VUs
    { duration: '10m', target: 30 },   // Hold for 10 minutes
    { duration: '30s', target: 0 },    // Ramp down
];

/**
 * API Endpoints
 */
export const endpoints = {
    // Events API
    events: {
        list: '/api/events',
        stats: '/api/events/stats',
        search: '/api/events/search',
        get: (id) => `/api/events/${id}`,
        detections: (id) => `/api/events/${id}/detections`,
    },
    // Cameras API
    cameras: {
        list: '/api/cameras',
        get: (id) => `/api/cameras/${id}`,
        snapshot: (id) => `/api/cameras/${id}/snapshot`,
        create: '/api/cameras',
        baseline: (id) => `/api/cameras/${id}/baseline`,
    },
    // System API
    system: {
        health: '/api/system/health',
        ready: '/api/system/health/ready',
        stats: '/api/system/stats',
        gpu: '/api/system/gpu',
        config: '/api/system/config',
    },
    // Detections API
    detections: {
        list: '/api/detections',
        get: (id) => `/api/detections/${id}`,
    },
    // WebSocket endpoints
    websocket: {
        events: '/ws/events',
        system: '/ws/system',
    },
    // Admin endpoints (development only)
    admin: {
        seedCameras: '/api/admin/seed/cameras',
        seedEvents: '/api/admin/seed/events',
        clearData: '/api/admin/seed/clear',
    },
};

/**
 * Select load profile based on environment variable
 *
 * Usage: k6 run -e LOAD_PROFILE=stress script.js
 */
export function getLoadStages() {
    const profile = __ENV.LOAD_PROFILE || 'average';

    switch (profile.toLowerCase()) {
        case 'smoke':
            return smokeTestStages;
        case 'stress':
            return stressTestStages;
        case 'spike':
            return spikeTestStages;
        case 'soak':
            return soakTestStages;
        case 'average':
        default:
            return averageLoadStages;
    }
}

/**
 * Helper to build full URL
 */
export function buildUrl(path) {
    return `${BASE_URL}${path}`;
}

/**
 * Helper to build WebSocket URL
 */
export function buildWsUrl(path) {
    return `${WS_URL}${path}`;
}
