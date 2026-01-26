/**
 * WebhookTestModal - Modal for testing a webhook with sample payload
 *
 * Features:
 * - Event type selector
 * - Test execution with loading state
 * - Results display (success/failure, response code, time)
 * - Response body preview
 *
 * @module components/webhooks/WebhookTestModal
 * @see NEM-3624 - Webhook Management Feature
 */

import { clsx } from 'clsx';
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  Play,
  XCircle,
} from 'lucide-react';
import { useCallback, useState } from 'react';

import { WEBHOOK_EVENT_TYPES, WEBHOOK_EVENT_LABELS } from '../../types/webhook';
import AnimatedModal from '../common/AnimatedModal';
import Button from '../common/Button';

import type { Webhook, WebhookEventType, WebhookTestResponse } from '../../types/webhook';

// ============================================================================
// Types
// ============================================================================

export interface WebhookTestModalProps {
  /** Webhook to test */
  webhook: Webhook | null;
  /** Whether the modal is open */
  isOpen: boolean;
  /** Close handler */
  onClose: () => void;
  /** Test handler */
  onTest: (webhookId: string, eventType: WebhookEventType) => Promise<WebhookTestResponse>;
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Test result display
 */
function TestResult({ result }: { result: WebhookTestResponse }) {
  const isSuccess = result.success;

  return (
    <div
      className={clsx(
        'rounded-lg border p-4',
        isSuccess
          ? 'border-green-500/30 bg-green-500/10'
          : 'border-red-500/30 bg-red-500/10'
      )}
      data-testid="test-result"
    >
      {/* Header */}
      <div className="flex items-center gap-2">
        {isSuccess ? (
          <CheckCircle2 className="h-5 w-5 text-green-400" />
        ) : (
          <XCircle className="h-5 w-5 text-red-400" />
        )}
        <span className={clsx('font-semibold', isSuccess ? 'text-green-400' : 'text-red-400')}>
          {isSuccess ? 'Test Passed' : 'Test Failed'}
        </span>
      </div>

      {/* Details */}
      <div className="mt-3 grid grid-cols-2 gap-4 text-sm">
        {/* Response Code */}
        <div>
          <span className="text-gray-500">Response Code</span>
          <p className="font-mono text-white">
            {result.status_code !== null ? (
              <span
                className={clsx(
                  'rounded px-2 py-0.5',
                  result.status_code >= 200 && result.status_code < 300
                    ? 'bg-green-500/20 text-green-400'
                    : result.status_code >= 400 && result.status_code < 500
                      ? 'bg-yellow-500/20 text-yellow-400'
                      : 'bg-red-500/20 text-red-400'
                )}
              >
                {result.status_code}
              </span>
            ) : (
              <span className="text-gray-500">N/A</span>
            )}
          </p>
        </div>

        {/* Response Time */}
        <div>
          <span className="text-gray-500">Response Time</span>
          <p className="flex items-center gap-1 text-white">
            <Clock className="h-4 w-4 text-gray-500" />
            {result.response_time_ms !== null ? `${result.response_time_ms}ms` : 'N/A'}
          </p>
        </div>
      </div>

      {/* Error Message */}
      {result.error_message && (
        <div className="mt-3">
          <span className="text-sm text-gray-500">Error</span>
          <p className="mt-1 rounded bg-red-500/20 px-3 py-2 text-sm text-red-300">
            {result.error_message}
          </p>
        </div>
      )}

      {/* Response Body Preview */}
      {result.response_body && (
        <div className="mt-3">
          <span className="text-sm text-gray-500">Response Body (truncated)</span>
          <pre className="mt-1 max-h-32 overflow-auto rounded bg-[#1A1A1A] p-3 text-xs text-gray-300">
            {result.response_body}
          </pre>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * WebhookTestModal for testing webhook delivery
 */
export default function WebhookTestModal({
  webhook,
  isOpen,
  onClose,
  onTest,
}: WebhookTestModalProps) {
  const [selectedEventType, setSelectedEventType] = useState<WebhookEventType>('alert_fired');
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<WebhookTestResponse | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  // Reset state when modal opens/closes or webhook changes
  const handleClose = useCallback(() => {
    setTestResult(null);
    setTestError(null);
    setIsTesting(false);
    onClose();
  }, [onClose]);

  // Run test
  const handleTest = useCallback(async () => {
    if (!webhook) return;

    setIsTesting(true);
    setTestResult(null);
    setTestError(null);

    try {
      const result = await onTest(webhook.id, selectedEventType);
      setTestResult(result);
    } catch (err) {
      setTestError(err instanceof Error ? err.message : 'Test failed');
    } finally {
      setIsTesting(false);
    }
  }, [webhook, selectedEventType, onTest]);

  if (!webhook) return null;

  return (
    <AnimatedModal
      isOpen={isOpen}
      onClose={handleClose}
      size="md"
      variant="scale"
      aria-labelledby="test-modal-title"
      modalName="webhook-test"
    >
      <div className="p-6" data-testid="webhook-test-modal">
        {/* Header */}
        <div className="mb-6">
          <h2 id="test-modal-title" className="text-xl font-semibold text-white">
            Test Webhook
          </h2>
          <p className="mt-1 text-sm text-gray-400">{webhook.name}</p>
          <p className="mt-1 max-w-full truncate text-xs text-gray-500" title={webhook.url}>
            {webhook.url}
          </p>
        </div>

        {/* Event Type Selector */}
        <div className="mb-6">
          <label
            htmlFor="test-event-type"
            className="block text-sm font-medium text-gray-300"
          >
            Event Type
          </label>
          <p className="mb-2 text-xs text-gray-500">
            Select the event type to use for the test payload
          </p>
          <select
            id="test-event-type"
            value={selectedEventType}
            onChange={(e) => setSelectedEventType(e.target.value as WebhookEventType)}
            className="w-full rounded-lg border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
            disabled={isTesting}
          >
            {WEBHOOK_EVENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {WEBHOOK_EVENT_LABELS[type]}
              </option>
            ))}
          </select>
        </div>

        {/* Test Button */}
        <div className="mb-6">
          <Button
            variant="primary"
            fullWidth
            leftIcon={isTesting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            onClick={() => void handleTest()}
            disabled={isTesting}
          >
            {isTesting ? 'Sending Test...' : 'Send Test'}
          </Button>
        </div>

        {/* Test Error */}
        {testError && (
          <div
            className="mb-6 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3"
            role="alert"
          >
            <AlertCircle className="h-5 w-5 shrink-0 text-red-500" />
            <span className="text-sm text-red-400">{testError}</span>
          </div>
        )}

        {/* Test Result */}
        {testResult && <TestResult result={testResult} />}

        {/* Footer */}
        <div className="mt-6 flex justify-end">
          <Button variant="ghost" onClick={handleClose}>
            Close
          </Button>
        </div>
      </div>
    </AnimatedModal>
  );
}
