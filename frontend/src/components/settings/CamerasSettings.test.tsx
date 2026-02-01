import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import CamerasSettings from './CamerasSettings';
import * as hooks from '../../hooks';

import type { UseCameraMutationReturn, UseRestoreCameraMutationReturn } from '../../hooks';
import type { Camera } from '../../services/api';

// Mock the hooks module
vi.mock('../../hooks', () => ({
  useCamerasQuery: vi.fn(),
  useCameraMutation: vi.fn(),
  useDeletedCamerasQuery: vi.fn(),
  useRestoreCameraMutation: vi.fn(),
}));

// Mock the useRtspTest hook (NEM-4748)
const mockTestConnectionMutate = vi.fn();
const mockTestConnectionReset = vi.fn();
let mockTestConnectionState = {
  mutate: mockTestConnectionMutate,
  reset: mockTestConnectionReset,
  isPending: false,
  isSuccess: false,
  isError: false,
  data: null as import('../../types/rtsp').RTSPTestResult | null,
};

vi.mock('../../hooks/useRtspTest', () => ({
  useRtspTest: () => ({
    testConnection: mockTestConnectionState,
  }),
}));

// Mock the useOnvifDiscovery hook (NEM-4754)
const mockDiscoverDevicesMutate = vi.fn();
const mockDiscoverDevicesReset = vi.fn();
let mockDiscoverDevicesState = {
  mutate: mockDiscoverDevicesMutate,
  reset: mockDiscoverDevicesReset,
  isPending: false,
  isSuccess: false,
  isError: false,
  isIdle: true,
  data: null as import('../../types/onvif').OnvifDiscoveryResponse | null,
  error: null as Error | null,
};

vi.mock('../../hooks/useOnvifDiscovery', () => ({
  useOnvifDiscovery: () => ({
    discoverDevices: mockDiscoverDevicesState,
  }),
}));

// Helper to create mock mutation object - uses type assertions for TanStack Query compatibility
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

// Default mock values - uses type assertion for TanStack Query mock compatibility
const createDefaultMutationReturn = (): UseCameraMutationReturn => ({
  createMutation: createMockMutation<
    Camera,
    Error,
    { name: string; folder_path: string; status: string }
  >() as UseCameraMutationReturn['createMutation'],
  updateMutation: createMockMutation<
    Camera,
    Error,
    { id: string; data: { name?: string; folder_path?: string; status?: string } }
  >() as UseCameraMutationReturn['updateMutation'],
  deleteMutation: createMockMutation<
    void,
    Error,
    string
  >() as UseCameraMutationReturn['deleteMutation'],
});

describe('CamerasSettings', () => {
  const mockCameras: Camera[] = [
    {
      id: 'cam-1',
      name: 'Front Door',
      folder_path: '/export/foscam/front_door',
      status: 'online',
      created_at: '2025-01-01T00:00:00Z',
      last_seen_at: '2025-01-10T12:00:00Z',
      ingestion_mode: 'ftp',
      motion_sensitivity: 0.5,
    },
    {
      id: 'cam-2',
      name: 'Backyard',
      folder_path: '/export/foscam/backyard',
      status: 'offline',
      created_at: '2025-01-01T00:00:00Z',
      last_seen_at: null,
      ingestion_mode: 'ftp',
      motion_sensitivity: 0.5,
    },
  ];

  let mockMutationReturn: UseCameraMutationReturn;
  let mockRestoreMutationReturn: UseRestoreCameraMutationReturn;

  beforeEach(() => {
    vi.clearAllMocks();
    mockMutationReturn = createDefaultMutationReturn();
    vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);

    // Reset useRtspTest mock state
    mockTestConnectionState = {
      mutate: mockTestConnectionMutate,
      reset: mockTestConnectionReset,
      isPending: false,
      isSuccess: false,
      isError: false,
      data: null,
    };

    // Reset useOnvifDiscovery mock state (NEM-4754)
    mockDiscoverDevicesState = {
      mutate: mockDiscoverDevicesMutate,
      reset: mockDiscoverDevicesReset,
      isPending: false,
      isSuccess: false,
      isError: false,
      isIdle: true,
      data: null,
      error: null,
    };

    // Mock deleted cameras hooks (NEM-3643)
    vi.mocked(hooks.useDeletedCamerasQuery).mockReturnValue({
      deletedCameras: [],
      isLoading: false,
      isRefetching: false,
      error: null,
      refetch: vi.fn(),
    });

    mockRestoreMutationReturn = {
      restoreMutation: createMockMutation<Camera, Error, string>() as UseRestoreCameraMutationReturn['restoreMutation'],
    };
    vi.mocked(hooks.useRestoreCameraMutation).mockReturnValue(mockRestoreMutationReturn);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial Load', () => {
    it('should show loading state initially', () => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: true,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });

      render(<CamerasSettings />);
      expect(screen.getByText('Loading cameras...')).toBeInTheDocument();
    });

    it('should load and display cameras', async () => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      expect(screen.getByText('Backyard')).toBeInTheDocument();
      expect(screen.getByText('/export/foscam/front_door')).toBeInTheDocument();
      expect(screen.getByText('/export/foscam/backyard')).toBeInTheDocument();
    });

    it('should display camera status with correct styling', async () => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      // Check status text exists
      const statusElements = screen.getAllByText(/online|offline|error/i);
      expect(statusElements).toHaveLength(2);
    });

    it('should display last seen timestamp', async () => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      // NEM-3519: Camera with null last_seen_at and offline status shows "Never connected"
      expect(screen.getByText('Never connected')).toBeInTheDocument(); // For cam-2 (offline)
    });

    it('should display status-specific last seen messages (NEM-3519)', async () => {
      const camerasWithDifferentStatuses: Camera[] = [
        {
          id: 'cam-online-no-timestamp',
          name: 'Online Camera No Timestamp',
          folder_path: '/export/foscam/online',
          status: 'online',
          created_at: '2025-01-01T00:00:00Z',
          last_seen_at: null, // Online but no timestamp
          ingestion_mode: 'ftp',
          motion_sensitivity: 0.5,
        },
        {
          id: 'cam-offline-no-timestamp',
          name: 'Offline Camera No Timestamp',
          folder_path: '/export/foscam/offline',
          status: 'offline',
          created_at: '2025-01-01T00:00:00Z',
          last_seen_at: null, // Offline with no timestamp
          ingestion_mode: 'ftp',
          motion_sensitivity: 0.5,
        },
        {
          id: 'cam-error-no-timestamp',
          name: 'Error Camera No Timestamp',
          folder_path: '/export/foscam/error',
          status: 'error',
          created_at: '2025-01-01T00:00:00Z',
          last_seen_at: null, // Error with no timestamp
          ingestion_mode: 'ftp',
          motion_sensitivity: 0.5,
        },
        {
          id: 'cam-unknown-no-timestamp',
          name: 'Unknown Camera No Timestamp',
          folder_path: '/export/foscam/unknown',
          status: 'unknown',
          created_at: '2025-01-01T00:00:00Z',
          last_seen_at: null, // Unknown status
          ingestion_mode: 'ftp',
          motion_sensitivity: 0.5,
        },
      ];

      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: camerasWithDifferentStatuses,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Online Camera No Timestamp')).toBeInTheDocument();
      });

      // NEM-3519: Each status should have an appropriate last seen message
      expect(screen.getByText('Recently active')).toBeInTheDocument(); // Online but no timestamp
      expect(screen.getByText('Never connected')).toBeInTheDocument(); // Offline
      expect(screen.getByText('No data available')).toBeInTheDocument(); // Error
      expect(screen.getByText('Awaiting first image')).toBeInTheDocument(); // Unknown (fallback)
    });

    it('should display error state when fetch fails', async () => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: false,
        isRefetching: false,
        error: new Error('Network error'),
        refetch: vi.fn(),
        isPlaceholderData: false,
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Error loading cameras')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
      expect(screen.getByText('Try again')).toBeInTheDocument();
    });

    it('should retry loading cameras on error', async () => {
      const mockRefetch = vi.fn().mockResolvedValue({ data: mockCameras });

      // Start with error state
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: false,
        isRefetching: false,
        error: new Error('Network error'),
        refetch: mockRefetch,
        isPlaceholderData: false,
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Error loading cameras')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByText('Try again'));

      expect(mockRefetch).toHaveBeenCalled();
    });

    it('should show empty state when no cameras exist', async () => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('No cameras configured')).toBeInTheDocument();
      });

      expect(screen.getByText(/Add your first camera to start monitoring/)).toBeInTheDocument();
    });
  });

  describe('Add Camera', () => {
    beforeEach(() => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });
    });

    it('should open add camera modal', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('No cameras configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const addButton = screen.getAllByText('Add Camera')[0];
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Camera Name')).toBeInTheDocument();
      expect(screen.getByLabelText('Folder Path')).toBeInTheDocument();
    });

    it('should validate required fields', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('No cameras configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Camera')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const dialog = screen.getByRole('dialog');
      const submitButton = within(dialog).getByRole('button', { name: 'Add Camera' });
      await user.click(submitButton);

      await waitFor(() => {
        // Updated to match backend validation (min_length=1)
        expect(screen.getByText('Name is required')).toBeInTheDocument();
      });

      expect(screen.getByText('Folder path is required')).toBeInTheDocument();
    });

    it('should accept single character name (aligned with backend min_length=1)', async () => {
      const newCamera: Camera = {
        id: 'cam-3',
        name: 'A',
        folder_path: '/export/foscam/test',
        status: 'online',
        created_at: '2025-01-10T00:00:00Z',
        last_seen_at: null,
        ingestion_mode: 'ftp',
        motion_sensitivity: 0.5,
      };

      const mockCreateMutateAsync = vi.fn().mockResolvedValue(newCamera);
      mockMutationReturn.createMutation = createMockMutation({
        mutateAsync: mockCreateMutateAsync,
      });
      vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('No cameras configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Camera')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText('Camera Name');
      const folderInput = screen.getByLabelText('Folder Path');

      await user.type(nameInput, 'A');
      await user.type(folderInput, '/export/foscam/test');

      const submitButton = within(screen.getByRole('dialog')).getByRole('button', {
        name: 'Add Camera',
      });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockCreateMutateAsync).toHaveBeenCalledWith(expect.objectContaining({ name: 'A' }));
      });
    });

    it('should validate folder path with path traversal (aligned with backend security)', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('No cameras configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Camera')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText('Camera Name');
      const folderInput = screen.getByLabelText('Folder Path');

      await user.type(nameInput, 'Test Camera');
      await user.type(folderInput, '/export/../etc/passwd');

      const submitButton = within(screen.getByRole('dialog')).getByRole('button', {
        name: 'Add Camera',
      });
      await user.click(submitButton);

      await waitFor(() => {
        // Updated to match backend security validation
        expect(
          screen.getByText('Path traversal (..) is not allowed in folder path')
        ).toBeInTheDocument();
      });
    });

    it('should create a new camera successfully', async () => {
      const newCamera: Camera = {
        id: 'cam-3',
        name: 'Test Camera',
        folder_path: '/export/foscam/test',
        status: 'online',
        created_at: '2025-01-10T00:00:00Z',
        last_seen_at: null,
        ingestion_mode: 'ftp',
        motion_sensitivity: 0.5,
      };

      const mockCreateMutateAsync = vi.fn().mockResolvedValue(newCamera);
      mockMutationReturn.createMutation = createMockMutation({
        mutateAsync: mockCreateMutateAsync,
      });
      vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);

      // After successful creation, the query will return the new camera
      let camerasState: Camera[] = [];
      vi.mocked(hooks.useCamerasQuery).mockImplementation(() => ({
        cameras: camerasState,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      }));

      const { rerender } = render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('No cameras configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Camera')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText('Camera Name');
      const folderInput = screen.getByLabelText('Folder Path');

      await user.type(nameInput, 'Test Camera');
      await user.type(folderInput, '/export/foscam/test');

      const submitButton = within(screen.getByRole('dialog')).getByRole('button', {
        name: 'Add Camera',
      });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockCreateMutateAsync).toHaveBeenCalledWith({
          name: 'Test Camera',
          folder_path: '/export/foscam/test',
          status: 'online',
        });
      });

      // Simulate cache update after mutation
      camerasState = [newCamera];
      rerender(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Test Camera')).toBeInTheDocument();
      });
    });

    it('should handle create error', async () => {
      const mockCreateMutateAsync = vi.fn().mockRejectedValue(new Error('Creation failed'));
      mockMutationReturn.createMutation = createMockMutation({
        mutateAsync: mockCreateMutateAsync,
      });
      vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('No cameras configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Camera')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText('Camera Name');
      const folderInput = screen.getByLabelText('Folder Path');

      await user.type(nameInput, 'Test Camera');
      await user.type(folderInput, '/export/foscam/test');

      const submitButton = within(screen.getByRole('dialog')).getByRole('button', {
        name: 'Add Camera',
      });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Creation failed')).toBeInTheDocument();
      });
    });

    it('should close modal on cancel', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('No cameras configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Camera')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await user.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('Edit Camera', () => {
    beforeEach(() => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });
    });

    it('should open edit modal with camera data', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByDisplayValue('Front Door')).toBeInTheDocument();
      expect(screen.getByDisplayValue('/export/foscam/front_door')).toBeInTheDocument();
    });

    it('should update camera successfully', async () => {
      const updatedCamera: Camera = {
        ...mockCameras[0],
        name: 'Updated Camera',
        folder_path: '/export/foscam/updated',
      };

      const mockUpdateMutateAsync = vi.fn().mockResolvedValue(updatedCamera);
      mockMutationReturn.updateMutation = createMockMutation({
        mutateAsync: mockUpdateMutateAsync,
      });
      vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);

      // Track cameras state for cache simulation
      let camerasState = mockCameras;
      vi.mocked(hooks.useCamerasQuery).mockImplementation(() => ({
        cameras: camerasState,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      }));

      const { rerender } = render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText('Camera Name');
      const folderInput = screen.getByLabelText('Folder Path');

      await user.clear(nameInput);
      await user.type(nameInput, 'Updated Camera');
      await user.clear(folderInput);
      await user.type(folderInput, '/export/foscam/updated');

      const submitButton = screen.getByRole('button', { name: 'Update' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockUpdateMutateAsync).toHaveBeenCalledWith({
          id: 'cam-1',
          data: {
            name: 'Updated Camera',
            folder_path: '/export/foscam/updated',
            status: 'online',
          },
        });
      });

      // Simulate cache update after mutation
      camerasState = [updatedCamera, mockCameras[1]];
      rerender(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Updated Camera')).toBeInTheDocument();
      });
    });

    it('should handle update error', async () => {
      const mockUpdateMutateAsync = vi.fn().mockRejectedValue(new Error('Update failed'));
      mockMutationReturn.updateMutation = createMockMutation({
        mutateAsync: mockUpdateMutateAsync,
      });
      vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText('Camera Name');
      await user.clear(nameInput);
      await user.type(nameInput, 'Updated Camera');

      const submitButton = screen.getByRole('button', { name: 'Update' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Update failed')).toBeInTheDocument();
      });
    });
  });

  describe('Delete Camera', () => {
    beforeEach(() => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });
    });

    it('should open delete confirmation modal', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const deleteButtons = screen.getAllByLabelText(/Delete/);
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        const dialogs = screen.getAllByRole('dialog');
        expect(dialogs.length).toBeGreaterThan(0);
      });

      expect(screen.getByRole('heading', { name: 'Delete Camera' })).toBeInTheDocument();
      expect(screen.getByText(/Are you sure you want to delete/)).toBeInTheDocument();
    });

    it('should delete camera successfully', async () => {
      const mockDeleteMutateAsync = vi.fn().mockResolvedValue(undefined);
      mockMutationReturn.deleteMutation = createMockMutation({
        mutateAsync: mockDeleteMutateAsync,
      });
      vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);

      // Track cameras state for cache simulation
      let camerasState = mockCameras;
      vi.mocked(hooks.useCamerasQuery).mockImplementation(() => ({
        cameras: camerasState,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      }));

      const { rerender } = render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const deleteButtons = screen.getAllByLabelText(/Delete/);
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Delete Camera' })).toBeInTheDocument();
      });

      // Type the camera name to confirm deletion (NEM-3643)
      const confirmInput = screen.getByTestId('delete-confirm-input');
      await user.type(confirmInput, 'Front Door');

      const confirmButton = screen.getByRole('button', { name: 'Delete Camera' });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(mockDeleteMutateAsync).toHaveBeenCalledWith('cam-1');
      });

      // Simulate cache update after mutation
      camerasState = [mockCameras[1]];
      rerender(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.queryByText('Front Door')).not.toBeInTheDocument();
      });
    });

    it('should handle delete error', async () => {
      const mockDeleteMutateAsync = vi.fn().mockRejectedValue(new Error('Delete failed'));
      mockMutationReturn.deleteMutation = createMockMutation({
        mutateAsync: mockDeleteMutateAsync,
      });
      vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const deleteButtons = screen.getAllByLabelText(/Delete/);
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Delete Camera' })).toBeInTheDocument();
      });

      // Type the camera name to confirm deletion (NEM-3643)
      const confirmInput = screen.getByTestId('delete-confirm-input');
      await user.type(confirmInput, 'Front Door');

      const confirmButton = screen.getByRole('button', { name: 'Delete Camera' });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(screen.getByText('Delete failed')).toBeInTheDocument();
      });
    });

    it('should cancel delete operation', async () => {
      const mockDeleteMutateAsync = vi.fn();
      mockMutationReturn.deleteMutation = createMockMutation({
        mutateAsync: mockDeleteMutateAsync,
      });
      vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const deleteButtons = screen.getAllByLabelText(/Delete/);
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Delete Camera' })).toBeInTheDocument();
      });

      // Find cancel button within the delete confirmation modal
      // The delete modal has specific text content that includes "Are you sure you want to delete"
      const dialogs = screen.getAllByRole('dialog');
      const deleteDialog = dialogs.find((dialog) =>
        dialog.textContent?.includes('Are you sure you want to delete')
      );
      expect(deleteDialog).toBeDefined();

      const cancelButton = within(deleteDialog!).getByRole('button', { name: 'Cancel' });
      await user.click(cancelButton);

      await waitFor(() => {
        const deleteHeadings = screen.queryAllByRole('heading', { name: 'Delete Camera' });
        expect(deleteHeadings).toHaveLength(0);
      });

      expect(mockDeleteMutateAsync).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    beforeEach(() => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });
    });

    it('should have proper aria-labels for action buttons', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Edit Front Door')).toBeInTheDocument();
      expect(screen.getByLabelText('Delete Front Door')).toBeInTheDocument();
      expect(screen.getByLabelText('Configure zones for Front Door')).toBeInTheDocument();
    });

    it('should have accessible modal close button', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Close modal')).toBeInTheDocument();
    });

    it('should have WCAG-compliant touch targets (44x44px minimum)', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      // Get action buttons for the first camera
      const editButton = screen.getByLabelText('Edit Front Door');
      const deleteButton = screen.getByLabelText('Delete Front Door');
      const zonesButton = screen.getByLabelText('Configure zones for Front Door');

      // All action buttons should have 44x44px minimum touch target (h-11 w-11 = 44px)
      // IconButton uses h-11 w-11 min-h-11 min-w-11 classes (11 * 0.25rem = 2.75rem = 44px)
      [editButton, deleteButton, zonesButton].forEach((button) => {
        expect(button).toHaveClass('h-11');
        expect(button).toHaveClass('w-11');
        expect(button).toHaveClass('min-h-11');
        expect(button).toHaveClass('min-w-11');
      });
    });

    it('should have visible hover states for action buttons', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const editButton = screen.getByLabelText('Edit Front Door');
      const deleteButton = screen.getByLabelText('Delete Front Door');
      const zonesButton = screen.getByLabelText('Configure zones for Front Door');

      // All action buttons use ghost variant which has hover:bg-gray-800 hover:text-white
      [editButton, deleteButton, zonesButton].forEach((button) => {
        expect(button).toHaveClass('hover:bg-gray-800');
      });

      // Edit and zones buttons should have default hover:text-white from ghost variant
      expect(editButton).toHaveClass('hover:text-white');
      expect(zonesButton).toHaveClass('hover:text-white');

      // Delete button has custom hover:!text-red-500 override
      expect(deleteButton.className).toContain('hover:!text-red-500');
    });

    it('should have visible focus indicators on action buttons', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const editButton = screen.getByLabelText('Edit Front Door');
      const deleteButton = screen.getByLabelText('Delete Front Door');
      const zonesButton = screen.getByLabelText('Configure zones for Front Door');

      // IconButton uses focus-visible instead of focus for better UX
      [editButton, deleteButton, zonesButton].forEach((button) => {
        expect(button).toHaveClass('focus:outline-none');
        expect(button).toHaveClass('focus-visible:ring-2');
      });

      // Edit and zones buttons use default NVIDIA green focus ring from IconButton
      expect(editButton.className).toContain('focus-visible:ring-[#76B900]');
      expect(zonesButton.className).toContain('focus-visible:ring-[#76B900]');

      // Delete button has custom focus-visible:!ring-red-500 override
      expect(deleteButton.className).toContain('focus-visible:!ring-red-500');
    });

    it('should have tooltips on action buttons', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const editButton = screen.getByLabelText('Edit Front Door');
      const deleteButton = screen.getByLabelText('Delete Front Door');
      const zonesButton = screen.getByLabelText('Configure zones for Front Door');

      expect(editButton).toHaveAttribute('title', 'Edit camera settings');
      expect(deleteButton).toHaveAttribute('title', 'Delete camera');
      expect(zonesButton).toHaveAttribute('title', 'Configure detection zones');
    });
  });

  describe('Camera Status Indicators', () => {
    beforeEach(() => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });
    });

    it('should display status indicator dot for online cameras', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const onlineIndicator = screen.getByTestId('camera-status-indicator-cam-1');
      expect(onlineIndicator).toBeInTheDocument();
      expect(onlineIndicator).toHaveClass('bg-green-500');
    });

    it('should display status indicator dot for offline cameras', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Backyard')).toBeInTheDocument();
      });

      const offlineIndicator = screen.getByTestId('camera-status-indicator-cam-2');
      expect(offlineIndicator).toBeInTheDocument();
      expect(offlineIndicator).toHaveClass('bg-gray-500');
    });

    it('should display status indicator dot for error cameras', async () => {
      const camerasWithError: Camera[] = [
        {
          id: 'cam-error',
          name: 'Error Camera',
          folder_path: '/export/foscam/error',
          status: 'error',
          created_at: '2025-01-01T00:00:00Z',
          last_seen_at: null,
          ingestion_mode: 'ftp',
          motion_sensitivity: 0.5,
        },
      ];

      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: camerasWithError,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Error Camera')).toBeInTheDocument();
      });

      const errorIndicator = screen.getByTestId('camera-status-indicator-cam-error');
      expect(errorIndicator).toBeInTheDocument();
      expect(errorIndicator).toHaveClass('bg-red-500');
    });

    it('should have correct styling for status indicator dots', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const indicator = screen.getByTestId('camera-status-indicator-cam-1');
      // Should be a small rounded dot
      expect(indicator).toHaveClass('h-2.5', 'w-2.5', 'rounded-full');
    });
  });

  describe('Status Handling', () => {
    it('should allow changing camera status', async () => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const statusSelect = screen.getByLabelText('Status');
      await user.selectOptions(statusSelect, 'offline');

      expect(statusSelect).toHaveValue('offline');
    });
  });

  describe('Soft Delete UI (NEM-3643)', () => {
    const mockDeletedCameras: Camera[] = [
      {
        id: 'deleted-cam-1',
        name: 'Deleted Front Door',
        folder_path: '/export/foscam/front_door',
        status: 'offline',
        created_at: '2025-01-01T00:00:00Z',
        last_seen_at: '2025-01-15T12:00:00Z',
        ingestion_mode: 'ftp',
        motion_sensitivity: 0.5,
      },
    ];

    beforeEach(() => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });
    });

    it('should show "Show deleted cameras" toggle when deleted cameras exist', async () => {
      vi.mocked(hooks.useDeletedCamerasQuery).mockReturnValue({
        deletedCameras: mockDeletedCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      expect(screen.getByTestId('show-deleted-toggle')).toBeInTheDocument();
      expect(screen.getByText(/Show deleted cameras/)).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument(); // Badge showing count
    });

    it('should hide toggle when no deleted cameras exist', async () => {
      vi.mocked(hooks.useDeletedCamerasQuery).mockReturnValue({
        deletedCameras: [],
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('show-deleted-toggle')).not.toBeInTheDocument();
    });

    it('should toggle deleted cameras section visibility', async () => {
      vi.mocked(hooks.useDeletedCamerasQuery).mockReturnValue({
        deletedCameras: mockDeletedCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();

      // Initially deleted section should be hidden
      expect(screen.queryByTestId('deleted-cameras-section')).not.toBeInTheDocument();

      // Click toggle to show deleted cameras
      await user.click(screen.getByTestId('show-deleted-toggle'));

      await waitFor(() => {
        expect(screen.getByTestId('deleted-cameras-section')).toBeInTheDocument();
      });

      expect(screen.getByText('Deleted Cameras')).toBeInTheDocument();
      expect(screen.getByText('Deleted Front Door')).toBeInTheDocument();

      // Click toggle again to hide
      await user.click(screen.getByTestId('show-deleted-toggle'));

      await waitFor(() => {
        expect(screen.queryByTestId('deleted-cameras-section')).not.toBeInTheDocument();
      });
    });

    it('should show restore button for deleted cameras', async () => {
      vi.mocked(hooks.useDeletedCamerasQuery).mockReturnValue({
        deletedCameras: mockDeletedCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('show-deleted-toggle'));

      await waitFor(() => {
        expect(screen.getByTestId('deleted-cameras-section')).toBeInTheDocument();
      });

      expect(screen.getByTestId('restore-camera-deleted-cam-1')).toBeInTheDocument();
      expect(screen.getByLabelText('Restore Deleted Front Door')).toBeInTheDocument();
    });

    it('should call restore mutation when restore button is clicked', async () => {
      const mockRestoreMutateAsync = vi.fn().mockResolvedValue(mockDeletedCameras[0]);
      mockRestoreMutationReturn.restoreMutation = createMockMutation({
        mutateAsync: mockRestoreMutateAsync,
      }) as UseRestoreCameraMutationReturn['restoreMutation'];
      vi.mocked(hooks.useRestoreCameraMutation).mockReturnValue(mockRestoreMutationReturn);

      vi.mocked(hooks.useDeletedCamerasQuery).mockReturnValue({
        deletedCameras: mockDeletedCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('show-deleted-toggle'));

      await waitFor(() => {
        expect(screen.getByTestId('deleted-cameras-section')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('restore-camera-deleted-cam-1'));

      await waitFor(() => {
        expect(mockRestoreMutateAsync).toHaveBeenCalledWith('deleted-cam-1');
      });
    });

    it('should style deleted cameras with strikethrough', async () => {
      vi.mocked(hooks.useDeletedCamerasQuery).mockReturnValue({
        deletedCameras: mockDeletedCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('show-deleted-toggle'));

      await waitFor(() => {
        expect(screen.getByTestId('deleted-cameras-section')).toBeInTheDocument();
      });

      const deletedCameraName = screen.getByText('Deleted Front Door');
      expect(deletedCameraName).toHaveClass('line-through');
    });

    it('should require typing camera name to confirm delete', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const deleteButtons = screen.getAllByLabelText(/Delete/);
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Delete Camera' })).toBeInTheDocument();
      });

      // Delete button should be disabled initially
      const confirmButton = screen.getByTestId('confirm-delete-button');
      expect(confirmButton).toBeDisabled();

      // Type partial name - button should still be disabled
      const confirmInput = screen.getByTestId('delete-confirm-input');
      await user.type(confirmInput, 'Front');
      expect(confirmButton).toBeDisabled();

      // Type full name - button should be enabled
      await user.clear(confirmInput);
      await user.type(confirmInput, 'Front Door');
      expect(confirmButton).not.toBeDisabled();
    });

    it('should show warning about soft delete behavior', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const deleteButtons = screen.getAllByLabelText(/Delete/);
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Delete Camera' })).toBeInTheDocument();
      });

      // Check for soft delete warning messages
      expect(screen.getByText('This will affect related data')).toBeInTheDocument();
      expect(screen.getByText(/All detections from this camera will be hidden/)).toBeInTheDocument();
      expect(screen.getByText(/Show deleted cameras/)).toBeInTheDocument();
    });
  });

  describe('RTSP Camera Configuration UI (NEM-4742 Phase 1)', () => {
    beforeEach(() => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });
    });

    describe('Ingestion Mode Selector', () => {
      it('should render ingestion mode selector in add camera modal', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        expect(screen.getByLabelText('Ingestion Mode')).toBeInTheDocument();
      });

      it('should show FTP, RTSP, and ONVIF options in ingestion mode selector', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        expect(ingestionModeSelect).toBeInTheDocument();

        // Check for options
        const ftpOption = within(ingestionModeSelect).getByRole('option', { name: /FTP/i });
        const rtspOption = within(ingestionModeSelect).getByRole('option', { name: /RTSP/i });
        const onvifOption = within(ingestionModeSelect).getByRole('option', { name: /ONVIF/i });

        expect(ftpOption).toBeInTheDocument();
        expect(rtspOption).toBeInTheDocument();
        expect(onvifOption).toBeInTheDocument();
      });

      it('should default to FTP ingestion mode', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        expect(ingestionModeSelect).toHaveValue('ftp');
      });

      it('should allow changing ingestion mode to RTSP', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        expect(ingestionModeSelect).toHaveValue('rtsp');
      });

      it('should allow changing ingestion mode to ONVIF', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'onvif');

        expect(ingestionModeSelect).toHaveValue('onvif');
      });
    });

    describe('RTSP Configuration Section Visibility', () => {
      it('should hide RTSP section when ingestion_mode is FTP', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        // RTSP fields should not be visible when FTP is selected
        expect(screen.queryByLabelText('RTSP URL')).not.toBeInTheDocument();
        expect(screen.queryByLabelText('RTSP Username')).not.toBeInTheDocument();
        expect(screen.queryByLabelText('RTSP Password')).not.toBeInTheDocument();
      });

      it('should show RTSP section when ingestion_mode is RTSP', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP URL')).toBeInTheDocument();
        });

        expect(screen.getByLabelText('RTSP Username')).toBeInTheDocument();
        expect(screen.getByLabelText('RTSP Password')).toBeInTheDocument();
      });

      it('should show RTSP section when ingestion_mode is ONVIF', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'onvif');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP URL')).toBeInTheDocument();
        });

        expect(screen.getByLabelText('RTSP Username')).toBeInTheDocument();
        expect(screen.getByLabelText('RTSP Password')).toBeInTheDocument();
      });
    });

    describe('RTSP URL Field', () => {
      it('should render RTSP URL input with placeholder', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP URL')).toBeInTheDocument();
        });

        const rtspUrlInput = screen.getByLabelText('RTSP URL');
        expect(rtspUrlInput).toHaveAttribute('placeholder', 'rtsp://192.168.1.100:554/stream1');
      });

      it('should accept valid RTSP URL input', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP URL')).toBeInTheDocument();
        });

        const rtspUrlInput = screen.getByLabelText('RTSP URL');
        await user.type(rtspUrlInput, 'rtsp://192.168.1.100:554/stream1');

        expect(rtspUrlInput).toHaveValue('rtsp://192.168.1.100:554/stream1');
      });

      it('should validate RTSP URL format', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP URL')).toBeInTheDocument();
        });

        const rtspUrlInput = screen.getByLabelText('RTSP URL');
        const nameInput = screen.getByLabelText('Camera Name');
        const folderInput = screen.getByLabelText('Folder Path');

        await user.type(nameInput, 'Test Camera');
        await user.type(folderInput, '/export/cameras/test');
        await user.type(rtspUrlInput, 'http://192.168.1.100/stream'); // Invalid (not rtsp://)

        const submitButton = within(screen.getByRole('dialog')).getByRole('button', {
          name: 'Add Camera',
        });
        await user.click(submitButton);

        await waitFor(() => {
          expect(screen.getByText(/must use rtsp:\/\/ or rtsps:\/\//i)).toBeInTheDocument();
        });
      });

      it('should require RTSP URL when ingestion_mode is rtsp', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        const nameInput = screen.getByLabelText('Camera Name');
        const folderInput = screen.getByLabelText('Folder Path');

        await user.type(nameInput, 'Test Camera');
        await user.type(folderInput, '/export/cameras/test');
        // Do not fill in RTSP URL

        const submitButton = within(screen.getByRole('dialog')).getByRole('button', {
          name: 'Add Camera',
        });
        await user.click(submitButton);

        await waitFor(() => {
          expect(screen.getByText(/RTSP URL is required/i)).toBeInTheDocument();
        });
      });
    });

    describe('RTSP Username Field', () => {
      it('should render RTSP Username input', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP Username')).toBeInTheDocument();
        });

        const usernameInput = screen.getByLabelText('RTSP Username');
        expect(usernameInput).toHaveAttribute('placeholder', 'admin');
      });

      it('should accept username input', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP Username')).toBeInTheDocument();
        });

        const usernameInput = screen.getByLabelText('RTSP Username');
        await user.type(usernameInput, 'admin');

        expect(usernameInput).toHaveValue('admin');
      });

      it('should mark RTSP Username as optional', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP Username')).toBeInTheDocument();
        });

        const usernameInput = screen.getByLabelText('RTSP Username');
        expect(usernameInput).not.toBeRequired();
      });
    });

    describe('RTSP Password Field', () => {
      it('should render RTSP Password as PasswordInput component', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP Password')).toBeInTheDocument();
        });

        const passwordInput = screen.getByLabelText('RTSP Password');
        expect(passwordInput).toHaveAttribute('type', 'password');
      });

      it('should have password visibility toggle button', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP Password')).toBeInTheDocument();
        });

        const toggleButton = screen.getByRole('button', {
          name: /show password/i,
        });
        expect(toggleButton).toBeInTheDocument();
      });

      it('should accept password input', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP Password')).toBeInTheDocument();
        });

        const passwordInput = screen.getByLabelText('RTSP Password');
        await user.type(passwordInput, 'secretpassword123');

        expect(passwordInput).toHaveValue('secretpassword123');
      });

      it('should toggle password visibility when toggle button is clicked', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP Password')).toBeInTheDocument();
        });

        const passwordInput = screen.getByLabelText('RTSP Password');
        const showButton = screen.getByRole('button', {
          name: /show password/i,
        });

        expect(passwordInput).toHaveAttribute('type', 'password');

        await user.click(showButton);

        expect(passwordInput).toHaveAttribute('type', 'text');
      });

      it('should mark RTSP Password as optional', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP Password')).toBeInTheDocument();
        });

        const passwordInput = screen.getByLabelText('RTSP Password');
        expect(passwordInput).not.toBeRequired();
      });
    });

    describe('Form Submission with RTSP Fields', () => {
      it('should submit form with RTSP fields when creating camera', async () => {
        const newCamera: Camera = {
          id: 'rtsp-camera',
          name: 'RTSP Test Camera',
          folder_path: '/export/cameras/rtsp1',
          status: 'online',
          created_at: '2025-01-31T00:00:00Z',
          last_seen_at: null,
          ingestion_mode: 'rtsp',
          rtsp_url: 'rtsp://192.168.1.100:554/stream1',
          rtsp_username: 'admin',
          rtsp_password: 'password123', // pragma: allowlist secret
          motion_sensitivity: 0.5,
        };

        const mockCreateMutateAsync = vi.fn().mockResolvedValue(newCamera);
        mockMutationReturn.createMutation = createMockMutation({
          mutateAsync: mockCreateMutateAsync,
        });
        vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);

        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP URL')).toBeInTheDocument();
        });

        const nameInput = screen.getByLabelText('Camera Name');
        const folderInput = screen.getByLabelText('Folder Path');
        const rtspUrlInput = screen.getByLabelText('RTSP URL');
        const usernameInput = screen.getByLabelText('RTSP Username');
        const passwordInput = screen.getByLabelText('RTSP Password');

        await user.type(nameInput, 'RTSP Test Camera');
        await user.type(folderInput, '/export/cameras/rtsp1');
        await user.type(rtspUrlInput, 'rtsp://192.168.1.100:554/stream1');
        await user.type(usernameInput, 'admin');
        await user.type(passwordInput, 'password123');

        const submitButton = within(screen.getByRole('dialog')).getByRole('button', {
          name: 'Add Camera',
        });
        await user.click(submitButton);

        await waitFor(() => {
          expect(mockCreateMutateAsync).toHaveBeenCalledWith({
            name: 'RTSP Test Camera',
            folder_path: '/export/cameras/rtsp1',
            status: 'online',
            ingestion_mode: 'rtsp',
            rtsp_url: 'rtsp://192.168.1.100:554/stream1',
            rtsp_username: 'admin',
            rtsp_password: 'password123', // pragma: allowlist secret
            motion_sensitivity: 0.5,
          });
        });
      });

      it('should submit form without credentials when omitted', async () => {
        const newCamera: Camera = {
          id: 'rtsp-camera',
          name: 'RTSP Test Camera',
          folder_path: '/export/cameras/rtsp1',
          status: 'online',
          created_at: '2025-01-31T00:00:00Z',
          last_seen_at: null,
          ingestion_mode: 'rtsp',
          rtsp_url: 'rtsp://192.168.1.100:554/stream1',
          motion_sensitivity: 0.5,
        };

        const mockCreateMutateAsync = vi.fn().mockResolvedValue(newCamera);
        mockMutationReturn.createMutation = createMockMutation({
          mutateAsync: mockCreateMutateAsync,
        });
        vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);

        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP URL')).toBeInTheDocument();
        });

        const nameInput = screen.getByLabelText('Camera Name');
        const folderInput = screen.getByLabelText('Folder Path');
        const rtspUrlInput = screen.getByLabelText('RTSP URL');

        await user.type(nameInput, 'RTSP Test Camera');
        await user.type(folderInput, '/export/cameras/rtsp1');
        await user.type(rtspUrlInput, 'rtsp://192.168.1.100:554/stream1');

        const submitButton = within(screen.getByRole('dialog')).getByRole('button', {
          name: 'Add Camera',
        });
        await user.click(submitButton);

        await waitFor(() => {
          expect(mockCreateMutateAsync).toHaveBeenCalledWith({
            name: 'RTSP Test Camera',
            folder_path: '/export/cameras/rtsp1',
            status: 'online',
            ingestion_mode: 'rtsp',
            rtsp_url: 'rtsp://192.168.1.100:554/stream1',
            motion_sensitivity: 0.5,
          });
        });
      });
    });
  });

  describe('RTSP Connection Testing UI (NEM-4748 Phase 2)', () => {
    beforeEach(() => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });
    });

    describe('Test Connection Button', () => {
      it('should render "Test Connection" button when ingestion_mode is RTSP', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByRole('button', { name: /test connection/i })).toBeInTheDocument();
        });
      });

      it('should not render "Test Connection" button when ingestion_mode is FTP', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        // Should not show test button for FTP mode (default)
        expect(screen.queryByRole('button', { name: /test connection/i })).not.toBeInTheDocument();
      });

      it('should render "Test Connection" button when ingestion_mode is ONVIF', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'onvif');

        await waitFor(() => {
          expect(screen.getByRole('button', { name: /test connection/i })).toBeInTheDocument();
        });
      });

      it('should have accessible button label', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          const testButton = screen.getByRole('button', { name: /test connection/i });
          expect(testButton).toHaveAccessibleName();
        });
      });
    });

    describe('Test Connection Action', () => {
      it('should trigger test when button is clicked', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP URL')).toBeInTheDocument();
        });

        const rtspUrlInput = screen.getByLabelText('RTSP URL');
        await user.type(rtspUrlInput, 'rtsp://192.168.1.100:554/stream1');

        const testButton = screen.getByRole('button', { name: /test connection/i });
        await user.click(testButton);

        await waitFor(() => {
          expect(mockTestConnectionMutate).toHaveBeenCalledWith({
            rtsp_url: 'rtsp://192.168.1.100:554/stream1',
            username: undefined,
            password: undefined,
          });
        });
      });

      it('should include credentials in test request when provided', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP URL')).toBeInTheDocument();
        });

        const rtspUrlInput = screen.getByLabelText('RTSP URL');
        const usernameInput = screen.getByLabelText('RTSP Username');
        const passwordInput = screen.getByLabelText('RTSP Password');

        await user.type(rtspUrlInput, 'rtsp://192.168.1.100:554/stream1');
        await user.type(usernameInput, 'admin');
        await user.type(passwordInput, 'password123');

        const testButton = screen.getByRole('button', { name: /test connection/i });
        await user.click(testButton);

        await waitFor(() => {
          expect(mockTestConnectionMutate).toHaveBeenCalledWith({
            rtsp_url: 'rtsp://192.168.1.100:554/stream1',
            username: 'admin',
            password: 'password123', // pragma: allowlist secret
          });
        });
      });

      it('should disable test button when RTSP URL is empty', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          const testButton = screen.getByRole('button', { name: /test connection/i });
          expect(testButton).toBeDisabled();
        });
      });

      it('should enable test button when RTSP URL is provided', async () => {
        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByLabelText('RTSP URL')).toBeInTheDocument();
        });

        const rtspUrlInput = screen.getByLabelText('RTSP URL');
        await user.type(rtspUrlInput, 'rtsp://192.168.1.100:554/stream1');

        await waitFor(() => {
          const testButton = screen.getByRole('button', { name: /test connection/i });
          expect(testButton).not.toBeDisabled();
        });
      });
    });

    describe('Connection Test Result Display', () => {
      it('should display ConnectionStatusCard when test is in progress', async () => {
        // Set mock state for isPending
        mockTestConnectionState.isPending = true;

        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          // Should show loading state
          expect(screen.getByText(/testing connection/i)).toBeInTheDocument();
        });
      });

      it('should display success result with capabilities', async () => {
        const mockResult = {
          success: true,
          latency_ms: 245,
          capabilities: {
            video: true,
            audio: true,
            ptz: false,
            resolution: '1920x1080',
            codec: 'H.264',
            fps: 30,
          },
          error_message: null,
        };

        // Set mock state for success
        mockTestConnectionState.isPending = false;
        mockTestConnectionState.isSuccess = true;
        mockTestConnectionState.data = mockResult;

        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          // Should show success message
          expect(screen.getByText(/connection successful/i)).toBeInTheDocument();
          expect(screen.getByText(/245.*ms/i)).toBeInTheDocument();
          expect(screen.getByText(/1920x1080/i)).toBeInTheDocument();
        });
      });

      it('should display error result with error message', async () => {
        const mockResult = {
          success: false,
          latency_ms: null,
          capabilities: null,
          error_message: 'Connection timeout - stream did not respond within 5 seconds',
        };

        // Set mock state for error result
        mockTestConnectionState.isPending = false;
        mockTestConnectionState.isSuccess = true;
        mockTestConnectionState.data = mockResult;

        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          // Should show error message
          expect(screen.getByText(/connection failed/i)).toBeInTheDocument();
          expect(screen.getByText(/timeout/i)).toBeInTheDocument();
        });
      });

      it('should clear result when RTSP URL is changed', async () => {
        const mockResult = {
          success: true,
          latency_ms: 245,
          capabilities: {
            video: true,
            audio: false,
            ptz: false,
            resolution: '1920x1080',
            codec: 'H.264',
            fps: 30,
          },
          error_message: null,
        };

        // Set mock state for success
        mockTestConnectionState.isPending = false;
        mockTestConnectionState.isSuccess = true;
        mockTestConnectionState.data = mockResult;

        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByText(/connection successful/i)).toBeInTheDocument();
        });

        // Clear the reset mock before changing URL to track new calls
        mockTestConnectionReset.mockClear();

        // Change RTSP URL
        const rtspUrlInput = screen.getByLabelText('RTSP URL');
        await user.clear(rtspUrlInput);
        await user.type(rtspUrlInput, 'rtsp://different.url:554/stream');

        // Reset should be called when URL changes (the useEffect triggers reset)
        await waitFor(() => {
          expect(mockTestConnectionReset).toHaveBeenCalled();
        });
      });
    });

    describe('Button State During Test', () => {
      it('should disable test button while test is in progress', async () => {
        // Set mock state for isPending
        mockTestConnectionState.isPending = true;

        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          const testButton = screen.getByRole('button', { name: /testing/i });
          expect(testButton).toBeDisabled();
        });
      });

      it('should show loading text on button during test', async () => {
        // Set mock state for isPending
        mockTestConnectionState.isPending = true;

        render(<CamerasSettings />);

        await waitFor(() => {
          expect(screen.getByText('No cameras configured')).toBeInTheDocument();
        });

        const user = userEvent.setup();
        await user.click(screen.getAllByText('Add Camera')[0]);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        const ingestionModeSelect = screen.getByLabelText('Ingestion Mode');
        await user.selectOptions(ingestionModeSelect, 'rtsp');

        await waitFor(() => {
          expect(screen.getByRole('button', { name: /testing/i })).toBeInTheDocument();
        });
      });
    });
  });
});
