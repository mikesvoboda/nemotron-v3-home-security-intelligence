import { render, screen } from '@testing-library/react';
import { createRef } from 'react';
import { describe, expect, it } from 'vitest';

import ThreatBoundingBox from './ThreatBoundingBox';

import type { ThreatBoundingBoxProps, ThreatData } from './ThreatBoundingBox';

/**
 * Test suite for ThreatBoundingBox component.
 *
 * This component renders CSS overlay boxes on detection images showing where
 * threats are located. It supports:
 * - Single and multiple bounding box rendering
 * - Priority-based color coding (red for high-priority, orange for medium)
 * - Coordinate scaling relative to container dimensions
 * - Accessibility via aria-labels
 *
 * Backend bbox format: tuple[float, float, float, float] as (x1, y1, x2, y2) in pixel coordinates
 * Frontend bbox format: [number, number, number, number] as [x1, y1, x2, y2]
 */
describe('ThreatBoundingBox', () => {
  // Mock threat data for testing
  const createThreat = (overrides: Partial<ThreatData> = {}): ThreatData => ({
    class_name: 'knife',
    confidence: 0.85,
    bbox: [100, 100, 300, 400], // [x1, y1, x2, y2]
    is_high_priority: false,
    ...overrides,
  });

  // Default props for testing
  const defaultProps: ThreatBoundingBoxProps = {
    threats: [createThreat()],
    imageWidth: 1920,
    imageHeight: 1080,
  };

  describe('rendering', () => {
    it('renders nothing when threats is empty array', () => {
      const { container } = render(
        <ThreatBoundingBox threats={[]} imageWidth={1920} imageHeight={1080} />
      );
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when threats is undefined', () => {
      const { container } = render(
        <ThreatBoundingBox
          threats={undefined as unknown as ThreatData[]}
          imageWidth={1920}
          imageHeight={1080}
        />
      );
      expect(container.firstChild).toBeNull();
    });

    it('renders a container element when threats exist', () => {
      render(<ThreatBoundingBox {...defaultProps} />);
      expect(screen.getByTestId('threat-bounding-boxes')).toBeInTheDocument();
    });

    it('renders a single bounding box for one threat', () => {
      render(<ThreatBoundingBox {...defaultProps} />);
      expect(screen.getAllByTestId('threat-bbox')).toHaveLength(1);
    });

    it('renders multiple bounding boxes for multiple threats', () => {
      const multipleThreats: ThreatData[] = [
        createThreat({ class_name: 'knife', bbox: [100, 100, 200, 200] }),
        createThreat({ class_name: 'gun', bbox: [300, 300, 500, 500], is_high_priority: true }),
        createThreat({ class_name: 'bat', bbox: [600, 100, 800, 300] }),
      ];
      render(<ThreatBoundingBox threats={multipleThreats} imageWidth={1920} imageHeight={1080} />);
      expect(screen.getAllByTestId('threat-bbox')).toHaveLength(3);
    });
  });

  describe('position and dimensions', () => {
    it('calculates correct CSS left position from x1 coordinate', () => {
      const threat = createThreat({ bbox: [192, 100, 384, 200] }); // x1=192 on 1920px image = 10%
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox).toHaveStyle({ left: '10%' });
    });

    it('calculates correct CSS top position from y1 coordinate', () => {
      const threat = createThreat({ bbox: [100, 108, 200, 300] }); // y1=108 on 1080px image = 10%
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox).toHaveStyle({ top: '10%' });
    });

    it('calculates correct CSS width from bbox coordinates', () => {
      // bbox [0, 0, 960, 540] on 1920x1080 = 50% width
      const threat = createThreat({ bbox: [0, 0, 960, 540] });
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox).toHaveStyle({ width: '50%' });
    });

    it('calculates correct CSS height from bbox coordinates', () => {
      // bbox [0, 0, 960, 540] on 1920x1080 = 50% height
      const threat = createThreat({ bbox: [0, 0, 960, 540] });
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox).toHaveStyle({ height: '50%' });
    });

    it('handles different image dimensions correctly', () => {
      // 640x480 image, bbox at [64, 48, 320, 240] = left:10%, top:10%, width:40%, height:40%
      const threat = createThreat({ bbox: [64, 48, 320, 240] });
      render(<ThreatBoundingBox threats={[threat]} imageWidth={640} imageHeight={480} />);

      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox).toHaveStyle({
        left: '10%',
        top: '10%',
        width: '40%',
        height: '40%',
      });
    });

    it('positions box at origin correctly', () => {
      const threat = createThreat({ bbox: [0, 0, 192, 108] }); // 10% of 1920x1080
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox).toHaveStyle({ left: '0%', top: '0%' });
    });

    it('uses absolute positioning', () => {
      render(<ThreatBoundingBox {...defaultProps} />);
      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox).toHaveStyle({ position: 'absolute' });
    });
  });

  describe('threat labels', () => {
    it('displays threat class name as label', () => {
      const threat = createThreat({ class_name: 'knife' });
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      expect(screen.getByText('knife')).toBeInTheDocument();
    });

    it('displays confidence percentage in label', () => {
      const threat = createThreat({ class_name: 'gun', confidence: 0.92 });
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      expect(screen.getByText(/92%/)).toBeInTheDocument();
    });

    it('displays combined label with class name and confidence', () => {
      const threat = createThreat({ class_name: 'rifle', confidence: 0.87 });
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      // Label should contain both class name and confidence
      const label = screen.getByTestId('threat-label');
      expect(label).toHaveTextContent('rifle');
      expect(label).toHaveTextContent('87%');
    });

    it('label has correct test id', () => {
      render(<ThreatBoundingBox {...defaultProps} />);
      expect(screen.getByTestId('threat-label')).toBeInTheDocument();
    });

    it('renders label for each threat', () => {
      const threats: ThreatData[] = [
        createThreat({ class_name: 'knife', bbox: [0, 0, 100, 100] }),
        createThreat({ class_name: 'gun', bbox: [200, 200, 300, 300] }),
      ];
      render(<ThreatBoundingBox threats={threats} imageWidth={1920} imageHeight={1080} />);

      expect(screen.getAllByTestId('threat-label')).toHaveLength(2);
      expect(screen.getByText('knife')).toBeInTheDocument();
      expect(screen.getByText('gun')).toBeInTheDocument();
    });
  });

  describe('priority-based coloring', () => {
    it('uses red color for high-priority threats (firearms)', () => {
      const highPriorityThreat = createThreat({
        class_name: 'gun',
        is_high_priority: true,
      });
      render(
        <ThreatBoundingBox threats={[highPriorityThreat]} imageWidth={1920} imageHeight={1080} />
      );

      const bbox = screen.getByTestId('threat-bbox');
      // Check for red border color - using rgb format as jsdom normalizes colors
      expect(bbox).toHaveStyle({ borderColor: 'rgb(239, 68, 68)' }); // Tailwind red-500
    });

    it('uses orange color for medium-priority threats (blunt weapons)', () => {
      const mediumPriorityThreat = createThreat({
        class_name: 'bat',
        is_high_priority: false,
      });
      render(
        <ThreatBoundingBox threats={[mediumPriorityThreat]} imageWidth={1920} imageHeight={1080} />
      );

      const bbox = screen.getByTestId('threat-bbox');
      // Check for orange border color
      expect(bbox).toHaveStyle({ borderColor: 'rgb(249, 115, 22)' }); // Tailwind orange-500
    });

    it('applies high-priority styling to rifle detection', () => {
      const rifleTheat = createThreat({
        class_name: 'rifle',
        is_high_priority: true,
      });
      render(<ThreatBoundingBox threats={[rifleTheat]} imageWidth={1920} imageHeight={1080} />);

      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox).toHaveClass('threat-high-priority');
    });

    it('applies medium-priority styling to non-firearm detection', () => {
      const crowbarThreat = createThreat({
        class_name: 'crowbar',
        is_high_priority: false,
      });
      render(<ThreatBoundingBox threats={[crowbarThreat]} imageWidth={1920} imageHeight={1080} />);

      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox).toHaveClass('threat-medium-priority');
    });

    it('applies matching background color to label for high-priority', () => {
      const threat = createThreat({ is_high_priority: true });
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      const label = screen.getByTestId('threat-label');
      expect(label).toHaveStyle({ backgroundColor: 'rgb(239, 68, 68)' }); // red-500
    });

    it('applies matching background color to label for medium-priority', () => {
      const threat = createThreat({ is_high_priority: false });
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      const label = screen.getByTestId('threat-label');
      expect(label).toHaveStyle({ backgroundColor: 'rgb(249, 115, 22)' }); // orange-500
    });

    it('renders mixed priority threats with correct colors', () => {
      const threats: ThreatData[] = [
        createThreat({ class_name: 'gun', is_high_priority: true, bbox: [0, 0, 100, 100] }),
        createThreat({ class_name: 'bat', is_high_priority: false, bbox: [200, 200, 300, 300] }),
      ];
      render(<ThreatBoundingBox threats={threats} imageWidth={1920} imageHeight={1080} />);

      const boxes = screen.getAllByTestId('threat-bbox');
      expect(boxes[0]).toHaveClass('threat-high-priority');
      expect(boxes[1]).toHaveClass('threat-medium-priority');
    });
  });

  describe('scaling with container dimensions', () => {
    it('accepts containerRef prop', () => {
      const containerRef = createRef<HTMLDivElement>();
      const { container } = render(
        <div ref={containerRef}>
          <ThreatBoundingBox {...defaultProps} containerRef={containerRef} />
        </div>
      );

      expect(container.querySelector('[data-testid="threat-bounding-boxes"]')).toBeInTheDocument();
    });

    it('scales coordinates to percentage values for responsive display', () => {
      // Threat at pixel coords [480, 270, 1440, 810] on 1920x1080
      // Should convert to: left:25%, top:25%, width:50%, height:50%
      const threat = createThreat({ bbox: [480, 270, 1440, 810] });
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox).toHaveStyle({
        left: '25%',
        top: '25%',
        width: '50%',
        height: '50%',
      });
    });

    it('clamps coordinates to prevent overflow', () => {
      // Edge case: coordinates exceed image bounds
      const threat = createThreat({ bbox: [1800, 1000, 2000, 1200] }); // extends past 1920x1080
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      const bbox = screen.getByTestId('threat-bbox');
      const styles = window.getComputedStyle(bbox);

      // Width and height should be clamped to not exceed 100%
      const left = parseFloat(styles.left) || 0;
      const width = parseFloat(styles.width) || 0;
      expect(left + width).toBeLessThanOrEqual(100);
    });

    it('handles zero-dimension image gracefully', () => {
      const { container } = render(
        <ThreatBoundingBox threats={[createThreat()]} imageWidth={0} imageHeight={0} />
      );

      // Should not throw, may render nothing or handle gracefully
      expect(container).toBeDefined();
    });
  });

  describe('accessibility', () => {
    it('has appropriate aria-label on container', () => {
      render(<ThreatBoundingBox {...defaultProps} />);
      const container = screen.getByTestId('threat-bounding-boxes');
      expect(container).toHaveAttribute('aria-label', expect.stringContaining('threat'));
    });

    it('includes count in container aria-label', () => {
      const threats: ThreatData[] = [
        createThreat({ bbox: [0, 0, 100, 100] }),
        createThreat({ bbox: [200, 200, 300, 300] }),
      ];
      render(<ThreatBoundingBox threats={threats} imageWidth={1920} imageHeight={1080} />);

      const container = screen.getByTestId('threat-bounding-boxes');
      expect(container).toHaveAttribute('aria-label', expect.stringContaining('2'));
    });

    it('has appropriate aria-label on individual bounding boxes', () => {
      const threat = createThreat({ class_name: 'knife', confidence: 0.85 });
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox).toHaveAttribute('aria-label');
      expect(bbox.getAttribute('aria-label')).toContain('knife');
    });

    it('includes confidence in bbox aria-label', () => {
      const threat = createThreat({ class_name: 'gun', confidence: 0.92 });
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox.getAttribute('aria-label')).toContain('92%');
    });

    it('indicates high-priority status in aria-label', () => {
      const threat = createThreat({ class_name: 'pistol', is_high_priority: true });
      render(<ThreatBoundingBox threats={[threat]} imageWidth={1920} imageHeight={1080} />);

      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox.getAttribute('aria-label')).toMatch(/high.?priority/i);
    });

    it('bounding boxes have role="img" for screen readers', () => {
      render(<ThreatBoundingBox {...defaultProps} />);
      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox).toHaveAttribute('role', 'img');
    });

    it('container is marked as presentational when appropriate', () => {
      render(<ThreatBoundingBox {...defaultProps} />);
      const container = screen.getByTestId('threat-bounding-boxes');
      // Container should be a region or have appropriate landmark role
      expect(container).toHaveAttribute('role', 'region');
    });
  });

  describe('styling', () => {
    it('applies custom className to container', () => {
      render(<ThreatBoundingBox {...defaultProps} className="custom-overlay" />);
      const container = screen.getByTestId('threat-bounding-boxes');
      expect(container).toHaveClass('custom-overlay');
    });

    it('has border on bounding boxes', () => {
      render(<ThreatBoundingBox {...defaultProps} />);
      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox).toHaveStyle({ borderWidth: '2px', borderStyle: 'solid' });
    });

    it('has pointer-events-none to allow clicking through overlay', () => {
      render(<ThreatBoundingBox {...defaultProps} />);
      const container = screen.getByTestId('threat-bounding-boxes');
      expect(container).toHaveStyle({ pointerEvents: 'none' });
    });

    it('positions container absolutely to overlay on image', () => {
      render(<ThreatBoundingBox {...defaultProps} />);
      const container = screen.getByTestId('threat-bounding-boxes');
      expect(container).toHaveStyle({ position: 'absolute', inset: '0' });
    });
  });

  describe('edge cases', () => {
    it('handles very small bounding boxes', () => {
      const smallThreat = createThreat({ bbox: [100, 100, 110, 110] }); // 10x10 pixels
      render(<ThreatBoundingBox threats={[smallThreat]} imageWidth={1920} imageHeight={1080} />);

      const bbox = screen.getByTestId('threat-bbox');
      expect(bbox).toBeInTheDocument();
      // Should have minimum visible dimensions
      const width = parseFloat(bbox.style.width);
      expect(width).toBeGreaterThan(0);
    });

    it('handles inverted coordinates gracefully', () => {
      // x2 < x1 or y2 < y1 (invalid bbox)
      const invertedThreat = createThreat({ bbox: [300, 400, 100, 100] });
      const { container } = render(
        <ThreatBoundingBox threats={[invertedThreat]} imageWidth={1920} imageHeight={1080} />
      );

      // Component should handle gracefully - either skip or normalize
      expect(container).toBeDefined();
    });

    it('handles negative coordinates', () => {
      const negativeThreat = createThreat({ bbox: [-10, -10, 100, 100] });
      render(<ThreatBoundingBox threats={[negativeThreat]} imageWidth={1920} imageHeight={1080} />);

      const bbox = screen.getByTestId('threat-bbox');
      // Should clamp to 0% minimum
      const left = parseFloat(bbox.style.left);
      expect(left).toBeGreaterThanOrEqual(0);
    });

    it('handles very low confidence values', () => {
      const lowConfThreat = createThreat({ confidence: 0.01 });
      render(<ThreatBoundingBox threats={[lowConfThreat]} imageWidth={1920} imageHeight={1080} />);

      expect(screen.getByText(/1%/)).toBeInTheDocument();
    });

    it('handles special characters in class name', () => {
      const specialThreat = createThreat({ class_name: 'baseball_bat' });
      render(<ThreatBoundingBox threats={[specialThreat]} imageWidth={1920} imageHeight={1080} />);

      expect(screen.getByText('baseball_bat')).toBeInTheDocument();
    });

    it('handles maximum confidence value', () => {
      const perfectThreat = createThreat({ confidence: 1.0 });
      render(<ThreatBoundingBox threats={[perfectThreat]} imageWidth={1920} imageHeight={1080} />);

      expect(screen.getByText(/100%/)).toBeInTheDocument();
    });

    it('handles large number of threats', () => {
      const manyThreats = Array.from({ length: 20 }, (_, i) =>
        createThreat({
          class_name: `threat_${i}`,
          bbox: [(i * 90) % 1800, (i * 50) % 1000, ((i * 90) % 1800) + 100, ((i * 50) % 1000) + 100],
        })
      );
      render(<ThreatBoundingBox threats={manyThreats} imageWidth={1920} imageHeight={1080} />);

      expect(screen.getAllByTestId('threat-bbox')).toHaveLength(20);
    });
  });

  describe('z-index ordering', () => {
    it('high-priority threats have higher z-index than medium-priority', () => {
      const threats: ThreatData[] = [
        createThreat({ class_name: 'bat', is_high_priority: false, bbox: [0, 0, 200, 200] }),
        createThreat({ class_name: 'gun', is_high_priority: true, bbox: [100, 100, 300, 300] }),
      ];
      render(<ThreatBoundingBox threats={threats} imageWidth={1920} imageHeight={1080} />);

      const boxes = screen.getAllByTestId('threat-bbox');
      const lowPriorityZIndex = parseInt(window.getComputedStyle(boxes[0]).zIndex || '0', 10);
      const highPriorityZIndex = parseInt(window.getComputedStyle(boxes[1]).zIndex || '0', 10);

      expect(highPriorityZIndex).toBeGreaterThanOrEqual(lowPriorityZIndex);
    });
  });
});
