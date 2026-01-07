import { BarChart3, AlertCircle, Loader2, Camera, RefreshCw } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';

import ActivityHeatmap from './ActivityHeatmap';
import AnomalyConfigPanel from './AnomalyConfigPanel';
import ClassFrequencyChart from './ClassFrequencyChart';
import PipelineLatencyPanel from './PipelineLatencyPanel';
import SceneChangePanel from './SceneChangePanel';
import {
  fetchCameras,
  fetchCameraActivityBaseline,
  fetchCameraClassBaseline,
  fetchAnomalyConfig,
  type Camera as CameraType,
  type ActivityBaselineResponse,
  type ClassBaselineResponse,
  type AnomalyConfig,
} from '../../services/api';

/**
 * AnalyticsPage - Baseline Analytics and Anomaly Detection Dashboard
 *
 * Displays:
 * - Camera selector
 * - Activity heatmap (24x7 pattern)
 * - Class frequency distribution
 * - Anomaly detection configuration
 */
export default function AnalyticsPage() {
  // State
  const [cameras, setCameras] = useState<CameraType[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [activityBaseline, setActivityBaseline] = useState<ActivityBaselineResponse | null>(null);
  const [classBaseline, setClassBaseline] = useState<ClassBaselineResponse | null>(null);
  const [anomalyConfig, setAnomalyConfig] = useState<AnomalyConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Load cameras on mount
  useEffect(() => {
    const loadCameras = async () => {
      try {
        const camerasData = await fetchCameras();
        setCameras(camerasData);
        if (camerasData.length > 0) {
          setSelectedCameraId(camerasData[0].id);
        } else {
          // No cameras available, stop loading
          setIsLoading(false);
        }
      } catch (err) {
        setError('Failed to load cameras');
        setIsLoading(false);
        console.error('Failed to load cameras:', err);
      }
    };

    void loadCameras();
  }, []);

  // Load baseline data when camera changes
  const loadBaselineData = useCallback(async (cameraId: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const [activity, classes, config] = await Promise.all([
        fetchCameraActivityBaseline(cameraId),
        fetchCameraClassBaseline(cameraId),
        fetchAnomalyConfig(),
      ]);

      setActivityBaseline(activity);
      setClassBaseline(classes);
      setAnomalyConfig(config);
    } catch (err) {
      setError('Failed to load baseline data');
      console.error('Failed to load baseline data:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load data when selected camera changes
  useEffect(() => {
    if (selectedCameraId) {
      void loadBaselineData(selectedCameraId);
    }
  }, [selectedCameraId, loadBaselineData]);

  // Handle refresh
  const handleRefresh = useCallback(async () => {
    if (!selectedCameraId || isRefreshing) return;

    setIsRefreshing(true);
    try {
      await loadBaselineData(selectedCameraId);
    } finally {
      setIsRefreshing(false);
    }
  }, [selectedCameraId, isRefreshing, loadBaselineData]);

  // Handle camera change
  const handleCameraChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedCameraId(e.target.value);
  };

  // Handle config update
  const handleConfigUpdated = (updatedConfig: AnomalyConfig) => {
    setAnomalyConfig(updatedConfig);
  };

  // Get selected camera
  const selectedCamera = cameras.find((c) => c.id === selectedCameraId);

  return (
    <div className="flex flex-col">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <BarChart3 className="h-8 w-8 text-[#76B900]" />
          <h1 className="text-3xl font-bold text-white">Analytics</h1>
        </div>
        <p className="mt-2 text-gray-400">
          View activity patterns and configure anomaly detection for your cameras
        </p>
      </div>

      {/* Camera Selector and Refresh */}
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <Camera className="h-5 w-5 text-gray-400" />
          <select
            value={selectedCameraId ?? ''}
            onChange={handleCameraChange}
            disabled={cameras.length === 0}
            className="rounded border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-[#76B900] focus:outline-none"
            data-testid="camera-selector"
          >
            {cameras.length === 0 ? (
              <option value="">No cameras available</option>
            ) : (
              cameras.map((camera) => (
                <option key={camera.id} value={camera.id}>
                  {camera.name || camera.id}
                </option>
              ))
            )}
          </select>
        </div>

        <button
          onClick={() => void handleRefresh()}
          disabled={isRefreshing || !selectedCameraId}
          className="flex items-center gap-2 rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-300 transition-colors hover:bg-gray-700 disabled:opacity-50"
          data-testid="refresh-button"
        >
          <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>

        {selectedCamera && activityBaseline && (
          <div className="flex items-center gap-4 text-sm text-gray-400">
            <span>
              Total samples: <span className="text-white">{activityBaseline.total_samples}</span>
            </span>
            {activityBaseline.learning_complete ? (
              <span className="rounded bg-green-500/20 px-2 py-0.5 text-green-400">
                Learning Complete
              </span>
            ) : (
              <span className="rounded bg-yellow-500/20 px-2 py-0.5 text-yellow-400">
                Still Learning
              </span>
            )}
          </div>
        )}
      </div>

      {/* Error State */}
      {error && (
        <div className="mb-6 flex items-center gap-2 rounded bg-red-500/10 px-4 py-3 text-red-400">
          <AlertCircle className="h-5 w-5" />
          {error}
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
          <span className="ml-3 text-gray-400">Loading baseline data...</span>
        </div>
      )}

      {/* Content */}
      {!isLoading && !error && selectedCameraId && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Activity Heatmap - Full Width */}
          <div className="lg:col-span-2">
            {activityBaseline && (
              <ActivityHeatmap
                entries={activityBaseline.entries}
                learningComplete={activityBaseline.learning_complete}
                minSamplesRequired={activityBaseline.min_samples_required}
              />
            )}
          </div>

          {/* Class Frequency Chart */}
          <div>
            {classBaseline && (
              <ClassFrequencyChart
                entries={classBaseline.entries}
                uniqueClasses={classBaseline.unique_classes}
                mostCommonClass={classBaseline.most_common_class}
              />
            )}
          </div>

          {/* Anomaly Config Panel */}
          <div>
            {anomalyConfig && (
              <AnomalyConfigPanel
                config={anomalyConfig}
                onConfigUpdated={handleConfigUpdated}
              />
            )}
          </div>

          {/* Pipeline Latency Panel - Full Width */}
          <div className="lg:col-span-2">
            <PipelineLatencyPanel refreshInterval={60000} />
          </div>

          {/* Scene Change Detection Panel - Full Width */}
          <div className="lg:col-span-2">
            <SceneChangePanel cameraId={selectedCameraId} cameraName={selectedCamera?.name} />
          </div>
        </div>
      )}

      {/* No Camera Selected */}
      {!isLoading && !error && !selectedCameraId && cameras.length === 0 && (
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
          <div className="text-center">
            <Camera className="mx-auto mb-4 h-12 w-12 text-gray-600" />
            <h2 className="mb-2 text-xl font-semibold text-white">No Cameras Found</h2>
            <p className="text-gray-400">
              Add cameras to start collecting baseline analytics data.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
