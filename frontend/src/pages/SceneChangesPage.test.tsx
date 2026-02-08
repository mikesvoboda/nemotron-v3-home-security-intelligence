/**
 * Tests for SceneChangesPage component
 *
 * Task: NEM-4935 - Scene Change Detection History Page
 *
 * This test suite covers:
 * - Page rendering with proper structure
 * - Camera selector functionality
 * - Time range and filter controls
 * - Scene changes list display
 * - Acknowledge functionality
 * - Loading and error states
 * - Accessibility requirements
 */

import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';

import SceneChangesPage from './SceneChangesPage';
import * as useCamerasQueryModule from '../hooks/useCamerasQuery';
import * as useSceneChangesQueryModule from '../hooks/useSceneChangesQuery';
import * as apiModule from '../services/api';
import { renderWithProviders } from '../test/utils';

import type { SceneChangeWithCamera } from '../hooks/useSceneChangesQuery';
import type { Camera } from '../services/api';

// ============================================================================
// Mocks
// ============================================================================

vi.mock('../hooks/useCamerasQuery', () => ({
  useCamerasQuery: vi.fn(),
}));

vi.mock('../hooks/useSceneChangesQuery', () => ({
  useSceneChangesQuery: vi.fn(),
}));

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof apiModule>();
  return {
    ...actual,
    acknowledgeSceneChange: vi.fn(),
  };
});

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

const mockSceneChanges: SceneChangeWithCamera[] = [
  {
    id: 1,
    camera_id: 'cam-1',
    camera_name: 'Front Door',
    change_type: 'view_blocked',
    similarity_score: 0.35,
    detected_at: '2026-01-31T10:30:00Z',
    acknowledged: false,
    acknowledged_at: null,
    file_path: '/path/to/image.jpg',
  },
  {
    id: 2,
    camera_id: 'cam-2',
    camera_name: 'Back Yard',
    change_type: 'angle_changed',
    similarity_score: 0.65,
    detected_at: '2026-01-31T09:00:00Z',
    acknowledged: true,
    acknowledged_at: '2026-01-31T09:30:00Z',
    file_path: '/path/to/image2.jpg',
  },
  {
    id: 3,
    camera_id: 'cam-1',
    camera_name: 'Front Door',
    change_type: 'view_tampered',
    similarity_score: 0.25,
    detected_at: '2026-01-31T08:00:00Z',
    acknowledged: false,
    acknowledged_at: null,
    file_path: '/path/to/image3.jpg',
  },
];

// Default mock return values
const defaultCamerasReturn: ReturnType<typeof useCamerasQueryModule.useCamerasQuery> = {
  cameras: mockCameras,
  isLoading: false,
  isRefetching: false,
  error: null,
  refetch: vi.fn(),
  isPlaceholderData: false,
};

const defaultSceneChangesReturn: ReturnType<typeof useSceneChangesQueryModule.useSceneChangesQuery> =
  {
    sceneChanges: mockSceneChanges,
    isLoading: false,
    isRefetching: false,
    error: null,
    refetch: vi.fn().mockResolvedValue(undefined),
    totalCount: 3,
    unacknowledgedCount: 2,
  };

// ============================================================================
// Tests
// ============================================================================

describe('SceneChangesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useCamerasQueryModule.useCamerasQuery as Mock).mockReturnValue(defaultCamerasReturn);
    (useSceneChangesQueryModule.useSceneChangesQuery as Mock).mockReturnValue(
      defaultSceneChangesReturn
    );
  });

  // ==========================================================================
  // Rendering Tests
  // ==========================================================================

  describe('rendering', () => {
    it('renders the page without crashing', () => {
      renderWithProviders(<SceneChangesPage />);
      expect(screen.getByTestId('scene-changes-page')).toBeInTheDocument();
    });

    it('displays page title "Scene Change History"', () => {
      renderWithProviders(<SceneChangesPage />);
      expect(screen.getByRole('heading', { name: /Scene Change History/i })).toBeInTheDocument();
    });

    it('displays page description', () => {
      renderWithProviders(<SceneChangesPage />);
      expect(
        screen.getByText(/Monitor and review detected scene changes across your cameras/i)
      ).toBeInTheDocument();
    });

    it('has proper heading hierarchy with H1', () => {
      renderWithProviders(<SceneChangesPage />);
      const mainHeading = screen.getByRole('heading', { name: /Scene Change History/i });
      expect(mainHeading).toBeInTheDocument();
      expect(mainHeading.tagName).toBe('H1');
    });

    it('has dark theme background', () => {
      renderWithProviders(<SceneChangesPage />);
      const page = screen.getByTestId('scene-changes-page');
      expect(page.className).toContain('bg-[#121212]');
    });

    it('displays total count and unacknowledged count', () => {
      renderWithProviders(<SceneChangesPage />);
      expect(screen.getByText('3 total')).toBeInTheDocument();
      expect(screen.getByText('2 unreviewed')).toBeInTheDocument();
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

      renderWithProviders(<SceneChangesPage />);
      expect(screen.getByTestId('page-loading')).toBeInTheDocument();
    });

    it('shows loading state while scene changes are loading', () => {
      (useSceneChangesQueryModule.useSceneChangesQuery as Mock).mockReturnValue({
        ...defaultSceneChangesReturn,
        sceneChanges: undefined,
        isLoading: true,
      });

      renderWithProviders(<SceneChangesPage />);
      expect(screen.getByTestId('scene-changes-loading')).toBeInTheDocument();
    });

    it('shows refresh button in header', () => {
      renderWithProviders(<SceneChangesPage />);
      expect(screen.getByTestId('refresh-button')).toBeInTheDocument();
    });

    it('refresh button shows spinning animation when refetching', () => {
      (useSceneChangesQueryModule.useSceneChangesQuery as Mock).mockReturnValue({
        ...defaultSceneChangesReturn,
        isRefetching: true,
      });

      renderWithProviders(<SceneChangesPage />);
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
    it('displays error message when scene changes fail to load', () => {
      (useSceneChangesQueryModule.useSceneChangesQuery as Mock).mockReturnValue({
        ...defaultSceneChangesReturn,
        sceneChanges: [],
        error: new Error('Network error'),
      });

      renderWithProviders(<SceneChangesPage />);
      expect(screen.getByText(/Failed to load scene changes/i)).toBeInTheDocument();
      expect(screen.getByText(/Network error/i)).toBeInTheDocument();
    });

    it('displays try again button on error', () => {
      (useSceneChangesQueryModule.useSceneChangesQuery as Mock).mockReturnValue({
        ...defaultSceneChangesReturn,
        sceneChanges: [],
        error: new Error('Network error'),
      });

      renderWithProviders(<SceneChangesPage />);
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

      renderWithProviders(<SceneChangesPage />);
      expect(screen.getByText(/No cameras configured/i)).toBeInTheDocument();
    });

    it('displays empty state when no scene changes match filters', () => {
      (useSceneChangesQueryModule.useSceneChangesQuery as Mock).mockReturnValue({
        ...defaultSceneChangesReturn,
        sceneChanges: [],
        totalCount: 0,
        unacknowledgedCount: 0,
      });

      renderWithProviders(<SceneChangesPage />);
      expect(screen.getByTestId('scene-changes-empty')).toBeInTheDocument();
      expect(screen.getByText(/No scene changes found/i)).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Camera Selector Tests
  // ==========================================================================

  describe('camera selector', () => {
    it('displays camera selector dropdown', () => {
      renderWithProviders(<SceneChangesPage />);
      expect(screen.getByTestId('camera-selector')).toBeInTheDocument();
    });

    it('shows "All Cameras" option', () => {
      renderWithProviders(<SceneChangesPage />);
      const selector = screen.getByTestId('camera-selector');
      expect(selector).toContainHTML('All Cameras');
    });

    it('shows all cameras in the dropdown', () => {
      renderWithProviders(<SceneChangesPage />);
      const selector = screen.getByTestId('camera-selector');

      expect(selector).toContainHTML('Front Door');
      expect(selector).toContainHTML('Back Yard');
      expect(selector).toContainHTML('Garage');
    });

    it('shows offline indicator for offline cameras', () => {
      renderWithProviders(<SceneChangesPage />);
      const selector = screen.getByTestId('camera-selector');
      expect(selector).toContainHTML('Garage (Offline)');
    });

    it('selects camera when option is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<SceneChangesPage />);

      const selector = screen.getByTestId('camera-selector');
      await user.selectOptions(selector, 'cam-1');

      expect((selector as HTMLSelectElement).value).toBe('cam-1');
    });
  });

  // ==========================================================================
  // Time Range Tests
  // ==========================================================================

  describe('time range selector', () => {
    it('displays time range selector', () => {
      renderWithProviders(<SceneChangesPage />);
      expect(screen.getByTestId('time-range-selector')).toBeInTheDocument();
    });

    it('shows all time range options', () => {
      renderWithProviders(<SceneChangesPage />);

      expect(screen.getByRole('button', { name: '1 Hour' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '6 Hours' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '24 Hours' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '7 Days' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '30 Days' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'All Time' })).toBeInTheDocument();
    });

    it('24 Hours is selected by default', () => {
      renderWithProviders(<SceneChangesPage />);
      const twentyFourHoursButton = screen.getByRole('button', { name: '24 Hours' });
      expect(twentyFourHoursButton).toHaveAttribute('aria-pressed', 'true');
    });

    it('changes time range when button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<SceneChangesPage />);

      const sevenDaysButton = screen.getByRole('button', { name: '7 Days' });
      await user.click(sevenDaysButton);

      expect(sevenDaysButton).toHaveAttribute('aria-pressed', 'true');
    });
  });

  // ==========================================================================
  // Change Type Filter Tests
  // ==========================================================================

  describe('change type filter', () => {
    it('displays change type selector', () => {
      renderWithProviders(<SceneChangesPage />);
      expect(screen.getByTestId('change-type-selector')).toBeInTheDocument();
    });

    it('shows all change type options', () => {
      renderWithProviders(<SceneChangesPage />);
      const selector = screen.getByTestId('change-type-selector');

      expect(selector).toContainHTML('All Types');
      expect(selector).toContainHTML('View Blocked');
      expect(selector).toContainHTML('Angle Changed');
      expect(selector).toContainHTML('Tampered');
    });
  });

  // ==========================================================================
  // Acknowledgement Filter Tests
  // ==========================================================================

  describe('acknowledgement filter', () => {
    it('displays acknowledgement selector', () => {
      renderWithProviders(<SceneChangesPage />);
      expect(screen.getByTestId('acknowledgement-selector')).toBeInTheDocument();
    });

    it('shows all acknowledgement options', () => {
      renderWithProviders(<SceneChangesPage />);
      const selector = screen.getByTestId('acknowledgement-selector');

      expect(selector).toContainHTML('All Status');
      expect(selector).toContainHTML('Unacknowledged');
      expect(selector).toContainHTML('Acknowledged');
    });
  });

  // ==========================================================================
  // Scene Changes List Tests
  // ==========================================================================

  describe('scene changes list', () => {
    it('displays scene changes list', () => {
      renderWithProviders(<SceneChangesPage />);
      expect(screen.getByTestId('scene-changes-list')).toBeInTheDocument();
    });

    it('shows all scene changes', () => {
      renderWithProviders(<SceneChangesPage />);

      expect(screen.getByTestId('scene-change-item-1')).toBeInTheDocument();
      expect(screen.getByTestId('scene-change-item-2')).toBeInTheDocument();
      expect(screen.getByTestId('scene-change-item-3')).toBeInTheDocument();
    });

    it('displays camera names for each scene change', () => {
      renderWithProviders(<SceneChangesPage />);

      // Front Door appears multiple times (in dropdown and in items 1 and 3)
      const frontDoorElements = screen.getAllByText('Front Door');
      expect(frontDoorElements.length).toBeGreaterThanOrEqual(2);

      // Back Yard appears in dropdown and in item 2
      const backYardElements = screen.getAllByText('Back Yard');
      expect(backYardElements.length).toBeGreaterThanOrEqual(1);
    });

    it('displays change type badges', () => {
      renderWithProviders(<SceneChangesPage />);

      // Check within the scene changes list to avoid matching dropdown options
      const sceneChangesList = screen.getByTestId('scene-changes-list');
      expect(sceneChangesList).toHaveTextContent('View Blocked');
      expect(sceneChangesList).toHaveTextContent('Angle Changed');
      expect(sceneChangesList).toHaveTextContent('Tampered');
    });

    it('displays similarity scores', () => {
      renderWithProviders(<SceneChangesPage />);

      expect(screen.getByText('35%')).toBeInTheDocument();
      expect(screen.getByText('65%')).toBeInTheDocument();
      expect(screen.getByText('25%')).toBeInTheDocument();
    });

    it('shows acknowledge button for unacknowledged items', () => {
      renderWithProviders(<SceneChangesPage />);

      expect(screen.getByTestId('acknowledge-1')).toBeInTheDocument();
      expect(screen.getByTestId('acknowledge-3')).toBeInTheDocument();
      expect(screen.queryByTestId('acknowledge-2')).not.toBeInTheDocument();
    });

    it('shows acknowledged badge for acknowledged items', () => {
      renderWithProviders(<SceneChangesPage />);

      // Item 2 is acknowledged
      const item2 = screen.getByTestId('scene-change-item-2');
      expect(item2).toHaveTextContent('Acknowledged');
    });
  });

  // ==========================================================================
  // Acknowledge Functionality Tests
  // ==========================================================================

  describe('acknowledge functionality', () => {
    it('calls acknowledgeSceneChange when acknowledge button is clicked', async () => {
      const user = userEvent.setup();
      const mockAcknowledge = vi.fn().mockResolvedValue({});
      (apiModule.acknowledgeSceneChange as Mock).mockImplementation(mockAcknowledge);

      renderWithProviders(<SceneChangesPage />);

      const acknowledgeButton = screen.getByTestId('acknowledge-1');
      await user.click(acknowledgeButton);

      await waitFor(() => {
        expect(mockAcknowledge).toHaveBeenCalledWith('cam-1', 1);
      });
    });

    it('calls refetch after acknowledging', async () => {
      const user = userEvent.setup();
      const mockRefetch = vi.fn().mockResolvedValue(undefined);
      (apiModule.acknowledgeSceneChange as Mock).mockResolvedValue({});
      (useSceneChangesQueryModule.useSceneChangesQuery as Mock).mockReturnValue({
        ...defaultSceneChangesReturn,
        refetch: mockRefetch,
      });

      renderWithProviders(<SceneChangesPage />);

      const acknowledgeButton = screen.getByTestId('acknowledge-1');
      await user.click(acknowledgeButton);

      await waitFor(() => {
        expect(mockRefetch).toHaveBeenCalled();
      });
    });
  });

  // ==========================================================================
  // Accessibility Tests
  // ==========================================================================

  describe('accessibility', () => {
    it('has accessible labels for all form controls', () => {
      renderWithProviders(<SceneChangesPage />);

      expect(screen.getByLabelText(/Select Camera/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Change Type/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Acknowledgement Status/i)).toBeInTheDocument();
      expect(screen.getByRole('group', { name: /Time range selection/i })).toBeInTheDocument();
    });

    it('has proper ARIA roles for interactive elements', () => {
      renderWithProviders(<SceneChangesPage />);

      const timeRangeSelector = screen.getByTestId('time-range-selector');
      expect(timeRangeSelector).toHaveAttribute('role', 'group');

      const timeRangeButtons = screen
        .getAllByRole('button')
        .filter((btn) => btn.closest('[data-testid="time-range-selector"]'));
      timeRangeButtons.forEach((btn) => {
        expect(btn).toHaveAttribute('aria-pressed');
      });
    });

    it('scene changes list has proper list role', () => {
      renderWithProviders(<SceneChangesPage />);
      const list = screen.getByTestId('scene-changes-list');
      expect(list).toHaveAttribute('role', 'list');
      expect(list).toHaveAttribute('aria-label', 'Scene changes');
    });
  });

  // ==========================================================================
  // Integration Tests
  // ==========================================================================

  describe('integration', () => {
    it('filters are passed to useSceneChangesQuery', async () => {
      const user = userEvent.setup();
      renderWithProviders(<SceneChangesPage />);

      // Select a camera
      await user.selectOptions(screen.getByTestId('camera-selector'), 'cam-1');

      // Change time range
      await user.click(screen.getByRole('button', { name: '7 Days' }));

      // Change type filter
      await user.selectOptions(screen.getByTestId('change-type-selector'), 'view_blocked');

      // Change acknowledgement filter
      await user.selectOptions(screen.getByTestId('acknowledgement-selector'), 'unacknowledged');

      await waitFor(() => {
        expect(useSceneChangesQueryModule.useSceneChangesQuery).toHaveBeenLastCalledWith(
          expect.objectContaining({
            cameraId: 'cam-1',
            timeRange: '7d',
            changeType: 'view_blocked',
            acknowledgementFilter: 'unacknowledged',
          })
        );
      });
    });
  });
});
