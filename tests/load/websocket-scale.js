/**
 * k6 Load Test: WebSocket Connection Scalability
 *
 * Tests WebSocket server's ability to handle high connection counts:
 * - Connection limit test: Verifies 1000+ concurrent connections
 * - Connection churn: Rapid connect/disconnect cycles
 * - Sustained connections: Long-lived connection stability
 *
 * Usage:
 *   k6 run tests/load/websocket-scale.js
 *   k6 run -e MAX_CONNECTIONS=2000 tests/load/websocket-scale.js
 *   k6 run -e WS_URL=ws://localhost:8000 tests/load/websocket-scale.js
 */

import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';
import {
    WS_URL,
    API_KEY,
    endpoints,
    buildWsUrl,
} from './config.js';

// Target connection count (configurable via env)
const MAX_CONNECTIONS = parseInt(__ENV.MAX_CONNECTIONS || '1000');
const RAMP_DURATION = __ENV.RAMP_DURATION || '2m';
const HOLD_DURATION = __ENV.HOLD_DURATION || '3m';

// Custom metrics for WebSocket scale testing
const wsConnectTime = new Trend('ws_scale_connect_time', true);
const wsActiveConnections = new Gauge('ws_scale_active_connections');
const wsConnectionSuccess = new Rate('ws_scale_connection_success');
const wsConnectionErrors = new Counter('ws_scale_connection_errors');
const wsMessagesReceived = new Counter('ws_scale_messages_received');
const wsConnectionDuration = new Trend('ws_scale_connection_duration', true);

// Test configuration for scale testing
export const options = {
    scenarios: {
        // Scenario 1: Ramp up to max connections and hold
        scale_test: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: RAMP_DURATION, target: MAX_CONNECTIONS },  // Ramp up
                { duration: HOLD_DURATION, target: MAX_CONNECTIONS },  // Hold at max
                { duration: '30s', target: 0 },                        // Ramp down
            ],
            gracefulRampDown: '30s',
        },
    },
    thresholds: {
        // Connection success rate should be >= 95%
        'ws_scale_connection_success': ['rate>=0.95'],
        // 95% of connections should establish within 2 seconds
        'ws_scale_connect_time': ['p(95)<2000', 'avg<1000'],
        // Less than 50 total connection errors (for 1000 VUs)
        'ws_scale_connection_errors': ['count<50'],
        // Connections should stay alive for at least 30 seconds on average
        'ws_scale_connection_duration': ['avg>30000'],
    },
    tags: {
        testSuite: 'websocket-scale',
    },
};

/**
 * Setup function
 */
export function setup() {
    console.log(`WebSocket Scale Test Configuration:`);
    console.log(`  Target Connections: ${MAX_CONNECTIONS}`);
    console.log(`  Ramp Duration: ${RAMP_DURATION}`);
    console.log(`  Hold Duration: ${HOLD_DURATION}`);
    console.log(`  WebSocket URL: ${WS_URL}`);

    return {
        wsUrl: WS_URL,
        maxConnections: MAX_CONNECTIONS,
    };
}

/**
 * Main test function - each VU maintains a long-lived WebSocket connection
 */
export default function (data) {
    const endpoint = Math.random() < 0.7
        ? endpoints.websocket.events   // 70% - Events stream
        : endpoints.websocket.system;  // 30% - System status stream

    let url = buildWsUrl(endpoint);
    if (API_KEY) {
        url += `?api_key=${API_KEY}`;
    }

    const startTime = Date.now();
    let connected = false;
    let messagesReceived = 0;

    const response = ws.connect(url, {
        tags: { name: 'websocket_scale' },
    }, function (socket) {
        const connectTime = Date.now() - startTime;
        wsConnectTime.add(connectTime);
        connected = true;
        wsConnectionSuccess.add(1);
        wsActiveConnections.add(1);

        // Handle incoming messages
        socket.on('message', function (message) {
            messagesReceived++;
            wsMessagesReceived.add(1);
        });

        // Handle errors
        socket.on('error', function (e) {
            console.error(`WebSocket error: ${e}`);
            wsConnectionErrors.add(1);
        });

        // Handle close
        socket.on('close', function (code, reason) {
            wsActiveConnections.add(-1);
            const duration = Date.now() - startTime;
            wsConnectionDuration.add(duration);
        });

        // Send periodic pings to keep connection alive
        socket.setInterval(function () {
            socket.send('ping');
        }, 5000);  // Every 5 seconds

        // Subscribe to events if on events endpoint
        if (endpoint === endpoints.websocket.events) {
            socket.setTimeout(function () {
                socket.send(JSON.stringify({
                    type: 'subscribe',
                    data: { cameras: ['all'] },
                }));
            }, 1000);
        }

        // Hold connection open for test duration (iteration-based)
        // Each VU will maintain its connection while the scenario runs
        // The ramping-vus executor handles scaling
        const holdTime = 60000 + Math.random() * 60000;  // 60-120 seconds
        socket.setTimeout(function () {
            socket.close(1000, 'Scale test iteration complete');
        }, holdTime);
    });

    // Check connection success
    check(response, {
        'WebSocket connection established': (r) => r && r.status === 101,
    });

    if (!connected) {
        wsConnectionSuccess.add(0);
        wsConnectionErrors.add(1);
    }

    // Brief pause between iterations
    sleep(Math.random() * 2 + 1);
}

/**
 * Teardown function
 */
export function teardown(data) {
    console.log('WebSocket scale test completed');
    console.log(`  Target was: ${data.maxConnections} concurrent connections`);
}
