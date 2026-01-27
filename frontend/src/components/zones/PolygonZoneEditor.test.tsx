/**
 * PolygonZoneEditor Tests
 *
 * Tests for the polygon zone drawing component used for restricted areas.
 * Polygon zones define specific areas with multiple vertices.
 *
 * @module components/zones/PolygonZoneEditor.test
 * @see NEM-3720 Create frontend zone editor components
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import PolygonZoneEditor from './PolygonZoneEditor';

import type { Point } from './ZoneCanvas';
import type { ZoneType } from '../../types/generated';

// ============================================================================
// Mock Setup
// ============================================================================

vi.mock('../../services/api', () => ({
  getCameraSnapshotUrl: (cameraId: string) => `/api/cameras/${cameraId}/snapshot`,
}));

// ============================================================================
// Test Data
// ============================================================================

const mockOnPolygonComplete = vi.fn();
const mockOnCancel = vi.fn();

const defaultProps = {
  snapshotUrl: '/api/cameras/cam-1/snapshot',
  isDrawing: true,
  zoneType: 'entry_point' as ZoneType,
  zoneColor: '#3B82F6',
  onPolygonComplete: mockOnPolygonComplete,
  onCancel: mockOnCancel,
};

// ============================================================================
// Tests
// ============================================================================

describe('PolygonZoneEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders the component with snapshot background', () => {
      render(<PolygonZoneEditor {...defaultProps} />);

      const img = screen.getByAltText('Camera snapshot');
      expect(img).toBeInTheDocument();
      expect(img).toHaveAttribute('src', '/api/cameras/cam-1/snapshot');
    });

    it('displays drawing instructions when in drawing mode', () => {
      render(<PolygonZoneEditor {...defaultProps} />);

      expect(
        screen.getByText(/click to add points/i)
      ).toBeInTheDocument();
    });

    it('shows zone type indicator', () => {
      render(<PolygonZoneEditor {...defaultProps} zoneType="entry_point" />);

      expect(screen.getByText(/entry point/i)).toBeInTheDocument();
    });

    it('applies cursor-crosshair class when drawing', () => {
      render(<PolygonZoneEditor {...defaultProps} />);

      const container = screen.getByRole('application');
      expect(container).toHaveClass('cursor-crosshair');
    });

    it('renders with different zone types', () => {
      const { rerender } = render(
        <PolygonZoneEditor {...defaultProps} zoneType="entry_point" />
      );
      expect(screen.getByText(/entry point/i)).toBeInTheDocument();

      rerender(<PolygonZoneEditor {...defaultProps} zoneType="driveway" />);
      expect(screen.getByText(/driveway/i)).toBeInTheDocument();

      rerender(<PolygonZoneEditor {...defaultProps} zoneType="sidewalk" />);
      expect(screen.getByText(/sidewalk/i)).toBeInTheDocument();

      rerender(<PolygonZoneEditor {...defaultProps} zoneType="yard" />);
      expect(screen.getByText(/yard/i)).toBeInTheDocument();
    });
  });

  describe('Drawing Interaction', () => {
    const setupWithImageLoad = () => {
      // Mock getBoundingClientRect on all HTMLElement instances before rendering
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

      vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(mockRect);

      render(<PolygonZoneEditor {...defaultProps} />);

      const container = screen.getByRole('application');

      // Simulate image load - this triggers the size update effect
      const img = screen.getByAltText('Camera snapshot');
      fireEvent.load(img);

      // Trigger resize event to ensure containerSize is updated
      window.dispatchEvent(new Event('resize'));

      return container;
    };

    it('records clicks as polygon points', async () => {
      const container = setupWithImageLoad();

      // Click to add first point
      fireEvent.mouseDown(container, { clientX: 100, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 100, clientY: 100 });

      // Click to add second point
      fireEvent.mouseDown(container, { clientX: 500, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 500, clientY: 100 });

      // Verify points counter updates
      await waitFor(() => {
        expect(screen.getByText(/2 points/i)).toBeInTheDocument();
      });
    });

    it('completes polygon on double-click with minimum 3 points', async () => {
      const container = setupWithImageLoad();

      // Add 3 points
      fireEvent.mouseDown(container, { clientX: 100, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 100, clientY: 100 });

      fireEvent.mouseDown(container, { clientX: 500, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 500, clientY: 100 });

      fireEvent.mouseDown(container, { clientX: 300, clientY: 400 });
      fireEvent.mouseUp(container, { clientX: 300, clientY: 400 });

      // Double-click to complete
      fireEvent.dblClick(container, { clientX: 300, clientY: 400 });

      await waitFor(() => {
        expect(mockOnPolygonComplete).toHaveBeenCalledTimes(1);
        const [points] = mockOnPolygonComplete.mock.calls[0];
        expect(points.length).toBeGreaterThanOrEqual(3);
      });
    });

    it('does not complete polygon with less than 3 points', () => {
      const container = setupWithImageLoad();

      // Add only 2 points
      fireEvent.mouseDown(container, { clientX: 100, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 100, clientY: 100 });

      fireEvent.mouseDown(container, { clientX: 500, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 500, clientY: 100 });

      // Try to double-click to complete
      fireEvent.dblClick(container, { clientX: 500, clientY: 100 });

      // Should NOT have called onPolygonComplete
      expect(mockOnPolygonComplete).not.toHaveBeenCalled();
    });

    it('shows SVG overlay after image loads', async () => {
      setupWithImageLoad();

      // After image load, SVG should be present
      await waitFor(() => {
        const svg = screen.getByTestId('zone-editor-svg');
        expect(svg).toBeInTheDocument();
      });
    });

    it('tracks points state correctly for drawing', async () => {
      const container = setupWithImageLoad();

      // Add 2 points
      fireEvent.mouseDown(container, { clientX: 100, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 100, clientY: 100 });

      fireEvent.mouseDown(container, { clientX: 500, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 500, clientY: 100 });

      // Points counter should update
      await waitFor(() => {
        expect(screen.getByText(/2 points/i)).toBeInTheDocument();
      });
    });
  });

  describe('Undo Functionality', () => {
    const setupWithImageLoad = () => {
      // Mock getBoundingClientRect on all HTMLElement instances before rendering
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

      vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(mockRect);

      render(<PolygonZoneEditor {...defaultProps} />);

      const container = screen.getByRole('application');

      // Simulate image load
      const img = screen.getByAltText('Camera snapshot');
      fireEvent.load(img);

      // Trigger resize event
      window.dispatchEvent(new Event('resize'));

      return container;
    };

    it('allows undoing the last point with Ctrl+Z', async () => {
      const container = setupWithImageLoad();

      // Add 3 points
      fireEvent.mouseDown(container, { clientX: 100, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 100, clientY: 100 });

      fireEvent.mouseDown(container, { clientX: 500, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 500, clientY: 100 });

      fireEvent.mouseDown(container, { clientX: 300, clientY: 400 });
      fireEvent.mouseUp(container, { clientX: 300, clientY: 400 });

      await waitFor(() => {
        expect(screen.getByText(/3 points/i)).toBeInTheDocument();
      });

      // Undo last point
      fireEvent.keyDown(window, { key: 'z', ctrlKey: true });

      await waitFor(() => {
        expect(screen.getByText(/2 points/i)).toBeInTheDocument();
      });
    });

    it('shows undo button when points exist', async () => {
      const container = setupWithImageLoad();

      // Add a point
      fireEvent.mouseDown(container, { clientX: 100, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 100, clientY: 100 });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /undo/i })).toBeInTheDocument();
      });
    });
  });

  describe('Cancellation', () => {
    it('calls onCancel when Escape is pressed', () => {
      render(<PolygonZoneEditor {...defaultProps} />);

      fireEvent.keyDown(window, { key: 'Escape' });

      expect(mockOnCancel).toHaveBeenCalledTimes(1);
    });

    it('resets drawing state on cancel', async () => {
      render(<PolygonZoneEditor {...defaultProps} />);

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

      // Add points
      fireEvent.mouseDown(container, { clientX: 100, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 100, clientY: 100 });

      // Cancel
      fireEvent.keyDown(window, { key: 'Escape' });

      // Points counter should reset
      await waitFor(() => {
        expect(screen.queryByText(/1 point/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Existing Polygon Display', () => {
    it('creates SVG element when image loads with existing zones', async () => {
      const existingZones = [
        {
          id: 'zone-1',
          coordinates: [[0.1, 0.2], [0.5, 0.2], [0.5, 0.6], [0.1, 0.6]] as Point[],
          color: '#3B82F6',
          name: 'Zone 1',
        },
      ];

      render(
        <PolygonZoneEditor
          {...defaultProps}
          isDrawing={false}
          existingZones={existingZones}
        />
      );

      // Simulate image load
      const img = screen.getByAltText('Camera snapshot');
      fireEvent.load(img);

      // SVG should be rendered after image load
      await waitFor(() => {
        const svg = screen.getByTestId('zone-editor-svg');
        expect(svg).toBeInTheDocument();
      });
    });

    it('receives existingZones prop correctly', () => {
      const existingZones = [
        {
          id: 'zone-1',
          coordinates: [[0.1, 0.2], [0.5, 0.2], [0.5, 0.6], [0.1, 0.6]] as Point[],
          color: '#3B82F6',
          name: 'Zone 1',
        },
      ];

      const { container } = render(
        <PolygonZoneEditor
          {...defaultProps}
          isDrawing={false}
          existingZones={existingZones}
        />
      );

      // Component should render without errors with existingZones
      expect(container).toBeInTheDocument();
    });

    it('passes selectedZoneId to component', () => {
      const existingZones = [
        {
          id: 'zone-1',
          coordinates: [[0.1, 0.2], [0.5, 0.2], [0.5, 0.6], [0.1, 0.6]] as Point[],
          color: '#3B82F6',
          name: 'Zone 1',
        },
      ];

      const { container } = render(
        <PolygonZoneEditor
          {...defaultProps}
          isDrawing={false}
          existingZones={existingZones}
          selectedZoneId="zone-1"
        />
      );

      // Component should render without errors with selectedZoneId
      expect(container).toBeInTheDocument();
    });

    it('accepts onZoneSelect callback', () => {
      const existingZones = [
        {
          id: 'zone-1',
          coordinates: [[0.1, 0.2], [0.5, 0.2], [0.5, 0.6], [0.1, 0.6]] as Point[],
          color: '#3B82F6',
          name: 'Zone 1',
        },
      ];
      const mockOnZoneSelect = vi.fn();

      const { container } = render(
        <PolygonZoneEditor
          {...defaultProps}
          isDrawing={false}
          existingZones={existingZones}
          onZoneSelect={mockOnZoneSelect}
        />
      );

      // Component should render without errors with onZoneSelect callback
      expect(container).toBeInTheDocument();
    });
  });

  describe('Zone Type Styling', () => {
    it('uses different colors for different zone types', () => {
      const { rerender } = render(
        <PolygonZoneEditor {...defaultProps} zoneType="entry_point" />
      );

      let indicator = screen.getByTestId('zone-type-indicator');
      expect(indicator).toHaveClass('bg-red-500');

      rerender(<PolygonZoneEditor {...defaultProps} zoneType="driveway" />);
      indicator = screen.getByTestId('zone-type-indicator');
      expect(indicator).toHaveClass('bg-amber-500');

      rerender(<PolygonZoneEditor {...defaultProps} zoneType="sidewalk" />);
      indicator = screen.getByTestId('zone-type-indicator');
      expect(indicator).toHaveClass('bg-blue-500');

      rerender(<PolygonZoneEditor {...defaultProps} zoneType="yard" />);
      indicator = screen.getByTestId('zone-type-indicator');
      expect(indicator).toHaveClass('bg-green-500');
    });
  });

  describe('Accessibility', () => {
    it('has accessible role when drawing', () => {
      render(<PolygonZoneEditor {...defaultProps} />);

      expect(screen.getByRole('application')).toBeInTheDocument();
    });

    it('has accessible role when viewing', () => {
      render(<PolygonZoneEditor {...defaultProps} isDrawing={false} />);

      // Use getByLabelText to find the specific container with img role
      const container = screen.getByLabelText('Camera polygon zones view');
      expect(container).toHaveAttribute('role', 'img');
    });

    it('has proper aria-label', () => {
      render(<PolygonZoneEditor {...defaultProps} />);

      const container = screen.getByRole('application');
      expect(container).toHaveAttribute(
        'aria-label',
        expect.stringMatching(/polygon/i)
      );
    });

    it('keyboard navigation works for completing polygon', async () => {
      render(<PolygonZoneEditor {...defaultProps} />);

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

      // Add 3 points
      fireEvent.mouseDown(container, { clientX: 100, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 100, clientY: 100 });

      fireEvent.mouseDown(container, { clientX: 500, clientY: 100 });
      fireEvent.mouseUp(container, { clientX: 500, clientY: 100 });

      fireEvent.mouseDown(container, { clientX: 300, clientY: 400 });
      fireEvent.mouseUp(container, { clientX: 300, clientY: 400 });

      // Press Enter to complete
      fireEvent.keyDown(window, { key: 'Enter' });

      await waitFor(() => {
        expect(mockOnPolygonComplete).toHaveBeenCalledTimes(1);
      });
    });
  });
});
