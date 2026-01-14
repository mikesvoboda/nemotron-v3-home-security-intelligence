import { AlertCircle, Camera, Car, Clock, Eye, Loader2, RefreshCw, User } from 'lucide-react';
import { useEffect, useState } from 'react';

import {
  fetchEntityHistory,
  type EntityAppearance,
  type EntityHistoryResponse,
} from '../../services/api';
import SafeErrorMessage from '../common/SafeErrorMessage';

export interface ReidHistoryPanelProps {
  /** Entity ID to display history for */
  entityId: string;
  /** Entity type (person or vehicle) */
  entityType: 'person' | 'vehicle';
  /** Optional CSS class name */
  className?: string;
  /** Callback when an appearance is clicked */
  onAppearanceClick?: (appearance: EntityAppearance) => void;
}

/**
 * ReidHistoryPanel - Display entity re-identification history
 *
 * Shows a chronological timeline of when an entity was seen across
 * different cameras, including:
 * - Thumbnails from each appearance
 * - Camera location and timestamp
 * - Confidence/similarity scores
 * - Side-by-side image comparison capability
 *
 * This component is designed to be used within EntityDetailModal or
 * as a standalone panel for tracking entity movements.
 */
export default function ReidHistoryPanel({
  entityId,
  entityType,
  className = '',
  onAppearanceClick,
}: ReidHistoryPanelProps) {
  const [history, setHistory] = useState<EntityHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAppearances, setSelectedAppearances] = useState<Set<string>>(new Set());

  // Load entity history
  const loadHistory = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await fetchEntityHistory(entityId);
      setHistory(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load entity history';
      setError(message);
      setHistory(null);
    } finally {
      setLoading(false);
    }
  };

  // Load history on mount or when entityId changes
  useEffect(() => {
    void loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadHistory uses entityId, triggering on entityId change is correct
  }, [entityId]);

  // Format timestamp to relative time
  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins} min ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays < 7) return `${diffDays}d ago`;

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

  // Format similarity score as percentage
  const formatSimilarity = (score: number | null | undefined): string => {
    if (score === null || score === undefined) return 'N/A';
    return `${Math.round(score * 100)}%`;
  };

  // Get similarity score badge color
  const getSimilarityColor = (score: number | null | undefined): string => {
    if (score === null || score === undefined) return 'bg-gray-700 text-gray-300';
    if (score >= 0.9) return 'bg-green-900/40 text-green-400';
    if (score >= 0.8) return 'bg-[#76B900]/20 text-[#76B900]';
    if (score >= 0.7) return 'bg-yellow-900/40 text-yellow-400';
    return 'bg-orange-900/40 text-orange-400';
  };

  // Handle appearance selection for comparison
  const toggleAppearanceSelection = (detectionId: string) => {
    setSelectedAppearances((prev) => {
      const next = new Set(prev);
      if (next.has(detectionId)) {
        next.delete(detectionId);
      } else {
        // Limit to 2 selections for side-by-side comparison
        if (next.size >= 2) {
          const first = Array.from(next)[0];
          next.delete(first);
        }
        next.add(detectionId);
      }
      return next;
    });
  };

  // Handle appearance click
  const handleAppearanceClick = (appearance: EntityAppearance) => {
    if (onAppearanceClick) {
      onAppearanceClick(appearance);
    }
    toggleAppearanceSelection(appearance.detection_id);
  };

  // Get entity icon
  const EntityIcon = entityType === 'person' ? User : Car;

  // Loading state
  if (loading) {
    return (
      <div
        className={`flex min-h-[300px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F] p-6 ${className}`}
      >
        <div className="flex flex-col items-center gap-3 text-gray-400">
          <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
          <p>Loading re-identification history...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className={`flex min-h-[300px] items-center justify-center rounded-lg border border-red-900/50 bg-red-900/10 p-6 ${className}`}
      >
        <div className="flex flex-col items-center gap-3 text-center">
          <AlertCircle className="h-8 w-8 text-red-500" />
          <SafeErrorMessage message={error} />
          <button
            onClick={() => void loadHistory()}
            className="mt-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  // No history
  if (!history || history.appearances.length === 0) {
    return (
      <div
        className={`flex min-h-[300px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F] p-6 ${className}`}
      >
        <div className="flex flex-col items-center gap-3 text-gray-400">
          <EntityIcon className="h-12 w-12" />
          <p>No re-identification history found</p>
        </div>
      </div>
    );
  }

  // Sort appearances by timestamp (most recent first)
  const sortedAppearances = [...history.appearances].sort((a, b) => {
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  });

  // Get selected appearances for comparison
  const selectedForComparison = sortedAppearances.filter((app) =>
    selectedAppearances.has(app.detection_id)
  );

  return (
    <div className={`rounded-lg border border-gray-800 bg-[#1F1F1F] ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 p-4">
        <div className="flex items-center gap-2">
          <Clock className="h-5 w-5 text-[#76B900]" />
          <h3 className="text-lg font-semibold text-white">Re-Identification History</h3>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-400">
            {history.count} {history.count === 1 ? 'appearance' : 'appearances'}
          </span>
          <button
            onClick={() => void loadHistory()}
            className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
            aria-label="Refresh history"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Comparison view (when 2 items selected) */}
      {selectedForComparison.length === 2 && (
        <div className="border-b border-gray-800 bg-black/30 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="text-sm font-semibold text-white">Side-by-Side Comparison</h4>
            <button
              onClick={() => setSelectedAppearances(new Set())}
              className="text-xs text-gray-400 hover:text-white"
            >
              Clear
            </button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {selectedForComparison.map((appearance) => (
              <div key={appearance.detection_id} className="flex flex-col gap-2">
                {/* Thumbnail */}
                <div className="relative aspect-square overflow-hidden rounded-lg bg-gray-800">
                  {appearance.thumbnail_url ? (
                    <img
                      src={appearance.thumbnail_url}
                      alt={`${entityType} at ${appearance.camera_name || appearance.camera_id}`}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-gray-600">
                      <EntityIcon className="h-16 w-16" />
                    </div>
                  )}
                </div>
                {/* Details */}
                <div className="space-y-1 text-sm">
                  <div className="flex items-center gap-1 text-gray-300">
                    <Camera className="h-3.5 w-3.5" />
                    <span className="truncate">{appearance.camera_name || appearance.camera_id}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-400">{formatTimestamp(appearance.timestamp)}</span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-xs font-medium ${getSimilarityColor(appearance.similarity_score)}`}
                    >
                      {formatSimilarity(appearance.similarity_score)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="max-h-[600px] overflow-y-auto p-4">
        <div className="space-y-0">
          {sortedAppearances.map((appearance, index) => {
            const isSelected = selectedAppearances.has(appearance.detection_id);

            return (
              <div key={appearance.detection_id} className="relative">
                {/* Timeline connector line */}
                {index < sortedAppearances.length - 1 && (
                  <div className="absolute left-6 top-16 h-full w-px border-l-2 border-dashed border-gray-700" />
                )}

                <button
                  onClick={() => handleAppearanceClick(appearance)}
                  className={`w-full text-left transition-all ${
                    isSelected ? 'rounded-lg bg-[#76B900]/10 ring-2 ring-[#76B900]/50' : 'hover:bg-gray-800/50'
                  } p-2`}
                  aria-pressed={isSelected}
                >
                  <div className="flex gap-3 pb-4">
                    {/* Thumbnail */}
                    <div className="relative flex h-12 w-12 flex-shrink-0 items-center justify-center overflow-hidden rounded-full bg-gray-800">
                      {appearance.thumbnail_url ? (
                        <img
                          src={appearance.thumbnail_url}
                          alt={`${entityType} at ${appearance.camera_name || appearance.camera_id}`}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center text-gray-600">
                          <EntityIcon className="h-6 w-6" />
                        </div>
                      )}
                      {/* Selection indicator */}
                      {isSelected && (
                        <div className="absolute inset-0 flex items-center justify-center bg-[#76B900]/30">
                          <Eye className="h-5 w-5 text-white" />
                        </div>
                      )}
                    </div>

                    {/* Content */}
                    <div className="min-w-0 flex-1">
                      {/* Camera name and similarity */}
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 truncate">
                          <Camera className="h-4 w-4 flex-shrink-0 text-gray-400" />
                          <span className="truncate font-medium text-white">
                            {appearance.camera_name || appearance.camera_id}
                          </span>
                        </div>
                        {appearance.similarity_score !== null && appearance.similarity_score !== undefined && (
                          <span
                            className={`flex-shrink-0 rounded px-1.5 py-0.5 text-xs font-medium ${getSimilarityColor(appearance.similarity_score)}`}
                          >
                            {formatSimilarity(appearance.similarity_score)}
                          </span>
                        )}
                      </div>

                      {/* Timestamp */}
                      <div className="mt-1 flex items-center gap-1 text-xs text-gray-400">
                        <Clock className="h-3 w-3" />
                        <span>{formatTimestamp(appearance.timestamp)}</span>
                      </div>

                      {/* Attributes (if any) */}
                      {appearance.attributes && Object.keys(appearance.attributes).length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {Object.entries(appearance.attributes).map(([key, value]) => (
                            <span
                              key={key}
                              className="rounded bg-gray-800 px-1.5 py-0.5 text-xs text-gray-400"
                            >
                              {key}: {String(value)}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer hint */}
      {selectedAppearances.size < 2 && (
        <div className="border-t border-gray-800 bg-black/20 p-3 text-center text-xs text-gray-500">
          Click on appearances to select up to 2 for side-by-side comparison
        </div>
      )}
    </div>
  );
}
