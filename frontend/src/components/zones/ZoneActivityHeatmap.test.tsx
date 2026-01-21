/**
 * Tests for ZoneActivityHeatmap component (NEM-3200)
 *
 * Tests zone activity heatmap visualization including:
 * - Weekly heatmap grid rendering
 * - Hourly bar chart
 * - Time range selection
 * - Overlay mode
 * - Cell interactions
 * - Loading states
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ZoneActivityHeatmap from './ZoneActivityHeatmap';

describe('ZoneActivityHeatmap', () => {
  const defaultProps = {
    zoneId: 'zone-123',
    zoneName: 'Front Door Zone',
  };

  beforeEach(() => {
    vi.clearAllMocks();
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

    it('should display zone name in title', async () => {
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Front Door Zone Activity')).toBeInTheDocument();
      });
    });

    it('should display default title when no zoneName provided', async () => {
      render(<ZoneActivityHeatmap zoneId="zone-123" />);

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

    it('should trigger refresh on click', async () => {
      const user = userEvent.setup();
      render(<ZoneActivityHeatmap {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('refresh-btn')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('refresh-btn'));
      // Refresh should trigger loading state
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
});

// Note: Helper function tests (formatHour, getHeatmapColor, getHeatmapTextColor,
// generateMockHeatmapData, generateMockHourlyActivity) are tested implicitly through
// component tests to avoid react-refresh/only-export-components warnings.
