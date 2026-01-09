/**
 * Tests for TrashPage component
 *
 * Tests cover:
 * - Loading state
 * - Error state
 * - Empty state when no deleted items
 * - Rendering deleted cameras
 * - Rendering deleted events
 * - Tab switching
 * - Restore confirmation modal
 * - Successful restore
 * - Error handling on restore
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import TrashPage from './TrashPage';
import * as api from '../../services/api';

import type { TrashListResponse } from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../../services/api');
  return {
    ...actual,
    fetchDeletedItems: vi.fn(),
    restoreCamera: vi.fn(),
    restoreEvent: vi.fn(),
  };
});

// Mock the toast hook
const mockToast = {
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
  loading: vi.fn(),
  dismiss: vi.fn(),
  promise: vi.fn(),
};

vi.mock('../../hooks/useToast', () => ({
  useToast: () => mockToast,
}));

// Mock date-fns format to avoid timezone issues in tests
vi.mock('date-fns', async () => {
  const actual = await vi.importActual<typeof import('date-fns')>('date-fns');
  return {
    ...actual,
    format: vi.fn(() => 'Jan 1, 2024 12:00 PM'),
  };
});

describe('TrashPage', () => {
  const mockDeletedCamera: api.DeletedCamera = {
    id: 'front_door',
    name: 'Front Door',
    folder_path: '/cameras/front_door',
    status: 'online' as const,
    created_at: '2024-01-01T00:00:00Z',
    last_seen_at: '2024-01-01T12:00:00Z',
    deleted_at: '2024-01-15T10:00:00Z',
  };

  const mockDeletedEvent: api.DeletedEvent = {
    id: 1,
    camera_id: 'front_door',
    started_at: '2024-01-01T10:00:00Z',
    ended_at: '2024-01-01T10:05:00Z',
    risk_score: 75,
    risk_level: 'high',
    summary: 'Person detected at front door',
    reviewed: false,
    detection_count: 3,
    notes: null,
    deleted_at: '2024-01-15T10:00:00Z',
  };

  const mockEmptyResponse: TrashListResponse = {
    cameras: [],
    events: [],
    camera_count: 0,
    event_count: 0,
  };

  const mockFilledResponse: TrashListResponse = {
    cameras: [mockDeletedCamera],
    events: [mockDeletedEvent],
    camera_count: 1,
    event_count: 1,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('loading state', () => {
    it('should show loading skeleton while fetching data', () => {
      // Create a promise that never resolves to keep loading state
      vi.mocked(api.fetchDeletedItems).mockImplementation(
        () => new Promise(() => {})
      );

      render(<TrashPage />);

      expect(screen.getByTestId('trash-page-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('should show error state when fetch fails', async () => {
      vi.mocked(api.fetchDeletedItems).mockRejectedValueOnce(
        new Error('Network error')
      );

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Error Loading Trash')).toBeInTheDocument();
      expect(mockToast.error).toHaveBeenCalledWith(
        'Failed to load deleted items',
        expect.objectContaining({ description: 'Network error' })
      );
    });

    it('should show retry button on error', async () => {
      vi.mocked(api.fetchDeletedItems).mockRejectedValueOnce(
        new Error('Network error')
      );

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
      });
    });
  });

  describe('empty state', () => {
    it('should show empty state when no deleted items', async () => {
      vi.mocked(api.fetchDeletedItems).mockResolvedValueOnce(mockEmptyResponse);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      expect(screen.getByText('Trash is Empty')).toBeInTheDocument();
      expect(
        screen.getByText(/There are no deleted cameras or events to display/)
      ).toBeInTheDocument();
    });
  });

  describe('rendering deleted items', () => {
    it('should render page title and description', async () => {
      vi.mocked(api.fetchDeletedItems).mockResolvedValueOnce(mockFilledResponse);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      expect(screen.getByRole('heading', { name: 'Trash' })).toBeInTheDocument();
      expect(
        screen.getByText(/View and restore soft-deleted cameras and events/)
      ).toBeInTheDocument();
    });

    it('should render tabs for cameras and events', async () => {
      vi.mocked(api.fetchDeletedItems).mockResolvedValueOnce(mockFilledResponse);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      expect(screen.getByTestId('tab-cameras')).toBeInTheDocument();
      expect(screen.getByTestId('tab-events')).toBeInTheDocument();
    });

    it('should show item counts in tabs', async () => {
      vi.mocked(api.fetchDeletedItems).mockResolvedValueOnce(mockFilledResponse);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      // Each tab should have a count badge
      const camerasTab = screen.getByTestId('tab-cameras');
      const eventsTab = screen.getByTestId('tab-events');

      expect(camerasTab).toHaveTextContent('1');
      expect(eventsTab).toHaveTextContent('1');
    });

    it('should render deleted camera in table', async () => {
      vi.mocked(api.fetchDeletedItems).mockResolvedValueOnce(mockFilledResponse);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      expect(screen.getByTestId('deleted-camera-front_door')).toBeInTheDocument();
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('/cameras/front_door')).toBeInTheDocument();
    });

    it('should render deleted event in events tab', async () => {
      const user = userEvent.setup();
      vi.mocked(api.fetchDeletedItems).mockResolvedValueOnce(mockFilledResponse);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      // Click on events tab
      const eventsTab = screen.getByTestId('tab-events');
      await user.click(eventsTab);

      expect(screen.getByTestId('deleted-event-1')).toBeInTheDocument();
      expect(screen.getByText('Event #1')).toBeInTheDocument();
      expect(screen.getByText('Person detected at front door')).toBeInTheDocument();
    });
  });

  describe('tab switching', () => {
    it('should switch between cameras and events tabs', async () => {
      const user = userEvent.setup();
      vi.mocked(api.fetchDeletedItems).mockResolvedValueOnce(mockFilledResponse);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      // Initially cameras panel should be visible
      expect(screen.getByTestId('cameras-panel')).toBeInTheDocument();

      // Click on events tab
      const eventsTab = screen.getByTestId('tab-events');
      await user.click(eventsTab);

      // Events panel should be visible
      expect(screen.getByTestId('events-panel')).toBeInTheDocument();
    });
  });

  describe('restore functionality', () => {
    it('should open confirmation modal when restore button is clicked', async () => {
      const user = userEvent.setup();
      vi.mocked(api.fetchDeletedItems).mockResolvedValueOnce(mockFilledResponse);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      // Click restore button for camera
      const restoreButton = screen.getByTestId('restore-camera-front_door');
      await user.click(restoreButton);

      // Confirmation modal should appear
      expect(
        screen.getByRole('dialog', { name: /restore camera/i })
      ).toBeInTheDocument();
      // Check the modal description mentions the item name
      expect(
        screen.getByText(/Are you sure you want to restore/)
      ).toBeInTheDocument();
    });

    it('should close confirmation modal when cancel is clicked', async () => {
      const user = userEvent.setup();
      vi.mocked(api.fetchDeletedItems).mockResolvedValueOnce(mockFilledResponse);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      // Open modal
      const restoreButton = screen.getByTestId('restore-camera-front_door');
      await user.click(restoreButton);

      // Click cancel
      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await user.click(cancelButton);

      // Modal should be closed
      await waitFor(() => {
        expect(
          screen.queryByRole('dialog', { name: /restore camera/i })
        ).not.toBeInTheDocument();
      });
    });

    it('should restore camera when confirm is clicked', async () => {
      const user = userEvent.setup();
      vi.mocked(api.fetchDeletedItems).mockResolvedValue(mockFilledResponse);
      vi.mocked(api.restoreCamera).mockResolvedValueOnce({
        ...mockDeletedCamera,
        deleted_at: undefined,
      } as unknown as api.Camera);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      // Open modal
      const restoreButton = screen.getByTestId('restore-camera-front_door');
      await user.click(restoreButton);

      // Click confirm
      const confirmButton = screen.getByTestId('confirm-restore-button');
      await user.click(confirmButton);

      await waitFor(() => {
        expect(api.restoreCamera).toHaveBeenCalledWith('front_door');
      });

      expect(mockToast.success).toHaveBeenCalledWith(
        'Camera "Front Door" restored successfully'
      );
    });

    it('should show error toast when restore fails', async () => {
      const user = userEvent.setup();
      vi.mocked(api.fetchDeletedItems).mockResolvedValue(mockFilledResponse);
      vi.mocked(api.restoreCamera).mockRejectedValueOnce(
        new Error('Restore failed')
      );

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      // Open modal
      const restoreButton = screen.getByTestId('restore-camera-front_door');
      await user.click(restoreButton);

      // Click confirm
      const confirmButton = screen.getByTestId('confirm-restore-button');
      await user.click(confirmButton);

      await waitFor(() => {
        expect(mockToast.error).toHaveBeenCalledWith(
          'Failed to restore',
          expect.objectContaining({ description: 'Restore failed' })
        );
      });
    });

    it('should restore event when confirm is clicked', async () => {
      const user = userEvent.setup();
      vi.mocked(api.fetchDeletedItems).mockResolvedValue(mockFilledResponse);
      vi.mocked(api.restoreEvent).mockResolvedValueOnce({
        ...mockDeletedEvent,
        deleted_at: undefined,
      } as unknown as api.Event);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      // Switch to events tab
      const eventsTab = screen.getByTestId('tab-events');
      await user.click(eventsTab);

      // Open modal
      const restoreButton = screen.getByTestId('restore-event-1');
      await user.click(restoreButton);

      // Click confirm
      const confirmButton = screen.getByTestId('confirm-restore-button');
      await user.click(confirmButton);

      await waitFor(() => {
        expect(api.restoreEvent).toHaveBeenCalledWith(1);
      });

      expect(mockToast.success).toHaveBeenCalledWith(
        'Event #1 restored successfully'
      );
    });
  });

  describe('accessibility', () => {
    it('should have proper heading hierarchy', async () => {
      vi.mocked(api.fetchDeletedItems).mockResolvedValueOnce(mockFilledResponse);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      const heading = screen.getByRole('heading', { level: 1, name: 'Trash' });
      expect(heading).toBeInTheDocument();
    });

    it('should have accessible restore buttons', async () => {
      vi.mocked(api.fetchDeletedItems).mockResolvedValueOnce(mockFilledResponse);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      const restoreButton = screen.getByTestId('restore-camera-front_door');
      expect(restoreButton).toHaveTextContent('Restore');
    });

    it('should have proper modal labeling', async () => {
      const user = userEvent.setup();
      vi.mocked(api.fetchDeletedItems).mockResolvedValueOnce(mockFilledResponse);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      // Open modal
      const restoreButton = screen.getByTestId('restore-camera-front_door');
      await user.click(restoreButton);

      // Modal should have proper aria attributes
      const modal = screen.getByRole('dialog');
      expect(modal).toHaveAttribute('aria-modal', 'true');
    });
  });

  describe('risk level badges', () => {
    it('should display correct risk level styling for high risk', async () => {
      const user = userEvent.setup();
      vi.mocked(api.fetchDeletedItems).mockResolvedValueOnce(mockFilledResponse);

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      // Switch to events tab
      const eventsTab = screen.getByTestId('tab-events');
      await user.click(eventsTab);

      const riskBadge = screen.getByText('high');
      expect(riskBadge).toBeInTheDocument();
      expect(riskBadge).toHaveClass('text-red-400');
    });

    it('should display correct risk level styling for low risk', async () => {
      const user = userEvent.setup();
      const lowRiskEvent: api.DeletedEvent = {
        ...mockDeletedEvent,
        id: 2,
        risk_level: 'low',
        risk_score: 25,
      };

      vi.mocked(api.fetchDeletedItems).mockResolvedValueOnce({
        cameras: [],
        events: [lowRiskEvent],
        camera_count: 0,
        event_count: 1,
      });

      render(<TrashPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-page')).toBeInTheDocument();
      });

      // Switch to events tab
      const eventsTab = screen.getByTestId('tab-events');
      await user.click(eventsTab);

      const riskBadge = screen.getByText('low');
      expect(riskBadge).toBeInTheDocument();
      expect(riskBadge).toHaveClass('text-green-400');
    });
  });
});
