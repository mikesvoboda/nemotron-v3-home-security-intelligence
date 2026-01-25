/**
 * WebhookList - Table of webhooks with management actions
 *
 * Displays webhooks in a table format with:
 * - Name, URL, Event Types, Status columns
 * - Success rate indicator
 * - Enable/disable toggle
 * - Edit, delete, and test action buttons
 *
 * @module components/webhooks/WebhookList
 * @see NEM-3624 - Webhook Management Feature
 */

import { clsx } from 'clsx';
import {
  Edit,
  ExternalLink,
  MoreVertical,
  Play,
  Trash2,
} from 'lucide-react';
import { useCallback, useState } from 'react';

import {
  WEBHOOK_EVENT_LABELS,
  INTEGRATION_INFO,
  calculateSuccessRate,
  isWebhookHealthy,
  isWebhookUnhealthy,
} from '../../types/webhook';
import EmptyState from '../common/EmptyState';

import type {
  Webhook,
  WebhookEventType,
  IntegrationType,
} from '../../types/webhook';

export interface WebhookListProps {
  /** List of webhooks to display */
  webhooks: Webhook[];
  /** Whether data is loading */
  isLoading?: boolean;
  /** Handler for toggling webhook enabled state */
  onToggle: (id: string, enabled: boolean) => void;
  /** Handler for editing a webhook */
  onEdit: (webhook: Webhook) => void;
  /** Handler for deleting a webhook */
  onDelete: (webhook: Webhook) => void;
  /** Handler for testing a webhook */
  onTest: (webhook: Webhook) => void;
  /** Handler for viewing delivery history */
  onViewHistory: (webhook: Webhook) => void;
  /** Whether any toggle is in progress */
  isToggling?: boolean;
  /** ID of webhook currently being toggled */
  togglingId?: string | null;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get integration icon component
 */
function IntegrationIcon({ type }: { type: IntegrationType }) {
  // Simple icon representations based on integration type
  const iconClasses = 'h-4 w-4';

  switch (type) {
    case 'slack':
      return (
        <svg className={iconClasses} viewBox="0 0 24 24" fill="currentColor">
          <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zm10.124 2.521a2.528 2.528 0 0 1 2.52-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.52V8.834zm-1.271 0a2.528 2.528 0 0 1-2.521 2.521 2.528 2.528 0 0 1-2.521-2.521V2.522A2.528 2.528 0 0 1 15.166 0a2.528 2.528 0 0 1 2.521 2.522v6.312zm-2.521 10.124a2.528 2.528 0 0 1 2.521 2.52A2.528 2.528 0 0 1 15.166 24a2.528 2.528 0 0 1-2.521-2.522v-2.52h2.521zm0-1.271a2.528 2.528 0 0 1-2.521-2.521 2.528 2.528 0 0 1 2.521-2.521h6.312A2.528 2.528 0 0 1 24 15.166a2.528 2.528 0 0 1-2.522 2.521h-6.312z" />
        </svg>
      );
    case 'discord':
      return (
        <svg className={iconClasses} viewBox="0 0 24 24" fill="currentColor">
          <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
        </svg>
      );
    case 'telegram':
      return (
        <svg className={iconClasses} viewBox="0 0 24 24" fill="currentColor">
          <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
        </svg>
      );
    case 'teams':
      return (
        <svg className={iconClasses} viewBox="0 0 24 24" fill="currentColor">
          <path d="M20.625 8.073h-5.27v10.575h3.188c1.15 0 2.082-.932 2.082-2.082V8.073zm-3.723 13.5c-1.725 0-3.127-1.401-3.127-3.127V6.955c0-1.726 1.402-3.127 3.127-3.127h3.724c1.726 0 3.127 1.401 3.127 3.127v11.491c0 1.726-1.401 3.127-3.127 3.127h-3.724zm-4.402-9.073H5.375v6.066c0 1.15.932 2.082 2.082 2.082h5.043v-8.148zm2.083-4.925H7.457c-1.726 0-3.127 1.401-3.127 3.127v8.244c0 1.726 1.401 3.127 3.127 3.127h7.126c1.726 0 3.127-1.401 3.127-3.127V10.7c0-1.726-1.401-3.125-3.127-3.125zM8.531 5.25a2.343 2.343 0 1 1 0-4.687 2.343 2.343 0 0 1 0 4.687zm8.438 0a1.875 1.875 0 1 1 0-3.75 1.875 1.875 0 0 1 0 3.75z" />
        </svg>
      );
    default:
      return <ExternalLink className={iconClasses} />;
  }
}

/**
 * Format event types for display
 */
function EventTypeBadges({ eventTypes }: { eventTypes: WebhookEventType[] }) {
  const maxVisible = 2;
  const visible = eventTypes.slice(0, maxVisible);
  const remaining = eventTypes.length - maxVisible;

  return (
    <div className="flex flex-wrap gap-1">
      {visible.map((type) => (
        <span
          key={type}
          className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-300"
        >
          {WEBHOOK_EVENT_LABELS[type]}
        </span>
      ))}
      {remaining > 0 && (
        <span className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-400">
          +{remaining} more
        </span>
      )}
    </div>
  );
}

/**
 * Success rate badge with color coding
 */
function SuccessRateBadge({ webhook }: { webhook: Webhook }) {
  const rate = calculateSuccessRate(webhook);
  const healthy = isWebhookHealthy(webhook);
  const unhealthy = isWebhookUnhealthy(webhook);

  const colorClasses = unhealthy
    ? 'bg-red-500/10 text-red-400 border-red-500/30'
    : healthy
      ? 'bg-green-500/10 text-green-400 border-green-500/30'
      : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30';

  return (
    <span
      className={`rounded border px-2 py-0.5 text-xs font-medium ${colorClasses}`}
    >
      {rate}%
    </span>
  );
}

/**
 * Loading skeleton for the table
 */
function TableSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="mb-4 h-10 rounded bg-gray-700" />
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="mb-2 h-16 rounded bg-gray-800" />
      ))}
    </div>
  );
}

/**
 * Action dropdown for webhook row
 */
function ActionDropdown({
  onEdit,
  onDelete,
  onTest,
  onViewHistory,
}: {
  onEdit: () => void;
  onDelete: () => void;
  onTest: () => void;
  onViewHistory: () => void;
}) {
  const [isOpen, setIsOpen] = useState(false);

  const handleAction = useCallback(
    (action: () => void) => {
      action();
      setIsOpen(false);
    },
    []
  );

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="rounded p-1.5 text-gray-400 hover:bg-gray-700 hover:text-white"
        aria-label="More actions"
        aria-haspopup="true"
        aria-expanded={isOpen}
      >
        <MoreVertical className="h-4 w-4" />
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
            aria-hidden="true"
          />

          {/* Dropdown menu */}
          <div className="absolute right-0 z-20 mt-1 w-48 rounded-lg border border-gray-700 bg-[#1A1A1A] py-1 shadow-xl">
            <button
              type="button"
              onClick={() => handleAction(onTest)}
              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 hover:text-white"
            >
              <Play className="h-4 w-4" />
              Test Webhook
            </button>
            <button
              type="button"
              onClick={() => handleAction(onViewHistory)}
              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 hover:text-white"
            >
              <ExternalLink className="h-4 w-4" />
              View Deliveries
            </button>
            <button
              type="button"
              onClick={() => handleAction(onEdit)}
              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 hover:text-white"
            >
              <Edit className="h-4 w-4" />
              Edit
            </button>
            <hr className="my-1 border-gray-700" />
            <button
              type="button"
              onClick={() => handleAction(onDelete)}
              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 hover:text-red-300"
            >
              <Trash2 className="h-4 w-4" />
              Delete
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/**
 * WebhookList component displays webhooks in a table format
 */
export default function WebhookList({
  webhooks,
  isLoading = false,
  onToggle,
  onEdit,
  onDelete,
  onTest,
  onViewHistory,
  isToggling = false,
  togglingId = null,
  className = '',
}: WebhookListProps) {
  if (isLoading) {
    return (
      <div className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-6 ${className}`}>
        <TableSkeleton />
      </div>
    );
  }

  if (webhooks.length === 0) {
    return (
      <EmptyState
        icon={ExternalLink}
        title="No Webhooks Configured"
        description="Create your first webhook to receive real-time notifications when events occur."
        variant="default"
        className={className}
      />
    );
  }

  return (
    <div
      className={`overflow-hidden rounded-lg border border-gray-800 bg-[#1F1F1F] ${className}`}
      data-testid="webhook-list"
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[800px]">
          <thead>
            <tr className="border-b border-gray-700 bg-[#1A1A1A]">
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">
                Webhook
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">
                URL
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">
                Events
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">
                Status
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">
                Success Rate
              </th>
              <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-400">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {webhooks.map((webhook) => {
              const isCurrentlyToggling = isToggling && togglingId === webhook.id;

              return (
                <tr
                  key={webhook.id}
                  className="transition-colors hover:bg-gray-800/50"
                  data-testid={`webhook-row-${webhook.id}`}
                >
                  {/* Name & Integration */}
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-700 text-gray-300">
                        <IntegrationIcon type={webhook.integration_type} />
                      </div>
                      <div>
                        <p className="font-medium text-white">{webhook.name}</p>
                        <p className="text-xs text-gray-500">
                          {INTEGRATION_INFO[webhook.integration_type].label}
                        </p>
                      </div>
                    </div>
                  </td>

                  {/* URL */}
                  <td className="px-4 py-4">
                    <p
                      className="max-w-[200px] truncate text-sm text-gray-300"
                      title={webhook.url}
                    >
                      {webhook.url}
                    </p>
                  </td>

                  {/* Event Types */}
                  <td className="px-4 py-4">
                    <EventTypeBadges eventTypes={webhook.event_types} />
                  </td>

                  {/* Status Toggle */}
                  <td className="px-4 py-4">
                    <button
                      type="button"
                      role="switch"
                      aria-checked={webhook.enabled}
                      aria-label={webhook.enabled ? 'Disable webhook' : 'Enable webhook'}
                      onClick={() => onToggle(webhook.id, !webhook.enabled)}
                      disabled={isCurrentlyToggling}
                      className={clsx(
                        'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1F1F1F]',
                        webhook.enabled ? 'bg-[#76B900]' : 'bg-gray-600',
                        isCurrentlyToggling && 'cursor-wait opacity-50'
                      )}
                    >
                      <span
                        className={clsx(
                          'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                          webhook.enabled ? 'translate-x-6' : 'translate-x-1'
                        )}
                      />
                    </button>
                  </td>

                  {/* Success Rate */}
                  <td className="px-4 py-4">
                    {webhook.total_deliveries > 0 ? (
                      <div className="flex items-center gap-2">
                        <SuccessRateBadge webhook={webhook} />
                        <span className="text-xs text-gray-500">
                          ({webhook.successful_deliveries}/{webhook.total_deliveries})
                        </span>
                      </div>
                    ) : (
                      <span className="text-sm text-gray-500">No deliveries</span>
                    )}
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-4">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        onClick={() => onTest(webhook)}
                        className="rounded p-1.5 text-gray-400 hover:bg-gray-700 hover:text-[#76B900]"
                        title="Test webhook"
                        aria-label={`Test ${webhook.name}`}
                      >
                        <Play className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => onEdit(webhook)}
                        className="rounded p-1.5 text-gray-400 hover:bg-gray-700 hover:text-white"
                        title="Edit webhook"
                        aria-label={`Edit ${webhook.name}`}
                      >
                        <Edit className="h-4 w-4" />
                      </button>
                      <ActionDropdown
                        onEdit={() => onEdit(webhook)}
                        onDelete={() => onDelete(webhook)}
                        onTest={() => onTest(webhook)}
                        onViewHistory={() => onViewHistory(webhook)}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
