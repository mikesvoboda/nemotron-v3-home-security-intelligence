/**
 * Webhook Management Types
 *
 * Types for outbound webhook management feature.
 * These types mirror the backend schemas defined in
 * `backend/api/schemas/outbound_webhook.py`.
 *
 * @see NEM-3624 - Webhook Management Feature
 */

// ============================================================================
// Enums and Literal Types
// ============================================================================

/**
 * Event types that can trigger webhooks.
 */
export type WebhookEventType =
  | 'alert_fired'
  | 'alert_dismissed'
  | 'alert_acknowledged'
  | 'event_created'
  | 'event_enriched'
  | 'entity_discovered'
  | 'anomaly_detected'
  | 'system_health_changed';

/**
 * All possible webhook event types.
 */
export const WEBHOOK_EVENT_TYPES: readonly WebhookEventType[] = [
  'alert_fired',
  'alert_dismissed',
  'alert_acknowledged',
  'event_created',
  'event_enriched',
  'entity_discovered',
  'anomaly_detected',
  'system_health_changed',
] as const;

/**
 * Webhook delivery attempt status.
 */
export type WebhookDeliveryStatus = 'pending' | 'success' | 'failed' | 'retrying';

/**
 * Pre-built integration types.
 */
export type IntegrationType = 'generic' | 'slack' | 'discord' | 'telegram' | 'teams';

/**
 * All possible integration types.
 */
export const INTEGRATION_TYPES: readonly IntegrationType[] = [
  'generic',
  'slack',
  'discord',
  'telegram',
  'teams',
] as const;

/**
 * Authentication types for webhook requests.
 */
export type WebhookAuthType = 'none' | 'bearer' | 'basic' | 'header';

// ============================================================================
// Authentication Configuration
// ============================================================================

/**
 * Authentication configuration for webhook requests.
 */
export interface WebhookAuthConfig {
  /** Auth type: none, bearer, basic, or header */
  type: WebhookAuthType;
  /** Bearer token (if type=bearer) */
  token?: string;
  /** Username (if type=basic) */
  username?: string;
  /** Password (if type=basic) */
  password?: string;
  /** Custom header name (if type=header) */
  header_name?: string;
  /** Custom header value (if type=header) */
  header_value?: string;
}

// ============================================================================
// Webhook Configuration Types
// ============================================================================

/**
 * Full webhook configuration response.
 */
export interface Webhook {
  /** Unique webhook identifier */
  id: string;
  /** Webhook name */
  name: string;
  /** Webhook endpoint URL */
  url: string;
  /** Subscribed event types */
  event_types: WebhookEventType[];
  /** Integration type */
  integration_type: IntegrationType;
  /** Whether webhook is active */
  enabled: boolean;
  /** Custom HTTP headers */
  custom_headers: Record<string, string>;
  /** Custom payload template (Jinja2) */
  payload_template: string | null;
  /** Max retry attempts */
  max_retries: number;
  /** Initial retry delay in seconds */
  retry_delay_seconds: number;
  /** Creation timestamp (ISO 8601) */
  created_at: string;
  /** Last update timestamp (ISO 8601) */
  updated_at: string;
  /** Total delivery attempts */
  total_deliveries: number;
  /** Successful deliveries */
  successful_deliveries: number;
  /** Last delivery timestamp (ISO 8601) */
  last_delivery_at: string | null;
  /** Last delivery status */
  last_delivery_status: WebhookDeliveryStatus | null;
}

/**
 * Schema for creating a new webhook.
 */
export interface WebhookCreate {
  /** Webhook name */
  name: string;
  /** Webhook endpoint URL */
  url: string;
  /** Events to subscribe to */
  event_types: WebhookEventType[];
  /** Integration type */
  integration_type?: IntegrationType;
  /** Whether webhook is active */
  enabled?: boolean;
  /** Authentication configuration */
  auth?: WebhookAuthConfig;
  /** Custom HTTP headers */
  custom_headers?: Record<string, string>;
  /** Custom payload template (Jinja2) */
  payload_template?: string;
  /** Max retry attempts (0-10) */
  max_retries?: number;
  /** Initial retry delay in seconds (1-3600) */
  retry_delay_seconds?: number;
}

/**
 * Schema for updating a webhook.
 */
export interface WebhookUpdate {
  /** Webhook name */
  name?: string;
  /** Webhook endpoint URL */
  url?: string;
  /** Events to subscribe to */
  event_types?: WebhookEventType[];
  /** Integration type */
  integration_type?: IntegrationType;
  /** Whether webhook is active */
  enabled?: boolean;
  /** Authentication configuration */
  auth?: WebhookAuthConfig;
  /** Custom HTTP headers */
  custom_headers?: Record<string, string>;
  /** Custom payload template (Jinja2) */
  payload_template?: string;
  /** Max retry attempts (0-10) */
  max_retries?: number;
  /** Initial retry delay in seconds (1-3600) */
  retry_delay_seconds?: number;
}

/**
 * Response for listing webhooks.
 */
export interface WebhookListResponse {
  /** List of webhooks */
  webhooks: Webhook[];
  /** Total count */
  total: number;
}

// ============================================================================
// Webhook Delivery Types
// ============================================================================

/**
 * Response for a webhook delivery attempt.
 */
export interface WebhookDelivery {
  /** Delivery ID */
  id: string;
  /** Parent webhook ID */
  webhook_id: string;
  /** Event that triggered delivery */
  event_type: WebhookEventType;
  /** Related event ID */
  event_id: string | null;
  /** Delivery status */
  status: WebhookDeliveryStatus;
  /** HTTP response status code */
  status_code: number | null;
  /** Response time in milliseconds */
  response_time_ms: number | null;
  /** Error message if failed */
  error_message: string | null;
  /** Number of attempts */
  attempt_count: number;
  /** Next retry timestamp (ISO 8601) */
  next_retry_at: string | null;
  /** Delivery creation timestamp (ISO 8601) */
  created_at: string;
  /** Successful delivery timestamp (ISO 8601) */
  delivered_at: string | null;
}

/**
 * Response for listing webhook deliveries.
 */
export interface WebhookDeliveryListResponse {
  /** List of deliveries */
  deliveries: WebhookDelivery[];
  /** Total count */
  total: number;
  /** Page limit */
  limit: number;
  /** Page offset */
  offset: number;
  /** Whether more items exist */
  has_more: boolean;
}

/**
 * Query parameters for fetching webhook deliveries.
 */
export interface WebhookDeliveryQueryParams {
  /** Maximum number of deliveries to return */
  limit?: number;
  /** Offset for pagination */
  offset?: number;
}

// ============================================================================
// Webhook Test Types
// ============================================================================

/**
 * Request to test a webhook with sample data.
 */
export interface WebhookTestRequest {
  /** Event type for test payload */
  event_type: WebhookEventType;
}

/**
 * Response from testing a webhook.
 */
export interface WebhookTestResponse {
  /** Whether test succeeded */
  success: boolean;
  /** HTTP response code */
  status_code: number | null;
  /** Response time in milliseconds */
  response_time_ms: number | null;
  /** Response body (truncated) */
  response_body: string | null;
  /** Error if failed */
  error_message: string | null;
}

// ============================================================================
// Webhook Health Types
// ============================================================================

/**
 * Health summary for all webhooks.
 */
export interface WebhookHealthSummary {
  /** Total number of webhooks */
  total_webhooks: number;
  /** Number of enabled webhooks */
  enabled_webhooks: number;
  /** Webhooks with >90% success rate */
  healthy_webhooks: number;
  /** Webhooks with <50% success rate */
  unhealthy_webhooks: number;
  /** Total deliveries in last 24 hours */
  total_deliveries_24h: number;
  /** Successful deliveries in last 24 hours */
  successful_deliveries_24h: number;
  /** Failed deliveries in last 24 hours */
  failed_deliveries_24h: number;
  /** Average response time in milliseconds */
  average_response_time_ms: number | null;
}

// ============================================================================
// UI Helper Constants
// ============================================================================

/**
 * Human-readable labels for webhook event types.
 */
export const WEBHOOK_EVENT_LABELS: Record<WebhookEventType, string> = {
  alert_fired: 'Alert Fired',
  alert_dismissed: 'Alert Dismissed',
  alert_acknowledged: 'Alert Acknowledged',
  event_created: 'Event Created',
  event_enriched: 'Event Enriched',
  entity_discovered: 'Entity Discovered',
  anomaly_detected: 'Anomaly Detected',
  system_health_changed: 'System Health Changed',
};

/**
 * Information about each integration type for UI display.
 */
export interface IntegrationInfo {
  /** Display label */
  label: string;
  /** Icon name (for use with icon library) */
  icon: string;
  /** URL pattern to identify this integration (optional) */
  urlPattern?: string;
}

/**
 * Integration type information for UI display.
 */
export const INTEGRATION_INFO: Record<IntegrationType, IntegrationInfo> = {
  generic: { label: 'Generic Webhook', icon: 'webhook' },
  slack: { label: 'Slack', icon: 'slack', urlPattern: 'hooks.slack.com' },
  discord: { label: 'Discord', icon: 'discord', urlPattern: 'discord.com/api/webhooks' },
  telegram: { label: 'Telegram', icon: 'telegram' },
  teams: { label: 'Microsoft Teams', icon: 'microsoft' },
};

/**
 * Human-readable labels for delivery status.
 */
export const DELIVERY_STATUS_LABELS: Record<WebhookDeliveryStatus, string> = {
  pending: 'Pending',
  success: 'Success',
  failed: 'Failed',
  retrying: 'Retrying',
};

/**
 * Color configurations for delivery status (for use with UI components).
 */
export const DELIVERY_STATUS_COLORS: Record<WebhookDeliveryStatus, string> = {
  pending: 'yellow',
  success: 'green',
  failed: 'red',
  retrying: 'orange',
};

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard to check if a string is a valid webhook event type.
 */
export function isWebhookEventType(value: unknown): value is WebhookEventType {
  return typeof value === 'string' && WEBHOOK_EVENT_TYPES.includes(value as WebhookEventType);
}

/**
 * Type guard to check if a string is a valid integration type.
 */
export function isIntegrationType(value: unknown): value is IntegrationType {
  return typeof value === 'string' && INTEGRATION_TYPES.includes(value as IntegrationType);
}

/**
 * Type guard to check if a string is a valid delivery status.
 */
export function isWebhookDeliveryStatus(value: unknown): value is WebhookDeliveryStatus {
  const validStatuses: WebhookDeliveryStatus[] = ['pending', 'success', 'failed', 'retrying'];
  return typeof value === 'string' && validStatuses.includes(value as WebhookDeliveryStatus);
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Calculate the success rate for a webhook.
 * Returns a percentage between 0 and 100.
 */
export function calculateSuccessRate(webhook: Webhook): number {
  if (webhook.total_deliveries === 0) {
    return 100; // No deliveries yet, consider healthy
  }
  return Math.round((webhook.successful_deliveries / webhook.total_deliveries) * 100);
}

/**
 * Determine if a webhook is healthy based on success rate.
 * Healthy: >90% success rate
 */
export function isWebhookHealthy(webhook: Webhook): boolean {
  return calculateSuccessRate(webhook) > 90;
}

/**
 * Determine if a webhook is unhealthy based on success rate.
 * Unhealthy: <50% success rate
 */
export function isWebhookUnhealthy(webhook: Webhook): boolean {
  return calculateSuccessRate(webhook) < 50;
}

/**
 * Detect integration type from webhook URL.
 */
export function detectIntegrationType(url: string): IntegrationType {
  const lowerUrl = url.toLowerCase();
  if (lowerUrl.includes('hooks.slack.com')) {
    return 'slack';
  }
  if (lowerUrl.includes('discord.com/api/webhooks')) {
    return 'discord';
  }
  if (lowerUrl.includes('api.telegram.org')) {
    return 'telegram';
  }
  if (lowerUrl.includes('.webhook.office.com') || lowerUrl.includes('teams.microsoft.com')) {
    return 'teams';
  }
  return 'generic';
}
