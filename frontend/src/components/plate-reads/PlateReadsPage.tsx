/**
 * Plate Reads Page
 *
 * Main page component for the License Plate Recognition (LPR) feature.
 * Displays plate read statistics, trends, and a search interface.
 *
 * Phase 1: Statistics display
 * - Statistics cards showing ALPR metrics
 * - Trends chart showing activity over time
 *
 * Phase 2 (coming soon):
 * - Search and filter functionality
 * - Paginated table of plate reads
 * - Detail modal for individual reads
 *
 * @see frontend/src/services/plateReadsApi.ts - API client
 * @see frontend/src/types/plateRead.ts - Type definitions
 * @see backend/api/routes/plate_reads.py - Backend endpoints
 */

import { useQueryClient } from '@tanstack/react-query';
import { Car, RefreshCw, Search } from 'lucide-react';
import { useMemo, useCallback, useState } from 'react';

import PlateReadTrendsCard from './PlateReadTrendsCard';
import PlateStatisticsCards from './PlateStatisticsCards';
import { plateStatisticsQueryKeys } from '../../hooks/usePlateStatisticsQuery';

// ============================================================================
// Component
// ============================================================================

/**
 * PlateReadsPage component - License Plate Recognition dashboard.
 *
 * Displays:
 * - Statistics cards with key ALPR metrics
 * - Trends chart showing plate read activity over time
 * - Placeholder for search functionality (Phase 2)
 */
export function PlateReadsPage(): React.ReactElement {
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);

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

  // Handle refresh button click
  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    void queryClient
      .invalidateQueries({
        queryKey: plateStatisticsQueryKeys.all,
      })
      .finally(() => {
        setIsRefreshing(false);
      });
  }, [queryClient]);

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

        {/* Grid for Trends and Future Components */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
          {/* Trends Chart - spans 2 columns */}
          <div className="md:col-span-2" data-testid="plate-reads-trends-section">
            <PlateReadTrendsCard dateRange={dateRange} />
          </div>

          {/* Search Placeholder - spans 2 columns */}
          <div className="md:col-span-2" data-testid="plate-reads-search-section">
            <div className="rounded-lg border border-dashed border-gray-700 bg-gray-800/50 p-8 text-center">
              <Search className="mx-auto h-10 w-10 text-gray-500" />
              <h3 className="mt-4 text-lg font-medium text-gray-300">
                Plate Search Coming Soon
              </h3>
              <p className="mt-2 text-sm text-gray-500">
                Phase 2 will add search and filtering capabilities for plate reads
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PlateReadsPage;
