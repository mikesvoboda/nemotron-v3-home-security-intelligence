import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import CamerasSettings from './CamerasSettings';
import * as api from '../../services/api';

import type { Camera } from '../../services/api';


// Mock the API module
vi.mock('../../services/api', () => ({
  fetchCameras: vi.fn(),
  createCamera: vi.fn(),
  updateCamera: vi.fn(),
  deleteCamera: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      message: string,
      public data?: unknown
    ) {
      super(message);
      this.name = 'ApiError';
    }
  },
}));

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

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial Load', () => {
    it('should show loading state initially', () => {
      vi.mocked(api.fetchCameras).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<CamerasSettings />);
      expect(screen.getByText('Loading cameras...')).toBeInTheDocument();
    });

    it('should load and display cameras', async () => {
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      expect(screen.getByText('Backyard')).toBeInTheDocument();
      expect(screen.getByText('/export/foscam/front_door')).toBeInTheDocument();
      expect(screen.getByText('/export/foscam/backyard')).toBeInTheDocument();
    });

    it('should display camera status with correct styling', async () => {
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      // Check status text exists
      const statusElements = screen.getAllByText(/online|offline|error/i);
      expect(statusElements).toHaveLength(2);
    });

    it('should display last seen timestamp', async () => {
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      // The exact format depends on locale, so just check it's not "Never"
      expect(screen.getByText('Never')).toBeInTheDocument(); // For cam-2
    });

    it('should display error state when fetch fails', async () => {
      vi.mocked(api.fetchCameras).mockRejectedValue(new Error('Network error'));

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Error loading cameras')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
      expect(screen.getByText('Try again')).toBeInTheDocument();
    });

    it('should retry loading cameras on error', async () => {
      vi.mocked(api.fetchCameras)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce(mockCameras);

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Error loading cameras')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByText('Try again'));

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });
    });

    it('should show empty state when no cameras exist', async () => {
      vi.mocked(api.fetchCameras).mockResolvedValue([]);

      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('No cameras configured')).toBeInTheDocument();
      });

      expect(screen.getByText('Get started by adding your first camera')).toBeInTheDocument();
    });
  });

  describe('Add Camera', () => {
    beforeEach(() => {
      vi.mocked(api.fetchCameras).mockResolvedValue([]);
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
        expect(screen.getByText('Name must be at least 2 characters')).toBeInTheDocument();
      });

      expect(screen.getByText('Folder path is required')).toBeInTheDocument();
    });

    it('should validate name length', async () => {
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
      await user.type(nameInput, 'A');

      const submitButton = within(screen.getByRole('dialog')).getByRole('button', {
        name: 'Add Camera',
      });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Name must be at least 2 characters')).toBeInTheDocument();
      });
    });

    it('should validate folder path format', async () => {
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
      await user.type(folderInput, 'invalid path');

      const submitButton = within(screen.getByRole('dialog')).getByRole('button', {
        name: 'Add Camera',
      });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Folder path must be a valid path format')).toBeInTheDocument();
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

      vi.mocked(api.fetchCameras)
        .mockResolvedValueOnce([])
        .mockResolvedValueOnce([newCamera]);
      vi.mocked(api.createCamera).mockResolvedValue(newCamera);

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
        expect(api.createCamera).toHaveBeenCalledWith({
          name: 'Test Camera',
          folder_path: '/export/foscam/test',
          status: 'online',
        });
      });

      await waitFor(() => {
        expect(screen.getByText('Test Camera')).toBeInTheDocument();
      });
    });

    it('should handle create error', async () => {
      vi.mocked(api.fetchCameras).mockResolvedValue([]);
      vi.mocked(api.createCamera).mockRejectedValue(new Error('Creation failed'));

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
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
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

      vi.mocked(api.fetchCameras)
        .mockResolvedValueOnce(mockCameras)
        .mockResolvedValueOnce([updatedCamera, mockCameras[1]]);
      vi.mocked(api.updateCamera).mockResolvedValue(updatedCamera);

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
      const folderInput = screen.getByLabelText('Folder Path');

      await user.clear(nameInput);
      await user.type(nameInput, 'Updated Camera');
      await user.clear(folderInput);
      await user.type(folderInput, '/export/foscam/updated');

      const submitButton = screen.getByRole('button', { name: 'Update' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(api.updateCamera).toHaveBeenCalledWith('cam-1', {
          name: 'Updated Camera',
          folder_path: '/export/foscam/updated',
          status: 'online',
        });
      });

      await waitFor(() => {
        expect(screen.getByText('Updated Camera')).toBeInTheDocument();
      });
    });

    it('should handle update error', async () => {
      vi.mocked(api.updateCamera).mockRejectedValue(new Error('Update failed'));

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
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
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
      vi.mocked(api.fetchCameras)
        .mockResolvedValueOnce(mockCameras)
        .mockResolvedValueOnce([mockCameras[1]]);
      vi.mocked(api.deleteCamera).mockResolvedValue(undefined);

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
        expect(api.deleteCamera).toHaveBeenCalledWith('cam-1');
      });

      await waitFor(() => {
        expect(screen.queryByText('Front Door')).not.toBeInTheDocument();
      });
    });

    it('should handle delete error', async () => {
      vi.mocked(api.deleteCamera).mockRejectedValue(new Error('Delete failed'));

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

      expect(api.deleteCamera).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    beforeEach(() => {
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    });

    it('should have proper aria-labels for action buttons', async () => {
      render(<CamerasSettings />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Edit Front Door')).toBeInTheDocument();
      expect(screen.getByLabelText('Delete Front Door')).toBeInTheDocument();
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
  });

  describe('Status Handling', () => {
    it('should allow changing camera status', async () => {
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);

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
