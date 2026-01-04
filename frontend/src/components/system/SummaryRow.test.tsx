import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import SummaryRow from './SummaryRow';

import type { IndicatorData, HealthStatus } from './SummaryRow';

describe('SummaryRow', () => {
  const createIndicator = (
    id: string,
    label: string,
    status: HealthStatus = 'healthy',
    overrides: Partial<IndicatorData> = {}
  ): IndicatorData => ({
    id,
    label,
    status,
    ...overrides,
  });

  const defaultProps = {
    overall: createIndicator('overall', 'Overall', 'healthy'),
    gpu: createIndicator('gpu', 'GPU', 'healthy', { primaryValue: '38%', secondaryValue: '40C' }),
    pipeline: createIndicator('pipeline', 'Pipeline', 'healthy', { primaryValue: '0 queue' }),
    aiModels: createIndicator('aiModels', 'AI Models', 'healthy', { primaryValue: '2/2' }),
    infrastructure: createIndicator('infrastructure', 'Infra', 'healthy', { primaryValue: '4/4' }),
  };

  const mockOnClick = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the summary row container', () => {
      render(<SummaryRow {...defaultProps} />);
      expect(screen.getByTestId('summary-row')).toBeInTheDocument();
    });

    it('renders all 5 indicators', () => {
      render(<SummaryRow {...defaultProps} />);

      expect(screen.getByTestId('summary-indicator-overall')).toBeInTheDocument();
      expect(screen.getByTestId('summary-indicator-gpu')).toBeInTheDocument();
      expect(screen.getByTestId('summary-indicator-pipeline')).toBeInTheDocument();
      expect(screen.getByTestId('summary-indicator-aiModels')).toBeInTheDocument();
      expect(screen.getByTestId('summary-indicator-infrastructure')).toBeInTheDocument();
    });

    it('displays labels for all indicators', () => {
      render(<SummaryRow {...defaultProps} />);

      expect(screen.getByText('Overall')).toBeInTheDocument();
      expect(screen.getByText('GPU')).toBeInTheDocument();
      expect(screen.getByText('Pipeline')).toBeInTheDocument();
      expect(screen.getByText('AI Models')).toBeInTheDocument();
      expect(screen.getByText('Infra')).toBeInTheDocument();
    });
  });

  describe('status display', () => {
    it('displays healthy status correctly', () => {
      render(<SummaryRow {...defaultProps} />);

      const overallIndicator = screen.getByTestId('summary-indicator-overall');
      expect(overallIndicator).toHaveAttribute(
        'aria-label',
        expect.stringContaining('Healthy')
      );
    });

    it('displays degraded status correctly', () => {
      const props = {
        ...defaultProps,
        gpu: createIndicator('gpu', 'GPU', 'degraded', { primaryValue: '85%' }),
      };

      render(<SummaryRow {...props} />);

      const gpuIndicator = screen.getByTestId('summary-indicator-gpu');
      expect(gpuIndicator).toHaveAttribute(
        'aria-label',
        expect.stringContaining('Degraded')
      );
    });

    it('displays critical status correctly', () => {
      const props = {
        ...defaultProps,
        overall: createIndicator('overall', 'Overall', 'critical'),
      };

      render(<SummaryRow {...props} />);

      const overallIndicator = screen.getByTestId('summary-indicator-overall');
      expect(overallIndicator).toHaveAttribute(
        'aria-label',
        expect.stringContaining('Critical')
      );
    });

    it('displays unknown status correctly', () => {
      const props = {
        ...defaultProps,
        infrastructure: createIndicator('infrastructure', 'Infra', 'unknown'),
      };

      render(<SummaryRow {...props} />);

      const infraIndicator = screen.getByTestId('summary-indicator-infrastructure');
      expect(infraIndicator).toHaveAttribute(
        'aria-label',
        expect.stringContaining('Unknown')
      );
    });
  });

  describe('metric values', () => {
    it('displays primary values', () => {
      render(<SummaryRow {...defaultProps} />);

      expect(screen.getByText('38%')).toBeInTheDocument();
      expect(screen.getByText('0 queue')).toBeInTheDocument();
      expect(screen.getByText('2/2')).toBeInTheDocument();
      expect(screen.getByText('4/4')).toBeInTheDocument();
    });

    it('displays secondary values', () => {
      render(<SummaryRow {...defaultProps} />);

      expect(screen.getByText('40C')).toBeInTheDocument();
    });

    it('displays tertiary values', () => {
      const props = {
        ...defaultProps,
        gpu: createIndicator('gpu', 'GPU', 'healthy', {
          primaryValue: '38%',
          secondaryValue: '40C',
          tertiaryValue: '0.2/24GB',
        }),
      };

      render(<SummaryRow {...props} />);

      expect(screen.getByText('0.2/24GB')).toBeInTheDocument();
    });

    it('falls back to status text when no primary value', () => {
      render(<SummaryRow {...defaultProps} />);

      // Overall indicator has no primary value, should show "Healthy"
      const healthyTexts = screen.getAllByText('Healthy');
      expect(healthyTexts.length).toBeGreaterThan(0);
    });
  });

  describe('click interaction', () => {
    it('calls onIndicatorClick when indicator is clicked', () => {
      render(<SummaryRow {...defaultProps} onIndicatorClick={mockOnClick} />);

      fireEvent.click(screen.getByTestId('summary-indicator-gpu'));
      expect(mockOnClick).toHaveBeenCalledWith('gpu');
    });

    it('calls onIndicatorClick with correct id for each indicator', () => {
      render(<SummaryRow {...defaultProps} onIndicatorClick={mockOnClick} />);

      fireEvent.click(screen.getByTestId('summary-indicator-overall'));
      expect(mockOnClick).toHaveBeenCalledWith('overall');

      fireEvent.click(screen.getByTestId('summary-indicator-pipeline'));
      expect(mockOnClick).toHaveBeenCalledWith('pipeline');

      fireEvent.click(screen.getByTestId('summary-indicator-aiModels'));
      expect(mockOnClick).toHaveBeenCalledWith('aiModels');

      fireEvent.click(screen.getByTestId('summary-indicator-infrastructure'));
      expect(mockOnClick).toHaveBeenCalledWith('infrastructure');
    });

    it('does not crash when onIndicatorClick is not provided', () => {
      render(<SummaryRow {...defaultProps} />);

      // Should not throw
      fireEvent.click(screen.getByTestId('summary-indicator-gpu'));
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(<SummaryRow {...defaultProps} className="custom-class" />);

      expect(screen.getByTestId('summary-row')).toHaveClass('custom-class');
    });

    it('applies healthy status styling', () => {
      render(<SummaryRow {...defaultProps} />);

      const indicator = screen.getByTestId('summary-indicator-overall');
      expect(indicator.className).toContain('bg-green');
    });

    it('applies degraded status styling', () => {
      const props = {
        ...defaultProps,
        gpu: createIndicator('gpu', 'GPU', 'degraded'),
      };

      render(<SummaryRow {...props} />);

      const indicator = screen.getByTestId('summary-indicator-gpu');
      expect(indicator.className).toContain('bg-yellow');
    });

    it('applies critical status styling', () => {
      const props = {
        ...defaultProps,
        pipeline: createIndicator('pipeline', 'Pipeline', 'critical'),
      };

      render(<SummaryRow {...props} />);

      const indicator = screen.getByTestId('summary-indicator-pipeline');
      expect(indicator.className).toContain('bg-red');
    });
  });

  describe('accessibility', () => {
    it('has correct aria-label on indicators', () => {
      render(<SummaryRow {...defaultProps} />);

      const gpuIndicator = screen.getByTestId('summary-indicator-gpu');
      expect(gpuIndicator).toHaveAttribute('aria-label', 'GPU: Healthy');
    });

    it('indicators are buttons for keyboard accessibility', () => {
      render(<SummaryRow {...defaultProps} />);

      const indicator = screen.getByTestId('summary-indicator-overall');
      expect(indicator.tagName.toLowerCase()).toBe('button');
    });

    it('indicators have correct type attribute', () => {
      render(<SummaryRow {...defaultProps} />);

      const indicator = screen.getByTestId('summary-indicator-overall');
      expect(indicator).toHaveAttribute('type', 'button');
    });
  });

  describe('all statuses combined', () => {
    it('handles mixed status states', () => {
      const props = {
        overall: createIndicator('overall', 'Overall', 'degraded'),
        gpu: createIndicator('gpu', 'GPU', 'healthy', { primaryValue: '38%' }),
        pipeline: createIndicator('pipeline', 'Pipeline', 'critical', { primaryValue: '50 queue' }),
        aiModels: createIndicator('aiModels', 'AI Models', 'healthy', { primaryValue: '2/2' }),
        infrastructure: createIndicator('infrastructure', 'Infra', 'unknown'),
      };

      render(<SummaryRow {...props} />);

      // Verify all render correctly
      expect(screen.getByTestId('summary-indicator-overall')).toBeInTheDocument();
      expect(screen.getByTestId('summary-indicator-gpu')).toBeInTheDocument();
      expect(screen.getByTestId('summary-indicator-pipeline')).toBeInTheDocument();
      expect(screen.getByTestId('summary-indicator-aiModels')).toBeInTheDocument();
      expect(screen.getByTestId('summary-indicator-infrastructure')).toBeInTheDocument();

      // Verify values
      expect(screen.getByText('38%')).toBeInTheDocument();
      expect(screen.getByText('50 queue')).toBeInTheDocument();
      expect(screen.getByText('2/2')).toBeInTheDocument();
    });
  });
});
