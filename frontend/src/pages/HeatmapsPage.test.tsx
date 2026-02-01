/**
 * Tests for HeatmapsPage component
 *
 * TDD Phase: RED - These tests define the expected behavior for the Heatmaps page.
 * Task: NEM-4927 - Heatmaps Visualization Page
 *
 * This test suite covers:
 * - Page rendering with proper structure
 * - Camera selector functionality
 * - Time range and resolution controls
 * - Heatmap display states (loading, empty, data)
 * - History panel
 * - Accessibility requirements
 */

import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';

import HeatmapsPage from './HeatmapsPage';
import * as useCamerasQueryModule from '../hooks/useCamerasQuery';
import * as useHeatmapQueryModule from '../hooks/useHeatmapQuery';
import { renderWithProviders } from '../test/utils';

import type { HeatmapResponse, HeatmapListResponse } from '../hooks/useHeatmapQuery';
import type { Camera } from '../services/api';

// ============================================================================
// Mocks
// ============================================================================

vi.mock('../hooks/useCamerasQuery', () => ({
  useCamerasQuery: vi.fn(),
}));

vi.mock('../hooks/useHeatmapQuery', () => ({
  useHeatmapQuery: vi.fn(),
  useHeatmapHistoryQuery: vi.fn(),
}));

// ============================================================================
// Test Data
// ============================================================================

const mockCameras: Camera[] = [
  {
    id: 'cam-1',
    name: 'Front Door',
    folder_path: '/cameras/front',
    status: 'online',
    last_seen_at: '2026-01-31T10:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    ingestion_mode: 'ftp',
    motion_sensitivity: 0.5,
  },
  {
    id: 'cam-2',
    name: 'Back Yard',
    folder_path: '/cameras/back',
    status: 'online',
    last_seen_at: '2026-01-31T10:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    ingestion_mode: 'rtsp',
    motion_sensitivity: 0.7,
  },
  {
    id: 'cam-3',
    name: 'Garage',
    folder_path: '/cameras/garage',
    status: 'offline',
    last_seen_at: '2026-01-30T10:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    ingestion_mode: 'ftp',
    motion_sensitivity: 0.5,
  },
];

const mockHeatmapData: HeatmapResponse = {
  camera_id: 'cam-1',
  resolution: 'hourly',
  time_bucket: '2026-01-31T10:00:00Z',
  image_base64: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk...',
  width: 640,
  height: 480,
  total_detections: 150,
  colormap: 'jet',
};

const mockHistoryData: HeatmapListResponse = {
  heatmaps: [
    {
      id: 1,
      camera_id: 'cam-1',
      time_bucket: '2026-01-31T09:00:00Z',
      resolution: 'hourly',
      width: 64,
      height: 48,
      total_detections: 120,
      created_at: '2026-01-31T10:00:00Z',
      updated_at: '2026-01-31T10:00:00Z',
    },
    {
      id: 2,
      camera_id: 'cam-1',
      time_bucket: '2026-01-31T08:00:00Z',
      resolution: 'hourly',
      width: 64,
      height: 48,
      total_detections: 85,
      created_at: '2026-01-31T09:00:00Z',
      updated_at: '2026-01-31T09:00:00Z',
    },
  ],
  total: 2,
};

// Default mock return values
const defaultCamerasReturn: ReturnType<typeof useCamerasQueryModule.useCamerasQuery> = {
  cameras: mockCameras,
  isLoading: false,
  isRefetching: false,
  error: null,
  refetch: vi.fn(),
  isPlaceholderData: false,
};

const defaultHeatmapReturn: ReturnType<typeof useHeatmapQueryModule.useHeatmapQuery> = {
  data: undefined,
  isLoading: false,
  isRefetching: false,
  error: null,
  refetch: vi.fn(),
};

const defaultHistoryReturn: ReturnType<typeof useHeatmapQueryModule.useHeatmapHistoryQuery> = {
  data: undefined,
  isLoading: false,
  isRefetching: false,
  error: null,
  refetch: vi.fn(),
};

// ============================================================================
// Tests
// ============================================================================

describe('HeatmapsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useCamerasQueryModule.useCamerasQuery as Mock).mockReturnValue(defaultCamerasReturn);
    (useHeatmapQueryModule.useHeatmapQuery as Mock).mockReturnValue(defaultHeatmapReturn);
    (useHeatmapQueryModule.useHeatmapHistoryQuery as Mock).mockReturnValue(defaultHistoryReturn);
  });

  // ==========================================================================
  // Rendering Tests
  // ==========================================================================

  describe('rendering', () => {
    it('renders the page without crashing', () => {
      renderWithProviders(<HeatmapsPage />);
      expect(screen.getByTestId('heatmaps-page')).toBeInTheDocument();
    });

    it('displays page title "Movement Heatmaps"', () => {
      renderWithProviders(<HeatmapsPage />);
      expect(screen.getByRole('heading', { name: /Movement Heatmaps/i })).toBeInTheDocument();
    });

    it('displays page description', () => {
      renderWithProviders(<HeatmapsPage />);
      expect(
        screen.getByText(/Visualize activity intensity patterns across your cameras/i)
      ).toBeInTheDocument();
    });

    it('has proper heading hierarchy with H1', () => {
      renderWithProviders(<HeatmapsPage />);
      const mainHeading = screen.getByRole('heading', { name: /Movement Heatmaps/i });
      expect(mainHeading).toBeInTheDocument();
      expect(mainHeading.tagName).toBe('H1');
    });

    it('has dark theme background', () => {
      renderWithProviders(<HeatmapsPage />);
      const page = screen.getByTestId('heatmaps-page');
      expect(page.className).toContain('bg-[#121212]');
    });
  });

  // ==========================================================================
  // Loading State Tests
  // ==========================================================================

  describe('loading state', () => {
    it('shows loading spinner while cameras are loading', () => {
      (useCamerasQueryModule.useCamerasQuery as Mock).mockReturnValue({
        ...defaultCamerasReturn,
        cameras: [],
        isLoading: true,
      });

      renderWithProviders(<HeatmapsPage />);
      expect(screen.getByTestId('page-loading')).toBeInTheDocument();
    });

    it('shows refresh button in header', () => {
      renderWithProviders(<HeatmapsPage />);
      expect(screen.getByTestId('refresh-button')).toBeInTheDocument();
    });

    it('refresh button shows spinning animation when refetching', () => {
      (useCamerasQueryModule.useCamerasQuery as Mock).mockReturnValue({
        ...defaultCamerasReturn,
        isRefetching: true,
      });

      renderWithProviders(<HeatmapsPage />);
      const refreshButton = screen.getByTestId('refresh-button');
      // The icon is inside a span wrapper from the Button component
      const iconWrapper = refreshButton.querySelector('span svg');
      expect(iconWrapper).toBeInTheDocument();
      // SVG elements use classList to access class names
      expect(iconWrapper?.classList.contains('animate-spin')).toBe(true);
    });
  });

  // ==========================================================================
  // Error State Tests
  // ==========================================================================

  describe('error state', () => {
    it('displays error message when cameras fail to load', () => {
      (useCamerasQueryModule.useCamerasQuery as Mock).mockReturnValue({
        ...defaultCamerasReturn,
        cameras: [],
        error: new Error('Network error'),
      });

      renderWithProviders(<HeatmapsPage />);
      expect(screen.getByText(/Failed to load heatmap data/i)).toBeInTheDocument();
      expect(screen.getByText(/Network error/i)).toBeInTheDocument();
    });

    it('displays try again button on error', () => {
      (useCamerasQueryModule.useCamerasQuery as Mock).mockReturnValue({
        ...defaultCamerasReturn,
        cameras: [],
        error: new Error('Network error'),
      });

      renderWithProviders(<HeatmapsPage />);
      expect(screen.getByRole('button', { name: /Try Again/i })).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Empty State Tests
  // ==========================================================================

  describe('empty state', () => {
    it('displays empty state when no cameras exist', () => {
      (useCamerasQueryModule.useCamerasQuery as Mock).mockReturnValue({
        ...defaultCamerasReturn,
        cameras: [],
      });

      renderWithProviders(<HeatmapsPage />);
      expect(screen.getByText(/No cameras configured/i)).toBeInTheDocument();
    });

    it('shows prompt to select camera when none is selected', () => {
      renderWithProviders(<HeatmapsPage />);
      // There are two "Select a camera" - one in dropdown, one in empty state
      // We check for the empty state heading
      expect(screen.getByRole('heading', { name: /Select a camera/i })).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Camera Selector Tests
  // ==========================================================================

  describe('camera selector', () => {
    it('displays camera selector dropdown', () => {
      renderWithProviders(<HeatmapsPage />);
      expect(screen.getByTestId('camera-selector')).toBeInTheDocument();
    });

    it('shows all cameras in the dropdown', () => {
      renderWithProviders(<HeatmapsPage />);
      const selector = screen.getByTestId('camera-selector');

      expect(selector).toContainHTML('Front Door');
      expect(selector).toContainHTML('Back Yard');
      expect(selector).toContainHTML('Garage');
    });

    it('shows offline indicator for offline cameras', () => {
      renderWithProviders(<HeatmapsPage />);
      const selector = screen.getByTestId('camera-selector');
      expect(selector).toContainHTML('Garage (Offline)');
    });

    it('selects camera when option is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HeatmapsPage />);

      const selector = screen.getByTestId('camera-selector');
      await user.selectOptions(selector, 'cam-1');

      expect((selector as HTMLSelectElement).value).toBe('cam-1');
    });

    it('triggers heatmap fetch when camera is selected', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HeatmapsPage />);

      const selector = screen.getByTestId('camera-selector');
      await user.selectOptions(selector, 'cam-1');

      await waitFor(() => {
        expect(useHeatmapQueryModule.useHeatmapQuery).toHaveBeenCalledWith(
          expect.objectContaining({
            cameraId: 'cam-1',
            enabled: true,
          })
        );
      });
    });
  });

  // ==========================================================================
  // Time Controls Tests
  // ==========================================================================

  describe('time controls', () => {
    it('displays resolution selector', () => {
      renderWithProviders(<HeatmapsPage />);
      expect(screen.getByTestId('resolution-selector')).toBeInTheDocument();
    });

    it('displays time range selector', () => {
      renderWithProviders(<HeatmapsPage />);
      expect(screen.getByTestId('time-range-selector')).toBeInTheDocument();
    });

    it('shows all resolution options', () => {
      renderWithProviders(<HeatmapsPage />);
      const selector = screen.getByTestId('resolution-selector');

      expect(selector).toContainHTML('Hourly');
      expect(selector).toContainHTML('Daily');
      expect(selector).toContainHTML('Weekly');
    });

    it('shows all time range options', () => {
      renderWithProviders(<HeatmapsPage />);

      expect(screen.getByRole('button', { name: '1 Hour' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '6 Hours' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '24 Hours' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '7 Days' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '30 Days' })).toBeInTheDocument();
    });

    it('highlights selected time range', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HeatmapsPage />);

      const sevenDaysButton = screen.getByRole('button', { name: '7 Days' });
      await user.click(sevenDaysButton);

      expect(sevenDaysButton).toHaveAttribute('aria-pressed', 'true');
    });

    it('changes resolution when option is selected', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HeatmapsPage />);

      const selector = screen.getByTestId('resolution-selector');
      await user.selectOptions(selector, 'daily');

      expect((selector as HTMLSelectElement).value).toBe('daily');
    });
  });

  // ==========================================================================
  // Colormap Selector Tests
  // ==========================================================================

  describe('colormap selector', () => {
    it('displays colormap selector when camera is selected', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HeatmapsPage />);

      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('colormap-selector')).toBeInTheDocument();
      });
    });

    it('shows all colormap options', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HeatmapsPage />);

      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        const selector = screen.getByTestId('colormap-selector');
        expect(selector).toContainHTML('Jet');
        expect(selector).toContainHTML('Hot');
        expect(selector).toContainHTML('Viridis');
        expect(selector).toContainHTML('Plasma');
      });
    });
  });

  // ==========================================================================
  // Heatmap Display Tests
  // ==========================================================================

  describe('heatmap display', () => {
    it('shows loading state while heatmap is loading', async () => {
      const user = userEvent.setup();
      (useHeatmapQueryModule.useHeatmapQuery as Mock).mockReturnValue({
        ...defaultHeatmapReturn,
        isLoading: true,
      });

      renderWithProviders(<HeatmapsPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('heatmap-loading')).toBeInTheDocument();
      });
    });

    it('shows empty state when no heatmap data available', async () => {
      const user = userEvent.setup();
      (useHeatmapQueryModule.useHeatmapQuery as Mock).mockReturnValue({
        ...defaultHeatmapReturn,
        data: undefined,
      });

      renderWithProviders(<HeatmapsPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('heatmap-empty')).toBeInTheDocument();
      });
    });

    it('displays heatmap image when data is available', async () => {
      const user = userEvent.setup();
      (useHeatmapQueryModule.useHeatmapQuery as Mock).mockReturnValue({
        ...defaultHeatmapReturn,
        data: mockHeatmapData,
      });

      renderWithProviders(<HeatmapsPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('heatmap-image')).toBeInTheDocument();
      });
    });

    it('shows detection count when heatmap is displayed', async () => {
      const user = userEvent.setup();
      (useHeatmapQueryModule.useHeatmapQuery as Mock).mockReturnValue({
        ...defaultHeatmapReturn,
        data: mockHeatmapData,
      });

      renderWithProviders(<HeatmapsPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('detection-count')).toHaveTextContent('150');
      });
    });

    it('shows download button when heatmap is displayed', async () => {
      const user = userEvent.setup();
      (useHeatmapQueryModule.useHeatmapQuery as Mock).mockReturnValue({
        ...defaultHeatmapReturn,
        data: mockHeatmapData,
      });

      renderWithProviders(<HeatmapsPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('download-button')).toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // History Panel Tests
  // ==========================================================================

  describe('history panel', () => {
    it('displays history panel when camera is selected', async () => {
      const user = userEvent.setup();
      (useHeatmapQueryModule.useHeatmapHistoryQuery as Mock).mockReturnValue({
        ...defaultHistoryReturn,
        data: mockHistoryData,
      });

      renderWithProviders(<HeatmapsPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('heatmap-history')).toBeInTheDocument();
      });
    });

    it('shows history entries with detection counts', async () => {
      const user = userEvent.setup();
      (useHeatmapQueryModule.useHeatmapHistoryQuery as Mock).mockReturnValue({
        ...defaultHistoryReturn,
        data: mockHistoryData,
      });

      renderWithProviders(<HeatmapsPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('history-entry-1')).toBeInTheDocument();
        expect(screen.getByTestId('history-entry-2')).toBeInTheDocument();
      });
    });

    it('shows loading skeletons while history is loading', async () => {
      const user = userEvent.setup();
      (useHeatmapQueryModule.useHeatmapHistoryQuery as Mock).mockReturnValue({
        ...defaultHistoryReturn,
        isLoading: true,
      });

      renderWithProviders(<HeatmapsPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getAllByTestId('history-skeleton').length).toBeGreaterThan(0);
      });
    });
  });

  // ==========================================================================
  // Accessibility Tests
  // ==========================================================================

  describe('accessibility', () => {
    it('has accessible labels for all form controls', () => {
      renderWithProviders(<HeatmapsPage />);

      expect(screen.getByLabelText(/Select Camera/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Resolution/i)).toBeInTheDocument();
      expect(screen.getByRole('group', { name: /Time range selection/i })).toBeInTheDocument();
    });

    it('has proper ARIA roles for interactive elements', () => {
      renderWithProviders(<HeatmapsPage />);

      const timeRangeSelector = screen.getByTestId('time-range-selector');
      expect(timeRangeSelector).toHaveAttribute('role', 'group');

      const timeRangeButtons = screen.getAllByRole('button').filter(
        (btn) => btn.closest('[data-testid="time-range-selector"]')
      );
      timeRangeButtons.forEach((btn) => {
        expect(btn).toHaveAttribute('aria-pressed');
      });
    });

    it('heatmap image has descriptive alt text', async () => {
      const user = userEvent.setup();
      (useHeatmapQueryModule.useHeatmapQuery as Mock).mockReturnValue({
        ...defaultHeatmapReturn,
        data: mockHeatmapData,
      });

      renderWithProviders(<HeatmapsPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        const image = screen.getByTestId('heatmap-image');
        expect(image).toHaveAttribute('alt', expect.stringContaining('Front Door'));
      });
    });
  });

  // ==========================================================================
  // Integration Tests
  // ==========================================================================

  describe('integration', () => {
    it('full workflow: select camera, view heatmap, change settings', async () => {
      const user = userEvent.setup();
      (useHeatmapQueryModule.useHeatmapQuery as Mock).mockReturnValue({
        ...defaultHeatmapReturn,
        data: mockHeatmapData,
      });
      (useHeatmapQueryModule.useHeatmapHistoryQuery as Mock).mockReturnValue({
        ...defaultHistoryReturn,
        data: mockHistoryData,
      });

      renderWithProviders(<HeatmapsPage />);

      // Step 1: Select camera
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      // Step 2: Verify heatmap is displayed
      await waitFor(() => {
        expect(screen.getByTestId('heatmap-image')).toBeInTheDocument();
      });

      // Step 3: Change resolution
      await user.selectOptions(screen.getByTestId('resolution-selector'), 'daily');

      // Step 4: Change time range
      await user.click(screen.getByRole('button', { name: '7 Days' }));

      // Step 5: Change colormap
      await user.selectOptions(screen.getByTestId('colormap-selector'), 'viridis');

      // Verify the queries were called with correct parameters
      expect(useHeatmapQueryModule.useHeatmapQuery).toHaveBeenLastCalledWith(
        expect.objectContaining({
          cameraId: 'cam-1',
          resolution: 'daily',
          colormap: 'viridis',
        })
      );
    });
  });
});
