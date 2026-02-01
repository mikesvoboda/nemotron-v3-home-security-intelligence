/**
 * FaceEventCard Component
 *
 * Displays an individual face detection event with thumbnail, timestamp,
 * camera info, and person identification details.
 *
 * For known persons: shows name and confidence
 * For unknown persons: shows action buttons (Identify, Add New, Dismiss)
 *
 * @module components/face-recognition/FaceEventCard
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

import { Eye, User, UserPlus, UserX, XCircle } from 'lucide-react';
import { memo } from 'react';

import type { FaceDetectionEvent } from '../../types/faceRecognition';

/**
 * Props for the FaceEventCard component.
 */
export interface FaceEventCardProps {
  /** The face detection event to display */
  event: FaceDetectionEvent;
  /** Callback when user wants to identify an unknown face as a known person */
  onIdentify?: (eventId: number) => void;
  /** Callback when user wants to create a new person from this face */
  onAddNewPerson?: (eventId: number) => void;
  /** Callback when user wants to dismiss an unknown face alert */
  onDismiss?: (eventId: number) => void;
  /** Callback to view the full detection details */
  onViewDetection?: (detectionId: string) => void;
}

/**
 * Get the confidence color class based on confidence percentage.
 * - Green: >= 90%
 * - Yellow: 70-89%
 * - Red: < 70%
 *
 * @param confidence - Confidence value between 0 and 1
 * @returns Tailwind CSS color class
 */
function getConfidenceColorClass(confidence: number): string {
  const percentage = confidence * 100;
  if (percentage >= 90) {
    return 'text-green-400';
  }
  if (percentage >= 70) {
    return 'text-yellow-400';
  }
  return 'text-red-400';
}

/**
 * Format confidence as a percentage string.
 *
 * @param confidence - Confidence value between 0 and 1
 * @returns Formatted percentage string (e.g., "95%")
 */
function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

/**
 * Format timestamp to display time in 12-hour format.
 *
 * @param timestamp - ISO timestamp string
 * @returns Formatted time string (e.g., "10:32 AM")
 */
function formatTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return timestamp;
  }
}

/**
 * FaceEventCard displays a single face detection event.
 *
 * Layout for known person:
 * ```
 * [Thumbnail] | 10:32 AM - Front Door
 *             | Matched: John Smith (95% confidence)
 *             | [View Detection]
 * ```
 *
 * Layout for unknown person:
 * ```
 * [Thumbnail] | 10:28 AM - Driveway
 *             | Unknown person
 *             | [Identify] [Add New] [Dismiss]
 * ```
 */
const FaceEventCard = memo(function FaceEventCard({
  event,
  onIdentify,
  onAddNewPerson,
  onDismiss,
  onViewDetection,
}: FaceEventCardProps) {
  const {
    id,
    camera_name,
    timestamp,
    matched_person_name,
    match_confidence,
    is_unknown,
    thumbnail_url,
    detection_id,
  } = event;

  // Determine if this is an unknown person (for styling and actions)
  const isUnknown = is_unknown || !matched_person_name;

  // Handle View Detection click
  const handleViewDetection = () => {
    if (onViewDetection && detection_id) {
      onViewDetection(detection_id);
    }
  };

  // Handle Identify click
  const handleIdentify = () => {
    if (onIdentify) {
      onIdentify(id);
    }
  };

  // Handle Add New Person click
  const handleAddNewPerson = () => {
    if (onAddNewPerson) {
      onAddNewPerson(id);
    }
  };

  // Handle Dismiss click
  const handleDismiss = () => {
    if (onDismiss) {
      onDismiss(id);
    }
  };

  // Base card classes
  const cardClasses = [
    'flex',
    'gap-4',
    'p-4',
    'border-b',
    'border-gray-700',
    'transition-colors',
    'hover:bg-gray-800/50',
  ];

  // Add unknown highlight styling
  if (isUnknown) {
    cardClasses.push('bg-yellow-500/10', 'border-l-4', 'border-yellow-500');
  }

  return (
    <div
      className={cardClasses.join(' ')}
      data-testid={`face-event-card-${id}`}
    >
      {/* Thumbnail Column */}
      <div className="flex-shrink-0">
        {thumbnail_url ? (
          <img
            src={thumbnail_url}
            alt="Face thumbnail"
            className="h-16 w-16 rounded-lg bg-gray-800 object-cover"
          />
        ) : (
          <div
            className="flex h-16 w-16 items-center justify-center rounded-lg bg-gray-800"
            data-testid="face-thumbnail-placeholder"
          >
            {isUnknown ? (
              <UserX className="h-8 w-8 text-gray-500" />
            ) : (
              <User className="h-8 w-8 text-gray-500" />
            )}
          </div>
        )}
      </div>

      {/* Content Column */}
      <div className="min-w-0 flex-1">
        {/* Header: Time and Camera */}
        <div className="mb-1 text-sm text-gray-400">
          <span className="font-medium text-gray-300">{formatTimestamp(timestamp)}</span>
          <span className="mx-2">-</span>
          <span>{camera_name}</span>
        </div>

        {/* Person Info or Unknown Status */}
        <div className="mb-2">
          {isUnknown ? (
            <p className="text-gray-300">Unknown person</p>
          ) : (
            <p className="text-gray-200">
              <span className="text-gray-400">Matched: </span>
              <span className="font-medium">{matched_person_name}</span>
              {match_confidence !== null && match_confidence !== undefined && (
                <span className={`ml-2 ${getConfidenceColorClass(match_confidence)}`}>
                  ({formatConfidence(match_confidence)} confidence)
                </span>
              )}
            </p>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-2">
          {isUnknown ? (
            <>
              {/* Unknown person actions */}
              {onIdentify && (
                <button
                  onClick={handleIdentify}
                  className="flex items-center gap-1 rounded-md border border-gray-600 bg-gray-700/50 px-3 py-1 text-xs font-medium text-gray-300 transition-colors hover:border-gray-500 hover:bg-gray-600/50"
                  aria-label="Identify"
                >
                  <User className="h-3 w-3" />
                  Identify
                </button>
              )}
              {onAddNewPerson && (
                <button
                  onClick={handleAddNewPerson}
                  className="flex items-center gap-1 rounded-md border border-gray-600 bg-gray-700/50 px-3 py-1 text-xs font-medium text-gray-300 transition-colors hover:border-gray-500 hover:bg-gray-600/50"
                  aria-label="Add New"
                >
                  <UserPlus className="h-3 w-3" />
                  Add New
                </button>
              )}
              {onDismiss && (
                <button
                  onClick={handleDismiss}
                  className="flex items-center gap-1 rounded-md border border-gray-600 bg-gray-700/50 px-3 py-1 text-xs font-medium text-gray-300 transition-colors hover:border-gray-500 hover:bg-gray-600/50"
                  aria-label="Dismiss"
                >
                  <XCircle className="h-3 w-3" />
                  Dismiss
                </button>
              )}
            </>
          ) : (
            <>
              {/* Known person actions */}
              {onViewDetection && (
                <button
                  onClick={handleViewDetection}
                  disabled={!detection_id}
                  className="flex items-center gap-1 rounded-md bg-[#76B900] px-3 py-1 text-xs font-medium text-black transition-colors hover:bg-[#88d200] disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label="View Detection"
                >
                  <Eye className="h-3 w-3" />
                  View Detection
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
});

export default FaceEventCard;
