import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import AreaCameraLinking from './AreaCameraLinking';
import * as cameraHooks from '../../hooks/useCamerasQuery';
import * as propertyHooks from '../../hooks/usePropertyQueries';

import type {
  AreaResponse,
  PropertyResponse,
  AreaCameraResponse,
  UseAreaMutationsReturn,
} from '../../hooks/usePropertyQueries';
import type { Camera } from '../../services/api';

// Mock the hooks modules
vi.mock('../../hooks/useCamerasQuery', () => ({
  useCamerasQuery: vi.fn(),
}));

vi.mock('../../hooks/usePropertyQueries', () => ({
  usePropertiesQuery: vi.fn(),
  useAreasQuery: vi.fn(),
  useAreaCamerasQuery: vi.fn(),
  useAreaMutations: vi.fn(),
}));

// =============================================================================
// Test Data
// =============================================================================

const mockCameras: Camera[] = [
  {
    id: 'cam-1',
    name: 'Front Door',
    folder_path: '/export/foscam/front_door',
    status: 'online',
    created_at: '2025-01-01T00:00:00Z',
    last_seen_at: '2025-01-10T12:00:00Z',
  },
  {
    id: 'cam-2',
    name: 'Backyard',
    folder_path: '/export/foscam/backyard',
    status: 'offline',
    created_at: '2025-01-01T00:00:00Z',
    last_seen_at: null,
  },
  {
    id: 'cam-3',
    name: 'Garage',
    folder_path: '/export/foscam/garage',
    status: 'online',
    created_at: '2025-01-01T00:00:00Z',
    last_seen_at: '2025-01-10T12:00:00Z',
  },
];

const mockProperties: PropertyResponse[] = [
  {
    id: 1,
    household_id: 1,
    name: 'Main House',
    address: '123 Main St',
    timezone: 'America/New_York',
    created_at: '2025-01-01T00:00:00Z',
  },
];

const mockAreas: AreaResponse[] = [
  {
    id: 1,
    property_id: 1,
    name: 'Front Yard',
    description: 'Main entrance and lawn area',
    color: '#10B981',
    created_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 2,
    property_id: 1,
    name: 'Backyard',
    description: 'Pool and garden area',
    color: '#3B82F6',
    created_at: '2025-01-01T00:00:00Z',
  },
];

const mockLinkedCameras: AreaCameraResponse[] = [
  {
    id: 'cam-1',
    name: 'Front Door',
    status: 'online',
  },
];

// Helper to create mock mutation object
function createMockMutation<TData, _TError, TVariables>(overrides?: {
  isPending?: boolean;
  mutateAsync?: (variables: TVariables) => Promise<TData>;
}) {
  return {
    mutate: vi.fn(),
    mutateAsync: overrides?.mutateAsync ?? vi.fn().mockResolvedValue(undefined),
    isPending: (overrides?.isPending ?? false) as false,
    isSuccess: false as const,
    isError: false as const,
    isIdle: true as const,
    data: undefined,
    error: null,
    reset: vi.fn(),
    context: undefined,
    failureCount: 0,
    failureReason: null,
    status: 'idle' as const,
    variables: undefined,
    submittedAt: 0,
    isPaused: false,
  };
}

// =============================================================================
// Tests
// =============================================================================

describe('AreaCameraLinking', () => {
  let mockMutations: UseAreaMutationsReturn;

  let mockLinkCameraMutateAsync: any;

  let mockUnlinkCameraMutateAsync: any;

  beforeEach(() => {
    vi.clearAllMocks();

    // Setup default mock mutations
    mockLinkCameraMutateAsync = vi.fn().mockResolvedValue({ area_id: 1, camera_id: 'cam-2', linked: true });
    mockUnlinkCameraMutateAsync = vi.fn().mockResolvedValue({ area_id: 1, camera_id: 'cam-1', linked: false });

    mockMutations = {
      createArea: createMockMutation(),
      updateArea: createMockMutation(),
      deleteArea: createMockMutation(),
      linkCamera: createMockMutation({ mutateAsync: mockLinkCameraMutateAsync }),
      unlinkCamera: createMockMutation({ mutateAsync: mockUnlinkCameraMutateAsync }),
    } as UseAreaMutationsReturn;

    vi.mocked(propertyHooks.useAreaMutations).mockReturnValue(mockMutations);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ---------------------------------------------------------------------------
  // Loading State Tests
  // ---------------------------------------------------------------------------

  describe('Loading State', () => {
    it('should show loading state while fetching cameras', () => {
      vi.mocked(cameraHooks.useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: true,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: [],
        total: 0,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: [],
        total: 0,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreaCamerasQuery).mockReturnValue({
        cameras: [],
        count: 0,
        areaName: '',
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<AreaCameraLinking />);

      expect(screen.getByTestId('area-camera-linking-loading')).toBeInTheDocument();
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('should show loading state while fetching properties', () => {
      vi.mocked(cameraHooks.useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: [],
        total: 0,
        isLoading: true,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: [],
        total: 0,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreaCamerasQuery).mockReturnValue({
        cameras: [],
        count: 0,
        areaName: '',
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<AreaCameraLinking />);

      expect(screen.getByTestId('area-camera-linking-loading')).toBeInTheDocument();
    });
  });

  // ---------------------------------------------------------------------------
  // Error State Tests
  // ---------------------------------------------------------------------------

  describe('Error State', () => {
    it('should show error state when cameras fail to load', () => {
      vi.mocked(cameraHooks.useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: false,
        isRefetching: false,
        error: new Error('Failed to load cameras'),
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: [],
        total: 0,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: [],
        total: 0,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreaCamerasQuery).mockReturnValue({
        cameras: [],
        count: 0,
        areaName: '',
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<AreaCameraLinking />);

      expect(screen.getByTestId('area-camera-linking-error')).toBeInTheDocument();
      expect(screen.getByText('Error loading data')).toBeInTheDocument();
      expect(screen.getByText('Failed to load cameras')).toBeInTheDocument();
    });

    it('should show error state when properties fail to load', () => {
      vi.mocked(cameraHooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: [],
        total: 0,
        isLoading: false,
        isError: true,
        error: new Error('Failed to load properties'),
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: [],
        total: 0,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreaCamerasQuery).mockReturnValue({
        cameras: [],
        count: 0,
        areaName: '',
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<AreaCameraLinking />);

      expect(screen.getByTestId('area-camera-linking-error')).toBeInTheDocument();
      expect(screen.getByText('Failed to load properties')).toBeInTheDocument();
    });
  });

  // ---------------------------------------------------------------------------
  // Rendering Tests
  // ---------------------------------------------------------------------------

  describe('Rendering', () => {
    beforeEach(() => {
      vi.mocked(cameraHooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: mockProperties,
        total: 1,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: mockAreas,
        total: 2,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreaCamerasQuery).mockReturnValue({
        cameras: [],
        count: 0,
        areaName: '',
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('should render the component with title and description', () => {
      render(<AreaCameraLinking />);

      expect(screen.getByText('Link Cameras to Areas')).toBeInTheDocument();
      expect(
        screen.getByText(/Select cameras and assign them to areas/)
      ).toBeInTheDocument();
    });

    it('should display all available cameras', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      expect(screen.getByText('Backyard')).toBeInTheDocument();
      expect(screen.getByText('Garage')).toBeInTheDocument();
    });

    it('should display camera folder paths', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByText('/export/foscam/front_door')).toBeInTheDocument();
      });

      expect(screen.getByText('/export/foscam/backyard')).toBeInTheDocument();
      expect(screen.getByText('/export/foscam/garage')).toBeInTheDocument();
    });

    it('should display properties', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });
    });

    it('should show empty state when no cameras exist', async () => {
      vi.mocked(cameraHooks.useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByText('No cameras configured')).toBeInTheDocument();
      });
    });

    it('should show empty state when no properties exist', async () => {
      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: [],
        total: 0,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByText('No properties configured')).toBeInTheDocument();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Camera Selection Tests
  // ---------------------------------------------------------------------------

  describe('Camera Selection', () => {
    beforeEach(() => {
      vi.mocked(cameraHooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: mockProperties,
        total: 1,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: mockAreas,
        total: 2,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreaCamerasQuery).mockReturnValue({
        cameras: [],
        count: 0,
        areaName: '',
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('should toggle camera selection when clicking checkbox', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('camera-checkbox-cam-1')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const checkbox = screen.getByTestId('camera-checkbox-cam-1');

      // Initially unchecked
      expect(checkbox).not.toBeChecked();

      // Click to select
      await user.click(checkbox);
      expect(checkbox).toBeChecked();

      // Click to deselect
      await user.click(checkbox);
      expect(checkbox).not.toBeChecked();
    });

    it('should select all cameras when clicking Select All', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('select-all-cameras')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('select-all-cameras'));

      // All checkboxes should be checked
      expect(screen.getByTestId('camera-checkbox-cam-1')).toBeChecked();
      expect(screen.getByTestId('camera-checkbox-cam-2')).toBeChecked();
      expect(screen.getByTestId('camera-checkbox-cam-3')).toBeChecked();
    });

    it('should deselect all cameras when clicking Clear', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('select-all-cameras')).toBeInTheDocument();
      });

      const user = userEvent.setup();

      // First select all
      await user.click(screen.getByTestId('select-all-cameras'));

      // Then clear
      await user.click(screen.getByTestId('deselect-all-cameras'));

      // All checkboxes should be unchecked
      expect(screen.getByTestId('camera-checkbox-cam-1')).not.toBeChecked();
      expect(screen.getByTestId('camera-checkbox-cam-2')).not.toBeChecked();
      expect(screen.getByTestId('camera-checkbox-cam-3')).not.toBeChecked();
    });
  });

  // ---------------------------------------------------------------------------
  // Property and Area Navigation Tests
  // ---------------------------------------------------------------------------

  describe('Property and Area Navigation', () => {
    beforeEach(() => {
      vi.mocked(cameraHooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: mockProperties,
        total: 1,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: mockAreas,
        total: 2,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreaCamerasQuery).mockReturnValue({
        cameras: [],
        count: 0,
        areaName: '',
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('should expand property to show areas when clicked', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('property-toggle-1')).toBeInTheDocument();
      });

      const user = userEvent.setup();

      // Initially areas are not visible
      expect(screen.queryByTestId('area-item-1')).not.toBeInTheDocument();

      // Click to expand
      await user.click(screen.getByTestId('property-toggle-1'));

      // Areas should now be visible
      await waitFor(() => {
        expect(screen.getByTestId('area-item-1')).toBeInTheDocument();
      });

      // Use testid to verify area items are visible (avoid name collision with camera named "Backyard")
      expect(screen.getByTestId('area-item-1')).toHaveTextContent('Front Yard');
      expect(screen.getByTestId('area-item-2')).toHaveTextContent('Backyard');
    });

    it('should collapse property when clicked again', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('property-toggle-1')).toBeInTheDocument();
      });

      const user = userEvent.setup();

      // Expand
      await user.click(screen.getByTestId('property-toggle-1'));
      await waitFor(() => {
        expect(screen.getByTestId('area-item-1')).toBeInTheDocument();
      });

      // Collapse
      await user.click(screen.getByTestId('property-toggle-1'));
      await waitFor(() => {
        expect(screen.queryByTestId('area-item-1')).not.toBeInTheDocument();
      });
    });

    it('should select an area when clicked', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('property-toggle-1')).toBeInTheDocument();
      });

      const user = userEvent.setup();

      // Expand property
      await user.click(screen.getByTestId('property-toggle-1'));
      await waitFor(() => {
        expect(screen.getByTestId('area-item-1')).toBeInTheDocument();
      });

      // Click on area
      await user.click(screen.getByTestId('area-item-1'));

      // Area should show selected state (check mark in the UI)
      const areaItem = screen.getByTestId('area-item-1');
      expect(areaItem).toHaveClass('border-primary');
    });
  });

  // ---------------------------------------------------------------------------
  // Camera Linking Tests
  // ---------------------------------------------------------------------------

  describe('Camera Linking', () => {
    beforeEach(() => {
      vi.mocked(cameraHooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: mockProperties,
        total: 1,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: mockAreas,
        total: 2,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreaCamerasQuery).mockReturnValue({
        cameras: [],
        count: 0,
        areaName: 'Front Yard',
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('should show link button when cameras are selected and area is chosen', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('camera-checkbox-cam-1')).toBeInTheDocument();
      });

      const user = userEvent.setup();

      // Select a camera
      await user.click(screen.getByTestId('camera-checkbox-cam-1'));

      // Expand property and select an area
      await user.click(screen.getByTestId('property-toggle-1'));
      await waitFor(() => {
        expect(screen.getByTestId('area-item-1')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('area-item-1'));

      // Link button should appear
      await waitFor(() => {
        expect(screen.getByTestId('link-selected-cameras')).toBeInTheDocument();
      });

      expect(screen.getByText(/Link 1 Camera to Area/)).toBeInTheDocument();
    });

    it('should call linkCamera mutation when link button is clicked', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('camera-checkbox-cam-2')).toBeInTheDocument();
      });

      const user = userEvent.setup();

      // Select a camera
      await user.click(screen.getByTestId('camera-checkbox-cam-2'));

      // Expand property and select an area
      await user.click(screen.getByTestId('property-toggle-1'));
      await waitFor(() => {
        expect(screen.getByTestId('area-item-1')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('area-item-1'));

      // Click link button
      await waitFor(() => {
        expect(screen.getByTestId('link-selected-cameras')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('link-selected-cameras'));

      // Mutation should be called
      await waitFor(() => {
        expect(mockLinkCameraMutateAsync).toHaveBeenCalledWith({
          areaId: 1,
          cameraId: 'cam-2',
        });
      });
    });

    it('should show success message after successful link', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('camera-checkbox-cam-2')).toBeInTheDocument();
      });

      const user = userEvent.setup();

      // Select a camera
      await user.click(screen.getByTestId('camera-checkbox-cam-2'));

      // Expand property and select an area
      await user.click(screen.getByTestId('property-toggle-1'));
      await waitFor(() => {
        expect(screen.getByTestId('area-item-1')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('area-item-1'));

      // Click link button
      await waitFor(() => {
        expect(screen.getByTestId('link-selected-cameras')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('link-selected-cameras'));

      // Success message should appear
      await waitFor(() => {
        expect(screen.getByTestId('operation-success')).toBeInTheDocument();
      });

      expect(screen.getByText(/Linked 1 camera\(s\) to area/)).toBeInTheDocument();
    });

    it('should show error message when link fails', async () => {
      mockLinkCameraMutateAsync.mockRejectedValue(new Error('Failed to link camera'));

      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('camera-checkbox-cam-2')).toBeInTheDocument();
      });

      const user = userEvent.setup();

      // Select a camera
      await user.click(screen.getByTestId('camera-checkbox-cam-2'));

      // Expand property and select an area
      await user.click(screen.getByTestId('property-toggle-1'));
      await waitFor(() => {
        expect(screen.getByTestId('area-item-1')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('area-item-1'));

      // Click link button
      await waitFor(() => {
        expect(screen.getByTestId('link-selected-cameras')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('link-selected-cameras'));

      // Error message should appear
      await waitFor(() => {
        expect(screen.getByTestId('operation-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Failed to link camera')).toBeInTheDocument();
    });
  });

  // ---------------------------------------------------------------------------
  // Camera Unlinking Tests
  // ---------------------------------------------------------------------------

  describe('Camera Unlinking', () => {
    beforeEach(() => {
      vi.mocked(cameraHooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: mockProperties,
        total: 1,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: mockAreas,
        total: 2,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreaCamerasQuery).mockReturnValue({
        cameras: mockLinkedCameras,
        count: 1,
        areaName: 'Front Yard',
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('should show linked indicator for cameras already linked to selected area', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('property-toggle-1')).toBeInTheDocument();
      });

      const user = userEvent.setup();

      // Expand property and select an area
      await user.click(screen.getByTestId('property-toggle-1'));
      await waitFor(() => {
        expect(screen.getByTestId('area-item-1')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('area-item-1'));

      // Linked indicator should appear for cam-1
      await waitFor(() => {
        expect(screen.getByTestId('linked-indicator-cam-1')).toBeInTheDocument();
      });
    });

    it('should disable checkbox for already linked cameras', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('property-toggle-1')).toBeInTheDocument();
      });

      const user = userEvent.setup();

      // Expand property and select an area
      await user.click(screen.getByTestId('property-toggle-1'));
      await waitFor(() => {
        expect(screen.getByTestId('area-item-1')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('area-item-1'));

      // Checkbox for linked camera should be disabled
      await waitFor(() => {
        expect(screen.getByTestId('camera-checkbox-cam-1')).toBeDisabled();
      });
    });

    it('should call unlinkCamera mutation when unlink button is clicked', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('property-toggle-1')).toBeInTheDocument();
      });

      const user = userEvent.setup();

      // Expand property and select an area
      await user.click(screen.getByTestId('property-toggle-1'));
      await waitFor(() => {
        expect(screen.getByTestId('area-item-1')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('area-item-1'));

      // Click unlink button
      await waitFor(() => {
        expect(screen.getByTestId('unlink-camera-cam-1')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('unlink-camera-cam-1'));

      // Mutation should be called
      await waitFor(() => {
        expect(mockUnlinkCameraMutateAsync).toHaveBeenCalledWith({
          areaId: 1,
          cameraId: 'cam-1',
        });
      });
    });

    it('should show success message after successful unlink', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('property-toggle-1')).toBeInTheDocument();
      });

      const user = userEvent.setup();

      // Expand property and select an area
      await user.click(screen.getByTestId('property-toggle-1'));
      await waitFor(() => {
        expect(screen.getByTestId('area-item-1')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('area-item-1'));

      // Click unlink button
      await waitFor(() => {
        expect(screen.getByTestId('unlink-camera-cam-1')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('unlink-camera-cam-1'));

      // Success message should appear
      await waitFor(() => {
        expect(screen.getByTestId('operation-success')).toBeInTheDocument();
      });

      expect(screen.getByText('Unlinked camera from area')).toBeInTheDocument();
    });

    it('should show error message when unlink fails', async () => {
      mockUnlinkCameraMutateAsync.mockRejectedValue(new Error('Failed to unlink camera'));

      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('property-toggle-1')).toBeInTheDocument();
      });

      const user = userEvent.setup();

      // Expand property and select an area
      await user.click(screen.getByTestId('property-toggle-1'));
      await waitFor(() => {
        expect(screen.getByTestId('area-item-1')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('area-item-1'));

      // Click unlink button
      await waitFor(() => {
        expect(screen.getByTestId('unlink-camera-cam-1')).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('unlink-camera-cam-1'));

      // Error message should appear
      await waitFor(() => {
        expect(screen.getByTestId('operation-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Failed to unlink camera')).toBeInTheDocument();
    });
  });

  // ---------------------------------------------------------------------------
  // Accessibility Tests
  // ---------------------------------------------------------------------------

  describe('Accessibility', () => {
    beforeEach(() => {
      vi.mocked(cameraHooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: mockProperties,
        total: 1,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: mockAreas,
        total: 2,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreaCamerasQuery).mockReturnValue({
        cameras: [],
        count: 0,
        areaName: '',
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('should have proper data-testid attributes on all interactive elements', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('area-camera-linking')).toBeInTheDocument();
      });

      // Camera items
      expect(screen.getByTestId('camera-item-cam-1')).toBeInTheDocument();
      expect(screen.getByTestId('camera-checkbox-cam-1')).toBeInTheDocument();

      // Selection controls
      expect(screen.getByTestId('select-all-cameras')).toBeInTheDocument();
      expect(screen.getByTestId('deselect-all-cameras')).toBeInTheDocument();

      // Property toggle
      expect(screen.getByTestId('property-toggle-1')).toBeInTheDocument();
    });

    it('should have accessible checkbox labels', async () => {
      render(<AreaCameraLinking />);

      await waitFor(() => {
        expect(screen.getByTestId('camera-item-cam-1')).toBeInTheDocument();
      });

      // Checkbox should be within a label element
      const cameraItem = screen.getByTestId('camera-item-cam-1');
      const label = cameraItem.querySelector('label');
      expect(label).toBeInTheDocument();
      expect(label?.querySelector('input[type="checkbox"]')).toBeInTheDocument();
    });
  });
});
