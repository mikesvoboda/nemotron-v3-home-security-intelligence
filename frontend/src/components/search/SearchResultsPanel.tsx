import { ChevronLeft, ChevronRight, FileSearch, XCircle } from 'lucide-react';

import SearchResultCard from './SearchResultCard';

import type { SearchResult } from '../../services/api';

export interface SearchResultsPanelProps {
  /** Search results to display */
  results: SearchResult[];
  /** Total number of matching results (for pagination) */
  totalCount: number;
  /** Current offset for pagination */
  offset: number;
  /** Results per page */
  limit: number;
  /** Whether search is in progress */
  isLoading: boolean;
  /** Error message if search failed */
  error?: string | null;
  /** Called when pagination changes */
  onPageChange: (newOffset: number) => void;
  /** Called when a result is clicked */
  onResultClick?: (eventId: number) => void;
  /** Called when user wants to clear search */
  onClearSearch?: () => void;
  /** The search query that produced these results */
  searchQuery?: string;
  /** Optional class name */
  className?: string;
}

/**
 * SearchResultsPanel displays search results with pagination.
 *
 * Features:
 * - Grid layout for result cards
 * - Loading and error states
 * - Pagination controls
 * - Empty state with helpful message
 * - Result count display
 */
export default function SearchResultsPanel({
  results,
  totalCount,
  offset,
  limit,
  isLoading,
  error,
  onPageChange,
  onResultClick,
  onClearSearch,
  searchQuery,
  className = '',
}: SearchResultsPanelProps) {
  // Calculate pagination info
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(totalCount / limit);
  const showingFrom = Math.min(offset + 1, totalCount);
  const showingTo = Math.min(offset + results.length, totalCount);

  // Handle pagination
  const handlePreviousPage = () => {
    if (offset > 0) {
      onPageChange(Math.max(0, offset - limit));
    }
  };

  const handleNextPage = () => {
    if (offset + limit < totalCount) {
      onPageChange(offset + limit);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className={`flex min-h-[300px] items-center justify-center ${className}`}>
        <div className="text-center">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-gray-700 border-t-[#76B900]" />
          <p className="text-gray-400">Searching events...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`flex min-h-[300px] items-center justify-center ${className}`}>
        <div className="text-center">
          <XCircle className="mx-auto mb-4 h-12 w-12 text-red-500" />
          <p className="mb-2 text-lg font-semibold text-red-500">Search Failed</p>
          <p className="mb-4 text-sm text-gray-400">{error}</p>
          {onClearSearch && (
            <button
              onClick={onClearSearch}
              className="rounded-md bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            >
              Clear Search
            </button>
          )}
        </div>
      </div>
    );
  }

  // Empty state
  if (results.length === 0) {
    return (
      <div className={`flex min-h-[300px] items-center justify-center ${className}`}>
        <div className="text-center">
          <FileSearch className="mx-auto mb-4 h-12 w-12 text-gray-600" />
          <p className="mb-2 text-lg font-semibold text-gray-300">No Results Found</p>
          <p className="mb-4 max-w-md text-sm text-gray-500">
            {searchQuery ? (
              <>
                No events match your search for &quot;<span className="text-[#76B900]">{searchQuery}</span>&quot;. Try
                different keywords or adjust your filters.
              </>
            ) : (
              'Enter a search query to find events.'
            )}
          </p>
          {onClearSearch && searchQuery && (
            <button
              onClick={onClearSearch}
              className="rounded-md bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            >
              Clear Search
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Results Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="text-sm text-gray-400">
          Showing <span className="font-medium text-white">{showingFrom}-{showingTo}</span> of{' '}
          <span className="font-medium text-white">{totalCount}</span> result{totalCount !== 1 ? 's' : ''}
          {searchQuery && (
            <span>
              {' '}for &quot;<span className="text-[#76B900]">{searchQuery}</span>&quot;
            </span>
          )}
        </div>
        {onClearSearch && (
          <button
            onClick={onClearSearch}
            className="text-sm text-gray-400 transition-colors hover:text-white"
          >
            Clear search
          </button>
        )}
      </div>

      {/* Results Grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {results.map((result) => (
          <SearchResultCard
            key={result.id}
            result={result}
            onClick={onResultClick}
          />
        ))}
      </div>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-between rounded-lg border border-gray-800 bg-[#1F1F1F] px-4 py-3">
          <button
            onClick={handlePreviousPage}
            disabled={offset === 0}
            className="flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#76B900]/10 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
            aria-label="Previous page"
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </button>

          <div className="text-sm text-gray-400">
            Page <span className="font-medium text-white">{currentPage}</span> of{' '}
            <span className="font-medium text-white">{totalPages}</span>
          </div>

          <button
            onClick={handleNextPage}
            disabled={offset + limit >= totalCount}
            className="flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#76B900]/10 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
            aria-label="Next page"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
