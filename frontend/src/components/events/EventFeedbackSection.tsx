/**
 * EventFeedbackSection component for submitting user feedback on event classifications.
 *
 * Allows users to mark events as:
 * - Correct: Classification was accurate
 * - False Positive: Event was incorrectly flagged as concerning
 * - Missed Detection: System failed to detect a concerning event
 * - Wrong Severity: Event was flagged but with wrong severity level
 *
 * NEM-2319: Add feedback buttons to EventDetailModal
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, ChevronDown, ChevronRight, Flag, Loader2, ThumbsDown, X } from 'lucide-react';
import { useCallback, useState } from 'react';

import {
  fetchEventFeedback,
  submitEventFeedback,
  ApiError,
  type EventFeedbackResponse,
  type FeedbackType,
} from '../../services/api';

export interface EventFeedbackSectionProps {
  /** Event ID to submit feedback for */
  eventId: number;
  /** Whether the event was calibration-adjusted (shows indicator) */
  calibrationAdjusted?: boolean;
  /** Additional CSS classes */
  className?: string;
}

interface FeedbackOption {
  type: FeedbackType;
  label: string;
  icon: React.ElementType;
  description: string;
}

const FEEDBACK_OPTIONS: FeedbackOption[] = [
  {
    type: 'accurate',
    label: 'Correct',
    icon: Check,
    description: 'Classification was accurate',
  },
  {
    type: 'false_positive',
    label: 'False Positive',
    icon: X,
    description: 'Event incorrectly flagged',
  },
  {
    type: 'missed_threat',
    label: 'Missed Detection',
    icon: Flag,
    description: 'System failed to detect threat',
  },
  {
    type: 'severity_wrong',
    label: 'Wrong Level',
    icon: ThumbsDown,
    description: 'Risk level was incorrect',
  },
];

/**
 * Format feedback type for display
 */
function formatFeedbackType(type: string): string {
  const option = FEEDBACK_OPTIONS.find((opt) => opt.type === type);
  return option?.label ?? type.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase());
}

/**
 * Get icon for feedback type
 */
function getFeedbackIcon(type: string): React.ElementType {
  const option = FEEDBACK_OPTIONS.find((opt) => opt.type === type);
  return option?.icon ?? Check;
}

/**
 * EventFeedbackSection component displays a collapsible feedback form
 * for users to classify event accuracy.
 */
export default function EventFeedbackSection({
  eventId,
  calibrationAdjusted = false,
  className = '',
}: EventFeedbackSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedType, setSelectedType] = useState<FeedbackType | null>(null);
  const [notes, setNotes] = useState('');
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const queryClient = useQueryClient();

  // Fetch existing feedback for this event
  const {
    data: existingFeedback,
    isLoading: isLoadingFeedback,
    error: feedbackError,
  } = useQuery<EventFeedbackResponse, ApiError>({
    queryKey: ['eventFeedback', eventId],
    queryFn: () => fetchEventFeedback(eventId),
    retry: false, // Don't retry on 404 (no feedback exists)
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Submit feedback mutation with optimistic update
  const submitMutation = useMutation({
    mutationFn: submitEventFeedback,
    onMutate: async (newFeedback) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['eventFeedback', eventId] });

      // Snapshot the previous value
      const previousFeedback = queryClient.getQueryData<EventFeedbackResponse>([
        'eventFeedback',
        eventId,
      ]);

      // Optimistically update to the new value
      const optimisticFeedback: EventFeedbackResponse = {
        id: 0, // Temporary ID
        event_id: newFeedback.event_id,
        feedback_type: newFeedback.feedback_type,
        notes: newFeedback.notes ?? null,
        created_at: new Date().toISOString(),
      };
      queryClient.setQueryData(['eventFeedback', eventId], optimisticFeedback);

      return { previousFeedback };
    },
    onError: (_err, _newFeedback, context) => {
      // Revert to previous value on error
      if (context?.previousFeedback) {
        queryClient.setQueryData(['eventFeedback', eventId], context.previousFeedback);
      } else {
        queryClient.removeQueries({ queryKey: ['eventFeedback', eventId] });
      }
    },
    onSuccess: (data) => {
      // Replace optimistic update with actual response
      queryClient.setQueryData(['eventFeedback', eventId], data);
      setSubmitSuccess(true);
      // Clear form state
      setSelectedType(null);
      setNotes('');
      // Auto-hide success after 3 seconds
      setTimeout(() => setSubmitSuccess(false), 3000);
    },
    onSettled: () => {
      // Invalidate feedback stats
      void queryClient.invalidateQueries({ queryKey: ['feedbackStats'] });
    },
  });

  const handleSubmit = useCallback(() => {
    if (!selectedType) return;

    submitMutation.mutate({
      event_id: eventId,
      feedback_type: selectedType,
      notes: notes.trim() || null,
    });
  }, [eventId, selectedType, notes, submitMutation]);

  const toggleExpanded = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  // Check if feedback already exists (404 error means no feedback)
  const hasFeedback = existingFeedback !== undefined && feedbackError === null;
  const is404Error = feedbackError instanceof ApiError && feedbackError.status === 404;
  const hasError = feedbackError !== null && !is404Error;

  // Render existing feedback in read-only mode
  if (hasFeedback && existingFeedback) {
    const FeedbackIcon = getFeedbackIcon(existingFeedback.feedback_type);
    return (
      <div className={`rounded-lg border border-gray-800 bg-black/20 p-4 ${className}`}>
        <div className="flex items-center gap-2">
          <FeedbackIcon className="h-4 w-4 text-[#76B900]" />
          <h3 className="text-sm font-semibold text-gray-400">Feedback Submitted</h3>
        </div>
        <div className="mt-3 flex items-center gap-2">
          <span className="rounded-full bg-[#76B900]/20 px-3 py-1 text-sm font-medium text-[#76B900]">
            {formatFeedbackType(existingFeedback.feedback_type)}
          </span>
          {calibrationAdjusted && (
            <span className="rounded-full bg-yellow-500/20 px-2 py-0.5 text-xs text-yellow-500">
              Calibration Adjusted
            </span>
          )}
        </div>
        {existingFeedback.notes && (
          <p className="mt-2 text-sm text-gray-400">{existingFeedback.notes}</p>
        )}
        <p className="mt-2 text-xs text-gray-500">
          Submitted {new Date(existingFeedback.created_at).toLocaleDateString()}
        </p>
      </div>
    );
  }

  // Loading state
  if (isLoadingFeedback) {
    return (
      <div className={`rounded-lg border border-gray-800 bg-black/20 p-4 ${className}`}>
        <div className="flex items-center justify-center gap-2 py-4">
          <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
          <span className="text-sm text-gray-400">Loading feedback...</span>
        </div>
      </div>
    );
  }

  // Error state (non-404)
  if (hasError) {
    return (
      <div className={`rounded-lg border border-red-800 bg-red-900/20 p-4 ${className}`}>
        <p className="text-sm text-red-400">Failed to load feedback. Please try again.</p>
      </div>
    );
  }

  return (
    <div
      className={`rounded-lg border border-gray-800 bg-black/20 ${className}`}
      data-testid="feedback-section"
    >
      {/* Collapsible header */}
      <button
        onClick={toggleExpanded}
        className="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-gray-800/30"
        aria-expanded={isExpanded}
        aria-controls="feedback-content"
        data-testid="feedback-toggle"
      >
        <div className="flex items-center gap-2">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-gray-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-400" />
          )}
          <span className="text-sm font-semibold text-gray-400">
            Was this classification correct?
          </span>
        </div>
        {calibrationAdjusted && !isExpanded && (
          <span className="rounded-full bg-yellow-500/20 px-2 py-0.5 text-xs text-yellow-500">
            Calibration Adjusted
          </span>
        )}
      </button>

      {/* Collapsible content */}
      {isExpanded && (
        <div id="feedback-content" className="border-t border-gray-800 p-4">
          {/* Calibration indicator */}
          {calibrationAdjusted && (
            <div className="mb-4 flex items-center gap-2 rounded-md bg-yellow-500/10 px-3 py-2 text-xs text-yellow-500">
              <Flag className="h-3.5 w-3.5" />
              <span>This event was adjusted by calibration settings</span>
            </div>
          )}

          {/* Success message */}
          {submitSuccess && (
            <div
              className="mb-4 flex items-center gap-2 rounded-md bg-green-900/20 px-3 py-2 text-sm text-green-400"
              data-testid="feedback-success"
            >
              <Check className="h-4 w-4" />
              <span>Feedback submitted successfully</span>
            </div>
          )}

          {/* Error message */}
          {submitMutation.isError && (
            <div
              className="mb-4 flex items-center gap-2 rounded-md bg-red-900/20 px-3 py-2 text-sm text-red-400"
              data-testid="feedback-error"
            >
              <X className="h-4 w-4" />
              <span>
                {submitMutation.error instanceof ApiError && submitMutation.error.status === 409
                  ? 'Feedback already submitted for this event'
                  : 'Failed to submit feedback. Please try again.'}
              </span>
            </div>
          )}

          {/* Feedback buttons */}
          <div className="grid grid-cols-2 gap-2" data-testid="feedback-buttons">
            {FEEDBACK_OPTIONS.map((option) => {
              const Icon = option.icon;
              const isSelected = selectedType === option.type;
              return (
                <button
                  key={option.type}
                  onClick={() => setSelectedType(option.type)}
                  className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                    isSelected
                      ? 'border-[#76B900] bg-[#76B900]/20 text-[#76B900]'
                      : 'border-gray-700 bg-gray-800/50 text-gray-300 hover:border-gray-600 hover:bg-gray-800'
                  }`}
                  aria-pressed={isSelected}
                  data-testid={`feedback-btn-${option.type}`}
                  title={option.description}
                >
                  <Icon className="h-4 w-4" />
                  <span>{option.label}</span>
                </button>
              );
            })}
          </div>

          {/* Notes textarea */}
          <div className="mt-4">
            <label htmlFor="feedback-notes" className="mb-1 block text-xs text-gray-500">
              Notes (optional)
            </label>
            <textarea
              id="feedback-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add any additional context..."
              rows={2}
              maxLength={1000}
              className="w-full rounded-lg border border-gray-700 bg-black/30 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 transition-colors focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20"
              data-testid="feedback-notes"
            />
            <div className="mt-1 text-right text-xs text-gray-500">{notes.length}/1000</div>
          </div>

          {/* Submit button */}
          <div className="mt-4 flex justify-end">
            <button
              onClick={handleSubmit}
              disabled={!selectedType || submitMutation.isPending}
              className="flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-semibold text-black transition-all hover:bg-[#88d200] active:bg-[#68a000] disabled:cursor-not-allowed disabled:opacity-50"
              data-testid="feedback-submit"
            >
              {submitMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Submitting...</span>
                </>
              ) : (
                <span>Submit</span>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
