/**
 * EventFeedbackButtons component for quick feedback submission on events.
 *
 * NEM-3025: Build frontend quick feedback UI for event review
 *
 * This component provides a streamlined way for users to submit feedback on
 * event classifications. The feedback is used by the camera calibration system
 * to reduce false positives and improve AI accuracy over time.
 *
 * Feedback types:
 * - Correct: Classification was accurate
 * - Not a Threat: Event was a false positive
 * - Was a Threat: System missed a genuine threat (only shown for low risk events)
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, X, AlertTriangle, Loader2 } from 'lucide-react';
import { useState } from 'react';

import { submitEventFeedback, ApiError, type FeedbackType } from '../../services/api';

export interface EventFeedbackButtonsProps {
  /** Event ID to submit feedback for */
  eventId: number;
  /** Current risk level of the event (low, medium, high, critical) */
  currentRiskLevel: string;
  /** Callback fired after feedback is successfully submitted */
  onFeedbackSubmitted?: () => void;
  /** Additional CSS classes */
  className?: string;
  /** Use compact button styling (smaller padding) */
  compact?: boolean;
}

type QuickFeedbackType = 'correct' | 'false_positive' | 'missed_threat';

interface FeedbackButton {
  type: QuickFeedbackType;
  feedbackType: FeedbackType;
  label: string;
  icon: React.ElementType;
  colorClasses: string;
}

const FEEDBACK_BUTTONS: FeedbackButton[] = [
  {
    type: 'correct',
    feedbackType: 'accurate',
    label: 'Correct',
    icon: Check,
    colorClasses: 'bg-green-600/20 hover:bg-green-600/30 text-green-400',
  },
  {
    type: 'false_positive',
    feedbackType: 'false_positive',
    label: 'Not a Threat',
    icon: X,
    colorClasses: 'bg-yellow-600/20 hover:bg-yellow-600/30 text-yellow-400',
  },
  {
    type: 'missed_threat',
    feedbackType: 'missed_threat',
    label: 'Was a Threat',
    icon: AlertTriangle,
    colorClasses: 'bg-red-600/20 hover:bg-red-600/30 text-red-400',
  },
];

/**
 * EventFeedbackButtons provides quick feedback buttons for event review.
 *
 * The component shows three buttons for low risk events:
 * - Correct: Mark the classification as accurate
 * - Not a Threat: Mark as false positive
 * - Was a Threat: Mark as missed threat (only for low risk events)
 *
 * For non-low risk events, only "Correct" and "Not a Threat" are shown,
 * as those events already indicate some level of detected threat.
 */
export default function EventFeedbackButtons({
  eventId,
  currentRiskLevel,
  onFeedbackSubmitted,
  className = '',
  compact = false,
}: EventFeedbackButtonsProps) {
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (feedbackType: FeedbackType) =>
      submitEventFeedback({
        event_id: eventId,
        feedback_type: feedbackType,
        notes: null,
      }),
    onSuccess: () => {
      setSubmitted(true);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ['events'] });
      onFeedbackSubmitted?.();
    },
    onError: (err: Error) => {
      if (err instanceof ApiError && err.status === 409) {
        setError('Feedback already submitted for this event');
      } else {
        setError('Failed to submit feedback. Please try again.');
      }
    },
  });

  const handleFeedback = (feedbackType: FeedbackType) => {
    setError(null);
    mutation.mutate(feedbackType);
  };

  // Show success state
  if (submitted) {
    return (
      <div
        className={`flex items-center gap-2 text-sm text-green-400 ${className}`}
        data-testid="feedback-success"
      >
        <Check className="h-4 w-4" />
        <span>Thanks for your feedback!</span>
      </div>
    );
  }

  // Filter buttons based on risk level
  // Only show "Was a Threat" button for low risk events
  const visibleButtons = FEEDBACK_BUTTONS.filter((button) => {
    if (button.type === 'missed_threat') {
      return currentRiskLevel === 'low';
    }
    return true;
  });

  const buttonPadding = compact ? 'px-2 py-1' : 'px-3 py-1.5';

  return (
    <div
      className={`flex flex-col gap-2 ${className}`}
      data-testid="event-feedback-buttons"
    >
      {/* Error message */}
      {error && (
        <div
          className="flex items-center gap-2 rounded-md bg-red-900/20 px-3 py-2 text-sm text-red-400"
          data-testid="feedback-error"
        >
          <X className="h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Feedback buttons */}
      <div className="flex flex-wrap gap-2">
        {visibleButtons.map((button) => {
          const Icon = button.icon;
          return (
            <button
              key={button.type}
              onClick={() => handleFeedback(button.feedbackType)}
              className={`flex items-center gap-1 ${buttonPadding} text-sm ${button.colorClasses} rounded-lg transition-colors disabled:cursor-not-allowed disabled:opacity-50`}
              disabled={mutation.isPending}
              data-testid={`feedback-btn-${button.type.replace('_', '-')}`}
              aria-label={button.label}
            >
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Icon className="h-4 w-4" />
              )}
              <span>{button.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
