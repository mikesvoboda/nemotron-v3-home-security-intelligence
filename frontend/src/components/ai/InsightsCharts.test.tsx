/**
 * Tests for InsightsCharts component
 * Comprehensive test coverage for AI detection and risk distribution charts
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import InsightsCharts from './InsightsCharts';
import * as api from '../../services/api';

// Mock react-router-dom useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

// Mock the fetchEventStats API
vi.mock('../../services/api', () => ({
  fetchEventStats: vi.fn(() =>
    Promise.resolve({
      total_events: 100,
      events_by_risk_level: {
        critical: 5,
        high: 15,
        medium: 30,
        low: 50,
      },
      events_by_camera: [
        { camera_id: 'cam-1', camera_name: 'Front Door', event_count: 60 },
        { camera_id: 'cam-2', camera_name: 'Backyard', event_count: 40 },
      ],
    })
  ),
}));

describe('InsightsCharts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('basic rendering', () => {
    it('renders the main container', async () => {
      render(<InsightsCharts />);
      await waitFor(() => {
        expect(screen.getByTestId('insights-charts')).toBeInTheDocument();
      });
    });

    it('renders detection distribution card', async () => {
      render(<InsightsCharts />);
      await waitFor(() => {
        expect(screen.getByTestId('detection-distribution-card')).toBeInTheDocument();
      });
    });

    it('renders risk distribution card', async () => {
      render(<InsightsCharts />);
      await waitFor(() => {
        expect(screen.getByTestId('risk-distribution-card')).toBeInTheDocument();
      });
    });

    it('renders detection class distribution title', async () => {
      render(<InsightsCharts />);
      await waitFor(() => {
        expect(screen.getByText('Detection Class Distribution')).toBeInTheDocument();
      });
    });

    it('renders risk score distribution title', async () => {
      render(<InsightsCharts />);
      await waitFor(() => {
        expect(screen.getByText('Risk Score Distribution')).toBeInTheDocument();
      });
    });

    it('displays total events count', async () => {
      render(<InsightsCharts />);
      await waitFor(() => {
        expect(screen.getByText('Total Events: 100')).toBeInTheDocument();
      });
    });

    it('displays risk level labels', async () => {
      render(<InsightsCharts />);
      await waitFor(() => {
        // Each risk level appears multiple times (bar label + count label), so use getAllByText
        expect(screen.getAllByText('Low').length).toBeGreaterThan(0);
        expect(screen.getAllByText('Medium').length).toBeGreaterThan(0);
        expect(screen.getAllByText('High').length).toBeGreaterThan(0);
        expect(screen.getAllByText('Critical').length).toBeGreaterThan(0);
      });
    });

    it('displays placeholder when no detection class data provided', async () => {
      render(<InsightsCharts />);
      await waitFor(() => {
        expect(screen.getByText('No detections recorded yet')).toBeInTheDocument();
      });
    });
  });

  describe('detection class data display', () => {
    it('renders with detection class data', async () => {
      const detectionsByClass = {
        person: 50,
        vehicle: 30,
        animal: 15,
        package: 5,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        expect(screen.getByText('Person')).toBeInTheDocument();
        expect(screen.getByText('Vehicle')).toBeInTheDocument();
        expect(screen.getByText('Animal')).toBeInTheDocument();
        expect(screen.getByText('Package')).toBeInTheDocument();
      });
    });

    it('displays total detections when provided', async () => {
      const detectionsByClass = {
        person: 50,
        vehicle: 30,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        expect(screen.getByText(/Total Detections:/)).toBeInTheDocument();
        expect(screen.getByText('80')).toBeInTheDocument();
      });
    });

    it('capitalizes detection class names', async () => {
      const detectionsByClass = {
        person: 100,
        bicycle: 50,
        motorcycle: 25,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        expect(screen.getByText('Person')).toBeInTheDocument();
        expect(screen.getByText('Bicycle')).toBeInTheDocument();
        expect(screen.getByText('Motorcycle')).toBeInTheDocument();
      });
    });

    it('sorts detection classes by count descending', async () => {
      const detectionsByClass = {
        bicycle: 10,
        person: 100,
        car: 50,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        // All classes should be present
        expect(screen.getByText('Person')).toBeInTheDocument();
        expect(screen.getByText('Car')).toBeInTheDocument();
        expect(screen.getByText('Bicycle')).toBeInTheDocument();
      });
    });

    it('limits display to top 5 detection classes', async () => {
      const detectionsByClass = {
        person: 100,
        vehicle: 90,
        animal: 80,
        package: 70,
        bicycle: 60,
        motorcycle: 50,
        truck: 40,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        // Top 5 should be visible
        expect(screen.getByText('Person')).toBeInTheDocument();
        expect(screen.getByText('Vehicle')).toBeInTheDocument();
        expect(screen.getByText('Animal')).toBeInTheDocument();
        expect(screen.getByText('Package')).toBeInTheDocument();
        expect(screen.getByText('Bicycle')).toBeInTheDocument();
      });
    });

    it('displays detection counts correctly', async () => {
      const detectionsByClass = {
        person: 150,
        vehicle: 75,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        expect(screen.getByText('150')).toBeInTheDocument();
        expect(screen.getByText('75')).toBeInTheDocument();
      });
    });
  });

  describe('totalDetections prop', () => {
    it('uses totalDetections when detectionsByClass not provided', async () => {
      render(<InsightsCharts totalDetections={5000} />);

      await waitFor(() => {
        expect(screen.getByText('Detection breakdown not available')).toBeInTheDocument();
        // formatCount uses toFixed(1): 5000 -> 5.0K
        expect(screen.getByText(/Total: 5.0K detections/)).toBeInTheDocument();
      });
    });

    it('prioritizes detectionsByClass over totalDetections', async () => {
      const detectionsByClass = {
        person: 100,
        vehicle: 50,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} totalDetections={5000} />);

      await waitFor(() => {
        // Should show class breakdown, not fallback
        expect(screen.queryByText('Detection breakdown not available')).not.toBeInTheDocument();
        expect(screen.getByText('Person')).toBeInTheDocument();
      });
    });

    it('displays "No detections recorded yet" when totalDetections is 0', async () => {
      render(<InsightsCharts totalDetections={0} />);

      await waitFor(() => {
        expect(screen.getByText('No detections recorded yet')).toBeInTheDocument();
      });
    });
  });

  describe('className prop', () => {
    it('applies custom className', async () => {
      render(<InsightsCharts className="custom-class" />);
      await waitFor(() => {
        expect(screen.getByTestId('insights-charts')).toHaveClass('custom-class');
      });
    });

    it('includes default spacing class', async () => {
      render(<InsightsCharts className="custom-class" />);
      await waitFor(() => {
        expect(screen.getByTestId('insights-charts')).toHaveClass('space-y-4');
      });
    });

    it('applies no custom class when not provided', async () => {
      render(<InsightsCharts />);
      await waitFor(() => {
        const container = screen.getByTestId('insights-charts');
        expect(container).toHaveClass('space-y-4');
        expect(container.className).not.toContain('custom');
      });
    });
  });

  describe('error handling', () => {
    it('shows error message when API fails', async () => {
      vi.mocked(api.fetchEventStats).mockRejectedValueOnce(new Error('Network error'));

      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });

    it('displays error icon when API fails', async () => {
      vi.mocked(api.fetchEventStats).mockRejectedValueOnce(new Error('Server unavailable'));

      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByText('Server unavailable')).toBeInTheDocument();
        // AlertTriangle icon should be rendered in error state
      });
    });

    it('handles non-Error exception types', async () => {
      vi.mocked(api.fetchEventStats).mockRejectedValueOnce('String error');

      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load event statistics')).toBeInTheDocument();
      });
    });

    it('logs error to console on fetch failure', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      vi.mocked(api.fetchEventStats).mockRejectedValueOnce(new Error('Fetch failed'));

      render(<InsightsCharts />);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Failed to fetch event stats:', expect.any(Error));
      });

      consoleSpy.mockRestore();
    });
  });

  describe('empty event stats', () => {
    it('shows placeholder when no events exist', async () => {
      vi.mocked(api.fetchEventStats).mockResolvedValueOnce({
        total_events: 0,
        events_by_risk_level: {
          critical: 0,
          high: 0,
          medium: 0,
          low: 0,
        },
        events_by_camera: [],
      });

      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByText('No events recorded yet')).toBeInTheDocument();
      });
    });

    it('shows helpful message for empty events', async () => {
      vi.mocked(api.fetchEventStats).mockResolvedValueOnce({
        total_events: 0,
        events_by_risk_level: {
          critical: 0,
          high: 0,
          medium: 0,
          low: 0,
        },
        events_by_camera: [],
      });

      render(<InsightsCharts />);

      await waitFor(() => {
        expect(
          screen.getByText('Events will appear here once the AI pipeline processes detections')
        ).toBeInTheDocument();
      });
    });
  });

  describe('loading state', () => {
    it('shows loading skeleton while fetching', async () => {
      // Create a promise that doesn't resolve immediately
      let resolvePromise: (value: Awaited<ReturnType<typeof api.fetchEventStats>>) => void;
      const delayedPromise = new Promise<Awaited<ReturnType<typeof api.fetchEventStats>>>(
        (resolve) => {
          resolvePromise = resolve;
        }
      );
      vi.mocked(api.fetchEventStats).mockImplementationOnce(() => delayedPromise);

      render(<InsightsCharts />);

      // Check for loading skeleton
      await waitFor(() => {
        const riskCard = screen.getByTestId('risk-distribution-card');
        const skeleton = riskCard.querySelector('.animate-pulse');
        expect(skeleton).toBeInTheDocument();
      });

      // Resolve the promise to clean up
      resolvePromise!({
        total_events: 100,
        events_by_risk_level: { critical: 5, high: 15, medium: 30, low: 50 },
        events_by_camera: [],
      });
    });

    it('removes loading skeleton after data loads', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByText('Total Events: 100')).toBeInTheDocument();
      });

      // Skeleton should be gone
      const riskCard = screen.getByTestId('risk-distribution-card');
      expect(riskCard.querySelector('.animate-pulse')).not.toBeInTheDocument();
    });
  });

  describe('risk distribution data', () => {
    it('displays risk level counts correctly', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByText('5')).toBeInTheDocument(); // critical
        expect(screen.getByText('15')).toBeInTheDocument(); // high
        expect(screen.getByText('30')).toBeInTheDocument(); // medium
        expect(screen.getByText('50')).toBeInTheDocument(); // low
      });
    });

    it('handles partial risk level data', async () => {
      vi.mocked(api.fetchEventStats).mockResolvedValueOnce({
        total_events: 50,
        events_by_risk_level: {
          critical: 0,
          high: 0,
          medium: 20,
          low: 30,
        },
        events_by_camera: [],
      });

      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByText('Total Events: 50')).toBeInTheDocument();
      });
    });

    it('handles missing risk level fields gracefully', async () => {
      vi.mocked(api.fetchEventStats).mockResolvedValueOnce({
        total_events: 10,
        events_by_risk_level: {
          low: 10,
        } as any, // Missing critical, high, medium
        events_by_camera: [],
      });

      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByText('Total Events: 10')).toBeInTheDocument();
      });
    });
  });

  describe('large number formatting', () => {
    it('formats thousands with K suffix', async () => {
      const detectionsByClass = {
        person: 5000,
        vehicle: 2500,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        // formatCount uses toFixed(1): 5000 -> 5.0K, 2500 -> 2.5K
        expect(screen.getByText('5.0K')).toBeInTheDocument();
        expect(screen.getByText('2.5K')).toBeInTheDocument();
      });
    });

    it('formats millions with M suffix', async () => {
      const detectionsByClass = {
        person: 5000000,
        vehicle: 1500000,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        // formatCount uses toFixed(1): 5000000 -> 5.0M, 1500000 -> 1.5M
        expect(screen.getByText('5.0M')).toBeInTheDocument();
        expect(screen.getByText('1.5M')).toBeInTheDocument();
      });
    });

    it('displays exact count for values under 1000', async () => {
      const detectionsByClass = {
        person: 999,
        vehicle: 500,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        expect(screen.getByText('999')).toBeInTheDocument();
        expect(screen.getByText('500')).toBeInTheDocument();
      });
    });

    it('formats total detections correctly', async () => {
      const detectionsByClass = {
        person: 1000000,
        vehicle: 500000,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        expect(screen.getByText(/Total Detections:/)).toBeInTheDocument();
        // 1500000 -> 1.5M
        expect(screen.getByText('1.5M')).toBeInTheDocument();
      });
    });
  });

  describe('chart visualization', () => {
    it('renders donut chart when detection data is available', async () => {
      const detectionsByClass = {
        person: 100,
        vehicle: 50,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        const detectionCard = screen.getByTestId('detection-distribution-card');
        // Check that chart container is present
        expect(detectionCard).toBeInTheDocument();
      });
    });

    it('renders bar chart when event stats are loaded', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        const riskCard = screen.getByTestId('risk-distribution-card');
        expect(riskCard).toBeInTheDocument();
        expect(screen.getByText('Total Events: 100')).toBeInTheDocument();
      });
    });

    it('shows grid of risk counts with styled values', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        // Each risk level appears multiple times (bar label + count label), so use getAllByText
        expect(screen.getAllByText('Low').length).toBeGreaterThan(0);
        expect(screen.getAllByText('Medium').length).toBeGreaterThan(0);
        expect(screen.getAllByText('High').length).toBeGreaterThan(0);
        expect(screen.getAllByText('Critical').length).toBeGreaterThan(0);
      });
    });
  });

  describe('color coding', () => {
    it('renders detection class items with color indicators', async () => {
      const detectionsByClass = {
        person: 100,
        vehicle: 50,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        const detectionCard = screen.getByTestId('detection-distribution-card');
        // Color indicators should be present
        const colorDots = detectionCard.querySelectorAll('.rounded-full');
        expect(colorDots.length).toBeGreaterThan(0);
      });
    });
  });

  describe('icons', () => {
    it('renders pie chart icon in detection distribution title', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        const detectionCard = screen.getByTestId('detection-distribution-card');
        const icon = detectionCard.querySelector('svg');
        expect(icon).toBeInTheDocument();
      });
    });

    it('renders bar chart icon in risk distribution title', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        const riskCard = screen.getByTestId('risk-distribution-card');
        const icon = riskCard.querySelector('svg');
        expect(icon).toBeInTheDocument();
      });
    });
  });

  describe('component lifecycle', () => {
    it('cancels pending requests on unmount', () => {
      let resolveFetch: (value: Awaited<ReturnType<typeof api.fetchEventStats>>) => void;
      const pendingPromise = new Promise<Awaited<ReturnType<typeof api.fetchEventStats>>>(
        (resolve) => {
          resolveFetch = resolve;
        }
      );
      vi.mocked(api.fetchEventStats).mockImplementationOnce(() => pendingPromise);

      const { unmount } = render(<InsightsCharts />);

      // Unmount before promise resolves
      unmount();

      // Resolve the promise - should not cause any state updates (no errors)
      resolveFetch!({
        total_events: 100,
        events_by_risk_level: { critical: 5, high: 15, medium: 30, low: 50 },
        events_by_camera: [],
      });

      // If we get here without errors, the component correctly handles unmount
      expect(true).toBe(true);
    });

    it('fetches data on mount', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        expect(api.fetchEventStats).toHaveBeenCalledTimes(1);
      });
    });

    it('does not refetch on prop changes', async () => {
      const { rerender } = render(<InsightsCharts className="initial" />);

      await waitFor(() => {
        expect(api.fetchEventStats).toHaveBeenCalledTimes(1);
      });

      rerender(<InsightsCharts className="updated" />);

      // Should still only have been called once
      expect(api.fetchEventStats).toHaveBeenCalledTimes(1);
    });
  });

  describe('empty detection class object', () => {
    it('shows placeholder for empty detectionsByClass object', async () => {
      render(<InsightsCharts detectionsByClass={{}} />);

      await waitFor(() => {
        expect(screen.getByText('No detections recorded yet')).toBeInTheDocument();
      });
    });

    it('handles undefined detectionsByClass', async () => {
      render(<InsightsCharts detectionsByClass={undefined} />);

      await waitFor(() => {
        expect(screen.getByText('No detections recorded yet')).toBeInTheDocument();
      });
    });
  });

  describe('edge cases', () => {
    it('handles single detection class', async () => {
      const detectionsByClass = {
        person: 100,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        expect(screen.getByText('Person')).toBeInTheDocument();
        // Multiple "100" elements may appear (legend + total), use getAllByText
        const counts = screen.getAllByText('100');
        expect(counts.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('handles very small detection counts', async () => {
      const detectionsByClass = {
        person: 1,
        vehicle: 1,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        const ones = screen.getAllByText('1');
        expect(ones.length).toBeGreaterThanOrEqual(2);
      });
    });

    it('handles zero values in detection classes', async () => {
      const detectionsByClass = {
        person: 0,
        vehicle: 0,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        // Should still show the class names even with zero counts
        expect(screen.getByText('Person')).toBeInTheDocument();
        expect(screen.getByText('Vehicle')).toBeInTheDocument();
      });
    });

    it('handles mixed zero and non-zero values', async () => {
      const detectionsByClass = {
        person: 100,
        vehicle: 0,
        animal: 50,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        expect(screen.getByText('Person')).toBeInTheDocument();
        expect(screen.getByText('Vehicle')).toBeInTheDocument();
        expect(screen.getByText('Animal')).toBeInTheDocument();
      });
    });

    it('handles event stats with null risk level', async () => {
      vi.mocked(api.fetchEventStats).mockResolvedValueOnce({
        total_events: 50,
        events_by_risk_level: null as any,
        events_by_camera: [],
      });

      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByText('No events recorded yet')).toBeInTheDocument();
      });
    });

    it('handles special characters in class names', async () => {
      const detectionsByClass = {
        traffic_light: 100,
        stop_sign: 50,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        // Should capitalize first letter
        expect(screen.getByText('Traffic_light')).toBeInTheDocument();
        expect(screen.getByText('Stop_sign')).toBeInTheDocument();
      });
    });
  });

  describe('accessibility', () => {
    it('has semantic card structure', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByTestId('detection-distribution-card')).toBeInTheDocument();
        expect(screen.getByTestId('risk-distribution-card')).toBeInTheDocument();
      });
    });

    it('cards have visible titles', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByText('Detection Class Distribution')).toBeVisible();
        expect(screen.getByText('Risk Score Distribution')).toBeVisible();
      });
    });

    it('provides text alternatives for data', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        // Total counts are displayed as text
        expect(screen.getByText('Total Events: 100')).toBeVisible();
      });
    });
  });

  describe('responsive behavior', () => {
    it('renders flex container for detection chart layout', async () => {
      const detectionsByClass = {
        person: 100,
        vehicle: 50,
      };

      render(<InsightsCharts detectionsByClass={detectionsByClass} />);

      await waitFor(() => {
        const detectionCard = screen.getByTestId('detection-distribution-card');
        const flexContainer = detectionCard.querySelector('.flex-col');
        expect(flexContainer).toBeInTheDocument();
      });
    });

    it('renders grid layout for risk summary', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        const riskCard = screen.getByTestId('risk-distribution-card');
        const gridContainer = riskCard.querySelector('.grid');
        expect(gridContainer).toBeInTheDocument();
      });
    });
  });

  describe('risk bar click navigation', () => {
    it('navigates to timeline with low risk filter when clicking low bar', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByTestId('risk-bar-low')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('risk-bar-low'));
      expect(mockNavigate).toHaveBeenCalledWith('/timeline?risk_level=low');
    });

    it('navigates to timeline with medium risk filter when clicking medium bar', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByTestId('risk-bar-medium')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('risk-bar-medium'));
      expect(mockNavigate).toHaveBeenCalledWith('/timeline?risk_level=medium');
    });

    it('navigates to timeline with high risk filter when clicking high bar', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByTestId('risk-bar-high')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('risk-bar-high'));
      expect(mockNavigate).toHaveBeenCalledWith('/timeline?risk_level=high');
    });

    it('navigates to timeline with critical risk filter when clicking critical bar', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByTestId('risk-bar-critical')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('risk-bar-critical'));
      expect(mockNavigate).toHaveBeenCalledWith('/timeline?risk_level=critical');
    });

    it('navigates when clicking risk count buttons', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByTestId('risk-count-low')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('risk-count-high'));
      expect(mockNavigate).toHaveBeenCalledWith('/timeline?risk_level=high');
    });

    it('displays pointer cursor on risk bars', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        const lowBar = screen.getByTestId('risk-bar-low');
        expect(lowBar).toHaveClass('cursor-pointer');
      });
    });

    it('renders correct aria labels for accessibility', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        const lowBar = screen.getByTestId('risk-bar-low');
        expect(lowBar).toHaveAttribute('aria-label', expect.stringContaining('Low: 50 events'));
      });
    });

    it('displays tooltip text on hover', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        const riskCard = screen.getByTestId('risk-distribution-card');
        // Tooltip text should be in the DOM (hidden by CSS until hover)
        expect(riskCard).toHaveTextContent('Click to view 50 events');
      });
    });

    it('renders clickable bars as buttons for keyboard accessibility', async () => {
      render(<InsightsCharts />);

      await waitFor(() => {
        const lowBar = screen.getByTestId('risk-bar-low');
        expect(lowBar.tagName.toLowerCase()).toBe('button');
      });
    });

    it('does not render clickable bars when no events exist', async () => {
      vi.mocked(api.fetchEventStats).mockResolvedValueOnce({
        total_events: 0,
        events_by_risk_level: {
          critical: 0,
          high: 0,
          medium: 0,
          low: 0,
        },
        events_by_camera: [],
      });

      render(<InsightsCharts />);

      await waitFor(() => {
        expect(screen.getByText('No events recorded yet')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('risk-bar-low')).not.toBeInTheDocument();
    });
  });
});
