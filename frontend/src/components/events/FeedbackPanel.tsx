/**
 * FeedbackPanel - Reusable component for event feedback collection
 *
 * Displays feedback buttons for users to classify event accuracy:
 * - Correct: AI classification was accurate
 * - False Positive: Event was incorrectly flagged as a threat
 * - Missed Threat: AI failed to detect a real threat
 * - Severity Wrong: Event detected but risk level was incorrect
 *
 * Features:
 * - Shows existing feedback if already submitted
 * - Opens feedback form for detailed input when needed
 * - Displays confirmation after submission
 * - Uses Tremor UI components for consistent styling
 *
 * @see NEM-2353 - Create FeedbackPanel component for EventDetailModal
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Loader2,
  Target,
  ThumbsDown,
  ThumbsUp,
  X,
} from 'lucide-react';
import { useCallback, useState } from 'react';

import FeedbackForm from './FeedbackForm';
import { useToast } from '../../hooks/useToast';
import {
  getEventFeedback,
  submitEventFeedback,
  type EventFeedbackResponse,
  type FeedbackType,
} from '../../services/api';

export interface FeedbackPanelProps {
  /** Event ID to submit feedback for */
  eventId: number;
  /** Current risk score of the event (0-100), used for severity correction */
  currentRiskScore: number;
  /** Whether the panel should be collapsed by default */
  defaultCollapsed?: boolean;
  /** Additional CSS classes */
  className?: string;
}

interface FeedbackButton {
  type: FeedbackType;
  label: string;
  icon: React.ElementType;
  description: string;
  colorClasses: string;
  /** If true, clicking opens a form rather than submitting directly */
  requiresForm: boolean;
}

const FEEDBACK_BUTTONS: FeedbackButton[] = [
  {
    type: 'accurate',
    label: 'Accurate',
    icon: ThumbsUp,
    description: 'AI classification was accurate',
    colorClasses: 'border-green-600/40 bg-green-600/10 text-green-400 hover:bg-green-600/20',
    requiresForm: false,
  },
  {
    type: 'false_positive',
    label: 'False Positive',
    icon: ThumbsDown,
    description: 'Event incorrectly flagged as a threat',
    colorClasses: 'border-red-600/40 bg-red-600/10 text-red-400 hover:bg-red-600/20',
    requiresForm: true,
  },
  {
    type: 'missed_threat',
    label: 'Missed Threat',
    icon: Target,
    description: 'AI failed to detect a real threat',
    colorClasses: 'border-orange-600/40 bg-orange-600/10 text-orange-400 hover:bg-orange-600/20',
    requiresForm: true,
  },
  {
    type: 'severity_wrong',
    label: 'Severity Wrong',
    icon: AlertCircle,
    description: 'Risk level was incorrect',
    colorClasses: 'border-yellow-600/40 bg-yellow-600/10 text-yellow-400 hover:bg-yellow-600/20',
    requiresForm: true,
  },
];

/**
 * Get display label for feedback type
 */
function getFeedbackTypeLabel(type: string): string {
  const button = FEEDBACK_BUTTONS.find((b) => b.type === type);
  return button?.label ?? type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * FeedbackPanel - Main component for collecting event feedback
 */
export default function FeedbackPanel({
  eventId,
  currentRiskScore,
  defaultCollapsed = false,
  className = '',
}: FeedbackPanelProps) {
  const [feedbackFormType, setFeedbackFormType] = useState<FeedbackType | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  const { success: toastSuccess, error: toastError } = useToast();
  const queryClient = useQueryClient();

  // Query for existing feedback
  const {
    data: existingFeedback,
    isLoading: isLoadingFeedback,
    error: feedbackError,
  } = useQuery<EventFeedbackResponse | null>({
    queryKey: ['eventFeedback', eventId],
    queryFn: () => getEventFeedback(eventId),
    enabled: !isNaN(eventId) && eventId > 0,
    staleTime: 30000, // 30 seconds
  });

  // Mutation for submitting feedback
  const feedbackMutation = useMutation({
    mutationFn: submitEventFeedback,
    onSuccess: () => {
      toastSuccess('Feedback submitted successfully');
      setFeedbackFormType(null);
      // Invalidate the feedback query to refetch
      void queryClient.invalidateQueries({ queryKey: ['eventFeedback', eventId] });
      // Invalidate feedback stats for calibration panel
      void queryClient.invalidateQueries({ queryKey: ['feedbackStats'] });
    },
    onError: (error: Error) => {
      toastError(`Failed to submit feedback: ${error.message}`);
    },
  });

  // Handle quick feedback submission (for "Correct" button)
  const handleQuickFeedback = useCallback((type: FeedbackType) => {
    if (isNaN(eventId) || eventId <= 0) return;
    feedbackMutation.mutate({
      event_id: eventId,
      feedback_type: type,
    });
  }, [eventId, feedbackMutation]);

  // Handle button click - either submit directly or open form
  const handleButtonClick = useCallback((button: FeedbackButton) => {
    if (button.requiresForm) {
      setFeedbackFormType(button.type);
    } else {
      handleQuickFeedback(button.type);
    }
  }, [handleQuickFeedback]);

  // Handle feedback form submission
  const handleFeedbackSubmit = useCallback((notes: string, expectedSeverity?: number) => {
    if (isNaN(eventId) || eventId <= 0 || !feedbackFormType) return;

    let finalNotes = notes;
    // Include expected severity in notes for severity_wrong feedback
    if (feedbackFormType === 'severity_wrong' && expectedSeverity !== undefined) {
      finalNotes = notes
        ? `Expected severity: ${expectedSeverity}. ${notes}`
        : `Expected severity: ${expectedSeverity}`;
    }

    feedbackMutation.mutate({
      event_id: eventId,
      feedback_type: feedbackFormType,
      notes: finalNotes || undefined,
    });
  }, [eventId, feedbackFormType, feedbackMutation]);

  // Handle form cancel
  const handleFormCancel = useCallback(() => {
    setFeedbackFormType(null);
  }, []);

  // Toggle collapsed state
  const toggleCollapsed = useCallback(() => {
    setIsCollapsed((prev) => !prev);
  }, []);

  // Loading state
  if (isLoadingFeedback) {
    return (
      <div className={`rounded-lg border border-gray-800 bg-black/20 p-4 ${className}`} data-testid="feedback-panel">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading feedback...
        </div>
      </div>
    );
  }

  // Error state (non-404)
  const is404Error = feedbackError &&
    typeof feedbackError === 'object' &&
    feedbackError !== null &&
    'status' in feedbackError &&
    (feedbackError as unknown as { status: number }).status === 404;
  if (feedbackError && !is404Error) {
    return (
      <div className={`rounded-lg border border-red-800 bg-red-900/20 p-4 ${className}`} data-testid="feedback-panel">
        <div className="flex items-center gap-2 text-sm text-red-400">
          <X className="h-4 w-4" />
          Failed to load feedback. Please try again.
        </div>
      </div>
    );
  }

  // Existing feedback display
  if (existingFeedback) {
    const feedbackButton = FEEDBACK_BUTTONS.find((b) => b.type === existingFeedback.feedback_type);
    const Icon = feedbackButton?.icon ?? Check;

    return (
      <div
        className={`rounded-lg border border-gray-700 bg-[#1F1F1F] p-4 ${className}`}
        data-testid="feedback-panel"
      >
        <div className="flex items-center gap-3">
          <CheckCircle2 className="h-5 w-5 flex-shrink-0 text-[#76B900]" />
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <Icon className="h-4 w-4 text-gray-400" />
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

  // Feedback form view
  if (feedbackFormType) {
    return (
      <div className={className} data-testid="feedback-panel">
        <FeedbackForm
          eventId={eventId}
          feedbackType={feedbackFormType}
          currentSeverity={currentRiskScore}
          onSubmit={handleFeedbackSubmit}
          onCancel={handleFormCancel}
          isSubmitting={feedbackMutation.isPending}
        />
      </div>
    );
  }

  // Main feedback buttons view
  return (
    <div className={`rounded-lg border border-gray-800 bg-black/20 ${className}`} data-testid="feedback-panel">
      {/* Header */}
      <button
        onClick={toggleCollapsed}
        className="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-gray-800/30"
        aria-expanded={!isCollapsed}
        aria-controls="feedback-panel-content"
        data-testid="feedback-panel-toggle"
      >
        <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
          Detection Feedback
        </h3>
        <span className="text-xs text-gray-500">
          {isCollapsed ? 'Show' : 'Hide'}
        </span>
      </button>

      {/* Content */}
      {!isCollapsed && (
        <div id="feedback-panel-content" className="border-t border-gray-800 p-4">
          <p className="mb-4 text-sm text-gray-400">
            Help improve AI accuracy by providing feedback on this detection.
          </p>

          {/* Feedback buttons grid */}
          <div className="grid grid-cols-2 gap-2" data-testid="feedback-buttons">
            {FEEDBACK_BUTTONS.map((button) => {
              const Icon = button.icon;
              return (
                <button
                  key={button.type}
                  onClick={() => handleButtonClick(button)}
                  disabled={feedbackMutation.isPending}
                  className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${button.colorClasses}`}
                  title={button.description}
                  data-testid={`feedback-btn-${button.type}`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{button.label}</span>
                </button>
              );
            })}
          </div>

          {/* Submission state indicator */}
          {feedbackMutation.isPending && (
            <div className="mt-3 flex items-center gap-2 text-sm text-gray-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Submitting feedback...
            </div>
          )}
        </div>
      )}
    </div>
  );
}
