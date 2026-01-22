/**
 * k6 Load Test: All API Endpoints Combined
 *
 * Comprehensive load test that simulates realistic mixed traffic across
 * all API endpoints. This provides the most accurate representation of
 * production traffic patterns.
 *
 * Traffic Distribution:
 * - 35% Events API (list, stats, search, details)
 * - 30% Cameras API (list, details, snapshots)
 * - 15% System API (health, stats, config)
 * - 10% WebSocket connections (events, system)
 * - 10% Detections API
 *
 * Usage:
 *   k6 run tests/load/all.js
 *   k6 run -e LOAD_PROFILE=stress tests/load/all.js
 *   k6 run -e BASE_URL=http://localhost:8000 tests/load/all.js
 */

import http from 'k6/http';
import ws from 'k6/ws';
import { check, group, sleep } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';
import {
    BASE_URL,
    WS_URL,
    API_KEY,
    defaultOptions,
    standardThresholds,
    wsThresholds,
    endpoints,
    getLoadStages,
    buildUrl,
    buildWsUrl,
} from './config.js';

// Custom metrics - API
const apiDuration = new Trend('api_duration', true);
const apiErrorRate = new Rate('api_error_rate');
const apiRequestCount = new Counter('api_request_count');

// Custom metrics - WebSocket
const wsConnectTime = new Trend('ws_connect_time', true);
const wsConnectionErrors = new Rate('ws_connection_errors');

// Combined thresholds (CI-friendly values)
// NOTE: Error rates are relaxed because AI services (RT-DETR, Nemotron) are not
// available in CI, causing many endpoints to return 503/500 errors.
// Latency thresholds remain strict to catch actual performance regressions.
export const options = {
    stages: getLoadStages(),
    thresholds: {
        ...standardThresholds,
        ...wsThresholds,
        // Custom API thresholds - latency strict, error rates relaxed for CI
        'api_duration': ['p(95)<2000', 'avg<1000'],
        'api_error_rate': ['rate<0.60'],  // Relaxed: AI services unavailable in CI
        'ws_connect_time': ['p(95)<2000'],
        'ws_connection_errors': ['rate<0.70'],  // Highly relaxed: WS frequently fails without AI services
    },
    tags: {
        testSuite: 'all',
    },
};

// Traffic weights (must sum to 1.0)
const TRAFFIC_WEIGHTS = {
    events: 0.35,
    cameras: 0.30,
    system: 0.15,
    websocket: 0.10,
    detections: 0.10,
};

/**
 * Setup function
 */
export function setup() {
    // Verify API is reachable
    const healthCheck = http.get(buildUrl('/api/system/health/ready'));

    if (healthCheck.status !== 200) {
        console.warn(`API not ready: ${healthCheck.status}`);
    }

    // Gather test data
    const camerasResponse = http.get(buildUrl(endpoints.cameras.list), defaultOptions);
    const eventsResponse = http.get(buildUrl(endpoints.events.list + '?limit=50'), defaultOptions);

    let cameraIds = [];
    let eventIds = [];

    try {
        if (camerasResponse.status === 200) {
            const data = JSON.parse(camerasResponse.body);
            // NEM-2075: API uses standardized pagination envelope with 'items' array
            cameraIds = data.items ? data.items.map(c => c.id) : [];
        }
    } catch (e) {
        console.warn('Could not parse cameras');
    }

    try {
        if (eventsResponse.status === 200) {
            const data = JSON.parse(eventsResponse.body);
            // NEM-2075: API uses standardized pagination envelope with 'items' array
            eventIds = data.items ? data.items.map(e => e.id) : [];
        }
    } catch (e) {
        console.warn('Could not parse events');
    }

    return {
        cameraIds,
        eventIds,
        hasCameras: cameraIds.length > 0,
        hasEvents: eventIds.length > 0,
    };
}

/**
 * Main test function
 */
export default function (data) {
    // Select scenario based on traffic weights
    const roll = Math.random();
    let cumulative = 0;

    if ((cumulative += TRAFFIC_WEIGHTS.events) > roll) {
        testEventsAPI(data);
    } else if ((cumulative += TRAFFIC_WEIGHTS.cameras) > roll) {
        testCamerasAPI(data);
    } else if ((cumulative += TRAFFIC_WEIGHTS.system) > roll) {
        testSystemAPI();
    } else if ((cumulative += TRAFFIC_WEIGHTS.websocket) > roll) {
        testWebSocket();
    } else {
        testDetectionsAPI();
    }

    // Think time
    sleep(Math.random() * 2 + 0.5);
}

/**
 * Events API Tests
 */
function testEventsAPI(data) {
    const scenario = Math.random();

    if (scenario < 0.4) {
        // List events
        group('Events - List', function () {
            apiRequestCount.add(1);
            const params = new URLSearchParams();
            params.append('limit', Math.floor(Math.random() * 30) + 10);
            if (Math.random() > 0.7) {
                params.append('risk_level', ['low', 'medium', 'high'][Math.floor(Math.random() * 3)]);
            }

            const response = http.get(
                buildUrl(endpoints.events.list + '?' + params.toString()),
                { ...defaultOptions, tags: { name: 'events_list', type: 'api' } }
            );

            apiDuration.add(response.timings.duration);
            apiErrorRate.add(response.status !== 200);

            check(response, {
                'events list OK': (r) => r.status === 200,
            });
        });
    } else if (scenario < 0.6) {
        // Event stats
        group('Events - Stats', function () {
            apiRequestCount.add(1);
            const response = http.get(
                buildUrl(endpoints.events.stats),
                { ...defaultOptions, tags: { name: 'events_stats', type: 'api' } }
            );

            apiDuration.add(response.timings.duration);
            apiErrorRate.add(response.status !== 200);

            check(response, {
                'events stats OK': (r) => r.status === 200,
            });
        });
    } else if (scenario < 0.8 && data.hasEvents) {
        // Get single event
        group('Events - Get', function () {
            apiRequestCount.add(1);
            const eventId = data.eventIds[Math.floor(Math.random() * data.eventIds.length)];
            const response = http.get(
                buildUrl(endpoints.events.get(eventId)),
                { ...defaultOptions, tags: { name: 'events_get', type: 'api' } }
            );

            apiDuration.add(response.timings.duration);
            apiErrorRate.add(response.status !== 200);

            check(response, {
                'events get OK': (r) => r.status === 200,
            });
        });
    } else {
        // Search events
        group('Events - Search', function () {
            apiRequestCount.add(1);
            const queries = ['person', 'vehicle', 'motion', 'delivery'];
            const q = queries[Math.floor(Math.random() * queries.length)];
            const response = http.get(
                buildUrl(endpoints.events.search + `?q=${q}`),
                { ...defaultOptions, tags: { name: 'events_search', type: 'api' } }
            );

            apiDuration.add(response.timings.duration);
            apiErrorRate.add(response.status !== 200);

            check(response, {
                'events search OK': (r) => r.status === 200,
            });
        });
    }
}

/**
 * Cameras API Tests
 */
function testCamerasAPI(data) {
    const scenario = Math.random();

    if (scenario < 0.4) {
        // List cameras
        group('Cameras - List', function () {
            apiRequestCount.add(1);
            const response = http.get(
                buildUrl(endpoints.cameras.list),
                { ...defaultOptions, tags: { name: 'cameras_list', type: 'api' } }
            );

            apiDuration.add(response.timings.duration);
            apiErrorRate.add(response.status !== 200);

            check(response, {
                'cameras list OK': (r) => r.status === 200,
            });
        });
    } else if (scenario < 0.7 && data.hasCameras) {
        // Get camera
        group('Cameras - Get', function () {
            apiRequestCount.add(1);
            const cameraId = data.cameraIds[Math.floor(Math.random() * data.cameraIds.length)];
            const response = http.get(
                buildUrl(endpoints.cameras.get(cameraId)),
                { ...defaultOptions, tags: { name: 'cameras_get', type: 'api' } }
            );

            apiDuration.add(response.timings.duration);
            apiErrorRate.add(response.status !== 200);

            check(response, {
                'cameras get OK': (r) => r.status === 200,
            });
        });
    } else if (data.hasCameras) {
        // Get snapshot
        group('Cameras - Snapshot', function () {
            apiRequestCount.add(1);
            const cameraId = data.cameraIds[Math.floor(Math.random() * data.cameraIds.length)];
            const response = http.get(
                buildUrl(endpoints.cameras.snapshot(cameraId)),
                { tags: { name: 'cameras_snapshot', type: 'media' } }
            );

            apiDuration.add(response.timings.duration);
            apiErrorRate.add(response.status !== 200 && response.status !== 404);

            check(response, {
                'cameras snapshot OK': (r) => r.status === 200 || r.status === 404,
            });
        });
    }
}

/**
 * System API Tests
 */
function testSystemAPI() {
    const scenario = Math.random();

    if (scenario < 0.4) {
        // Health check
        group('System - Health', function () {
            apiRequestCount.add(1);
            const response = http.get(
                buildUrl(endpoints.system.health),
                { ...defaultOptions, tags: { name: 'system_health', type: 'api' } }
            );

            apiDuration.add(response.timings.duration);
            apiErrorRate.add(response.status !== 200);

            check(response, {
                'system health OK': (r) => r.status === 200,
            });
        });
    } else if (scenario < 0.7) {
        // System stats
        group('System - Stats', function () {
            apiRequestCount.add(1);
            const response = http.get(
                buildUrl(endpoints.system.stats),
                { ...defaultOptions, tags: { name: 'system_stats', type: 'api' } }
            );

            apiDuration.add(response.timings.duration);
            apiErrorRate.add(response.status !== 200);

            check(response, {
                'system stats OK': (r) => r.status === 200,
            });
        });
    } else {
        // GPU stats
        group('System - GPU', function () {
            apiRequestCount.add(1);
            const response = http.get(
                buildUrl(endpoints.system.gpu),
                { ...defaultOptions, tags: { name: 'system_gpu', type: 'api' } }
            );

            apiDuration.add(response.timings.duration);
            apiErrorRate.add(response.status !== 200);

            check(response, {
                'system gpu OK': (r) => r.status === 200,
            });
        });
    }
}

/**
 * WebSocket Tests
 */
function testWebSocket() {
    const endpoint = Math.random() < 0.7
        ? endpoints.websocket.events
        : endpoints.websocket.system;

    let url = buildWsUrl(endpoint);
    if (API_KEY) {
        url += `?api_key=${API_KEY}`;
    }

    const startTime = Date.now();

    const response = ws.connect(url, {
        tags: { name: endpoint.replace('/ws/', 'ws_') },
    }, function (socket) {
        wsConnectTime.add(Date.now() - startTime);

        socket.on('message', function () {
            // Count messages received
        });

        socket.on('error', function () {
            wsConnectionErrors.add(1);
        });

        // Send ping
        socket.setTimeout(function () {
            socket.send('ping');
        }, 100);

        // Close after short duration
        socket.setTimeout(function () {
            socket.close(1000);
        }, Math.random() * 3000 + 2000);
    });

    check(response, {
        'WebSocket connected': (r) => r && r.status === 101,
    });

    if (!response || response.status !== 101) {
        wsConnectionErrors.add(1);
    }
}

/**
 * Detections API Tests
 */
function testDetectionsAPI() {
    group('Detections - List', function () {
        apiRequestCount.add(1);
        const params = new URLSearchParams();
        params.append('limit', '20');
        if (Math.random() > 0.5) {
            params.append('object_type', ['person', 'vehicle', 'animal'][Math.floor(Math.random() * 3)]);
        }

        const response = http.get(
            buildUrl(endpoints.detections.list + '?' + params.toString()),
            { ...defaultOptions, tags: { name: 'detections_list', type: 'api' } }
        );

        apiDuration.add(response.timings.duration);
        apiErrorRate.add(response.status !== 200);

        check(response, {
            'detections list OK': (r) => r.status === 200,
        });
    });
}

/**
 * Teardown function
 */
export function teardown(data) {
    console.log('Combined load test completed');
    console.log(`  Cameras available: ${data.hasCameras ? data.cameraIds.length : 0}`);
    console.log(`  Events available: ${data.hasEvents ? data.eventIds.length : 0}`);
}
