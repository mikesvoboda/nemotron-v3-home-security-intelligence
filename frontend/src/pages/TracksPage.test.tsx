/**
 * Tests for TracksPage component
 *
 * TDD Phase: RED - These tests define the expected behavior for the Tracks page.
 * Task: NEM-5024 Phase 5 - Tracks Visualization UI
 *
 * This test suite covers:
 * - Page rendering with proper structure
 * - Camera selector functionality
 * - Track list display with filtering
 * - Trajectory visualization panel
 * - Active tracks indicator
 * - Track statistics display
 * - Accessibility requirements
 */

import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';

import TracksPage from './TracksPage';
import * as useCamerasQueryModule from '../hooks/useCamerasQuery';
import * as useTracksModule from '../hooks/useTracks';
import { renderWithProviders } from '../test/utils';

import type {
  Track,
  TrackHistory,
  CameraTrackStats,
} from '../hooks/useTracks';
import type { Camera } from '../services/api';

// ============================================================================
// Mocks
// ============================================================================

vi.mock('../hooks/useCamerasQuery', () => ({
  useCamerasQuery: vi.fn(),
}));

vi.mock('../hooks/useTracks', () => ({
  useCameraTracks: vi.fn(),
  useCameraTracksStats: vi.fn(),
  useActiveTracks: vi.fn(),
  useTrack: vi.fn(),
  useTrackHistory: vi.fn(),
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

const mockTracks: Track[] = [
  {
    id: 1,
    track_id: 101,
    camera_id: 'cam-1',
    object_class: 'person',
    first_seen: '2026-01-31T09:00:00Z',
    last_seen: '2026-01-31T09:05:00Z',
    metrics: {
      total_distance: 150.5,
      avg_speed: 0.5,
      direction: 45,
      duration_seconds: 300,
    },
  },
  {
    id: 2,
    track_id: 102,
    camera_id: 'cam-1',
    object_class: 'vehicle',
    first_seen: '2026-01-31T08:30:00Z',
    last_seen: '2026-01-31T08:32:00Z',
    metrics: {
      total_distance: 500.2,
      avg_speed: 4.2,
      direction: 180,
      duration_seconds: 120,
    },
  },
  {
    id: 3,
    track_id: 103,
    camera_id: 'cam-1',
    object_class: 'person',
    first_seen: '2026-01-31T08:00:00Z',
    last_seen: '2026-01-31T08:03:00Z',
    metrics: null,
  },
];

const mockActiveTracks: Track[] = [
  {
    id: 1,
    track_id: 101,
    camera_id: 'cam-1',
    object_class: 'person',
    first_seen: '2026-01-31T09:55:00Z',
    last_seen: '2026-01-31T10:00:00Z',
    metrics: {
      total_distance: 50.0,
      avg_speed: 0.3,
      direction: 90,
      duration_seconds: 300,
    },
  },
];

const mockTrackHistory: TrackHistory = {
  id: 1,
  track_id: 101,
  camera_id: 'cam-1',
  object_class: 'person',
  first_seen: '2026-01-31T09:00:00Z',
  last_seen: '2026-01-31T09:05:00Z',
  trajectory: [
    { x: 0.1, y: 0.2, timestamp: '2026-01-31T09:00:00Z' },
    { x: 0.2, y: 0.25, timestamp: '2026-01-31T09:01:00Z' },
    { x: 0.3, y: 0.3, timestamp: '2026-01-31T09:02:00Z' },
    { x: 0.4, y: 0.35, timestamp: '2026-01-31T09:03:00Z' },
    { x: 0.5, y: 0.4, timestamp: '2026-01-31T09:04:00Z' },
    { x: 0.6, y: 0.45, timestamp: '2026-01-31T09:05:00Z' },
  ],
  metrics: {
    total_distance: 150.5,
    avg_speed: 0.5,
    direction: 45,
    duration_seconds: 300,
  },
};

const mockStats: CameraTrackStats = {
  active_count: 1,
  total_today: 42,
  avg_duration_seconds: 185.5,
  by_object_type: {
    person: 25,
    vehicle: 12,
    animal: 5,
  },
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

const defaultCameraTracksReturn = {
  tracks: [],
  total: 0,
  page: 1,
  pageSize: 20,
  isLoading: false,
  isRefetching: false,
  error: null,
  refetch: vi.fn(),
};

const defaultStatsReturn = {
  data: undefined,
  isLoading: false,
  error: null,
  refetch: vi.fn(),
};

const defaultActiveTracksReturn = {
  tracks: [],
  count: 0,
  isLoading: false,
  isRefetching: false,
  error: null,
  refetch: vi.fn(),
};

const defaultTrackReturn = {
  data: undefined,
  isLoading: false,
  error: null,
  refetch: vi.fn(),
};

const defaultTrackHistoryReturn = {
  data: undefined,
  isLoading: false,
  error: null,
  refetch: vi.fn(),
};

// ============================================================================
// Tests
// ============================================================================

describe('TracksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useCamerasQueryModule.useCamerasQuery as Mock).mockReturnValue(defaultCamerasReturn);
    (useTracksModule.useCameraTracks as Mock).mockReturnValue(defaultCameraTracksReturn);
    (useTracksModule.useCameraTracksStats as Mock).mockReturnValue(defaultStatsReturn);
    (useTracksModule.useActiveTracks as Mock).mockReturnValue(defaultActiveTracksReturn);
    (useTracksModule.useTrack as Mock).mockReturnValue(defaultTrackReturn);
    (useTracksModule.useTrackHistory as Mock).mockReturnValue(defaultTrackHistoryReturn);
  });

  // ==========================================================================
  // Rendering Tests
  // ==========================================================================

  describe('rendering', () => {
    it('renders the page without crashing', () => {
      renderWithProviders(<TracksPage />);
      expect(screen.getByTestId('tracks-page')).toBeInTheDocument();
    });

    it('displays page title "Object Tracks"', () => {
      renderWithProviders(<TracksPage />);
      expect(screen.getByRole('heading', { name: /Object Tracks/i })).toBeInTheDocument();
    });

    it('displays page description', () => {
      renderWithProviders(<TracksPage />);
      expect(
        screen.getByText(/Visualize object trajectories and movement patterns/i)
      ).toBeInTheDocument();
    });

    it('has proper heading hierarchy with H1', () => {
      renderWithProviders(<TracksPage />);
      const mainHeading = screen.getByRole('heading', { name: /Object Tracks/i });
      expect(mainHeading).toBeInTheDocument();
      expect(mainHeading.tagName).toBe('H1');
    });

    it('has dark theme background', () => {
      renderWithProviders(<TracksPage />);
      const page = screen.getByTestId('tracks-page');
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

      renderWithProviders(<TracksPage />);
      expect(screen.getByTestId('page-loading')).toBeInTheDocument();
    });

    it('shows refresh button in header', () => {
      renderWithProviders(<TracksPage />);
      expect(screen.getByTestId('refresh-button')).toBeInTheDocument();
    });

    it('refresh button shows spinning animation when refetching', () => {
      (useCamerasQueryModule.useCamerasQuery as Mock).mockReturnValue({
        ...defaultCamerasReturn,
        isRefetching: true,
      });

      renderWithProviders(<TracksPage />);
      const refreshButton = screen.getByTestId('refresh-button');
      const iconWrapper = refreshButton.querySelector('span svg');
      expect(iconWrapper).toBeInTheDocument();
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

      renderWithProviders(<TracksPage />);
      expect(screen.getByText(/Failed to load track data/i)).toBeInTheDocument();
      expect(screen.getByText(/Network error/i)).toBeInTheDocument();
    });

    it('displays try again button on error', () => {
      (useCamerasQueryModule.useCamerasQuery as Mock).mockReturnValue({
        ...defaultCamerasReturn,
        cameras: [],
        error: new Error('Network error'),
      });

      renderWithProviders(<TracksPage />);
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

      renderWithProviders(<TracksPage />);
      expect(screen.getByText(/No cameras configured/i)).toBeInTheDocument();
    });

    it('shows prompt to select camera when none is selected', () => {
      renderWithProviders(<TracksPage />);
      expect(screen.getByRole('heading', { name: /Select a camera/i })).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Camera Selector Tests
  // ==========================================================================

  describe('camera selector', () => {
    it('displays camera selector dropdown', () => {
      renderWithProviders(<TracksPage />);
      expect(screen.getByTestId('camera-selector')).toBeInTheDocument();
    });

    it('shows all cameras in the dropdown', () => {
      renderWithProviders(<TracksPage />);
      const selector = screen.getByTestId('camera-selector');

      expect(selector).toContainHTML('Front Door');
      expect(selector).toContainHTML('Back Yard');
      expect(selector).toContainHTML('Garage');
    });

    it('shows offline indicator for offline cameras', () => {
      renderWithProviders(<TracksPage />);
      const selector = screen.getByTestId('camera-selector');
      expect(selector).toContainHTML('Garage (Offline)');
    });

    it('selects camera when option is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<TracksPage />);

      const selector = screen.getByTestId('camera-selector');
      await user.selectOptions(selector, 'cam-1');

      expect((selector as HTMLSelectElement).value).toBe('cam-1');
    });

    it('triggers tracks fetch when camera is selected', async () => {
      const user = userEvent.setup();
      renderWithProviders(<TracksPage />);

      const selector = screen.getByTestId('camera-selector');
      await user.selectOptions(selector, 'cam-1');

      await waitFor(() => {
        expect(useTracksModule.useCameraTracks).toHaveBeenCalledWith(
          'cam-1',
          expect.objectContaining({
            page: 1,
          })
        );
      });
    });
  });

  // ==========================================================================
  // Filter Controls Tests
  // ==========================================================================

  describe('filter controls', () => {
    it('displays object class filter', async () => {
      const user = userEvent.setup();
      renderWithProviders(<TracksPage />);

      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('object-class-filter')).toBeInTheDocument();
      });
    });

    it('shows all object class filter options', async () => {
      const user = userEvent.setup();
      renderWithProviders(<TracksPage />);

      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        const selector = screen.getByTestId('object-class-filter');
        expect(selector).toContainHTML('All Types');
        expect(selector).toContainHTML('Person');
        expect(selector).toContainHTML('Vehicle');
        expect(selector).toContainHTML('Animal');
      });
    });

    it('filters tracks when object class is selected', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: mockTracks.length,
      });

      renderWithProviders(<TracksPage />);

      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('object-class-filter')).toBeInTheDocument();
      });

      await user.selectOptions(screen.getByTestId('object-class-filter'), 'person');

      await waitFor(() => {
        expect(useTracksModule.useCameraTracks).toHaveBeenCalledWith(
          'cam-1',
          expect.objectContaining({
            objectClass: 'person',
          })
        );
      });
    });
  });

  // ==========================================================================
  // Track Statistics Display Tests
  // ==========================================================================

  describe('track statistics', () => {
    it('displays statistics panel when camera is selected', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracksStats as Mock).mockReturnValue({
        ...defaultStatsReturn,
        data: mockStats,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('stats-panel')).toBeInTheDocument();
      });
    });

    it('shows active count statistic', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracksStats as Mock).mockReturnValue({
        ...defaultStatsReturn,
        data: mockStats,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('stat-active-count')).toHaveTextContent('1');
      });
    });

    it('shows total today statistic', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracksStats as Mock).mockReturnValue({
        ...defaultStatsReturn,
        data: mockStats,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('stat-total-today')).toHaveTextContent('42');
      });
    });

    it('shows average duration statistic', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracksStats as Mock).mockReturnValue({
        ...defaultStatsReturn,
        data: mockStats,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('stat-avg-duration')).toBeInTheDocument();
        // 185.5 seconds should be displayed as "3m 5s" or similar
        expect(screen.getByTestId('stat-avg-duration')).toHaveTextContent(/3.*m/);
      });
    });

    it('shows object type breakdown', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracksStats as Mock).mockReturnValue({
        ...defaultStatsReturn,
        data: mockStats,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('stat-object-types')).toBeInTheDocument();
        expect(screen.getByTestId('stat-object-types')).toHaveTextContent(/person.*25/i);
        expect(screen.getByTestId('stat-object-types')).toHaveTextContent(/vehicle.*12/i);
      });
    });
  });

  // ==========================================================================
  // Active Tracks Indicator Tests
  // ==========================================================================

  describe('active tracks indicator', () => {
    it('shows active tracks badge in header when camera selected', async () => {
      const user = userEvent.setup();
      (useTracksModule.useActiveTracks as Mock).mockReturnValue({
        ...defaultActiveTracksReturn,
        tracks: mockActiveTracks,
        count: 1,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('active-tracks-badge')).toBeInTheDocument();
        expect(screen.getByTestId('active-tracks-badge')).toHaveTextContent('1');
      });
    });

    it('shows pulsing indicator when tracks are active', async () => {
      const user = userEvent.setup();
      (useTracksModule.useActiveTracks as Mock).mockReturnValue({
        ...defaultActiveTracksReturn,
        tracks: mockActiveTracks,
        count: 1,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        const badge = screen.getByTestId('active-tracks-badge');
        expect(badge.className).toContain('animate');
      });
    });

    it('does not show badge when no active tracks', async () => {
      const user = userEvent.setup();
      (useTracksModule.useActiveTracks as Mock).mockReturnValue({
        ...defaultActiveTracksReturn,
        tracks: [],
        count: 0,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.queryByTestId('active-tracks-badge')).not.toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // Track List Tests
  // ==========================================================================

  describe('track list', () => {
    it('displays track list when camera is selected', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: mockTracks.length,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('track-list')).toBeInTheDocument();
      });
    });

    it('shows track cards for each track', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: mockTracks.length,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('track-card-1')).toBeInTheDocument();
        expect(screen.getByTestId('track-card-2')).toBeInTheDocument();
        expect(screen.getByTestId('track-card-3')).toBeInTheDocument();
      });
    });

    it('shows object class on track card', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: mockTracks.length,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        const card = screen.getByTestId('track-card-1');
        expect(card).toHaveTextContent(/person/i);
      });
    });

    it('shows duration on track card', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: mockTracks.length,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        const card = screen.getByTestId('track-card-1');
        // 300 seconds = 5 minutes
        expect(card).toHaveTextContent(/5.*m/);
      });
    });

    it('shows empty state when no tracks exist for camera', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: [],
        total: 0,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByText(/No tracks recorded/i)).toBeInTheDocument();
      });
    });

    it('shows loading skeleton while tracks are loading', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        isLoading: true,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getAllByTestId('track-skeleton').length).toBeGreaterThan(0);
      });
    });
  });

  // ==========================================================================
  // Trajectory Visualization Tests
  // ==========================================================================

  describe('trajectory visualization', () => {
    it('shows trajectory panel when track is selected', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: mockTracks.length,
      });
      (useTracksModule.useTrackHistory as Mock).mockReturnValue({
        ...defaultTrackHistoryReturn,
        data: mockTrackHistory,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('track-card-1')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('track-card-1'));

      await waitFor(() => {
        expect(screen.getByTestId('trajectory-panel')).toBeInTheDocument();
      });
    });

    it('displays trajectory SVG visualization', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: mockTracks.length,
      });
      (useTracksModule.useTrackHistory as Mock).mockReturnValue({
        ...defaultTrackHistoryReturn,
        data: mockTrackHistory,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('track-card-1')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('track-card-1'));

      await waitFor(() => {
        expect(screen.getByTestId('trajectory-svg')).toBeInTheDocument();
      });
    });

    it('shows trajectory metrics in panel', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: mockTracks.length,
      });
      (useTracksModule.useTrackHistory as Mock).mockReturnValue({
        ...defaultTrackHistoryReturn,
        data: mockTrackHistory,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('track-card-1')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('track-card-1'));

      await waitFor(() => {
        const panel = screen.getByTestId('trajectory-panel');
        expect(within(panel).getByText(/distance/i)).toBeInTheDocument();
        expect(within(panel).getByText(/speed/i)).toBeInTheDocument();
        expect(within(panel).getByText(/direction/i)).toBeInTheDocument();
      });
    });

    it('shows loading state while trajectory loads', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: mockTracks.length,
      });
      (useTracksModule.useTrackHistory as Mock).mockReturnValue({
        ...defaultTrackHistoryReturn,
        isLoading: true,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('track-card-1')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('track-card-1'));

      await waitFor(() => {
        expect(screen.getByTestId('trajectory-loading')).toBeInTheDocument();
      });
    });

    it('closes trajectory panel when close button is clicked', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: mockTracks.length,
      });
      (useTracksModule.useTrackHistory as Mock).mockReturnValue({
        ...defaultTrackHistoryReturn,
        data: mockTrackHistory,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('track-card-1')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('track-card-1'));

      await waitFor(() => {
        expect(screen.getByTestId('trajectory-panel')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('close-trajectory-button'));

      await waitFor(() => {
        expect(screen.queryByTestId('trajectory-panel')).not.toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // Pagination Tests
  // ==========================================================================

  describe('pagination', () => {
    it('displays pagination when total exceeds page size', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: 100,
        page: 1,
        pageSize: 20,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('pagination')).toBeInTheDocument();
      });
    });

    it('shows current page number', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: 100,
        page: 2,
        pageSize: 20,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('current-page')).toHaveTextContent('2');
      });
    });

    it('navigates to next page when next button is clicked', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: 100,
        page: 1,
        pageSize: 20,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('next-page-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('next-page-button'));

      await waitFor(() => {
        expect(useTracksModule.useCameraTracks).toHaveBeenCalledWith(
          'cam-1',
          expect.objectContaining({
            page: 2,
          })
        );
      });
    });
  });

  // ==========================================================================
  // Accessibility Tests
  // ==========================================================================

  describe('accessibility', () => {
    it('has accessible labels for all form controls', () => {
      renderWithProviders(<TracksPage />);

      expect(screen.getByLabelText(/Select Camera/i)).toBeInTheDocument();
    });

    it('track cards are keyboard accessible', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: mockTracks.length,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('track-card-1')).toBeInTheDocument();
      });

      const card = screen.getByTestId('track-card-1');
      expect(card).toHaveAttribute('tabIndex', '0');
    });

    it('trajectory panel can be closed with Escape key', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: mockTracks.length,
      });
      (useTracksModule.useTrackHistory as Mock).mockReturnValue({
        ...defaultTrackHistoryReturn,
        data: mockTrackHistory,
      });

      renderWithProviders(<TracksPage />);
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      await waitFor(() => {
        expect(screen.getByTestId('track-card-1')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('track-card-1'));

      await waitFor(() => {
        expect(screen.getByTestId('trajectory-panel')).toBeInTheDocument();
      });

      await user.keyboard('{Escape}');

      await waitFor(() => {
        expect(screen.queryByTestId('trajectory-panel')).not.toBeInTheDocument();
      });
    });
  });

  // ==========================================================================
  // Integration Tests
  // ==========================================================================

  describe('integration', () => {
    it('full workflow: select camera, view tracks, select track, view trajectory', async () => {
      const user = userEvent.setup();
      (useTracksModule.useCameraTracks as Mock).mockReturnValue({
        ...defaultCameraTracksReturn,
        tracks: mockTracks,
        total: mockTracks.length,
      });
      (useTracksModule.useCameraTracksStats as Mock).mockReturnValue({
        ...defaultStatsReturn,
        data: mockStats,
      });
      (useTracksModule.useActiveTracks as Mock).mockReturnValue({
        ...defaultActiveTracksReturn,
        tracks: mockActiveTracks,
        count: 1,
      });
      (useTracksModule.useTrackHistory as Mock).mockReturnValue({
        ...defaultTrackHistoryReturn,
        data: mockTrackHistory,
      });

      renderWithProviders(<TracksPage />);

      // Step 1: Select camera
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      // Step 2: Verify stats are displayed
      await waitFor(() => {
        expect(screen.getByTestId('stats-panel')).toBeInTheDocument();
        expect(screen.getByTestId('stat-total-today')).toHaveTextContent('42');
      });

      // Step 3: Verify active tracks badge
      expect(screen.getByTestId('active-tracks-badge')).toHaveTextContent('1');

      // Step 4: Verify track list
      expect(screen.getByTestId('track-list')).toBeInTheDocument();
      expect(screen.getByTestId('track-card-1')).toBeInTheDocument();

      // Step 5: Select a track
      await user.click(screen.getByTestId('track-card-1'));

      // Step 6: Verify trajectory panel
      await waitFor(() => {
        expect(screen.getByTestId('trajectory-panel')).toBeInTheDocument();
        expect(screen.getByTestId('trajectory-svg')).toBeInTheDocument();
      });

      // Step 7: Filter by object type
      await user.selectOptions(screen.getByTestId('object-class-filter'), 'vehicle');

      // Step 8: Verify filter was applied
      await waitFor(() => {
        expect(useTracksModule.useCameraTracks).toHaveBeenCalledWith(
          'cam-1',
          expect.objectContaining({
            objectClass: 'vehicle',
          })
        );
      });
    });
  });
});
