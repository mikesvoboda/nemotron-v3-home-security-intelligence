/**
 * MQTT Configuration API Client
 *
 * Provides API methods for managing MQTT broker configuration,
 * connection status, and publishing settings.
 *
 * Related Issues:
 * - NEM-5140: [Implement] Phase 2: MQTT Configuration UI
 * - NEM-5032: Epic 3: Ecosystem Integration
 */

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;
const API_BASE = '/api/mqtt-config';

// =============================================================================
// Types
// =============================================================================

export interface MqttBrokerConfig {
  broker_host: string;
  broker_port: number;
  client_id: string | null;
  username: string | null;
  password: string | null;
  topic_prefix: string;
  qos_default: number;
  use_tls: boolean;
  tls_ca_cert: string | null;
  keepalive: number;
}

export interface MqttPublisherConfig {
  enabled: boolean;
  events_qos: number;
  status_qos: number;
  retain_status: boolean;
  retain_events: boolean;
}

export interface MqttConfig {
  broker: MqttBrokerConfig;
  publisher: MqttPublisherConfig;
  ha_discovery_enabled: boolean;
  frigate_enabled: boolean;
}

export interface MqttConnectionStatus {
  connected: boolean;
  broker_host: string | null;
  broker_port: number | null;
  last_connected_at: string | null;
  last_error: string | null;
  messages_published: number;
  messages_received: number;
}

export interface MqttTestResult {
  success: boolean;
  latency_ms: number | null;
  error: string | null;
}

export interface MqttConfigUpdate {
  broker?: Partial<MqttBrokerConfig>;
  publisher?: Partial<MqttPublisherConfig>;
  ha_discovery_enabled?: boolean;
  frigate_enabled?: boolean;
}

// =============================================================================
// Error Handling
// =============================================================================

export class MqttApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'MqttApiError';
  }
}

function buildHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return headers;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      errorData = await response.text();
    }
    throw new MqttApiError(
      response.status,
      `API Error: ${response.statusText}`,
      errorData
    );
  }
  return response.json() as Promise<T>;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Get current MQTT configuration.
 */
export async function getMqttConfig(): Promise<MqttConfig> {
  const response = await fetch(`${BASE_URL}${API_BASE}`, {
    headers: buildHeaders(),
  });
  return handleResponse<MqttConfig>(response);
}

/**
 * Update MQTT configuration.
 */
export async function updateMqttConfig(
  config: MqttConfigUpdate
): Promise<MqttConfig> {
  const response = await fetch(`${BASE_URL}${API_BASE}`, {
    method: 'PUT',
    headers: buildHeaders(),
    body: JSON.stringify(config),
  });
  return handleResponse<MqttConfig>(response);
}

/**
 * Get MQTT connection status.
 */
export async function getMqttStatus(): Promise<MqttConnectionStatus> {
  const response = await fetch(`${BASE_URL}${API_BASE}/status`, {
    headers: buildHeaders(),
  });
  return handleResponse<MqttConnectionStatus>(response);
}

/**
 * Test MQTT connection with current or provided settings.
 */
export async function testMqttConnection(
  broker?: Partial<MqttBrokerConfig>
): Promise<MqttTestResult> {
  const response = await fetch(`${BASE_URL}${API_BASE}/test`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(broker || {}),
  });
  return handleResponse<MqttTestResult>(response);
}

/**
 * Reconnect MQTT client.
 */
export async function reconnectMqtt(): Promise<{ success: boolean }> {
  const response = await fetch(`${BASE_URL}${API_BASE}/reconnect`, {
    method: 'POST',
    headers: buildHeaders(),
  });
  return handleResponse<{ success: boolean }>(response);
}

/**
 * Disconnect MQTT client.
 */
export async function disconnectMqtt(): Promise<{ success: boolean }> {
  const response = await fetch(`${BASE_URL}${API_BASE}/disconnect`, {
    method: 'POST',
    headers: buildHeaders(),
  });
  return handleResponse<{ success: boolean }>(response);
}

// =============================================================================
// Default Export
// =============================================================================

export const mqttConfigApi = {
  getConfig: getMqttConfig,
  updateConfig: updateMqttConfig,
  getStatus: getMqttStatus,
  testConnection: testMqttConnection,
  reconnect: reconnectMqtt,
  disconnect: disconnectMqtt,
};

export default mqttConfigApi;
