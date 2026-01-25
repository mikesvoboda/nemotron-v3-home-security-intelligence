/**
 * Tests for ObjectDistributionCard component
 *
 * Tests cover:
 * - Rendering with object distribution data
 * - Empty state when no data
 * - Loading state
 * - Error state
 * - Date range display
 * - Object type percentages display
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ObjectDistributionCard from './ObjectDistributionCard';
import * as useObjectDistributionQueryModule from '../../hooks/useObjectDistributionQuery';

// Mock the hook
vi.mock('../../hooks/useObjectDistributionQuery', () => ({
  useObjectDistributionQuery: vi.fn(),
}));

describe('ObjectDistributionCard', () => {
  const mockDateRange = {
    startDate: '2026-01-10',
    endDate: '2026-01-17',
  };

  const mockObjectTypes = [
    { object_type: 'person', count: 150, percentage: 50.0 },
    { object_type: 'car', count: 90, percentage: 30.0 },
    { object_type: 'dog', count: 36, percentage: 12.0 },
    { object_type: 'cat', count: 18, percentage: 6.0 },
    { object_type: 'bicycle', count: 6, percentage: 2.0 },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering with data', () => {
    beforeEach(() => {
      vi.mocked(useObjectDistributionQueryModule.useObjectDistributionQuery).mockReturnValue({
        data: {
          object_types: mockObjectTypes,
          total_detections: 300,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        },
        objectTypes: mockObjectTypes,
        totalDetections: 300,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('renders the card title', () => {
      render(<ObjectDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByText('Object Distribution')).toBeInTheDocument();
    });

    it('displays object types with percentages', () => {
      render(<ObjectDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('object-item-person')).toBeInTheDocument();
      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('50.0%')).toBeInTheDocument();

      expect(screen.getByTestId('object-item-car')).toBeInTheDocument();
      expect(screen.getByText('Car')).toBeInTheDocument();
      expect(screen.getByText('30.0%')).toBeInTheDocument();
    });

    it('displays date range label', () => {
      render(<ObjectDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByText(/Jan 10 - Jan 17/)).toBeInTheDocument();
    });

    it('renders the main card element', () => {
      render(<ObjectDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('object-distribution-card')).toBeInTheDocument();
    });

    it('shows only first 5 object types in legend', () => {
      render(<ObjectDistributionCard dateRange={mockDateRange} />);

      // First 5 should be visible
      expect(screen.getByTestId('object-item-person')).toBeInTheDocument();
      expect(screen.getByTestId('object-item-car')).toBeInTheDocument();
      expect(screen.getByTestId('object-item-dog')).toBeInTheDocument();
      expect(screen.getByTestId('object-item-cat')).toBeInTheDocument();
      expect(screen.getByTestId('object-item-bicycle')).toBeInTheDocument();
    });
  });

  describe('more than 5 object types', () => {
    beforeEach(() => {
      const manyObjectTypes = [
        { object_type: 'person', count: 100, percentage: 25.0 },
        { object_type: 'car', count: 80, percentage: 20.0 },
        { object_type: 'dog', count: 60, percentage: 15.0 },
        { object_type: 'cat', count: 50, percentage: 12.5 },
        { object_type: 'bicycle', count: 40, percentage: 10.0 },
        { object_type: 'motorcycle', count: 30, percentage: 7.5 },
        { object_type: 'truck', count: 20, percentage: 5.0 },
        { object_type: 'bird', count: 20, percentage: 5.0 },
      ];
      vi.mocked(useObjectDistributionQueryModule.useObjectDistributionQuery).mockReturnValue({
        data: {
          object_types: manyObjectTypes,
          total_detections: 400,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        },
        objectTypes: manyObjectTypes,
        totalDetections: 400,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('shows "+N more types" indicator when more than 5 types', () => {
      render(<ObjectDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByText('+3 more types')).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    beforeEach(() => {
      vi.mocked(useObjectDistributionQueryModule.useObjectDistributionQuery).mockReturnValue({
        data: undefined,
        objectTypes: [],
        totalDetections: 0,
        isLoading: true,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('shows loading indicator when isLoading is true', () => {
      render(<ObjectDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('object-distribution-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    beforeEach(() => {
      vi.mocked(useObjectDistributionQueryModule.useObjectDistributionQuery).mockReturnValue({
        data: undefined,
        objectTypes: [],
        totalDetections: 0,
        isLoading: false,
        isRefetching: false,
        error: new Error('Failed to fetch'),
        isError: true,
        refetch: vi.fn(),
      });
    });

    it('shows error message when error occurs', () => {
      render(<ObjectDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('object-distribution-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to load object distribution/)).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    beforeEach(() => {
      vi.mocked(useObjectDistributionQueryModule.useObjectDistributionQuery).mockReturnValue({
        data: {
          object_types: [],
          total_detections: 0,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        },
        objectTypes: [],
        totalDetections: 0,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('shows empty state when no object types', () => {
      render(<ObjectDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('object-distribution-empty')).toBeInTheDocument();
      expect(screen.getByText(/No object data available/)).toBeInTheDocument();
    });
  });

  describe('hook parameters', () => {
    beforeEach(() => {
      vi.mocked(useObjectDistributionQueryModule.useObjectDistributionQuery).mockReturnValue({
        data: {
          object_types: mockObjectTypes,
          total_detections: 300,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        },
        objectTypes: mockObjectTypes,
        totalDetections: 300,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('passes correct date range to hook', () => {
      render(<ObjectDistributionCard dateRange={mockDateRange} />);

      expect(useObjectDistributionQueryModule.useObjectDistributionQuery).toHaveBeenCalledWith({
        start_date: '2026-01-10',
        end_date: '2026-01-17',
      });
    });
  });
});
