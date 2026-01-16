import { Camera, AlertTriangle, CheckCircle, RefreshCw, Loader2 } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';

import { fetchSceneChanges, acknowledgeSceneChange } from '../../services/api';

import type { SceneChangeResponse } from '../../services/api';

interface SceneChangePanelProps {
  /** Camera ID to fetch scene changes for */
  cameraId: string;
  /** Camera name for display */
  cameraName?: string;
}

/**
 * SceneChangePanel displays detected scene changes for camera tampering monitoring.
 *
 * Shows:
 * - List of recent scene changes with timestamps
 * - Change type and similarity scores
 * - Visual indicators for acknowledged/unacknowledged changes
 * - Ability to acknowledge scene changes
 */
export default function SceneChangePanel({ cameraId, cameraName }: SceneChangePanelProps) {
  const [sceneChanges, setSceneChanges] = useState<SceneChangeResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [acknowledgingId, setAcknowledgingId] = useState<number | null>(null);

  // Load scene changes
  const loadSceneChanges = useCallback(async () => {
    try {
      const response = await fetchSceneChanges(cameraId, { limit: 20 });
      setSceneChanges(response.scene_changes ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load scene changes');
      console.error('Failed to load scene changes:', err);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [cameraId]);

  // Load on mount and camera change
  useEffect(() => {
    setIsLoading(true);
    void loadSceneChanges();
  }, [loadSceneChanges]);

  // Handle refresh
  const handleRefresh = useCallback(async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    await loadSceneChanges();
  }, [isRefreshing, loadSceneChanges]);

  // Handle acknowledge
  const handleAcknowledge = useCallback(
    async (sceneChangeId: number) => {
      setAcknowledgingId(sceneChangeId);
      try {
        await acknowledgeSceneChange(cameraId, sceneChangeId);
        // Update local state
        setSceneChanges((prev) =>
          prev.map((sc) =>
            sc.id === sceneChangeId
              ? { ...sc, acknowledged: true, acknowledged_at: new Date().toISOString() }
              : sc
          )
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to acknowledge scene change');
        console.error('Failed to acknowledge scene change:', err);
      } finally {
        setAcknowledgingId(null);
      }
    },
    [cameraId]
  );

  // Get change type display info
  const getChangeTypeInfo = (
    changeType: string
  ): { label: string; color: string; icon: React.ReactNode } => {
    switch (changeType) {
      case 'view_blocked':
        return {
          label: 'View Blocked',
          color: 'text-red-400 bg-red-500/10',
          icon: <AlertTriangle className="h-4 w-4" />,
        };
      case 'angle_changed':
        return {
          label: 'Angle Changed',
          color: 'text-orange-400 bg-orange-500/10',
          icon: <AlertTriangle className="h-4 w-4" />,
        };
      case 'view_tampered':
        return {
          label: 'View Tampered',
          color: 'text-red-400 bg-red-500/10',
          icon: <AlertTriangle className="h-4 w-4" />,
        };
      default:
        return {
          label: 'Unknown',
          color: 'text-gray-400 bg-gray-500/10',
          icon: <AlertTriangle className="h-4 w-4" />,
        };
    }
  };

  // Format similarity score
  const formatSimilarity = (score: number): string => {
    return `${(score * 100).toFixed(1)}%`;
  };

  // Format timestamp
  const formatTimestamp = (timestamp: string): string => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  return (
    <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Camera className="h-5 w-5 text-[#76B900]" />
          <h3 className="text-lg font-semibold text-white">Scene Change Detection</h3>
        </div>
        <button
          onClick={() => void handleRefresh()}
          disabled={isRefreshing}
          className="flex items-center gap-2 rounded border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-300 transition-colors hover:bg-gray-700 disabled:opacity-50"
          data-testid="refresh-scene-changes"
        >
          <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Camera Info */}
      {cameraName && (
        <div className="mb-4 text-sm text-gray-400">
          Camera: <span className="text-white">{cameraName}</span>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="mb-4 flex items-center gap-2 rounded bg-red-500/10 px-3 py-2 text-sm text-red-400">
          <AlertTriangle className="h-4 w-4" />
          {error}
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="flex h-32 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-[#76B900]" />
          <span className="ml-2 text-sm text-gray-400">Loading scene changes...</span>
        </div>
      )}

      {/* Content */}
      {!isLoading && (
        <>
          {/* Summary */}
          <div className="mb-4 flex items-center gap-4 text-sm">
            <span className="text-gray-400">
              Total: <span className="text-white">{sceneChanges.length}</span>
            </span>
            <span className="text-gray-400">
              Unacknowledged:{' '}
              <span className="text-yellow-400">
                {sceneChanges.filter((sc) => !sc.acknowledged).length}
              </span>
            </span>
          </div>

          {/* Scene Changes List */}
          {sceneChanges.length === 0 ? (
            <div className="flex h-32 items-center justify-center rounded border border-dashed border-gray-700">
              <div className="text-center">
                <CheckCircle className="mx-auto mb-2 h-8 w-8 text-green-500" />
                <p className="text-sm text-gray-400">No scene changes detected</p>
              </div>
            </div>
          ) : (
            <div className="space-y-2" data-testid="scene-changes-list">
              {sceneChanges.map((sceneChange) => {
                const typeInfo = getChangeTypeInfo(sceneChange.change_type);
                return (
                  <div
                    key={sceneChange.id}
                    className="rounded border border-gray-800 bg-gray-900 p-3 transition-colors hover:border-gray-700"
                    data-testid={`scene-change-${sceneChange.id}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        {/* Change Type Badge */}
                        <div className="mb-2 flex items-center gap-2">
                          <span
                            className={`flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${typeInfo.color}`}
                          >
                            {typeInfo.icon}
                            {typeInfo.label}
                          </span>
                          {sceneChange.acknowledged && (
                            <span className="flex items-center gap-1 rounded bg-green-500/10 px-2 py-0.5 text-xs text-green-400">
                              <CheckCircle className="h-3 w-3" />
                              Acknowledged
                            </span>
                          )}
                        </div>

                        {/* Details */}
                        <div className="space-y-1 text-sm">
                          <div className="flex items-center gap-2">
                            <span className="text-gray-500">Detected:</span>
                            <span className="text-gray-300">
                              {formatTimestamp(sceneChange.detected_at)}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-gray-500">Similarity:</span>
                            <span className="text-gray-300">
                              {formatSimilarity(sceneChange.similarity_score)}
                            </span>
                            <span className="text-xs text-gray-500">(lower = more different)</span>
                          </div>
                          {sceneChange.acknowledged_at && (
                            <div className="flex items-center gap-2">
                              <span className="text-gray-500">Acknowledged:</span>
                              <span className="text-gray-300">
                                {formatTimestamp(sceneChange.acknowledged_at)}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Action Button */}
                      {!sceneChange.acknowledged && (
                        <button
                          onClick={() => void handleAcknowledge(sceneChange.id)}
                          disabled={acknowledgingId === sceneChange.id}
                          className="ml-4 flex items-center gap-2 rounded bg-[#76B900] px-3 py-1.5 text-xs font-medium text-black transition-colors hover:bg-[#8BD000] disabled:opacity-50"
                          data-testid={`acknowledge-${sceneChange.id}`}
                        >
                          {acknowledgingId === sceneChange.id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <CheckCircle className="h-3 w-3" />
                          )}
                          Acknowledge
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Info Footer */}
      <div className="mt-4 border-t border-gray-800 pt-4 text-xs text-gray-500">
        Scene changes are detected when the camera view significantly differs from the baseline. Low
        similarity scores indicate potential tampering or view changes.
      </div>
    </div>
  );
}
