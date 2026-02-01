/**
 * Tests for ZoneComparisonChart component (NEM-4714)
 *
 * Tests the zone comparison chart including:
 * - Rendering chart with data
 * - Summary statistics
 * - Loading and empty states
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import { ZoneComparisonChart } from './ZoneComparisonChart';

import type { ZoneComparisonData } from '../../hooks/useZoneComparison';

// Mock Tremor's BarChart component
vi.mock('@tremor/react', async () => {
  const actual = await vi.importActual('@tremor/react');
  return {
    ...actual,
    BarChart: vi.fn(({ data, 'data-testid': testId }) => (
      <div data-testid={testId || 'mock-bar-chart'}>
        BarChart with {data?.length ?? 0} items
      </div>
    )),
  };
});

describe('ZoneComparisonChart', () => {
  // Helper to create mock zone data
  const createMockZone = (overrides: Partial<ZoneComparisonData> = {}): ZoneComparisonData => ({
    zone_id: Math.floor(Math.random() * 1000),
    zone_name: 'Test Zone',
    zone_type: 'entry_point',
    camera_id: 'cam-123',
    value: 42,
    trend_percent: 5.5,
    ...overrides,
  });

  describe('rendering', () => {
    it('renders chart with zones', () => {
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 100 }),
        createMockZone({ zone_id: 2, zone_name: 'Zone B', value: 75 }),
      ];

      render(<ZoneComparisonChart zones={zones} metric="crossings" />);

      expect(screen.getByTestId('zone-comparison-chart')).toBeInTheDocument();
    });

    it('displays chart title with metric', () => {
      const zones = [createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 100 })];

      render(<ZoneComparisonChart zones={zones} metric="crossings" />);

      expect(screen.getByText(/Zone Comparison - Crossings/)).toBeInTheDocument();
    });

    it('shows dwell time metric in title', () => {
      const zones = [createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 100 })];

      render(<ZoneComparisonChart zones={zones} metric="dwell_time" />);

      expect(screen.getByText(/Zone Comparison - Avg Dwell Time/)).toBeInTheDocument();
    });
  });

  describe('summary statistics', () => {
    it('displays zone count', () => {
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 100 }),
        createMockZone({ zone_id: 2, zone_name: 'Zone B', value: 75 }),
        createMockZone({ zone_id: 3, zone_name: 'Zone C', value: 50 }),
      ];

      render(<ZoneComparisonChart zones={zones} metric="crossings" />);

      expect(screen.getByTestId('zone-count')).toHaveTextContent('3');
    });

    it('displays average value for crossings', () => {
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 100 }),
        createMockZone({ zone_id: 2, zone_name: 'Zone B', value: 50 }),
      ];

      render(<ZoneComparisonChart zones={zones} metric="crossings" />);

      // Average should be 75
      expect(screen.getByTestId('avg-value')).toHaveTextContent('75');
    });

    it('displays formatted average for dwell_time', () => {
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 45 }), // 45 seconds
        createMockZone({ zone_id: 2, zone_name: 'Zone B', value: 75 }), // 75 seconds
      ];

      render(<ZoneComparisonChart zones={zones} metric="dwell_time" />);

      // Average is 60 seconds = 1m
      expect(screen.getByTestId('avg-value')).toHaveTextContent('1m');
    });

    it('displays highest zone name', () => {
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 50 }),
        createMockZone({ zone_id: 2, zone_name: 'Top Zone', value: 200 }),
        createMockZone({ zone_id: 3, zone_name: 'Zone C', value: 75 }),
      ];

      render(<ZoneComparisonChart zones={zones} metric="crossings" />);

      expect(screen.getByTestId('max-zone')).toHaveTextContent('Top Zone');
    });
  });

  describe('loading state', () => {
    it('shows loading spinner when isLoading is true', () => {
      render(<ZoneComparisonChart zones={[]} metric="crossings" isLoading={true} />);

      expect(screen.getByTestId('zone-comparison-chart-loading')).toBeInTheDocument();
      expect(screen.getByTestId('chart-skeleton')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows empty message when no zones', () => {
      render(<ZoneComparisonChart zones={[]} metric="crossings" />);

      expect(screen.getByTestId('zone-comparison-chart-empty')).toBeInTheDocument();
      expect(screen.getByTestId('chart-empty')).toBeInTheDocument();
      expect(screen.getByText('Select zones to compare')).toBeInTheDocument();
    });
  });

  describe('custom className', () => {
    it('applies custom className', () => {
      const zones = [createMockZone({ zone_id: 1 })];
      render(<ZoneComparisonChart zones={zones} metric="crossings" className="custom-class" />);

      expect(screen.getByTestId('zone-comparison-chart')).toHaveClass('custom-class');
    });
  });

  describe('metric labels', () => {
    it('shows anomalies metric in title', () => {
      const zones = [createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 10 })];

      render(<ZoneComparisonChart zones={zones} metric="anomalies" />);

      expect(screen.getByText(/Zone Comparison - Anomalies/)).toBeInTheDocument();
    });

    it('shows occupancy metric in title', () => {
      const zones = [createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 5 })];

      render(<ZoneComparisonChart zones={zones} metric="occupancy" />);

      expect(screen.getByText(/Zone Comparison - Occupancy/)).toBeInTheDocument();
    });
  });
});
