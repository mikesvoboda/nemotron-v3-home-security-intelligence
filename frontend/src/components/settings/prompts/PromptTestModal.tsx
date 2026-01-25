/**
 * PromptTestModal - A/B Testing Modal for Prompt Configuration
 *
 * Allows users to test prompt changes against real events before saving.
 * Users can:
 * 1. Select a test event from history
 * 2. Run inference with both current and modified configs
 * 3. Compare results side-by-side
 * 4. Decide whether to save based on results
 *
 * @see NEM-2698 - Implement prompt A/B testing UI with real inference comparison
 */

import { useQuery } from '@tanstack/react-query';
import { Dialog, DialogPanel, Title, Button } from '@tremor/react';
import { X, Play, AlertCircle } from 'lucide-react';
import { useState, useCallback, useEffect } from 'react';

import EventSelector from './EventSelector';
import TestResultsComparison from './TestResultsComparison';
import { usePromptTest, usePromptConfig } from '../../../hooks/usePromptQueries';
import { fetchEvents } from '../../../services/api';
import { queryKeys } from '../../../services/queryClient';

import type { TestResult } from './TestResultsComparison';
import type { AIModelEnum } from '../../../types/promptManagement';

// ============================================================================
// Types
// ============================================================================

export interface PromptTestModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** The AI model being tested */
  model: AIModelEnum;
  /** Modified configuration to test */
  modifiedConfig: Record<string, unknown>;
}

// ============================================================================
// Component
// ============================================================================

/**
 * Modal for A/B testing prompt configurations.
 *
 * Fetches recent events, allows user to select one, and runs
 * inference with both current and modified configs for comparison.
 *
 * @example
 * ```tsx
 * <PromptTestModal
 *   isOpen={isTestModalOpen}
 *   onClose={() => setIsTestModalOpen(false)}
 *   model={AIModelEnum.NEMOTRON}
 *   modifiedConfig={currentConfig}
 * />
 * ```
 */
export default function PromptTestModal({
  isOpen,
  onClose,
  model,
  modifiedConfig,
}: PromptTestModalProps) {
  // State
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);
  const [currentResult, setCurrentResult] = useState<TestResult | null>(null);
  const [modifiedResult, setModifiedResult] = useState<TestResult | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  // Fetch current config for comparison
  const { data: currentConfig } = usePromptConfig(model, { enabled: isOpen });

  // Fetch recent events for selection
  const {
    data: eventsData,
    isLoading: eventsLoading,
    error: eventsError,
  } = useQuery({
    queryKey: [...queryKeys.events.all, 'test-selection', { limit: 20 }],
    queryFn: () => fetchEvents({ limit: 20 }),
    enabled: isOpen,
    staleTime: 30000, // 30 seconds
  });

  // Prompt test mutation hooks
  const currentTestMutation = usePromptTest();
  const modifiedTestMutation = usePromptTest();

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setSelectedEventId(null);
      setCurrentResult(null);
      setModifiedResult(null);
      setTestError(null);
      setIsRunning(false);
      currentTestMutation.reset();
      modifiedTestMutation.reset();
    }
  }, [isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle running the A/B test
  const handleRunTest = useCallback(async () => {
    if (!selectedEventId || !currentConfig) {
      setTestError('Please select an event to test');
      return;
    }

    setIsRunning(true);
    setTestError(null);
    setCurrentResult(null);
    setModifiedResult(null);

    try {
      // Run both tests in parallel
      const [currentRes, modifiedRes] = await Promise.all([
        currentTestMutation.mutateAsync({
          model,
          config: currentConfig.config,
          eventId: selectedEventId,
        }),
        modifiedTestMutation.mutateAsync({
          model,
          config: modifiedConfig,
          eventId: selectedEventId,
        }),
      ]);

      setCurrentResult(currentRes);
      setModifiedResult(modifiedRes);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to run A/B test';
      setTestError(errorMessage);
    } finally {
      setIsRunning(false);
    }
  }, [
    selectedEventId,
    currentConfig,
    model,
    modifiedConfig,
    currentTestMutation,
    modifiedTestMutation,
  ]);

  // Handle event selection
  const handleEventSelect = useCallback((eventId: number) => {
    setSelectedEventId(eventId);
    // Clear previous results when selecting a new event
    setCurrentResult(null);
    setModifiedResult(null);
    setTestError(null);
  }, []);

  // Extract events array
  const events = eventsData?.items ?? [];

  return (
    <Dialog open={isOpen} onClose={onClose} static={true}>
      <DialogPanel className="max-w-4xl border border-gray-700 bg-[#1A1A1A]">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <Title className="text-white">A/B Test Configuration</Title>
            <p className="mt-1 text-sm text-gray-400">
              Compare your changes against the current configuration
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Event Selection */}
        <div className="mb-6">
          <h3 className="mb-3 text-sm font-medium text-gray-200">Select Test Event</h3>
          {eventsError ? (
            <div className="rounded-lg border border-red-800 bg-red-900/20 p-4">
              <div className="flex items-center gap-2 text-red-400">
                <AlertCircle className="h-4 w-4" />
                <span>Failed to load events: {eventsError.message}</span>
              </div>
            </div>
          ) : (
            <EventSelector
              events={events}
              selectedEventId={selectedEventId}
              onSelect={handleEventSelect}
              disabled={isRunning}
              isLoading={eventsLoading}
            />
          )}
        </div>

        {/* Run Test Button */}
        <div className="mb-6 flex justify-center">
          <Button
            icon={Play}
            onClick={() => void handleRunTest()}
            disabled={!selectedEventId || isRunning || !currentConfig}
            loading={isRunning}
            size="lg"
          >
            {isRunning ? 'Running Test...' : 'Run Test'}
          </Button>
        </div>

        {/* Results Section */}
        {(currentResult || modifiedResult || testError || isRunning) && (
          <div className="mb-6">
            <h3 className="mb-3 text-sm font-medium text-gray-200">Results</h3>
            <TestResultsComparison
              currentResult={currentResult}
              modifiedResult={modifiedResult}
              currentVersion={currentConfig?.version}
              isLoading={isRunning}
              error={testError}
            />
          </div>
        )}

        {/* Rate Limit Warning */}
        <div className="mb-4 rounded-lg border border-yellow-800/50 bg-yellow-900/10 p-3">
          <p className="text-xs text-yellow-400">
            <strong>Note:</strong> A/B testing is rate-limited to protect AI services. Each test
            runs inference on both configurations, which may take a few seconds.
          </p>
        </div>

        {/* Actions */}
        <div className="flex justify-end">
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </DialogPanel>
    </Dialog>
  );
}
