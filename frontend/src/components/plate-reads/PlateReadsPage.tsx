/**
 * Plate Reads Page
 *
 * Main page component for the License Plate Recognition (LPR) feature.
 * Displays plate read statistics, trends, search interface, and results table.
 *
 * Features:
 * - Statistics cards showing ALPR metrics
 * - Trends chart showing activity over time
 * - Search and filter functionality (text search, camera, date range, confidence)
 * - Paginated table of plate reads with search highlighting
 * - Detail modal for individual plate reads
 *
 * @see frontend/src/services/plateReadsApi.ts - API client
 * @see frontend/src/types/plateRead.ts - Type definitions
 * @see backend/api/routes/plate_reads.py - Backend endpoints
 */

import { useQueryClient } from '@tanstack/react-query';
import { Car, RefreshCw } from 'lucide-react';
import { useMemo, useCallback, useState } from 'react';

import { PlateDetailModal } from './PlateDetailModal';
import PlateReadTable from './PlateReadTable';
import PlateReadTrendsCard from './PlateReadTrendsCard';
import PlateSearchBar from './PlateSearchBar';
import PlateStatisticsCards from './PlateStatisticsCards';
import {
  usePlateSearchQuery,
  plateSearchQueryKeys,
} from '../../hooks/usePlateSearchQuery';
import { plateStatisticsQueryKeys } from '../../hooks/usePlateStatisticsQuery';

import type { PlateSearchFilters as SearchBarFilters } from './PlateSearchBar';
import type { PlateRead } from '../../types/plateRead';

// ============================================================================
// Constants
// ============================================================================

/** Default page size for the plate reads table */
const DEFAULT_PAGE_SIZE = 25;

// ============================================================================
// Component
// ============================================================================

/**
 * PlateReadsPage component - License Plate Recognition dashboard.
 *
 * Displays:
 * - Statistics cards with key ALPR metrics
 * - Trends chart showing plate read activity over time
 * - Search bar with text search and advanced filters
 * - Paginated results table with search highlighting
 * - Detail modal for individual plate reads
 */
export function PlateReadsPage(): React.ReactElement {
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Search state
  const [searchText, setSearchText] = useState('');
  const [exactMatch, setExactMatch] = useState(false);
  const [filters, setFilters] = useState<SearchBarFilters>({});
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  // Modal state
  const [selectedPlateText, setSelectedPlateText] = useState<string | null>(null);

  // Calculate date range for trends (last 7 days)
  const dateRange = useMemo(() => {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(endDate.getDate() - 7);
    return {
      startDate: startDate.toISOString().split('T')[0],
      endDate: endDate.toISOString().split('T')[0],
    };
  }, []);

  // Fetch plate reads using the combined search/filter hook
  const {
    plateReads,
    total,
    isLoading: isSearchLoading,
    isRefetching,
  } = usePlateSearchQuery(
    {
      text: searchText || undefined,
      exact: exactMatch || undefined,
      camera_id: filters.camera_id,
      start_time: filters.start_time,
      end_time: filters.end_time,
      min_confidence: filters.min_confidence,
      page: currentPage,
      page_size: pageSize,
    },
    { enabled: true }
  );

  // Handle refresh button click - invalidate all relevant queries
  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    void Promise.all([
      queryClient.invalidateQueries({
        queryKey: plateStatisticsQueryKeys.all,
      }),
      queryClient.invalidateQueries({
        queryKey: plateSearchQueryKeys.all,
      }),
    ]).finally(() => {
      setIsRefreshing(false);
    });
  }, [queryClient]);

  // Reset page to 1 when search text changes
  const handleSearchTextChange = useCallback((text: string) => {
    setSearchText(text);
    setCurrentPage(1);
  }, []);

  // Reset page to 1 when exact match toggles
  const handleExactMatchChange = useCallback((exact: boolean) => {
    setExactMatch(exact);
    setCurrentPage(1);
  }, []);

  // Reset page to 1 when filters change
  const handleFiltersChange = useCallback((newFilters: SearchBarFilters) => {
    setFilters(newFilters);
    setCurrentPage(1);
  }, []);

  // Handle page size changes - reset to page 1
  const handlePageSizeChange = useCallback((newPageSize: number) => {
    setPageSize(newPageSize);
    setCurrentPage(1);
  }, []);

  // Handle row click to open detail modal
  const handleRowClick = useCallback((plateRead: PlateRead) => {
    setSelectedPlateText(plateRead.plate_text);
  }, []);

  // Handle modal close
  const handleModalClose = useCallback(() => {
    setSelectedPlateText(null);
  }, []);

  return (
    <div className="min-h-screen bg-[#121212]" data-testid="plate-reads-page">
      {/* Page Header */}
      <div className="flex items-start justify-between border-b border-gray-800 px-8 py-4">
        <div className="flex items-center gap-3">
          <Car className="h-8 w-8 text-[#76B900]" />
          <div>
            <h1 className="text-page-title">Plate Reads</h1>
            <p className="text-sm text-gray-400">
              License plate recognition data and analytics
            </p>
          </div>
        </div>

        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
          data-testid="plate-reads-refresh-button"
        >
          <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Main Content */}
      <div className="p-6">
        {/* Statistics Cards */}
        <section className="mb-6" data-testid="plate-reads-statistics-section">
          <PlateStatisticsCards />
        </section>

        {/* Grid for Trends */}
        <div className="mb-6 grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
          {/* Trends Chart - spans 2 columns */}
          <div className="md:col-span-2" data-testid="plate-reads-trends-section">
            <PlateReadTrendsCard dateRange={dateRange} />
          </div>
        </div>

        {/* Plate Search and Results */}
        <section data-testid="plate-reads-search-section">
          {/* Search Bar */}
          <div className="mb-4">
            <PlateSearchBar
              searchText={searchText}
              onSearchTextChange={handleSearchTextChange}
              exactMatch={exactMatch}
              onExactMatchChange={handleExactMatchChange}
              filters={filters}
              onFiltersChange={handleFiltersChange}
              isSearching={isSearchLoading || isRefetching}
            />
          </div>

          {/* Results Table */}
          <PlateReadTable
            plateReads={plateReads}
            total={total}
            page={currentPage}
            pageSize={pageSize}
            onPageChange={setCurrentPage}
            onPageSizeChange={handlePageSizeChange}
            onRowClick={handleRowClick}
            searchText={searchText}
            isLoading={isSearchLoading}
          />
        </section>
      </div>

      {/* Detail Modal */}
      <PlateDetailModal
        plateText={selectedPlateText}
        onClose={handleModalClose}
      />
    </div>
  );
}

export default PlateReadsPage;
