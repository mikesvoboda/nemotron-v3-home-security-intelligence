/**
 * WebSocket Mock Utilities for E2E Tests
 *
 * Provides comprehensive utilities for simulating WebSocket behaviors in E2E tests.
 * Since Playwright cannot directly intercept WebSocket connections, these utilities
 * work by injecting a mock WebSocket implementation into the page that:
 * 1. Intercepts WebSocket constructor calls
 * 2. Simulates connection states (open, close, error, reconnecting)
 * 3. Allows tests to dispatch messages and events to the application
 * 4. Supports testing connection error and recovery scenarios
 *
 * @example
 * ```typescript
 * test('real-time events update dashboard', async ({ page }) => {
 *   await setupApiMocks(page);
 *   const wsMock = await setupWebSocketMock(page);
 *
 *   await page.goto('/');
 *   await wsMock.waitForConnection();
 *
 *   // Simulate receiving a new event
 *   await wsMock.sendMessage('events', {
 *     type: 'event',
 *     data: { id: 1, camera_id: 'cam-1', risk_score: 75, ... }
 *   });
 *
 *   // Verify UI updated
 *   await expect(page.getByText('New high-risk event')).toBeVisible();
 * });
 * ```
 */

import type { Page } from '@playwright/test';

/**
 * WebSocket channel types matching the application's WebSocket endpoints
 */
export type WebSocketChannel = 'events' | 'system';

/**
 * WebSocket connection state
 */
export type WebSocketConnectionState = 'connecting' | 'connected' | 'disconnected' | 'reconnecting' | 'failed';

/**
 * WebSocket message types that can be sent to the application
 */
export interface WebSocketEventMessage {
  type: 'event';
  data: {
    id: number;
    event_id?: number;
    batch_id?: string;
    camera_id: string;
    camera_name?: string;
    risk_score: number;
    risk_level: 'low' | 'medium' | 'high' | 'critical';
    summary: string;
    timestamp?: string;
    started_at?: string;
  };
}

export interface WebSocketSystemMessage {
  type: 'service_status' | 'gpu_update' | 'system_alert' | 'performance_update' | 'ping';
  data?: Record<string, unknown>;
}

export interface WebSocketPingMessage {
  type: 'ping';
  timestamp?: string;
}

export type WebSocketMessage = WebSocketEventMessage | WebSocketSystemMessage | WebSocketPingMessage;

/**
 * Configuration for WebSocket mock behavior
 */
export interface WebSocketMockConfig {
  /** Whether to automatically connect WebSockets (default: true) */
  autoConnect?: boolean;
  /** Delay before connection is established in ms (default: 100) */
  connectionDelay?: number;
  /** Whether to simulate initial connection failure (default: false) */
  simulateConnectionFailure?: boolean;
  /** Number of failed connection attempts before success (default: 0) */
  failedAttemptsBeforeSuccess?: number;
  /** Whether to simulate disconnection after connection (default: false) */
  simulateDisconnection?: boolean;
  /** Delay before simulating disconnection in ms (default: 5000) */
  disconnectionDelay?: number;
  /** Whether to send periodic heartbeats (default: true) */
  enableHeartbeats?: boolean;
  /** Heartbeat interval in ms (default: 30000) */
  heartbeatInterval?: number;
}

/**
 * Default WebSocket mock configuration
 */
export const defaultWebSocketMockConfig: WebSocketMockConfig = {
  autoConnect: true,
  connectionDelay: 100,
  simulateConnectionFailure: false,
  failedAttemptsBeforeSuccess: 0,
  simulateDisconnection: false,
  disconnectionDelay: 5000,
  enableHeartbeats: true,
  heartbeatInterval: 30000,
};

/**
 * Interface for controlling mocked WebSocket connections
 */
export interface WebSocketMockController {
  /** Wait for WebSocket connection to be established */
  waitForConnection: (channel?: WebSocketChannel, timeout?: number) => Promise<void>;

  /** Wait for WebSocket to disconnect */
  waitForDisconnect: (channel?: WebSocketChannel, timeout?: number) => Promise<void>;

  /** Send a message to the application on a specific channel */
  sendMessage: (channel: WebSocketChannel, message: WebSocketMessage) => Promise<void>;

  /** Send a security event to the events channel */
  sendSecurityEvent: (event: WebSocketEventMessage['data']) => Promise<void>;

  /** Send a system status update to the system channel */
  sendSystemStatus: (data: Record<string, unknown>) => Promise<void>;

  /** Send a GPU update to the system channel */
  sendGpuUpdate: (data: Record<string, unknown>) => Promise<void>;

  /** Send a heartbeat (ping) message */
  sendHeartbeat: (channel: WebSocketChannel) => Promise<void>;

  /** Simulate connection error on a channel */
  simulateConnectionError: (channel: WebSocketChannel, errorMessage?: string) => Promise<void>;

  /** Simulate reconnection on a channel */
  simulateReconnection: (channel: WebSocketChannel) => Promise<void>;

  /** Simulate connection recovery after failure */
  simulateConnectionRecovery: (channel: WebSocketChannel) => Promise<void>;

  /** Get current connection state for a channel */
  getConnectionState: (channel: WebSocketChannel) => Promise<WebSocketConnectionState>;

  /** Get all received messages from the application (sent via WebSocket) */
  getReceivedMessages: (channel: WebSocketChannel) => Promise<unknown[]>;

  /** Clear all mocked state */
  reset: () => Promise<void>;
}

/**
 * Sets up WebSocket mocking for E2E tests
 *
 * This function injects a mock WebSocket implementation into the page that
 * intercepts all WebSocket connections and allows tests to control connection
 * state and dispatch messages.
 *
 * @param page - Playwright page object
 * @param config - Optional configuration for mock behavior
 * @returns Controller object for interacting with mocked WebSockets
 */
export async function setupWebSocketMock(
  page: Page,
  config: WebSocketMockConfig = {}
): Promise<WebSocketMockController> {
  const mergedConfig = { ...defaultWebSocketMockConfig, ...config };

  // Block actual WebSocket upgrade requests
  await page.route('**/ws/**', async (route) => {
    await route.abort('connectionrefused');
  });

  // Inject WebSocket mock into the page
  await page.addInitScript((cfg) => {
    // Store for mock WebSocket instances
    const mockWebSockets: Map<string, MockWebSocket> = new Map();
    const receivedMessages: Map<string, unknown[]> = new Map();

    // Initialize message stores
    receivedMessages.set('events', []);
    receivedMessages.set('system', []);

    // Connection attempt counter for simulating failures
    const connectionAttempts: Map<string, number> = new Map();
    connectionAttempts.set('events', 0);
    connectionAttempts.set('system', 0);

    class MockWebSocket {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSING = 2;
      static readonly CLOSED = 3;

      readonly CONNECTING = MockWebSocket.CONNECTING;
      readonly OPEN = MockWebSocket.OPEN;
      readonly CLOSING = MockWebSocket.CLOSING;
      readonly CLOSED = MockWebSocket.CLOSED;

      url: string;
      readyState: number = MockWebSocket.CONNECTING;
      protocol: string = '';
      extensions: string = '';
      bufferedAmount: number = 0;
      binaryType: BinaryType = 'blob';

      onopen: ((event: Event) => void) | null = null;
      onclose: ((event: CloseEvent) => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;

      private channel: string;
      private listeners: Map<string, Set<EventListener>> = new Map();

      constructor(url: string | URL, protocols?: string | string[]) {
        this.url = url.toString();
        this.channel = this.extractChannel(this.url);

        if (protocols) {
          this.protocol = Array.isArray(protocols) ? protocols[0] : protocols;
        }

        // Store this instance
        mockWebSockets.set(this.channel, this);

        // Track connection attempts
        const attempts = connectionAttempts.get(this.channel) || 0;
        connectionAttempts.set(this.channel, attempts + 1);

        // Simulate connection establishment
        if (cfg.autoConnect) {
          this.simulateConnection();
        }
      }

      private extractChannel(url: string): string {
        if (url.includes('/ws/events')) return 'events';
        if (url.includes('/ws/system')) return 'system';
        return 'unknown';
      }

      private simulateConnection(): void {
        const attempts = connectionAttempts.get(this.channel) || 0;
        const shouldFail = cfg.simulateConnectionFailure &&
          attempts <= (cfg.failedAttemptsBeforeSuccess || 0);

        setTimeout(() => {
          if (shouldFail) {
            this.simulateError('Connection failed');
          } else {
            this.readyState = MockWebSocket.OPEN;

            const openEvent = new Event('open');
            this.onopen?.(openEvent);
            this.dispatchEvent('open', openEvent);

            // Optionally simulate disconnection after delay
            if (cfg.simulateDisconnection) {
              setTimeout(() => {
                this.close(1006, 'Abnormal closure');
              }, cfg.disconnectionDelay || 5000);
            }

            // Start heartbeats if enabled
            if (cfg.enableHeartbeats) {
              this.startHeartbeats();
            }
          }
        }, cfg.connectionDelay || 100);
      }

      private heartbeatInterval: ReturnType<typeof setInterval> | null = null;

      private startHeartbeats(): void {
        if (this.heartbeatInterval) {
          clearInterval(this.heartbeatInterval);
        }

        this.heartbeatInterval = setInterval(() => {
          if (this.readyState === MockWebSocket.OPEN) {
            this.receiveMessage({ type: 'ping', timestamp: new Date().toISOString() });
          } else if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
          }
        }, cfg.heartbeatInterval || 30000);
      }

      simulateError(message: string): void {
        const errorEvent = new ErrorEvent('error', { message });
        this.onerror?.(errorEvent);
        this.dispatchEvent('error', errorEvent);

        // Close the connection after error
        this.readyState = MockWebSocket.CLOSED;
        const closeEvent = new CloseEvent('close', {
          code: 1006,
          reason: message,
          wasClean: false,
        });
        this.onclose?.(closeEvent);
        this.dispatchEvent('close', closeEvent);
      }

      receiveMessage(data: unknown): void {
        if (this.readyState !== MockWebSocket.OPEN) {
          console.warn('Cannot receive message on closed WebSocket');
          return;
        }

        const messageEvent = new MessageEvent('message', {
          data: typeof data === 'string' ? data : JSON.stringify(data),
        });
        this.onmessage?.(messageEvent);
        this.dispatchEvent('message', messageEvent);
      }

      send(data: string | ArrayBuffer | Blob | ArrayBufferView): void {
        if (this.readyState !== MockWebSocket.OPEN) {
          throw new DOMException('WebSocket is not open', 'InvalidStateError');
        }

        // Store sent messages for test verification
        const messages = receivedMessages.get(this.channel) || [];
        try {
          messages.push(typeof data === 'string' ? JSON.parse(data) : data);
        } catch {
          messages.push(data);
        }
        receivedMessages.set(this.channel, messages);
      }

      close(code: number = 1000, reason: string = ''): void {
        if (this.readyState === MockWebSocket.CLOSED || this.readyState === MockWebSocket.CLOSING) {
          return;
        }

        this.readyState = MockWebSocket.CLOSING;

        // Clear heartbeat interval
        if (this.heartbeatInterval) {
          clearInterval(this.heartbeatInterval);
          this.heartbeatInterval = null;
        }

        setTimeout(() => {
          this.readyState = MockWebSocket.CLOSED;

          const closeEvent = new CloseEvent('close', {
            code,
            reason,
            wasClean: code === 1000,
          });
          this.onclose?.(closeEvent);
          this.dispatchEvent('close', closeEvent);
        }, 0);
      }

      addEventListener(type: string, listener: EventListener): void {
        if (!this.listeners.has(type)) {
          this.listeners.set(type, new Set());
        }
        this.listeners.get(type)!.add(listener);
      }

      removeEventListener(type: string, listener: EventListener): void {
        this.listeners.get(type)?.delete(listener);
      }

      dispatchEvent(type: string, event: Event): boolean {
        const listeners = this.listeners.get(type);
        if (listeners) {
          listeners.forEach((listener) => {
            if (typeof listener === 'function') {
              listener(event);
            }
          });
        }
        return true;
      }

      // Reconnect simulation for tests
      reconnect(): void {
        this.readyState = MockWebSocket.CONNECTING;
        connectionAttempts.set(this.channel, 0); // Reset attempt counter
        this.simulateConnection();
      }
    }

    // Store original WebSocket
    const OriginalWebSocket = window.WebSocket;

    // Replace WebSocket constructor
    // @ts-expect-error - Replacing WebSocket constructor
    window.WebSocket = MockWebSocket;

    // Copy static properties
    // @ts-expect-error - Copying static properties
    window.WebSocket.CONNECTING = MockWebSocket.CONNECTING;
    // @ts-expect-error - Copying static properties
    window.WebSocket.OPEN = MockWebSocket.OPEN;
    // @ts-expect-error - Copying static properties
    window.WebSocket.CLOSING = MockWebSocket.CLOSING;
    // @ts-expect-error - Copying static properties
    window.WebSocket.CLOSED = MockWebSocket.CLOSED;

    // Expose controls for test interaction
    (window as unknown as Record<string, unknown>).__wsMock = {
      mockWebSockets,
      receivedMessages,
      connectionAttempts,
      OriginalWebSocket,
      MockWebSocket,
    };
  }, mergedConfig);

  // Create controller object
  const controller: WebSocketMockController = {
    async waitForConnection(channel: WebSocketChannel = 'events', timeout: number = 10000): Promise<void> {
      await page.waitForFunction(
        (ch) => {
          const mock = (window as unknown as Record<string, unknown>).__wsMock as {
            mockWebSockets: Map<string, { readyState: number }>;
          };
          const ws = mock?.mockWebSockets?.get(ch);
          return ws?.readyState === 1; // OPEN
        },
        channel,
        { timeout }
      );
    },

    async waitForDisconnect(channel: WebSocketChannel = 'events', timeout: number = 10000): Promise<void> {
      await page.waitForFunction(
        (ch) => {
          const mock = (window as unknown as Record<string, unknown>).__wsMock as {
            mockWebSockets: Map<string, { readyState: number }>;
          };
          const ws = mock?.mockWebSockets?.get(ch);
          return !ws || ws.readyState === 3; // CLOSED or not existing
        },
        channel,
        { timeout }
      );
    },

    async sendMessage(channel: WebSocketChannel, message: WebSocketMessage): Promise<void> {
      await page.evaluate(
        ({ ch, msg }) => {
          const mock = (window as unknown as Record<string, unknown>).__wsMock as {
            mockWebSockets: Map<string, { receiveMessage: (data: unknown) => void }>;
          };
          const ws = mock?.mockWebSockets?.get(ch);
          if (ws) {
            ws.receiveMessage(msg);
          } else {
            console.warn(`No WebSocket found for channel: ${ch}`);
          }
        },
        { ch: channel, msg: message }
      );
    },

    async sendSecurityEvent(event: WebSocketEventMessage['data']): Promise<void> {
      await controller.sendMessage('events', { type: 'event', data: event });
    },

    async sendSystemStatus(data: Record<string, unknown>): Promise<void> {
      await controller.sendMessage('system', { type: 'service_status', data });
    },

    async sendGpuUpdate(data: Record<string, unknown>): Promise<void> {
      await controller.sendMessage('system', { type: 'gpu_update', data });
    },

    async sendHeartbeat(channel: WebSocketChannel): Promise<void> {
      await controller.sendMessage(channel, { type: 'ping', timestamp: new Date().toISOString() });
    },

    async simulateConnectionError(channel: WebSocketChannel, errorMessage: string = 'Connection error'): Promise<void> {
      await page.evaluate(
        ({ ch, msg }) => {
          const mock = (window as unknown as Record<string, unknown>).__wsMock as {
            mockWebSockets: Map<string, { simulateError: (message: string) => void }>;
          };
          const ws = mock?.mockWebSockets?.get(ch);
          if (ws) {
            ws.simulateError(msg);
          }
        },
        { ch: channel, msg: errorMessage }
      );
    },

    async simulateReconnection(channel: WebSocketChannel): Promise<void> {
      await page.evaluate(
        (ch) => {
          const mock = (window as unknown as Record<string, unknown>).__wsMock as {
            mockWebSockets: Map<string, { close: (code: number, reason: string) => void }>;
          };
          const ws = mock?.mockWebSockets?.get(ch);
          if (ws) {
            // Close with abnormal closure code to trigger reconnection
            ws.close(1006, 'Simulated disconnection for reconnection test');
          }
        },
        channel
      );
    },

    async simulateConnectionRecovery(channel: WebSocketChannel): Promise<void> {
      await page.evaluate(
        (ch) => {
          const mock = (window as unknown as Record<string, unknown>).__wsMock as {
            mockWebSockets: Map<string, { reconnect: () => void }>;
          };
          const ws = mock?.mockWebSockets?.get(ch);
          if (ws) {
            ws.reconnect();
          }
        },
        channel
      );
    },

    async getConnectionState(channel: WebSocketChannel): Promise<WebSocketConnectionState> {
      return page.evaluate(
        (ch) => {
          const mock = (window as unknown as Record<string, unknown>).__wsMock as {
            mockWebSockets: Map<string, { readyState: number }>;
          };
          const ws = mock?.mockWebSockets?.get(ch);
          if (!ws) return 'disconnected';

          switch (ws.readyState) {
            case 0:
              return 'connecting';
            case 1:
              return 'connected';
            case 2:
            case 3:
            default:
              return 'disconnected';
          }
        },
        channel
      ) as Promise<WebSocketConnectionState>;
    },

    async getReceivedMessages(channel: WebSocketChannel): Promise<unknown[]> {
      return page.evaluate(
        (ch) => {
          const mock = (window as unknown as Record<string, unknown>).__wsMock as {
            receivedMessages: Map<string, unknown[]>;
          };
          return mock?.receivedMessages?.get(ch) || [];
        },
        channel
      );
    },

    async reset(): Promise<void> {
      await page.evaluate(() => {
        const mock = (window as unknown as Record<string, unknown>).__wsMock as {
          mockWebSockets: Map<string, { close: (code: number, reason: string) => void }>;
          receivedMessages: Map<string, unknown[]>;
          connectionAttempts: Map<string, number>;
        };
        if (mock) {
          // Close all connections
          mock.mockWebSockets?.forEach((ws) => ws.close(1000, 'Test reset'));
          mock.mockWebSockets?.clear();
          // Clear received messages
          mock.receivedMessages?.forEach((_, key, map) => map.set(key, []));
          // Reset connection attempts
          mock.connectionAttempts?.forEach((_, key, map) => map.set(key, 0));
        }
      });
    },
  };

  return controller;
}

/**
 * Creates a security event message for testing
 *
 * @param overrides - Optional overrides for the default event
 * @returns A complete WebSocketEventMessage
 */
export function createTestSecurityEvent(
  overrides: Partial<WebSocketEventMessage['data']> = {}
): WebSocketEventMessage['data'] {
  return {
    id: Date.now(),
    event_id: Date.now(),
    camera_id: 'cam-1',
    camera_name: 'Front Door',
    risk_score: 50,
    risk_level: 'medium',
    summary: 'Test security event detected',
    timestamp: new Date().toISOString(),
    started_at: new Date().toISOString(),
    ...overrides,
  };
}

/**
 * Creates a GPU update message for testing
 *
 * @param overrides - Optional overrides for the default GPU stats
 * @returns A GPU update message
 */
export function createTestGpuUpdate(
  overrides: Partial<{
    gpu_name: string;
    utilization: number;
    memory_used: number;
    memory_total: number;
    temperature: number;
    power_usage: number;
    inference_fps: number;
  }> = {}
): Record<string, unknown> {
  return {
    gpu_name: 'NVIDIA RTX A5500',
    utilization: 45,
    memory_used: 8192,
    memory_total: 24576,
    temperature: 52,
    power_usage: 125,
    inference_fps: 12.5,
    ...overrides,
  };
}

/**
 * Creates a system status message for testing
 *
 * @param overrides - Optional overrides for the default status
 * @returns A system status message
 */
export function createTestSystemStatus(
  overrides: Partial<{
    status: string;
    services: Record<string, { status: string; message?: string }>;
  }> = {}
): Record<string, unknown> {
  return {
    status: 'healthy',
    services: {
      postgresql: { status: 'healthy', message: 'Connected' },
      redis: { status: 'healthy', message: 'Connected' },
      rtdetr_server: { status: 'healthy', message: 'Ready' },
      nemotron: { status: 'healthy', message: 'Model loaded' },
    },
    ...overrides,
  };
}

// Legacy exports for backward compatibility
// NEM-2505: These legacy underscore format event types are normalized to hierarchical
// format by extractEventType() in websocket-events.ts via LEGACY_EVENT_TYPE_ALIASES.
// The job_* events are now first-class types and don't need normalization.
export type WebSocketEventType =
  | 'event_created'
  | 'event_updated'
  | 'event.created'  // Hierarchical format (preferred)
  | 'event.updated'  // Hierarchical format (preferred)
  | 'camera_status'
  | 'gpu_update'
  | 'system_alert'
  | 'performance_update'
  | 'job_progress'   // Legacy format (backend schema format)
  | 'job_completed'  // Legacy format (backend schema format)
  | 'job_failed';    // Legacy format (backend schema format)

export interface SimulatedWebSocketMessage {
  type: WebSocketEventType;
  data: Record<string, unknown>;
  timestamp: string;
}

export function createWebSocketMessage(
  type: WebSocketEventType,
  data: Record<string, unknown>
): SimulatedWebSocketMessage {
  return {
    type,
    data,
    timestamp: new Date().toISOString(),
  };
}

export async function simulateNewEvent(
  page: Page,
  eventData: {
    id: number;
    camera_id: string;
    camera_name: string;
    risk_score: number;
    risk_level: 'low' | 'medium' | 'high' | 'critical';
    summary: string;
  }
): Promise<void> {
  await page.evaluate((event) => {
    window.dispatchEvent(
      new CustomEvent('ws-simulated-event', {
        detail: {
          type: 'event_created',
          data: event,
        },
      })
    );
  }, eventData);
}

export async function simulateCameraStatusChange(
  page: Page,
  cameraId: string,
  status: 'online' | 'offline'
): Promise<void> {
  await page.evaluate(
    ({ id, newStatus }) => {
      window.dispatchEvent(
        new CustomEvent('ws-simulated-event', {
          detail: {
            type: 'camera_status',
            data: {
              camera_id: id,
              status: newStatus,
              timestamp: new Date().toISOString(),
            },
          },
        })
      );
    },
    { id: cameraId, newStatus: status }
  );
}

export async function simulateGpuUpdate(
  page: Page,
  gpuStats: {
    utilization: number;
    memory_used: number;
    memory_total: number;
    temperature: number;
  }
): Promise<void> {
  await page.evaluate((stats) => {
    window.dispatchEvent(
      new CustomEvent('ws-simulated-event', {
        detail: {
          type: 'gpu_update',
          data: stats,
        },
      })
    );
  }, gpuStats);
}

export async function simulateSystemAlert(
  page: Page,
  alert: {
    severity: 'info' | 'warning' | 'critical';
    message: string;
    component?: string;
  }
): Promise<void> {
  await page.evaluate((alertData) => {
    window.dispatchEvent(
      new CustomEvent('ws-simulated-event', {
        detail: {
          type: 'system_alert',
          data: alertData,
        },
      })
    );
  }, alert);
}

export async function isShowingDisconnectedState(page: Page): Promise<boolean> {
  const disconnectedIndicator = page.getByText(/Disconnected/i);
  return disconnectedIndicator.isVisible().catch(() => false);
}

export async function waitForConnectionAttempt(
  page: Page,
  timeoutMs: number = 5000
): Promise<boolean> {
  let connectionAttempted = false;

  const listener = (request: { url: () => string }) => {
    if (request.url().includes('/ws/')) {
      connectionAttempted = true;
    }
  };

  page.on('request', listener);

  await page.waitForTimeout(timeoutMs);

  return connectionAttempted;
}
