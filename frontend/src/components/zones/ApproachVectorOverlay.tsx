/**
 * ApproachVectorOverlay - SVG visualization of entity approach vectors (NEM-4936)
 *
 * This component renders directional arrows showing entities approaching zones,
 * with ETA countdown displays and urgency-based color coding:
 * - Red (imminent): ETA < 3 seconds
 * - Yellow (approaching): ETA 3-10 seconds
 * - Green (distant): ETA > 10 seconds
 *
 * Integrates with CameraZoneOverlay for unified zone intelligence visualization.
 *
 * @module components/zones/ApproachVectorOverlay
 * @see NEM-4936 Zone: Approach Vector Visualization (ETA to Zone)
 *
 * @example
 * ```tsx
 * <div className="relative">
 *   <video src={cameraFeed} />
 *   <CameraZoneOverlay cameraId="cam-1" videoWidth={1920} videoHeight={1080} />
 *   <ApproachVectorOverlay
 *     cameraId="cam-1"
 *     videoWidth={1920}
 *     videoHeight={1080}
 *     enablePolling
 *   />
 * </div>
 * ```
 */

import { clsx } from 'clsx';
import { memo, useMemo } from 'react';

import {
  useCameraApproachVectors,
  getUrgencyColor,
  formatETA,
  type ApproachVectorData,
  type ApproachUrgency,
} from '../../hooks/useApproachVectors';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the ApproachVectorOverlay component.
 */
export interface ApproachVectorOverlayProps {
  /** Camera ID to fetch approach vectors for */
  cameraId: string;
  /** Video/container width in pixels */
  videoWidth: number;
  /** Video/container height in pixels */
  videoHeight: number;
  /** Whether to enable real-time polling (default: true) */
  enablePolling?: boolean;
  /** Filter to only show specific urgency levels */
  urgencyFilter?: ApproachUrgency[];
  /** Whether to show ETA labels (default: true) */
  showETA?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

/** Arrow head size in pixels */
const ARROW_HEAD_SIZE = 12;

/** Arrow shaft width in pixels */
const ARROW_WIDTH = 3;

/** ETA label offset from arrow head */
const LABEL_OFFSET = 20;

/** Minimum arrow length to display */
const MIN_ARROW_LENGTH = 30;

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Convert normalized coordinates (0-1) to pixel coordinates.
 */
function normalizedToPixel(
  x: number,
  y: number,
  width: number,
  height: number
): [number, number] {
  return [x * width, y * height];
}

/**
 * Calculate arrow end point based on direction and distance.
 * Arrow points FROM current position TOWARD zone.
 */
function calculateArrowPoints(
  startX: number,
  startY: number,
  targetX: number,
  targetY: number,
  maxLength: number = 80
): { endX: number; endY: number; length: number } {
  const dx = targetX - startX;
  const dy = targetY - startY;
  const distance = Math.sqrt(dx * dx + dy * dy);

  if (distance === 0) {
    return { endX: startX, endY: startY, length: 0 };
  }

  // Limit arrow length but keep direction
  const length = Math.min(distance * 0.6, maxLength);
  const scale = length / distance;

  return {
    endX: startX + dx * scale,
    endY: startY + dy * scale,
    length,
  };
}

/**
 * Generate SVG path for an arrow with head.
 */
function createArrowPath(
  startX: number,
  startY: number,
  endX: number,
  endY: number,
  headSize: number = ARROW_HEAD_SIZE
): string {
  const dx = endX - startX;
  const dy = endY - startY;
  const length = Math.sqrt(dx * dx + dy * dy);

  if (length < 5) return '';

  // Normalize direction
  const nx = dx / length;
  const ny = dy / length;

  // Perpendicular for arrow head wings
  const px = -ny;
  const py = nx;

  // Arrow head points
  const headBaseX = endX - nx * headSize;
  const headBaseY = endY - ny * headSize;
  const wing1X = headBaseX + px * (headSize * 0.5);
  const wing1Y = headBaseY + py * (headSize * 0.5);
  const wing2X = headBaseX - px * (headSize * 0.5);
  const wing2Y = headBaseY - py * (headSize * 0.5);

  return `
    M ${startX} ${startY}
    L ${headBaseX} ${headBaseY}
    M ${wing1X} ${wing1Y}
    L ${endX} ${endY}
    L ${wing2X} ${wing2Y}
  `;
}

// ============================================================================
// Subcomponents
// ============================================================================

/**
 * Single approach vector arrow with optional ETA label.
 */
interface ApproachArrowProps {
  vector: ApproachVectorData;
  videoWidth: number;
  videoHeight: number;
  showETA: boolean;
}

function ApproachArrow({
  vector,
  videoWidth,
  videoHeight,
  showETA,
}: ApproachArrowProps) {
  // Convert positions to pixels
  const [startX, startY] = normalizedToPixel(
    vector.current_position.x,
    vector.current_position.y,
    videoWidth,
    videoHeight
  );

  const [targetX, targetY] = normalizedToPixel(
    vector.zone_centroid.x,
    vector.zone_centroid.y,
    videoWidth,
    videoHeight
  );

  // Calculate arrow geometry
  const { endX, endY, length } = calculateArrowPoints(
    startX,
    startY,
    targetX,
    targetY
  );

  // Skip rendering if arrow is too short
  if (length < MIN_ARROW_LENGTH) {
    return null;
  }

  const color = getUrgencyColor(vector.urgency);
  const arrowPath = createArrowPath(startX, startY, endX, endY);
  const etaText = formatETA(vector.estimated_arrival_seconds);

  // Calculate label position (near arrow head)
  const labelX = endX + LABEL_OFFSET * ((endX - startX) / length || 0);
  const labelY = endY + LABEL_OFFSET * ((endY - startY) / length || 0);

  return (
    <g
      data-testid={`approach-arrow-${vector.track_id}`}
      className={clsx(
        'approach-arrow',
        vector.urgency === 'imminent' && 'animate-pulse'
      )}
    >
      {/* Arrow path */}
      <path
        d={arrowPath}
        fill="none"
        stroke={color}
        strokeWidth={ARROW_WIDTH}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.9}
      />

      {/* Entity indicator dot */}
      <circle
        cx={startX}
        cy={startY}
        r={6}
        fill={color}
        stroke="white"
        strokeWidth={2}
        opacity={0.9}
      />

      {/* ETA label */}
      {showETA && vector.estimated_arrival_seconds !== null && (
        <g>
          {/* Label background */}
          <rect
            x={labelX - 18}
            y={labelY - 10}
            width={36}
            height={20}
            rx={4}
            fill="rgba(0, 0, 0, 0.75)"
          />
          {/* Label text */}
          <text
            x={labelX}
            y={labelY + 4}
            fill={color}
            fontSize="12"
            fontWeight="bold"
            textAnchor="middle"
            dominantBaseline="middle"
            className="pointer-events-none select-none"
          >
            {etaText}
          </text>
        </g>
      )}
    </g>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ApproachVectorOverlay component.
 *
 * Renders SVG arrows showing entities approaching zones with ETA countdowns.
 * Designed to overlay on top of camera feeds alongside CameraZoneOverlay.
 *
 * @param props - Component props
 * @returns Rendered SVG overlay
 */
function ApproachVectorOverlayComponent({
  cameraId,
  videoWidth,
  videoHeight,
  enablePolling = true,
  urgencyFilter,
  showETA = true,
  className,
}: ApproachVectorOverlayProps) {
  // Fetch approach vectors with polling
  const { data, isLoading, error } = useCameraApproachVectors({
    cameraId,
    enabled: true,
    enablePolling,
  });

  // Collect all approach vectors across zones
  const allVectors = useMemo(() => {
    if (!data) return [];

    const vectors: ApproachVectorData[] = [];
    for (const zone of data.zones) {
      for (const vector of zone.approach_vectors) {
        // Only include approaching entities
        if (!vector.is_approaching) continue;

        // Apply urgency filter if provided
        if (urgencyFilter && !urgencyFilter.includes(vector.urgency)) {
          continue;
        }

        vectors.push(vector);
      }
    }

    // Sort by urgency (imminent first)
    vectors.sort((a, b) => {
      const order: Record<ApproachUrgency, number> = {
        imminent: 0,
        approaching: 1,
        distant: 2,
        not_approaching: 3,
      };
      return order[a.urgency] - order[b.urgency];
    });

    return vectors;
  }, [data, urgencyFilter]);

  // Don't render anything if loading or no data
  if (isLoading || error || allVectors.length === 0) {
    return null;
  }

  return (
    <svg
      data-testid="approach-vector-overlay"
      viewBox={`0 0 ${videoWidth} ${videoHeight}`}
      width="100%"
      height="100%"
      className={clsx(
        'pointer-events-none absolute inset-0',
        className
      )}
      aria-label="Approach vector overlay"
      role="img"
      style={{ overflow: 'visible' }}
    >
      {/* Render approach arrows */}
      {allVectors.map((vector) => (
        <ApproachArrow
          key={`arrow-${vector.track_id}`}
          vector={vector}
          videoWidth={videoWidth}
          videoHeight={videoHeight}
          showETA={showETA}
        />
      ))}
    </svg>
  );
}

/**
 * Memoized ApproachVectorOverlay for performance.
 */
export const ApproachVectorOverlay = memo(ApproachVectorOverlayComponent);

export default ApproachVectorOverlay;
