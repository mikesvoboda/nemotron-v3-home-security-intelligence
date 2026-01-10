import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import AlertsPage from './AlertsPage.new';
import * as api from '../../services/api';

import type { Camera, Event, EventListResponse } from '../../services/api';

// Mock API module
vi.mock('../../services/api');

// Mock new alert components
vi.mock('./AlertCard', () => ({
  default: vi.fn(({ id, summary, onAcknowledge, onDismiss, selected, onSelectChange }) => (
    <div data-testid={`alert-card-${id}`}>
      <div>{summary}</div>
      {selected !== undefined && (
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onSelectChange?.(id, !selected)}
          data-testid={`checkbox-${id}`}
        />
      )}
      {onAcknowledge && (
        <button onClick={() => onAcknowledge(id)} data-testid={`acknowledge-${id}`}>
          Acknowledge
        </button>
      )}
      {onDismiss && (
        <button onClick={() => onDismiss(id)} data-testid={`dismiss-${id}`}>
          Dismiss
        </button>
      )}
    </div>
  )),
}));

vi.mock('./AlertFilters', () => ({
  default: vi.fn(({ activeFilter, onFilterChange, counts }) => (
    <div data-testid="alert-filters">
      <button onClick={() => onFilterChange('all')}>All ({counts.all})</button>
      <button onClick={() => onFilterChange('critical')}>Critical ({counts.critical})</button>
      <button onClick={() => onFilterChange('high')}>High ({counts.high})</button>
      <button onClick={() => onFilterChange('medium')}>Medium ({counts.medium})</button>
      <button onClick={() => onFilterChange('unread')}>Unread ({counts.unread})</button>
      <span>Active: {activeFilter}</span>
    </div>
  )),
}));

vi.mock('./AlertActions', () => ({
  default: vi.fn(
    ({
      selectedCount,
      totalCount,
      onSelectAll,
      onAcknowledgeSelected,
      onDismissSelected,
      onClearSelection,
    }) =>
      totalCount > 0 ? (
        <div data-testid="alert-actions">
          <button onClick={() => onSelectAll(true)}>Select All</button>
          <button onClick={onAcknowledgeSelected}>Acknowledge Selected</button>
          <button onClick={onDismissSelected}>Dismiss Selected</button>
          <button onClick={onClearSelection}>Clear</button>
          <span>{selectedCount} selected</span>
        </div>
      ) : null
  ),
}));

describe('AlertsPage (Redesigned)', () => {
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
    {
      id: 2,
      camera_id: 'camera-1',
      started_at: '2024-01-01T11:00:00Z',
      ended_at: '2024-01-01T11:01:00Z',
      risk_score: 80,
      risk_level: 'high',
      summary: 'Vehicle in restricted area',
      reviewed: false,
      detection_count: 3,
      notes: null,
    },
  ];

  const mockCriticalRiskEvents: Event[] = [
    {
      id: 3,
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
    items: mockHighRiskEvents,
    pagination: {
      total: 2,
      limit: 20,
      offset: 0,
      has_more: false,
    },
  };

  const mockCriticalResponse: EventListResponse = {
    items: mockCriticalRiskEvents,
    pagination: {
      total: 1,
      limit: 20,
      offset: 0,
      has_more: false,
    },
  };

  const mockEmptyResponse: EventListResponse = {
    items: [],
    pagination: {
      total: 0,
      limit: 20,
      offset: 0,
      has_more: false,
    },
  };

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    vi.mocked(api.isAbortError).mockReturnValue(false);
    vi.mocked(api.updateEvent).mockResolvedValue({
      id: 1,
      camera_id: 'camera-1',
      started_at: '2024-01-01T10:00:00Z',
      ended_at: null,
      risk_score: 75,
      risk_level: 'high',
      summary: 'Updated event',
      reviewed: true,
      detection_count: 0,
      notes: null,
    });
  });

  describe('New Header and Statistics', () => {
    it('displays alert statistics in header', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      // Should show unacknowledged count in header
      expect(screen.getByText(/unacknowledged/i)).toBeInTheDocument();
    });

    it('displays "Configure Rules" button in header', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const mockOnConfigureRules = vi.fn();
      render(<AlertsPage onConfigureRules={mockOnConfigureRules} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /configure rules/i })).toBeInTheDocument();
      });
    });

    it('displays "Mark All Read" button when there are unacknowledged alerts', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /mark all read/i })).toBeInTheDocument();
      });
    });
  });

  describe('Alert Filters Integration', () => {
    it('renders AlertFilters component with correct counts', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-filters')).toBeInTheDocument();
      });

      // Should show filter counts
      expect(screen.getByText(/All \(3\)/)).toBeInTheDocument();
      expect(screen.getByText(/Critical \(1\)/)).toBeInTheDocument();
      expect(screen.getByText(/High \(2\)/)).toBeInTheDocument();
    });

    it('filters alerts when severity filter is changed', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-filters')).toBeInTheDocument();
      });

      // Mock next fetch for filtered results
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockEmptyResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      // Click critical filter
      const criticalBtn = screen.getByText(/Critical \(1\)/);
      await user.click(criticalBtn);

      await waitFor(() => {
        expect(screen.getByText('Active: critical')).toBeInTheDocument();
      });
    });
  });

  describe('Alert Card Rendering', () => {
    it('renders AlertCard components for each alert', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      // Wait for loading to complete - check for header stats first
      await waitFor(() => {
        expect(screen.getByText(/unacknowledged/i)).toBeInTheDocument();
      });

      // Check for alert cards (as strings since component uses String(event.id))
      expect(screen.getByTestId('alert-card-1')).toBeInTheDocument();
      expect(screen.getByTestId('alert-card-2')).toBeInTheDocument();
      expect(screen.getByTestId('alert-card-3')).toBeInTheDocument();
    });

    it('passes correct props to AlertCard components', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
        expect(screen.getByText('Unknown person at door')).toBeInTheDocument();
      });
    });
  });

  describe('Batch Selection and Actions', () => {
    it('renders AlertActions component when alerts exist', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-actions')).toBeInTheDocument();
      });
    });

    it('allows selecting individual alerts', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('checkbox-1')).toBeInTheDocument();
      });

      const checkbox = screen.getByTestId('checkbox-1');
      await user.click(checkbox);

      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeInTheDocument();
      });
    });

    it('allows selecting all alerts', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-actions')).toBeInTheDocument();
      });

      const selectAllBtn = screen.getByText('Select All');
      await user.click(selectAllBtn);

      await waitFor(() => {
        expect(screen.getByText('3 selected')).toBeInTheDocument();
      });
    });

    it('batch acknowledges selected alerts', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-actions')).toBeInTheDocument();
      });

      // Select an alert
      const checkbox = screen.getByTestId('checkbox-1');
      await user.click(checkbox);

      // Click batch acknowledge
      const acknowledgeBtn = screen.getByText('Acknowledge Selected');
      await user.click(acknowledgeBtn);

      await waitFor(() => {
        expect(api.updateEvent).toHaveBeenCalledWith(1, { reviewed: true });
      });
    });

    it('clears selection after batch dismiss', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-actions')).toBeInTheDocument();
      });

      // Select an alert
      const checkbox = screen.getByTestId('checkbox-1');
      await user.click(checkbox);

      // Mock refetch
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce({ ...mockHighResponse, items: [mockHighRiskEvents[1]] })
        .mockResolvedValueOnce(mockCriticalResponse);

      // Click batch dismiss
      const dismissBtn = screen.getByText('Dismiss Selected');
      await user.click(dismissBtn);

      await waitFor(() => {
        expect(screen.getByText('0 selected')).toBeInTheDocument();
      });
    });
  });

  describe('Individual Alert Actions', () => {
    it('acknowledges individual alert', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('acknowledge-1')).toBeInTheDocument();
      });

      const acknowledgeBtn = screen.getByTestId('acknowledge-1');
      await user.click(acknowledgeBtn);

      await waitFor(() => {
        expect(api.updateEvent).toHaveBeenCalledWith(1, { reviewed: true });
      });
    });

    it('dismisses individual alert', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      render(<AlertsPage />);

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.getByText(/unacknowledged/i)).toBeInTheDocument();
      });

      // Now check for dismiss button
      const dismissBtn = screen.getByTestId('dismiss-1');
      await user.click(dismissBtn);

      // Alert should be removed from DOM (component handles dismiss locally, not via refetch)
      await waitFor(() => {
        expect(screen.queryByTestId('alert-card-1')).not.toBeInTheDocument();
      });
    });
  });

  describe('Empty States', () => {
    it('shows empty state when no alerts exist', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockEmptyResponse)
        .mockResolvedValueOnce(mockEmptyResponse);

      render(<AlertsPage />);

      // Wait for loading to complete - empty state shows "No Alerts at This Time"
      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      expect(screen.getByText(/no alerts/i)).toBeInTheDocument();
    });

    it('does not render AlertActions when no alerts', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockEmptyResponse)
        .mockResolvedValueOnce(mockEmptyResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('alert-actions')).not.toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('displays error message when API fails', async () => {
      vi.mocked(api.fetchEvents).mockRejectedValue(new Error('Network error'));

      render(<AlertsPage />);

      // Wait for error state to appear - component shows "Error Loading Alerts" on failure
      await waitFor(
        () => {
          expect(screen.getByText(/error loading alerts/i)).toBeInTheDocument();
        },
        { timeout: 3000 }
      );
    });
  });
});
