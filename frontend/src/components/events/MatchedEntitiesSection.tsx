import { Car, User, Users } from 'lucide-react';
import { useEffect, useState } from 'react';

import { fetchEventEntityMatches } from '../../services/api';

import type { EntityMatch, EventEntityMatchesResponse } from '../../services/api';

/**
 * Get confidence level from similarity score (0-1).
 */
function getConfidenceLevel(similarity: number): 'low' | 'medium' | 'high' {
  if (similarity >= 0.9) return 'high';
  if (similarity >= 0.75) return 'medium';
  return 'low';
}

/**
 * Get color classes for confidence badge based on similarity score.
 */
function getConfidenceBadgeClasses(similarity: number): string {
  const level = getConfidenceLevel(similarity);
  switch (level) {
    case 'high':
      return 'bg-green-500/20 text-green-400 border-green-500/30';
    case 'medium':
      return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    case 'low':
      return 'bg-red-500/20 text-red-400 border-red-500/30';
  }
}

/**
 * Format time gap into human-readable string.
 */
function formatTimeGap(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s ago`;
  }
  if (seconds < 3600) {
    const mins = Math.round(seconds / 60);
    return `${mins}m ago`;
  }
  if (seconds < 86400) {
    const hours = Math.round(seconds / 3600);
    return `${hours}h ago`;
  }
  const days = Math.round(seconds / 86400);
  return `${days}d ago`;
}

export interface MatchedEntitiesSectionProps {
  /** Event ID to fetch matches for */
  eventId: number;
  /** Callback when an entity is clicked to open EntityDetailModal */
  onEntityClick?: (entityId: string) => void;
}

/**
 * MatchedEntitiesSection displays entity re-ID matches for an event.
 * Shows persons and vehicles that were matched via cross-camera re-identification.
 */
export default function MatchedEntitiesSection({
  eventId,
  onEntityClick,
}: MatchedEntitiesSectionProps) {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [matchData, setMatchData] = useState<EventEntityMatchesResponse | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadMatches = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetchEventEntityMatches(eventId);
        if (!cancelled) {
          setMatchData(response);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to fetch entity matches:', err);
          setError('Failed to load entity matches');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadMatches();

    return () => {
      cancelled = true;
    };
  }, [eventId]);

  // Loading state
  if (loading) {
    return (
      <div className="mb-6" data-testid="matched-entities-loading">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
          Matched Entities
        </h3>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-500 border-t-transparent" />
          <span>Loading matches...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="mb-6" data-testid="matched-entities-error">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
          Matched Entities
        </h3>
        <p className="text-sm text-red-400">{error}</p>
      </div>
    );
  }

  // Empty state - no matches found
  if (!matchData || matchData.total_matches === 0) {
    return (
      <div className="mb-6" data-testid="matched-entities-empty">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
          Matched Entities
        </h3>
        <div className="flex items-center gap-2 rounded-lg border border-gray-800 bg-black/20 p-4 text-sm text-gray-500">
          <Users className="h-5 w-5" />
          <span>No entity matches found for this event</span>
        </div>
      </div>
    );
  }

  const allMatches: EntityMatch[] = [
    ...matchData.person_matches,
    ...matchData.vehicle_matches,
  ].sort((a, b) => b.similarity - a.similarity);

  return (
    <div className="mb-6" data-testid="matched-entities-section">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">
        Matched Entities ({matchData.total_matches})
      </h3>
      <div className="grid gap-2">
        {allMatches.map((match) => {
          const isPerson = match.entity_type === 'person';
          const Icon = isPerson ? User : Car;

          return (
            <button
              key={match.entity_id}
              onClick={() => onEntityClick?.(match.entity_id)}
              className="flex items-center gap-3 rounded-lg border border-gray-800 bg-black/30 p-3 text-left transition-colors hover:border-[#76B900]/50 hover:bg-black/40"
              aria-label={`View ${match.entity_type} entity details`}
              data-testid={`entity-match-${match.entity_id}`}
            >
              {/* Entity thumbnail or icon */}
              <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center overflow-hidden rounded-full bg-gray-800">
                {match.thumbnail_url ? (
                  <img
                    src={match.thumbnail_url}
                    alt={`${match.entity_type} entity`}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <Icon className="h-6 w-6 text-gray-500" />
                )}
              </div>

              {/* Entity info */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium capitalize text-white">
                    {match.entity_type}
                  </span>
                  {/* Similarity confidence badge */}
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${getConfidenceBadgeClasses(match.similarity)}`}
                    title={`Similarity: ${Math.round(match.similarity * 100)}%`}
                  >
                    {Math.round(match.similarity * 100)}%
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-2 text-xs text-gray-400">
                  <span>Last seen: {match.last_seen_camera}</span>
                  <span aria-hidden="true">-</span>
                  <span>{formatTimeGap(match.time_gap_seconds)}</span>
                </div>
              </div>

              {/* Chevron indicator */}
              <div className="flex-shrink-0 text-gray-500">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
