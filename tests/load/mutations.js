/**
 * k6 Load Test: Mutation Endpoints (POST/PATCH/DELETE)
 *
 * Tests write operations including:
 * - Admin seed endpoints (development only)
 * - Camera creation/update
 * - Event updates (mark as reviewed)
 * - System configuration updates
 *
 * Usage:
 *   k6 run tests/load/mutations.js
 *   k6 run -e LOAD_PROFILE=stress tests/load/mutations.js
 *   k6 run -e ADMIN_API_KEY=your-key tests/load/mutations.js
 *
 * Note: This test requires ADMIN_ENABLED=true and DEBUG=true for seed endpoints.
 *       Run in development environment only.
 */

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import {
    BASE_URL,
    defaultOptions,
    adminOptions,
    standardThresholds,
    endpoints,
    getLoadStages,
    buildUrl,
} from './config.js';

// Custom metrics
const createDuration = new Trend('mutation_create_duration', true);
const updateDuration = new Trend('mutation_update_duration', true);
const mutationErrorRate = new Rate('mutation_error_rate');
const mutationRequestCount = new Counter('mutation_request_count');

// Test configuration - use lighter load for mutation tests with CI-friendly thresholds
export const options = {
    stages: [
        { duration: '20s', target: 5 },   // Ramp up slowly
        { duration: '1m', target: 5 },    // Steady state with fewer VUs
        { duration: '10s', target: 0 },   // Ramp down
    ],
    thresholds: {
        ...standardThresholds,
        // Mutation thresholds relaxed for CI environment variability
        'mutation_create_duration': ['p(95)<5000', 'avg<2500'],
        'mutation_update_duration': ['p(95)<2500', 'avg<1250'],
        'mutation_error_rate': ['rate<0.15'],  // 15% error rate acceptable for admin endpoints in CI
    },
    tags: {
        testSuite: 'mutations',
    },
};

// Counter for generating unique names
let cameraCounter = 0;

/**
 * Setup function
 */
export function setup() {
    // Check if admin endpoints are available
    const healthCheck = http.get(buildUrl('/api/system/health/ready'));

    if (healthCheck.status !== 200) {
        console.warn('API not ready, tests may fail');
    }

    // Get existing cameras and events for update tests
    const camerasResponse = http.get(buildUrl(endpoints.cameras.list), defaultOptions);
    const eventsResponse = http.get(buildUrl(endpoints.events.list + '?limit=20'), defaultOptions);

    let cameraIds = [];
    let eventIds = [];

    if (camerasResponse.status === 200) {
        try {
            const data = JSON.parse(camerasResponse.body);
            // NEM-2075: API uses standardized pagination envelope with 'items' array
            cameraIds = data.items ? data.items.map(c => c.id) : [];
        } catch (e) {
            console.warn('Could not parse cameras');
        }
    }

    if (eventsResponse.status === 200) {
        try {
            const data = JSON.parse(eventsResponse.body);
            // NEM-2075: API uses standardized pagination envelope with 'items' array
            eventIds = data.items ? data.items.map(e => e.id) : [];
        } catch (e) {
            console.warn('Could not parse events');
        }
    }

    // Check admin endpoint availability
    const adminCheck = http.post(
        buildUrl(endpoints.admin.seedCameras),
        JSON.stringify({ count: 0, clear_existing: false }),
        adminOptions
    );
    const adminAvailable = adminCheck.status !== 403 && adminCheck.status !== 401;

    return {
        cameraIds,
        eventIds,
        hasEvents: eventIds.length > 0,
        hasCameras: cameraIds.length > 0,
        adminAvailable,
    };
}

/**
 * Main test function
 */
export default function (data) {
    const scenario = Math.random();

    if (scenario < 0.3 && data.hasEvents) {
        // 30% - Update event (mark as reviewed)
        testUpdateEvent(data.eventIds);
    } else if (scenario < 0.5 && data.adminAvailable) {
        // 20% - Admin seed cameras (if available)
        testSeedCameras();
    } else if (scenario < 0.7 && data.adminAvailable) {
        // 20% - Admin seed events (if available)
        testSeedEvents();
    } else if (scenario < 0.85) {
        // 15% - Create camera
        testCreateCamera();
    } else {
        // 15% - Frontend log submission
        testSubmitLog();
    }

    sleep(Math.random() * 2 + 1);
}

/**
 * Test: Update Event (Mark as Reviewed)
 *
 * Tests PATCH /api/events/{event_id}
 */
function testUpdateEvent(eventIds) {
    if (!eventIds || eventIds.length === 0) {
        return;
    }

    group('Update Event', function () {
        mutationRequestCount.add(1);

        const eventId = eventIds[Math.floor(Math.random() * eventIds.length)];
        const url = buildUrl(endpoints.events.get(eventId));

        const payload = JSON.stringify({
            reviewed: Math.random() > 0.5,
            notes: `Load test update at ${new Date().toISOString()}`,
        });

        const response = http.patch(url, payload, {
            ...defaultOptions,
            tags: { name: 'update_event', type: 'mutation' },
        });

        updateDuration.add(response.timings.duration);
        mutationErrorRate.add(response.status !== 200);

        check(response, {
            'update event status is 200': (r) => r.status === 200,
            'update event returns updated data': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return body.id === eventId;
                } catch {
                    return false;
                }
            },
            'update event response time OK': (r) => r.timings.duration < 2500,
        });
    });
}

/**
 * Test: Seed Cameras (Admin)
 *
 * Tests POST /api/admin/seed/cameras
 */
function testSeedCameras() {
    group('Seed Cameras', function () {
        mutationRequestCount.add(1);

        const url = buildUrl(endpoints.admin.seedCameras);
        const payload = JSON.stringify({
            count: Math.floor(Math.random() * 3) + 1,  // 1-3 cameras
            clear_existing: false,
            create_folders: false,
        });

        const response = http.post(url, payload, {
            ...adminOptions,
            tags: { name: 'seed_cameras', type: 'admin' },
        });

        createDuration.add(response.timings.duration);
        // Admin endpoints may return 403 if not enabled
        mutationErrorRate.add(response.status !== 200 && response.status !== 403 && response.status !== 401);

        check(response, {
            'seed cameras status is success or forbidden': (r) =>
                r.status === 200 || r.status === 403 || r.status === 401,
            'seed cameras response time OK': (r) => r.timings.duration < 5000,
        });
    });
}

/**
 * Test: Seed Events (Admin)
 *
 * Tests POST /api/admin/seed/events
 */
function testSeedEvents() {
    group('Seed Events', function () {
        mutationRequestCount.add(1);

        const url = buildUrl(endpoints.admin.seedEvents);
        const payload = JSON.stringify({
            count: Math.floor(Math.random() * 5) + 1,  // 1-5 events
            clear_existing: false,
        });

        const response = http.post(url, payload, {
            ...adminOptions,
            tags: { name: 'seed_events', type: 'admin' },
        });

        createDuration.add(response.timings.duration);
        mutationErrorRate.add(response.status !== 200 && response.status !== 400 &&
                             response.status !== 403 && response.status !== 401);

        check(response, {
            'seed events status is acceptable': (r) =>
                r.status === 200 || r.status === 400 || r.status === 403 || r.status === 401,
            'seed events response time OK': (r) => r.timings.duration < 10000,
        });
    });
}

/**
 * Test: Create Camera
 *
 * Tests POST /api/cameras
 */
function testCreateCamera() {
    group('Create Camera', function () {
        mutationRequestCount.add(1);

        // Generate unique camera name to avoid conflicts
        const uniqueId = `${__VU}-${__ITER}-${Date.now()}`;
        const cameraName = `Load Test Camera ${uniqueId}`;

        const url = buildUrl(endpoints.cameras.create);
        const payload = JSON.stringify({
            name: cameraName,
            folder_path: `/tmp/load-test-cameras/${uniqueId}`,
            status: 'offline',
        });

        const response = http.post(url, payload, {
            ...defaultOptions,
            tags: { name: 'create_camera', type: 'mutation' },
        });

        createDuration.add(response.timings.duration);
        // 409 Conflict is acceptable if camera already exists
        mutationErrorRate.add(response.status !== 201 && response.status !== 409);

        check(response, {
            'create camera status is 201 or 409': (r) => r.status === 201 || r.status === 409,
            'create camera returns camera data': (r) => {
                if (r.status === 201) {
                    try {
                        const body = JSON.parse(r.body);
                        return body.name === cameraName;
                    } catch {
                        return false;
                    }
                }
                return true; // Skip for 409
            },
            'create camera response time OK': (r) => r.timings.duration < 5000,
        });
    });
}

/**
 * Test: Submit Frontend Log
 *
 * Tests POST /api/logs/frontend
 */
function testSubmitLog() {
    group('Submit Log', function () {
        mutationRequestCount.add(1);

        const url = buildUrl('/api/logs/frontend');
        const logLevels = ['INFO', 'WARNING', 'ERROR', 'DEBUG'];
        const components = ['Dashboard', 'CameraGrid', 'EventList', 'RiskGauge'];

        const payload = JSON.stringify({
            level: logLevels[Math.floor(Math.random() * logLevels.length)],
            message: `Load test log message at ${new Date().toISOString()}`,
            component: components[Math.floor(Math.random() * components.length)],
            timestamp: new Date().toISOString(),
        });

        const response = http.post(url, payload, {
            ...defaultOptions,
            tags: { name: 'submit_log', type: 'mutation' },
        });

        createDuration.add(response.timings.duration);
        mutationErrorRate.add(response.status !== 201 && response.status !== 200);

        check(response, {
            'submit log status is success': (r) => r.status === 200 || r.status === 201,
            'submit log response time OK': (r) => r.timings.duration < 2500,
        });
    });
}

/**
 * Teardown function
 */
export function teardown(data) {
    console.log(`Mutation tests completed. Admin available: ${data.adminAvailable}`);
}
