/**
 * Tests for ZoneActivityHeatmap component (NEM-3200, NEM-5024)
 *
 * Tests zone activity heatmap visualization including:
 * - Weekly heatmap grid rendering
 * - Hourly bar chart
 * - Time range selection
 * - Overlay mode
 * - Cell interactions
 * - Loading and error states
 * - API integration via mocked hook
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ZoneActivityHeatmap from './ZoneActivityHeatmap';

import type { UseZoneActivityHeatmapReturn } from '../../hooks/useZoneActivityHeatmap';

// Mock the hook
const mockRefresh = vi.fn().mockResolvedValue(undefined);
const mockRefetch = vi.fn().mockResolvedValue(undefined);

const defaultMockHookReturn: UseZoneActivityHeatmapReturn = {
  weeklyData: [
    { hour: 0, dayOfWeek: 0, value: 5 },
    { hour: 6, dayOfWeek: 1, value: 10 },
    { hour: 12, dayOfWeek: 2, value: 15 },
    { hour: 18, dayOfWeek: 3, value: 8 },
  ],
  hourlyData: Array.from({ length: 24 }, (_, i) => ({ hour: i, count: Math.floor(Math.random() * 10) })),
  zoneName: 'Test Zone',
  totalActivity: 42,
  startTime: '2026-01-25T00:00:00Z',
  endTime: '2026-02-01T00:00:00Z',
  isLoading: false,
  isFetching: false,
  error: null,
  isError: false,
  refetch: mockRefetch,
  refresh: mockRefresh,
};

let mockHookReturn = { ...defaultMockHookReturn };

vi.mock('../../hooks/useZoneActivityHeatmap', () => ({
  useZoneActivityHeatmap: () => mockHookReturn,
}));

describe('ZoneActivityHeatmap', () => {
  const defaultProps = {
    zoneId: 1,
    zoneName: 'Front Door Zone',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockHookReturn = { ...defaultMockHookReturn };
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('should render the heatmap card', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-activity-heatmap')).toBeInTheDocument();
      });
    });

    it('should display zone name in title from props', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Front Door Zone Activity')).toBeInTheDocument();
      });
    });

    it('should display zone name from API when props zoneName not provided', async () => {
      render(<ZoneActivityHeatmap zoneId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Test Zone Activity')).toBeInTheDocument();
      });
    });

    it('should display default title when no zoneName from props or API', async () => {
      mockHookReturn = { ...defaultMockHookReturn, zoneName: null };
      render(<ZoneActivityHeatmap zoneId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Activity Heatmap')).toBeInTheDocument();
      });
    });

    it('should render weekly pattern section', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Weekly Pattern')).toBeInTheDocument();
      });
    });

    it('should render day of week headers', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Sun')).toBeInTheDocument();
        expect(screen.getByText('Mon')).toBeInTheDocument();
        expect(screen.getByText('Tue')).toBeInTheDocument();
        expect(screen.getByText('Wed')).toBeInTheDocument();
        expect(screen.getByText('Thu')).toBeInTheDocument();
        expect(screen.getByText('Fri')).toBeInTheDocument();
        expect(screen.getByText('Sat')).toBeInTheDocument();
      });
    });

    it('should render legend', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Low')).toBeInTheDocument();
        expect(screen.getByText('High')).toBeInTheDocument();
      });
    });

    it('should display total activity count', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('(42 total)')).toBeInTheDocument();
      });
    });
  });

  describe('Loading State', () => {
    it('should show skeleton while loading', async () => {
      mockHookReturn = { ...defaultMockHookReturn, isLoading: true };
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-activity-heatmap')).toBeInTheDocument();
      });

      // Should show skeleton (animated pulse elements)
      expect(screen.queryByText('Weekly Pattern')).not.toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should show error message on fetch failure', async () => {
      mockHookReturn = {
        ...defaultMockHookReturn,
        isError: true,
        error: new Error('Failed to fetch data'),
        weeklyData: [],
        hourlyData: [],
      };
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Failed to fetch data')).toBeInTheDocument();
      });

      expect(screen.getByText('Try Again')).toBeInTheDocument();
    });

    it('should call refresh when Try Again is clicked', async () => {
      mockHookReturn = {
        ...defaultMockHookReturn,
        isError: true,
        error: new Error('Failed to fetch'),
        weeklyData: [],
        hourlyData: [],
      };
      const user = userEvent.setup();
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Try Again')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Try Again'));
      expect(mockRefresh).toHaveBeenCalled();
    });
  });

  describe('Empty State', () => {
    it('should show empty message when no data', async () => {
      mockHookReturn = {
        ...defaultMockHookReturn,
        weeklyData: [],
        hourlyData: [],
        totalActivity: 0,
      };
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('No activity data available for this time range')).toBeInTheDocument();
      });
    });
  });

  describe('Time Range Selection', () => {
    it('should render time range selector', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('time-range-select')).toBeInTheDocument();
      });
    });

    it('should use initial time range', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} initialTimeRange="24h" />);

      await waitFor(() => {
        const select = screen.getByTestId('time-range-select');
        expect(select).toBeInTheDocument();
      });
    });
  });

  describe('Refresh Button', () => {
    it('should render refresh button', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('refresh-btn')).toBeInTheDocument();
      });
    });

    it('should call refresh on click', async () => {
      const user = userEvent.setup();
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('refresh-btn')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('refresh-btn'));
      expect(mockRefresh).toHaveBeenCalled();
    });

    it('should disable refresh button while fetching', async () => {
      mockHookReturn = { ...defaultMockHookReturn, isFetching: true };
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        const btn = screen.getByTestId('refresh-btn');
        expect(btn).toBeDisabled();
      });
    });
  });

  describe('Heatmap Grid', () => {
    it('should render heatmap cells', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        // Check for a few cells at different times
        expect(screen.getByTestId('heatmap-cell-0-0')).toBeInTheDocument();
        expect(screen.getByTestId('heatmap-cell-6-3')).toBeInTheDocument();
        expect(screen.getByTestId('heatmap-cell-12-5')).toBeInTheDocument();
      });
    });

    it('should call onCellClick when cell is clicked', async () => {
      const onCellClick = vi.fn();
      const user = userEvent.setup();

      render(<ZoneActivityHeatmap {...defaultProps} onCellClick={onCellClick} />);

      await waitFor(() => {
        expect(screen.getByTestId('heatmap-cell-6-3')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('heatmap-cell-6-3'));
      expect(onCellClick).toHaveBeenCalledWith(6, 3);
    });
  });

  describe('Hourly Bar Chart', () => {
    it('should render hourly bars in non-compact mode', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText("Today's Activity")).toBeInTheDocument();
      });

      // Check for some hourly bars
      expect(screen.getByTestId('hourly-bar-0')).toBeInTheDocument();
      expect(screen.getByTestId('hourly-bar-12')).toBeInTheDocument();
    });

    it('should not render hourly chart in compact mode', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} compact />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-activity-heatmap')).toBeInTheDocument();
      });

      expect(screen.queryByText("Today's Activity")).not.toBeInTheDocument();
    });
  });

  describe('Compact Mode', () => {
    it('should render in compact mode', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} compact />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-activity-heatmap')).toBeInTheDocument();
      });
    });

    it('should show abbreviated day names in compact mode', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} compact />);

      await waitFor(() => {
        // In compact mode, day names are single characters
        const dayHeaders = screen.getAllByText('S');
        expect(dayHeaders.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('should not show total activity count in compact mode', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} compact />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-activity-heatmap')).toBeInTheDocument();
      });

      expect(screen.queryByText('(42 total)')).not.toBeInTheDocument();
    });
  });

  describe('Overlay Mode', () => {
    it('should render in overlay mode', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} overlay />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-activity-heatmap-overlay')).toBeInTheDocument();
      });
    });

    it('should not render card elements in overlay mode', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} overlay />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-activity-heatmap-overlay')).toBeInTheDocument();
      });

      expect(screen.queryByText('Activity Heatmap')).not.toBeInTheDocument();
      expect(screen.queryByTestId('time-range-select')).not.toBeInTheDocument();
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} className="custom-class" />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-activity-heatmap')).toHaveClass('custom-class');
      });
    });
  });

  describe('Zone ID Types', () => {
    it('should accept numeric zone ID', async () => {
      render(<ZoneActivityHeatmap zoneId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-activity-heatmap')).toBeInTheDocument();
      });
    });

    it('should accept string zone ID', async () => {
      render(<ZoneActivityHeatmap zoneId="zone-123" />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-activity-heatmap')).toBeInTheDocument();
      });
    });
  });
});
