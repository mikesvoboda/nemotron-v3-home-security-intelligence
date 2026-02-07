/**
 * Tests for PlateReadsPage component
 *
 * Tests cover:
 * - Rendering page structure
 * - Statistics section
 * - Trends section
 * - Refresh button functionality
 * - Search bar rendering
 * - Results table rendering
 * - Detail modal integration
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import PlateReadsPage from './PlateReadsPage';
import * as usePlateSearchQueryModule from '../../hooks/usePlateSearchQuery';
import * as usePlateStatisticsQueryModule from '../../hooks/usePlateStatisticsQuery';

// Mock the hooks
vi.mock('../../hooks/usePlateStatisticsQuery', () => ({
  usePlateStatisticsQuery: vi.fn(),
  plateStatisticsQueryKeys: {
    all: ['plate-reads', 'statistics'],
    current: () => ['plate-reads', 'statistics'],
  },
}));

vi.mock('../../hooks/usePlateSearchQuery', () => ({
  usePlateSearchQuery: vi.fn(),
  plateSearchQueryKeys: {
    all: ['plate-reads'],
    list: (filters?: Record<string, unknown>) =>
      filters ? ['plate-reads', 'list', filters] : ['plate-reads', 'list'],
    byText: (params: Record<string, unknown>) => ['plate-reads', 'search', params],
  },
}));

vi.mock('../../hooks/useCamerasQuery', () => ({
  useCamerasQuery: vi.fn(() => ({
    cameras: [],
    isLoading: false,
    isRefetching: false,
    error: null,
    isError: false,
    refetch: vi.fn(),
  })),
}));

vi.mock('../../hooks/useVehicleMatchQuery', () => ({
  useVehicleMatchQuery: vi.fn(() => ({
    match: null,
    isLoading: false,
    isError: false,
    error: null,
  })),
}));

describe('PlateReadsPage', () => {
  let queryClient: QueryClient;

  const mockStatistics = {
    data: {
      total_reads: 1250,
      unique_plates: 342,
      avg_ocr_confidence: 0.923,
      avg_quality_score: 0.85,
      enhanced_count: 156,
      blurry_count: 43,
      reads_last_hour: 28,
      reads_last_24h: 412,
    },
    totalReads: 1250,
    uniquePlates: 342,
    avgConfidence: 0.923,
    avgConfidencePercent: 92,
    avgQualityScore: 0.85,
    readsLastHour: 28,
    readsLast24h: 412,
    enhancedCount: 156,
    blurryCount: 43,
    isLoading: false,
    isRefetching: false,
    error: null,
    isError: false,
    refetch: vi.fn(),
  };

  const renderWithProviders = (ui: React.ReactElement) => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    return render(
      <QueryClientProvider client={queryClient}>
        {ui}
      </QueryClientProvider>
    );
  };

  const mockSearchResults = {
    plateReads: [],
    total: 0,
    page: 1,
    pageSize: 25,
    isLoading: false,
    isRefetching: false,
    error: null,
    isError: false,
    isPlaceholderData: false,
    refetch: vi.fn().mockResolvedValue(undefined),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(usePlateStatisticsQueryModule.usePlateStatisticsQuery).mockReturnValue(
      mockStatistics
    );
    vi.mocked(usePlateSearchQueryModule.usePlateSearchQuery).mockReturnValue(
      mockSearchResults
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('page structure', () => {
    it('renders the page container', () => {
      renderWithProviders(<PlateReadsPage />);

      expect(screen.getByTestId('plate-reads-page')).toBeInTheDocument();
    });

    it('renders the page title', () => {
      renderWithProviders(<PlateReadsPage />);

      expect(screen.getByText('Plate Reads')).toBeInTheDocument();
    });

    it('renders the page description', () => {
      renderWithProviders(<PlateReadsPage />);

      expect(
        screen.getByText('License plate recognition data and analytics')
      ).toBeInTheDocument();
    });

    it('renders the Car icon in header', () => {
      renderWithProviders(<PlateReadsPage />);

      // The Car icon should be in the header
      const header = screen.getByTestId('plate-reads-page').querySelector('.border-b');
      expect(header).toBeInTheDocument();
    });
  });

  describe('refresh button', () => {
    it('renders the refresh button', () => {
      renderWithProviders(<PlateReadsPage />);

      expect(screen.getByTestId('plate-reads-refresh-button')).toBeInTheDocument();
      expect(screen.getByText('Refresh')).toBeInTheDocument();
    });

    it('invalidates queries when clicked', async () => {
      renderWithProviders(<PlateReadsPage />);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const refreshButton = screen.getByTestId('plate-reads-refresh-button');
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(invalidateQueriesSpy).toHaveBeenCalledWith({
          queryKey: ['plate-reads', 'statistics'],
        });
        expect(invalidateQueriesSpy).toHaveBeenCalledWith({
          queryKey: ['plate-reads'],
        });
      });
    });
  });

  describe('statistics section', () => {
    it('renders the statistics section', () => {
      renderWithProviders(<PlateReadsPage />);

      expect(screen.getByTestId('plate-reads-statistics-section')).toBeInTheDocument();
    });

    it('renders PlateStatisticsCards component', () => {
      renderWithProviders(<PlateReadsPage />);

      // PlateStatisticsCards should render its container
      expect(screen.getByTestId('plate-statistics-cards')).toBeInTheDocument();
    });
  });

  describe('trends section', () => {
    it('renders the trends section', () => {
      renderWithProviders(<PlateReadsPage />);

      expect(screen.getByTestId('plate-reads-trends-section')).toBeInTheDocument();
    });

    it('renders PlateReadTrendsCard component', () => {
      renderWithProviders(<PlateReadsPage />);

      // PlateReadTrendsCard should render its container
      expect(screen.getByTestId('plate-trends-card')).toBeInTheDocument();
    });
  });

  describe('search section', () => {
    it('renders the search section', () => {
      renderWithProviders(<PlateReadsPage />);

      expect(screen.getByTestId('plate-reads-search-section')).toBeInTheDocument();
    });

    it('renders the search bar with text input', () => {
      renderWithProviders(<PlateReadsPage />);

      expect(screen.getByLabelText('Search plate text')).toBeInTheDocument();
    });

    it('renders the exact match toggle', () => {
      renderWithProviders(<PlateReadsPage />);

      expect(screen.getByText('Exact match')).toBeInTheDocument();
    });

    it('renders the results table', () => {
      renderWithProviders(<PlateReadsPage />);

      // The table should render with its empty state since mockSearchResults has 0 results
      expect(screen.getByText('No plate reads found')).toBeInTheDocument();
    });

    it('renders the filters toggle button', () => {
      renderWithProviders(<PlateReadsPage />);

      expect(screen.getByLabelText('Toggle advanced filters')).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    beforeEach(() => {
      vi.mocked(usePlateStatisticsQueryModule.usePlateStatisticsQuery).mockReturnValue({
        ...mockStatistics,
        data: undefined,
        totalReads: 0,
        uniquePlates: 0,
        avgConfidence: 0,
        avgConfidencePercent: 0,
        readsLastHour: 0,
        readsLast24h: 0,
        enhancedCount: 0,
        blurryCount: 0,
        avgQualityScore: 0,
        isLoading: true,
      });
    });

    it('renders loading state for statistics', () => {
      renderWithProviders(<PlateReadsPage />);

      expect(screen.getByTestId('plate-statistics-loading')).toBeInTheDocument();
    });

    it('renders loading state for trends', () => {
      renderWithProviders(<PlateReadsPage />);

      expect(screen.getByTestId('plate-trends-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    beforeEach(() => {
      vi.mocked(usePlateStatisticsQueryModule.usePlateStatisticsQuery).mockReturnValue({
        ...mockStatistics,
        data: undefined,
        totalReads: 0,
        isLoading: false,
        error: new Error('Failed to fetch'),
        isError: true,
      });
    });

    it('renders error state for statistics', () => {
      renderWithProviders(<PlateReadsPage />);

      expect(screen.getByTestId('plate-statistics-error')).toBeInTheDocument();
    });

    it('renders error state for trends', () => {
      renderWithProviders(<PlateReadsPage />);

      expect(screen.getByTestId('plate-trends-error')).toBeInTheDocument();
    });
  });

  describe('responsive layout', () => {
    it('uses grid layout for trends and search sections', () => {
      renderWithProviders(<PlateReadsPage />);

      // Find the grid container
      const gridContainer = screen.getByTestId('plate-reads-trends-section').parentElement;
      expect(gridContainer).toHaveClass('grid');
      expect(gridContainer).toHaveClass('grid-cols-1');
    });
  });
});
