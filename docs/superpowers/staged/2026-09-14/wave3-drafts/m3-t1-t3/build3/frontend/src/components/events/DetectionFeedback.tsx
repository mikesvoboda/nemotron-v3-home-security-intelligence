/**
 * DetectionFeedback Component
 *
 * Provides feedback buttons for individual detection boxes, allowing users
 * to mark detections as correct, incorrect, or unsure. When marking a
 * detection as incorrect, users can select a reason from a dropdown.
 *
 * Features:
 * - Three feedback buttons: Correct (green), Incorrect (red), Unsure (gray)
 * - Reason dropdown for incorrect feedback with predefined options
 * - Compact mode for use in space-constrained contexts
 * - Full keyboard accessibility with Tab, Enter, Space, and arrow key navigation
 * - Hover tooltips for button descriptions
 *
 * @see NEM-3622
 */

import { clsx } from 'clsx';
import { Check, HelpCircle, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Types of feedback for detection accuracy
 */
export type DetectionFeedbackType = 'correct' | 'incorrect' | 'unsure';

/**
 * Predefined reasons for marking a detection as incorrect
 */
export type IncorrectReason =
  | 'shadow'
  | 'reflection'
  | 'animal'
  | 'weather'
  | 'wrong_label'
  | 'other';

/**
 * Display labels for incorrect reasons
 */
const REASON_LABELS: Record<IncorrectReason, string> = {
  shadow: 'Shadow',
  reflection: 'Reflection',
  animal: 'Animal',
  weather: 'Weather',
  wrong_label: 'Wrong Label',
  other: 'Other',
};

/**
 * All available incorrect reasons in display order
 */
const INCORRECT_REASONS: IncorrectReason[] = [
  'shadow',
  'reflection',
  'animal',
  'weather',
  'wrong_label',
  'other',
];

/**
 * Data structure for feedback submission
 */
export interface DetectionFeedbackData {
  /** ID of the detection being reviewed */
  detectionId: string;
  /** ID of the parent event */
  eventId: string;
  /** Type of feedback */
  feedback: DetectionFeedbackType;
  /** Reason for incorrect feedback (only set when feedback is 'incorrect') */
  reason: IncorrectReason | undefined;
}

/**
 * Initial feedback state
 */
export interface InitialFeedback {
  /** Previously selected feedback type */
  feedback: DetectionFeedbackType;
  /** Previously selected reason (if feedback was incorrect) */
  reason?: IncorrectReason;
}

/**
 * Props for the DetectionFeedback component
 */
export interface DetectionFeedbackProps {
  /** ID of the detection */
  detectionId: string;
  /** ID of the parent event */
  eventId: string;
  /** Callback when feedback is submitted */
  onFeedbackSubmit?: (feedback: DetectionFeedbackData) => void;
  /** Additional CSS classes */
  className?: string;
  /** Disable all feedback interactions */
  disabled?: boolean;
  /** Initial feedback state (for displaying previously submitted feedback) */
  initialFeedback?: InitialFeedback;
  /** Compact mode with smaller buttons */
  compact?: boolean;
}

/**
 * DetectionFeedback component for marking detection accuracy
 */
export default function DetectionFeedback({
  detectionId,
  eventId,
  onFeedbackSubmit,
  className,
  disabled = false,
  initialFeedback,
  compact = false,
}: DetectionFeedbackProps) {
  // Currently selected feedback type
  const [selectedFeedback, setSelectedFeedback] = useState<DetectionFeedbackType | null>(
    initialFeedback?.feedback ?? null
  );
  // Selected reason for incorrect feedback
  const [selectedReason, setSelectedReason] = useState<IncorrectReason | undefined>(
    initialFeedback?.reason
  );
  // Whether the reason dropdown is visible
  const [showReasonDropdown, setShowReasonDropdown] = useState(false);
  // Active tooltip
  const [activeTooltip, setActiveTooltip] = useState<DetectionFeedbackType | null>(null);
  // Focused dropdown item index
  const [focusedDropdownIndex, setFocusedDropdownIndex] = useState<number>(-1);

  // Refs for click-outside detection and focus management
  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const dropdownItemsRef = useRef<(HTMLButtonElement | null)[]>([]);

  // Tooltip descriptions
  const tooltipDescriptions: Record<DetectionFeedbackType, string> = {
    correct: 'This detection is accurate',
    incorrect: 'This detection is wrong or a false positive',
    unsure: 'Not sure if this detection is correct',
  };

  /**
   * Submit feedback data
   */
  const submitFeedback = useCallback(
    (feedback: DetectionFeedbackType, reason?: IncorrectReason) => {
      onFeedbackSubmit?.({
        detectionId,
        eventId,
        feedback,
        reason,
      });
    },
    [detectionId, eventId, onFeedbackSubmit]
  );

  /**
   * Handle feedback button click
   */
  const handleFeedbackClick = useCallback(
    (feedback: DetectionFeedbackType) => {
      if (disabled) return;

      setSelectedFeedback(feedback);

      if (feedback === 'incorrect') {
        setShowReasonDropdown(true);
        setFocusedDropdownIndex(-1);
      } else {
        setShowReasonDropdown(false);
        setSelectedReason(undefined);
        submitFeedback(feedback, undefined);
      }
    },
    [disabled, submitFeedback]
  );

  /**
   * Handle reason selection
   */
  const handleReasonSelect = useCallback(
    (reason: IncorrectReason) => {
      setSelectedReason(reason);
      setShowReasonDropdown(false);
      submitFeedback('incorrect', reason);
    },
    [submitFeedback]
  );

  /**
   * Handle click outside to close dropdown
   */
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setShowReasonDropdown(false);
        setActiveTooltip(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  /**
   * Handle Escape key to close dropdown
   */
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && showReasonDropdown) {
        setShowReasonDropdown(false);
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [showReasonDropdown]);

  /**
   * Handle keyboard navigation in dropdown
   */
  const handleDropdownKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (!showReasonDropdown) return;

      switch (event.key) {
        case 'ArrowDown':
          event.preventDefault();
          setFocusedDropdownIndex((prev) => Math.min(prev + 1, INCORRECT_REASONS.length - 1));
          break;
        case 'ArrowUp':
          event.preventDefault();
          setFocusedDropdownIndex((prev) => Math.max(prev - 1, 0));
          break;
        case 'Enter':
        case ' ':
          event.preventDefault();
          if (focusedDropdownIndex >= 0) {
            handleReasonSelect(INCORRECT_REASONS[focusedDropdownIndex]);
          }
          break;
      }
    },
    [showReasonDropdown, focusedDropdownIndex, handleReasonSelect]
  );

  /**
   * Focus the dropdown item when focusedDropdownIndex changes
   */
  useEffect(() => {
    if (focusedDropdownIndex >= 0 && dropdownItemsRef.current[focusedDropdownIndex]) {
      dropdownItemsRef.current[focusedDropdownIndex]?.focus();
    }
  }, [focusedDropdownIndex]);

  // Button size classes based on compact mode
  const buttonSizeClasses = compact ? 'h-5 w-5' : 'h-6 w-6';
  const iconSizeClasses = compact ? 'h-3 w-3' : 'h-4 w-4';

  return (
    <div
      ref={containerRef}
      data-testid="detection-feedback"
      className={clsx(
        'relative flex gap-1 rounded bg-background/80 p-1',
        compact && 'detection-feedback--compact',
        className
      )}
    >
      {/* Correct Button */}
      <button
        type="button"
        aria-label="Mark detection as correct"
        onClick={() => handleFeedbackClick('correct')}
        onMouseEnter={() => setActiveTooltip('correct')}
        onMouseLeave={() => setActiveTooltip(null)}
        disabled={disabled}
        data-selected={selectedFeedback === 'correct' ? 'true' : 'false'}
        className={clsx(
          'flex items-center justify-center rounded transition-colors focus:outline-none focus:ring-2 focus:ring-green-500/50',
          buttonSizeClasses,
          selectedFeedback === 'correct'
            ? 'bg-green-600 text-white'
            : 'text-green-600 hover:bg-green-600/20',
          disabled && 'cursor-not-allowed opacity-50'
        )}
      >
        <Check className={iconSizeClasses} />
      </button>

      {/* Incorrect Button */}
      <button
        type="button"
        aria-label="Mark detection as incorrect"
        onClick={() => handleFeedbackClick('incorrect')}
        onMouseEnter={() => setActiveTooltip('incorrect')}
        onMouseLeave={() => setActiveTooltip(null)}
        disabled={disabled}
        data-selected={selectedFeedback === 'incorrect' ? 'true' : 'false'}
        className={clsx(
          'flex items-center justify-center rounded transition-colors focus:outline-none focus:ring-2 focus:ring-red-500/50',
          buttonSizeClasses,
          selectedFeedback === 'incorrect'
            ? 'bg-red-600 text-white'
            : 'text-red-600 hover:bg-red-600/20',
          disabled && 'cursor-not-allowed opacity-50'
        )}
      >
        <X className={iconSizeClasses} />
      </button>

      {/* Unsure Button */}
      <button
        type="button"
        aria-label="Mark detection as unsure"
        onClick={() => handleFeedbackClick('unsure')}
        onMouseEnter={() => setActiveTooltip('unsure')}
        onMouseLeave={() => setActiveTooltip(null)}
        disabled={disabled}
        data-selected={selectedFeedback === 'unsure' ? 'true' : 'false'}
        className={clsx(
          'flex items-center justify-center rounded transition-colors focus:outline-none focus:ring-2 focus:ring-gray-500/50',
          buttonSizeClasses,
          selectedFeedback === 'unsure'
            ? 'bg-gray-600 text-white'
            : 'text-gray-400 hover:bg-gray-600/20',
          disabled && 'cursor-not-allowed opacity-50'
        )}
      >
        <HelpCircle className={iconSizeClasses} />
      </button>

      {/* Tooltip */}
      {activeTooltip && !showReasonDropdown && (
        <div
          role="tooltip"
          className="absolute -top-8 left-1/2 z-50 -translate-x-1/2 whitespace-nowrap rounded bg-gray-900 px-2 py-1 text-xs text-white shadow-lg"
        >
          {tooltipDescriptions[activeTooltip]}
        </div>
      )}

      {/* Reason Dropdown for Incorrect Feedback */}
      {showReasonDropdown && (
        <div
          ref={dropdownRef}
          data-testid="reason-dropdown"
          role="listbox"
          aria-label="Select reason for incorrect detection"
          tabIndex={-1}
          onKeyDown={handleDropdownKeyDown}
          className="absolute left-0 top-full z-50 mt-1 min-w-32 rounded-lg border border-gray-700 bg-gray-800 py-1 shadow-xl"
        >
          {INCORRECT_REASONS.map((reason, index) => (
            <button
              key={reason}
              ref={(el) => {
                dropdownItemsRef.current[index] = el;
              }}
              type="button"
              role="option"
              aria-selected={selectedReason === reason}
              onClick={() => handleReasonSelect(reason)}
              className={clsx(
                'w-full px-3 py-1.5 text-left text-sm transition-colors',
                'hover:bg-gray-700 focus:bg-gray-700 focus:outline-none',
                focusedDropdownIndex === index && 'bg-gray-700',
                selectedReason === reason && 'text-red-400'
              )}
            >
              {REASON_LABELS[reason]}
            </button>
          ))}
        </div>
      )}

      {/* Show selected reason badge when not showing dropdown */}
      {selectedFeedback === 'incorrect' && selectedReason && !showReasonDropdown && (
        <span className="ml-1 rounded bg-red-600/20 px-1.5 py-0.5 text-xs text-red-400">
          {REASON_LABELS[selectedReason]}
        </span>
      )}
    </div>
  );
}
