/**
 * BatchAuditModal Component
 *
 * Modal dialog for triggering batch AI audit processing.
 * Allows configuring limit, min risk score, and force re-evaluate options.
 *
 * @see frontend/src/services/auditApi.ts - triggerBatchAudit function
 */

import { Dialog, Transition } from '@headlessui/react';
import { AlertCircle, Play, X } from 'lucide-react';
import { Fragment, useEffect, useState } from 'react';

import { triggerBatchAudit, AuditApiError, type BatchAuditResponse } from '../../services/auditApi';
import IconButton from '../common/IconButton';

// ============================================================================
// Types
// ============================================================================

export interface BatchAuditModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal should close */
  onClose: () => void;
  /** Optional callback when batch audit is successfully triggered */
  onSuccess?: (response: BatchAuditResponse) => void;
}

// ============================================================================
// Component
// ============================================================================

/**
 * BatchAuditModal - Modal for configuring and triggering batch AI audit.
 *
 * Features:
 * - Configurable event limit (1-1000, default 50)
 * - Configurable minimum risk score filter (0-100, default 50)
 * - Force re-evaluate checkbox for already-evaluated events
 * - Loading state during submission
 * - Error display with clear action
 */
export default function BatchAuditModal({ isOpen, onClose, onSuccess }: BatchAuditModalProps) {
  // Form state
  const [limit, setLimit] = useState(50);
  const [minRiskScore, setMinRiskScore] = useState(50);
  const [forceReevaluate, setForceReevaluate] = useState(false);

  // UI state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form state when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setLimit(50);
      setMinRiskScore(50);
      setForceReevaluate(false);
      setError(null);
    }
  }, [isOpen]);

  // Clear error when form changes
  const handleLimitChange = (value: number) => {
    setLimit(value);
    setError(null);
  };

  const handleMinRiskScoreChange = (value: number) => {
    setMinRiskScore(value);
    setError(null);
  };

  const handleForceChange = (checked: boolean) => {
    setForceReevaluate(checked);
    setError(null);
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await triggerBatchAudit(limit, minRiskScore, forceReevaluate);
      onSuccess?.(response);
      onClose();
    } catch (err) {
      if (err instanceof AuditApiError) {
        setError(err.message);
      } else {
        setError('Failed to trigger batch audit. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        {/* Dark backdrop */}
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/75" aria-hidden="true" />
        </Transition.Child>

        {/* Modal content */}
        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel
                className="w-full max-w-md transform overflow-hidden rounded-xl border border-gray-800 bg-[#1A1A1A] shadow-2xl transition-all"
                data-testid="batch-audit-modal"
              >
                {/* Header */}
                <div className="flex items-start justify-between border-b border-gray-800 p-6">
                  <div>
                    <Dialog.Title as="h2" className="text-xl font-bold text-white">
                      Trigger Batch Audit
                    </Dialog.Title>
                    <p className="mt-1 text-sm text-gray-400">
                      Queue multiple events for AI self-evaluation
                    </p>
                  </div>
                  <IconButton
                    icon={<X />}
                    aria-label="Close modal"
                    onClick={onClose}
                    variant="ghost"
                    size="md"
                  />
                </div>

                {/* Form */}
                <form onSubmit={(e) => void handleSubmit(e)}>
                  <div className="space-y-6 p-6">
                    {/* Error Banner */}
                    {error && (
                      <div className="rounded-lg border border-red-800 bg-red-900/20 p-4">
                        <div className="flex items-center gap-2 text-red-400">
                          <AlertCircle className="h-5 w-5 flex-shrink-0" />
                          <span className="text-sm">{error}</span>
                        </div>
                      </div>
                    )}

                    {/* Limit Input */}
                    <div>
                      <label
                        htmlFor="batch-limit"
                        className="block text-sm font-medium text-gray-300"
                      >
                        Event Limit
                      </label>
                      <p className="mt-1 text-xs text-gray-500">
                        Maximum number of events to process (1-1000)
                      </p>
                      <input
                        id="batch-limit"
                        type="number"
                        min={1}
                        max={1000}
                        value={limit}
                        onChange={(e) => {
                          const val = e.target.valueAsNumber;
                          handleLimitChange(isNaN(val) ? 1 : val);
                        }}
                        className="mt-2 w-full rounded-lg border border-gray-700 bg-black/30 px-4 py-2 text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20"
                        data-testid="batch-audit-limit"
                      />
                    </div>

                    {/* Min Risk Score Input */}
                    <div>
                      <label
                        htmlFor="batch-min-risk"
                        className="block text-sm font-medium text-gray-300"
                      >
                        Minimum Risk Score
                      </label>
                      <p className="mt-1 text-xs text-gray-500">
                        Only process events with risk score at or above this value (0-100)
                      </p>
                      <input
                        id="batch-min-risk"
                        type="number"
                        min={0}
                        max={100}
                        value={minRiskScore}
                        onChange={(e) => {
                          const val = e.target.valueAsNumber;
                          handleMinRiskScoreChange(isNaN(val) ? 0 : val);
                        }}
                        className="mt-2 w-full rounded-lg border border-gray-700 bg-black/30 px-4 py-2 text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20"
                        data-testid="batch-audit-min-risk"
                      />
                    </div>

                    {/* Force Re-evaluate Checkbox */}
                    <div className="flex items-start gap-3">
                      <input
                        id="batch-force"
                        type="checkbox"
                        checked={forceReevaluate}
                        onChange={(e) => handleForceChange(e.target.checked)}
                        className="mt-0.5 h-4 w-4 rounded border-gray-600 bg-black/30 text-[#76B900] focus:ring-[#76B900] focus:ring-offset-0"
                        data-testid="batch-audit-force"
                      />
                      <div>
                        <label htmlFor="batch-force" className="text-sm font-medium text-gray-300">
                          Force Re-evaluate
                        </label>
                        <p className="text-xs text-gray-500">
                          Re-process events that have already been evaluated
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Footer */}
                  <div className="flex items-center justify-end gap-3 border-t border-gray-800 bg-black/20 p-6">
                    <button
                      type="button"
                      onClick={onClose}
                      disabled={isSubmitting}
                      className="rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-semibold text-black transition-colors hover:bg-[#8ACE00] disabled:cursor-not-allowed disabled:opacity-50"
                      data-testid="batch-audit-submit"
                    >
                      <Play className="h-4 w-4" />
                      {isSubmitting ? 'Processing...' : 'Start Batch Audit'}
                    </button>
                  </div>
                </form>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
