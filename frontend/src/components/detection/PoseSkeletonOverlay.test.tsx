import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import PoseSkeletonOverlay, {
  arePropsEqual,
  BODY_PART_COLORS,
  COCO_KEYPOINT_NAMES,
  getBodyPart,
  getConnectionColor,
  getKeypointColor,
  Keypoint,
  PoseSkeletonOverlayProps,
  SKELETON_CONNECTIONS,
} from './PoseSkeletonOverlay';

describe('PoseSkeletonOverlay', () => {
  // Sample keypoints in COCO 17-keypoint format
  // All keypoints with high confidence for basic tests
  const mockKeypoints: Keypoint[] = [
    [100, 50, 0.95], // 0: nose
    [90, 45, 0.9], // 1: left_eye
    [110, 45, 0.9], // 2: right_eye
    [80, 50, 0.85], // 3: left_ear
    [120, 50, 0.85], // 4: right_ear
    [70, 100, 0.92], // 5: left_shoulder
    [130, 100, 0.92], // 6: right_shoulder
    [60, 150, 0.88], // 7: left_elbow
    [140, 150, 0.88], // 8: right_elbow
    [50, 200, 0.82], // 9: left_wrist
    [150, 200, 0.82], // 10: right_wrist
    [80, 180, 0.9], // 11: left_hip
    [120, 180, 0.9], // 12: right_hip
    [75, 250, 0.85], // 13: left_knee
    [125, 250, 0.85], // 14: right_knee
    [70, 320, 0.8], // 15: left_ankle
    [130, 320, 0.8], // 16: right_ankle
  ];

  describe('rendering', () => {
    it('renders without crashing', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      expect(container.querySelector('svg')).toBeInTheDocument();
    });

    it('renders SVG with correct viewBox', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={640} imageHeight={480} />
      );
      const svg = container.querySelector('svg');
      expect(svg?.getAttribute('viewBox')).toBe('0 0 640 480');
    });

    it('renders with data-testid for the overlay', () => {
      const { getByTestId } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      expect(getByTestId('pose-skeleton-overlay')).toBeInTheDocument();
    });

    it('renders keypoints as circles', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      const circles = container.querySelectorAll('circle');
      expect(circles.length).toBe(17); // All 17 COCO keypoints
    });

    it('renders connections as lines', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      const lines = container.querySelectorAll('line');
      expect(lines.length).toBe(SKELETON_CONNECTIONS.length);
    });

    it('renders keypoints with correct positions', () => {
      const { getByTestId } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      const noseKeypoint = getByTestId('pose-keypoint-0');
      expect(noseKeypoint.getAttribute('cx')).toBe('100');
      expect(noseKeypoint.getAttribute('cy')).toBe('50');
    });

    it('renders connections with correct endpoints', () => {
      const { getByTestId } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      // Check nose-to-left_eye connection
      const connection = getByTestId('pose-connection-0-1');
      expect(connection.getAttribute('x1')).toBe('100'); // nose x
      expect(connection.getAttribute('y1')).toBe('50'); // nose y
      expect(connection.getAttribute('x2')).toBe('90'); // left_eye x
      expect(connection.getAttribute('y2')).toBe('45'); // left_eye y
    });
  });

  describe('visibility control', () => {
    it('returns null when visible is false', () => {
      const { container } = render(
        <PoseSkeletonOverlay
          keypoints={mockKeypoints}
          imageWidth={400}
          imageHeight={400}
          visible={false}
        />
      );
      expect(container.querySelector('svg')).not.toBeInTheDocument();
    });

    it('returns null when keypoints is null', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={null} imageWidth={400} imageHeight={400} />
      );
      expect(container.querySelector('svg')).not.toBeInTheDocument();
    });

    it('returns null when keypoints is undefined', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={undefined} imageWidth={400} imageHeight={400} />
      );
      expect(container.querySelector('svg')).not.toBeInTheDocument();
    });

    it('returns null when keypoints array is empty', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={[]} imageWidth={400} imageHeight={400} />
      );
      expect(container.querySelector('svg')).not.toBeInTheDocument();
    });

    it('returns null when imageWidth is 0', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={0} imageHeight={400} />
      );
      expect(container.querySelector('svg')).not.toBeInTheDocument();
    });

    it('returns null when imageHeight is 0', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={0} />
      );
      expect(container.querySelector('svg')).not.toBeInTheDocument();
    });

    it('returns null when imageWidth is negative', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={-100} imageHeight={400} />
      );
      expect(container.querySelector('svg')).not.toBeInTheDocument();
    });

    it('returns null when all keypoints below minConfidence', () => {
      const lowConfidenceKeypoints: Keypoint[] = mockKeypoints.map(([x, y]) => [x, y, 0.1]);
      const { container } = render(
        <PoseSkeletonOverlay
          keypoints={lowConfidenceKeypoints}
          imageWidth={400}
          imageHeight={400}
          minConfidence={0.5}
        />
      );
      expect(container.querySelector('svg')).not.toBeInTheDocument();
    });
  });

  describe('confidence filtering', () => {
    it('filters keypoints below minConfidence threshold', () => {
      const mixedConfidenceKeypoints: Keypoint[] = [
        [100, 50, 0.95], // 0: nose - above threshold
        [90, 45, 0.2], // 1: left_eye - below threshold
        [110, 45, 0.2], // 2: right_eye - below threshold
        [80, 50, 0.2], // 3: left_ear - below threshold
        [120, 50, 0.2], // 4: right_ear - below threshold
        [70, 100, 0.92], // 5: left_shoulder - above threshold
        [130, 100, 0.92], // 6: right_shoulder - above threshold
        [60, 150, 0.2], // 7: left_elbow - below
        [140, 150, 0.2], // 8: right_elbow - below
        [50, 200, 0.2], // 9: left_wrist - below
        [150, 200, 0.2], // 10: right_wrist - below
        [80, 180, 0.9], // 11: left_hip - above
        [120, 180, 0.9], // 12: right_hip - above
        [75, 250, 0.2], // 13: left_knee - below
        [125, 250, 0.2], // 14: right_knee - below
        [70, 320, 0.2], // 15: left_ankle - below
        [130, 320, 0.2], // 16: right_ankle - below
      ];

      const { container } = render(
        <PoseSkeletonOverlay
          keypoints={mixedConfidenceKeypoints}
          imageWidth={400}
          imageHeight={400}
          minConfidence={0.5}
        />
      );

      // Should only render keypoints above 0.5 confidence
      // nose, left_shoulder, right_shoulder, left_hip, right_hip = 5 keypoints
      const circles = container.querySelectorAll('circle');
      expect(circles.length).toBe(5);
    });

    it('uses default minConfidence of 0.3', () => {
      const lowConfidenceKeypoints: Keypoint[] = mockKeypoints.map(([x, y]) => [x, y, 0.25]);
      const { container } = render(
        <PoseSkeletonOverlay
          keypoints={lowConfidenceKeypoints}
          imageWidth={400}
          imageHeight={400}
        />
      );
      // All keypoints at 0.25 should be filtered out by default 0.3 threshold
      expect(container.querySelector('svg')).not.toBeInTheDocument();
    });

    it('shows all keypoints when minConfidence is 0', () => {
      const lowConfidenceKeypoints: Keypoint[] = mockKeypoints.map(([x, y]) => [x, y, 0.1]);
      const { container } = render(
        <PoseSkeletonOverlay
          keypoints={lowConfidenceKeypoints}
          imageWidth={400}
          imageHeight={400}
          minConfidence={0}
        />
      );
      const circles = container.querySelectorAll('circle');
      expect(circles.length).toBe(17);
    });

    it('applies confidence as opacity to keypoints', () => {
      const { getByTestId } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      const noseKeypoint = getByTestId('pose-keypoint-0');
      expect(noseKeypoint.getAttribute('opacity')).toBe('0.95');
    });

    it('applies minimum confidence as opacity to connections', () => {
      const { getByTestId } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      // Connection between nose (0.95) and left_eye (0.9) should have opacity 0.9
      const connection = getByTestId('pose-connection-0-1');
      expect(connection.getAttribute('opacity')).toBe('0.9');
    });
  });

  describe('display options', () => {
    it('hides keypoints when showKeypoints is false', () => {
      const { container } = render(
        <PoseSkeletonOverlay
          keypoints={mockKeypoints}
          imageWidth={400}
          imageHeight={400}
          showKeypoints={false}
        />
      );
      const circles = container.querySelectorAll('circle');
      expect(circles.length).toBe(0);
    });

    it('still shows connections when showKeypoints is false', () => {
      const { container } = render(
        <PoseSkeletonOverlay
          keypoints={mockKeypoints}
          imageWidth={400}
          imageHeight={400}
          showKeypoints={false}
        />
      );
      const lines = container.querySelectorAll('line');
      expect(lines.length).toBe(SKELETON_CONNECTIONS.length);
    });

    it('hides connections when showConnections is false', () => {
      const { container } = render(
        <PoseSkeletonOverlay
          keypoints={mockKeypoints}
          imageWidth={400}
          imageHeight={400}
          showConnections={false}
        />
      );
      const lines = container.querySelectorAll('line');
      expect(lines.length).toBe(0);
    });

    it('still shows keypoints when showConnections is false', () => {
      const { container } = render(
        <PoseSkeletonOverlay
          keypoints={mockKeypoints}
          imageWidth={400}
          imageHeight={400}
          showConnections={false}
        />
      );
      const circles = container.querySelectorAll('circle');
      expect(circles.length).toBe(17);
    });

    it('applies custom keypointRadius', () => {
      const { getByTestId } = render(
        <PoseSkeletonOverlay
          keypoints={mockKeypoints}
          imageWidth={400}
          imageHeight={400}
          keypointRadius={8}
        />
      );
      const noseKeypoint = getByTestId('pose-keypoint-0');
      expect(noseKeypoint.getAttribute('r')).toBe('8');
    });

    it('applies default keypointRadius of 4', () => {
      const { getByTestId } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      const noseKeypoint = getByTestId('pose-keypoint-0');
      expect(noseKeypoint.getAttribute('r')).toBe('4');
    });

    it('applies custom lineWidth', () => {
      const { getByTestId } = render(
        <PoseSkeletonOverlay
          keypoints={mockKeypoints}
          imageWidth={400}
          imageHeight={400}
          lineWidth={4}
        />
      );
      const connection = getByTestId('pose-connection-0-1');
      expect(connection.getAttribute('stroke-width')).toBe('4');
    });

    it('applies default lineWidth of 2', () => {
      const { getByTestId } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      const connection = getByTestId('pose-connection-0-1');
      expect(connection.getAttribute('stroke-width')).toBe('2');
    });
  });

  describe('color coding', () => {
    it('applies body part colors to keypoints', () => {
      const { getByTestId } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );

      // Head keypoints should be green
      const noseKeypoint = getByTestId('pose-keypoint-0');
      expect(noseKeypoint.getAttribute('fill')).toBe(BODY_PART_COLORS.head);

      // Left arm keypoints should be blue
      const leftElbow = getByTestId('pose-keypoint-7');
      expect(leftElbow.getAttribute('fill')).toBe(BODY_PART_COLORS.left_arm);

      // Right leg keypoints should be orange
      const rightAnkle = getByTestId('pose-keypoint-16');
      expect(rightAnkle.getAttribute('fill')).toBe(BODY_PART_COLORS.right_leg);
    });

    it('applies white stroke to keypoints', () => {
      const { getByTestId } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      const noseKeypoint = getByTestId('pose-keypoint-0');
      expect(noseKeypoint.getAttribute('stroke')).toBe('#ffffff');
      expect(noseKeypoint.getAttribute('stroke-width')).toBe('1');
    });

    it('applies body part colors to connections', () => {
      const { getByTestId } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );

      // Left arm connection should be blue
      const leftArmConnection = getByTestId('pose-connection-7-9'); // left_elbow to left_wrist
      expect(leftArmConnection.getAttribute('stroke')).toBe(BODY_PART_COLORS.left_arm);
    });

    it('applies round line caps to connections', () => {
      const { getByTestId } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      const connection = getByTestId('pose-connection-0-1');
      expect(connection.getAttribute('stroke-linecap')).toBe('round');
    });
  });

  describe('SVG styling', () => {
    it('has correct z-index', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      const svg = container.querySelector('svg');
      expect(svg?.style.zIndex).toBe('20');
    });

    it('has pointer-events-none class', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      const svg = container.querySelector('svg');
      expect(svg?.classList.contains('pointer-events-none')).toBe(true);
    });

    it('has absolute positioning classes', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      const svg = container.querySelector('svg');
      expect(svg?.classList.contains('absolute')).toBe(true);
      expect(svg?.classList.contains('inset-0')).toBe(true);
    });

    it('has responsive size classes', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      const svg = container.querySelector('svg');
      expect(svg?.classList.contains('w-full')).toBe(true);
      expect(svg?.classList.contains('h-full')).toBe(true);
    });

    it('has preserveAspectRatio set to none', () => {
      const { container } = render(
        <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
      );
      const svg = container.querySelector('svg');
      expect(svg?.getAttribute('preserveAspectRatio')).toBe('none');
    });
  });

  describe('connection filtering', () => {
    it('does not render connections where one endpoint is below confidence', () => {
      const partialKeypoints: Keypoint[] = [
        [100, 50, 0.95], // 0: nose - above threshold
        [90, 45, 0.1], // 1: left_eye - below threshold
        [110, 45, 0.9], // 2: right_eye - above threshold
        [80, 50, 0.1], // 3: left_ear - below
        [120, 50, 0.1], // 4: right_ear - below
        [70, 100, 0.92], // 5: left_shoulder - above
        [130, 100, 0.92], // 6: right_shoulder - above
        [60, 150, 0.1], // 7: left_elbow - below
        [140, 150, 0.1], // 8: right_elbow - below
        [50, 200, 0.1], // 9: left_wrist - below
        [150, 200, 0.1], // 10: right_wrist - below
        [80, 180, 0.9], // 11: left_hip - above
        [120, 180, 0.9], // 12: right_hip - above
        [75, 250, 0.1], // 13: left_knee - below
        [125, 250, 0.1], // 14: right_knee - below
        [70, 320, 0.1], // 15: left_ankle - below
        [130, 320, 0.1], // 16: right_ankle - below
      ];

      const { container, queryByTestId } = render(
        <PoseSkeletonOverlay
          keypoints={partialKeypoints}
          imageWidth={400}
          imageHeight={400}
          minConfidence={0.5}
        />
      );

      // Connection from nose to left_eye should NOT exist (left_eye is below threshold)
      expect(queryByTestId('pose-connection-0-1')).not.toBeInTheDocument();

      // Connection from nose to right_eye SHOULD exist (both above threshold)
      expect(queryByTestId('pose-connection-0-2')).toBeInTheDocument();

      // Connection between shoulders SHOULD exist
      expect(queryByTestId('pose-connection-5-6')).toBeInTheDocument();

      // Count total lines - should be fewer than normal
      const lines = container.querySelectorAll('line');
      expect(lines.length).toBeLessThan(SKELETON_CONNECTIONS.length);
    });
  });
});

// =============================================================================
// Helper Function Tests
// =============================================================================

describe('helper functions', () => {
  describe('getBodyPart', () => {
    it('returns head for nose', () => {
      expect(getBodyPart(0)).toBe('head');
    });

    it('returns head for eyes', () => {
      expect(getBodyPart(1)).toBe('head');
      expect(getBodyPart(2)).toBe('head');
    });

    it('returns head for ears', () => {
      expect(getBodyPart(3)).toBe('head');
      expect(getBodyPart(4)).toBe('head');
    });

    it('returns torso for shoulders', () => {
      expect(getBodyPart(5)).toBe('torso');
      expect(getBodyPart(6)).toBe('torso');
    });

    it('returns torso for hips', () => {
      expect(getBodyPart(11)).toBe('torso');
      expect(getBodyPart(12)).toBe('torso');
    });

    it('returns left_arm for left arm parts', () => {
      expect(getBodyPart(7)).toBe('left_arm');
      expect(getBodyPart(9)).toBe('left_arm');
    });

    it('returns right_arm for right arm parts', () => {
      expect(getBodyPart(8)).toBe('right_arm');
      expect(getBodyPart(10)).toBe('right_arm');
    });

    it('returns left_leg for left leg parts', () => {
      expect(getBodyPart(13)).toBe('left_leg');
      expect(getBodyPart(15)).toBe('left_leg');
    });

    it('returns right_leg for right leg parts', () => {
      expect(getBodyPart(14)).toBe('right_leg');
      expect(getBodyPart(16)).toBe('right_leg');
    });

    it('returns torso for unknown keypoint index', () => {
      expect(getBodyPart(99)).toBe('torso');
    });
  });

  describe('getKeypointColor', () => {
    it('returns green for head keypoints', () => {
      expect(getKeypointColor(0)).toBe(BODY_PART_COLORS.head);
      expect(getKeypointColor(1)).toBe(BODY_PART_COLORS.head);
    });

    it('returns yellow for torso keypoints', () => {
      expect(getKeypointColor(5)).toBe(BODY_PART_COLORS.torso);
      expect(getKeypointColor(11)).toBe(BODY_PART_COLORS.torso);
    });

    it('returns blue for left arm keypoints', () => {
      expect(getKeypointColor(7)).toBe(BODY_PART_COLORS.left_arm);
    });

    it('returns purple for right arm keypoints', () => {
      expect(getKeypointColor(8)).toBe(BODY_PART_COLORS.right_arm);
    });

    it('returns red for left leg keypoints', () => {
      expect(getKeypointColor(13)).toBe(BODY_PART_COLORS.left_leg);
    });

    it('returns orange for right leg keypoints', () => {
      expect(getKeypointColor(14)).toBe(BODY_PART_COLORS.right_leg);
    });
  });

  describe('getConnectionColor', () => {
    it('returns body part color for same-body-part connections', () => {
      // Left arm connection (elbow to wrist)
      expect(getConnectionColor(7, 9)).toBe(BODY_PART_COLORS.left_arm);
    });

    it('returns non-torso color for torso-to-limb connections', () => {
      // Shoulder (torso) to elbow (arm) should use arm color
      expect(getConnectionColor(5, 7)).toBe(BODY_PART_COLORS.left_arm);
      expect(getConnectionColor(6, 8)).toBe(BODY_PART_COLORS.right_arm);
    });

    it('returns limb color for hip-to-leg connections', () => {
      // Hip (torso) to knee (leg) should use leg color
      expect(getConnectionColor(11, 13)).toBe(BODY_PART_COLORS.left_leg);
      expect(getConnectionColor(12, 14)).toBe(BODY_PART_COLORS.right_leg);
    });
  });
});

// =============================================================================
// Constants Tests
// =============================================================================

describe('constants', () => {
  describe('COCO_KEYPOINT_NAMES', () => {
    it('has 17 keypoints', () => {
      expect(COCO_KEYPOINT_NAMES.length).toBe(17);
    });

    it('has correct keypoint at index 0', () => {
      expect(COCO_KEYPOINT_NAMES[0]).toBe('nose');
    });

    it('has correct keypoint at last index', () => {
      expect(COCO_KEYPOINT_NAMES[16]).toBe('right_ankle');
    });
  });

  describe('SKELETON_CONNECTIONS', () => {
    it('has expected number of connections', () => {
      // 16 connections for standard COCO skeleton
      expect(SKELETON_CONNECTIONS.length).toBe(16);
    });

    it('all connections reference valid keypoint indices', () => {
      for (const [from, to] of SKELETON_CONNECTIONS) {
        expect(from).toBeGreaterThanOrEqual(0);
        expect(from).toBeLessThan(17);
        expect(to).toBeGreaterThanOrEqual(0);
        expect(to).toBeLessThan(17);
      }
    });
  });

  describe('BODY_PART_COLORS', () => {
    it('has colors for all body parts', () => {
      expect(BODY_PART_COLORS.head).toBeDefined();
      expect(BODY_PART_COLORS.torso).toBeDefined();
      expect(BODY_PART_COLORS.left_arm).toBeDefined();
      expect(BODY_PART_COLORS.right_arm).toBeDefined();
      expect(BODY_PART_COLORS.left_leg).toBeDefined();
      expect(BODY_PART_COLORS.right_leg).toBeDefined();
    });

    it('colors are valid hex values', () => {
      const hexPattern = /^#[0-9a-fA-F]{6}$/;
      Object.values(BODY_PART_COLORS).forEach((color) => {
        expect(color).toMatch(hexPattern);
      });
    });
  });
});

// =============================================================================
// React.memo Optimization Tests
// =============================================================================

describe('arePropsEqual - React.memo custom comparator', () => {
  const baseKeypoints: Keypoint[] = [
    [100, 50, 0.95],
    [90, 45, 0.9],
  ];

  const baseProps: PoseSkeletonOverlayProps = {
    keypoints: baseKeypoints,
    imageWidth: 400,
    imageHeight: 400,
    minConfidence: 0.3,
    visible: true,
    showKeypoints: true,
    showConnections: true,
    keypointRadius: 4,
    lineWidth: 2,
  };

  it('returns true when props are identical', () => {
    expect(arePropsEqual(baseProps, baseProps)).toBe(true);
  });

  it('returns true when keypoints array has same content', () => {
    const prevProps = { ...baseProps, keypoints: [[100, 50, 0.95], [90, 45, 0.9]] as Keypoint[] };
    const nextProps = { ...baseProps, keypoints: [[100, 50, 0.95], [90, 45, 0.9]] as Keypoint[] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(true);
  });

  it('returns false when keypoints array length changes', () => {
    const prevProps = { ...baseProps, keypoints: baseKeypoints };
    const nextProps = { ...baseProps, keypoints: [...baseKeypoints, [110, 45, 0.9] as Keypoint] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when keypoint x changes', () => {
    const prevProps = { ...baseProps, keypoints: [[100, 50, 0.95]] as Keypoint[] };
    const nextProps = { ...baseProps, keypoints: [[110, 50, 0.95]] as Keypoint[] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when keypoint y changes', () => {
    const prevProps = { ...baseProps, keypoints: [[100, 50, 0.95]] as Keypoint[] };
    const nextProps = { ...baseProps, keypoints: [[100, 60, 0.95]] as Keypoint[] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when keypoint confidence changes', () => {
    const prevProps = { ...baseProps, keypoints: [[100, 50, 0.95]] as Keypoint[] };
    const nextProps = { ...baseProps, keypoints: [[100, 50, 0.8]] as Keypoint[] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when imageWidth changes', () => {
    const prevProps = { ...baseProps };
    const nextProps = { ...baseProps, imageWidth: 800 };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when imageHeight changes', () => {
    const prevProps = { ...baseProps };
    const nextProps = { ...baseProps, imageHeight: 600 };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when minConfidence changes', () => {
    const prevProps = { ...baseProps };
    const nextProps = { ...baseProps, minConfidence: 0.5 };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when visible changes', () => {
    const prevProps = { ...baseProps };
    const nextProps = { ...baseProps, visible: false };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when showKeypoints changes', () => {
    const prevProps = { ...baseProps };
    const nextProps = { ...baseProps, showKeypoints: false };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when showConnections changes', () => {
    const prevProps = { ...baseProps };
    const nextProps = { ...baseProps, showConnections: false };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when keypointRadius changes', () => {
    const prevProps = { ...baseProps };
    const nextProps = { ...baseProps, keypointRadius: 8 };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when lineWidth changes', () => {
    const prevProps = { ...baseProps };
    const nextProps = { ...baseProps, lineWidth: 4 };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns true when both keypoints are null', () => {
    const prevProps = { ...baseProps, keypoints: null };
    const nextProps = { ...baseProps, keypoints: null };
    expect(arePropsEqual(prevProps, nextProps)).toBe(true);
  });

  it('returns false when one keypoints is null and other is not', () => {
    const prevProps = { ...baseProps, keypoints: null };
    const nextProps = { ...baseProps, keypoints: baseKeypoints };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('handles empty keypoints arrays', () => {
    const prevProps = { ...baseProps, keypoints: [] };
    const nextProps = { ...baseProps, keypoints: [] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(true);
  });
});

describe('PoseSkeletonOverlay memoization', () => {
  it('is wrapped with React.memo', () => {
    expect(PoseSkeletonOverlay).toHaveProperty('$$typeof');
    expect(PoseSkeletonOverlay).toHaveProperty('compare', arePropsEqual);
  });
});

// =============================================================================
// Snapshot Tests
// =============================================================================

describe('PoseSkeletonOverlay snapshots', () => {
  const mockKeypoints: Keypoint[] = [
    [100, 50, 0.95], // nose
    [90, 45, 0.9], // left_eye
    [110, 45, 0.9], // right_eye
    [80, 50, 0.85], // left_ear
    [120, 50, 0.85], // right_ear
    [70, 100, 0.92], // left_shoulder
    [130, 100, 0.92], // right_shoulder
    [60, 150, 0.88], // left_elbow
    [140, 150, 0.88], // right_elbow
    [50, 200, 0.82], // left_wrist
    [150, 200, 0.82], // right_wrist
    [80, 180, 0.9], // left_hip
    [120, 180, 0.9], // right_hip
    [75, 250, 0.85], // left_knee
    [125, 250, 0.85], // right_knee
    [70, 320, 0.8], // left_ankle
    [130, 320, 0.8], // right_ankle
  ];

  it('renders with default props', () => {
    const { container } = render(
      <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={400} imageHeight={400} />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it('renders with keypoints only (no connections)', () => {
    const { container } = render(
      <PoseSkeletonOverlay
        keypoints={mockKeypoints}
        imageWidth={400}
        imageHeight={400}
        showConnections={false}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it('renders with connections only (no keypoints)', () => {
    const { container } = render(
      <PoseSkeletonOverlay
        keypoints={mockKeypoints}
        imageWidth={400}
        imageHeight={400}
        showKeypoints={false}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it('renders with custom styling', () => {
    const { container } = render(
      <PoseSkeletonOverlay
        keypoints={mockKeypoints}
        imageWidth={400}
        imageHeight={400}
        keypointRadius={8}
        lineWidth={4}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it('renders with high confidence filter', () => {
    const { container } = render(
      <PoseSkeletonOverlay
        keypoints={mockKeypoints}
        imageWidth={400}
        imageHeight={400}
        minConfidence={0.9}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it('renders with different image dimensions', () => {
    const { container } = render(
      <PoseSkeletonOverlay keypoints={mockKeypoints} imageWidth={1920} imageHeight={1080} />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
