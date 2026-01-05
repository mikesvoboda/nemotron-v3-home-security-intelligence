import { Title, Text, Select, SelectItem } from '@tremor/react';
import { Camera, TrendingUp, AlertCircle, RefreshCw } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';


import ActivityHeatmap from './ActivityHeatmap';
import AnomalyConfigPanel from './AnomalyConfigPanel';
import ClassFrequencyChart from './ClassFrequencyChart';
import {
  fetchCameras,
  fetchCameraActivityBaseline,
  fetchCameraClassBaseline,
  type Camera as CameraType,
  type ActivityBaselineResponse,
  type ClassBaselineResponse,
} from '../../services/api';

export interface BaselineAnalyticsProps {
  /** Optional className for styling */
  className?: string;
  /** Pre-selected camera ID (optional) */
  initialCameraId?: string;
}

/**
 * BaselineAnalytics provides a comprehensive view of baseline activity patterns
 * and anomaly detection configuration for cameras.
 *
 * Features:
 * - Camera selector dropdown
 * - Activity heatmap (24x7 grid)
 * - Object class frequency distribution
 * - Anomaly detection configuration panel
 * - Learning progress indicator
 */
export default function BaselineAnalytics({
  className = '',
  initialCameraId,
}: BaselineAnalyticsProps) {
  const [cameras, setCameras] = useState<CameraType[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string>(initialCameraId ?? '');
  const [activityBaseline, setActivityBaseline] = useState<ActivityBaselineResponse | null>(null);
  const [classBaseline, setClassBaseline] = useState<ClassBaselineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load cameras on mount
  useEffect(() => {
    const loadCameras = async () => {
      try {
        const cameraList = await fetchCameras();
        setCameras(cameraList);

        // Auto-select first camera if none selected
        if (!selectedCameraId && cameraList.length > 0) {
          setSelectedCameraId(cameraList[0].id);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load cameras');
      } finally {
        setLoading(false);
      }
    };

    void loadCameras();
  }, [selectedCameraId]);

  // Load baseline data when camera changes
  const loadBaselineData = useCallback(async (cameraId: string, isRefresh = false) => {
    if (!cameraId) return;

    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      const [activityData, classData] = await Promise.all([
        fetchCameraActivityBaseline(cameraId),
        fetchCameraClassBaseline(cameraId),
      ]);

      setActivityBaseline(activityData);
      setClassBaseline(classData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load baseline data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (selectedCameraId) {
      void loadBaselineData(selectedCameraId);
    }
  }, [selectedCameraId, loadBaselineData]);

  const handleRefresh = () => {
    if (selectedCameraId) {
      void loadBaselineData(selectedCameraId, true);
    }
  };

  const selectedCamera = cameras.find((c) => c.id === selectedCameraId);

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <TrendingUp className="h-6 w-6 text-green-500" />
          <div>
            <Title className="text-white">Baseline Analytics</Title>
            <Text className="text-gray-400">
              View activity patterns and configure anomaly detection
            </Text>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {/* Camera Selector */}
          <div className="flex items-center gap-2">
            <Camera className="h-4 w-4 text-gray-400" />
            <Select
              value={selectedCameraId}
              onValueChange={setSelectedCameraId}
              placeholder="Select a camera"
              className="w-48"
              disabled={cameras.length === 0}
            >
              {cameras.map((camera) => (
                <SelectItem key={camera.id} value={camera.id}>
                  {camera.name}
                </SelectItem>
              ))}
            </Select>
          </div>
          {/* Refresh Button */}
          <button
            onClick={handleRefresh}
            disabled={!selectedCameraId || refreshing}
            className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-50
                       disabled:cursor-not-allowed transition-colors"
            title="Refresh baseline data"
          >
            <RefreshCw className={`h-4 w-4 text-gray-400 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="p-4 bg-red-900/20 border border-red-800 rounded-lg flex items-center gap-3">
          <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
          <div>
            <Text className="text-red-400 font-medium">Error loading baseline data</Text>
            <Text className="text-red-400/80">{error}</Text>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && !error && (
        <div className="flex items-center justify-center h-64">
          <div className="animate-pulse text-gray-400">Loading baseline data...</div>
        </div>
      )}

      {/* No Camera Selected */}
      {!loading && !error && !selectedCameraId && cameras.length > 0 && (
        <div className="flex flex-col items-center justify-center h-64 text-gray-400">
          <Camera className="h-12 w-12 mb-4 opacity-50" />
          <Text>Select a camera to view baseline analytics</Text>
        </div>
      )}

      {/* No Cameras Available */}
      {!loading && !error && cameras.length === 0 && (
        <div className="flex flex-col items-center justify-center h-64 text-gray-400">
          <Camera className="h-12 w-12 mb-4 opacity-50" />
          <Text>No cameras configured</Text>
          <Text className="text-sm">Add cameras in the Cameras settings tab</Text>
        </div>
      )}

      {/* Baseline Data */}
      {!loading && !error && selectedCameraId && activityBaseline && classBaseline && (
        <>
          {/* Learning Progress */}
          <div className="bg-[#1A1A1A] border border-gray-800 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div
                  className={`w-3 h-3 rounded-full ${
                    activityBaseline.learning_complete ? 'bg-green-500' : 'bg-yellow-500 animate-pulse'
                  }`}
                />
                <div>
                  <Text className="text-white font-medium">
                    {selectedCamera?.name ?? 'Camera'} Baseline Status
                  </Text>
                  <Text className="text-gray-400 text-sm">
                    {activityBaseline.learning_complete
                      ? 'Baseline learning complete - anomaly detection active'
                      : 'Collecting data - anomaly detection will activate when learning completes'}
                  </Text>
                </div>
              </div>
              <div className="text-right">
                <Text className="text-white font-medium">
                  {activityBaseline.total_samples.toLocaleString()}
                </Text>
                <Text className="text-gray-400 text-sm">total samples</Text>
              </div>
            </div>
          </div>

          {/* Activity Heatmap */}
          <ActivityHeatmap
            entries={activityBaseline.entries}
            peakHour={activityBaseline.peak_hour}
            peakDay={activityBaseline.peak_day}
            learningComplete={activityBaseline.learning_complete}
          />

          {/* Class Frequency Chart */}
          <ClassFrequencyChart
            entries={classBaseline.entries}
            uniqueClasses={classBaseline.unique_classes}
            totalSamples={classBaseline.total_samples}
            mostCommonClass={classBaseline.most_common_class}
          />
        </>
      )}

      {/* Anomaly Config Panel - Always visible */}
      <AnomalyConfigPanel />
    </div>
  );
}
