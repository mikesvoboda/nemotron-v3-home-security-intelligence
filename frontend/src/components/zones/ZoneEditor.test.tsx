/**
 * Tests for ZoneEditor component
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ZoneEditor from './ZoneEditor';
import * as api from '../../services/api';

import type { Camera, Zone, ZoneListResponse } from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchZones: vi.fn(),
  createZone: vi.fn(),
  updateZone: vi.fn(),
  deleteZone: vi.fn(),
  getCameraSnapshotUrl: vi.fn((cameraId: string) => `/api/cameras/${cameraId}/snapshot`),
}));

// Mock ResizeObserver for canvas sizing
const mockResizeObserver = vi.fn();
mockResizeObserver.mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));
window.ResizeObserver = mockResizeObserver;

describe('ZoneEditor', () => {
  const mockCamera: Camera = {
    id: 'cam-1',
    name: 'Front Door Camera',
    folder_path: '/export/foscam/front_door',
    status: 'online',
    created_at: '2025-01-01T00:00:00Z',
    last_seen_at: '2025-01-10T12:00:00Z',
  };

  const mockZones: Zone[] = [
    {
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
    },
    {
      id: 'zone-2',
      camera_id: 'cam-1',
      name: 'Driveway',
      zone_type: 'driveway',
      coordinates: [
        [0.5, 0.5],
        [0.9, 0.5],
        [0.9, 0.9],
        [0.5, 0.9],
      ],
      shape: 'rectangle',
      color: '#10B981',
      enabled: false,
      priority: 5,
      created_at: '2025-01-02T00:00:00Z',
      updated_at: '2025-01-02T00:00:00Z',
    },
  ];

  const mockZoneListResponse: ZoneListResponse = {
    items: mockZones,
    pagination: { total: 2, limit: 50, offset: 0, has_more: false },
  };

  const defaultProps = {
    camera: mockCamera,
    isOpen: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchZones).mockResolvedValue(mockZoneListResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Modal Open/Close', () => {
    it('should render modal when isOpen is true', async () => {
      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByText('Zone Configuration - Front Door Camera')).toBeInTheDocument();
    });

    it('should not render modal when isOpen is false', () => {
      render(<ZoneEditor {...defaultProps} isOpen={false} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('should call onClose when close button is clicked', async () => {
      const onClose = vi.fn();
      render(<ZoneEditor {...defaultProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Find the close button by its position in the header
      const header = screen.getByText('Zone Configuration - Front Door Camera').closest('div');
      const buttons = header?.parentElement?.querySelectorAll('button');
      const xButton = buttons?.[0]; // First button in header should be close

      if (xButton) {
        await userEvent.click(xButton);
        expect(onClose).toHaveBeenCalled();
      }
    });
  });

  describe('Loading Zones', () => {
    it('should show loading state while fetching zones', async () => {
      vi.mocked(api.fetchZones).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Loading zones...')).toBeInTheDocument();
      });
    });

    it('should load zones when modal opens', async () => {
      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(api.fetchZones).toHaveBeenCalledWith('cam-1');
      });
    });

    it('should display loaded zones in the list', async () => {
      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });
      // 'Driveway' appears twice - as zone name and as type badge
      expect(screen.getAllByText('Driveway').length).toBeGreaterThanOrEqual(1);
    });

    it('should display zone count', async () => {
      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Zones (2)')).toBeInTheDocument();
      });
    });

    it('should display error when fetch fails', async () => {
      vi.mocked(api.fetchZones).mockRejectedValue(new Error('Network error'));

      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });
  });

  describe('Drawing Mode Switching', () => {
    it('should show rectangle and polygon drawing buttons', async () => {
      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Zones (2)')).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /Rectangle/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Polygon/i })).toBeInTheDocument();
    });

    it('should enter rectangle drawing mode when rectangle button is clicked', async () => {
      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Zones (2)')).toBeInTheDocument();
      });

      const rectButton = screen.getByRole('button', { name: /Rectangle/i });
      await userEvent.click(rectButton);

      await waitFor(() => {
        expect(screen.getByText('Drawing rectangle...')).toBeInTheDocument();
      });
    });

    it('should enter polygon drawing mode when polygon button is clicked', async () => {
      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Zones (2)')).toBeInTheDocument();
      });

      const polyButton = screen.getByRole('button', { name: /Polygon/i });
      await userEvent.click(polyButton);

      await waitFor(() => {
        expect(screen.getByText('Drawing polygon...')).toBeInTheDocument();
      });
    });

    it('should show cancel button when in drawing mode', async () => {
      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Zones (2)')).toBeInTheDocument();
      });

      const rectButton = screen.getByRole('button', { name: /Rectangle/i });
      await userEvent.click(rectButton);

      await waitFor(() => {
        expect(screen.getByText('Cancel')).toBeInTheDocument();
      });
    });

    it('should exit drawing mode when cancel is clicked', async () => {
      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Zones (2)')).toBeInTheDocument();
      });

      const rectButton = screen.getByRole('button', { name: /Rectangle/i });
      await userEvent.click(rectButton);

      await waitFor(() => {
        expect(screen.getByText('Drawing rectangle...')).toBeInTheDocument();
      });

      const cancelButton = screen.getByText('Cancel');
      await userEvent.click(cancelButton);

      await waitFor(() => {
        // Should be back in view mode with drawing buttons
        expect(screen.getByRole('button', { name: /Rectangle/i })).toBeInTheDocument();
      });
    });

    it('should show color picker in drawing mode', async () => {
      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Zones (2)')).toBeInTheDocument();
      });

      const rectButton = screen.getByRole('button', { name: /Rectangle/i });
      await userEvent.click(rectButton);

      await waitFor(() => {
        expect(screen.getByText('Zone Color')).toBeInTheDocument();
      });
    });
  });

  describe('CRUD Operations', () => {
    it('should toggle zone enabled state', async () => {
      const updatedZone = { ...mockZones[0], enabled: false };
      vi.mocked(api.updateZone).mockResolvedValue(updatedZone);
      vi.mocked(api.fetchZones)
        .mockResolvedValueOnce(mockZoneListResponse)
        .mockResolvedValueOnce({
          items: [updatedZone, mockZones[1]],
          pagination: { total: 2, limit: 50, offset: 0, has_more: false },
        });

      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      // Find the enable/disable button by title
      const toggleButtons = screen.getAllByTitle(/able zone/i);
      await userEvent.click(toggleButtons[0]);

      await waitFor(() => {
        expect(api.updateZone).toHaveBeenCalledWith('cam-1', 'zone-1', { enabled: false });
      });
    });

    it('should open edit form when edit button is clicked', async () => {
      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const editButtons = screen.getAllByTitle('Edit zone');
      await userEvent.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Edit Zone')).toBeInTheDocument();
      });
    });

    it('should update zone when edit form is submitted', async () => {
      const updatedZone = { ...mockZones[0], name: 'Updated Zone Name' };
      vi.mocked(api.updateZone).mockResolvedValue(updatedZone);
      vi.mocked(api.fetchZones)
        .mockResolvedValueOnce(mockZoneListResponse)
        .mockResolvedValueOnce({
          items: [updatedZone, mockZones[1]],
          pagination: { total: 2, limit: 50, offset: 0, has_more: false },
        });

      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const editButtons = screen.getAllByTitle('Edit zone');
      await userEvent.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Edit Zone')).toBeInTheDocument();
      });

      // Update the name
      const nameInput = screen.getByLabelText('Zone Name');
      await userEvent.clear(nameInput);
      await userEvent.type(nameInput, 'Updated Zone Name');

      // Submit the form
      const submitButton = screen.getByRole('button', { name: 'Update Zone' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(api.updateZone).toHaveBeenCalledWith(
          'cam-1',
          'zone-1',
          expect.objectContaining({ name: 'Updated Zone Name' })
        );
      });
    });

    it('should show delete confirmation when delete button is clicked', async () => {
      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByTitle('Delete zone');
      await userEvent.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByText(/Delete zone "Front Door"/)).toBeInTheDocument();
      });
    });

    it('should delete zone when confirmed', async () => {
      vi.mocked(api.deleteZone).mockResolvedValue(undefined);
      vi.mocked(api.fetchZones)
        .mockResolvedValueOnce(mockZoneListResponse)
        .mockResolvedValueOnce({
          items: [mockZones[1]],
          pagination: { total: 1, limit: 50, offset: 0, has_more: false },
        });

      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByTitle('Delete zone');
      await userEvent.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByText(/Delete zone "Front Door"/)).toBeInTheDocument();
      });

      const confirmButton = screen.getByRole('button', { name: 'Delete' });
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(api.deleteZone).toHaveBeenCalledWith('cam-1', 'zone-1');
      });
    });

    it('should cancel delete when cancel button is clicked', async () => {
      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByTitle('Delete zone');
      await userEvent.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByText(/Delete zone "Front Door"/)).toBeInTheDocument();
      });

      // Find the cancel button in the delete confirmation
      const cancelButtons = screen.getAllByRole('button', { name: 'Cancel' });
      // The last Cancel should be in the delete confirmation
      await userEvent.click(cancelButtons[cancelButtons.length - 1]);

      await waitFor(() => {
        expect(screen.queryByText(/Delete zone "Front Door"/)).not.toBeInTheDocument();
      });

      expect(api.deleteZone).not.toHaveBeenCalled();
    });

    it('should display error when delete fails', async () => {
      vi.mocked(api.deleteZone).mockRejectedValue(new Error('Delete failed'));

      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByTitle('Delete zone');
      await userEvent.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByText(/Delete zone "Front Door"/)).toBeInTheDocument();
      });

      const confirmButton = screen.getByRole('button', { name: 'Delete' });
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(screen.getByText('Delete failed')).toBeInTheDocument();
      });
    });
  });

  describe('Form Cancellation', () => {
    it('should return to view mode when form cancel is clicked', async () => {
      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      const editButtons = screen.getAllByTitle('Edit zone');
      await userEvent.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Edit Zone')).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await userEvent.click(cancelButton);

      await waitFor(() => {
        // Should be back in view mode
        expect(screen.getByText('Zones (2)')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('should display error when update fails', async () => {
      vi.mocked(api.updateZone).mockRejectedValue(new Error('Update failed'));

      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      // Try to toggle enabled
      const toggleButtons = screen.getAllByTitle(/able zone/i);
      await userEvent.click(toggleButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Update failed')).toBeInTheDocument();
      });
    });

    it('should allow dismissing error message', async () => {
      vi.mocked(api.fetchZones).mockRejectedValue(new Error('Network error'));

      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      // Find the error dismiss button (X)
      const errorBanner = screen.getByText('Network error').closest('div');
      const dismissButton = errorBanner?.querySelector('button');
      if (dismissButton) {
        await userEvent.click(dismissButton);
      }

      await waitFor(() => {
        expect(screen.queryByText('Network error')).not.toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    it('should display zones list even when empty', async () => {
      vi.mocked(api.fetchZones).mockResolvedValue({
        items: [],
        pagination: { total: 0, limit: 50, offset: 0, has_more: false },
      });

      render(<ZoneEditor {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Zones (0)')).toBeInTheDocument();
      });
    });
  });
});
