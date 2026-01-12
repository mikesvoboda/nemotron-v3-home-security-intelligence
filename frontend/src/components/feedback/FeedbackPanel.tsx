/**
 * FeedbackPanel component for EventDetailModal
 *
 * Displays feedback buttons for event classification:
 * - accurate: Detection was correct
 * - false_positive: Event was incorrectly flagged
 * - missed_threat: System failed to detect a threat
 * - severity_wrong: Risk level was incorrect
 *
 * @see NEM-2353 - Create FeedbackPanel component for EventDetailModal
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { clsx } from 'clsx';
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Loader2,
  MessageSquare,
  ThumbsDown,
  ThumbsUp,
  X,
} from 'lucide-react';
import { useCallback, useState } from 'react';

import {
  getEventFeedback,
  submitEventFeedback,
  type EventFeedbackResponse,
  type FeedbackType,
} from '../../services/api';

export interface FeedbackPanelProps {
  /** Event ID to submit feedback for */
  eventId: number;
  /** Current risk score of the event (0-100) */
  currentRiskScore?: number;
  /** Optional CSS class name */
  className?: string;
  /** Callback when feedback is successfully submitted */
  onFeedbackSubmitted?: (feedback: EventFeedbackResponse) => void;
}

interface FeedbackOption {
  type: FeedbackType;
  label: string;
  icon: React.ElementType;
  description: string;
  colorClass: string;
  bgClass: string;
  borderClass: string;
}

const FEEDBACK_OPTIONS: FeedbackOption[] = [
  {
    type: 'accurate',
    label: 'Accurate',
    icon: ThumbsUp,
    description: 'Detection was correct',
    colorClass: 'text-green-400',
    bgClass: 'bg-green-600/10 hover:bg-green-600/20',
    borderClass: 'border-green-600/40',
  },
  {
    type: 'false_positive',
    label: 'False Positive',
    icon: ThumbsDown,
    description: 'Event was incorrectly flagged',
    colorClass: 'text-red-400',
    bgClass: 'bg-red-600/10 hover:bg-red-600/20',
    borderClass: 'border-red-600/40',
  },
  {
    type: 'missed_threat',
    label: 'Missed Threat',
    icon: AlertTriangle,
    description: 'System failed to detect a threat',
    colorClass: 'text-orange-400',
    bgClass: 'bg-orange-600/10 hover:bg-orange-600/20',
    borderClass: 'border-orange-600/40',
  },
  {
    type: 'severity_wrong',
    label: 'Severity Wrong',
    icon: MessageSquare,
    description: 'Risk level was incorrect',
    colorClass: 'text-yellow-400',
    bgClass: 'bg-yellow-600/10 hover:bg-yellow-600/20',
    borderClass: 'border-yellow-600/40',
  },
];

/**
 * Get display label for feedback type
 */
function getFeedbackTypeLabel(type: string): string {
  const option = FEEDBACK_OPTIONS.find((opt) => opt.type === type);
  return option?.label ?? type.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase());
}

/**
 * FeedbackPanel component for submitting event feedback
 */
export default function FeedbackPanel({
  eventId,
  currentRiskScore,
  className,
  onFeedbackSubmitted,
}: FeedbackPanelProps) {
  const [selectedType, setSelectedType] = useState<FeedbackType | null>(null);
  const [notes, setNotes] = useState('');
  const [showNotesForm, setShowNotesForm] = useState(false);

  const queryClient = useQueryClient();

  // Query for existing feedback
  const {
    data: existingFeedback,
    isLoading: isLoadingFeedback,
    error: feedbackError,
  } = useQuery<EventFeedbackResponse | null>({
    queryKey: ['eventFeedback', eventId],
    queryFn: () => getEventFeedback(eventId),
    enabled: !isNaN(eventId),
    staleTime: 30000, // 30 seconds
  });

  // Mutation for submitting feedback
  const feedbackMutation = useMutation({
    mutationFn: submitEventFeedback,
    onSuccess: (data) => {
      setSelectedType(null);
      setNotes('');
      setShowNotesForm(false);
      // Invalidate the feedback query to refetch
      void queryClient.invalidateQueries({ queryKey: ['eventFeedback', eventId] });
      // Invalidate feedback stats
      void queryClient.invalidateQueries({ queryKey: ['feedbackStats'] });
      // Call optional callback
      onFeedbackSubmitted?.(data);
    },
  });

  // Handle quick feedback submission (for "Accurate")
  const handleQuickFeedback = useCallback(
    (type: FeedbackType) => {
      if (isNaN(eventId)) return;
      feedbackMutation.mutate({
        event_id: eventId,
        feedback_type: type,
      });
    },
    [eventId, feedbackMutation]
  );

  // Handle opening notes form for feedback types that need explanation
  const handleOpenNotesForm = useCallback((type: FeedbackType) => {
    setSelectedType(type);
    setShowNotesForm(true);
  }, []);

  // Handle feedback form submission with notes
  const handleSubmitWithNotes = useCallback(() => {
    if (isNaN(eventId) || !selectedType) return;

    // For wrong_severity, include expected severity in notes if available
    let finalNotes = notes.trim();
    if (selectedType === 'severity_wrong' && currentRiskScore !== undefined) {
      finalNotes = finalNotes
        ? `Current score: ${currentRiskScore}. ${finalNotes}`
        : `Current score: ${currentRiskScore}`;
    }

    feedbackMutation.mutate({
      event_id: eventId,
      feedback_type: selectedType,
      notes: finalNotes || undefined,
    });
  }, [eventId, selectedType, notes, currentRiskScore, feedbackMutation]);

  // Handle cancel notes form
  const handleCancelNotesForm = useCallback(() => {
    setSelectedType(null);
    setNotes('');
    setShowNotesForm(false);
  }, []);

  // Loading state
  if (isLoadingFeedback) {
    return (
      <div className={clsx('rounded-lg border border-gray-800 bg-[#1A1A1A] p-4', className)} data-testid="feedback-panel">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading feedback...
        </div>
      </div>
    );
  }

  // Error state (only show if not a 404 - which means no feedback exists yet)
  if (feedbackError && (feedbackError as { status?: number }).status !== 404) {
    return (
      <div className={clsx('rounded-lg border border-red-800 bg-red-900/20 p-4', className)} data-testid="feedback-panel">
        <p className="text-sm text-red-400">Failed to load feedback status.</p>
      </div>
    );
  }

  // Existing feedback display (read-only)
  if (existingFeedback) {
    const option = FEEDBACK_OPTIONS.find((opt) => opt.type === existingFeedback.feedback_type);
    const Icon = option?.icon ?? Check;

    return (
      <div
        className={clsx('rounded-lg border border-gray-800 bg-[#1A1A1A] p-4', className)}
        data-testid="feedback-panel"
      >
        <div className="flex items-center gap-3">
          <CheckCircle2 className="h-5 w-5 flex-shrink-0 text-[#76B900]" />
          <div>
            <div className="flex items-center gap-2">
              <Icon className={clsx('h-4 w-4', option?.colorClass ?? 'text-gray-400')} />
              <span className="font-medium text-white">
                {getFeedbackTypeLabel(existingFeedback.feedback_type)}
              </span>
            </div>
            {existingFeedback.notes && (
              <p className="mt-1 text-sm text-gray-400">{existingFeedback.notes}</p>
            )}
            <p className="mt-1 text-xs text-gray-500">
              Submitted {new Date(existingFeedback.created_at).toLocaleDateString()}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Notes form view
  if (showNotesForm && selectedType) {
    const option = FEEDBACK_OPTIONS.find((opt) => opt.type === selectedType);

    return (
      <div
        className={clsx('rounded-lg border border-gray-800 bg-[#1A1A1A] p-4', className)}
        data-testid="feedback-panel"
      >
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h4 className="flex items-center gap-2 text-sm font-semibold text-white">
            <MessageSquare className="h-4 w-4 text-[#76B900]" />
            {option?.label ?? 'Feedback'}
          </h4>
          <button
            type="button"
            onClick={handleCancelNotesForm}
            className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-white"
            aria-label="Cancel feedback"
            data-testid="cancel-feedback-button"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Notes textarea */}
        <div className="mb-4">
          <label htmlFor="feedback-notes" className="mb-2 block text-sm text-gray-400">
            {selectedType === 'severity_wrong'
              ? 'What should the severity be?'
              : 'Additional notes (optional)'}
          </label>
          <textarea
            id="feedback-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={
              selectedType === 'false_positive'
                ? 'Explain why this is a false positive...'
                : selectedType === 'severity_wrong'
                  ? 'Describe the expected severity level...'
                  : 'Add any additional context...'
            }
            rows={3}
            maxLength={1000}
            className="w-full rounded-lg border border-gray-700 bg-black/30 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 transition-colors focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20"
            data-testid="feedback-notes"
          />
          <div className="mt-1 text-right text-xs text-gray-500">{notes.length}/1000</div>
        </div>

        {/* Error message */}
        {feedbackMutation.isError && (
          <div className="mb-4 flex items-center gap-2 rounded-md bg-red-900/20 px-3 py-2 text-sm text-red-400">
            <X className="h-4 w-4" />
            <span>Failed to submit feedback. Please try again.</span>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={handleCancelNotesForm}
            disabled={feedbackMutation.isPending}
            className="rounded-lg px-4 py-2 text-sm font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="cancel-button"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmitWithNotes}
            disabled={feedbackMutation.isPending}
            className="flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-semibold text-black transition-all hover:bg-[#88d200] active:bg-[#68a000] disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="submit-feedback-button"
          >
            {feedbackMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Submitting...</span>
              </>
            ) : (
              <span>Submit Feedback</span>
            )}
          </button>
        </div>
      </div>
    );
  }

  // Main feedback buttons view
  return (
    <div
      className={clsx('rounded-lg border border-gray-800 bg-[#1A1A1A] p-4', className)}
      data-testid="feedback-panel"
    >
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">
        Detection Feedback
      </h3>

      <p className="mb-3 text-sm text-gray-400">
        Help improve AI accuracy by providing feedback on this detection.
      </p>

      {/* Error message */}
      {feedbackMutation.isError && (
        <div className="mb-3 flex items-center gap-2 rounded-md bg-red-900/20 px-3 py-2 text-sm text-red-400">
          <X className="h-4 w-4" />
          <span>Failed to submit feedback. Please try again.</span>
        </div>
      )}

      {/* Feedback buttons */}
      <div className="flex flex-wrap gap-2" data-testid="feedback-buttons">
        {FEEDBACK_OPTIONS.map((option) => {
          const Icon = option.icon;
          const isAccurate = option.type === 'accurate';

          return (
            <button
              key={option.type}
              onClick={() =>
                isAccurate ? handleQuickFeedback(option.type) : handleOpenNotesForm(option.type)
              }
              disabled={feedbackMutation.isPending}
              className={clsx(
                'flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                'disabled:cursor-not-allowed disabled:opacity-50',
                option.bgClass,
                option.borderClass,
                option.colorClass
              )}
              title={option.description}
              data-testid={`feedback-${option.type}-button`}
            >
              <Icon className="h-4 w-4" />
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
