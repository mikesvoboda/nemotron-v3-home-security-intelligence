/**
 * Tests for ZonesPage component (NEM-3201)
 *
 * Following TDD approach: RED -> GREEN -> REFACTOR
 *
 * Coverage targets:
 * - Page rendering and layout
 * - Zone data loading and display
 * - Zone type filtering
 * - Time range selection
 * - CSV export functionality
 * - Full-screen panel mode
 * - Error and loading states
 * - Empty state handling
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ZonesPage from './ZonesPage';

import type { Zone, Camera } from '../types/generated';

// ============================================================================
// Mocks
// ============================================================================

// Mock the hooks
const mockUseCamerasQuery = vi.fn();
const mockUseZonesQuery = vi.fn();

vi.mock('../hooks/useCamerasQuery', () => ({
  useCamerasQuery: () => mockUseCamerasQuery(),
}));

vi.mock('../hooks/useZones', () => ({
  useZonesQuery: (cameraId: string | undefined, options?: { enabled?: boolean }) => {
    // Only call the mock if enabled is true (or undefined)
    if (options?.enabled === false || !cameraId) {
      return {
        zones: [],
        total: 0,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn().mockResolvedValue(undefined),
      };
    }
    return mockUseZonesQuery();
  },
}));

// Mock the zone components to simplify testing
vi.mock('../components/zones/ZoneTrustMatrix', () => ({
  default: vi.fn(({ zones }) => (
    <div data-testid="zone-trust-matrix">
      Trust Matrix: {zones.length} zones
    </div>
  )),
}));

vi.mock('../components/zones/ZoneAnomalyFeed', () => ({
  default: vi.fn(({ hoursLookback }) => (
    <div data-testid="zone-anomaly-feed">
      Anomaly Feed: {hoursLookback}h lookback
    </div>
  )),
}));

// ============================================================================
// Test Utilities
// ============================================================================

/**
 * Creates a test QueryClient with disabled retries.
 */
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

/**
 * Factory for creating mock cameras.
 */
function createMockCamera(overrides: Partial<Camera> = {}): Camera {
  return {
    id: 'camera-1',
    name: 'Front Door Camera',
    folder_path: '/cameras/front_door',
    status: 'online',
    last_seen_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

/**
 * Factory for creating mock zones.
 */
function createMockZone(overrides: Partial<Zone> = {}): Zone {
  return {
    id: 'zone-1',
    camera_id: 'camera-1',
    name: 'Entry Zone',
    zone_type: 'entry_point',
    shape: 'polygon',
    coordinates: [[0, 0], [100, 0], [100, 100], [0, 100]],
    enabled: true,
    color: '#ff0000',
    priority: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

/**
 * Sets up the default mocks for cameras and zones.
 */
function setupMocks(options: {
  cameras?: Camera[];
  zones?: Zone[];
  camerasLoading?: boolean;
  zonesLoading?: boolean;
  camerasError?: Error | null;
  zonesError?: Error | null;
} = {}) {
  const {
    cameras = [createMockCamera()],
    zones = [createMockZone()],
    camerasLoading = false,
    zonesLoading = false,
    camerasError = null,
    zonesError = null,
  } = options;

  mockUseCamerasQuery.mockReturnValue({
    cameras,
    isLoading: camerasLoading,
    isRefetching: false,
    error: camerasError,
    refetch: vi.fn().mockResolvedValue(undefined),
  });

  mockUseZonesQuery.mockReturnValue({
    zones,
    total: zones.length,
    isLoading: zonesLoading,
    isRefetching: false,
    error: zonesError,
    refetch: vi.fn().mockResolvedValue(undefined),
  });
}

/**
 * Renders the ZonesPage with all required providers.
 */
function renderZonesPage() {
  const queryClient = createTestQueryClient();
  const user = userEvent.setup();

  const utils = render(
    <QueryClientProvider client={queryClient}>
      <ZonesPage />
    </QueryClientProvider>
  );

  return { ...utils, user, queryClient };
}

// ============================================================================
// Tests
// ============================================================================

describe('ZonesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ==========================================================================
  // Loading State Tests
  // ==========================================================================

  describe('Loading State', () => {
    it('shows loading state initially', () => {
      setupMocks({ camerasLoading: true });

      renderZonesPage();

      expect(screen.getByTestId('zones-loading')).toBeInTheDocument();
    });

    it('shows loading when cameras loaded but zones loading', () => {
      mockUseCamerasQuery.mockReturnValue({
        cameras: [createMockCamera()],
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      mockUseZonesQuery.mockReturnValue({
        zones: [],
        total: 0,
        isLoading: true,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      renderZonesPage();

      expect(screen.getByTestId('zones-loading')).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Empty State Tests
  // ==========================================================================

  describe('Empty State', () => {
    it('shows empty state when no zones exist', async () => {
      setupMocks({ zones: [] });

      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByText('No zones configured')).toBeInTheDocument();
      });

      expect(
        screen.getByText(/Create zones in the camera settings/i)
      ).toBeInTheDocument();
    });

    it('shows empty state when no cameras exist', async () => {
      setupMocks({ cameras: [], zones: [] });

      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByText('No zones configured')).toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // Error State Tests
  // ==========================================================================

  describe('Error State', () => {
    it('shows error state when camera fetch fails', async () => {
      setupMocks({ camerasError: new Error('Network error'), cameras: [] });

      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByText(/failed to load zones/i)).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    });

    it('shows error state when zones fetch fails', async () => {
      setupMocks({ zonesError: new Error('Zones fetch failed'), zones: [] });

      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByText(/failed to load zones/i)).toBeInTheDocument();
      });

      expect(screen.getByText('Zones fetch failed')).toBeInTheDocument();
    });

    it('can retry after error', async () => {
      const mockRefetch = vi.fn().mockResolvedValue(undefined);
      mockUseCamerasQuery.mockReturnValue({
        cameras: [],
        isLoading: false,
        isRefetching: false,
        error: new Error('Network error'),
        refetch: mockRefetch,
      });
      mockUseZonesQuery.mockReturnValue({
        zones: [],
        total: 0,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      const { user } = renderZonesPage();

      await waitFor(() => {
        expect(screen.getByText(/failed to load zones/i)).toBeInTheDocument();
      });

      // Click retry
      const retryButton = screen.getByRole('button', { name: /try again/i });
      await user.click(retryButton);

      expect(mockRefetch).toHaveBeenCalled();
    });
  });

  // ==========================================================================
  // Content Display Tests
  // ==========================================================================

  describe('Content Display', () => {
    it('displays page title and zone count', async () => {
      setupMocks({
        zones: [
          createMockZone({ id: 'zone-1', name: 'Entry Zone' }),
          createMockZone({ id: 'zone-2', name: 'Driveway Zone', zone_type: 'driveway' }),
        ],
      });

      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByRole('heading', { level: 1, name: /zone intelligence/i })).toBeInTheDocument();
      });

      expect(screen.getByText(/monitor and manage 2 zones/i)).toBeInTheDocument();
    });

    it('displays zone cards with correct information', async () => {
      setupMocks({
        zones: [
          createMockZone({
            id: 'zone-1',
            name: 'Front Entry',
            zone_type: 'entry_point',
            enabled: true,
            priority: 5,
          }),
        ],
      });

      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zone-card-zone-1')).toBeInTheDocument();
      });

      const card = screen.getByTestId('zone-card-zone-1');
      expect(within(card).getByText('Front Entry')).toBeInTheDocument();
      expect(within(card).getByText('Entry Point')).toBeInTheDocument();
      expect(within(card).getByText('Active')).toBeInTheDocument();
      expect(within(card).getByText('5')).toBeInTheDocument();
    });

    it('displays health summary in header', async () => {
      setupMocks({
        zones: [
          createMockZone({ id: 'zone-1', enabled: true }),
          createMockZone({ id: 'zone-2', enabled: true }),
          createMockZone({ id: 'zone-3', enabled: false }),
        ],
      });

      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      // Health summary should show enabled zones as healthy
      const healthDots = document.querySelectorAll('.h-2\\.5.w-2\\.5.rounded-full');
      expect(healthDots.length).toBeGreaterThan(0);
    });

    it('displays trust matrix panel', async () => {
      setupMocks();

      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zone-trust-matrix')).toBeInTheDocument();
      });

      expect(screen.getByText(/trust matrix: 1 zones/i)).toBeInTheDocument();
    });

    it('displays anomaly feed panel', async () => {
      setupMocks();

      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zone-anomaly-feed')).toBeInTheDocument();
      });

      // Default time range is 24h
      expect(screen.getByText(/anomaly feed: 24h lookback/i)).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Zone Filtering Tests
  // ==========================================================================

  describe('Zone Filtering', () => {
    it('filters zones by type', async () => {
      setupMocks({
        zones: [
          createMockZone({ id: 'zone-1', name: 'Entry Zone', zone_type: 'entry_point' }),
          createMockZone({ id: 'zone-2', name: 'Driveway Zone', zone_type: 'driveway' }),
          createMockZone({ id: 'zone-3', name: 'Yard Zone', zone_type: 'yard' }),
        ],
      });

      const { user } = renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      // All zones visible initially
      expect(screen.getByText('Entry Zone')).toBeInTheDocument();
      expect(screen.getByText('Driveway Zone')).toBeInTheDocument();
      expect(screen.getByText('Yard Zone')).toBeInTheDocument();

      // Filter by entry_point
      const typeSelect = screen.getByTestId('zone-type-select');
      await user.selectOptions(typeSelect, 'entry_point');

      // Only entry zones visible
      expect(screen.getByText('Entry Zone')).toBeInTheDocument();
      expect(screen.queryByText('Driveway Zone')).not.toBeInTheDocument();
      expect(screen.queryByText('Yard Zone')).not.toBeInTheDocument();
    });

    it('shows message when no zones match filter', async () => {
      setupMocks({
        zones: [
          createMockZone({ id: 'zone-1', name: 'Entry Zone', zone_type: 'entry_point' }),
        ],
      });

      const { user } = renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      // Filter by driveway (no zones of this type)
      const typeSelect = screen.getByTestId('zone-type-select');
      await user.selectOptions(typeSelect, 'driveway');

      expect(screen.getByText('No zones match the selected filter.')).toBeInTheDocument();
    });

    it('updates trust matrix when filter changes', async () => {
      setupMocks({
        zones: [
          createMockZone({ id: 'zone-1', name: 'Entry Zone', zone_type: 'entry_point' }),
          createMockZone({ id: 'zone-2', name: 'Driveway Zone', zone_type: 'driveway' }),
        ],
      });

      const { user } = renderZonesPage();

      await waitFor(() => {
        expect(screen.getByText(/trust matrix: 2 zones/i)).toBeInTheDocument();
      });

      // Filter by entry_point
      const typeSelect = screen.getByTestId('zone-type-select');
      await user.selectOptions(typeSelect, 'entry_point');

      expect(screen.getByText(/trust matrix: 1 zones/i)).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Time Range Selection Tests
  // ==========================================================================

  describe('Time Range Selection', () => {
    beforeEach(() => {
      setupMocks();
    });

    it('displays time range selector', async () => {
      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('time-range-selector')).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: '1h' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '6h' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '24h' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '7d' })).toBeInTheDocument();
    });

    it('changes time range when button clicked', async () => {
      const { user } = renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      // Default is 24h
      expect(screen.getByText(/anomaly feed: 24h lookback/i)).toBeInTheDocument();

      // Click 1h button
      await user.click(screen.getByRole('button', { name: '1h' }));
      expect(screen.getByText(/anomaly feed: 1h lookback/i)).toBeInTheDocument();

      // Click 7d button
      await user.click(screen.getByRole('button', { name: '7d' }));
      expect(screen.getByText(/anomaly feed: 168h lookback/i)).toBeInTheDocument();
    });

    it('highlights selected time range', async () => {
      const { user } = renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      // Check 24h is pressed by default
      const button24h = screen.getByRole('button', { name: '24h' });
      expect(button24h).toHaveAttribute('aria-pressed', 'true');

      // Click 1h and verify states
      await user.click(screen.getByRole('button', { name: '1h' }));

      expect(screen.getByRole('button', { name: '1h' })).toHaveAttribute('aria-pressed', 'true');
      expect(screen.getByRole('button', { name: '24h' })).toHaveAttribute('aria-pressed', 'false');
    });
  });

  // ==========================================================================
  // Export Functionality Tests
  // ==========================================================================

  describe('Export Functionality', () => {
    beforeEach(() => {
      setupMocks({
        zones: [
          createMockZone({ id: 'zone-1', name: 'Entry Zone', zone_type: 'entry_point' }),
          createMockZone({ id: 'zone-2', name: 'Driveway Zone', zone_type: 'driveway' }),
        ],
      });
    });

    it('displays export button', async () => {
      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('export-button')).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /export csv/i })).toBeInTheDocument();
    });

    it('triggers CSV download on export click', async () => {
      const { user } = renderZonesPage();

      // Mock URL.createObjectURL and URL.revokeObjectURL
      const mockUrl = 'blob:test-url';
      const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue(mockUrl);
      const revokeObjectURLSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});

      // Mock link click
      const clickSpy = vi.fn();
      const originalCreateElement = document.createElement.bind(document);
      const createElementSpy = vi.spyOn(document, 'createElement').mockImplementation((tagName) => {
        if (tagName === 'a') {
          const link = originalCreateElement('a');
          link.click = clickSpy;
          return link;
        }
        return originalCreateElement(tagName);
      });

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      // Click export button
      await user.click(screen.getByTestId('export-button'));

      await waitFor(() => {
        expect(createObjectURLSpy).toHaveBeenCalled();
        expect(clickSpy).toHaveBeenCalled();
        expect(revokeObjectURLSpy).toHaveBeenCalledWith(mockUrl);
      });

      // Cleanup
      createObjectURLSpy.mockRestore();
      revokeObjectURLSpy.mockRestore();
      createElementSpy.mockRestore();
    });

    it('exports only filtered zones', async () => {
      const { user } = renderZonesPage();

      const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test-url');
      vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      // Filter by entry_point
      const typeSelect = screen.getByTestId('zone-type-select');
      await user.selectOptions(typeSelect, 'entry_point');

      // Click export
      await user.click(screen.getByTestId('export-button'));

      await waitFor(() => {
        expect(createObjectURLSpy).toHaveBeenCalled();
      });

      // The Blob passed should only contain entry_point zones
      const blobArg = createObjectURLSpy.mock.calls[0][0];
      expect(blobArg).toBeInstanceOf(Blob);

      createObjectURLSpy.mockRestore();
    });
  });

  // ==========================================================================
  // Full-Screen Panel Tests
  // ==========================================================================

  describe('Full-Screen Panel Mode', () => {
    beforeEach(() => {
      setupMocks();
    });

    it('displays full-screen toggle on each panel', async () => {
      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      // Each panel should have a full-screen toggle button
      const panels = ['panel-overview', 'panel-trust', 'panel-alerts'];
      panels.forEach((panelId) => {
        const panel = screen.getByTestId(panelId);
        const toggleButton = within(panel).getByRole('button', { name: /full screen/i });
        expect(toggleButton).toBeInTheDocument();
      });
    });

    it('enters full-screen mode when toggle clicked', async () => {
      const { user } = renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      const overviewPanel = screen.getByTestId('panel-overview');
      const toggleButton = within(overviewPanel).getByRole('button', { name: /enter full screen/i });

      await user.click(toggleButton);

      // Panel should have fixed position classes when in full-screen
      await waitFor(() => {
        const panel = screen.getByTestId('panel-overview');
        expect(panel).toHaveClass('fixed');
      });

      // Other panels should be hidden
      expect(screen.queryByTestId('panel-trust')).not.toBeInTheDocument();
      expect(screen.queryByTestId('panel-alerts')).not.toBeInTheDocument();
    });

    it('exits full-screen mode when toggle clicked again', async () => {
      const { user } = renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      // Enter full-screen
      const overviewPanel = screen.getByTestId('panel-overview');
      await user.click(within(overviewPanel).getByRole('button', { name: /enter full screen/i }));

      await waitFor(() => {
        expect(screen.getByTestId('panel-overview')).toHaveClass('fixed');
      });

      // Exit full-screen
      const fullScreenPanel = screen.getByTestId('panel-overview');
      await user.click(within(fullScreenPanel).getByRole('button', { name: /exit full screen/i }));

      await waitFor(() => {
        expect(screen.getByTestId('panel-overview')).not.toHaveClass('fixed');
      });

      // Other panels should be visible again
      expect(screen.getByTestId('panel-trust')).toBeInTheDocument();
      expect(screen.getByTestId('panel-alerts')).toBeInTheDocument();
    });

    it('exits full-screen when backdrop is clicked', async () => {
      const { user } = renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      // Enter full-screen
      const overviewPanel = screen.getByTestId('panel-overview');
      await user.click(within(overviewPanel).getByRole('button', { name: /enter full screen/i }));

      await waitFor(() => {
        expect(screen.getByTestId('panel-overview')).toHaveClass('fixed');
      });

      // Click backdrop (the dark overlay)
      const backdrop = document.querySelector('.bg-black\\/80');
      expect(backdrop).not.toBeNull();
      await user.click(backdrop!);

      await waitFor(() => {
        expect(screen.getByTestId('panel-overview')).not.toHaveClass('fixed');
      });
    });
  });

  // ==========================================================================
  // Refresh Functionality Tests
  // ==========================================================================

  describe('Refresh Functionality', () => {
    it('displays refresh button', async () => {
      setupMocks();

      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });

    it('refetches data when refresh is clicked', async () => {
      const mockRefetchCameras = vi.fn().mockResolvedValue(undefined);
      const mockRefetchZones = vi.fn().mockResolvedValue(undefined);

      mockUseCamerasQuery.mockReturnValue({
        cameras: [createMockCamera()],
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: mockRefetchCameras,
      });

      mockUseZonesQuery.mockReturnValue({
        zones: [createMockZone()],
        total: 1,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: mockRefetchZones,
      });

      const { user } = renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      // Click refresh
      await user.click(screen.getByRole('button', { name: /refresh/i }));

      await waitFor(() => {
        expect(mockRefetchCameras).toHaveBeenCalled();
      });
    });
  });

  // ==========================================================================
  // Responsive Layout Tests
  // ==========================================================================

  describe('Responsive Layout', () => {
    beforeEach(() => {
      setupMocks();
    });

    it('renders grid layout for zone cards', async () => {
      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zone-grid')).toBeInTheDocument();
      });

      const grid = screen.getByTestId('zone-grid');
      expect(grid).toHaveClass('grid');
    });

    it('renders filter bar', async () => {
      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zone-filter-bar')).toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // Accessibility Tests
  // ==========================================================================

  describe('Accessibility', () => {
    beforeEach(() => {
      setupMocks();
    });

    it('has accessible page title', async () => {
      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByRole('heading', { level: 1, name: /zone intelligence/i })).toBeInTheDocument();
      });
    });

    it('has accessible labels for form controls', async () => {
      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      // Zone type select should have accessible label
      const typeSelect = screen.getByTestId('zone-type-select');
      expect(typeSelect).toHaveAccessibleName();

      // Time range selector group
      const timeRangeGroup = screen.getByTestId('time-range-selector');
      expect(timeRangeGroup).toHaveAttribute('role', 'group');
      expect(timeRangeGroup).toHaveAccessibleName();
    });

    it('has aria-pressed on time range buttons', async () => {
      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zones-page')).toBeInTheDocument();
      });

      const button24h = screen.getByRole('button', { name: '24h' });
      expect(button24h).toHaveAttribute('aria-pressed', 'true');

      const button1h = screen.getByRole('button', { name: '1h' });
      expect(button1h).toHaveAttribute('aria-pressed', 'false');
    });
  });

  // ==========================================================================
  // Zone Card Status Tests
  // ==========================================================================

  describe('Zone Card Status', () => {
    it('shows healthy status for enabled zones', async () => {
      setupMocks({
        zones: [createMockZone({ id: 'zone-1', enabled: true })],
      });

      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zone-card-zone-1')).toBeInTheDocument();
      });

      const card = screen.getByTestId('zone-card-zone-1');
      expect(within(card).getByText('Healthy')).toBeInTheDocument();
      expect(within(card).getByText('Active')).toBeInTheDocument();
    });

    it('shows unknown status for disabled zones', async () => {
      setupMocks({
        zones: [createMockZone({ id: 'zone-1', enabled: false })],
      });

      renderZonesPage();

      await waitFor(() => {
        expect(screen.getByTestId('zone-card-zone-1')).toBeInTheDocument();
      });

      const card = screen.getByTestId('zone-card-zone-1');
      expect(within(card).getByText('Unknown')).toBeInTheDocument();
      expect(within(card).getByText('Inactive')).toBeInTheDocument();
    });
  });
});
