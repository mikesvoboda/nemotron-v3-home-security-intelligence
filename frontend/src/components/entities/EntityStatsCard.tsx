import { AlertCircle, Car, Camera, Loader2, RefreshCw, User, Users } from 'lucide-react';

import { useEntityStats, type UseEntityStatsOptions } from '../../hooks/useEntityHistory';

export interface EntityStatsCardProps {
  /** Filter entities seen since this timestamp */
  since?: Date;
  /** Filter entities seen until this timestamp */
  until?: Date;
  /** Optional class name */
  className?: string;
  /** Whether to show the card in compact mode */
  compact?: boolean;
}

/**
 * EntityStatsCard displays aggregated entity statistics including:
 * - Total unique entities
 * - Total appearances
 * - Breakdown by type (person, vehicle)
 * - Repeat visitors count
 *
 * Uses the /api/entities/stats endpoint via useEntityStats hook.
 */
export default function EntityStatsCard({
  since,
  until,
  className = '',
  compact = false,
}: EntityStatsCardProps) {
  const options: UseEntityStatsOptions = {
    since,
    until,
    enabled: true,
    refetchInterval: 60000, // Refresh every minute
  };

  const {
    totalEntities,
    totalAppearances,
    byType,
    repeatVisitors,
    isLoading,
    error,
    refetch,
  } = useEntityStats(options);

  // Loading state
  if (isLoading) {
    return (
      <div className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`rounded-lg border border-red-900/50 bg-red-900/10 p-4 ${className}`}>
        <div className="flex flex-col items-center gap-2 text-center">
          <AlertCircle className="h-6 w-6 text-red-500" />
          <p className="text-sm text-red-400">Failed to load entity statistics</p>
          <button
            onClick={() => void refetch()}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-white"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Extract type counts
  const personCount = byType.person ?? 0;
  const vehicleCount = byType.vehicle ?? 0;

  // Compact mode - horizontal layout
  if (compact) {
    return (
      <div
        className={`flex items-center gap-6 rounded-lg border border-gray-800 bg-[#1F1F1F] px-4 py-3 ${className}`}
      >
        <div className="flex items-center gap-2">
          <Users className="h-5 w-5 text-[#76B900]" />
          <span className="text-sm text-gray-400">
            <span className="font-semibold text-white">{totalEntities}</span> entities
          </span>
        </div>
        <div className="flex items-center gap-2">
          <User className="h-4 w-4 text-gray-400" />
          <span className="text-sm text-gray-400">
            <span className="font-medium text-white">{personCount}</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Car className="h-4 w-4 text-gray-400" />
          <span className="text-sm text-gray-400">
            <span className="font-medium text-white">{vehicleCount}</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Camera className="h-4 w-4 text-gray-400" />
          <span className="text-sm text-gray-400">
            <span className="font-medium text-white">{totalAppearances}</span> appearances
          </span>
        </div>
        {repeatVisitors > 0 && (
          <div className="flex items-center gap-1 rounded-full bg-[#76B900]/20 px-2 py-0.5 text-xs font-medium text-[#76B900]">
            {repeatVisitors} repeat
          </div>
        )}
      </div>
    );
  }

  // Full card mode - grid layout
  return (
    <div className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}>
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
          <Users className="h-5 w-5 text-[#76B900]" />
          Entity Statistics
        </h3>
        <button
          onClick={() => void refetch()}
          className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
          aria-label="Refresh statistics"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {/* Total entities */}
        <div className="rounded-lg border border-gray-700 bg-black/30 p-3">
          <div className="flex items-center gap-2 text-2xl font-bold text-white">
            <Users className="h-5 w-5 text-gray-400" />
            <span>{totalEntities}</span>
          </div>
          <p className="mt-1 text-xs text-gray-400">Total Entities</p>
        </div>

        {/* Persons */}
        <div className="rounded-lg border border-gray-700 bg-black/30 p-3">
          <div className="flex items-center gap-2 text-2xl font-bold text-white">
            <User className="h-5 w-5 text-blue-400" />
            <span>{personCount}</span>
          </div>
          <p className="mt-1 text-xs text-gray-400">Persons</p>
        </div>

        {/* Vehicles */}
        <div className="rounded-lg border border-gray-700 bg-black/30 p-3">
          <div className="flex items-center gap-2 text-2xl font-bold text-white">
            <Car className="h-5 w-5 text-amber-400" />
            <span>{vehicleCount}</span>
          </div>
          <p className="mt-1 text-xs text-gray-400">Vehicles</p>
        </div>

        {/* Repeat visitors */}
        <div className="rounded-lg border border-gray-700 bg-black/30 p-3">
          <div className="flex items-center gap-2 text-2xl font-bold text-[#76B900]">
            <RefreshCw className="h-5 w-5" />
            <span>{repeatVisitors}</span>
          </div>
          <p className="mt-1 text-xs text-gray-400">Repeat Visitors</p>
        </div>
      </div>

      {/* Total appearances footer */}
      <div className="mt-4 flex items-center justify-center border-t border-gray-800 pt-4">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Camera className="h-4 w-4" />
          <span>
            <span className="font-medium text-white">{totalAppearances.toLocaleString()}</span>{' '}
            total appearances
          </span>
        </div>
      </div>
    </div>
  );
}
