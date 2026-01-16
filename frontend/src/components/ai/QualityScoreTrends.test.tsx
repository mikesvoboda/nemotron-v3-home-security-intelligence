/**
 * Tests for QualityScoreTrends component
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import QualityScoreTrends from './QualityScoreTrends';

describe('QualityScoreTrends', () => {
  const defaultProps = {
    avgQualityScore: 4.2,
    avgConsistencyRate: 4.0,
    avgEnrichmentUtilization: 0.75,
    totalEvents: 1000,
    fullyEvaluatedEvents: 800,
  };

  it('renders all score cards', () => {
    render(<QualityScoreTrends {...defaultProps} />);

    expect(screen.getByTestId('quality-score-card')).toBeInTheDocument();
    expect(screen.getByTestId('consistency-rate-card')).toBeInTheDocument();
    expect(screen.getByTestId('enrichment-utilization-card')).toBeInTheDocument();
    expect(screen.getByTestId('evaluation-coverage-card')).toBeInTheDocument();
  });

  it('displays quality score correctly', () => {
    render(<QualityScoreTrends {...defaultProps} />);

    expect(screen.getByText('4.2 / 5')).toBeInTheDocument();
  });

  it('displays consistency rate correctly', () => {
    render(<QualityScoreTrends {...defaultProps} />);

    expect(screen.getByText('4.0 / 5')).toBeInTheDocument();
  });

  it('displays enrichment utilization as percentage', () => {
    render(<QualityScoreTrends {...defaultProps} />);

    expect(screen.getByText('75%')).toBeInTheDocument();
  });

  it('displays evaluation coverage percentage', () => {
    render(<QualityScoreTrends {...defaultProps} />);

    // 800 / 1000 = 80%
    expect(screen.getByText('80%')).toBeInTheDocument();
  });

  it('handles null quality score', () => {
    render(<QualityScoreTrends {...defaultProps} avgQualityScore={null} />);

    expect(screen.getByText('N/A')).toBeInTheDocument();
  });

  it('handles null consistency rate', () => {
    render(<QualityScoreTrends {...defaultProps} avgConsistencyRate={null} />);

    expect(screen.getAllByText('N/A')).toHaveLength(1);
  });

  it('handles null enrichment utilization', () => {
    render(<QualityScoreTrends {...defaultProps} avgEnrichmentUtilization={null} />);

    expect(screen.getAllByText('N/A').length).toBeGreaterThanOrEqual(1);
  });

  it('handles zero total events', () => {
    render(<QualityScoreTrends {...defaultProps} totalEvents={0} fullyEvaluatedEvents={0} />);

    // Evaluation coverage should be 0%
    expect(screen.getByText('0%')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<QualityScoreTrends {...defaultProps} className="custom-class" />);

    const container = screen.getByTestId('quality-score-trends');
    expect(container).toHaveClass('custom-class');
  });
});
