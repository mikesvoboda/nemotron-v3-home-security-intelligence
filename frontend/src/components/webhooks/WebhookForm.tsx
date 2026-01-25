/**
 * WebhookForm - Form for creating and editing webhooks
 *
 * Features:
 * - Name and URL fields
 * - Event type multi-select
 * - Integration type selector
 * - Authentication configuration (bearer, basic, header)
 * - Custom headers key-value pairs
 * - Retry configuration
 *
 * @module components/webhooks/WebhookForm
 * @see NEM-3624 - Webhook Management Feature
 */

import { clsx } from 'clsx';
import { AlertCircle, Plus, Trash2, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import {
  WEBHOOK_EVENT_TYPES,
  WEBHOOK_EVENT_LABELS,
  INTEGRATION_TYPES,
  INTEGRATION_INFO,
  detectIntegrationType,
} from '../../types/webhook';
import Button from '../common/Button';

import type {
  Webhook,
  WebhookCreate,
  WebhookUpdate,
  WebhookEventType,
  IntegrationType,
  WebhookAuthType,
  WebhookAuthConfig,
} from '../../types/webhook';

// ============================================================================
// Types
// ============================================================================

export interface WebhookFormProps {
  /** Existing webhook for editing (undefined for create mode) */
  webhook?: Webhook;
  /** Submit handler */
  onSubmit: (data: WebhookCreate | WebhookUpdate) => Promise<void>;
  /** Cancel handler */
  onCancel: () => void;
  /** Whether form is submitting */
  isSubmitting?: boolean;
  /** API error message */
  apiError?: string | null;
  /** Clear API error callback */
  onClearApiError?: () => void;
}

interface FormState {
  name: string;
  url: string;
  event_types: WebhookEventType[];
  integration_type: IntegrationType;
  enabled: boolean;
  auth_type: WebhookAuthType;
  auth_token: string;
  auth_username: string;
  auth_password: string;
  auth_header_name: string;
  auth_header_value: string;
  custom_headers: Array<{ key: string; value: string }>;
  max_retries: number;
  retry_delay_seconds: number;
}

interface FormErrors {
  name?: string;
  url?: string;
  event_types?: string;
  auth_token?: string;
  auth_username?: string;
  auth_password?: string;
  auth_header_name?: string;
  auth_header_value?: string;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_FORM_STATE: FormState = {
  name: '',
  url: '',
  event_types: [],
  integration_type: 'generic',
  enabled: true,
  auth_type: 'none',
  auth_token: '',
  auth_username: '',
  auth_password: '',
  auth_header_name: '',
  auth_header_value: '',
  custom_headers: [],
  max_retries: 3,
  retry_delay_seconds: 60,
};

const AUTH_TYPES: Array<{ value: WebhookAuthType; label: string; description: string }> = [
  { value: 'none', label: 'No Authentication', description: 'No authentication required' },
  { value: 'bearer', label: 'Bearer Token', description: 'Authorization: Bearer <token>' },
  { value: 'basic', label: 'Basic Auth', description: 'Authorization: Basic <base64>' },
  { value: 'header', label: 'Custom Header', description: 'Custom header name and value' },
];

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Convert webhook to form state
 */
function webhookToFormState(webhook: Webhook): FormState {
  return {
    name: webhook.name,
    url: webhook.url,
    event_types: [...webhook.event_types],
    integration_type: webhook.integration_type,
    enabled: webhook.enabled,
    auth_type: 'none', // Auth is not returned by API for security
    auth_token: '',
    auth_username: '',
    auth_password: '',
    auth_header_name: '',
    auth_header_value: '',
    custom_headers: Object.entries(webhook.custom_headers).map(([key, value]) => ({
      key,
      value,
    })),
    max_retries: webhook.max_retries,
    retry_delay_seconds: webhook.retry_delay_seconds,
  };
}

/**
 * Convert form state to create/update payload
 */
function formStateToPayload(
  state: FormState,
  _isEdit: boolean
): WebhookCreate | WebhookUpdate {
  // Build auth config
  let auth: WebhookAuthConfig | undefined;
  if (state.auth_type !== 'none') {
    auth = { type: state.auth_type };
    switch (state.auth_type) {
      case 'bearer':
        auth.token = state.auth_token;
        break;
      case 'basic':
        auth.username = state.auth_username;
        auth.password = state.auth_password;
        break;
      case 'header':
        auth.header_name = state.auth_header_name;
        auth.header_value = state.auth_header_value;
        break;
    }
  }

  // Build custom headers
  const custom_headers: Record<string, string> = {};
  state.custom_headers.forEach(({ key, value }) => {
    if (key.trim()) {
      custom_headers[key.trim()] = value;
    }
  });

  const payload: WebhookCreate | WebhookUpdate = {
    name: state.name.trim(),
    url: state.url.trim(),
    event_types: state.event_types,
    integration_type: state.integration_type,
    enabled: state.enabled,
    custom_headers,
    max_retries: state.max_retries,
    retry_delay_seconds: state.retry_delay_seconds,
  };

  // Only include auth if configured
  if (auth) {
    payload.auth = auth;
  }

  return payload;
}

/**
 * Validate form state
 */
function validateForm(state: FormState): FormErrors {
  const errors: FormErrors = {};

  // Name validation
  if (!state.name.trim()) {
    errors.name = 'Name is required';
  } else if (state.name.trim().length > 100) {
    errors.name = 'Name must be 100 characters or less';
  }

  // URL validation
  if (!state.url.trim()) {
    errors.url = 'URL is required';
  } else {
    try {
      const url = new URL(state.url.trim());
      if (!['http:', 'https:'].includes(url.protocol)) {
        errors.url = 'URL must start with http:// or https://';
      }
    } catch {
      errors.url = 'Invalid URL format';
    }
  }

  // Event types validation
  if (state.event_types.length === 0) {
    errors.event_types = 'Select at least one event type';
  }

  // Auth validation
  if (state.auth_type === 'bearer' && !state.auth_token.trim()) {
    errors.auth_token = 'Token is required for bearer authentication';
  }
  if (state.auth_type === 'basic') {
    if (!state.auth_username.trim()) {
      errors.auth_username = 'Username is required for basic authentication';
    }
    // pragma: allowlist secret - this is a form validation error message, not a secret
    if (!state.auth_password.trim()) {
      errors.auth_password = 'Credential is required for basic authentication';
    }
  }
  if (state.auth_type === 'header') {
    if (!state.auth_header_name.trim()) {
      errors.auth_header_name = 'Header name is required';
    }
    if (!state.auth_header_value.trim()) {
      errors.auth_header_value = 'Header value is required';
    }
  }

  return errors;
}

// ============================================================================
// Component
// ============================================================================

/**
 * WebhookForm component for creating and editing webhooks
 */
export default function WebhookForm({
  webhook,
  onSubmit,
  onCancel,
  isSubmitting = false,
  apiError,
  onClearApiError,
}: WebhookFormProps) {
  const isEdit = Boolean(webhook);

  // Form state
  const [state, setState] = useState<FormState>(() =>
    webhook ? webhookToFormState(webhook) : DEFAULT_FORM_STATE
  );
  const [errors, setErrors] = useState<FormErrors>({});

  // Reset form when webhook changes
  useEffect(() => {
    if (webhook) {
      setState(webhookToFormState(webhook));
    } else {
      setState(DEFAULT_FORM_STATE);
    }
    setErrors({});
  }, [webhook]);

  // Auto-detect integration type from URL
  useEffect(() => {
    if (state.url && !isEdit) {
      const detected = detectIntegrationType(state.url);
      if (detected !== state.integration_type) {
        setState((prev) => ({ ...prev, integration_type: detected }));
      }
    }
  }, [state.url, isEdit, state.integration_type]);

  // Handle field change
  const handleChange = useCallback(
    <K extends keyof FormState>(field: K, value: FormState[K]) => {
      setState((prev) => ({ ...prev, [field]: value }));
    },
    []
  );

  // Handle event type toggle
  const toggleEventType = useCallback((eventType: WebhookEventType) => {
    setState((prev) => ({
      ...prev,
      event_types: prev.event_types.includes(eventType)
        ? prev.event_types.filter((t) => t !== eventType)
        : [...prev.event_types, eventType],
    }));
  }, []);

  // Handle custom header add/remove
  const addCustomHeader = useCallback(() => {
    setState((prev) => ({
      ...prev,
      custom_headers: [...prev.custom_headers, { key: '', value: '' }],
    }));
  }, []);

  const removeCustomHeader = useCallback((index: number) => {
    setState((prev) => ({
      ...prev,
      custom_headers: prev.custom_headers.filter((_, i) => i !== index),
    }));
  }, []);

  const updateCustomHeader = useCallback(
    (index: number, field: 'key' | 'value', value: string) => {
      setState((prev) => ({
        ...prev,
        custom_headers: prev.custom_headers.map((h, i) =>
          i === index ? { ...h, [field]: value } : h
        ),
      }));
    },
    []
  );

  // Handle form submission
  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      const validationErrors = validateForm(state);
      setErrors(validationErrors);

      if (Object.keys(validationErrors).length > 0) {
        return;
      }

      const payload = formStateToPayload(state, isEdit);
      await onSubmit(payload);
    },
    [state, isEdit, onSubmit]
  );

  return (
    <form
      onSubmit={(e) => void handleSubmit(e)}
      className="space-y-6"
      noValidate
      data-testid="webhook-form"
    >
      {/* API Error */}
      {apiError && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2"
        >
          <AlertCircle className="h-4 w-4 shrink-0 text-red-500" />
          <span className="flex-1 text-sm text-red-400">{apiError}</span>
          {onClearApiError && (
            <button
              type="button"
              onClick={onClearApiError}
              className="text-red-400 hover:text-red-300"
              aria-label="Dismiss error"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      )}

      {/* Basic Information */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-white">Basic Information</h3>

        {/* Name */}
        <div>
          <label htmlFor="webhook-name" className="block text-sm font-medium text-gray-300">
            Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            id="webhook-name"
            value={state.name}
            onChange={(e) => handleChange('name', e.target.value)}
            maxLength={100}
            className={clsx(
              'mt-1 block w-full rounded-lg border bg-[#1A1A1A] px-3 py-2 text-white focus:outline-none focus:ring-2',
              errors.name
                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
            )}
            placeholder="My Slack Webhook"
            disabled={isSubmitting}
          />
          {errors.name && <p className="mt-1 text-sm text-red-500">{errors.name}</p>}
        </div>

        {/* URL */}
        <div>
          <label htmlFor="webhook-url" className="block text-sm font-medium text-gray-300">
            URL <span className="text-red-500">*</span>
          </label>
          <input
            type="url"
            id="webhook-url"
            value={state.url}
            onChange={(e) => handleChange('url', e.target.value)}
            className={clsx(
              'mt-1 block w-full rounded-lg border bg-[#1A1A1A] px-3 py-2 text-white focus:outline-none focus:ring-2',
              errors.url
                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
            )}
            placeholder="https://hooks.slack.com/services/..."
            disabled={isSubmitting}
          />
          {errors.url && <p className="mt-1 text-sm text-red-500">{errors.url}</p>}
        </div>

        {/* Integration Type */}
        <div>
          <label htmlFor="webhook-integration" className="block text-sm font-medium text-gray-300">
            Integration Type
          </label>
          <select
            id="webhook-integration"
            value={state.integration_type}
            onChange={(e) => handleChange('integration_type', e.target.value as IntegrationType)}
            className="mt-1 block w-full rounded-lg border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
            disabled={isSubmitting}
          >
            {INTEGRATION_TYPES.map((type) => (
              <option key={type} value={type}>
                {INTEGRATION_INFO[type].label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-gray-500">
            Integration type affects payload formatting
          </p>
        </div>

        {/* Enabled Toggle */}
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-gray-300">Enabled</span>
            <p className="text-xs text-gray-500">Webhook will receive events when enabled</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={state.enabled}
            onClick={() => handleChange('enabled', !state.enabled)}
            className={clsx(
              'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1F1F1F]',
              state.enabled ? 'bg-[#76B900]' : 'bg-gray-600'
            )}
            disabled={isSubmitting}
          >
            <span
              className={clsx(
                'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                state.enabled ? 'translate-x-6' : 'translate-x-1'
              )}
            />
          </button>
        </div>
      </div>

      {/* Event Types */}
      <div className="space-y-4 border-t border-gray-800 pt-6">
        <div>
          <h3 className="text-sm font-semibold text-white">
            Event Types <span className="text-red-500">*</span>
          </h3>
          <p className="text-xs text-gray-500">Select which events trigger this webhook</p>
        </div>

        <div className="flex flex-wrap gap-2">
          {WEBHOOK_EVENT_TYPES.map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => toggleEventType(type)}
              className={clsx(
                'rounded-full px-3 py-1.5 text-sm font-medium transition-colors',
                state.event_types.includes(type)
                  ? 'bg-[#76B900] text-black'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              )}
              disabled={isSubmitting}
            >
              {WEBHOOK_EVENT_LABELS[type]}
            </button>
          ))}
        </div>
        {errors.event_types && (
          <p className="text-sm text-red-500">{errors.event_types}</p>
        )}
      </div>

      {/* Authentication */}
      <div className="space-y-4 border-t border-gray-800 pt-6">
        <h3 className="text-sm font-semibold text-white">Authentication</h3>

        {/* Auth Type */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {AUTH_TYPES.map((authType) => (
            <button
              key={authType.value}
              type="button"
              onClick={() => handleChange('auth_type', authType.value)}
              className={clsx(
                'rounded-lg border px-3 py-2 text-left text-sm transition-colors',
                state.auth_type === authType.value
                  ? 'border-[#76B900] bg-[#76B900]/10 text-white'
                  : 'border-gray-700 bg-[#1A1A1A] text-gray-400 hover:border-gray-600 hover:text-gray-300'
              )}
              disabled={isSubmitting}
            >
              <p className="font-medium">{authType.label}</p>
            </button>
          ))}
        </div>

        {/* Bearer Token */}
        {state.auth_type === 'bearer' && (
          <div>
            <label
              htmlFor="webhook-auth-token"
              className="block text-sm font-medium text-gray-300"
            >
              Bearer Token <span className="text-red-500">*</span>
            </label>
            <input
              type="password"
              id="webhook-auth-token"
              value={state.auth_token}
              onChange={(e) => handleChange('auth_token', e.target.value)}
              className={clsx(
                'mt-1 block w-full rounded-lg border bg-[#1A1A1A] px-3 py-2 text-white focus:outline-none focus:ring-2',
                errors.auth_token
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
              )}
              placeholder="Your bearer token"
              disabled={isSubmitting}
            />
            {errors.auth_token && (
              <p className="mt-1 text-sm text-red-500">{errors.auth_token}</p>
            )}
          </div>
        )}

        {/* Basic Auth */}
        {state.auth_type === 'basic' && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label
                htmlFor="webhook-auth-username"
                className="block text-sm font-medium text-gray-300"
              >
                Username <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="webhook-auth-username"
                value={state.auth_username}
                onChange={(e) => handleChange('auth_username', e.target.value)}
                className={clsx(
                  'mt-1 block w-full rounded-lg border bg-[#1A1A1A] px-3 py-2 text-white focus:outline-none focus:ring-2',
                  errors.auth_username
                    ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                    : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
                )}
                disabled={isSubmitting}
              />
              {errors.auth_username && (
                <p className="mt-1 text-sm text-red-500">{errors.auth_username}</p>
              )}
            </div>
            <div>
              <label
                htmlFor="webhook-auth-password"
                className="block text-sm font-medium text-gray-300"
              >
                Password <span className="text-red-500">*</span>
              </label>
              <input
                type="password"
                id="webhook-auth-password"
                value={state.auth_password}
                onChange={(e) => handleChange('auth_password', e.target.value)}
                className={clsx(
                  'mt-1 block w-full rounded-lg border bg-[#1A1A1A] px-3 py-2 text-white focus:outline-none focus:ring-2',
                  errors.auth_password
                    ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                    : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
                )}
                disabled={isSubmitting}
              />
              {errors.auth_password && (
                <p className="mt-1 text-sm text-red-500">{errors.auth_password}</p>
              )}
            </div>
          </div>
        )}

        {/* Custom Header Auth */}
        {state.auth_type === 'header' && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label
                htmlFor="webhook-auth-header-name"
                className="block text-sm font-medium text-gray-300"
              >
                Header Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="webhook-auth-header-name"
                value={state.auth_header_name}
                onChange={(e) => handleChange('auth_header_name', e.target.value)}
                className={clsx(
                  'mt-1 block w-full rounded-lg border bg-[#1A1A1A] px-3 py-2 text-white focus:outline-none focus:ring-2',
                  errors.auth_header_name
                    ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                    : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
                )}
                placeholder="X-API-Key"
                disabled={isSubmitting}
              />
              {errors.auth_header_name && (
                <p className="mt-1 text-sm text-red-500">{errors.auth_header_name}</p>
              )}
            </div>
            <div>
              <label
                htmlFor="webhook-auth-header-value"
                className="block text-sm font-medium text-gray-300"
              >
                Header Value <span className="text-red-500">*</span>
              </label>
              <input
                type="password"
                id="webhook-auth-header-value"
                value={state.auth_header_value}
                onChange={(e) => handleChange('auth_header_value', e.target.value)}
                className={clsx(
                  'mt-1 block w-full rounded-lg border bg-[#1A1A1A] px-3 py-2 text-white focus:outline-none focus:ring-2',
                  errors.auth_header_value
                    ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                    : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
                )}
                disabled={isSubmitting}
              />
              {errors.auth_header_value && (
                <p className="mt-1 text-sm text-red-500">{errors.auth_header_value}</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Custom Headers */}
      <div className="space-y-4 border-t border-gray-800 pt-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Custom Headers</h3>
            <p className="text-xs text-gray-500">Additional headers to include in requests</p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={addCustomHeader}
            disabled={isSubmitting}
          >
            Add Header
          </Button>
        </div>

        {state.custom_headers.length > 0 && (
          <div className="space-y-2">
            {state.custom_headers.map((header, index) => (
              <div key={index} className="flex items-center gap-2">
                <input
                  type="text"
                  value={header.key}
                  onChange={(e) => updateCustomHeader(index, 'key', e.target.value)}
                  placeholder="Header name"
                  className="flex-1 rounded-lg border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
                  disabled={isSubmitting}
                />
                <input
                  type="text"
                  value={header.value}
                  onChange={(e) => updateCustomHeader(index, 'value', e.target.value)}
                  placeholder="Header value"
                  className="flex-1 rounded-lg border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
                  disabled={isSubmitting}
                />
                <button
                  type="button"
                  onClick={() => removeCustomHeader(index)}
                  className="rounded p-2 text-gray-400 hover:bg-gray-700 hover:text-red-400"
                  aria-label={`Remove header ${header.key || index + 1}`}
                  disabled={isSubmitting}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Retry Configuration */}
      <div className="space-y-4 border-t border-gray-800 pt-6">
        <h3 className="text-sm font-semibold text-white">Retry Configuration</h3>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label
              htmlFor="webhook-max-retries"
              className="block text-sm font-medium text-gray-300"
            >
              Max Retries (0-10)
            </label>
            <input
              type="number"
              id="webhook-max-retries"
              value={state.max_retries}
              onChange={(e) =>
                handleChange('max_retries', Math.min(10, Math.max(0, parseInt(e.target.value) || 0)))
              }
              min={0}
              max={10}
              className="mt-1 block w-full rounded-lg border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
              disabled={isSubmitting}
            />
            <p className="mt-1 text-xs text-gray-500">Number of retry attempts on failure</p>
          </div>

          <div>
            <label
              htmlFor="webhook-retry-delay"
              className="block text-sm font-medium text-gray-300"
            >
              Retry Delay (seconds)
            </label>
            <input
              type="number"
              id="webhook-retry-delay"
              value={state.retry_delay_seconds}
              onChange={(e) =>
                handleChange(
                  'retry_delay_seconds',
                  Math.min(3600, Math.max(1, parseInt(e.target.value) || 1))
                )
              }
              min={1}
              max={3600}
              className="mt-1 block w-full rounded-lg border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
              disabled={isSubmitting}
            />
            <p className="mt-1 text-xs text-gray-500">
              Initial delay between retries (exponential backoff)
            </p>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-3 border-t border-gray-800 pt-6">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" isLoading={isSubmitting}>
          {isEdit ? 'Save Changes' : 'Create Webhook'}
        </Button>
      </div>
    </form>
  );
}
