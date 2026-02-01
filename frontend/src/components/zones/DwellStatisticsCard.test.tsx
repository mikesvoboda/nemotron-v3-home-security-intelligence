/**
 * Tests for DwellStatisticsCard component (NEM-4714)
 *
 * Tests dwell statistics display including:
 * - Rendering zone information
 * - Displaying dwell times (avg, min, max)
 * - Alerts badge display
 * - Loading state
 * - Configure button functionality
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import DwellStatisticsCard from './DwellStatisticsCard';

import type { DwellStatistics, PolygonZone } from '../../hooks/useDwellTimeAnalytics';

describe('DwellStatisticsCard', () => {
  // Helper to create mock zone data
  const createMockZone = (overrides: Partial<PolygonZone> = {}): PolygonZone => ({
    id: 1,
    name: 'Front Yard',
    camera_id: 'cam-123',
    zone_type: 'monitoring',
    is_active: true,
    current_count: 2,
    ...overrides,
  });

  // Helper to create mock statistics data
  const createMockStatistics = (overrides: Partial<DwellStatistics> = {}): DwellStatistics => ({
    zone_id: 1,
    total_records: 50,
    avg_dwell_seconds: 120,
    max_dwell_seconds: 300,
    min_dwell_seconds: 30,
    alerts_triggered: 3,
    start_time: '2024-01-01T00:00:00Z',
    end_time: '2024-01-01T23:59:59Z',
    ...overrides,
  });

  const defaultProps = {
    zone: createMockZone(),
    statistics: createMockStatistics(),
    onConfigure: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('should render the card with zone name', () => {
      render(<DwellStatisticsCard {...defaultProps} />);

      expect(screen.getByTestId('dwell-stats-card-1')).toBeInTheDocument();
      expect(screen.getByText('Front Yard')).toBeInTheDocument();
    });

    it('should display Active badge when zone is active', () => {
      render(<DwellStatisticsCard {...defaultProps} />);

      expect(screen.getByTestId('zone-status-badge')).toHaveTextContent('Active');
    });

    it('should display Inactive badge when zone is inactive', () => {
      const zone = createMockZone({ is_active: false });
      render(<DwellStatisticsCard {...defaultProps} zone={zone} />);

      expect(screen.getByTestId('zone-status-badge')).toHaveTextContent('Inactive');
    });

    it('should apply custom className', () => {
      render(<DwellStatisticsCard {...defaultProps} className="custom-class" />);

      expect(screen.getByTestId('dwell-stats-card-1')).toHaveClass('custom-class');
    });
  });

  describe('Dwell Times Display', () => {
    it('should display average dwell time', () => {
      render(<DwellStatisticsCard {...defaultProps} />);

      expect(screen.getByTestId('avg-dwell')).toHaveTextContent('2m 0s');
      expect(screen.getByText('Avg')).toBeInTheDocument();
    });

    it('should display minimum dwell time', () => {
      render(<DwellStatisticsCard {...defaultProps} />);

      expect(screen.getByTestId('min-dwell')).toHaveTextContent('30s');
      expect(screen.getByText('Min')).toBeInTheDocument();
    });

    it('should display maximum dwell time', () => {
      render(<DwellStatisticsCard {...defaultProps} />);

      expect(screen.getByTestId('max-dwell')).toHaveTextContent('5m 0s');
      expect(screen.getByText('Max')).toBeInTheDocument();
    });

    it('should display "--" for null dwell values', () => {
      const statistics = createMockStatistics({
        avg_dwell_seconds: null,
        min_dwell_seconds: null,
        max_dwell_seconds: null,
      });
      render(<DwellStatisticsCard {...defaultProps} statistics={statistics} />);

      expect(screen.getByTestId('avg-dwell')).toHaveTextContent('--');
      expect(screen.getByTestId('min-dwell')).toHaveTextContent('--');
      expect(screen.getByTestId('max-dwell')).toHaveTextContent('--');
    });

    it('should display total records count', () => {
      render(<DwellStatisticsCard {...defaultProps} />);

      expect(screen.getByTestId('total-records')).toHaveTextContent('50');
      expect(screen.getByText('total records')).toBeInTheDocument();
    });

    it('should display "No dwell records" when total_records is 0', () => {
      const statistics = createMockStatistics({ total_records: 0 });
      render(<DwellStatisticsCard {...defaultProps} statistics={statistics} />);

      expect(screen.getByTestId('no-records')).toHaveTextContent('No dwell records in time range');
    });
  });

  describe('Alerts Badge', () => {
    it('should display alerts badge when alerts_triggered > 0', () => {
      render(<DwellStatisticsCard {...defaultProps} />);

      expect(screen.getByTestId('alerts-badge')).toHaveTextContent('3');
    });

    it('should not display alerts badge when alerts_triggered is 0', () => {
      const statistics = createMockStatistics({ alerts_triggered: 0 });
      render(<DwellStatisticsCard {...defaultProps} statistics={statistics} />);

      expect(screen.queryByTestId('alerts-badge')).not.toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('should display loading spinner when isLoading is true', () => {
      render(
        <DwellStatisticsCard
          zone={createMockZone()}
          isLoading={true}
          statistics={undefined}
        />
      );

      expect(screen.getByTestId('loading-state')).toBeInTheDocument();
    });

    it('should not display statistics when loading', () => {
      render(
        <DwellStatisticsCard
          zone={createMockZone()}
          isLoading={true}
          statistics={createMockStatistics()}
        />
      );

      expect(screen.queryByTestId('avg-dwell')).not.toBeInTheDocument();
    });
  });

  describe('No Data State', () => {
    it('should display "No statistics available" when no statistics provided', () => {
      render(
        <DwellStatisticsCard
          zone={createMockZone()}
          statistics={undefined}
        />
      );

      expect(screen.getByTestId('no-data-state')).toBeInTheDocument();
      expect(screen.getByText('No statistics available')).toBeInTheDocument();
    });
  });

  describe('Configure Button', () => {
    it('should render configure button', () => {
      render(<DwellStatisticsCard {...defaultProps} />);

      expect(screen.getByTestId('configure-button')).toBeInTheDocument();
      expect(screen.getByTestId('configure-button')).toHaveTextContent('Configure Threshold');
    });

    it('should call onConfigure with zone id when clicked', async () => {
      const onConfigure = vi.fn();
      const user = userEvent.setup();
      render(<DwellStatisticsCard {...defaultProps} onConfigure={onConfigure} />);

      await user.click(screen.getByTestId('configure-button'));

      expect(onConfigure).toHaveBeenCalledWith(1);
    });

    it('should not throw when onConfigure is not provided', async () => {
      const user = userEvent.setup();
      render(<DwellStatisticsCard zone={createMockZone()} statistics={createMockStatistics()} />);

      // Should not throw
      await user.click(screen.getByTestId('configure-button'));
    });
  });

  describe('Status Badge Styling', () => {
    it('should have green styling for active zone', () => {
      const zone = createMockZone({ is_active: true });
      render(<DwellStatisticsCard {...defaultProps} zone={zone} />);

      const badge = screen.getByTestId('zone-status-badge');
      expect(badge).toHaveClass('bg-green-500/20');
      expect(badge).toHaveClass('text-green-400');
    });

    it('should have gray styling for inactive zone', () => {
      const zone = createMockZone({ is_active: false });
      render(<DwellStatisticsCard {...defaultProps} zone={zone} />);

      const badge = screen.getByTestId('zone-status-badge');
      expect(badge).toHaveClass('bg-gray-500/20');
      expect(badge).toHaveClass('text-gray-400');
    });
  });

  describe('Large Numbers', () => {
    it('should format large record counts with locale string', () => {
      const statistics = createMockStatistics({ total_records: 1000000 });
      render(<DwellStatisticsCard {...defaultProps} statistics={statistics} />);

      // toLocaleString formats with commas (varies by locale, but should be formatted)
      expect(screen.getByTestId('total-records')).toHaveTextContent('1,000,000');
    });
  });
});
