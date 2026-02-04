/**
 * EntityRecognitionSummary component for displaying entity recognition statistics.
 *
 * Shows counts of known vs unknown persons and vehicles detected in the
 * summary time window. Displays summary counts with breakdown details.
 *
 * Features:
 * - Person stats: known vs unknown faces
 * - Vehicle stats: known vs unknown license plates
 * - Expandable details showing individual counts
 * - Loading and error states
 *
 * Implements NEM-5397: Entity Recognition Summary - Frontend Component
 */

import { useQuery } from '@tanstack/react-query';
import { Card, Text } from '@tremor/react';
import { User, Car, ChevronDown, ChevronUp, Check, AlertCircle, RefreshCw } from 'lucide-react';
import { useState } from 'react';

import { fetchEntityRecognitionStats } from '../../services/api';

import type { EntityRecognitionStats } from '../../services/api';

// =============================================================================
// Types
// =============================================================================

interface EntityRecognitionSummaryProps {
  /** Optional class name for styling */
  className?: string;
}

// =============================================================================
// Loading Skeleton
// =============================================================================

function EntityRecognitionSkeleton() {
  return (
    <Card
      className="animate-pulse border-gray-800 bg-[#1A1A1A]"
      data-testid="entity-recognition-loading"
    >
      <div className="space-y-3">
        {/* Header skeleton */}
        <div className="h-4 w-32 rounded bg-gray-700" />

        {/* Stats skeleton */}
        <div className="flex gap-6">
          <div className="flex items-center gap-2">
            <div className="h-5 w-5 rounded bg-gray-700" />
            <div className="h-6 w-16 rounded bg-gray-700" />
          </div>
          <div className="flex items-center gap-2">
            <div className="h-5 w-5 rounded bg-gray-700" />
            <div className="h-6 w-16 rounded bg-gray-700" />
          </div>
        </div>

        {/* Breakdown skeleton */}
        <div className="space-y-2">
          <div className="h-3 w-24 rounded bg-gray-700" />
          <div className="h-3 w-28 rounded bg-gray-700" />
        </div>
      </div>
    </Card>
  );
}

// =============================================================================
// Error State
// =============================================================================

interface ErrorStateProps {
  onRetry: () => void;
}

function EntityRecognitionError({ onRetry }: ErrorStateProps) {
  return (
    <Card
      className="border-red-500/30 bg-[#1A1A1A]"
      data-testid="entity-recognition-error"
    >
      <div className="flex flex-col items-center gap-3 py-2">
        <AlertCircle className="h-6 w-6 text-red-400" aria-hidden="true" />
        <Text className="text-sm text-gray-400">Failed to load entity stats</Text>
        <button
          type="button"
          onClick={onRetry}
          className="flex items-center gap-1 rounded-md bg-gray-800 px-3 py-1.5 text-xs text-gray-300 transition-colors hover:bg-gray-700"
        >
          <RefreshCw className="h-3 w-3" aria-hidden="true" />
          Retry
        </button>
      </div>
    </Card>
  );
}

// =============================================================================
// Main Component
// =============================================================================

/**
 * EntityRecognitionSummary displays statistics about recognized entities.
 *
 * Shows:
 * - Total persons detected with known vs unknown breakdown
 * - Total vehicles detected with known vs unknown breakdown
 * - Expandable section with detailed counts
 *
 * @example
 * ```tsx
 * <EntityRecognitionSummary className="mb-4" />
 * ```
 */
export default function EntityRecognitionSummary({ className = '' }: EntityRecognitionSummaryProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Fetch entity recognition stats
  const {
    data: stats,
    isLoading,
    error,
    refetch,
  } = useQuery<EntityRecognitionStats>({
    queryKey: ['entity-recognition-stats'],
    queryFn: fetchEntityRecognitionStats,
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
  });

  // Loading state
  if (isLoading) {
    return <EntityRecognitionSkeleton />;
  }

  // Error state
  if (error) {
    return <EntityRecognitionError onRetry={() => void refetch()} />;
  }

  // No data
  if (!stats) {
    return null;
  }

  const toggleExpanded = () => setIsExpanded(!isExpanded);

  return (
    <Card
      className={`border-gray-800 bg-[#1A1A1A] ${className}`}
      data-testid="entity-recognition-summary"
      aria-label="Entity recognition summary"
    >
      {/* Header with time window */}
      <div className="mb-3 flex items-center justify-between">
        <Text className="text-xs font-medium uppercase tracking-wide text-gray-400">
          Entity Recognition
        </Text>
        <span className="text-xs text-gray-500" data-testid="time-window">
          Last 60 minutes
        </span>
      </div>

      {/* Summary Stats */}
      <div className="flex flex-wrap gap-6">
        {/* Persons */}
        <div className="flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-500/10"
            data-testid="persons-icon"
          >
            <User className="h-5 w-5 text-blue-400" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-baseline gap-2">
              <span
                className="text-2xl font-semibold text-white"
                data-testid="persons-total"
              >
                {stats.persons.total}
              </span>
              <span className="text-sm text-gray-400">persons</span>
            </div>
            <span
              className="text-xs text-gray-500"
              data-testid="persons-breakdown"
            >
              {stats.persons.breakdown}
            </span>
          </div>
        </div>

        {/* Vehicles */}
        <div className="flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-500/10"
            data-testid="vehicles-icon"
          >
            <Car className="h-5 w-5 text-amber-400" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-baseline gap-2">
              <span
                className="text-2xl font-semibold text-white"
                data-testid="vehicles-total"
              >
                {stats.vehicles.total}
              </span>
              <span className="text-sm text-gray-400">vehicles</span>
            </div>
            <span
              className="text-xs text-gray-500"
              data-testid="vehicles-breakdown"
            >
              {stats.vehicles.breakdown}
            </span>
          </div>
        </div>
      </div>

      {/* Expand/Collapse Button */}
      <button
        type="button"
        onClick={toggleExpanded}
        className="mt-3 flex w-full items-center justify-center gap-1 rounded-md py-1.5 text-xs text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-300"
        aria-expanded={isExpanded}
        aria-label={isExpanded ? 'Hide details' : 'Show details'}
        data-testid="expand-details-button"
      >
        {isExpanded ? (
          <>
            <span>Hide details</span>
            <ChevronUp className="h-4 w-4" aria-hidden="true" />
          </>
        ) : (
          <>
            <span>Show details</span>
            <ChevronDown className="h-4 w-4" aria-hidden="true" />
          </>
        )}
      </button>

      {/* Expanded Details */}
      {isExpanded && (
        <div
          className="mt-3 space-y-3 border-t border-gray-800 pt-3"
          data-testid="expanded-details"
        >
          {/* Persons Details */}
          <div className="space-y-2">
            <Text className="text-xs font-medium text-gray-400">Persons</Text>
            <div className="grid grid-cols-2 gap-2">
              {/* Known */}
              <div className="flex items-center gap-2 rounded-md bg-green-500/10 px-3 py-2">
                <Check
                  className="h-4 w-4 text-green-400"
                  aria-hidden="true"
                  data-testid="known-indicator"
                />
                <div>
                  <span
                    className="text-lg font-semibold text-white"
                    data-testid="persons-known-count"
                  >
                    {stats.persons.known}
                  </span>
                  <Text className="text-xs text-gray-400">known</Text>
                </div>
              </div>

              {/* Unknown */}
              <div className="flex items-center gap-2 rounded-md bg-gray-500/10 px-3 py-2">
                <AlertCircle
                  className="h-4 w-4 text-gray-400"
                  aria-hidden="true"
                  data-testid="unknown-indicator"
                />
                <div>
                  <span
                    className="text-lg font-semibold text-white"
                    data-testid="persons-unknown-count"
                  >
                    {stats.persons.unknown}
                  </span>
                  <Text className="text-xs text-gray-400">unknown</Text>
                </div>
              </div>
            </div>
          </div>

          {/* Vehicles Details */}
          <div className="space-y-2">
            <Text className="text-xs font-medium text-gray-400">Vehicles</Text>
            <div className="grid grid-cols-2 gap-2">
              {/* Known */}
              <div className="flex items-center gap-2 rounded-md bg-green-500/10 px-3 py-2">
                <Check className="h-4 w-4 text-green-400" aria-hidden="true" />
                <div>
                  <span
                    className="text-lg font-semibold text-white"
                    data-testid="vehicles-known-count"
                  >
                    {stats.vehicles.known}
                  </span>
                  <Text className="text-xs text-gray-400">known</Text>
                </div>
              </div>

              {/* Unknown */}
              <div className="flex items-center gap-2 rounded-md bg-gray-500/10 px-3 py-2">
                <AlertCircle className="h-4 w-4 text-gray-400" aria-hidden="true" />
                <div>
                  <span
                    className="text-lg font-semibold text-white"
                    data-testid="vehicles-unknown-count"
                  >
                    {stats.vehicles.unknown}
                  </span>
                  <Text className="text-xs text-gray-400">unknown</Text>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
