/* eslint-disable react-refresh/only-export-components -- exporting pose skeleton utilities alongside component for convenient co-location */
/**
 * PoseSkeletonOverlay Component
 *
 * Renders pose skeleton keypoints and connections on detection thumbnails.
 * Uses COCO 17-keypoint format for body pose visualization.
 *
 * Features:
 * - Renders keypoints as circles with confidence-based opacity
 * - Draws connections (bones) between related keypoints
 * - Color-codes different body parts (head, torso, arms, legs)
 * - Supports minimum confidence filtering
 * - Toggleable visibility
 * - Scales automatically to container dimensions
 */

import React, { memo } from 'react';

/**
 * Keypoint data structure matching backend pose enrichment format.
 * Each keypoint is [x, y, confidence] where:
 * - x, y: pixel coordinates in the original image
 * - confidence: detection confidence 0-1
 */
export type Keypoint = [number, number, number];

export interface PoseSkeletonOverlayProps {
  /** Array of keypoints in COCO format [[x, y, conf], ...] */
  keypoints: Keypoint[] | null | undefined;
  /** Width of the underlying image in pixels */
  imageWidth: number;
  /** Height of the underlying image in pixels */
  imageHeight: number;
  /** Minimum confidence threshold to show keypoints (default: 0.3) */
  minConfidence?: number;
  /** Whether to show the skeleton overlay (default: true) */
  visible?: boolean;
  /** Whether to show keypoint circles (default: true) */
  showKeypoints?: boolean;
  /** Whether to show skeleton connections/bones (default: true) */
  showConnections?: boolean;
  /** Keypoint circle radius in pixels (default: 4) */
  keypointRadius?: number;
  /** Connection line width in pixels (default: 2) */
  lineWidth?: number;
}

/**
 * COCO keypoint indices for the 17-keypoint format.
 * Standard format used by most pose estimation models.
 */
export const COCO_KEYPOINT_NAMES = [
  'nose', // 0
  'left_eye', // 1
  'right_eye', // 2
  'left_ear', // 3
  'right_ear', // 4
  'left_shoulder', // 5
  'right_shoulder', // 6
  'left_elbow', // 7
  'right_elbow', // 8
  'left_wrist', // 9
  'right_wrist', // 10
  'left_hip', // 11
  'right_hip', // 12
  'left_knee', // 13
  'right_knee', // 14
  'left_ankle', // 15
  'right_ankle', // 16
] as const;

/**
 * Skeleton connections defining which keypoints to connect.
 * Each pair [from, to] indicates a bone/connection.
 */
export const SKELETON_CONNECTIONS: [number, number][] = [
  // Head
  [0, 1], // nose - left_eye
  [0, 2], // nose - right_eye
  [1, 3], // left_eye - left_ear
  [2, 4], // right_eye - right_ear
  // Torso
  [5, 6], // left_shoulder - right_shoulder
  [5, 11], // left_shoulder - left_hip
  [6, 12], // right_shoulder - right_hip
  [11, 12], // left_hip - right_hip
  // Left arm
  [5, 7], // left_shoulder - left_elbow
  [7, 9], // left_elbow - left_wrist
  // Right arm
  [6, 8], // right_shoulder - right_elbow
  [8, 10], // right_elbow - right_wrist
  // Left leg
  [11, 13], // left_hip - left_knee
  [13, 15], // left_knee - left_ankle
  // Right leg
  [12, 14], // right_hip - right_knee
  [14, 16], // right_knee - right_ankle
];

/**
 * Body part categories for color coding.
 */
type BodyPart = 'head' | 'torso' | 'left_arm' | 'right_arm' | 'left_leg' | 'right_leg';

/**
 * Map keypoint indices to body parts for color coding.
 */
const KEYPOINT_BODY_PARTS: Record<number, BodyPart> = {
  0: 'head', // nose
  1: 'head', // left_eye
  2: 'head', // right_eye
  3: 'head', // left_ear
  4: 'head', // right_ear
  5: 'torso', // left_shoulder
  6: 'torso', // right_shoulder
  7: 'left_arm', // left_elbow
  8: 'right_arm', // right_elbow
  9: 'left_arm', // left_wrist
  10: 'right_arm', // right_wrist
  11: 'torso', // left_hip
  12: 'torso', // right_hip
  13: 'left_leg', // left_knee
  14: 'right_leg', // right_knee
  15: 'left_leg', // left_ankle
  16: 'right_leg', // right_ankle
};

/**
 * Colors for different body parts.
 * Using distinct, visible colors for easy identification.
 */
export const BODY_PART_COLORS: Record<BodyPart, string> = {
  head: '#22c55e', // green
  torso: '#eab308', // yellow
  left_arm: '#3b82f6', // blue
  right_arm: '#8b5cf6', // purple
  left_leg: '#ef4444', // red
  right_leg: '#f97316', // orange
};

/**
 * Get the body part for a given keypoint index.
 */
export function getBodyPart(keypointIndex: number): BodyPart {
  return KEYPOINT_BODY_PARTS[keypointIndex] ?? 'torso';
}

/**
 * Get the color for a given keypoint index.
 */
export function getKeypointColor(keypointIndex: number): string {
  const bodyPart = getBodyPart(keypointIndex);
  return BODY_PART_COLORS[bodyPart];
}

/**
 * Get the color for a connection based on the body parts it connects.
 * Uses the color of the "from" keypoint's body part.
 */
export function getConnectionColor(fromIndex: number, toIndex: number): string {
  // Use the body part of the connection endpoints to determine color
  const fromPart = getBodyPart(fromIndex);
  const toPart = getBodyPart(toIndex);

  // For connections between different body parts, use a blend or prefer one
  if (fromPart === toPart) {
    return BODY_PART_COLORS[fromPart];
  }

  // For cross-body-part connections, prefer the more specific part
  // (e.g., arm over torso for shoulder-elbow connection)
  if (fromPart === 'torso') {
    return BODY_PART_COLORS[toPart];
  }
  if (toPart === 'torso') {
    return BODY_PART_COLORS[fromPart];
  }

  return BODY_PART_COLORS[fromPart];
}

/**
 * Custom equality function for React.memo to prevent unnecessary re-renders.
 */
export function arePropsEqual(
  prevProps: PoseSkeletonOverlayProps,
  nextProps: PoseSkeletonOverlayProps
): boolean {
  // Check primitive props first (fast path)
  if (
    prevProps.imageWidth !== nextProps.imageWidth ||
    prevProps.imageHeight !== nextProps.imageHeight ||
    prevProps.minConfidence !== nextProps.minConfidence ||
    prevProps.visible !== nextProps.visible ||
    prevProps.showKeypoints !== nextProps.showKeypoints ||
    prevProps.showConnections !== nextProps.showConnections ||
    prevProps.keypointRadius !== nextProps.keypointRadius ||
    prevProps.lineWidth !== nextProps.lineWidth
  ) {
    return false;
  }

  // Handle null/undefined keypoints
  const prevKeypoints = prevProps.keypoints;
  const nextKeypoints = nextProps.keypoints;

  if (prevKeypoints === nextKeypoints) {
    return true;
  }
  if (!prevKeypoints || !nextKeypoints) {
    return false;
  }
  if (prevKeypoints.length !== nextKeypoints.length) {
    return false;
  }

  // Deep compare each keypoint
  for (let i = 0; i < prevKeypoints.length; i++) {
    const prev = prevKeypoints[i];
    const next = nextKeypoints[i];
    if (prev[0] !== next[0] || prev[1] !== next[1] || prev[2] !== next[2]) {
      return false;
    }
  }

  return true;
}

/**
 * PoseSkeletonOverlay renders body pose keypoints and connections on detection images.
 *
 * @example
 * ```tsx
 * <PoseSkeletonOverlay
 *   keypoints={[[100, 150, 0.9], [120, 160, 0.85], ...]}
 *   imageWidth={640}
 *   imageHeight={480}
 *   minConfidence={0.5}
 * />
 * ```
 */
const PoseSkeletonOverlayComponent: React.FC<PoseSkeletonOverlayProps> = ({
  keypoints,
  imageWidth,
  imageHeight,
  minConfidence = 0.3,
  visible = true,
  showKeypoints = true,
  showConnections = true,
  keypointRadius = 4,
  lineWidth = 2,
}) => {
  // Early returns for invalid states
  if (!visible) {
    return null;
  }

  if (imageWidth <= 0 || imageHeight <= 0) {
    return null;
  }

  if (!keypoints || keypoints.length === 0) {
    return null;
  }

  // Filter keypoints by confidence
  const validKeypoints = keypoints.map((kp, index) => ({
    index,
    x: kp[0],
    y: kp[1],
    confidence: kp[2],
    isValid: kp[2] >= minConfidence,
  }));

  // Check if we have any valid keypoints to render
  const hasValidKeypoints = validKeypoints.some((kp) => kp.isValid);
  if (!hasValidKeypoints) {
    return null;
  }

  // Filter connections where both endpoints are valid
  const validConnections = SKELETON_CONNECTIONS.filter(([from, to]) => {
    const fromKp = validKeypoints[from];
    const toKp = validKeypoints[to];
    return fromKp?.isValid && toKp?.isValid;
  });

  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full"
      viewBox={`0 0 ${imageWidth} ${imageHeight}`}
      preserveAspectRatio="none"
      style={{ zIndex: 20 }}
      data-testid="pose-skeleton-overlay"
    >
      {/* Render connections (bones) first so keypoints render on top */}
      {showConnections &&
        validConnections.map(([from, to]) => {
          const fromKp = validKeypoints[from];
          const toKp = validKeypoints[to];
          const color = getConnectionColor(from, to);
          // Use minimum opacity of the two endpoints
          const opacity = Math.min(fromKp.confidence, toKp.confidence);

          return (
            <line
              key={`connection-${from}-${to}`}
              x1={fromKp.x}
              y1={fromKp.y}
              x2={toKp.x}
              y2={toKp.y}
              stroke={color}
              strokeWidth={lineWidth}
              strokeLinecap="round"
              opacity={opacity}
              data-testid={`pose-connection-${from}-${to}`}
            />
          );
        })}

      {/* Render keypoints */}
      {showKeypoints &&
        validKeypoints
          .filter((kp) => kp.isValid)
          .map((kp) => {
            const color = getKeypointColor(kp.index);
            return (
              <circle
                key={`keypoint-${kp.index}`}
                cx={kp.x}
                cy={kp.y}
                r={keypointRadius}
                fill={color}
                stroke="#ffffff"
                strokeWidth={1}
                opacity={kp.confidence}
                data-testid={`pose-keypoint-${kp.index}`}
              />
            );
          })}
    </svg>
  );
};

// Wrap component with React.memo using custom equality function
const PoseSkeletonOverlay = memo(PoseSkeletonOverlayComponent, arePropsEqual);

export default PoseSkeletonOverlay;
