/**
 * FeedbackForm - Component for submitting event feedback
 *
 * Allows users to provide feedback on event classifications:
 * - False positive: Event was incorrectly flagged
 * - Wrong severity: Event severity was miscalculated
 *
 * Displays appropriate form fields based on feedback type:
 * - false_positive: Notes field only
 * - severity_wrong: Expected severity slider + notes field
 */

import { clsx } from 'clsx';
import { MessageSquare, Sliders, X } from 'lucide-react';
import { useState } from 'react';

import type { FeedbackType } from '../../types/generated';

export interface FeedbackFormProps {
  /** Event ID this feedback is for */
  eventId: number;
  /** Type of feedback being submitted */
  feedbackType: FeedbackType;
  /** Current risk score of the event (0-100) */
  currentSeverity: number;
  /** Callback when form is submitted */
  onSubmit: (notes: string, expectedSeverity?: number) => void;
  /** Callback when form is cancelled */
  onCancel: () => void;
  /** Whether the form is currently submitting */
  isSubmitting?: boolean;
}

/**
 * Get display label for feedback type
 */
function getFeedbackTypeLabel(type: FeedbackType): string {
  switch (type) {
    case 'false_positive':
      return 'False Positive';
    case 'severity_wrong':
      return 'Wrong Severity';
    case 'missed_threat':
      return 'Missed Detection';
    case 'accurate':
      return 'Correct Detection';
    default:
      return type;
  }
}

/**
 * Get severity level label and color based on score
 */
function getSeverityDisplay(score: number): { label: string; colorClass: string } {
  if (score >= 80) {
    return { label: 'Critical', colorClass: 'text-red-500' };
  } else if (score >= 60) {
    return { label: 'High', colorClass: 'text-orange-500' };
  } else if (score >= 40) {
    return { label: 'Medium', colorClass: 'text-yellow-500' };
  } else if (score >= 20) {
    return { label: 'Low', colorClass: 'text-blue-500' };
  }
  return { label: 'Minimal', colorClass: 'text-gray-400' };
}

/**
 * Get slider track color based on severity value
 */
function getSeverityTrackColor(score: number): string {
  if (score >= 80) {
    return 'bg-red-500';
  } else if (score >= 60) {
    return 'bg-orange-500';
  } else if (score >= 40) {
    return 'bg-yellow-500';
  } else if (score >= 20) {
    return 'bg-blue-500';
  }
  return 'bg-gray-500';
}

/**
 * FeedbackForm - Main component
 */
export default function FeedbackForm({
  eventId: _eventId,
  feedbackType,
  currentSeverity,
  onSubmit,
  onCancel,
  isSubmitting = false,
}: FeedbackFormProps) {
  const [notes, setNotes] = useState('');
  const [expectedSeverity, setExpectedSeverity] = useState(currentSeverity);

  const isWrongSeverity = feedbackType === 'severity_wrong';
  const severityDisplay = getSeverityDisplay(expectedSeverity);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isWrongSeverity) {
      onSubmit(notes, expectedSeverity);
    } else {
      onSubmit(notes);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border border-gray-700 bg-[#1F1F1F] p-4"
      data-testid="feedback-form"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h4 className="flex items-center gap-2 text-sm font-semibold text-white">
          <MessageSquare className="h-4 w-4 text-[#76B900]" />
          {getFeedbackTypeLabel(feedbackType)} Feedback
        </h4>
        <button
          type="button"
          onClick={onCancel}
          className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-white"
          aria-label="Cancel feedback"
          data-testid="cancel-feedback-button"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Wrong Severity: Slider for expected score */}
      {isWrongSeverity && (
        <div className="mb-4">
          <label
            htmlFor="expected-severity"
            className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-300"
          >
            <Sliders className="h-4 w-4" />
            Expected Severity
          </label>
          <div className="mb-2">
            <input
              type="range"
              id="expected-severity"
              min="0"
              max="100"
              value={expectedSeverity}
              onChange={(e) => setExpectedSeverity(Number(e.target.value))}
              className={clsx(
                'h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700',
                '[&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4',
                '[&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:appearance-none',
                '[&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#76B900]',
                '[&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4',
                '[&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:rounded-full',
                '[&::-moz-range-thumb]:border-none [&::-moz-range-thumb]:bg-[#76B900]'
              )}
              data-testid="severity-slider"
            />
            {/* Track fill indicator */}
            <div className="relative -mt-2 h-2 rounded-lg" style={{ pointerEvents: 'none' }}>
              <div
                className={clsx(
                  'absolute left-0 top-0 h-full rounded-l-lg',
                  getSeverityTrackColor(expectedSeverity)
                )}
                style={{ width: `${expectedSeverity}%` }}
              />
            </div>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">
              Current: <span className="font-medium text-gray-200">{currentSeverity}</span>
            </span>
            <span className={clsx('font-medium', severityDisplay.colorClass)}>
              {severityDisplay.label} ({expectedSeverity})
            </span>
          </div>
        </div>
      )}

      {/* Notes field */}
      <div className="mb-4">
        <label htmlFor="feedback-notes" className="mb-2 block text-sm font-medium text-gray-300">
          {isWrongSeverity ? 'Additional Notes (optional)' : 'Notes (optional)'}
        </label>
        <textarea
          id="feedback-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={
            feedbackType === 'false_positive'
              ? 'Explain why this is a false positive...'
              : 'Add any additional context...'
          }
          rows={3}
          className="w-full rounded-lg border border-gray-700 bg-black/30 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 transition-colors focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20"
          data-testid="feedback-notes"
        />
      </div>

      {/* Action buttons */}
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="rounded-lg px-4 py-2 text-sm font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
          data-testid="cancel-button"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-semibold text-black transition-all hover:bg-[#88d200] active:bg-[#68a000] disabled:cursor-not-allowed disabled:opacity-50"
          data-testid="submit-feedback-button"
        >
          {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
        </button>
      </div>
    </form>
  );
}
