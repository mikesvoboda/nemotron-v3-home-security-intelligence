/**
 * Webhook API Client
 *
 * Provides typed fetch wrappers for outbound webhook management REST endpoints.
 *
 * Endpoints:
 *   POST   /api/outbound-webhooks              - Create webhook
 *   GET    /api/outbound-webhooks              - List webhooks
 *   GET    /api/outbound-webhooks/:id          - Get webhook
 *   PATCH  /api/outbound-webhooks/:id          - Update webhook
 *   DELETE /api/outbound-webhooks/:id          - Delete webhook
 *   POST   /api/outbound-webhooks/:id/test     - Test webhook
 *   POST   /api/outbound-webhooks/:id/enable   - Enable webhook
 *   POST   /api/outbound-webhooks/:id/disable  - Disable webhook
 *   GET    /api/outbound-webhooks/:id/deliveries - List deliveries
 *   GET    /api/outbound-webhooks/health       - Get health summary
 *   POST   /api/outbound-webhooks/deliveries/:id/retry - Retry delivery
 *
 * @see NEM-3624 - Webhook Management Feature
 * @see backend/api/routes/outbound_webhooks.py - Backend implementation
 */

import type {
  Webhook,
  WebhookCreate,
  WebhookUpdate,
  WebhookListResponse,
  WebhookDeliveryListResponse,
  WebhookDeliveryQueryParams,
  WebhookTestRequest,
  WebhookTestResponse,
  WebhookHealthSummary,
  WebhookDelivery,
} from '../types/webhook';

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;
const API_BASE = '/api/outbound-webhooks';

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Custom error class for Webhook API failures.
 * Includes HTTP status code and parsed error data.
 */
export class WebhookApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'WebhookApiError';
  }
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Build headers with optional API key authentication.
 */
function buildHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return headers;
}

/**
 * Handle API response with proper error handling.
 * Parses error details from FastAPI response format.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    let errorData: unknown = undefined;

    try {
      const errorBody: unknown = await response.json();
      if (typeof errorBody === 'object' && errorBody !== null && 'detail' in errorBody) {
        errorMessage = String((errorBody as { detail: unknown }).detail);
        errorData = errorBody;
      } else if (typeof errorBody === 'string') {
        errorMessage = errorBody;
      } else {
        errorData = errorBody;
      }
    } catch {
      // If response body is not JSON, use status text
    }

    throw new WebhookApiError(response.status, errorMessage, errorData);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new WebhookApiError(response.status, 'Failed to parse response JSON', error);
  }
}

/**
 * Perform a fetch request to the Webhook API with error handling.
 *
 * @param endpoint - API endpoint path (relative to /api/outbound-webhooks)
 * @param options - Optional fetch options
 * @returns Parsed JSON response
 */
async function fetchWebhookApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${API_BASE}${endpoint}`;

  const fetchOptions: RequestInit = {
    ...options,
    headers: buildHeaders(),
  };

  try {
    const response = await fetch(url, fetchOptions);
    return handleResponse<T>(response);
  } catch (error) {
    if (error instanceof WebhookApiError) {
      throw error;
    }
    throw new WebhookApiError(
      0,
      error instanceof Error ? error.message : 'Network request failed'
    );
  }
}

// ============================================================================
// API Functions - CRUD Operations
// ============================================================================

/**
 * Create a new webhook.
 *
 * @param data - Webhook creation data
 * @returns Created webhook
 * @throws WebhookApiError on validation or server errors
 *
 * @example
 * ```typescript
 * const webhook = await createWebhook({
 *   name: 'Slack Alerts',
 *   url: 'https://hooks.slack.com/services/xxx/yyy/zzz',
 *   event_types: ['alert_fired', 'alert_dismissed'],
 *   integration_type: 'slack',
 * });
 * ```
 */
export async function createWebhook(data: WebhookCreate): Promise<Webhook> {
  return fetchWebhookApi<Webhook>('', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * List all webhooks.
 *
 * @returns List of webhooks with total count
 * @throws WebhookApiError on server errors
 *
 * @example
 * ```typescript
 * const { webhooks, total } = await listWebhooks();
 * console.log(`Found ${total} webhooks`);
 * ```
 */
export async function listWebhooks(): Promise<WebhookListResponse> {
  return fetchWebhookApi<WebhookListResponse>('');
}

/**
 * Get a webhook by ID.
 *
 * @param id - Webhook UUID
 * @returns Webhook details
 * @throws WebhookApiError if not found or on server errors
 *
 * @example
 * ```typescript
 * const webhook = await getWebhook('123e4567-e89b-12d3-a456-426614174000');
 * console.log(`Webhook: ${webhook.name}`);
 * ```
 */
export async function getWebhook(id: string): Promise<Webhook> {
  return fetchWebhookApi<Webhook>(`/${id}`);
}

/**
 * Update a webhook.
 *
 * @param id - Webhook UUID
 * @param data - Fields to update
 * @returns Updated webhook
 * @throws WebhookApiError if not found or on validation/server errors
 *
 * @example
 * ```typescript
 * const updated = await updateWebhook('123...', {
 *   name: 'Updated Name',
 *   enabled: false,
 * });
 * ```
 */
export async function updateWebhook(id: string, data: WebhookUpdate): Promise<Webhook> {
  return fetchWebhookApi<Webhook>(`/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * Delete a webhook.
 *
 * @param id - Webhook UUID
 * @throws WebhookApiError if not found or on server errors
 *
 * @example
 * ```typescript
 * await deleteWebhook('123e4567-e89b-12d3-a456-426614174000');
 * ```
 */
export async function deleteWebhook(id: string): Promise<void> {
  return fetchWebhookApi<void>(`/${id}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// API Functions - Webhook Operations
// ============================================================================

/**
 * Test a webhook with sample payload.
 *
 * Sends a test request to the webhook URL with sample data
 * for the specified event type. Does not create a delivery record.
 *
 * @param id - Webhook UUID
 * @param request - Test request with event type
 * @returns Test result including success status and response details
 * @throws WebhookApiError if webhook not found or on server errors
 *
 * @example
 * ```typescript
 * const result = await testWebhook('123...', { event_type: 'alert_fired' });
 * if (result.success) {
 *   console.log(`Test successful! Response time: ${result.response_time_ms}ms`);
 * } else {
 *   console.error(`Test failed: ${result.error_message}`);
 * }
 * ```
 */
export async function testWebhook(
  id: string,
  request: WebhookTestRequest
): Promise<WebhookTestResponse> {
  return fetchWebhookApi<WebhookTestResponse>(`/${id}/test`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Enable a webhook.
 *
 * @param id - Webhook UUID
 * @returns Updated webhook with enabled=true
 * @throws WebhookApiError if not found or on server errors
 *
 * @example
 * ```typescript
 * const webhook = await enableWebhook('123...');
 * console.log(`Webhook enabled: ${webhook.enabled}`); // true
 * ```
 */
export async function enableWebhook(id: string): Promise<Webhook> {
  return fetchWebhookApi<Webhook>(`/${id}/enable`, {
    method: 'POST',
  });
}

/**
 * Disable a webhook.
 *
 * @param id - Webhook UUID
 * @returns Updated webhook with enabled=false
 * @throws WebhookApiError if not found or on server errors
 *
 * @example
 * ```typescript
 * const webhook = await disableWebhook('123...');
 * console.log(`Webhook enabled: ${webhook.enabled}`); // false
 * ```
 */
export async function disableWebhook(id: string): Promise<Webhook> {
  return fetchWebhookApi<Webhook>(`/${id}/disable`, {
    method: 'POST',
  });
}

// ============================================================================
// API Functions - Delivery Operations
// ============================================================================

/**
 * Get delivery history for a webhook.
 *
 * @param webhookId - Webhook UUID
 * @param params - Optional pagination parameters
 * @returns Paginated list of deliveries
 * @throws WebhookApiError if webhook not found or on server errors
 *
 * @example
 * ```typescript
 * const { deliveries, total, has_more } = await getDeliveries('123...', {
 *   limit: 20,
 *   offset: 0,
 * });
 * console.log(`Showing ${deliveries.length} of ${total} deliveries`);
 * ```
 */
export async function getDeliveries(
  webhookId: string,
  params?: WebhookDeliveryQueryParams
): Promise<WebhookDeliveryListResponse> {
  const queryParams = new URLSearchParams();
  if (params?.limit !== undefined) {
    queryParams.append('limit', String(params.limit));
  }
  if (params?.offset !== undefined) {
    queryParams.append('offset', String(params.offset));
  }

  const queryString = queryParams.toString();
  const endpoint = `/${webhookId}/deliveries${queryString ? `?${queryString}` : ''}`;

  return fetchWebhookApi<WebhookDeliveryListResponse>(endpoint);
}

/**
 * Get details of a specific delivery.
 *
 * @param deliveryId - Delivery UUID
 * @returns Delivery details
 * @throws WebhookApiError if not found or on server errors
 *
 * @example
 * ```typescript
 * const delivery = await getDelivery('abc...');
 * console.log(`Status: ${delivery.status}, Attempts: ${delivery.attempt_count}`);
 * ```
 */
export async function getDelivery(deliveryId: string): Promise<WebhookDelivery> {
  return fetchWebhookApi<WebhookDelivery>(`/deliveries/${deliveryId}`);
}

/**
 * Retry a failed delivery.
 *
 * @param deliveryId - Delivery UUID
 * @returns Updated delivery
 * @throws WebhookApiError if delivery not found, not in failed state, or on server errors
 *
 * @example
 * ```typescript
 * const delivery = await retryDelivery('abc...');
 * console.log(`Retry queued, attempt count: ${delivery.attempt_count}`);
 * ```
 */
export async function retryDelivery(deliveryId: string): Promise<WebhookDelivery> {
  return fetchWebhookApi<WebhookDelivery>(`/deliveries/${deliveryId}/retry`, {
    method: 'POST',
  });
}

// ============================================================================
// API Functions - Health Dashboard
// ============================================================================

/**
 * Get webhook health summary for dashboard.
 *
 * Returns aggregated health metrics across all webhooks including
 * success rates, delivery counts, and response times.
 *
 * @returns Health summary with aggregated metrics
 * @throws WebhookApiError on server errors
 *
 * @example
 * ```typescript
 * const health = await getHealthSummary();
 * console.log(`${health.healthy_webhooks}/${health.total_webhooks} webhooks healthy`);
 * console.log(`24h success rate: ${(health.successful_deliveries_24h / health.total_deliveries_24h * 100).toFixed(1)}%`);
 * ```
 */
export async function getHealthSummary(): Promise<WebhookHealthSummary> {
  return fetchWebhookApi<WebhookHealthSummary>('/health');
}
