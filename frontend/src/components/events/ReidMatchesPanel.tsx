/**
 * ReidMatchesPanel - Displays re-identification matches for a detection
 *
 * Shows entities that match a detection's embedding across cameras,
 * including similarity scores and timestamps. Used in EventDetailModal
 * to surface cross-camera entity tracking.
 */

import { AlertCircle, Camera, Car, Clock, Loader2, RefreshCw, User, Users } from 'lucide-react';
import { useEffect, useState } from 'react';

import {
  fetchEntityMatches,
  type EntityMatchItem,
  type EntityMatchResponse,
} from '../../services/api';

export interface ReidMatchesPanelProps {
  /** Detection ID to find matches for */
  detectionId: number;
  /** Type of entity to search ('person' or 'vehicle') */
  entityType?: 'person' | 'vehicle';
  /** Optional CSS class name */
  className?: string;
  /** Callback when a match is clicked (to navigate to entity detail) */
  onMatchClick?: (match: EntityMatchItem) => void;
}

/**
 * Format time gap in human-readable form
 */
function formatTimeGap(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s ago`;
  }
  const mins = Math.floor(seconds / 60);
  if (mins < 60) {
    return `${mins}m ago`;
  }
  const hours = Math.floor(mins / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/**
 * Format similarity score as percentage with color coding
 */
function SimilarityBadge({ score }: { score: number }) {
  const percent = Math.round(score * 100);

  // Color coding based on similarity
  let colorClass: string;
  if (score >= 0.95) {
    colorClass = 'bg-green-900/40 text-green-400 border-green-700';
  } else if (score >= 0.9) {
    colorClass = 'bg-[#76B900]/20 text-[#76B900] border-[#76B900]/50';
  } else if (score >= 0.85) {
    colorClass = 'bg-yellow-900/40 text-yellow-400 border-yellow-700';
  } else {
    colorClass = 'bg-orange-900/40 text-orange-400 border-orange-700';
  }

  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold ${colorClass}`}
      title={`${percent}% similarity`}
    >
      {percent}%
    </span>
  );
}

/**
 * ReidMatchesPanel - Main component
 */
export default function ReidMatchesPanel({
  detectionId,
  entityType = 'person',
  className = '',
  onMatchClick,
}: ReidMatchesPanelProps) {
  const [data, setData] = useState<EntityMatchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load matches for the detection
  const loadMatches = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetchEntityMatches(String(detectionId), {
        entity_type: entityType,
      });
      setData(response);
    } catch (err) {
      // 404 is expected when no embedding exists for this detection
      if (err instanceof Error && err.message.includes('404')) {
        setData(null);
        setError(null); // Not an error, just no data
      } else {
        const message = err instanceof Error ? err.message : 'Failed to load matches';
        setError(message);
        setData(null);
      }
    } finally {
      setLoading(false);
    }
  };

  // Load on mount or when detectionId/entityType changes
  useEffect(() => {
    void loadMatches();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detectionId, entityType]);

  // Format timestamp
  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      });
    } catch {
      return isoString;
    }
  };

  // Get entity icon
  const EntityIcon = entityType === 'person' ? User : Car;

  // Loading state
  if (loading) {
    return (
      <div
        className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}
        data-testid="reid-matches-loading"
      >
        <div className="flex items-center gap-3 text-gray-400">
          <Loader2 className="h-5 w-5 animate-spin text-[#76B900]" />
          <span className="text-sm">Looking for re-ID matches...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className={`rounded-lg border border-red-900/50 bg-red-900/10 p-4 ${className}`}
        data-testid="reid-matches-error"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-red-400">
            <AlertCircle className="h-5 w-5" />
            <span className="text-sm">{error}</span>
          </div>
          <button
            onClick={() => void loadMatches()}
            className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
            aria-label="Retry"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>
    );
  }

  // No matches found (not an error, just no data)
  if (!data || data.matches.length === 0) {
    return (
      <div
        className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}
        data-testid="reid-matches-empty"
      >
        <div className="flex items-center gap-2 text-gray-500">
          <Users className="h-5 w-5" />
          <span className="text-sm">No re-ID matches found for this {entityType}</span>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`rounded-lg border border-gray-800 bg-[#1F1F1F] ${className}`}
      data-testid="reid-matches-panel"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
        <div className="flex items-center gap-2">
          <Users className="h-5 w-5 text-[#76B900]" />
          <h3 className="text-sm font-semibold text-white">Re-ID Matches</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">
            {data.total_matches} {data.total_matches === 1 ? 'match' : 'matches'}
          </span>
          <button
            onClick={() => void loadMatches()}
            className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
            aria-label="Refresh matches"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Match list */}
      <div className="max-h-[300px] overflow-y-auto">
        <ul className="divide-y divide-gray-800">
          {data.matches.map((match) => (
            <li key={match.entity_id}>
              <button
                onClick={() => onMatchClick?.(match)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-gray-800/50"
                disabled={!onMatchClick}
              >
                {/* Thumbnail */}
                <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center overflow-hidden rounded-full bg-gray-800">
                  {match.thumbnail_url ? (
                    <img
                      src={match.thumbnail_url}
                      alt={`${match.entity_type} at ${match.camera_name || match.camera_id}`}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <EntityIcon className="h-6 w-6 text-gray-600" />
                  )}
                </div>

                {/* Details */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Camera className="h-4 w-4 flex-shrink-0 text-gray-400" />
                    <span className="truncate text-sm font-medium text-white">
                      {match.camera_name || match.camera_id}
                    </span>
                    <SimilarityBadge score={match.similarity_score} />
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-gray-400">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatTimestamp(match.timestamp)}
                    </span>
                    <span className="text-gray-500">({formatTimeGap(match.time_gap_seconds)})</span>
                  </div>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </div>

      {/* Footer with threshold info */}
      <div className="border-t border-gray-800 bg-black/20 px-4 py-2">
        <p className="text-xs text-gray-500">
          Showing matches with {'\u2265'}
          {Math.round(data.threshold * 100)}% similarity
        </p>
      </div>
    </div>
  );
}
