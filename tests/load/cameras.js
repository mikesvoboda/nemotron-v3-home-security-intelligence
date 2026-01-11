/**
 * k6 Load Test: Cameras API
 *
 * Tests the /api/cameras endpoints including:
 * - List cameras
 * - Get single camera details
 * - Camera snapshots (media serving)
 * - Camera baselines
 *
 * Usage:
 *   k6 run tests/load/cameras.js
 *   k6 run -e LOAD_PROFILE=stress tests/load/cameras.js
 *   k6 run -e BASE_URL=http://localhost:8000 tests/load/cameras.js
 */

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import {
    BASE_URL,
    defaultOptions,
    standardThresholds,
    endpoints,
    getLoadStages,
    buildUrl,
} from './config.js';

// Custom metrics
const cameraListDuration = new Trend('camera_list_duration', true);
const cameraGetDuration = new Trend('camera_get_duration', true);
const cameraSnapshotDuration = new Trend('camera_snapshot_duration', true);
const cameraBaselineDuration = new Trend('camera_baseline_duration', true);
const cameraErrorRate = new Rate('camera_error_rate');
const cameraRequestCount = new Counter('camera_request_count');

// Test configuration
export const options = {
    stages: getLoadStages(),
    thresholds: {
        ...standardThresholds,
        // Cameras-specific thresholds
        'camera_list_duration': ['p(95)<300', 'avg<150'],
        'camera_get_duration': ['p(95)<200', 'avg<100'],
        'camera_snapshot_duration': ['p(95)<1000', 'avg<500'],  // Snapshots can be larger
        'camera_baseline_duration': ['p(95)<400', 'avg<200'],
        'camera_error_rate': ['rate<0.02'],
    },
    tags: {
        testSuite: 'cameras',
    },
};

// Camera status values for filtering
const cameraStatuses = ['online', 'offline'];

/**
 * Setup function - runs once before all VUs start
 */
export function setup() {
    // Verify the API is reachable
    const healthCheck = http.get(buildUrl('/api/system/health/ready'));

    if (healthCheck.status !== 200) {
        console.error(`API not ready. Status: ${healthCheck.status}`);
    }

    // Get list of cameras for testing
    const camerasResponse = http.get(buildUrl(endpoints.cameras.list), defaultOptions);
    let cameraIds = [];

    if (camerasResponse.status === 200) {
        try {
            const data = JSON.parse(camerasResponse.body);
            // NEM-2075: API uses standardized pagination envelope with 'items' array
            cameraIds = data.items ? data.items.map(c => c.id) : [];
        } catch (e) {
            console.warn('Could not parse cameras response:', e);
        }
    }

    return {
        cameraIds: cameraIds,
        hasCameras: cameraIds.length > 0,
    };
}

/**
 * Main test function - executed by each VU
 */
export default function (data) {
    // Randomly select which test scenario to run
    const scenario = Math.random();

    if (scenario < 0.35) {
        // 35% - List cameras (common dashboard operation)
        testListCameras();
    } else if (scenario < 0.55 && data.hasCameras) {
        // 20% - Get single camera
        testGetCamera(data.cameraIds);
    } else if (scenario < 0.80 && data.hasCameras) {
        // 25% - Get camera snapshot (image serving)
        testGetSnapshot(data.cameraIds);
    } else if (data.hasCameras) {
        // 20% - Get camera baseline
        testGetBaseline(data.cameraIds);
    } else {
        // Fallback to list cameras
        testListCameras();
    }

    // Think time
    sleep(Math.random() * 2 + 0.5);
}

/**
 * Test: List Cameras
 *
 * Tests GET /api/cameras with optional status filter
 */
function testListCameras() {
    group('List Cameras', function () {
        cameraRequestCount.add(1);

        // Optionally filter by status
        let url = buildUrl(endpoints.cameras.list);
        if (Math.random() > 0.7) {
            const status = cameraStatuses[Math.floor(Math.random() * cameraStatuses.length)];
            url += `?status=${status}`;
        }

        const response = http.get(url, {
            ...defaultOptions,
            tags: { name: 'list_cameras', type: 'api' },
        });

        // Record metrics
        cameraListDuration.add(response.timings.duration);
        cameraErrorRate.add(response.status !== 200);

        // Validate response
        // NEM-2075: API uses standardized pagination envelope with 'items' array
        const success = check(response, {
            'list cameras status is 200': (r) => r.status === 200,
            'list cameras has items array': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return Array.isArray(body.items);
                } catch {
                    return false;
                }
            },
            'list cameras has pagination total': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return body.pagination && typeof body.pagination.total === 'number';
                } catch {
                    return false;
                }
            },
            'list cameras response time OK': (r) => r.timings.duration < 300,
        });

        if (!success) {
            console.warn(`List cameras failed: ${response.status}`);
        }
    });
}

/**
 * Test: Get Single Camera
 *
 * Tests GET /api/cameras/{camera_id}
 */
function testGetCamera(cameraIds) {
    if (!cameraIds || cameraIds.length === 0) {
        return;
    }

    group('Get Camera', function () {
        cameraRequestCount.add(1);

        const cameraId = cameraIds[Math.floor(Math.random() * cameraIds.length)];
        const url = buildUrl(endpoints.cameras.get(cameraId));

        const response = http.get(url, {
            ...defaultOptions,
            tags: { name: 'get_camera', type: 'api' },
        });

        // Record metrics
        cameraGetDuration.add(response.timings.duration);
        cameraErrorRate.add(response.status !== 200);

        // Validate response
        check(response, {
            'get camera status is 200': (r) => r.status === 200,
            'get camera has id': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return body.id !== undefined;
                } catch {
                    return false;
                }
            },
            'get camera has name': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return typeof body.name === 'string';
                } catch {
                    return false;
                }
            },
            'get camera has status': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return typeof body.status === 'string';
                } catch {
                    return false;
                }
            },
            'get camera response time OK': (r) => r.timings.duration < 200,
        });
    });
}

/**
 * Test: Get Camera Snapshot
 *
 * Tests GET /api/cameras/{camera_id}/snapshot
 * This endpoint serves image files, so we expect different behavior
 */
function testGetSnapshot(cameraIds) {
    if (!cameraIds || cameraIds.length === 0) {
        return;
    }

    group('Get Camera Snapshot', function () {
        cameraRequestCount.add(1);

        const cameraId = cameraIds[Math.floor(Math.random() * cameraIds.length)];
        const url = buildUrl(endpoints.cameras.snapshot(cameraId));

        const response = http.get(url, {
            // Don't include JSON content-type for image requests
            tags: { name: 'get_snapshot', type: 'media' },
        });

        // Record metrics
        cameraSnapshotDuration.add(response.timings.duration);
        // 404 is acceptable if no snapshot exists
        cameraErrorRate.add(response.status !== 200 && response.status !== 404);

        // Validate response
        check(response, {
            'get snapshot status is 200 or 404': (r) => r.status === 200 || r.status === 404,
            'get snapshot has correct content type': (r) => {
                if (r.status === 200) {
                    const contentType = r.headers['Content-Type'] || '';
                    return contentType.startsWith('image/');
                }
                return true; // Skip check for 404
            },
            'get snapshot response time OK': (r) => r.timings.duration < 1000,
        });
    });
}

/**
 * Test: Get Camera Baseline
 *
 * Tests GET /api/cameras/{camera_id}/baseline
 */
function testGetBaseline(cameraIds) {
    if (!cameraIds || cameraIds.length === 0) {
        return;
    }

    group('Get Camera Baseline', function () {
        cameraRequestCount.add(1);

        const cameraId = cameraIds[Math.floor(Math.random() * cameraIds.length)];
        const url = buildUrl(endpoints.cameras.baseline(cameraId));

        const response = http.get(url, {
            ...defaultOptions,
            tags: { name: 'get_baseline', type: 'api' },
        });

        // Record metrics
        cameraBaselineDuration.add(response.timings.duration);
        cameraErrorRate.add(response.status !== 200);

        // Validate response
        check(response, {
            'get baseline status is 200': (r) => r.status === 200,
            'get baseline has camera_id': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return body.camera_id !== undefined;
                } catch {
                    return false;
                }
            },
            'get baseline has data_points': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return typeof body.data_points === 'number';
                } catch {
                    return false;
                }
            },
            'get baseline response time OK': (r) => r.timings.duration < 400,
        });
    });
}

/**
 * Teardown function
 */
export function teardown(data) {
    console.log(`Test completed. Cameras found: ${data.hasCameras ? data.cameraIds.length : 0}`);
}
