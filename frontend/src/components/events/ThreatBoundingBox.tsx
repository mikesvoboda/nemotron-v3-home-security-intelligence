/**
 * ThreatBoundingBox - Render CSS overlay boxes on detection images (NEM-5019)
 *
 * This component renders absolutely positioned div boxes over a parent container
 * showing where threats are located in detection images. It supports:
 * - Single and multiple bounding box rendering
 * - Priority-based color coding (red for high-priority, orange for medium)
 * - Coordinate scaling relative to container dimensions
 * - Accessibility via aria-labels
 *
 * Backend bbox format: tuple[float, float, float, float] as (x1, y1, x2, y2) in pixel coordinates
 * Frontend bbox format: [number, number, number, number] as [x1, y1, x2, y2]
 */

import { clsx } from 'clsx';

import type { RefObject } from 'react';

/**
 * Data structure for a single threat detection
 */
export interface ThreatData {
  /** Class name of the detected threat (e.g., 'knife', 'gun', 'bat') */
  class_name: string;
  /** Detection confidence score between 0 and 1 */
  confidence: number;
  /** Bounding box coordinates [x1, y1, x2, y2] in pixel coordinates */
  bbox: [number, number, number, number];
  /** Whether this is a high-priority threat (firearms) */
  is_high_priority: boolean;
}

/**
 * Props for the ThreatBoundingBox component
 */
export interface ThreatBoundingBoxProps {
  /** Array of threat detections to display */
  threats: ThreatData[];
  /** Width of the source image in pixels */
  imageWidth: number;
  /** Height of the source image in pixels */
  imageHeight: number;
  /** Optional ref to the container element for responsive scaling */
  containerRef?: RefObject<HTMLDivElement | null>;
  /** Additional CSS classes for the container */
  className?: string;
}

// Tailwind red-500: #ef4444 -> rgb(239, 68, 68)
const HIGH_PRIORITY_COLOR = 'rgb(239, 68, 68)';
// Tailwind orange-500: #f97316 -> rgb(249, 115, 22)
const MEDIUM_PRIORITY_COLOR = 'rgb(249, 115, 22)';

/**
 * Calculate percentage position from pixel coordinates
 */
function calculatePercentage(value: number, total: number): number {
  if (total <= 0) return 0;
  return (value / total) * 100;
}

/**
 * Clamp a value between min and max
 */
function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/**
 * Normalize bounding box coordinates (handle inverted or negative values)
 */
function normalizeBbox(
  bbox: [number, number, number, number],
  imageWidth: number,
  imageHeight: number
): { left: number; top: number; width: number; height: number } {
  let [x1, y1, x2, y2] = bbox;

  // Handle inverted coordinates
  if (x2 < x1) {
    [x1, x2] = [x2, x1];
  }
  if (y2 < y1) {
    [y1, y2] = [y2, y1];
  }

  // Clamp to image bounds
  x1 = clamp(x1, 0, imageWidth);
  y1 = clamp(y1, 0, imageHeight);
  x2 = clamp(x2, 0, imageWidth);
  y2 = clamp(y2, 0, imageHeight);

  // Calculate percentages
  const left = calculatePercentage(x1, imageWidth);
  const top = calculatePercentage(y1, imageHeight);
  const width = calculatePercentage(x2 - x1, imageWidth);
  const height = calculatePercentage(y2 - y1, imageHeight);

  return { left, top, width, height };
}

/**
 * Format confidence as a percentage string
 */
function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

/**
 * Get the color for a threat based on priority
 */
function getThreatColor(isHighPriority: boolean): string {
  return isHighPriority ? HIGH_PRIORITY_COLOR : MEDIUM_PRIORITY_COLOR;
}

/**
 * Get the z-index for a threat based on priority
 */
function getThreatZIndex(isHighPriority: boolean): number {
  return isHighPriority ? 20 : 10;
}

/**
 * Single bounding box component
 */
function BoundingBox({
  threat,
  imageWidth,
  imageHeight,
}: {
  threat: ThreatData;
  imageWidth: number;
  imageHeight: number;
}) {
  const { left, top, width, height } = normalizeBbox(
    threat.bbox,
    imageWidth,
    imageHeight
  );

  const color = getThreatColor(threat.is_high_priority);
  const zIndex = getThreatZIndex(threat.is_high_priority);
  const confidenceStr = formatConfidence(threat.confidence);

  const priorityLabel = threat.is_high_priority ? 'high-priority' : 'medium-priority';
  const ariaLabel = `${threat.class_name} detected with ${confidenceStr} confidence, ${priorityLabel}`;

  return (
    <div
      data-testid="threat-bbox"
      role="img"
      aria-label={ariaLabel}
      className={clsx(
        threat.is_high_priority ? 'threat-high-priority' : 'threat-medium-priority'
      )}
      style={{
        position: 'absolute',
        left: `${left}%`,
        top: `${top}%`,
        width: `${width}%`,
        height: `${height}%`,
        borderWidth: '2px',
        borderStyle: 'solid',
        borderColor: color,
        borderRadius: '4px',
        backgroundColor: `${color}20`, // 20 = ~12% opacity in hex
        zIndex,
      }}
    >
      <div
        data-testid="threat-label"
        style={{
          position: 'absolute',
          top: '-1.5rem',
          left: '0',
          backgroundColor: color,
          color: 'white',
          padding: '2px 6px',
          borderRadius: '4px',
          fontSize: '0.75rem',
          fontWeight: 500,
          whiteSpace: 'nowrap',
        }}
      >
        <span>{threat.class_name}</span> <span>{confidenceStr}</span>
      </div>
    </div>
  );
}

/**
 * ThreatBoundingBox component
 *
 * Renders overlay boxes on detection images showing where threats are located.
 * Returns null if no threats are provided or the array is empty.
 */
export default function ThreatBoundingBox({
  threats,
  imageWidth,
  imageHeight,
  className,
}: ThreatBoundingBoxProps) {
  // Don't render if no threats or invalid image dimensions
  if (!threats || threats.length === 0) {
    return null;
  }

  // Handle zero-dimension images gracefully
  if (imageWidth <= 0 || imageHeight <= 0) {
    return null;
  }

  const threatCount = threats.length;
  const containerAriaLabel = `${threatCount} threat${threatCount === 1 ? '' : 's'} detected`;

  return (
    <div
      data-testid="threat-bounding-boxes"
      role="region"
      aria-label={containerAriaLabel}
      className={clsx(className)}
      style={{
        position: 'absolute',
        inset: '0',
        pointerEvents: 'none',
      }}
    >
      {threats.map((threat, index) => (
        <BoundingBox
          key={`${threat.class_name}-${index}`}
          threat={threat}
          imageWidth={imageWidth}
          imageHeight={imageHeight}
        />
      ))}
    </div>
  );
}
