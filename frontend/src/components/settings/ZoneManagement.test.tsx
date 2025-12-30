import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ZoneManagement from './ZoneManagement';
import * as api from '../../services/api';

import type { Camera, Zone } from '../../services/api';

// Mock ResizeObserver for ZoneEditor
const mockResizeObserver = vi.fn(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));
vi.stubGlobal('ResizeObserver', mockResizeObserver);

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchZones: vi.fn(),
  fetchZone: vi.fn(),
  createZone: vi.fn(),
  updateZone: vi.fn(),
  deleteZone: vi.fn(),
  getCameraSnapshotUrl: vi.fn().mockReturnValue('/api/cameras/cam-1/snapshot'),
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

describe('ZoneManagement', () => {
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
      name: 'Entry Point',
      zone_type: 'entry_point',
      coordinates: [
        [0.1, 0.1],
        [0.3, 0.1],
        [0.3, 0.3],
        [0.1, 0.3],
      ],
      shape: 'rectangle',
      color: '#ef4444',
      enabled: true,
      priority: 1,
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
        [0.8, 0.5],
        [0.8, 0.9],
        [0.5, 0.9],
      ],
      shape: 'rectangle',
      color: '#3b82f6',
      enabled: false,
      priority: 0,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    },
  ];

  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial Load', () => {
    it('should show loading state initially', () => {
      vi.mocked(api.fetchZones).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<ZoneManagement camera={mockCamera} onClose={mockOnClose} />);
      expect(screen.getByText('Loading zones...')).toBeInTheDocument();
    });

    it('should load and display zones', async () => {
      vi.mocked(api.fetchZones).mockResolvedValue(mockZones);

      render(<ZoneManagement camera={mockCamera} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Entry Point')).toBeInTheDocument();
      });

      expect(screen.getByText('Driveway')).toBeInTheDocument();
      expect(screen.getByText('Zones (2)')).toBeInTheDocument();
    });

    it('should display camera name in header', async () => {
      vi.mocked(api.fetchZones).mockResolvedValue([]);

      render(<ZoneManagement camera={mockCamera} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Zone Management')).toBeInTheDocument();
      });

      expect(screen.getByText('Front Door Camera')).toBeInTheDocument();
    });

    it('should display error state when fetch fails', async () => {
      vi.mocked(api.fetchZones).mockRejectedValue(new Error('Network error'));

      render(<ZoneManagement camera={mockCamera} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      expect(screen.getByText('Try again')).toBeInTheDocument();
    });

    it('should retry loading zones on error', async () => {
      vi.mocked(api.fetchZones)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce(mockZones);

      render(<ZoneManagement camera={mockCamera} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByText('Try again'));

      await waitFor(() => {
        expect(screen.getByText('Entry Point')).toBeInTheDocument();
      });
    });

    it('should show empty state when no zones exist', async () => {
      vi.mocked(api.fetchZones).mockResolvedValue([]);

      render(<ZoneManagement camera={mockCamera} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('No zones defined')).toBeInTheDocument();
      });
    });
  });

  describe('Close Modal', () => {
    it('should call onClose when close button is clicked', async () => {
      vi.mocked(api.fetchZones).mockResolvedValue([]);

      render(<ZoneManagement camera={mockCamera} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Zone Management')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByLabelText('Close zone management'));

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Toolbar', () => {
    it('should have Rectangle and Polygon draw buttons', async () => {
      vi.mocked(api.fetchZones).mockResolvedValue([]);

      render(<ZoneManagement camera={mockCamera} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Zone Management')).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /Rectangle/ })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Polygon/ })).toBeInTheDocument();
    });
  });

  describe('Zone List', () => {
    it('should display zone type for each zone', async () => {
      vi.mocked(api.fetchZones).mockResolvedValue(mockZones);

      render(<ZoneManagement camera={mockCamera} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Entry Point')).toBeInTheDocument();
      });

      // Zone types are shown in format "entry point - rectangle" and "driveway - rectangle"
      expect(screen.getByText(/entry point - rectangle/i)).toBeInTheDocument();
      expect(screen.getByText(/driveway - rectangle/i)).toBeInTheDocument();
    });

    it('should have edit and delete buttons for each zone', async () => {
      vi.mocked(api.fetchZones).mockResolvedValue(mockZones);

      render(<ZoneManagement camera={mockCamera} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Entry Point')).toBeInTheDocument();
      });

      const editButtons = screen.getAllByTitle('Edit zone');
      const deleteButtons = screen.getAllByTitle('Delete zone');

      expect(editButtons).toHaveLength(2);
      expect(deleteButtons).toHaveLength(2);
    });

    it('should have enable/disable toggle for each zone', async () => {
      vi.mocked(api.fetchZones).mockResolvedValue(mockZones);

      render(<ZoneManagement camera={mockCamera} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Entry Point')).toBeInTheDocument();
      });

      expect(screen.getByTitle('Disable zone')).toBeInTheDocument(); // Enabled zone
      expect(screen.getByTitle('Enable zone')).toBeInTheDocument(); // Disabled zone
    });
  });

  describe('Toggle Zone Enabled', () => {
    it('should toggle zone enabled state', async () => {
      const updatedZone = { ...mockZones[0], enabled: false };
      vi.mocked(api.fetchZones)
        .mockResolvedValueOnce(mockZones)
        .mockResolvedValueOnce([updatedZone, mockZones[1]]);
      vi.mocked(api.updateZone).mockResolvedValue(updatedZone);

      render(<ZoneManagement camera={mockCamera} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Entry Point')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const disableButton = screen.getByTitle('Disable zone');
      await user.click(disableButton);

      await waitFor(() => {
        expect(api.updateZone).toHaveBeenCalledWith('cam-1', 'zone-1', { enabled: false });
      });
    });
  });

  describe('Delete Zone', () => {
    it('should open delete confirmation modal', async () => {
      vi.mocked(api.fetchZones).mockResolvedValue(mockZones);

      render(<ZoneManagement camera={mockCamera} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Entry Point')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const deleteButtons = screen.getAllByTitle('Delete zone');
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Delete Zone' })).toBeInTheDocument();
      });

      expect(screen.getByText(/Are you sure you want to delete/)).toBeInTheDocument();
    });

    it('should delete zone successfully', async () => {
      vi.mocked(api.fetchZones)
        .mockResolvedValueOnce(mockZones)
        .mockResolvedValueOnce([mockZones[1]]);
      vi.mocked(api.deleteZone).mockResolvedValue(undefined);

      render(<ZoneManagement camera={mockCamera} onClose={mockOnClose} />);

      await waitFor(() => {
        expect(screen.getByText('Entry Point')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const deleteButtons = screen.getAllByTitle('Delete zone');
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Delete Zone' })).toBeInTheDocument();
      });

      const confirmButton = screen.getByRole('button', { name: 'Delete Zone' });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(api.deleteZone).toHaveBeenCalledWith('cam-1', 'zone-1');
      });

      await waitFor(() => {
        expect(screen.queryByText('Entry Point')).not.toBeInTheDocument();
      });
    });
  });
});
