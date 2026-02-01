/**
 * Tests for ZoneComparisonTable component (NEM-4714)
 *
 * Tests the zone comparison table including:
 * - Rendering zone data
 * - Sorting functionality
 * - Trend indicators
 * - Loading and empty states
 */
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';

import { ZoneComparisonTable } from './ZoneComparisonTable';

import type { ZoneComparisonData } from '../../hooks/useZoneComparison';

describe('ZoneComparisonTable', () => {
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
    it('renders zones in a table', () => {
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 100 }),
        createMockZone({ zone_id: 2, zone_name: 'Zone B', value: 75 }),
      ];

      render(<ZoneComparisonTable zones={zones} metric="crossings" />);

      expect(screen.getByTestId('zone-comparison-table')).toBeInTheDocument();
      expect(screen.getByText('Zone A')).toBeInTheDocument();
      expect(screen.getByText('Zone B')).toBeInTheDocument();
    });

    it('displays metric values correctly', () => {
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 1234 }),
      ];

      render(<ZoneComparisonTable zones={zones} metric="crossings" />);

      expect(screen.getByTestId('zone-value-1')).toHaveTextContent('1,234');
    });

    it('formats dwell time values correctly', () => {
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 45 }), // 45 seconds
        createMockZone({ zone_id: 2, zone_name: 'Zone B', value: 125 }), // ~2 minutes
        createMockZone({ zone_id: 3, zone_name: 'Zone C', value: 3700 }), // ~1 hour
      ];

      render(<ZoneComparisonTable zones={zones} metric="dwell_time" />);

      expect(screen.getByTestId('zone-value-1')).toHaveTextContent('45s');
      expect(screen.getByTestId('zone-value-2')).toHaveTextContent('2m');
      expect(screen.getByTestId('zone-value-3')).toHaveTextContent('1.0h');
    });

    it('displays zone type badges', () => {
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', zone_type: 'entry_point' }),
        createMockZone({ zone_id: 2, zone_name: 'Zone B', zone_type: 'driveway' }),
      ];

      render(<ZoneComparisonTable zones={zones} metric="crossings" />);

      expect(screen.getByText('Entry Point')).toBeInTheDocument();
      expect(screen.getByText('Driveway')).toBeInTheDocument();
    });
  });

  describe('trend indicators', () => {
    it('shows positive trend with green color and up arrow', () => {
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', trend_percent: 15.5 }),
      ];

      render(<ZoneComparisonTable zones={zones} metric="crossings" />);

      const row = screen.getByTestId('zone-row-1');
      const trendIndicator = within(row).getByTestId('trend-indicator');
      expect(trendIndicator).toHaveTextContent('+15.5%');
      expect(trendIndicator).toHaveClass('text-green-400');
    });

    it('shows negative trend with red color and down arrow', () => {
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', trend_percent: -8.2 }),
      ];

      render(<ZoneComparisonTable zones={zones} metric="crossings" />);

      const row = screen.getByTestId('zone-row-1');
      const trendIndicator = within(row).getByTestId('trend-indicator');
      expect(trendIndicator).toHaveTextContent('-8.2%');
      expect(trendIndicator).toHaveClass('text-red-400');
    });

    it('shows neutral trend for zero change', () => {
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', trend_percent: 0 }),
      ];

      render(<ZoneComparisonTable zones={zones} metric="crossings" />);

      const row = screen.getByTestId('zone-row-1');
      const trendIndicator = within(row).getByTestId('trend-indicator');
      expect(trendIndicator).toHaveTextContent('0.0%');
      expect(trendIndicator).toHaveClass('text-gray-400');
    });

    it('shows dash for null trend', () => {
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', trend_percent: null }),
      ];

      render(<ZoneComparisonTable zones={zones} metric="crossings" />);

      const row = screen.getByTestId('zone-row-1');
      expect(within(row).getByTestId('trend-no-data')).toHaveTextContent('-');
    });
  });

  describe('sorting', () => {
    it('sorts by value descending by default', () => {
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 50 }),
        createMockZone({ zone_id: 2, zone_name: 'Zone B', value: 100 }),
        createMockZone({ zone_id: 3, zone_name: 'Zone C', value: 25 }),
      ];

      render(<ZoneComparisonTable zones={zones} metric="crossings" />);

      const rows = screen.getAllByTestId(/^zone-row-/);
      expect(rows[0]).toHaveAttribute('data-testid', 'zone-row-2'); // 100
      expect(rows[1]).toHaveAttribute('data-testid', 'zone-row-1'); // 50
      expect(rows[2]).toHaveAttribute('data-testid', 'zone-row-3'); // 25
    });

    it('toggles sort direction when clicking same column', async () => {
      const user = userEvent.setup();
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 50 }),
        createMockZone({ zone_id: 2, zone_name: 'Zone B', value: 100 }),
      ];

      render(<ZoneComparisonTable zones={zones} metric="crossings" />);

      // Click on Value header to toggle from desc to asc
      const headers = screen.getAllByRole('columnheader');
      const valueHeader = headers.find((h) => h.textContent?.includes('Crossings'));
      expect(valueHeader).toBeDefined();

      await user.click(valueHeader!);

      // Now should be ascending
      const rows = screen.getAllByTestId(/^zone-row-/);
      expect(rows[0]).toHaveAttribute('data-testid', 'zone-row-1'); // 50
      expect(rows[1]).toHaveAttribute('data-testid', 'zone-row-2'); // 100
    });

    it('sorts by zone name', async () => {
      const user = userEvent.setup();
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Charlie Zone', value: 50 }),
        createMockZone({ zone_id: 2, zone_name: 'Alpha Zone', value: 100 }),
        createMockZone({ zone_id: 3, zone_name: 'Beta Zone', value: 25 }),
      ];

      render(<ZoneComparisonTable zones={zones} metric="crossings" />);

      // Click on Zone header
      const headers = screen.getAllByRole('columnheader');
      const zoneHeader = headers.find((h) => h.textContent?.includes('Zone'));
      await user.click(zoneHeader!);

      // Should be sorted by name descending first
      let rows = screen.getAllByTestId(/^zone-row-/);
      expect(rows[0]).toHaveAttribute('data-testid', 'zone-row-1'); // Charlie

      // Click again for ascending
      await user.click(zoneHeader!);
      rows = screen.getAllByTestId(/^zone-row-/);
      expect(rows[0]).toHaveAttribute('data-testid', 'zone-row-2'); // Alpha
    });

    it('sorts by trend', async () => {
      const user = userEvent.setup();
      const zones = [
        createMockZone({ zone_id: 1, zone_name: 'Zone A', value: 50, trend_percent: 5 }),
        createMockZone({ zone_id: 2, zone_name: 'Zone B', value: 50, trend_percent: 15 }),
        createMockZone({ zone_id: 3, zone_name: 'Zone C', value: 50, trend_percent: null }),
      ];

      render(<ZoneComparisonTable zones={zones} metric="crossings" />);

      // Click on Trend header to sort by trend (descending first)
      const headers = screen.getAllByRole('columnheader');
      const trendHeader = headers.find((h) => h.textContent?.includes('Trend'));
      await user.click(trendHeader!);

      // Should be sorted by trend descending, null values at end
      const rows = screen.getAllByTestId(/^zone-row-/);
      expect(rows[0]).toHaveAttribute('data-testid', 'zone-row-2'); // 15 (highest)
      expect(rows[1]).toHaveAttribute('data-testid', 'zone-row-1'); // 5
      expect(rows[2]).toHaveAttribute('data-testid', 'zone-row-3'); // null (at end)
    });
  });

  describe('loading state', () => {
    it('shows loading skeleton when isLoading is true', () => {
      render(<ZoneComparisonTable zones={[]} metric="crossings" isLoading={true} />);

      expect(screen.getByTestId('zone-comparison-table-loading')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows empty message when no zones', () => {
      render(<ZoneComparisonTable zones={[]} metric="crossings" />);

      expect(screen.getByTestId('zone-comparison-table-empty')).toBeInTheDocument();
      expect(screen.getByText('No zones selected for comparison')).toBeInTheDocument();
    });
  });

  describe('metric labels', () => {
    it('shows correct header for crossings metric', () => {
      const zones = [createMockZone({ zone_id: 1 })];
      render(<ZoneComparisonTable zones={zones} metric="crossings" />);

      expect(screen.getByText('Crossings')).toBeInTheDocument();
    });

    it('shows correct header for dwell_time metric', () => {
      const zones = [createMockZone({ zone_id: 1 })];
      render(<ZoneComparisonTable zones={zones} metric="dwell_time" />);

      expect(screen.getByText('Avg Dwell Time')).toBeInTheDocument();
    });

    it('shows correct header for anomalies metric', () => {
      const zones = [createMockZone({ zone_id: 1 })];
      render(<ZoneComparisonTable zones={zones} metric="anomalies" />);

      expect(screen.getByText('Anomalies')).toBeInTheDocument();
    });

    it('shows correct header for occupancy metric', () => {
      const zones = [createMockZone({ zone_id: 1 })];
      render(<ZoneComparisonTable zones={zones} metric="occupancy" />);

      expect(screen.getByText('Occupancy')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has aria-sort attribute on sorted column', () => {
      const zones = [createMockZone({ zone_id: 1 })];
      render(<ZoneComparisonTable zones={zones} metric="crossings" />);

      const headers = screen.getAllByRole('columnheader');
      const valueHeader = headers.find((h) => h.textContent?.includes('Crossings'));
      expect(valueHeader).toHaveAttribute('aria-sort', 'descending');
    });
  });

  describe('custom className', () => {
    it('applies custom className', () => {
      const zones = [createMockZone({ zone_id: 1 })];
      render(<ZoneComparisonTable zones={zones} metric="crossings" className="custom-class" />);

      expect(screen.getByTestId('zone-comparison-table')).toHaveClass('custom-class');
    });
  });
});
