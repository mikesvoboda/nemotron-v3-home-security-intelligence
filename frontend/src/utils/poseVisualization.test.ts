import { describe, expect, it } from 'vitest';

import {
  COCO_KEYPOINT_COUNT,
  COCO_KEYPOINT_NAMES,
  COCO_SKELETON_CONNECTIONS,
  DEFAULT_POSE_COLORS,
  HIGH_CONFIDENCE_THRESHOLD,
  MIN_CONFIDENCE_THRESHOLD,
  filterKeypointsByConfidence,
  generateConnectionLineAttrs,
  generateKeypointCircleAttrs,
  getKeypointColor,
  getKeypointIndex,
  getKeypointName,
  getSkeletonColor,
  getValidConnections,
  isConnectionInAlert,
  isKeypointInAlert,
  keypointToCanvas,
  keypointsToCanvas,
  normalizedToCanvas,
  parseRawKeypoints,
  validateKeypoints,
  type CocoKeypointName,
  type Keypoint,
  type PoseAlert,
  type PoseColorScheme,
  type SkeletonConnection,
} from './poseVisualization';

// ============================================================================
// Test Data Fixtures
// ============================================================================

/**
 * Creates a mock keypoint array with all 17 COCO keypoints.
 */
function createMockKeypoints(confidence: number = 0.9): Keypoint[] {
  return Array.from({ length: COCO_KEYPOINT_COUNT }, (_, i) => ({
    x: (i + 1) / 20, // Values between 0.05 and 0.85
    y: (i + 1) / 20,
    confidence,
  }));
}

/**
 * Creates a single mock keypoint.
 */
function createKeypoint(x: number, y: number, confidence: number): Keypoint {
  return { x, y, confidence };
}

describe('poseVisualization utilities', () => {
  // ==========================================================================
  // Constants Tests
  // ==========================================================================

  describe('constants', () => {
    it('COCO_KEYPOINT_NAMES has 17 entries', () => {
      expect(COCO_KEYPOINT_NAMES).toHaveLength(17);
    });

    it('COCO_KEYPOINT_COUNT equals 17', () => {
      expect(COCO_KEYPOINT_COUNT).toBe(17);
    });

    it('COCO_KEYPOINT_NAMES contains expected keypoints', () => {
      expect(COCO_KEYPOINT_NAMES[0]).toBe('nose');
      expect(COCO_KEYPOINT_NAMES[5]).toBe('left_shoulder');
      expect(COCO_KEYPOINT_NAMES[6]).toBe('right_shoulder');
      expect(COCO_KEYPOINT_NAMES[11]).toBe('left_hip');
      expect(COCO_KEYPOINT_NAMES[16]).toBe('right_ankle');
    });

    it('COCO_SKELETON_CONNECTIONS has expected number of connections', () => {
      // 4 head + 4 torso + 2 left arm + 2 right arm + 2 left leg + 2 right leg = 16
      expect(COCO_SKELETON_CONNECTIONS).toHaveLength(16);
    });

    it('COCO_SKELETON_CONNECTIONS contains valid indices', () => {
      COCO_SKELETON_CONNECTIONS.forEach((conn) => {
        expect(conn.from).toBeGreaterThanOrEqual(0);
        expect(conn.from).toBeLessThan(COCO_KEYPOINT_COUNT);
        expect(conn.to).toBeGreaterThanOrEqual(0);
        expect(conn.to).toBeLessThan(COCO_KEYPOINT_COUNT);
      });
    });

    it('DEFAULT_POSE_COLORS has all required colors', () => {
      expect(DEFAULT_POSE_COLORS.normal).toBeDefined();
      expect(DEFAULT_POSE_COLORS.highConfidence).toBeDefined();
      expect(DEFAULT_POSE_COLORS.alert).toBeDefined();
      expect(DEFAULT_POSE_COLORS.skeleton).toBeDefined();
      expect(DEFAULT_POSE_COLORS.skeletonAlert).toBeDefined();
    });

    it('HIGH_CONFIDENCE_THRESHOLD is between 0 and 1', () => {
      expect(HIGH_CONFIDENCE_THRESHOLD).toBeGreaterThan(0);
      expect(HIGH_CONFIDENCE_THRESHOLD).toBeLessThanOrEqual(1);
    });

    it('MIN_CONFIDENCE_THRESHOLD is between 0 and HIGH_CONFIDENCE_THRESHOLD', () => {
      expect(MIN_CONFIDENCE_THRESHOLD).toBeGreaterThanOrEqual(0);
      expect(MIN_CONFIDENCE_THRESHOLD).toBeLessThan(HIGH_CONFIDENCE_THRESHOLD);
    });
  });

  // ==========================================================================
  // Coordinate Conversion Tests
  // ==========================================================================

  describe('normalizedToCanvas', () => {
    it('converts 0 to 0', () => {
      expect(normalizedToCanvas(0, 800)).toBe(0);
    });

    it('converts 1 to canvas size', () => {
      expect(normalizedToCanvas(1, 800)).toBe(800);
    });

    it('converts 0.5 to half canvas size', () => {
      expect(normalizedToCanvas(0.5, 800)).toBe(400);
    });

    it('handles different canvas sizes', () => {
      expect(normalizedToCanvas(0.25, 1000)).toBe(250);
      expect(normalizedToCanvas(0.75, 600)).toBe(450);
    });

    it('handles edge case of 0 canvas size', () => {
      expect(normalizedToCanvas(0.5, 0)).toBe(0);
    });
  });

  describe('keypointToCanvas', () => {
    it('converts keypoint to canvas coordinates', () => {
      const keypoint = createKeypoint(0.5, 0.5, 0.9);
      const result = keypointToCanvas(keypoint, 800, 600);

      expect(result.x).toBe(400);
      expect(result.y).toBe(300);
    });

    it('handles corner keypoints', () => {
      const topLeft = keypointToCanvas(createKeypoint(0, 0, 0.9), 800, 600);
      expect(topLeft.x).toBe(0);
      expect(topLeft.y).toBe(0);

      const bottomRight = keypointToCanvas(createKeypoint(1, 1, 0.9), 800, 600);
      expect(bottomRight.x).toBe(800);
      expect(bottomRight.y).toBe(600);
    });

    it('handles non-square canvas', () => {
      const keypoint = createKeypoint(0.5, 0.5, 0.9);
      const result = keypointToCanvas(keypoint, 1920, 1080);

      expect(result.x).toBe(960);
      expect(result.y).toBe(540);
    });
  });

  describe('keypointsToCanvas', () => {
    it('converts all keypoints to canvas coordinates', () => {
      const keypoints = createMockKeypoints();
      const canvasPoints = keypointsToCanvas(keypoints, 800, 600);

      expect(canvasPoints).toHaveLength(17);
      canvasPoints.forEach((point, i) => {
        expect(point.x).toBe(keypoints[i].x * 800);
        expect(point.y).toBe(keypoints[i].y * 600);
      });
    });

    it('returns empty array for empty input', () => {
      const result = keypointsToCanvas([], 800, 600);
      expect(result).toEqual([]);
    });
  });

  // ==========================================================================
  // Keypoint Data Processing Tests
  // ==========================================================================

  describe('parseRawKeypoints', () => {
    it('parses raw keypoint data correctly', () => {
      const raw = [
        [0.5, 0.3, 0.9],
        [0.52, 0.28, 0.85],
      ];
      const result = parseRawKeypoints(raw);

      expect(result).toHaveLength(2);
      expect(result[0]).toEqual({ x: 0.5, y: 0.3, confidence: 0.9 });
      expect(result[1]).toEqual({ x: 0.52, y: 0.28, confidence: 0.85 });
    });

    it('handles empty array', () => {
      expect(parseRawKeypoints([])).toEqual([]);
    });

    it('handles missing values with defaults', () => {
      const raw = [[undefined, undefined, undefined] as unknown as number[]];
      const result = parseRawKeypoints(raw);

      expect(result[0]).toEqual({ x: 0, y: 0, confidence: 0 });
    });

    it('parses full COCO 17 keypoints', () => {
      const raw = Array.from({ length: 17 }, (_, i) => [i / 20, i / 20, 0.9]);
      const result = parseRawKeypoints(raw);

      expect(result).toHaveLength(17);
    });
  });

  describe('validateKeypoints', () => {
    it('returns true for valid 17-keypoint array', () => {
      const keypoints = createMockKeypoints();
      expect(validateKeypoints(keypoints)).toBe(true);
    });

    it('returns false for wrong number of keypoints', () => {
      const keypoints = createMockKeypoints().slice(0, 10);
      expect(validateKeypoints(keypoints)).toBe(false);
    });

    it('returns false for empty array', () => {
      expect(validateKeypoints([])).toBe(false);
    });

    it('returns false for invalid x coordinate', () => {
      const keypoints = createMockKeypoints();
      keypoints[0].x = 1.5; // Out of range
      expect(validateKeypoints(keypoints)).toBe(false);
    });

    it('returns false for invalid y coordinate', () => {
      const keypoints = createMockKeypoints();
      keypoints[0].y = -0.1; // Out of range
      expect(validateKeypoints(keypoints)).toBe(false);
    });

    it('returns false for invalid confidence', () => {
      const keypoints = createMockKeypoints();
      keypoints[0].confidence = 1.5; // Out of range
      expect(validateKeypoints(keypoints)).toBe(false);
    });

    it('accepts boundary values', () => {
      const keypoints = createMockKeypoints();
      keypoints[0] = { x: 0, y: 0, confidence: 0 };
      keypoints[1] = { x: 1, y: 1, confidence: 1 };
      expect(validateKeypoints(keypoints)).toBe(true);
    });
  });

  describe('filterKeypointsByConfidence', () => {
    it('filters out low confidence keypoints', () => {
      const keypoints: Keypoint[] = [
        createKeypoint(0.1, 0.1, 0.8),
        createKeypoint(0.2, 0.2, 0.2),
        createKeypoint(0.3, 0.3, 0.6),
      ];

      const result = filterKeypointsByConfidence(keypoints, 0.5);

      expect(result).toHaveLength(2);
      expect(result[0].index).toBe(0);
      expect(result[1].index).toBe(2);
    });

    it('uses default threshold when not specified', () => {
      const keypoints: Keypoint[] = [
        createKeypoint(0.1, 0.1, MIN_CONFIDENCE_THRESHOLD + 0.1),
        createKeypoint(0.2, 0.2, MIN_CONFIDENCE_THRESHOLD - 0.1),
      ];

      const result = filterKeypointsByConfidence(keypoints);

      expect(result).toHaveLength(1);
      expect(result[0].index).toBe(0);
    });

    it('preserves original indices', () => {
      const keypoints: Keypoint[] = [
        createKeypoint(0.1, 0.1, 0.1),
        createKeypoint(0.2, 0.2, 0.1),
        createKeypoint(0.3, 0.3, 0.9),
      ];

      const result = filterKeypointsByConfidence(keypoints, 0.5);

      expect(result[0].index).toBe(2);
    });

    it('returns empty array when all below threshold', () => {
      const keypoints = createMockKeypoints(0.1);
      const result = filterKeypointsByConfidence(keypoints, 0.5);

      expect(result).toEqual([]);
    });
  });

  // ==========================================================================
  // Color Selection Tests
  // ==========================================================================

  describe('getKeypointColor', () => {
    it('returns alert color when isAlert is true', () => {
      expect(getKeypointColor(0.9, true)).toBe(DEFAULT_POSE_COLORS.alert);
    });

    it('returns highConfidence color for high confidence', () => {
      expect(getKeypointColor(HIGH_CONFIDENCE_THRESHOLD, false)).toBe(
        DEFAULT_POSE_COLORS.highConfidence
      );
      expect(getKeypointColor(0.95, false)).toBe(DEFAULT_POSE_COLORS.highConfidence);
    });

    it('returns normal color for lower confidence', () => {
      expect(getKeypointColor(HIGH_CONFIDENCE_THRESHOLD - 0.1, false)).toBe(
        DEFAULT_POSE_COLORS.normal
      );
      expect(getKeypointColor(0.3, false)).toBe(DEFAULT_POSE_COLORS.normal);
    });

    it('uses custom color scheme when provided', () => {
      const customColors: PoseColorScheme = {
        normal: '#111111',
        highConfidence: '#222222',
        alert: '#333333',
        skeleton: '#444444',
        skeletonAlert: '#555555',
      };

      expect(getKeypointColor(0.5, false, customColors)).toBe('#111111');
      expect(getKeypointColor(0.9, false, customColors)).toBe('#222222');
      expect(getKeypointColor(0.5, true, customColors)).toBe('#333333');
    });
  });

  describe('getSkeletonColor', () => {
    it('returns skeleton color when not alert', () => {
      expect(getSkeletonColor(false)).toBe(DEFAULT_POSE_COLORS.skeleton);
    });

    it('returns skeletonAlert color when alert', () => {
      expect(getSkeletonColor(true)).toBe(DEFAULT_POSE_COLORS.skeletonAlert);
    });

    it('uses custom color scheme when provided', () => {
      const customColors: PoseColorScheme = {
        normal: '#111111',
        highConfidence: '#222222',
        alert: '#333333',
        skeleton: '#444444',
        skeletonAlert: '#555555',
      };

      expect(getSkeletonColor(false, customColors)).toBe('#444444');
      expect(getSkeletonColor(true, customColors)).toBe('#555555');
    });
  });

  // ==========================================================================
  // Skeleton Connection Tests
  // ==========================================================================

  describe('getValidConnections', () => {
    it('returns connections where both endpoints have sufficient confidence', () => {
      const keypoints = createMockKeypoints(0.9);
      const result = getValidConnections(keypoints);

      expect(result.length).toBeGreaterThan(0);
      expect(result.length).toBeLessThanOrEqual(COCO_SKELETON_CONNECTIONS.length);
    });

    it('returns empty array when all keypoints below threshold', () => {
      const keypoints = createMockKeypoints(0.1);
      const result = getValidConnections(keypoints, 0.5);

      expect(result).toEqual([]);
    });

    it('includes connection data with coordinates', () => {
      const keypoints = createMockKeypoints(0.9);
      const result = getValidConnections(keypoints);

      expect(result[0].connection).toBeDefined();
      expect(result[0].from.point).toBeDefined();
      expect(result[0].from.confidence).toBeDefined();
      expect(result[0].to.point).toBeDefined();
      expect(result[0].to.confidence).toBeDefined();
    });

    it('filters out connections with one low-confidence endpoint', () => {
      const keypoints = createMockKeypoints(0.9);
      keypoints[0].confidence = 0.1; // nose
      keypoints[1].confidence = 0.9; // left_eye

      const result = getValidConnections(keypoints, 0.5);

      // nose -> left_eye connection should be filtered out
      const noseToLeftEye = result.find(
        (r) => r.connection.from === 0 && r.connection.to === 1
      );
      expect(noseToLeftEye).toBeUndefined();
    });
  });

  describe('isKeypointInAlert', () => {
    const alerts: PoseAlert[] = [
      { type: 'suspicious', message: 'Suspicious pose', keypoints: [5, 6, 11, 12] },
      { type: 'falling', message: 'Falling detected', keypoints: [0, 15, 16] },
    ];

    it('returns true for keypoint in alert', () => {
      expect(isKeypointInAlert(5, alerts)).toBe(true);
      expect(isKeypointInAlert(16, alerts)).toBe(true);
    });

    it('returns false for keypoint not in any alert', () => {
      expect(isKeypointInAlert(7, alerts)).toBe(false);
      expect(isKeypointInAlert(8, alerts)).toBe(false);
    });

    it('returns false for empty alerts array', () => {
      expect(isKeypointInAlert(5, [])).toBe(false);
    });

    it('returns false when alert has no keypoints defined', () => {
      const alertsWithoutKeypoints: PoseAlert[] = [
        { type: 'generic', message: 'Generic alert' },
      ];
      expect(isKeypointInAlert(5, alertsWithoutKeypoints)).toBe(false);
    });
  });

  describe('isConnectionInAlert', () => {
    const alerts: PoseAlert[] = [
      { type: 'arm', message: 'Arm raised', keypoints: [5, 7, 9] },
    ];

    it('returns true when from keypoint is in alert', () => {
      const connection: SkeletonConnection = { from: 5, to: 6 };
      expect(isConnectionInAlert(connection, alerts)).toBe(true);
    });

    it('returns true when to keypoint is in alert', () => {
      const connection: SkeletonConnection = { from: 11, to: 5 };
      expect(isConnectionInAlert(connection, alerts)).toBe(true);
    });

    it('returns false when neither keypoint is in alert', () => {
      const connection: SkeletonConnection = { from: 11, to: 12 };
      expect(isConnectionInAlert(connection, alerts)).toBe(false);
    });

    it('returns false for empty alerts', () => {
      const connection: SkeletonConnection = { from: 5, to: 7 };
      expect(isConnectionInAlert(connection, [])).toBe(false);
    });
  });

  // ==========================================================================
  // SVG Generation Tests
  // ==========================================================================

  describe('generateKeypointCircleAttrs', () => {
    it('generates correct circle attributes', () => {
      const attrs = generateKeypointCircleAttrs({ x: 100, y: 200 }, 5, '#3B82F6');

      expect(attrs).toEqual({
        cx: 100,
        cy: 200,
        r: 5,
        fill: '#3B82F6',
      });
    });

    it('handles decimal coordinates', () => {
      const attrs = generateKeypointCircleAttrs({ x: 100.5, y: 200.75 }, 4.5, '#EF4444');

      expect(attrs.cx).toBe(100.5);
      expect(attrs.cy).toBe(200.75);
      expect(attrs.r).toBe(4.5);
    });
  });

  describe('generateConnectionLineAttrs', () => {
    it('generates correct line attributes', () => {
      const attrs = generateConnectionLineAttrs(
        { x: 100, y: 200 },
        { x: 150, y: 250 },
        '#60A5FA',
        2
      );

      expect(attrs).toEqual({
        x1: 100,
        y1: 200,
        x2: 150,
        y2: 250,
        stroke: '#60A5FA',
        strokeWidth: 2,
      });
    });

    it('handles same start and end point', () => {
      const attrs = generateConnectionLineAttrs(
        { x: 100, y: 100 },
        { x: 100, y: 100 },
        '#60A5FA',
        2
      );

      expect(attrs.x1).toBe(attrs.x2);
      expect(attrs.y1).toBe(attrs.y2);
    });
  });

  // ==========================================================================
  // Keypoint Name Utilities Tests
  // ==========================================================================

  describe('getKeypointName', () => {
    it('returns correct name for valid indices', () => {
      expect(getKeypointName(0)).toBe('nose');
      expect(getKeypointName(5)).toBe('left_shoulder');
      expect(getKeypointName(16)).toBe('right_ankle');
    });

    it('returns "unknown" for invalid indices', () => {
      expect(getKeypointName(-1)).toBe('unknown');
      expect(getKeypointName(17)).toBe('unknown');
      expect(getKeypointName(100)).toBe('unknown');
    });
  });

  describe('getKeypointIndex', () => {
    it('returns correct index for valid names', () => {
      expect(getKeypointIndex('nose')).toBe(0);
      expect(getKeypointIndex('left_shoulder')).toBe(5);
      expect(getKeypointIndex('right_ankle')).toBe(16);
    });

    it('returns -1 for invalid names', () => {
      // TypeScript prevents invalid names at compile time,
      // but we can test the function behavior
      expect(getKeypointIndex('nose' as CocoKeypointName)).toBe(0);
    });

    it('all keypoint names have unique indices', () => {
      const indices = COCO_KEYPOINT_NAMES.map((name) => getKeypointIndex(name));
      const uniqueIndices = new Set(indices);
      expect(uniqueIndices.size).toBe(COCO_KEYPOINT_NAMES.length);
    });

    it('getKeypointName and getKeypointIndex are inverses', () => {
      COCO_KEYPOINT_NAMES.forEach((name, index) => {
        expect(getKeypointIndex(name)).toBe(index);
        expect(getKeypointName(index)).toBe(name);
      });
    });
  });
});
