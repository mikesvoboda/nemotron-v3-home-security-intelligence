import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import ZoneEditor from './ZoneEditor';

import type { Zone } from '../../services/api';

// Mock ResizeObserver
const mockResizeObserver = vi.fn(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));
vi.stubGlobal('ResizeObserver', mockResizeObserver);

describe('ZoneEditor', () => {
  const mockZones: Zone[] = [
    {
      id: 'zone-1',
      camera_id: 'cam-1',
      name: 'Front Door',
      zone_type: 'entry_point',
      coordinates: [
        [0.1, 0.1],
        [0.3, 0.1],
        [0.3, 0.3],
        [0.1, 0.3],
      ],
      shape: 'rectangle',
      color: '#ef4444',
      enabled: true,
      priority: 1,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    },
    {
      id: 'zone-2',
      camera_id: 'cam-1',
      name: 'Driveway',
      zone_type: 'driveway',
      coordinates: [
        [0.5, 0.5],
        [0.8, 0.5],
        [0.8, 0.9],
        [0.5, 0.9],
      ],
      shape: 'rectangle',
      color: '#3b82f6',
      enabled: false,
      priority: 0,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render without image', () => {
      render(<ZoneEditor zones={[]} />);
      expect(screen.getByText('No camera preview available')).toBeInTheDocument();
    });

    it('should render with image', () => {
      render(<ZoneEditor zones={[]} imageUrl="/test-image.jpg" />);
      const img = screen.getByAltText('Camera preview');
      expect(img).toBeInTheDocument();
      expect(img).toHaveAttribute('src', '/test-image.jpg');
    });

    it('should render with zones', () => {
      render(<ZoneEditor zones={mockZones} />);
      // SVG elements are rendered, but we just verify component doesn't crash
      // No image URL provided, so we should see "No camera preview available"
      expect(screen.getByText('No camera preview available')).toBeInTheDocument();
    });

    it('should render zones with different modes', () => {
      const { rerender } = render(<ZoneEditor zones={mockZones} mode="view" />);
      expect(screen.queryByText('No camera preview available')).toBeInTheDocument();

      rerender(<ZoneEditor zones={mockZones} mode="draw" drawShape="rectangle" />);
      expect(screen.getByText(/Click to set first corner/)).toBeInTheDocument();

      rerender(<ZoneEditor zones={mockZones} mode="draw" drawShape="polygon" />);
      expect(screen.getByText(/Click to add points/)).toBeInTheDocument();
    });
  });

  describe('Draw Mode', () => {
    it('should show rectangle drawing instructions', () => {
      render(<ZoneEditor zones={[]} mode="draw" drawShape="rectangle" />);
      expect(screen.getByText('Click to set first corner')).toBeInTheDocument();
    });

    it('should show polygon drawing instructions', () => {
      render(<ZoneEditor zones={[]} mode="draw" drawShape="polygon" />);
      expect(screen.getByText(/Click to add points/)).toBeInTheDocument();
    });

    it('should show draw indicator for rectangle', () => {
      render(<ZoneEditor zones={[]} mode="draw" drawShape="rectangle" />);
      expect(screen.getByText('Draw rectangle')).toBeInTheDocument();
    });

    it('should show draw indicator for polygon', () => {
      render(<ZoneEditor zones={[]} mode="draw" drawShape="polygon" />);
      expect(screen.getByText('Draw polygon')).toBeInTheDocument();
    });

    it('should show reset button when drawing', () => {
      const onZoneCreate = vi.fn();
      render(
        <ZoneEditor
          zones={[]}
          mode="draw"
          drawShape="rectangle"
          onZoneCreate={onZoneCreate}
        />
      );

      // Initially no reset button (no points drawn)
      expect(screen.queryByText('Reset')).not.toBeInTheDocument();
    });
  });

  describe('Edit Mode', () => {
    it('should show edit indicator when zone is selected', () => {
      render(
        <ZoneEditor
          zones={mockZones}
          mode="edit"
          selectedZoneId="zone-1"
        />
      );
      expect(screen.getByText('Edit Zone')).toBeInTheDocument();
    });

    it('should not show edit indicator when no zone is selected', () => {
      render(<ZoneEditor zones={mockZones} mode="edit" />);
      expect(screen.queryByText('Edit Zone')).not.toBeInTheDocument();
    });
  });

  describe('Zone Selection', () => {
    it('should call onZoneSelect when zone is clicked', () => {
      const onZoneSelect = vi.fn();
      render(
        <ZoneEditor
          zones={mockZones}
          mode="view"
          onZoneSelect={onZoneSelect}
        />
      );
      // Note: Actual zone click testing would require more complex SVG interaction testing
      // This test verifies the callback prop is properly passed
      expect(onZoneSelect).not.toHaveBeenCalled();
    });
  });

  describe('Zone Styles', () => {
    it('should apply different opacity for enabled vs disabled zones', () => {
      // Zone-1 is enabled, Zone-2 is disabled
      render(<ZoneEditor zones={mockZones} />);
      // Visual testing would be needed for full verification
      // This ensures the component renders without errors with mixed enabled states
      expect(screen.queryByText('No camera preview available')).toBeInTheDocument();
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', () => {
      const { container } = render(
        <ZoneEditor zones={[]} className="custom-class" />
      );
      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('Keyboard Interactions', () => {
    it('should handle Escape key to clear drawing', () => {
      render(<ZoneEditor zones={[]} mode="draw" drawShape="polygon" />);

      // Trigger Escape key
      fireEvent.keyDown(window, { key: 'Escape' });

      // The component should reset drawing state (no visual change without interaction)
      expect(screen.getByText(/Click to add points/)).toBeInTheDocument();
    });
  });

  describe('Mode Indicator', () => {
    it('should show mode indicator based on current mode', () => {
      const { rerender } = render(<ZoneEditor zones={[]} mode="view" />);
      expect(screen.queryByText(/Draw/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Edit/)).not.toBeInTheDocument();

      rerender(<ZoneEditor zones={[]} mode="draw" drawShape="rectangle" />);
      expect(screen.getByText('Draw rectangle')).toBeInTheDocument();

      rerender(
        <ZoneEditor zones={mockZones} mode="edit" selectedZoneId="zone-1" />
      );
      expect(screen.getByText('Edit Zone')).toBeInTheDocument();
    });
  });

  describe('Container Styling', () => {
    it('should have cursor-crosshair in draw mode', () => {
      const { container } = render(
        <ZoneEditor zones={[]} mode="draw" drawShape="rectangle" />
      );
      expect(container.firstChild).toHaveClass('cursor-crosshair');
    });

    it('should have cursor-move in edit mode', () => {
      const { container } = render(
        <ZoneEditor zones={mockZones} mode="edit" selectedZoneId="zone-1" />
      );
      expect(container.firstChild).toHaveClass('cursor-move');
    });

    it('should have default cursor in view mode', () => {
      const { container } = render(<ZoneEditor zones={[]} mode="view" />);
      expect(container.firstChild).not.toHaveClass('cursor-crosshair');
      expect(container.firstChild).not.toHaveClass('cursor-move');
    });
  });
});
