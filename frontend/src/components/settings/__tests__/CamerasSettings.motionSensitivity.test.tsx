/**
 * TDD Phase 5: Motion Sensitivity UI Tests
 *
 * These tests WILL FAIL initially since the implementation doesn't exist yet.
 * This follows the RED-GREEN-REFACTOR TDD cycle.
 *
 * Test Requirements:
 * - Motion sensitivity slider appears for RTSP cameras
 * - Motion sensitivity slider hidden for FTP cameras
 * - Slider range is 0-1 with step 0.01
 * - Default value is 0.5
 * - Slider value changes update form state
 * - Low/High labels are displayed
 * - API calls include motion_sensitivity field
 */

import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import * as hooks from '../../../hooks';
import CamerasSettings from '../CamerasSettings';

import type { UseCameraMutationReturn } from '../../../hooks';
import type { Camera } from '../../../services/api';

// Mock the hooks module
vi.mock('../../../hooks', () => ({
  useCamerasQuery: vi.fn(),
  useCameraMutation: vi.fn(),
  useDeletedCamerasQuery: vi.fn(),
  useRestoreCameraMutation: vi.fn(),
}));

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

// Default mock mutation return
const createDefaultMutationReturn = (): UseCameraMutationReturn => ({
  createMutation: createMockMutation<
    Camera,
    Error,
    { name: string; folder_path: string; status: string; motion_sensitivity?: number }
  >() as UseCameraMutationReturn['createMutation'],
  updateMutation: createMockMutation<
    Camera,
    Error,
    {
      id: string;
      data: {
        name?: string;
        folder_path?: string;
        status?: string;
        motion_sensitivity?: number;
      };
    }
  >() as UseCameraMutationReturn['updateMutation'],
  deleteMutation: createMockMutation<void, Error, string>() as UseCameraMutationReturn['deleteMutation'],
});

describe('CamerasSettings - Motion Sensitivity UI (TDD Phase 5)', () => {
  const mockRtspCamera: Camera = {
    id: 'cam-rtsp-1',
    name: 'RTSP Camera',
    folder_path: 'rtsp://192.168.1.100/stream',
    status: 'online',
    created_at: '2025-01-01T00:00:00Z',
    last_seen_at: '2025-01-10T12:00:00Z',
    ingestion_mode: 'rtsp',
    motion_sensitivity: 0.5,
  };

  const mockFtpCamera: Camera = {
    id: 'cam-ftp-1',
    name: 'FTP Camera',
    folder_path: '/export/foscam/front_door',
    status: 'online',
    created_at: '2025-01-01T00:00:00Z',
    last_seen_at: '2025-01-10T12:00:00Z',
    ingestion_mode: 'ftp',
    motion_sensitivity: 0.5,
  };

  let mockMutationReturn: UseCameraMutationReturn;

  beforeEach(() => {
    vi.clearAllMocks();
    mockMutationReturn = createDefaultMutationReturn();
    vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);

    // Mock deleted cameras hooks
    vi.mocked(hooks.useDeletedCamerasQuery).mockReturnValue({
      deletedCameras: [],
      isLoading: false,
      isRefetching: false,
      error: null,
      refetch: vi.fn(),
    });

    vi.mocked(hooks.useRestoreCameraMutation).mockReturnValue({
      restoreMutation: createMockMutation<Camera, Error, string>() as any,
    });
  });

  describe('Motion Sensitivity Slider - RTSP Cameras', () => {
    beforeEach(() => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: [mockRtspCamera],
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });
    });

    it('should display motion sensitivity slider when editing RTSP camera', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('RTSP Camera')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Motion sensitivity slider should be present for RTSP camera
      expect(screen.getByLabelText('Motion Sensitivity')).toBeInTheDocument();
      expect(screen.getByTestId('motion-sensitivity-slider')).toBeInTheDocument();
    });

    it('should display Low and High labels for motion sensitivity slider', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('RTSP Camera')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Check for Low and High labels
      expect(screen.getByText('Low')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
    });

    it('should have correct slider attributes (range 0-1, step 0.01)', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('RTSP Camera')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const slider = screen.getByTestId('motion-sensitivity-slider') ;
      expect(slider).toHaveAttribute('type', 'range');
      expect(slider).toHaveAttribute('min', '0');
      expect(slider).toHaveAttribute('max', '1');
      expect(slider).toHaveAttribute('step', '0.01');
    });

    it('should display default value of 0.5 for new RTSP camera', async () => {
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

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Camera')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Set folder path to RTSP to trigger motion sensitivity display
      const folderInput = screen.getByLabelText('Folder Path');
      await user.type(folderInput, 'rtsp://192.168.1.100/stream');

      await waitFor(() => {
        const slider = screen.getByTestId('motion-sensitivity-slider');
        expect(slider).toHaveAttribute('value', '0.5');
      });
    });

    it('should display current motion_sensitivity value when editing existing RTSP camera', async () => {
      const cameraWithSensitivity: Camera = {
        ...mockRtspCamera,
        motion_sensitivity: 0.75,
      };

      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: [cameraWithSensitivity],
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('RTSP Camera')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const slider = screen.getByTestId('motion-sensitivity-slider');
      expect(slider).toHaveAttribute('value', '0.75');
    });

    it('should update form state when slider value changes', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('RTSP Camera')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const slider = screen.getByTestId('motion-sensitivity-slider');

      // Change slider value using fireEvent (range inputs don't support clear/type)
      fireEvent.change(slider, { target: { value: '0.8' } });

      expect(slider).toHaveAttribute('value', '0.8');
    });

    it('should display current slider value as a number', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('RTSP Camera')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Check that current value is displayed
      expect(screen.getByTestId('motion-sensitivity-value')).toHaveTextContent('0.5');
    });

    it('should send motion_sensitivity in create request for RTSP camera', async () => {
      const newCamera: Camera = {
        id: 'cam-new',
        name: 'New RTSP Camera',
        folder_path: 'rtsp://192.168.1.101/stream',
        status: 'online',
        created_at: '2025-01-10T00:00:00Z',
        last_seen_at: null,
        ingestion_mode: 'rtsp',
        motion_sensitivity: 0.6,
      };

      const mockCreateMutateAsync = vi.fn().mockResolvedValue(newCamera);
      mockMutationReturn.createMutation = createMockMutation({
        mutateAsync: mockCreateMutateAsync,
      });
      vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);

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

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Camera')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText('Camera Name');
      const folderInput = screen.getByLabelText('Folder Path');

      await user.type(nameInput, 'New RTSP Camera');
      await user.type(folderInput, 'rtsp://192.168.1.101/stream');

      // Wait for slider to appear and change its value
      await waitFor(() => {
        expect(screen.getByTestId('motion-sensitivity-slider')).toBeInTheDocument();
      });

      const slider = screen.getByTestId('motion-sensitivity-slider') ;
      // Change slider value using fireEvent (range inputs don't support clear/type)
      fireEvent.change(slider, { target: { value: '0.6' } });

      const submitButton = within(screen.getByRole('dialog')).getByRole('button', {
        name: 'Add Camera',
      });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockCreateMutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'New RTSP Camera',
            folder_path: 'rtsp://192.168.1.101/stream',
            status: 'online',
            motion_sensitivity: 0.6,
          })
        );
      });
    });

    it('should send motion_sensitivity in update request for RTSP camera', async () => {
      const updatedCamera: Camera = {
        ...mockRtspCamera,
        motion_sensitivity: 0.8,
      };

      const mockUpdateMutateAsync = vi.fn().mockResolvedValue(updatedCamera);
      mockMutationReturn.updateMutation = createMockMutation({
        mutateAsync: mockUpdateMutateAsync,
      });
      vi.mocked(hooks.useCameraMutation).mockReturnValue(mockMutationReturn);

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('RTSP Camera')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const slider = screen.getByTestId('motion-sensitivity-slider') ;
      // Change slider value using fireEvent (range inputs don't support clear/type)
      fireEvent.change(slider, { target: { value: '0.8' } });

      const submitButton = screen.getByRole('button', { name: 'Update' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockUpdateMutateAsync).toHaveBeenCalledWith({
          id: 'cam-rtsp-1',
          data: expect.objectContaining({
            motion_sensitivity: 0.8,
          }),
        });
      });
    });
  });

  describe('Motion Sensitivity Slider - FTP Cameras', () => {
    beforeEach(() => {
      vi.mocked(hooks.useCamerasQuery).mockReturnValue({
        cameras: [mockFtpCamera],
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
        isPlaceholderData: false,
      });
    });

    it('should NOT display motion sensitivity slider for FTP camera', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('FTP Camera')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Motion sensitivity slider should NOT be present for FTP camera
      expect(screen.queryByLabelText('Motion Sensitivity')).not.toBeInTheDocument();
      expect(screen.queryByTestId('motion-sensitivity-slider')).not.toBeInTheDocument();
    });

    it('should NOT include motion_sensitivity in create request for FTP camera', async () => {
      const newCamera: Camera = {
        id: 'cam-new-ftp',
        name: 'New FTP Camera',
        folder_path: '/export/foscam/new_camera',
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

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Camera')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText('Camera Name');
      const folderInput = screen.getByLabelText('Folder Path');

      await user.type(nameInput, 'New FTP Camera');
      await user.type(folderInput, '/export/foscam/new_camera');

      // Slider should not appear
      expect(screen.queryByTestId('motion-sensitivity-slider')).not.toBeInTheDocument();

      const submitButton = within(screen.getByRole('dialog')).getByRole('button', {
        name: 'Add Camera',
      });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockCreateMutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'New FTP Camera',
            folder_path: '/export/foscam/new_camera',
            status: 'online',
          })
        );
        // Should NOT include motion_sensitivity
        expect(mockCreateMutateAsync).toHaveBeenCalledWith(
          expect.not.objectContaining({
            motion_sensitivity: expect.anything(),
          })
        );
      });
    });
  });

  describe('RTSP Detection Logic', () => {
    it('should detect RTSP camera by folder_path starting with "rtsp://"', async () => {
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

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Camera')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const folderInput = screen.getByLabelText('Folder Path');

      // Initially no slider (empty folder path)
      expect(screen.queryByTestId('motion-sensitivity-slider')).not.toBeInTheDocument();

      // Type RTSP path - slider should appear
      await user.type(folderInput, 'rtsp://192.168.1.100/stream');

      await waitFor(() => {
        expect(screen.getByTestId('motion-sensitivity-slider')).toBeInTheDocument();
      });
    });

    it('should detect RTSP camera by folder_path starting with "rtsp://" (case insensitive)', async () => {
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

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Camera')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const folderInput = screen.getByLabelText('Folder Path');

      // Type RTSP path with uppercase - slider should appear
      await user.type(folderInput, 'RTSP://192.168.1.100/stream');

      await waitFor(() => {
        expect(screen.getByTestId('motion-sensitivity-slider')).toBeInTheDocument();
      });
    });

    it('should hide slider when folder path is changed from RTSP to FTP', async () => {
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

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Camera')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const folderInput = screen.getByLabelText('Folder Path');

      // Type RTSP path - slider should appear
      await user.type(folderInput, 'rtsp://192.168.1.100/stream');

      await waitFor(() => {
        expect(screen.getByTestId('motion-sensitivity-slider')).toBeInTheDocument();
      });

      // Change to FTP path - slider should disappear
      await user.clear(folderInput);
      await user.type(folderInput, '/export/foscam/camera');

      await waitFor(() => {
        expect(screen.queryByTestId('motion-sensitivity-slider')).not.toBeInTheDocument();
      });
    });
  });
});
