/**
 * k6 Load Test: WebSocket Connections
 *
 * Tests WebSocket endpoints for real-time event streaming:
 * - /ws/events - Security event stream
 * - /ws/system - System status stream
 *
 * Usage:
 *   k6 run tests/load/websocket.js
 *   k6 run -e LOAD_PROFILE=stress tests/load/websocket.js
 *   k6 run -e WS_URL=ws://localhost:8000 tests/load/websocket.js
 */

import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';
import {
    WS_URL,
    API_KEY,
    wsThresholds,
    endpoints,
    getLoadStages,
    buildWsUrl,
} from './config.js';

// Custom metrics for WebSocket
const wsConnectTime = new Trend('ws_connect_time', true);
const wsMessageReceived = new Counter('ws_messages_received');
const wsPingPongLatency = new Trend('ws_ping_pong_latency', true);
const wsConnectionErrors = new Rate('ws_connection_errors');
const wsSessionDuration = new Trend('ws_session_duration', true);
const wsActiveConnections = new Gauge('ws_active_connections');

// Test configuration with CI-friendly thresholds
export const options = {
    stages: getLoadStages(),
    thresholds: {
        ...wsThresholds,
        // WebSocket thresholds relaxed for CI environment variability
        'ws_connect_time': ['p(95)<2000', 'avg<1000'],
        'ws_ping_pong_latency': ['p(95)<500', 'avg<250'],
        'ws_connection_errors': ['rate<0.10'],  // 10% errors acceptable in CI
        'ws_session_duration': ['avg>2000'],  // Sessions should last at least 2 seconds (CI-friendly)
    },
    tags: {
        testSuite: 'websocket',
    },
};

// WebSocket message types
const MessageTypes = {
    PING: 'ping',
    PONG: 'pong',
    EVENT: 'event',
    SYSTEM_STATUS: 'system_status',
    SUBSCRIBE: 'subscribe',
    UNSUBSCRIBE: 'unsubscribe',
};

/**
 * Setup function
 */
export function setup() {
    console.log(`WebSocket tests starting against ${WS_URL}`);
    return {
        wsUrl: WS_URL,
    };
}

/**
 * Main test function - executed by each VU
 */
export default function (data) {
    // Randomly choose which WebSocket endpoint to test
    const endpoint = Math.random() < 0.7
        ? endpoints.websocket.events   // 70% - Events stream (primary use case)
        : endpoints.websocket.system;  // 30% - System status stream

    testWebSocketConnection(endpoint);

    // Brief pause between connection attempts
    sleep(Math.random() * 3 + 1); // 1-4 seconds
}

/**
 * Test WebSocket Connection
 *
 * Establishes a WebSocket connection, sends ping messages,
 * and validates responses
 */
function testWebSocketConnection(endpoint) {
    let url = buildWsUrl(endpoint);

    // Add API key if provided
    if (API_KEY) {
        url += `?api_key=${API_KEY}`;
    }

    const startTime = Date.now();
    let connected = false;
    let messagesReceived = 0;
    let pingTime = 0;

    const response = ws.connect(url, {
        tags: { name: endpoint.replace('/ws/', 'ws_') },
    }, function (socket) {
        // Connection opened
        const connectTime = Date.now() - startTime;
        wsConnectTime.add(connectTime);
        connected = true;
        wsActiveConnections.add(1);

        // Handle incoming messages
        socket.on('message', function (message) {
            messagesReceived++;
            wsMessageReceived.add(1);

            try {
                const data = JSON.parse(message);

                // Handle pong response for latency measurement
                if (data.type === MessageTypes.PONG) {
                    if (pingTime > 0) {
                        const latency = Date.now() - pingTime;
                        wsPingPongLatency.add(latency);
                        pingTime = 0;
                    }
                }

                // Log interesting messages
                if (data.type === MessageTypes.EVENT) {
                    console.log(`Received event: ${JSON.stringify(data.data).substring(0, 100)}`);
                }
            } catch (e) {
                // Plain text message (legacy format)
                if (message === 'pong') {
                    if (pingTime > 0) {
                        wsPingPongLatency.add(Date.now() - pingTime);
                        pingTime = 0;
                    }
                }
            }
        });

        // Handle errors
        socket.on('error', function (e) {
            console.error(`WebSocket error on ${endpoint}: ${e}`);
            wsConnectionErrors.add(1);
        });

        // Handle close
        socket.on('close', function (code, reason) {
            wsActiveConnections.add(-1);
            const sessionDuration = Date.now() - startTime;
            wsSessionDuration.add(sessionDuration);
        });

        // Send ping immediately after connection
        socket.setTimeout(function () {
            sendPing(socket);
        }, 100);

        // Send periodic pings to keep connection alive and measure latency
        socket.setInterval(function () {
            sendPing(socket);
        }, 2000); // Every 2 seconds

        // Send JSON ping (test message validation)
        socket.setTimeout(function () {
            sendJsonMessage(socket, { type: 'ping' });
        }, 1000);

        // Test subscribe message (if events endpoint)
        if (endpoint === endpoints.websocket.events) {
            socket.setTimeout(function () {
                sendJsonMessage(socket, {
                    type: 'subscribe',
                    data: { cameras: ['front_door', 'backyard'] },
                });
            }, 1500);
        }

        // Keep connection open for varying duration
        // This simulates real users who stay connected for different periods
        const sessionLength = Math.random() * 8000 + 5000; // 5-13 seconds

        socket.setTimeout(function () {
            socket.close(1000, 'Load test complete');
        }, sessionLength);
    });

    // Capture ping time for latency calculation
    function sendPing(socket) {
        pingTime = Date.now();
        socket.send('ping');  // Legacy format
    }

    function sendJsonMessage(socket, message) {
        socket.send(JSON.stringify(message));
    }

    // Check connection success
    check(response, {
        'WebSocket connection established': (r) => r && r.status === 101,
        'WebSocket received messages': () => messagesReceived > 0 || !connected,
    });

    if (!connected) {
        wsConnectionErrors.add(1);
    }
}

/**
 * Test concurrent WebSocket connections
 *
 * This tests the server's ability to handle multiple simultaneous connections
 */
export function testConcurrentConnections() {
    const connections = [];
    const numConnections = 5; // Each VU opens multiple connections

    for (let i = 0; i < numConnections; i++) {
        const endpoint = i % 2 === 0
            ? endpoints.websocket.events
            : endpoints.websocket.system;

        const url = buildWsUrl(endpoint) + (API_KEY ? `?api_key=${API_KEY}` : '');

        const conn = ws.connect(url, {}, function (socket) {
            socket.on('message', function () {
                wsMessageReceived.add(1);
            });

            // Keep alive for 3 seconds
            socket.setTimeout(function () {
                socket.close(1000);
            }, 3000);
        });

        connections.push(conn);
    }

    // Brief sleep while connections are active
    sleep(4);
}

/**
 * Teardown function
 */
export function teardown(data) {
    console.log('WebSocket load test completed');
}
