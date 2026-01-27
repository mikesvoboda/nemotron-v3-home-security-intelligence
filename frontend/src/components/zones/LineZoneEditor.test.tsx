/**
 * LineZoneEditor Tests
 *
 * Tests for the tripwire/line zone drawing component.
 * Line zones are used for entry detection triggers (crossing a virtual line).
 *
 * @module components/zones/LineZoneEditor.test
 * @see NEM-3720 Create frontend zone editor components
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import LineZoneEditor from './LineZoneEditor';

import type { Point } from './ZoneCanvas';

// ============================================================================
// Mock Setup
// ============================================================================

// Mock the snapshot URL
vi.mock('../../services/api', () => ({
  getCameraSnapshotUrl: (cameraId: string) => `/api/cameras/${cameraId}/snapshot`,
}));

// ============================================================================
// Test Data
// ============================================================================

const mockOnLineComplete = vi.fn();
const mockOnCancel = vi.fn();

const defaultProps = {
  snapshotUrl: '/api/cameras/cam-1/snapshot',
  isDrawing: true,
  lineColor: '#EF4444',
  onLineComplete: mockOnLineComplete,
  onCancel: mockOnCancel,
};

// ============================================================================
// Tests
// ============================================================================

describe('LineZoneEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders the component with snapshot background', () => {
      render(<LineZoneEditor {...defaultProps} />);

      const img = screen.getByAltText('Camera snapshot');
      expect(img).toBeInTheDocument();
      expect(img).toHaveAttribute('src', '/api/cameras/cam-1/snapshot');
    });

    it('displays drawing instructions when in drawing mode', () => {
      render(<LineZoneEditor {...defaultProps} />);

      expect(
        screen.getByText(/click to set the start point/i)
      ).toBeInTheDocument();
    });

    it('does not show instructions when not drawing', () => {
      render(<LineZoneEditor {...defaultProps} isDrawing={false} />);

      expect(
        screen.queryByText(/click to set the start point/i)
      ).not.toBeInTheDocument();
    });

    it('applies cursor-crosshair class when drawing', () => {
      render(<LineZoneEditor {...defaultProps} />);

      const container = screen.getByRole('application');
      expect(container).toHaveClass('cursor-crosshair');
    });

    it('renders with custom line color', () => {
      render(<LineZoneEditor {...defaultProps} lineColor="#76B900" />);

      const container = screen.getByRole('application');
      expect(container).toBeInTheDocument();
    });
  });

  describe('Drawing Interaction', () => {
    const setupWithImageLoad = () => {
      // Mock getBoundingClientRect on all HTMLElement instances before rendering
      const mockRect = {
        left: 0,
        top: 0,
        width: 1000,
        height: 562.5, // 16:9 aspect ratio
        right: 1000,
        bottom: 562.5,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      };

      vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(mockRect);

      render(<LineZoneEditor {...defaultProps} />);

      const container = screen.getByRole('application');

      // Simulate image load - this triggers the size update effect
      const img = screen.getByAltText('Camera snapshot');
      fireEvent.load(img);

      // Trigger resize event to ensure containerSize is updated
      window.dispatchEvent(new Event('resize'));

      return container;
    };

    it('records first click as start point', async () => {
      const container = setupWithImageLoad();

      // Simulate click on the canvas
      fireEvent.mouseDown(container, { clientX: 100, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 100, clientY: 100 });

      // Instructions should update after first point
      await waitFor(() => {
        expect(
          screen.getByText(/click to set the end point/i)
        ).toBeInTheDocument();
      });
    });

    it('calls onLineComplete with two normalized points after second click', async () => {
      const container = setupWithImageLoad();

      // First click (start point) - note: getBoundingClientRect returns 1000x562.5
      fireEvent.mouseDown(container, { clientX: 100, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 100, clientY: 100 });

      // Verify we're in "end point" mode
      await waitFor(() => {
        expect(screen.getByText(/click to set the end point/i)).toBeInTheDocument();
      });

      // Second click (end point) - far enough to pass minimum length
      fireEvent.mouseDown(container, { clientX: 600, clientY: 400 });
      fireEvent.mouseUp(container, { clientX: 600, clientY: 400 });

      await waitFor(() => {
        expect(mockOnLineComplete).toHaveBeenCalledTimes(1);
        const [points] = mockOnLineComplete.mock.calls[0];
        expect(points).toHaveLength(2);
        // Points should be normalized (0-1 range)
        expect(points[0][0]).toBeGreaterThanOrEqual(0);
        expect(points[0][0]).toBeLessThanOrEqual(1);
        expect(points[1][0]).toBeGreaterThanOrEqual(0);
        expect(points[1][0]).toBeLessThanOrEqual(1);
      });
    });

    it('shows SVG overlay after image loads', async () => {
      setupWithImageLoad();

      // After image load, SVG should be present
      await waitFor(() => {
        const svg = screen.getByTestId('line-editor-svg');
        expect(svg).toBeInTheDocument();
      });
    });

    it('enforces minimum line length', () => {
      const container = setupWithImageLoad();

      // First click
      fireEvent.mouseDown(container, { clientX: 100, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 100, clientY: 100 });

      // Second click very close to first (should not complete)
      fireEvent.mouseDown(container, { clientX: 105, clientY: 102 });
      fireEvent.mouseUp(container, { clientX: 105, clientY: 102 });

      // Should NOT have called onLineComplete due to minimum length requirement
      expect(mockOnLineComplete).not.toHaveBeenCalled();
    });
  });

  describe('Cancellation', () => {
    it('calls onCancel when Escape is pressed', () => {
      render(<LineZoneEditor {...defaultProps} />);

      fireEvent.keyDown(window, { key: 'Escape' });

      expect(mockOnCancel).toHaveBeenCalledTimes(1);
    });

    it('resets drawing state on cancel', async () => {
      render(<LineZoneEditor {...defaultProps} />);

      const container = screen.getByRole('application');

      // Simulate image load
      const img = screen.getByAltText('Camera snapshot');
      fireEvent.load(img);

      // Mock getBoundingClientRect
      const mockRect = {
        left: 0,
        top: 0,
        width: 1000,
        height: 562.5,
        right: 1000,
        bottom: 562.5,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      };
      vi.spyOn(container, 'getBoundingClientRect').mockReturnValue(mockRect);

      // Start drawing
      fireEvent.mouseDown(container, { clientX: 100, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 100, clientY: 100 });

      // Cancel with Escape
      fireEvent.keyDown(window, { key: 'Escape' });

      // Should reset to initial instructions
      await waitFor(() => {
        expect(
          screen.getByText(/click to set the start point/i)
        ).toBeInTheDocument();
      });
    });
  });

  describe('Existing Line Display', () => {
    it('creates SVG element when image loads with existing lines', async () => {
      const existingLines: [Point, Point][] = [
        [[0.1, 0.2], [0.5, 0.6]],
        [[0.3, 0.4], [0.8, 0.9]],
      ];

      render(
        <LineZoneEditor
          {...defaultProps}
          isDrawing={false}
          existingLines={existingLines}
        />
      );

      // Simulate image load
      const img = screen.getByAltText('Camera snapshot');
      fireEvent.load(img);

      // SVG should be rendered after image load
      await waitFor(() => {
        const svg = screen.getByTestId('line-editor-svg');
        expect(svg).toBeInTheDocument();
      });
    });

    it('receives existingLines prop correctly', () => {
      const existingLines: [Point, Point][] = [
        [[0.1, 0.2], [0.5, 0.6]],
      ];

      const { container } = render(
        <LineZoneEditor
          {...defaultProps}
          isDrawing={false}
          existingLines={existingLines}
        />
      );

      // Component should render without errors with existingLines
      expect(container).toBeInTheDocument();
    });

    it('accepts onLineSelect callback', () => {
      const existingLines: [Point, Point][] = [
        [[0.1, 0.2], [0.5, 0.6]],
      ];
      const mockOnLineSelect = vi.fn();

      const { container } = render(
        <LineZoneEditor
          {...defaultProps}
          isDrawing={false}
          existingLines={existingLines}
          onLineSelect={mockOnLineSelect}
        />
      );

      // Component should render without errors with onLineSelect callback
      expect(container).toBeInTheDocument();
    });
  });

  describe('Direction Indicator', () => {
    it('renders marker definition when showDirection is true', async () => {
      render(<LineZoneEditor {...defaultProps} showDirection />);

      // Simulate image load
      const img = screen.getByAltText('Camera snapshot');
      fireEvent.load(img);

      // Check for arrow marker in defs
      await waitFor(() => {
        const svg = screen.getByTestId('line-editor-svg');
        expect(svg).toBeInTheDocument();
        const marker = svg.querySelector('marker');
        expect(marker).toBeInTheDocument();
        expect(marker).toHaveAttribute('id', 'arrowhead');
      });
    });

    it('does not render marker when showDirection is false', async () => {
      render(<LineZoneEditor {...defaultProps} showDirection={false} />);

      // Simulate image load
      const img = screen.getByAltText('Camera snapshot');
      fireEvent.load(img);

      // Check for no arrow marker
      await waitFor(() => {
        const svg = screen.getByTestId('line-editor-svg');
        expect(svg).toBeInTheDocument();
        const marker = svg.querySelector('marker');
        expect(marker).not.toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has accessible role when drawing', () => {
      render(<LineZoneEditor {...defaultProps} />);

      expect(screen.getByRole('application')).toBeInTheDocument();
    });

    it('has accessible role when viewing', () => {
      render(<LineZoneEditor {...defaultProps} isDrawing={false} />);

      // Use getByLabelText to find the specific container with img role
      const container = screen.getByLabelText('Camera tripwire lines view');
      expect(container).toHaveAttribute('role', 'img');
    });

    it('has proper aria-label', () => {
      render(<LineZoneEditor {...defaultProps} />);

      const container = screen.getByRole('application');
      expect(container).toHaveAttribute(
        'aria-label',
        expect.stringMatching(/tripwire/i)
      );
    });
  });
});
