/**
 * Tests for TestResultsComparison component
 *
 * @see NEM-2698 - Implement prompt A/B testing UI with real inference comparison
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import TestResultsComparison from './TestResultsComparison';

import type { TestResult } from './TestResultsComparison';

// ============================================================================
// Test Data
// ============================================================================

const mockCurrentResult: TestResult = {
  riskScore: 72,
  riskLevel: 'high',
  reasoning: 'Person detected near entrance with suspicious behavior pattern.',
  summary: 'High risk activity detected at front door.',
  processingTimeMs: 1200,
  tokensUsed: 450,
};

const mockModifiedResult: TestResult = {
  riskScore: 85,
  riskLevel: 'critical',
  reasoning: 'Person detected near entrance exhibiting highly suspicious behavior.',
  summary: 'Critical risk activity detected at front door.',
  processingTimeMs: 1400,
  tokensUsed: 520,
};

const mockLowerResult: TestResult = {
  riskScore: 45,
  riskLevel: 'medium',
  reasoning: 'Person detected, but behavior appears normal.',
  summary: 'Medium risk activity detected at front door.',
  processingTimeMs: 1100,
  tokensUsed: 380,
};

// ============================================================================
// Tests
// ============================================================================

describe('TestResultsComparison', () => {
  describe('rendering', () => {
    it('renders the component', () => {
      render(<TestResultsComparison currentResult={null} modifiedResult={null} />);

      expect(screen.getByTestId('test-results-comparison')).toBeInTheDocument();
    });

    it('renders both result cards', () => {
      render(
        <TestResultsComparison
          currentResult={mockCurrentResult}
          modifiedResult={mockModifiedResult}
        />
      );

      expect(screen.getByTestId('result-card-current')).toBeInTheDocument();
      expect(screen.getByTestId('result-card-modified')).toBeInTheDocument();
    });

    it('displays version number when provided', () => {
      render(
        <TestResultsComparison
          currentResult={mockCurrentResult}
          modifiedResult={mockModifiedResult}
          currentVersion={3}
        />
      );

      expect(screen.getByText(/Current Config \(v3\)/i)).toBeInTheDocument();
    });

    it('renders loading state', () => {
      render(<TestResultsComparison currentResult={null} modifiedResult={null} isLoading={true} />);

      expect(screen.getAllByText(/Running inference/i)).toHaveLength(2);
    });

    it('renders error state', () => {
      const errorMessage = 'Failed to run inference';

      render(
        <TestResultsComparison currentResult={null} modifiedResult={null} error={errorMessage} />
      );

      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });

    it('renders no results message when results are null', () => {
      render(<TestResultsComparison currentResult={null} modifiedResult={null} />);

      expect(screen.getAllByText(/No results yet/i)).toHaveLength(2);
    });
  });

  describe('result display', () => {
    it('displays risk scores correctly', () => {
      render(
        <TestResultsComparison
          currentResult={mockCurrentResult}
          modifiedResult={mockModifiedResult}
        />
      );

      expect(screen.getByText('72')).toBeInTheDocument();
      expect(screen.getByText('85')).toBeInTheDocument();
    });

    it('displays risk level badges', () => {
      render(
        <TestResultsComparison
          currentResult={mockCurrentResult}
          modifiedResult={mockModifiedResult}
        />
      );

      // Use getAllByText since risk levels also appear in summaries
      const highBadges = screen.getAllByText(/High/i);
      const criticalBadges = screen.getAllByText(/Critical/i);
      expect(highBadges.length).toBeGreaterThan(0);
      expect(criticalBadges.length).toBeGreaterThan(0);
    });

    it('displays processing times', () => {
      render(
        <TestResultsComparison
          currentResult={mockCurrentResult}
          modifiedResult={mockModifiedResult}
        />
      );

      expect(screen.getByText('1.2s')).toBeInTheDocument();
      expect(screen.getByText('1.4s')).toBeInTheDocument();
    });

    it('displays token counts when provided', () => {
      render(
        <TestResultsComparison
          currentResult={mockCurrentResult}
          modifiedResult={mockModifiedResult}
        />
      );

      expect(screen.getByText('450 tokens')).toBeInTheDocument();
      expect(screen.getByText('520 tokens')).toBeInTheDocument();
    });

    it('displays summaries', () => {
      render(
        <TestResultsComparison
          currentResult={mockCurrentResult}
          modifiedResult={mockModifiedResult}
        />
      );

      expect(screen.getByText(/High risk activity detected at front door/i)).toBeInTheDocument();
      expect(
        screen.getByText(/Critical risk activity detected at front door/i)
      ).toBeInTheDocument();
    });

    it('displays reasoning text', () => {
      render(
        <TestResultsComparison
          currentResult={mockCurrentResult}
          modifiedResult={mockModifiedResult}
        />
      );

      expect(
        screen.getByText(/Person detected near entrance with suspicious/i)
      ).toBeInTheDocument();
      expect(screen.getByText(/Person detected near entrance exhibiting/i)).toBeInTheDocument();
    });
  });

  describe('delta summary', () => {
    it('shows delta summary when both results exist', () => {
      render(
        <TestResultsComparison
          currentResult={mockCurrentResult}
          modifiedResult={mockModifiedResult}
        />
      );

      expect(screen.getByTestId('delta-summary')).toBeInTheDocument();
      expect(screen.getByText(/Comparison Summary/i)).toBeInTheDocument();
    });

    it('does not show delta summary when results are null', () => {
      render(<TestResultsComparison currentResult={null} modifiedResult={null} />);

      expect(screen.queryByTestId('delta-summary')).not.toBeInTheDocument();
    });

    it('shows positive delta with up arrow when score increases', () => {
      render(
        <TestResultsComparison
          currentResult={mockCurrentResult}
          modifiedResult={mockModifiedResult}
        />
      );

      // Modified score (85) - Current score (72) = +13
      expect(screen.getByText(/\+13/i)).toBeInTheDocument();
    });

    it('shows negative delta with down arrow when score decreases', () => {
      render(
        <TestResultsComparison currentResult={mockCurrentResult} modifiedResult={mockLowerResult} />
      );

      // Modified score (45) - Current score (72) = -27
      expect(screen.getByText(/-27/i)).toBeInTheDocument();
    });

    it('shows no change indicator when scores are equal', () => {
      render(
        <TestResultsComparison
          currentResult={mockCurrentResult}
          modifiedResult={{ ...mockCurrentResult }}
        />
      );

      expect(screen.getByText(/No change/i)).toBeInTheDocument();
    });

    it('shows inference time delta', () => {
      render(
        <TestResultsComparison
          currentResult={mockCurrentResult}
          modifiedResult={mockModifiedResult}
        />
      );

      // Modified time (1400) - Current time (1200) = +200ms
      expect(screen.getByText(/\+200ms/i)).toBeInTheDocument();
    });
  });

  describe('formatting', () => {
    it('formats milliseconds correctly for short times', () => {
      render(
        <TestResultsComparison
          currentResult={{ ...mockCurrentResult, processingTimeMs: 500 }}
          modifiedResult={mockModifiedResult}
        />
      );

      expect(screen.getByText('500ms')).toBeInTheDocument();
    });

    it('formats milliseconds correctly for long times', () => {
      render(
        <TestResultsComparison
          currentResult={{ ...mockCurrentResult, processingTimeMs: 5500 }}
          modifiedResult={mockModifiedResult}
        />
      );

      expect(screen.getByText('5.5s')).toBeInTheDocument();
    });
  });

  describe('partial results', () => {
    it('handles only current result', () => {
      render(<TestResultsComparison currentResult={mockCurrentResult} modifiedResult={null} />);

      expect(screen.getByTestId('result-card-current')).toBeInTheDocument();
      expect(screen.getByText('72')).toBeInTheDocument();
      // Should not show delta since modified result is null
      expect(screen.queryByTestId('delta-summary')).not.toBeInTheDocument();
    });

    it('handles only modified result', () => {
      render(<TestResultsComparison currentResult={null} modifiedResult={mockModifiedResult} />);

      expect(screen.getByTestId('result-card-modified')).toBeInTheDocument();
      expect(screen.getByText('85')).toBeInTheDocument();
      // Should not show delta since current result is null
      expect(screen.queryByTestId('delta-summary')).not.toBeInTheDocument();
    });
  });
});
