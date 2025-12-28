import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import AlertsPage from './AlertsPage';
import * as api from '../../services/api';

import type { Camera, Event, EventListResponse } from '../../services/api';

// Mock API module
vi.mock('../../services/api');

describe('AlertsPage', () => {
  const mockCameras: Camera[] = [
    {
      id: 'camera-1',
      name: 'Front Door',
      folder_path: '/path/to/front',
      status: 'online',
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T12:00:00Z',
    },
    {
      id: 'camera-2',
      name: 'Back Yard',
      folder_path: '/path/to/back',
      status: 'online',
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T12:00:00Z',
    },
  ];

  const mockHighRiskEvents: Event[] = [
    {
      id: 1,
      camera_id: 'camera-1',
      started_at: '2024-01-01T10:00:00Z',
      ended_at: '2024-01-01T10:02:00Z',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Person detected near entrance',
      reviewed: false,
      detection_count: 5,
      notes: null,
    },
  ];

  const mockCriticalRiskEvents: Event[] = [
    {
      id: 2,
      camera_id: 'camera-2',
      started_at: '2024-01-01T11:00:00Z',
      ended_at: '2024-01-01T11:01:00Z',
      risk_score: 90,
      risk_level: 'critical',
      summary: 'Unknown person at door',
      reviewed: false,
      detection_count: 8,
      notes: null,
    },
  ];

  const mockHighResponse: EventListResponse = {
    events: mockHighRiskEvents,
    count: 1,
    limit: 20,
    offset: 0,
  };

  const mockCriticalResponse: EventListResponse = {
    events: mockCriticalRiskEvents,
    count: 1,
    limit: 20,
    offset: 0,
  };

  const mockEmptyResponse: EventListResponse = {
    events: [],
    count: 0,
    limit: 20,
    offset: 0,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
  });

  describe('Rendering', () => {
    it('renders the alerts page header', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      expect(screen.getByText('Alerts')).toBeInTheDocument();
      expect(
        screen.getByText('High and critical risk events requiring attention')
      ).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.queryByText('Loading alerts...')).not.toBeInTheDocument();
      });
    });

    it('displays loading state initially', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      expect(screen.getByText('Loading alerts...')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.queryByText('Loading alerts...')).not.toBeInTheDocument();
      });
    });

    it('displays alerts after loading', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      expect(screen.getByText('Unknown person at door')).toBeInTheDocument();
    });

    it('displays alert count', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('2 alerts found')).toBeInTheDocument();
      });
    });

    it('displays risk summary badges', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Check for risk badges with counts
      expect(screen.getByText('1', { selector: '.text-red-400' })).toBeInTheDocument(); // Critical
      expect(screen.getByText('1', { selector: '.text-orange-400' })).toBeInTheDocument(); // High
    });
  });

  describe('Empty State', () => {
    it('shows friendly placeholder when no alerts exist', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockEmptyResponse)
        .mockResolvedValueOnce(mockEmptyResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('No Alerts at This Time')).toBeInTheDocument();
      });

      expect(
        screen.getByText('There are no high or critical risk events to review. Keep up the good work!')
      ).toBeInTheDocument();
    });

    it('shows filtered placeholder when filter returns no results', async () => {
      // Mock will be called multiple times: initial load + after filter change
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEmptyResponse);

      const user = userEvent.setup();
      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('No Alerts at This Time')).toBeInTheDocument();
      });

      // Change filter to critical only
      const filterSelect = screen.getByLabelText('Filter by severity:');
      await user.selectOptions(filterSelect, 'critical');

      await waitFor(() => {
        expect(
          screen.getByText('There are no critical risk events to review.')
        ).toBeInTheDocument();
      });
    });
  });

  describe('Filtering', () => {
    it('displays severity filter dropdown', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      const filterSelect = screen.getByLabelText('Filter by severity:');
      expect(filterSelect).toBeInTheDocument();
    });

    it('filters by critical risk level', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Mock the next set of API calls for filtered results
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const filterSelect = screen.getByLabelText('Filter by severity:');
      await user.selectOptions(filterSelect, 'critical');

      await waitFor(() => {
        expect(screen.getByText('Unknown person at door')).toBeInTheDocument();
      });

      // High risk event should not be visible with critical filter
      expect(screen.queryByText('Person detected near entrance')).not.toBeInTheDocument();
    });

    it('filters by high risk level', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Unknown person at door')).toBeInTheDocument();
      });

      // Mock the next set of API calls for filtered results
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const filterSelect = screen.getByLabelText('Filter by severity:');
      await user.selectOptions(filterSelect, 'high');

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Critical risk event should not be visible with high filter
      expect(screen.queryByText('Unknown person at door')).not.toBeInTheDocument();
    });
  });

  describe('Refresh', () => {
    it('displays refresh button', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      expect(screen.getByText('Refresh')).toBeInTheDocument();
    });

    it('refresh button is disabled while loading', () => {
      vi.mocked(api.fetchEvents).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<AlertsPage />);

      const refreshButton = screen.getByText('Refresh').closest('button');
      expect(refreshButton).toBeDisabled();
    });
  });

  describe('Error Handling', () => {
    it('displays error message when fetching alerts fails', async () => {
      vi.mocked(api.fetchEvents).mockRejectedValue(new Error('Network error'));

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Error Loading Alerts')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('handles camera fetch errors gracefully', async () => {
      vi.mocked(api.fetchCameras).mockRejectedValue(new Error('Camera fetch failed'));
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      // Should still load alerts
      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Camera name should fall back to 'Unknown Camera'
      expect(screen.getAllByText('Unknown Camera').length).toBeGreaterThan(0);
    });
  });

  describe('Pagination', () => {
    it('displays pagination controls when there are multiple pages', async () => {
      const manyHighEvents: Event[] = Array.from({ length: 15 }, (_, i) => ({
        id: i + 1,
        camera_id: 'camera-1',
        started_at: `2024-01-01T${String(i).padStart(2, '0')}:00:00Z`,
        ended_at: null,
        risk_score: 75,
        risk_level: 'high',
        summary: `High risk event ${i + 1}`,
        reviewed: false,
        detection_count: 1,
        notes: null,
      }));

      const manyCriticalEvents: Event[] = Array.from({ length: 15 }, (_, i) => ({
        id: i + 20,
        camera_id: 'camera-2',
        started_at: `2024-01-01T${String(i + 15).padStart(2, '0')}:00:00Z`,
        ended_at: null,
        risk_score: 90,
        risk_level: 'critical',
        summary: `Critical event ${i + 1}`,
        reviewed: false,
        detection_count: 1,
        notes: null,
      }));

      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce({
          events: manyHighEvents,
          count: 15,
          limit: 20,
          offset: 0,
        })
        .mockResolvedValueOnce({
          events: manyCriticalEvents,
          count: 15,
          limit: 20,
          offset: 0,
        });

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('30 alerts found')).toBeInTheDocument();
      });

      // Should show pagination controls
      expect(screen.getByLabelText('Previous page')).toBeInTheDocument();
      expect(screen.getByLabelText('Next page')).toBeInTheDocument();
      expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
    });

    it('does not display pagination when all alerts fit on one page', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('2 alerts found')).toBeInTheDocument();
      });

      // Should not show pagination controls
      expect(screen.queryByLabelText('Previous page')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Next page')).not.toBeInTheDocument();
    });
  });

  describe('Event Card Integration', () => {
    it('calls onViewEventDetails when View Details is clicked', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const handleViewDetails = vi.fn();
      const user = userEvent.setup();

      render(<AlertsPage onViewEventDetails={handleViewDetails} />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      const viewButtons = screen.getAllByText('View Details');
      await user.click(viewButtons[0]);

      expect(handleViewDetails).toHaveBeenCalled();
    });

    it('displays camera names in event cards', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      expect(screen.getByText('Back Yard')).toBeInTheDocument();
    });
  });

  describe('Singular/Plural Alert Count', () => {
    it('displays singular "alert" when count is 1', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockEmptyResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('1 alert found')).toBeInTheDocument();
      });
    });

    it('displays plural "alerts" when count is not 1', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('2 alerts found')).toBeInTheDocument();
      });
    });

    it('displays "0 alerts found" when empty', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockEmptyResponse)
        .mockResolvedValueOnce(mockEmptyResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('0 alerts found')).toBeInTheDocument();
      });
    });
  });
});
