/**
 * Tests for CameraAnalyticsDetail component
 *
 * Tests cover:
 * - Rendering detection statistics cards
 * - Displaying class distribution
 * - Loading state
 * - Error state
 * - Empty state (no detections)
 * - Camera name display
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import CameraAnalyticsDetail from './CameraAnalyticsDetail';

describe('CameraAnalyticsDetail', () => {
  const defaultProps = {
    totalDetections: 1250,
    detectionsByClass: {
      person: 500,
      car: 350,
      truck: 200,
      dog: 100,
      cat: 100,
    },
    averageConfidence: 0.87,
    isLoading: false,
    error: null,
    cameraName: undefined,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering with data', () => {
    it('renders the component with test id', () => {
      render(<CameraAnalyticsDetail {...defaultProps} />);

      expect(screen.getByTestId('camera-analytics-detail')).toBeInTheDocument();
    });

    it('displays total detections count', () => {
      render(<CameraAnalyticsDetail {...defaultProps} />);

      expect(screen.getByText('1,250')).toBeInTheDocument();
      expect(screen.getByText('Total Detections')).toBeInTheDocument();
    });

    it('displays average confidence percentage', () => {
      render(<CameraAnalyticsDetail {...defaultProps} />);

      expect(screen.getByText('87%')).toBeInTheDocument();
      expect(screen.getByText('Average Confidence')).toBeInTheDocument();
    });

    it('displays detection class distribution', () => {
      render(<CameraAnalyticsDetail {...defaultProps} />);

      // Check class names are displayed
      expect(screen.getByText('person')).toBeInTheDocument();
      expect(screen.getByText('car')).toBeInTheDocument();
      expect(screen.getByText('truck')).toBeInTheDocument();
      expect(screen.getByText('dog')).toBeInTheDocument();
      expect(screen.getByText('cat')).toBeInTheDocument();

      // Check counts are displayed
      expect(screen.getByText('500')).toBeInTheDocument();
      expect(screen.getByText('350')).toBeInTheDocument();
      expect(screen.getByText('200')).toBeInTheDocument();
    });

    it('displays "All Cameras" title when no camera name provided', () => {
      render(<CameraAnalyticsDetail {...defaultProps} />);

      expect(screen.getByText('Detection Analytics')).toBeInTheDocument();
    });

    it('displays camera name in title when provided', () => {
      render(<CameraAnalyticsDetail {...defaultProps} cameraName="Front Door" />);

      expect(screen.getByText(/Front Door/)).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('shows loading indicator when isLoading is true', () => {
      render(<CameraAnalyticsDetail {...defaultProps} isLoading />);

      expect(screen.getByTestId('camera-analytics-loading')).toBeInTheDocument();
    });

    it('does not show stats when loading', () => {
      render(<CameraAnalyticsDetail {...defaultProps} isLoading />);

      expect(screen.queryByText('1,250')).not.toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error message when error is provided', () => {
      const error = new Error('Failed to load statistics');
      render(<CameraAnalyticsDetail {...defaultProps} error={error} />);

      expect(screen.getByTestId('camera-analytics-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to load/)).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows empty state when total detections is 0', () => {
      render(
        <CameraAnalyticsDetail
          {...defaultProps}
          totalDetections={0}
          detectionsByClass={{}}
        />
      );

      expect(screen.getByTestId('camera-analytics-empty')).toBeInTheDocument();
      // Check for the primary empty state message
      expect(screen.getByText('No detections found')).toBeInTheDocument();
    });
  });

  describe('class distribution sorting', () => {
    it('sorts classes by count in descending order', () => {
      render(<CameraAnalyticsDetail {...defaultProps} />);

      // Get all class items
      const classItems = screen.getAllByTestId(/^class-item-/);

      // First item should be person (500)
      expect(classItems[0]).toHaveAttribute('data-testid', 'class-item-person');
      // Second should be car (350)
      expect(classItems[1]).toHaveAttribute('data-testid', 'class-item-car');
    });
  });

  describe('null confidence', () => {
    it('displays N/A when confidence is null', () => {
      render(<CameraAnalyticsDetail {...defaultProps} averageConfidence={null} />);

      expect(screen.getByText('N/A')).toBeInTheDocument();
    });
  });
});
