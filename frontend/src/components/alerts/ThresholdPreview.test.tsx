/**
 * Tests for ThresholdPreview component.
 *
 * @see NEM-3604 Alert Threshold Configuration
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import ThresholdPreview from './ThresholdPreview';

import type { UseThresholdPreviewResult } from '../../hooks/useThresholdPreview';

// Mock preview state factory
function createMockPreviewState(
  overrides: Partial<UseThresholdPreviewResult> = {}
): UseThresholdPreviewResult {
  return {
    isLoading: false,
    error: null,
    eventsMatched: null,
    eventsTested: null,
    matchRate: null,
    testResponse: null,
    refresh: vi.fn(),
    clear: vi.fn(),
    ...overrides,
  };
}

describe('ThresholdPreview', () => {
  describe('Loading State', () => {
    it('should show loading indicator when isLoading is true', () => {
      const previewState = createMockPreviewState({ isLoading: true });

      render(<ThresholdPreview previewState={previewState} />);

      expect(screen.getByText('Calculating preview...')).toBeInTheDocument();
    });

    it('should render loader icon during loading', () => {
      const previewState = createMockPreviewState({ isLoading: true });

      render(<ThresholdPreview previewState={previewState} />);

      // Check that the container is rendered with testId
      expect(screen.getByTestId('threshold-preview')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should show error message when error is present', () => {
      const previewState = createMockPreviewState({
        error: 'Failed to load preview',
      });

      render(<ThresholdPreview previewState={previewState} />);

      expect(screen.getByText('Preview unavailable')).toBeInTheDocument();
    });

    it('should have alert role when showing error', () => {
      const previewState = createMockPreviewState({
        error: 'Network error',
      });

      render(<ThresholdPreview previewState={previewState} />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('should show retry button when error occurs', () => {
      const previewState = createMockPreviewState({
        error: 'API error',
      });

      render(<ThresholdPreview previewState={previewState} showRefresh={true} />);

      expect(screen.getByTestId('threshold-preview-retry')).toBeInTheDocument();
    });

    it('should call refresh on retry click', async () => {
      const refresh = vi.fn();
      const previewState = createMockPreviewState({
        error: 'API error',
        refresh,
      });

      render(<ThresholdPreview previewState={previewState} showRefresh={true} />);

      const retryButton = screen.getByTestId('threshold-preview-retry');
      await userEvent.click(retryButton);

      expect(refresh).toHaveBeenCalledTimes(1);
    });

    it('should not show retry button when showRefresh is false', () => {
      const previewState = createMockPreviewState({
        error: 'API error',
      });

      render(<ThresholdPreview previewState={previewState} showRefresh={false} />);

      expect(screen.queryByTestId('threshold-preview-retry')).not.toBeInTheDocument();
    });
  });

  describe('No Data State', () => {
    it('should show save prompt when no data available', () => {
      const previewState = createMockPreviewState({
        eventsMatched: null,
        eventsTested: null,
      });

      render(<ThresholdPreview previewState={previewState} />);

      expect(screen.getByText('Save rule to see threshold preview')).toBeInTheDocument();
    });
  });

  describe('Data Display', () => {
    it('should display events matched and tested counts', () => {
      const previewState = createMockPreviewState({
        eventsMatched: 25,
        eventsTested: 100,
        matchRate: 25.0,
      });

      render(<ThresholdPreview previewState={previewState} />);

      expect(screen.getByTestId('threshold-preview-count')).toHaveTextContent('25 / 100');
    });

    it('should display match rate percentage', () => {
      const previewState = createMockPreviewState({
        eventsMatched: 33,
        eventsTested: 100,
        matchRate: 33.33,
      });

      render(<ThresholdPreview previewState={previewState} />);

      expect(screen.getByText('(33.3%)')).toBeInTheDocument();
    });

    it('should display custom label', () => {
      const previewState = createMockPreviewState({
        eventsMatched: 10,
        eventsTested: 50,
        matchRate: 20.0,
      });

      render(
        <ThresholdPreview
          previewState={previewState}
          label="Matching events:"
        />
      );

      expect(screen.getByText('Matching events:')).toBeInTheDocument();
    });

    it('should show refresh button when showRefresh is true', () => {
      const previewState = createMockPreviewState({
        eventsMatched: 10,
        eventsTested: 50,
        matchRate: 20.0,
      });

      render(<ThresholdPreview previewState={previewState} showRefresh={true} />);

      expect(screen.getByTestId('threshold-preview-refresh')).toBeInTheDocument();
    });

    it('should not show refresh button when showRefresh is false', () => {
      const previewState = createMockPreviewState({
        eventsMatched: 10,
        eventsTested: 50,
        matchRate: 20.0,
      });

      render(<ThresholdPreview previewState={previewState} showRefresh={false} />);

      expect(screen.queryByTestId('threshold-preview-refresh')).not.toBeInTheDocument();
    });

    it('should call refresh when refresh button is clicked', async () => {
      const refresh = vi.fn();
      const previewState = createMockPreviewState({
        eventsMatched: 10,
        eventsTested: 50,
        matchRate: 20.0,
        refresh,
      });

      render(<ThresholdPreview previewState={previewState} showRefresh={true} />);

      const refreshButton = screen.getByTestId('threshold-preview-refresh');
      await userEvent.click(refreshButton);

      expect(refresh).toHaveBeenCalledTimes(1);
    });
  });

  describe('Color Coding', () => {
    it('should show green color for 0% match rate', () => {
      const previewState = createMockPreviewState({
        eventsMatched: 0,
        eventsTested: 100,
        matchRate: 0,
      });

      render(<ThresholdPreview previewState={previewState} />);

      const count = screen.getByTestId('threshold-preview-count');
      expect(count).toHaveClass('text-green-400');
    });

    it('should show yellow color for low match rate (1-25%)', () => {
      const previewState = createMockPreviewState({
        eventsMatched: 20,
        eventsTested: 100,
        matchRate: 20.0,
      });

      render(<ThresholdPreview previewState={previewState} />);

      const count = screen.getByTestId('threshold-preview-count');
      expect(count).toHaveClass('text-yellow-400');
    });

    it('should show orange color for medium match rate (26-50%)', () => {
      const previewState = createMockPreviewState({
        eventsMatched: 40,
        eventsTested: 100,
        matchRate: 40.0,
      });

      render(<ThresholdPreview previewState={previewState} />);

      const count = screen.getByTestId('threshold-preview-count');
      expect(count).toHaveClass('text-orange-400');
    });

    it('should show red color for high match rate (>50%)', () => {
      const previewState = createMockPreviewState({
        eventsMatched: 75,
        eventsTested: 100,
        matchRate: 75.0,
      });

      render(<ThresholdPreview previewState={previewState} />);

      const count = screen.getByTestId('threshold-preview-count');
      expect(count).toHaveClass('text-red-400');
    });
  });

  describe('Custom Test ID', () => {
    it('should use custom testId', () => {
      const previewState = createMockPreviewState({
        eventsMatched: 10,
        eventsTested: 50,
        matchRate: 20.0,
      });

      render(<ThresholdPreview previewState={previewState} testId="custom-preview" />);

      expect(screen.getByTestId('custom-preview')).toBeInTheDocument();
      expect(screen.getByTestId('custom-preview-count')).toBeInTheDocument();
    });
  });

  describe('Custom Class Name', () => {
    it('should apply custom className', () => {
      const previewState = createMockPreviewState({
        eventsMatched: 10,
        eventsTested: 50,
        matchRate: 20.0,
      });

      render(<ThresholdPreview previewState={previewState} className="my-custom-class" />);

      const container = screen.getByTestId('threshold-preview');
      expect(container).toHaveClass('my-custom-class');
    });
  });

  describe('Accessibility', () => {
    it('should have proper aria-label on refresh button', () => {
      const previewState = createMockPreviewState({
        eventsMatched: 10,
        eventsTested: 50,
        matchRate: 20.0,
      });

      render(<ThresholdPreview previewState={previewState} showRefresh={true} />);

      const refreshButton = screen.getByTestId('threshold-preview-refresh');
      expect(refreshButton).toHaveAttribute('aria-label', 'Refresh preview');
    });

    it('should have proper aria-label on retry button', () => {
      const previewState = createMockPreviewState({
        error: 'API error',
      });

      render(<ThresholdPreview previewState={previewState} showRefresh={true} />);

      const retryButton = screen.getByTestId('threshold-preview-retry');
      expect(retryButton).toHaveAttribute('aria-label', 'Retry preview');
    });
  });
});
