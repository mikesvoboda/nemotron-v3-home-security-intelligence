/**
 * JobsPage - Background jobs monitoring page with split view layout
 *
 * Displays a list of background jobs on the left with a detail panel on the right.
 * Supports filtering by status and type, and searching with debounced input.
 * All filter state is persisted in the URL using useSearchParams.
 *
 * Route: /jobs
 */

import { useQuery } from '@tanstack/react-query';
import { Briefcase, RefreshCw, BarChart3 } from 'lucide-react';
import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

import JobDetailPanel from './JobDetailPanel';
import JobsEmptyState from './JobsEmptyState';
import JobsList from './JobsList';
import JobsSearchBar from './JobsSearchBar';
import { useJobsSearchQuery, type JobsSearchFilters } from '../../hooks/useJobsSearchQuery';
import { fetchJob } from '../../services/api';
import SafeErrorMessage from '../common/SafeErrorMessage';

import type { JobStatusEnum } from '../../services/api';

export default function JobsPage() {
  // URL search params for filter persistence
  const [searchParams, setSearchParams] = useSearchParams();

  // Get filter values from URL
  const urlQuery = searchParams.get('q') || '';
  const urlStatus = searchParams.get('status') as JobStatusEnum | null;
  const urlType = searchParams.get('type') || undefined;

  // Local state for immediate UI updates (before debounce)
  const [searchQuery, setSearchQuery] = useState(urlQuery);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  // Build filters object for the hook
  const filters: JobsSearchFilters = {
    q: urlQuery || undefined,
    status: urlStatus || undefined,
    type: urlType,
  };

  // Use the jobs search query hook with debouncing
  const {
    jobs,
    totalCount,
    // aggregations available for showing filter counts in the future
    aggregations: _aggregations,
    isLoading: isLoadingJobs,
    isFetching: isFetchingJobs,
    isError: isJobsError,
    error: jobsError,
    refetch: refetchJobs,
  } = useJobsSearchQuery({
    filters,
    limit: 50,
    debounceMs: 300, // 300ms debounce for search
  });

  // Fetch selected job details
  const { data: selectedJob, isLoading: isLoadingSelectedJob } = useQuery({
    queryKey: ['jobs', 'detail', selectedJobId],
    queryFn: () => {
      if (!selectedJobId) throw new Error('No job selected');
      return fetchJob(selectedJobId);
    },
    enabled: !!selectedJobId,
    staleTime: 10000, // 10 seconds - more frequent for job details
  });

  // Sync local search query with URL on mount
  useEffect(() => {
    setSearchQuery(urlQuery);
  }, [urlQuery]);

  // Handle search change - update local state and URL
  const handleSearchChange = useCallback(
    (query: string) => {
      setSearchQuery(query);
      // Update URL with debounce effect in the hook
      setSearchParams(
        (prev) => {
          const newParams = new URLSearchParams(prev);
          if (query) {
            newParams.set('q', query);
          } else {
            newParams.delete('q');
          }
          return newParams;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  // Handle status change
  const handleStatusChange = useCallback(
    (status?: JobStatusEnum) => {
      setSearchParams(
        (prev) => {
          const newParams = new URLSearchParams(prev);
          if (status) {
            newParams.set('status', status);
          } else {
            newParams.delete('status');
          }
          return newParams;
        },
        { replace: true }
      );
      setSelectedJobId(null); // Clear selection when filter changes
    },
    [setSearchParams]
  );

  // Handle type change
  const handleTypeChange = useCallback(
    (type?: string) => {
      setSearchParams(
        (prev) => {
          const newParams = new URLSearchParams(prev);
          if (type) {
            newParams.set('type', type);
          } else {
            newParams.delete('type');
          }
          return newParams;
        },
        { replace: true }
      );
      setSelectedJobId(null); // Clear selection when filter changes
    },
    [setSearchParams]
  );

  // Handle clear all filters
  const handleClearFilters = useCallback(() => {
    setSearchQuery('');
    setSearchParams({}, { replace: true });
    setSelectedJobId(null);
  }, [setSearchParams]);

  // Handle job selection
  const handleSelectJob = useCallback((jobId: string) => {
    setSelectedJobId(jobId);
  }, []);

  // Handle refresh
  const handleRefresh = () => {
    void refetchJobs();
  };

  // Check if any filters are active for empty state handling
  const hasActiveFilters = Boolean(urlQuery || urlStatus || urlType);

  return (
    <div data-testid="jobs-page" className="flex h-full flex-col">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Briefcase className="h-8 w-8 text-[#76B900]" />
            <h1 className="text-3xl font-bold text-white">Jobs</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              disabled={isFetchingJobs}
              aria-label="Refresh jobs"
              className="flex items-center gap-2 rounded-md bg-[#76B900]/10 px-4 py-2 text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${isFetchingJobs ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              aria-label="View stats"
              className="flex items-center gap-2 rounded-md border border-gray-700 bg-gray-800 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-700"
            >
              <BarChart3 className="h-4 w-4" />
              Stats
            </button>
          </div>
        </div>
        <p className="mt-2 text-gray-400">Monitor background jobs and their progress</p>
      </div>

      {/* Search and Filter Bar - hidden when no jobs exist */}
      {(jobs.length > 0 || hasActiveFilters || isLoadingJobs) && (
        <div className="mb-6">
          <JobsSearchBar
            query={searchQuery}
            status={urlStatus || undefined}
            type={urlType}
            onSearchChange={handleSearchChange}
            onStatusChange={handleStatusChange}
            onTypeChange={handleTypeChange}
            onClear={handleClearFilters}
            isLoading={isFetchingJobs}
            totalCount={totalCount}
          />
        </div>
      )}

      {/* Loading State */}
      {isLoadingJobs && (
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
          <div className="text-center">
            <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-700 border-t-[#76B900]" />
            <p className="text-gray-400">Loading jobs...</p>
          </div>
        </div>
      )}

      {/* Error State */}
      {isJobsError && !isLoadingJobs && (
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-red-900/50 bg-red-950/20">
          <div className="text-center">
            <p className="mb-2 text-lg font-semibold text-red-400">Error Loading Jobs</p>
            <SafeErrorMessage
              message={jobsError?.message || 'An error occurred'}
              size="sm"
              color="gray"
            />
          </div>
        </div>
      )}

      {/* Empty State - only show when no filters active and no jobs */}
      {!isLoadingJobs && !isJobsError && jobs.length === 0 && !hasActiveFilters && (
        <JobsEmptyState />
      )}

      {/* Split View Layout */}
      {!isLoadingJobs && !isJobsError && (jobs.length > 0 || hasActiveFilters) && (
        <div className="flex flex-1 gap-4 overflow-hidden">
          {/* Left Panel - Jobs List */}
          <div className="flex w-full flex-col overflow-hidden rounded-lg border border-gray-800 bg-[#1F1F1F] md:w-1/3 lg:w-2/5">
            {/* Jobs List or Empty Search State */}
            {jobs.length > 0 ? (
              <JobsList
                jobs={jobs}
                selectedJobId={selectedJobId}
                onSelectJob={handleSelectJob}
              />
            ) : (
              <div className="flex flex-1 items-center justify-center p-4">
                <p className="text-sm text-gray-500">No jobs match your search</p>
              </div>
            )}
          </div>

          {/* Right Panel - Job Details */}
          <div className="hidden flex-1 md:block">
            <JobDetailPanel job={selectedJob ?? null} isLoading={isLoadingSelectedJob} />
          </div>
        </div>
      )}
    </div>
  );
}
