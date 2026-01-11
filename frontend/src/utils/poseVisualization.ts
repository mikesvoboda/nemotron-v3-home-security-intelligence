/**
 * Pose Visualization Utility
 *
 * Provides utilities for rendering COCO 17 keypoint pose skeletons on detection thumbnails.
 * Handles coordinate conversion from normalized (0-1) to canvas coordinates and defines
 * the skeleton connections for proper anatomical rendering.
 *
 * COCO 17 Keypoint Format:
 * 0: nose, 1: left_eye, 2: right_eye, 3: left_ear, 4: right_ear,
 * 5: left_shoulder, 6: right_shoulder, 7: left_elbow, 8: right_elbow,
 * 9: left_wrist, 10: right_wrist, 11: left_hip, 12: right_hip,
 * 13: left_knee, 14: right_knee, 15: left_ankle, 16: right_ankle
 *
 * @see backend/api/schemas/enrichment.py - PoseEnrichment schema
 */

// ============================================================================
// Types
// ============================================================================

/**
 * A single keypoint with x, y coordinates (normalized 0-1) and confidence score.
 */
export interface Keypoint {
  /** X coordinate (0-1 normalized) */
  x: number;
  /** Y coordinate (0-1 normalized) */
  y: number;
  /** Confidence score (0-1) */
  confidence: number;
}

/**
 * A point in canvas/pixel coordinates.
 */
export interface CanvasPoint {
  x: number;
  y: number;
}

/**
 * A skeleton connection between two keypoint indices.
 */
export interface SkeletonConnection {
  /** Starting keypoint index */
  from: number;
  /** Ending keypoint index */
  to: number;
}

/**
 * Pose alert information for highlighting specific poses.
 */
export interface PoseAlert {
  /** Alert type identifier */
  type: string;
  /** Human-readable message */
  message: string;
  /** Keypoint indices involved in the alert */
  keypoints?: number[];
}

/**
 * Color scheme for pose visualization.
 */
export interface PoseColorScheme {
  /** Color for normal keypoints */
  normal: string;
  /** Color for high-confidence keypoints */
  highConfidence: string;
  /** Color for alert/warning poses */
  alert: string;
  /** Color for skeleton lines */
  skeleton: string;
  /** Color for skeleton lines in alert state */
  skeletonAlert: string;
}

// ============================================================================
// Constants
// ============================================================================

/**
 * COCO 17 keypoint names in order.
 */
export const COCO_KEYPOINT_NAMES = [
  'nose',
  'left_eye',
  'right_eye',
  'left_ear',
  'right_ear',
  'left_shoulder',
  'right_shoulder',
  'left_elbow',
  'right_elbow',
  'left_wrist',
  'right_wrist',
  'left_hip',
  'right_hip',
  'left_knee',
  'right_knee',
  'left_ankle',
  'right_ankle',
] as const;

/**
 * Type for COCO keypoint names.
 */
export type CocoKeypointName = (typeof COCO_KEYPOINT_NAMES)[number];

/**
 * Total number of COCO keypoints.
 */
export const COCO_KEYPOINT_COUNT = 17;

/**
 * COCO skeleton connections defining which keypoints to connect.
 * Organized by body region for clarity.
 */
export const COCO_SKELETON_CONNECTIONS: readonly SkeletonConnection[] = [
  // Head connections
  { from: 0, to: 1 },   // nose -> left_eye
  { from: 0, to: 2 },   // nose -> right_eye
  { from: 1, to: 3 },   // left_eye -> left_ear
  { from: 2, to: 4 },   // right_eye -> right_ear

  // Upper body - torso
  { from: 5, to: 6 },   // left_shoulder -> right_shoulder
  { from: 5, to: 11 },  // left_shoulder -> left_hip
  { from: 6, to: 12 },  // right_shoulder -> right_hip
  { from: 11, to: 12 }, // left_hip -> right_hip

  // Left arm
  { from: 5, to: 7 },   // left_shoulder -> left_elbow
  { from: 7, to: 9 },   // left_elbow -> left_wrist

  // Right arm
  { from: 6, to: 8 },   // right_shoulder -> right_elbow
  { from: 8, to: 10 },  // right_elbow -> right_wrist

  // Left leg
  { from: 11, to: 13 }, // left_hip -> left_knee
  { from: 13, to: 15 }, // left_knee -> left_ankle

  // Right leg
  { from: 12, to: 14 }, // right_hip -> right_knee
  { from: 14, to: 16 }, // right_knee -> right_ankle
] as const;

/**
 * Default color scheme for pose visualization.
 */
export const DEFAULT_POSE_COLORS: PoseColorScheme = {
  normal: '#60A5FA',        // light blue (tailwind blue-400)
  highConfidence: '#3B82F6', // bright blue (tailwind blue-500)
  alert: '#EF4444',          // red (tailwind red-500)
  skeleton: '#60A5FA',       // light blue for skeleton lines
  skeletonAlert: '#EF4444',  // red for alert skeleton lines
};

/**
 * Confidence threshold for high-confidence keypoints.
 */
export const HIGH_CONFIDENCE_THRESHOLD = 0.7;

/**
 * Minimum confidence threshold for rendering keypoints.
 */
export const MIN_CONFIDENCE_THRESHOLD = 0.3;

// ============================================================================
// Coordinate Conversion Functions
// ============================================================================

/**
 * Converts a normalized coordinate (0-1) to canvas/pixel coordinate.
 *
 * @param normalizedValue - Value between 0 and 1
 * @param canvasSize - Canvas dimension (width or height) in pixels
 * @returns Pixel coordinate
 *
 * @example
 * ```ts
 * const pixelX = normalizedToCanvas(0.5, 800); // Returns 400
 * ```
 */
export function normalizedToCanvas(normalizedValue: number, canvasSize: number): number {
  return normalizedValue * canvasSize;
}

/**
 * Converts a keypoint with normalized coordinates to canvas coordinates.
 *
 * @param keypoint - Keypoint with normalized x, y (0-1)
 * @param canvasWidth - Canvas width in pixels
 * @param canvasHeight - Canvas height in pixels
 * @returns Canvas point in pixel coordinates
 *
 * @example
 * ```ts
 * const canvasPoint = keypointToCanvas(
 *   { x: 0.5, y: 0.5, confidence: 0.9 },
 *   800,
 *   600
 * );
 * // Returns { x: 400, y: 300 }
 * ```
 */
export function keypointToCanvas(
  keypoint: Keypoint,
  canvasWidth: number,
  canvasHeight: number
): CanvasPoint {
  return {
    x: normalizedToCanvas(keypoint.x, canvasWidth),
    y: normalizedToCanvas(keypoint.y, canvasHeight),
  };
}

/**
 * Converts an array of keypoints from normalized to canvas coordinates.
 *
 * @param keypoints - Array of 17 keypoints with normalized coordinates
 * @param canvasWidth - Canvas width in pixels
 * @param canvasHeight - Canvas height in pixels
 * @returns Array of canvas points (preserves original indices)
 */
export function keypointsToCanvas(
  keypoints: Keypoint[],
  canvasWidth: number,
  canvasHeight: number
): CanvasPoint[] {
  return keypoints.map((kp) => keypointToCanvas(kp, canvasWidth, canvasHeight));
}

// ============================================================================
// Keypoint Data Processing Functions
// ============================================================================

/**
 * Parses raw keypoint data from the backend (array of [x, y, conf]) to Keypoint objects.
 *
 * @param rawKeypoints - Array of [x, y, confidence] tuples from backend
 * @returns Array of Keypoint objects
 *
 * @example
 * ```ts
 * const keypoints = parseRawKeypoints([[0.5, 0.3, 0.9], [0.52, 0.28, 0.85]]);
 * // Returns [{ x: 0.5, y: 0.3, confidence: 0.9 }, ...]
 * ```
 */
export function parseRawKeypoints(rawKeypoints: number[][]): Keypoint[] {
  return rawKeypoints.map(([x, y, confidence]) => ({
    x: x ?? 0,
    y: y ?? 0,
    confidence: confidence ?? 0,
  }));
}

/**
 * Validates that keypoints array has the expected COCO 17 format.
 *
 * @param keypoints - Array of keypoints to validate
 * @returns True if valid, false otherwise
 */
export function validateKeypoints(keypoints: Keypoint[]): boolean {
  if (keypoints.length !== COCO_KEYPOINT_COUNT) {
    return false;
  }

  return keypoints.every(
    (kp) =>
      typeof kp.x === 'number' &&
      typeof kp.y === 'number' &&
      typeof kp.confidence === 'number' &&
      kp.x >= 0 &&
      kp.x <= 1 &&
      kp.y >= 0 &&
      kp.y <= 1 &&
      kp.confidence >= 0 &&
      kp.confidence <= 1
  );
}

/**
 * Filters keypoints by minimum confidence threshold.
 *
 * @param keypoints - Array of keypoints
 * @param minConfidence - Minimum confidence threshold (default: MIN_CONFIDENCE_THRESHOLD)
 * @returns Array of keypoints with their original indices that pass the threshold
 */
export function filterKeypointsByConfidence(
  keypoints: Keypoint[],
  minConfidence: number = MIN_CONFIDENCE_THRESHOLD
): Array<{ keypoint: Keypoint; index: number }> {
  return keypoints
    .map((keypoint, index) => ({ keypoint, index }))
    .filter(({ keypoint }) => keypoint.confidence >= minConfidence);
}

// ============================================================================
// Color Selection Functions
// ============================================================================

/**
 * Gets the color for a keypoint based on confidence and alert status.
 *
 * @param confidence - Keypoint confidence score (0-1)
 * @param isAlert - Whether the keypoint is part of an alert pose
 * @param colors - Color scheme to use (default: DEFAULT_POSE_COLORS)
 * @returns Hex color string
 */
export function getKeypointColor(
  confidence: number,
  isAlert: boolean = false,
  colors: PoseColorScheme = DEFAULT_POSE_COLORS
): string {
  if (isAlert) {
    return colors.alert;
  }
  if (confidence >= HIGH_CONFIDENCE_THRESHOLD) {
    return colors.highConfidence;
  }
  return colors.normal;
}

/**
 * Gets the color for a skeleton connection based on alert status.
 *
 * @param isAlert - Whether the connection is part of an alert pose
 * @param colors - Color scheme to use (default: DEFAULT_POSE_COLORS)
 * @returns Hex color string
 */
export function getSkeletonColor(
  isAlert: boolean = false,
  colors: PoseColorScheme = DEFAULT_POSE_COLORS
): string {
  return isAlert ? colors.skeletonAlert : colors.skeleton;
}

// ============================================================================
// Skeleton Connection Utilities
// ============================================================================

/**
 * Gets valid skeleton connections where both keypoints exceed confidence threshold.
 *
 * @param keypoints - Array of 17 keypoints
 * @param minConfidence - Minimum confidence for both endpoints
 * @returns Array of valid connections with their keypoint data
 */
export function getValidConnections(
  keypoints: Keypoint[],
  minConfidence: number = MIN_CONFIDENCE_THRESHOLD
): Array<{
  connection: SkeletonConnection;
  from: { point: CanvasPoint; confidence: number };
  to: { point: CanvasPoint; confidence: number };
}> {
  // This returns raw keypoint data, not canvas points
  // Caller should convert to canvas coordinates with specific dimensions
  return COCO_SKELETON_CONNECTIONS.filter(
    (conn) =>
      keypoints[conn.from]?.confidence >= minConfidence &&
      keypoints[conn.to]?.confidence >= minConfidence
  ).map((connection) => ({
    connection,
    from: {
      point: { x: keypoints[connection.from].x, y: keypoints[connection.from].y },
      confidence: keypoints[connection.from].confidence,
    },
    to: {
      point: { x: keypoints[connection.to].x, y: keypoints[connection.to].y },
      confidence: keypoints[connection.to].confidence,
    },
  }));
}

/**
 * Checks if a keypoint index is part of any alert.
 *
 * @param index - Keypoint index (0-16)
 * @param alerts - Array of pose alerts
 * @returns True if the keypoint is involved in any alert
 */
export function isKeypointInAlert(index: number, alerts: PoseAlert[]): boolean {
  return alerts.some((alert) => alert.keypoints?.includes(index));
}

/**
 * Checks if a connection is part of any alert.
 *
 * @param connection - Skeleton connection
 * @param alerts - Array of pose alerts
 * @returns True if either endpoint is involved in any alert
 */
export function isConnectionInAlert(connection: SkeletonConnection, alerts: PoseAlert[]): boolean {
  return isKeypointInAlert(connection.from, alerts) || isKeypointInAlert(connection.to, alerts);
}

// ============================================================================
// SVG Path Generation
// ============================================================================

/**
 * Generates SVG circle element attributes for a keypoint.
 *
 * @param point - Canvas point coordinates
 * @param radius - Circle radius in pixels
 * @param color - Fill color
 * @returns SVG circle attributes object
 */
export function generateKeypointCircleAttrs(
  point: CanvasPoint,
  radius: number,
  color: string
): { cx: number; cy: number; r: number; fill: string } {
  return {
    cx: point.x,
    cy: point.y,
    r: radius,
    fill: color,
  };
}

/**
 * Generates SVG line element attributes for a skeleton connection.
 *
 * @param from - Starting canvas point
 * @param to - Ending canvas point
 * @param color - Stroke color
 * @param strokeWidth - Line width in pixels
 * @returns SVG line attributes object
 */
export function generateConnectionLineAttrs(
  from: CanvasPoint,
  to: CanvasPoint,
  color: string,
  strokeWidth: number
): { x1: number; y1: number; x2: number; y2: number; stroke: string; strokeWidth: number } {
  return {
    x1: from.x,
    y1: from.y,
    x2: to.x,
    y2: to.y,
    stroke: color,
    strokeWidth,
  };
}

// ============================================================================
// Keypoint Name Utilities
// ============================================================================

/**
 * Gets the name of a keypoint by its index.
 *
 * @param index - Keypoint index (0-16)
 * @returns Keypoint name or 'unknown' if index is invalid
 */
export function getKeypointName(index: number): string {
  if (index < 0 || index >= COCO_KEYPOINT_COUNT) {
    return 'unknown';
  }
  return COCO_KEYPOINT_NAMES[index];
}

/**
 * Gets the index of a keypoint by its name.
 *
 * @param name - Keypoint name
 * @returns Keypoint index or -1 if name is not found
 */
export function getKeypointIndex(name: CocoKeypointName): number {
  return COCO_KEYPOINT_NAMES.indexOf(name);
}
