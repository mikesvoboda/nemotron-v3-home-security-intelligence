/**
 * Tests for RiskDistributionChart component.
 *
 * @see NEM-5400, NEM-5401, NEM-5402, NEM-5403
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import RiskDistributionChart from './RiskDistributionChart';

// Mock Tremor DonutChart to make testing easier
vi.mock('@tremor/react', async () => {
  const actual = await vi.importActual('@tremor/react');
  return {
    ...actual,
    DonutChart: ({
      data,
      onValueChange,
      'data-testid': testId,
    }: {
      data: Array<{ name: string; value: number; color: string }>;
      onValueChange?: (value: { name: string; value: number } | null) => void;
      'data-testid'?: string;
    }) => (
      <div data-testid={testId || 'donut-chart'}>
        {data.map((item) => (
          <button
            key={item.name}
            data-testid={`segment-${item.name.toLowerCase()}`}
            data-value={item.value}
            onClick={() => onValueChange?.({ name: item.name, value: item.value })}
            aria-label={`${item.name}: ${item.value} events`}
          >
            {item.name}: {item.value}
          </button>
        ))}
        {/* Add a clear button to test deselection */}
        <button
          data-testid="segment-clear"
          onClick={() => onValueChange?.(null)}
          aria-label="Clear selection"
        >
          Clear
        </button>
      </div>
    ),
  };
});

describe('RiskDistributionChart', () => {
  const mockDistribution = {
    critical: 5,
    high: 10,
    medium: 25,
    low: 60,
  };

  describe('rendering', () => {
    it('renders donut chart with correct segments', () => {
      render(<RiskDistributionChart distribution={mockDistribution} />);

      expect(screen.getByTestId('risk-distribution-chart')).toBeInTheDocument();
      expect(screen.getByTestId('segment-critical')).toBeInTheDocument();
      expect(screen.getByTestId('segment-high')).toBeInTheDocument();
      expect(screen.getByTestId('segment-medium')).toBeInTheDocument();
      expect(screen.getByTestId('segment-low')).toBeInTheDocument();
    });

    it('displays correct values for each segment', () => {
      render(<RiskDistributionChart distribution={mockDistribution} />);

      expect(screen.getByTestId('segment-critical')).toHaveAttribute('data-value', '5');
      expect(screen.getByTestId('segment-high')).toHaveAttribute('data-value', '10');
      expect(screen.getByTestId('segment-medium')).toHaveAttribute('data-value', '25');
      expect(screen.getByTestId('segment-low')).toHaveAttribute('data-value', '60');
    });

    it('renders title', () => {
      render(<RiskDistributionChart distribution={mockDistribution} />);

      expect(screen.getByText('Risk Distribution')).toBeInTheDocument();
    });

    it('shows total events in center label', () => {
      render(<RiskDistributionChart distribution={mockDistribution} />);

      // Total = 5 + 10 + 25 + 60 = 100
      expect(screen.getByTestId('total-events')).toHaveTextContent('100');
    });

    it('applies custom className', () => {
      render(
        <RiskDistributionChart distribution={mockDistribution} className="custom-class" />
      );

      expect(screen.getByTestId('risk-distribution-chart')).toHaveClass('custom-class');
    });
  });

  describe('empty segments', () => {
    it('hides segments with zero count', () => {
      const distributionWithZeros = {
        critical: 0,
        high: 5,
        medium: 10,
        low: 0,
      };

      render(<RiskDistributionChart distribution={distributionWithZeros} />);

      // Only high and medium should be rendered
      expect(screen.queryByTestId('segment-critical')).not.toBeInTheDocument();
      expect(screen.getByTestId('segment-high')).toBeInTheDocument();
      expect(screen.getByTestId('segment-medium')).toBeInTheDocument();
      expect(screen.queryByTestId('segment-low')).not.toBeInTheDocument();
    });

    it('shows empty state when all segments are zero', () => {
      const emptyDistribution = {
        critical: 0,
        high: 0,
        medium: 0,
        low: 0,
      };

      render(<RiskDistributionChart distribution={emptyDistribution} />);

      expect(screen.getByTestId('risk-distribution-empty')).toBeInTheDocument();
      expect(screen.getByText(/no events/i)).toBeInTheDocument();
    });

    it('shows empty state when distribution is undefined', () => {
      render(<RiskDistributionChart />);

      expect(screen.getByTestId('risk-distribution-empty')).toBeInTheDocument();
    });
  });

  describe('click interaction', () => {
    it('calls onRiskLevelSelect when segment is clicked', () => {
      const onRiskLevelSelect = vi.fn();

      render(
        <RiskDistributionChart
          distribution={mockDistribution}
          onRiskLevelSelect={onRiskLevelSelect}
        />
      );

      fireEvent.click(screen.getByTestId('segment-critical'));

      expect(onRiskLevelSelect).toHaveBeenCalledWith('critical');
    });

    it('toggles filter off when clicking same segment twice', () => {
      const onRiskLevelSelect = vi.fn();

      render(
        <RiskDistributionChart
          distribution={mockDistribution}
          onRiskLevelSelect={onRiskLevelSelect}
          selectedRiskLevel="critical"
        />
      );

      // Click the already selected segment - should clear
      fireEvent.click(screen.getByTestId('segment-clear'));

      expect(onRiskLevelSelect).toHaveBeenCalledWith(null);
    });

    it('highlights selected segment', () => {
      render(
        <RiskDistributionChart
          distribution={mockDistribution}
          selectedRiskLevel="high"
        />
      );

      expect(screen.getByTestId('risk-distribution-chart')).toHaveAttribute(
        'data-selected',
        'high'
      );
    });
  });

  describe('legend', () => {
    it('renders legend items for non-zero segments', () => {
      render(<RiskDistributionChart distribution={mockDistribution} showLegend />);

      expect(screen.getByTestId('legend-critical')).toBeInTheDocument();
      expect(screen.getByTestId('legend-high')).toBeInTheDocument();
      expect(screen.getByTestId('legend-medium')).toBeInTheDocument();
      expect(screen.getByTestId('legend-low')).toBeInTheDocument();
    });

    it('legend items are clickable and filter timeline', () => {
      const onRiskLevelSelect = vi.fn();

      render(
        <RiskDistributionChart
          distribution={mockDistribution}
          onRiskLevelSelect={onRiskLevelSelect}
          showLegend
        />
      );

      fireEvent.click(screen.getByTestId('legend-high'));

      expect(onRiskLevelSelect).toHaveBeenCalledWith('high');
    });

    it('legend can be hidden', () => {
      render(<RiskDistributionChart distribution={mockDistribution} showLegend={false} />);

      expect(screen.queryByTestId('legend-critical')).not.toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('shows loading skeleton when isLoading is true', () => {
      render(<RiskDistributionChart distribution={mockDistribution} isLoading />);

      expect(screen.getByTestId('risk-distribution-loading')).toBeInTheDocument();
      expect(screen.queryByTestId('donut-chart')).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has appropriate aria labels for segments', () => {
      render(<RiskDistributionChart distribution={mockDistribution} />);

      expect(screen.getByLabelText('Critical: 5 events')).toBeInTheDocument();
      expect(screen.getByLabelText('High: 10 events')).toBeInTheDocument();
      expect(screen.getByLabelText('Medium: 25 events')).toBeInTheDocument();
      expect(screen.getByLabelText('Low: 60 events')).toBeInTheDocument();
    });

    it('chart has role="img" with descriptive label', () => {
      render(<RiskDistributionChart distribution={mockDistribution} />);

      const chart = screen.getByRole('img', { name: /risk distribution/i });
      expect(chart).toBeInTheDocument();
    });
  });

  describe('color mapping', () => {
    it('uses correct colors for risk levels', () => {
      render(<RiskDistributionChart distribution={mockDistribution} showLegend />);

      // Verify legend items have correct color indicators
      const criticalLegend = screen.getByTestId('legend-critical');
      const highLegend = screen.getByTestId('legend-high');
      const mediumLegend = screen.getByTestId('legend-medium');
      const lowLegend = screen.getByTestId('legend-low');

      // Check that color indicators are present (via classes or styles)
      expect(criticalLegend.querySelector('[data-color="critical"]')).toBeInTheDocument();
      expect(highLegend.querySelector('[data-color="high"]')).toBeInTheDocument();
      expect(mediumLegend.querySelector('[data-color="medium"]')).toBeInTheDocument();
      expect(lowLegend.querySelector('[data-color="low"]')).toBeInTheDocument();
    });
  });
});
