import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import CamerasSettings from './CamerasSettings';
import * as hooks from '../../hooks';

import type { UseCameraMutationReturn } from '../../hooks';
import type { Camera } from '../../services/api';

// Mock the hooks module
vi.mock('../../hooks', () => ({
  useCamerasQuery: vi.fn(),
  useCameraMutation: vi.fn(),
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
    },
    {
      id: 'cam-2',
      name: 'Backyard',
      folder_path: '/export/foscam/backyard',
      status: 'offline',
      created_at: '2025-01-01T00:00:00Z',
      last_seen_at: null,
    },
  ];

  let mockMutationReturn: UseCameraMutationReturn;

  beforeEach(() => {
    vi.clearAllMocks();
    mockMutationReturn = createDefaultMutationReturn();
    vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);
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
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      // Camera with null last_seen_at should show "Awaiting first image"
      expect(screen.getByText('Awaiting first image')).toBeInTheDocument(); // For cam-2
    });

    it('should display error state when fetch fails', async () => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: false,
        isRefetching: false,
        error: new Error('Network error'),
        refetch: vi.fn(),
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

      // All action buttons should have 44x44px minimum touch target classes
      [editButton, deleteButton, zonesButton].forEach((button) => {
        expect(button).toHaveClass('min-h-[44px]');
        expect(button).toHaveClass('min-w-[44px]');
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

      // All action buttons should have hover state classes
      [editButton, deleteButton, zonesButton].forEach((button) => {
        expect(button).toHaveClass('hover:bg-gray-800');
      });

      // Edit and zones buttons should turn primary on hover
      expect(editButton).toHaveClass('hover:text-primary');
      expect(zonesButton).toHaveClass('hover:text-primary');

      // Delete button should turn red on hover
      expect(deleteButton).toHaveClass('hover:text-red-500');
    });

    it('should have visible focus indicators on action buttons', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const editButton = screen.getByLabelText('Edit Front Door');
      const deleteButton = screen.getByLabelText('Delete Front Door');
      const zonesButton = screen.getByLabelText('Configure zones for Front Door');

      // All action buttons should have focus ring classes
      [editButton, deleteButton, zonesButton].forEach((button) => {
        expect(button).toHaveClass('focus:outline-none');
        expect(button).toHaveClass('focus:ring-2');
      });

      // Edit and zones buttons should have primary focus ring
      expect(editButton).toHaveClass('focus:ring-primary');
      expect(zonesButton).toHaveClass('focus:ring-primary');

      // Delete button should have red focus ring
      expect(deleteButton).toHaveClass('focus:ring-red-500');
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
        },
      ];

      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: camerasWithError,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
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
});
