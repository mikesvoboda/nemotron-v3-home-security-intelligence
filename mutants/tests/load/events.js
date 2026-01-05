/**
 * k6 Load Test: Events API
 *
 * Tests the /api/events endpoints including:
 * - List events with pagination
 * - Get event statistics
 * - Search events
 * - Get single event details
 * - Get event detections
 *
 * Usage:
 *   k6 run tests/load/events.js
 *   k6 run -e LOAD_PROFILE=stress tests/load/events.js
 *   k6 run -e BASE_URL=http://localhost:8000 tests/load/events.js
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
const eventListDuration = new Trend('event_list_duration', true);
const eventStatsDuration = new Trend('event_stats_duration', true);
const eventSearchDuration = new Trend('event_search_duration', true);
const eventGetDuration = new Trend('event_get_duration', true);
const eventErrorRate = new Rate('event_error_rate');
const eventRequestCount = new Counter('event_request_count');

// Test configuration
export const options = {
    stages: getLoadStages(),
    thresholds: {
        ...standardThresholds,
        // Events-specific thresholds
        'event_list_duration': ['p(95)<400', 'avg<200'],
        'event_stats_duration': ['p(95)<300', 'avg<150'],
        'event_search_duration': ['p(95)<500', 'avg<250'],
        'event_get_duration': ['p(95)<200', 'avg<100'],
        'event_error_rate': ['rate<0.02'],  // Less than 2% errors
    },
    // Tags for organizing results
    tags: {
        testSuite: 'events',
    },
};

// Sample search queries for realistic load testing
const searchQueries = [
    'person',
    'vehicle',
    'suspicious',
    'motion',
    'delivery',
    'front door',
    'backyard',
    'night',
    'package',
    'visitor',
];

// Risk levels for filtering
const riskLevels = ['low', 'medium', 'high', 'critical'];

/**
 * Setup function - runs once before all VUs start
 */
export function setup() {
    // Verify the API is reachable
    const healthCheck = http.get(buildUrl('/api/system/health/ready'));

    if (healthCheck.status !== 200) {
        console.error(`API not ready. Status: ${healthCheck.status}`);
        console.error(`Response: ${healthCheck.body}`);
        // Continue anyway - the test will show failures
    }

    // Try to get some events to use for detail tests
    const eventsResponse = http.get(buildUrl(endpoints.events.list + '?limit=10'), defaultOptions);
    let eventIds = [];

    if (eventsResponse.status === 200) {
        try {
            const data = JSON.parse(eventsResponse.body);
            eventIds = data.events ? data.events.map(e => e.id) : [];
        } catch (e) {
            console.warn('Could not parse events response:', e);
        }
    }

    return {
        eventIds: eventIds,
        hasEvents: eventIds.length > 0,
    };
}

/**
 * Main test function - executed by each VU
 */
export default function (data) {
    // Randomly select which test scenario to run
    // This simulates realistic mixed traffic patterns
    const scenario = Math.random();

    if (scenario < 0.4) {
        // 40% - List events (most common operation)
        testListEvents();
    } else if (scenario < 0.6) {
        // 20% - Get event statistics
        testEventStats();
    } else if (scenario < 0.75) {
        // 15% - Search events
        testSearchEvents();
    } else if (scenario < 0.9 && data.hasEvents) {
        // 15% - Get event details (if events exist)
        testGetEvent(data.eventIds);
    } else if (data.hasEvents) {
        // 10% - Get event detections (if events exist)
        testGetEventDetections(data.eventIds);
    } else {
        // Fallback to list events if no events exist
        testListEvents();
    }

    // Think time between requests (simulates real user behavior)
    sleep(Math.random() * 2 + 0.5); // 0.5-2.5 seconds
}

/**
 * Test: List Events
 *
 * Tests GET /api/events with various filters and pagination
 */
function testListEvents() {
    group('List Events', function () {
        eventRequestCount.add(1);

        // Build query parameters
        const params = new URLSearchParams();

        // Randomly add filters to simulate real usage
        if (Math.random() > 0.5) {
            params.append('limit', Math.floor(Math.random() * 50) + 10);
        }
        if (Math.random() > 0.7) {
            params.append('offset', Math.floor(Math.random() * 100));
        }
        if (Math.random() > 0.8) {
            params.append('risk_level', riskLevels[Math.floor(Math.random() * riskLevels.length)]);
        }
        if (Math.random() > 0.9) {
            params.append('reviewed', Math.random() > 0.5 ? 'true' : 'false');
        }

        const queryString = params.toString() ? `?${params.toString()}` : '';
        const url = buildUrl(endpoints.events.list + queryString);

        const response = http.get(url, {
            ...defaultOptions,
            tags: { name: 'list_events', type: 'api' },
        });

        // Record metrics
        eventListDuration.add(response.timings.duration);
        eventErrorRate.add(response.status !== 200);

        // Validate response
        const success = check(response, {
            'list events status is 200': (r) => r.status === 200,
            'list events has events array': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return Array.isArray(body.events);
                } catch {
                    return false;
                }
            },
            'list events has count': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return typeof body.count === 'number';
                } catch {
                    return false;
                }
            },
            'list events response time OK': (r) => r.timings.duration < 500,
        });

        if (!success) {
            console.warn(`List events failed: ${response.status} - ${response.body.substring(0, 200)}`);
        }
    });
}

/**
 * Test: Event Statistics
 *
 * Tests GET /api/events/stats
 */
function testEventStats() {
    group('Event Statistics', function () {
        eventRequestCount.add(1);

        const url = buildUrl(endpoints.events.stats);

        const response = http.get(url, {
            ...defaultOptions,
            tags: { name: 'event_stats', type: 'api' },
        });

        // Record metrics
        eventStatsDuration.add(response.timings.duration);
        eventErrorRate.add(response.status !== 200);

        // Validate response
        check(response, {
            'event stats status is 200': (r) => r.status === 200,
            'event stats has total_events': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return typeof body.total_events === 'number';
                } catch {
                    return false;
                }
            },
            'event stats has events_by_risk_level': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return body.events_by_risk_level !== undefined;
                } catch {
                    return false;
                }
            },
            'event stats response time OK': (r) => r.timings.duration < 300,
        });
    });
}

/**
 * Test: Search Events
 *
 * Tests GET /api/events/search with various queries
 */
function testSearchEvents() {
    group('Search Events', function () {
        eventRequestCount.add(1);

        // Select a random search query
        const query = searchQueries[Math.floor(Math.random() * searchQueries.length)];
        const params = new URLSearchParams({ q: query });

        // Optionally add filters
        if (Math.random() > 0.7) {
            params.append('limit', '25');
        }
        if (Math.random() > 0.8) {
            params.append('severity', riskLevels[Math.floor(Math.random() * riskLevels.length)]);
        }

        const url = buildUrl(endpoints.events.search + '?' + params.toString());

        const response = http.get(url, {
            ...defaultOptions,
            tags: { name: 'search_events', type: 'api' },
        });

        // Record metrics
        eventSearchDuration.add(response.timings.duration);
        eventErrorRate.add(response.status !== 200);

        // Validate response
        check(response, {
            'search events status is 200': (r) => r.status === 200,
            'search events has results': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return Array.isArray(body.results);
                } catch {
                    return false;
                }
            },
            'search events has total_count': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return typeof body.total_count === 'number';
                } catch {
                    return false;
                }
            },
            'search events response time OK': (r) => r.timings.duration < 500,
        });
    });
}

/**
 * Test: Get Single Event
 *
 * Tests GET /api/events/{event_id}
 */
function testGetEvent(eventIds) {
    if (!eventIds || eventIds.length === 0) {
        return;
    }

    group('Get Event', function () {
        eventRequestCount.add(1);

        // Select a random event ID
        const eventId = eventIds[Math.floor(Math.random() * eventIds.length)];
        const url = buildUrl(endpoints.events.get(eventId));

        const response = http.get(url, {
            ...defaultOptions,
            tags: { name: 'get_event', type: 'api' },
        });

        // Record metrics
        eventGetDuration.add(response.timings.duration);
        eventErrorRate.add(response.status !== 200);

        // Validate response
        check(response, {
            'get event status is 200': (r) => r.status === 200,
            'get event has id': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return body.id !== undefined;
                } catch {
                    return false;
                }
            },
            'get event has risk_score': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return typeof body.risk_score === 'number' || body.risk_score === null;
                } catch {
                    return false;
                }
            },
            'get event response time OK': (r) => r.timings.duration < 200,
        });
    });
}

/**
 * Test: Get Event Detections
 *
 * Tests GET /api/events/{event_id}/detections
 */
function testGetEventDetections(eventIds) {
    if (!eventIds || eventIds.length === 0) {
        return;
    }

    group('Get Event Detections', function () {
        eventRequestCount.add(1);

        // Select a random event ID
        const eventId = eventIds[Math.floor(Math.random() * eventIds.length)];
        const url = buildUrl(endpoints.events.detections(eventId));

        const response = http.get(url, {
            ...defaultOptions,
            tags: { name: 'get_event_detections', type: 'api' },
        });

        // Record metrics (reuse event_get as it's similar)
        eventGetDuration.add(response.timings.duration);
        eventErrorRate.add(response.status !== 200);

        // Validate response
        check(response, {
            'get detections status is 200': (r) => r.status === 200,
            'get detections has array': (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return Array.isArray(body.detections);
                } catch {
                    return false;
                }
            },
            'get detections response time OK': (r) => r.timings.duration < 300,
        });
    });
}

/**
 * Teardown function - runs once after all VUs finish
 */
export function teardown(data) {
    console.log(`Test completed. Events found: ${data.hasEvents ? data.eventIds.length : 0}`);
}
