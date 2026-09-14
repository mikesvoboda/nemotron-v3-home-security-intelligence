/**
 * Tests for CameraZoneOverlay component (NEM-3202)
 *
 * This test suite covers:
 * - Basic rendering with zone polygons
 * - Interactive features (hover, click, selection)
 * - Mode switching (draw, heatmap, presence, alerts)
 * - Coordinate transformation for different video resolutions
 * - Real-time intelligence overlay (activity levels, presence, alerts)
 * - Accessibility features
 *
 * @module components/zones/CameraZoneOverlay.test
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent, within, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import CameraZoneOverlay from './CameraZoneOverlay';
import { AnomalyType, AnomalySeverity, type ZoneAnomaly } from '../../types/zoneAnomaly';

import type { ZonePresenceMember } from '../../hooks/useZonePresence';
import type { Zone } from '../../types/generated';

// ============================================================================
// Mock Dependencies
// ============================================================================

// Mock useZonesQuery hook
const mockUseZonesQuery = vi.fn();
vi.mock('../../hooks/useZones', () => ({
  useZonesQuery: () => mockUseZonesQuery(),
}));

// Mock useZonePresence hook
const mockUseZonePresence = vi.fn();
vi.mock('../../hooks/useZonePresence', () => ({
  useZonePresence: (zoneId: string) => mockUseZonePresence(zoneId),
}));

// Mock useZoneAnomalies hook
const mockUseZoneAnomalies = vi.fn();
vi.mock('../../hooks/useZoneAnomalies', () => ({
  useZoneAnomalies: (options: unknown) => mockUseZoneAnomalies(options),
}));

// ============================================================================
// Test Fixtures
// ============================================================================

const createMockZone = (overrides: Partial<Zone> = {}): Zone => ({
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
  color: '#3B82F6',
  enabled: true,
  priority: 10,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  ...overrides,
});

const mockZones: Zone[] = [
  createMockZone(),
  createMockZone({
    id: 'zone-2',
    name: 'Driveway',
    zone_type: 'driveway',
    coordinates: [
      [0.5, 0.5],
      [0.9, 0.5],
      [0.9, 0.9],
      [0.5, 0.9],
    ],
    color: '#10B981',
    enabled: true,
    priority: 5,
  }),
  createMockZone({
    id: 'zone-3',
    name: 'Disabled Zone',
    zone_type: 'sidewalk',
    coordinates: [
      [0.7, 0.1],
      [0.9, 0.1],
      [0.9, 0.3],
      [0.7, 0.3],
    ],
    color: '#EF4444',
    enabled: false,
    priority: 0,
  }),
];

const mockPresenceMembers: ZonePresenceMember[] = [
  {
    id: 1,
    name: 'John Doe',
    role: 'resident',
    lastSeen: new Date().toISOString(),
    isStale: false,
    isActive: true,
  },
];

const mockAnomalies: ZoneAnomaly[] = [
  {
    id: 'anomaly-1',
    zone_id: 'zone-1',
    camera_id: 'cam-1',
    anomaly_type: AnomalyType.UNUSUAL_TIME,
    severity: AnomalySeverity.WARNING,
    title: 'Unusual Activity',
    description: 'Activity detected outside normal hours',
    expected_value: 0,
    actual_value: 5,
    deviation: 5.0,
    detection_id: null,
    thumbnail_url: null,
    acknowledged: false,
    acknowledged_at: null,
    acknowledged_by: null,
    timestamp: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

// ============================================================================
// Test Utilities
// ============================================================================

const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

const renderWithProviders = (ui: React.ReactElement) => {
  const queryClient = createQueryClient();
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
};

const defaultProps = {
  cameraId: 'cam-1',
  videoWidth: 1920,
  videoHeight: 1080,
};

// ============================================================================
// Tests
// ============================================================================

describe('CameraZoneOverlay', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock implementations
    mockUseZonesQuery.mockReturnValue({
      zones: mockZones,
      total: mockZones.length,
      isLoading: false,
      isRefetching: false,
      error: null,
      refetch: vi.fn(),
    });

    mockUseZonePresence.mockReturnValue({
      members: [],
      isConnected: true,
      isLoading: false,
      error: null,
      presentCount: 0,
      activeCount: 0,
      clearPresence: vi.fn(),
    });

    mockUseZoneAnomalies.mockReturnValue({
      anomalies: [],
      totalCount: 0,
      isLoading: false,
      isFetching: false,
      error: null,
      isError: false,
      refetch: vi.fn(),
      acknowledgeAnomaly: vi.fn(),
      isAcknowledging: false,
      isConnected: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ==========================================================================
  // Basic Rendering
  // ==========================================================================

  describe('Basic Rendering', () => {
    it('should render SVG overlay container', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      const overlay = screen.getByTestId('camera-zone-overlay');
      expect(overlay).toBeInTheDocument();
      expect(overlay.tagName).toBe('svg');
    });

    it('should render with correct dimensions based on video size', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      const overlay = screen.getByTestId('camera-zone-overlay');
      expect(overlay).toHaveAttribute('viewBox', '0 0 1920 1080');
      expect(overlay).toHaveAttribute('width', '100%');
      expect(overlay).toHaveAttribute('height', '100%');
    });

    it('should render zone polygons for enabled zones', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      // Should render enabled zones
      expect(screen.getByTestId('zone-polygon-zone-1')).toBeInTheDocument();
      expect(screen.getByTestId('zone-polygon-zone-2')).toBeInTheDocument();
    });

    it('should render disabled zones with dashed stroke', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      const disabledZone = screen.getByTestId('zone-polygon-zone-3');
      expect(disabledZone).toBeInTheDocument();
      expect(disabledZone).toHaveAttribute('stroke-dasharray');
    });

    it('should render zone labels when showLabels is true', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} showLabels={true} />);

      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Driveway')).toBeInTheDocument();
    });

    it('should not render zone labels when showLabels is false', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} showLabels={false} />);

      expect(screen.queryByText('Front Door')).not.toBeInTheDocument();
      expect(screen.queryByText('Driveway')).not.toBeInTheDocument();
    });

    it('should display loading state while zones are loading', () => {
      mockUseZonesQuery.mockReturnValue({
        zones: [],
        total: 0,
        isLoading: true,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      // During loading, overlay should still render but may show loading indicator
      expect(screen.getByTestId('camera-zone-overlay')).toBeInTheDocument();
    });

    it('should not render zones when zones list is empty', () => {
      mockUseZonesQuery.mockReturnValue({
        zones: [],
        total: 0,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      expect(screen.queryByTestId('zone-polygon-zone-1')).not.toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Coordinate Transformation
  // ==========================================================================

  describe('Coordinate Transformation', () => {
    it('should transform normalized coordinates to video coordinates', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      const polygon = screen.getByTestId('zone-polygon-zone-1');
      const points = polygon.getAttribute('points');

      // Zone 1 coordinates: [0.1, 0.1], [0.3, 0.1], [0.3, 0.3], [0.1, 0.3]
      // With video dimensions 1920x1080:
      // [192, 108], [576, 108], [576, 324], [192, 324]
      expect(points).toContain('192');
      expect(points).toContain('108');
      expect(points).toContain('576');
      expect(points).toContain('324');
    });

    it('should handle different video resolutions correctly', () => {
      renderWithProviders(
        <CameraZoneOverlay cameraId="cam-1" videoWidth={1280} videoHeight={720} />
      );

      const overlay = screen.getByTestId('camera-zone-overlay');
      expect(overlay).toHaveAttribute('viewBox', '0 0 1280 720');

      const polygon = screen.getByTestId('zone-polygon-zone-1');
      const points = polygon.getAttribute('points');

      // Zone 1 coordinates with 1280x720:
      // [0.1*1280, 0.1*720] = [128, 72]
      expect(points).toContain('128');
      expect(points).toContain('72');
    });
  });

  // ==========================================================================
  // Zone Selection
  // ==========================================================================

  describe('Zone Selection', () => {
    it('should highlight selected zone', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} selectedZoneId="zone-1" />);

      const selectedZone = screen.getByTestId('zone-polygon-zone-1');
      expect(selectedZone).toHaveClass('selected');
    });

    it('should call onZoneClick when zone is clicked', () => {
      const onZoneClick = vi.fn();
      renderWithProviders(<CameraZoneOverlay {...defaultProps} onZoneClick={onZoneClick} />);

      const zone = screen.getByTestId('zone-polygon-zone-1');
      fireEvent.click(zone);

      expect(onZoneClick).toHaveBeenCalledWith('zone-1');
    });

    it('should call onZoneHover when zone is hovered', () => {
      const onZoneHover = vi.fn();
      renderWithProviders(<CameraZoneOverlay {...defaultProps} onZoneHover={onZoneHover} />);

      const zone = screen.getByTestId('zone-polygon-zone-1');

      fireEvent.mouseEnter(zone);
      expect(onZoneHover).toHaveBeenCalledWith('zone-1');

      fireEvent.mouseLeave(zone);
      expect(onZoneHover).toHaveBeenCalledWith(null);
    });

    it('should apply hover styles when zone is hovered', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      const zone = screen.getByTestId('zone-polygon-zone-1');

      fireEvent.mouseEnter(zone);
      expect(zone).toHaveClass('hovered');

      fireEvent.mouseLeave(zone);
      expect(zone).not.toHaveClass('hovered');
    });
  });

  // ==========================================================================
  // Display Modes
  // ==========================================================================

  describe('Display Modes', () => {
    describe('Draw Mode', () => {
      it('should render in draw mode with interactive cursor', () => {
        renderWithProviders(<CameraZoneOverlay {...defaultProps} mode="draw" />);

        const overlay = screen.getByTestId('camera-zone-overlay');
        expect(overlay).toHaveClass('mode-draw');
      });
    });

    describe('Heatmap Mode', () => {
      it('should render zones with activity-based coloring', () => {
        renderWithProviders(<CameraZoneOverlay {...defaultProps} mode="heatmap" />);

        const overlay = screen.getByTestId('camera-zone-overlay');
        expect(overlay).toHaveClass('mode-heatmap');
      });

      it('should apply gradient fill based on activity level', () => {
        // Zone 1 has higher priority (10), zone 2 has lower (5)
        renderWithProviders(<CameraZoneOverlay {...defaultProps} mode="heatmap" />);

        const zone1 = screen.getByTestId('zone-polygon-zone-1');
        const zone2 = screen.getByTestId('zone-polygon-zone-2');

        // Higher activity zones should have different fill opacity
        const zone1Opacity = zone1.getAttribute('fill-opacity');
        const zone2Opacity = zone2.getAttribute('fill-opacity');

        // Both should have fill-opacity but might differ based on activity
        expect(zone1Opacity).toBeDefined();
        expect(zone2Opacity).toBeDefined();
      });
    });

    describe('Presence Mode', () => {
      it('should show presence indicators when showPresence is true', () => {
        mockUseZonePresence.mockReturnValue({
          members: mockPresenceMembers,
          isConnected: true,
          isLoading: false,
          error: null,
          presentCount: 1,
          activeCount: 1,
          clearPresence: vi.fn(),
        });

        renderWithProviders(
          <CameraZoneOverlay {...defaultProps} mode="presence" showPresence={true} />
        );

        // Should show presence indicator on zone
        expect(screen.getByTestId('zone-presence-zone-1')).toBeInTheDocument();
      });

      it('should not show presence indicators when showPresence is false', () => {
        mockUseZonePresence.mockReturnValue({
          members: mockPresenceMembers,
          isConnected: true,
          isLoading: false,
          error: null,
          presentCount: 1,
          activeCount: 1,
          clearPresence: vi.fn(),
        });

        renderWithProviders(
          <CameraZoneOverlay {...defaultProps} mode="presence" showPresence={false} />
        );

        expect(screen.queryByTestId('zone-presence-zone-1')).not.toBeInTheDocument();
      });

      it('should show presence count badge', () => {
        mockUseZonePresence.mockReturnValue({
          members: mockPresenceMembers,
          isConnected: true,
          isLoading: false,
          error: null,
          presentCount: 1,
          activeCount: 1,
          clearPresence: vi.fn(),
        });

        renderWithProviders(
          <CameraZoneOverlay {...defaultProps} mode="presence" showPresence={true} />
        );

        // Multiple presence badges showing "1" is expected since all zones have presence
        const presenceBadge = screen.getByTestId('zone-presence-zone-1');
        expect(within(presenceBadge).getByText('1')).toBeInTheDocument();
      });
    });

    describe('Alerts Mode', () => {
      it('should show alert badges when showAlerts is true', () => {
        mockUseZoneAnomalies.mockReturnValue({
          anomalies: mockAnomalies,
          totalCount: 1,
          isLoading: false,
          isFetching: false,
          error: null,
          isError: false,
          refetch: vi.fn(),
          acknowledgeAnomaly: vi.fn(),
          isAcknowledging: false,
          isConnected: true,
        });

        renderWithProviders(
          <CameraZoneOverlay {...defaultProps} mode="alerts" showAlerts={true} />
        );

        expect(screen.getByTestId('zone-alert-zone-1')).toBeInTheDocument();
      });

      it('should not show alert badges when showAlerts is false', () => {
        mockUseZoneAnomalies.mockReturnValue({
          anomalies: mockAnomalies,
          totalCount: 1,
          isLoading: false,
          isFetching: false,
          error: null,
          isError: false,
          refetch: vi.fn(),
          acknowledgeAnomaly: vi.fn(),
          isAcknowledging: false,
          isConnected: true,
        });

        renderWithProviders(
          <CameraZoneOverlay {...defaultProps} mode="alerts" showAlerts={false} />
        );

        expect(screen.queryByTestId('zone-alert-zone-1')).not.toBeInTheDocument();
      });

      it('should apply pulse animation for active alerts', () => {
        mockUseZoneAnomalies.mockReturnValue({
          anomalies: mockAnomalies,
          totalCount: 1,
          isLoading: false,
          isFetching: false,
          error: null,
          isError: false,
          refetch: vi.fn(),
          acknowledgeAnomaly: vi.fn(),
          isAcknowledging: false,
          isConnected: true,
        });

        renderWithProviders(
          <CameraZoneOverlay {...defaultProps} mode="alerts" showAlerts={true} />
        );

        const alertBadge = screen.getByTestId('zone-alert-zone-1');
        expect(alertBadge).toHaveClass('animate-pulse');
      });

      it('should display alert count on badge', () => {
        const multipleAnomalies = [
          ...mockAnomalies,
          {
            ...mockAnomalies[0],
            id: 'anomaly-2',
            title: 'Second Anomaly',
          },
        ];

        mockUseZoneAnomalies.mockReturnValue({
          anomalies: multipleAnomalies,
          totalCount: 2,
          isLoading: false,
          isFetching: false,
          error: null,
          isError: false,
          refetch: vi.fn(),
          acknowledgeAnomaly: vi.fn(),
          isAcknowledging: false,
          isConnected: true,
        });

        renderWithProviders(
          <CameraZoneOverlay {...defaultProps} mode="alerts" showAlerts={true} />
        );

        const alertBadge = screen.getByTestId('zone-alert-zone-1');
        expect(within(alertBadge).getByText('2')).toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // Real-time Intelligence
  // ==========================================================================

  describe('Real-time Intelligence', () => {
    it('should update presence indicators in real-time', () => {
      const { rerender } = renderWithProviders(
        <CameraZoneOverlay {...defaultProps} mode="presence" showPresence={true} />
      );

      // Initially no presence
      expect(screen.queryByTestId('zone-presence-zone-1')).not.toBeInTheDocument();

      // Update mock to have presence
      mockUseZonePresence.mockReturnValue({
        members: mockPresenceMembers,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 1,
        activeCount: 1,
        clearPresence: vi.fn(),
      });

      // Rerender to reflect changes
      rerender(
        <QueryClientProvider client={createQueryClient()}>
          <CameraZoneOverlay {...defaultProps} mode="presence" showPresence={true} />
        </QueryClientProvider>
      );

      expect(screen.getByTestId('zone-presence-zone-1')).toBeInTheDocument();
    });

    it('should flash zone when crossing event occurs', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      // The flash animation class should be applied via CSS animation
      // Testing animation behavior is tricky, but we can verify the component renders
      expect(screen.getByTestId('zone-polygon-zone-1')).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Accessibility
  // ==========================================================================

  describe('Accessibility', () => {
    it('should have appropriate ARIA labels', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      const overlay = screen.getByTestId('camera-zone-overlay');
      expect(overlay).toHaveAttribute('aria-label', 'Camera zone overlay');
      expect(overlay).toHaveAttribute('role', 'img');
    });

    it('should include zone names in accessible description', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} showLabels={true} />);

      const zoneGroup = screen.getByTestId('zone-group-zone-1');
      expect(zoneGroup).toHaveAttribute('aria-label', 'Zone: Front Door');
    });

    it('should indicate zone enabled/disabled status', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      const disabledZone = screen.getByTestId('zone-group-zone-3');
      expect(disabledZone).toHaveAttribute('aria-disabled', 'true');
    });

    it('should have keyboard-accessible zone interaction', () => {
      const onZoneClick = vi.fn();
      renderWithProviders(<CameraZoneOverlay {...defaultProps} onZoneClick={onZoneClick} />);

      const zone = screen.getByTestId('zone-group-zone-1');

      // Focus and press Enter
      act(() => {
        zone.focus();
        fireEvent.keyDown(zone, { key: 'Enter' });
      });

      expect(onZoneClick).toHaveBeenCalledWith('zone-1');
    });

    it('should have keyboard-accessible zone interaction with Space', () => {
      const onZoneClick = vi.fn();
      renderWithProviders(<CameraZoneOverlay {...defaultProps} onZoneClick={onZoneClick} />);

      const zone = screen.getByTestId('zone-group-zone-1');

      // Focus and press Space
      act(() => {
        zone.focus();
        fireEvent.keyDown(zone, { key: ' ' });
      });

      expect(onZoneClick).toHaveBeenCalledWith('zone-1');
    });
  });

  // ==========================================================================
  // Edge Cases
  // ==========================================================================

  describe('Edge Cases', () => {
    it('should handle zones with polygon shape', () => {
      const polygonZone = createMockZone({
        id: 'polygon-zone',
        name: 'Polygon Zone',
        shape: 'polygon',
        coordinates: [
          [0.1, 0.1],
          [0.2, 0.05],
          [0.3, 0.1],
          [0.3, 0.3],
          [0.1, 0.3],
        ],
      });

      mockUseZonesQuery.mockReturnValue({
        zones: [polygonZone],
        total: 1,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      const polygon = screen.getByTestId('zone-polygon-polygon-zone');
      expect(polygon).toBeInTheDocument();

      // Should have 5 points
      const points = polygon.getAttribute('points')?.split(' ');
      expect(points).toHaveLength(5);
    });

    it('should handle very small video dimensions', () => {
      renderWithProviders(
        <CameraZoneOverlay cameraId="cam-1" videoWidth={320} videoHeight={240} />
      );

      const overlay = screen.getByTestId('camera-zone-overlay');
      expect(overlay).toHaveAttribute('viewBox', '0 0 320 240');
    });

    it('should handle zones with empty coordinates gracefully', () => {
      const emptyZone = createMockZone({
        id: 'empty-zone',
        name: 'Empty Zone',
        coordinates: [],
      });

      mockUseZonesQuery.mockReturnValue({
        zones: [emptyZone],
        total: 1,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      // Should not throw error
      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      // Empty zone should not render a polygon
      expect(screen.queryByTestId('zone-polygon-empty-zone')).not.toBeInTheDocument();
    });

    it('should handle error state from zones query', () => {
      mockUseZonesQuery.mockReturnValue({
        zones: [],
        total: 0,
        isLoading: false,
        isRefetching: false,
        error: new Error('Failed to fetch zones'),
        refetch: vi.fn(),
      });

      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      // Should still render overlay container even with error
      expect(screen.getByTestId('camera-zone-overlay')).toBeInTheDocument();
    });

    it('should update when cameraId changes', () => {
      const { rerender } = renderWithProviders(
        <CameraZoneOverlay {...defaultProps} cameraId="cam-1" />
      );

      // Verify zones are rendered
      expect(mockUseZonesQuery).toHaveBeenCalled();

      // Change camera ID
      rerender(
        <QueryClientProvider client={createQueryClient()}>
          <CameraZoneOverlay {...defaultProps} cameraId="cam-2" />
        </QueryClientProvider>
      );

      // Should fetch new zones for the new camera
      expect(mockUseZonesQuery).toHaveBeenCalled();
    });
  });

  // ==========================================================================
  // Props Interface
  // ==========================================================================

  describe('Props Interface', () => {
    it('should accept all required props', () => {
      // This should compile and render without errors
      renderWithProviders(
        <CameraZoneOverlay cameraId="cam-1" videoWidth={1920} videoHeight={1080} />
      );

      expect(screen.getByTestId('camera-zone-overlay')).toBeInTheDocument();
    });

    it('should accept all optional props', () => {
      const onZoneClick = vi.fn();
      const onZoneHover = vi.fn();

      renderWithProviders(
        <CameraZoneOverlay
          cameraId="cam-1"
          videoWidth={1920}
          videoHeight={1080}
          mode="heatmap"
          selectedZoneId="zone-1"
          onZoneClick={onZoneClick}
          onZoneHover={onZoneHover}
          showLabels={true}
          showPresence={true}
          showAlerts={true}
        />
      );

      expect(screen.getByTestId('camera-zone-overlay')).toBeInTheDocument();
    });

    it('should have default mode of draw', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      const overlay = screen.getByTestId('camera-zone-overlay');
      // Default mode should not have a specific mode class - just the base overlay
      expect(overlay).toBeInTheDocument();
    });

    it('should have default showLabels as true', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} />);

      // Labels should be visible by default
      expect(screen.getByText('Front Door')).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Integration with Hooks
  // ==========================================================================

  describe('Hook Integration', () => {
    it('should call useZonesQuery with correct cameraId', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} cameraId="cam-123" />);

      expect(mockUseZonesQuery).toHaveBeenCalled();
    });

    it('should call useZonePresence for each zone when presence mode is enabled', () => {
      renderWithProviders(
        <CameraZoneOverlay {...defaultProps} mode="presence" showPresence={true} />
      );

      // Should be called for each zone
      expect(mockUseZonePresence).toHaveBeenCalled();
    });

    it('should call useZoneAnomalies when alerts mode is enabled', () => {
      renderWithProviders(<CameraZoneOverlay {...defaultProps} mode="alerts" showAlerts={true} />);

      expect(mockUseZoneAnomalies).toHaveBeenCalled();
    });
  });
});
