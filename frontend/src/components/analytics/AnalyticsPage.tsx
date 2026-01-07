import {
  TabGroup,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
  Card,
  Title,
  Text,
  Metric,
  AreaChart,
  DonutChart,
  BarChart,
  ProgressBar,
  Badge,
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
} from '@tremor/react';
import { BarChart3, AlertCircle, Camera, RefreshCw, TrendingUp, Shield, Activity } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';

import ActivityHeatmap from './ActivityHeatmap';
import { ChartSkeleton, Skeleton } from '../common';
import AnomalyConfigPanel from './AnomalyConfigPanel';
import ClassFrequencyChart from './ClassFrequencyChart';
import PipelineLatencyPanel from './PipelineLatencyPanel';
import SceneChangePanel from './SceneChangePanel';
import {
  fetchCameras,
  fetchCameraActivityBaseline,
  fetchCameraClassBaseline,
  fetchAnomalyConfig,
  fetchEventStats,
  fetchDetectionStats,
  fetchEvents,
  type Camera as CameraType,
  type ActivityBaselineResponse,
  type ClassBaselineResponse,
  type AnomalyConfig,
  type EventStatsResponse,
  type DetectionStatsResponse,
  type Event,
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
  const [eventStats, setEventStats] = useState<EventStatsResponse | null>(null);
  const [detectionStats, setDetectionStats] = useState<DetectionStatsResponse | null>(null);
  const [highRiskEvents, setHighRiskEvents] = useState<Event[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [selectedTab, setSelectedTab] = useState(0);

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
      // Calculate date range for last 7 days
      const endDate = new Date();
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - 7);

      const [activity, classes, config, stats, detStats, events] = await Promise.all([
        fetchCameraActivityBaseline(cameraId),
        fetchCameraClassBaseline(cameraId),
        fetchAnomalyConfig(),
        fetchEventStats({
          start_date: startDate.toISOString().split('T')[0],
          end_date: endDate.toISOString().split('T')[0],
        }),
        fetchDetectionStats(),
        fetchEvents({ risk_level: 'high', limit: 10 }),
      ]);

      setActivityBaseline(activity);
      setClassBaseline(classes);
      setAnomalyConfig(config);
      setEventStats(stats);
      setDetectionStats(detStats);
      setHighRiskEvents(events.events);
    } catch (err) {
      setError('Failed to load analytics data');
      console.error('Failed to load analytics data:', err);
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

  // Empty state component
  const EmptyState = ({ message }: { message: string }) => (
    <div className="flex min-h-[300px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
      <div className="text-center">
        <AlertCircle className="mx-auto mb-4 h-12 w-12 text-gray-600" />
        <p className="text-gray-400">{message}</p>
        <p className="mt-2 text-sm text-gray-500">Try selecting a different time period or camera</p>
      </div>
    </div>
  );

  // Prepare chart data
  const prepareDetectionTrendData = () => {
    // Mock data for last 7 days - in real implementation, this would come from API
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    return days.map((day) => ({
      date: day,
      detections: Math.floor(Math.random() * 100) + 20,
    }));
  };

  const prepareObjectDistributionData = () => {
    if (!detectionStats?.detections_by_class) return [];
    return Object.entries(detectionStats.detections_by_class).map(([name, value]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      value,
    }));
  };

  const prepareRiskDistributionData = () => {
    if (!eventStats) return [];
    const riskLevels = eventStats.events_by_risk_level || {};
    return [
      { name: 'Low (0-30)', value: riskLevels.low || 0 },
      { name: 'Medium (30-70)', value: riskLevels.medium || 0 },
      { name: 'High (70+)', value: riskLevels.high || 0 },
    ].filter((item) => item.value > 0);
  };

  const prepareCameraActivityData = () => {
    if (!eventStats?.events_by_camera) return [];
    return eventStats.events_by_camera
      .map((cam) => ({
        camera: cam.camera_name || cam.camera_id,
        events: cam.event_count,
      }))
      .sort((a, b) => b.events - a.events)
      .slice(0, 5);
  };

  return (
    <div className="flex flex-col">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <BarChart3 className="h-8 w-8 text-[#76B900]" />
          <h1 className="text-page-title">Analytics</h1>
        </div>
        <p className="text-body-sm mt-2">
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
          data-testid="analytics-refresh-button"
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

      {/* Loading State with Skeletons */}
      {isLoading && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Activity Heatmap skeleton - Full Width */}
          <div className="lg:col-span-2">
            <ChartSkeleton height={320} />
          </div>

          {/* Class Frequency Chart skeleton */}
          <ChartSkeleton height={280} />

          {/* Anomaly Config Panel skeleton */}
          <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
            <Skeleton variant="text" width={160} height={24} className="mb-4" />
            <div className="space-y-4">
              {Array.from({ length: 4 }, (_, i) => (
                <div key={i} className="flex items-center justify-between">
                  <Skeleton variant="text" width={120} height={16} />
                  <Skeleton variant="rectangular" width={80} height={32} />
                </div>
              ))}
            </div>
          </div>

          {/* Pipeline Latency Panel skeleton - Full Width */}
          <div className="lg:col-span-2">
            <ChartSkeleton height={250} />
          </div>

          {/* Scene Change Detection Panel skeleton - Full Width */}
          <div className="lg:col-span-2">
            <ChartSkeleton height={200} />
          </div>
        </div>
      )}

      {/* Content */}
      {!isLoading && !error && selectedCameraId && (
        <TabGroup index={selectedTab} onIndexChange={setSelectedTab}>
          <TabList className="mb-6">
            <Tab
              className="data-[selected]:bg-[#76B900] data-[selected]:text-white bg-transparent text-gray-400"
              data-testid="analytics-tab-overview"
            >
              <div className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4" />
                Overview
              </div>
            </Tab>
            <Tab
              className="data-[selected]:bg-[#76B900] data-[selected]:text-white bg-transparent text-gray-400"
              data-testid="analytics-tab-detections"
            >
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4" />
                Detections
              </div>
            </Tab>
            <Tab
              className="data-[selected]:bg-[#76B900] data-[selected]:text-white bg-transparent text-gray-400"
              data-testid="analytics-tab-risk"
            >
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4" />
                Risk Analysis
              </div>
            </Tab>
            <Tab
              className="data-[selected]:bg-[#76B900] data-[selected]:text-white bg-transparent text-gray-400"
              data-testid="analytics-tab-camera-performance"
            >
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4" />
                Camera Performance
              </div>
            </Tab>
          </TabList>

          <TabPanels>
            {/* Overview Tab */}
            <TabPanel>
              <div className="space-y-6">
                {/* Key Metrics Row */}
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <Card decoration="top" decorationColor="green">
                    <Text>Total Events</Text>
                    <Metric>{eventStats?.total_events || 0}</Metric>
                  </Card>
                  <Card decoration="top" decorationColor="blue">
                    <Text>Total Detections</Text>
                    <Metric>{detectionStats?.total_detections || 0}</Metric>
                  </Card>
                  <Card decoration="top" decorationColor="yellow">
                    <Text>Average Confidence</Text>
                    <Metric>
                      {detectionStats?.average_confidence
                        ? `${(detectionStats.average_confidence * 100).toFixed(1)}%`
                        : 'N/A'}
                    </Metric>
                  </Card>
                  <Card decoration="top" decorationColor="red">
                    <Text>High Risk Events</Text>
                    <Metric>{highRiskEvents.length}</Metric>
                  </Card>
                </div>

                {/* Detection Trend Chart */}
                <Card>
                  <Title>Detection Trend (Last 7 Days)</Title>
                  {prepareDetectionTrendData().length > 0 ? (
                    <AreaChart
                      className="mt-4 h-72"
                      data={prepareDetectionTrendData()}
                      index="date"
                      categories={['detections']}
                      colors={['green']}
                      valueFormatter={(value) => `${value} detections`}
                    />
                  ) : (
                    <EmptyState message="No detection data available for the selected period" />
                  )}
                </Card>

                {/* Top Cameras by Activity */}
                <Card>
                  <Title>Top Cameras by Activity</Title>
                  {prepareCameraActivityData().length > 0 ? (
                    <BarChart
                      className="mt-4 h-72"
                      data={prepareCameraActivityData()}
                      index="camera"
                      categories={['events']}
                      colors={['green']}
                      valueFormatter={(value) => `${value} events`}
                    />
                  ) : (
                    <EmptyState message="No camera activity data available" />
                  )}
                </Card>
              </div>
            </TabPanel>

            {/* Detections Tab */}
            <TabPanel>
              <div className="space-y-6">
                {/* Object Type Distribution */}
                <div className="grid gap-6 lg:grid-cols-2">
                  <Card>
                    <Title>Object Type Distribution</Title>
                    {prepareObjectDistributionData().length > 0 ? (
                      <DonutChart
                        className="mt-4 h-72"
                        data={prepareObjectDistributionData()}
                        category="value"
                        index="name"
                        colors={['green', 'blue', 'yellow', 'red', 'purple', 'pink']}
                        valueFormatter={(value) => `${value} detections`}
                      />
                    ) : (
                      <EmptyState message="No detection class data available" />
                    )}
                  </Card>

                  {/* Class Frequency Chart */}
                  <div>
                    {classBaseline ? (
                      <ClassFrequencyChart
                        entries={classBaseline.entries}
                        uniqueClasses={classBaseline.unique_classes}
                        mostCommonClass={classBaseline.most_common_class}
                      />
                    ) : (
                      <Card>
                        <EmptyState message="No class baseline data available" />
                      </Card>
                    )}
                  </div>
                </div>

                {/* Detections Over Time */}
                <Card>
                  <Title>Detections Over Time</Title>
                  {prepareDetectionTrendData().length > 0 ? (
                    <AreaChart
                      className="mt-4 h-72"
                      data={prepareDetectionTrendData()}
                      index="date"
                      categories={['detections']}
                      colors={['blue']}
                      valueFormatter={(value) => `${value} detections`}
                    />
                  ) : (
                    <EmptyState message="No detection trend data available" />
                  )}
                </Card>

                {/* Detection Confidence Stats */}
                <Card>
                  <Title>Detection Quality Metrics</Title>
                  <div className="mt-4 space-y-4">
                    <div>
                      <div className="flex justify-between">
                        <Text>Average Confidence</Text>
                        <Text>
                          {detectionStats?.average_confidence
                            ? `${(detectionStats.average_confidence * 100).toFixed(1)}%`
                            : 'N/A'}
                        </Text>
                      </div>
                      <ProgressBar
                        value={
                          detectionStats?.average_confidence
                            ? detectionStats.average_confidence * 100
                            : 0
                        }
                        color="green"
                        className="mt-2"
                      />
                    </div>
                    <div>
                      <div className="flex justify-between">
                        <Text>Total Detections</Text>
                        <Metric>{detectionStats?.total_detections || 0}</Metric>
                      </div>
                    </div>
                  </div>
                </Card>
              </div>
            </TabPanel>

            {/* Risk Analysis Tab */}
            <TabPanel>
              <div className="space-y-6">
                {/* Risk Score Distribution */}
                <div className="grid gap-6 lg:grid-cols-2">
                  <Card>
                    <Title>Risk Score Distribution</Title>
                    {prepareRiskDistributionData().length > 0 ? (
                      <DonutChart
                        className="mt-4 h-72"
                        data={prepareRiskDistributionData()}
                        category="value"
                        index="name"
                        colors={['green', 'yellow', 'red']}
                        valueFormatter={(value) => `${value} events`}
                      />
                    ) : (
                      <EmptyState message="No risk distribution data available" />
                    )}
                  </Card>

                  {/* Anomaly Config Panel */}
                  <div>
                    {anomalyConfig ? (
                      <AnomalyConfigPanel
                        config={anomalyConfig}
                        onConfigUpdated={handleConfigUpdated}
                      />
                    ) : (
                      <Card>
                        <EmptyState message="No anomaly configuration available" />
                      </Card>
                    )}
                  </div>
                </div>

                {/* High-Risk Events List */}
                <Card>
                  <Title>Recent High-Risk Events</Title>
                  {highRiskEvents.length > 0 ? (
                    <Table className="mt-4">
                      <TableHead>
                        <TableRow>
                          <TableHeaderCell>Time</TableHeaderCell>
                          <TableHeaderCell>Camera</TableHeaderCell>
                          <TableHeaderCell>Risk Score</TableHeaderCell>
                          <TableHeaderCell>Description</TableHeaderCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {highRiskEvents.map((event) => (
                          <TableRow key={event.id}>
                            <TableCell>
                              {new Date(event.started_at).toLocaleString()}
                            </TableCell>
                            <TableCell>{event.camera_id}</TableCell>
                            <TableCell>
                              <Badge color="red">{event.risk_score || 'N/A'}</Badge>
                            </TableCell>
                            <TableCell className="max-w-md truncate">
                              {event.reasoning || 'No description available'}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <EmptyState message="No high-risk events found" />
                  )}
                </Card>

                {/* Risk Trends Over Time */}
                <Card>
                  <Title>Event Activity Trend</Title>
                  {prepareDetectionTrendData().length > 0 ? (
                    <AreaChart
                      className="mt-4 h-72"
                      data={prepareDetectionTrendData()}
                      index="date"
                      categories={['detections']}
                      colors={['red']}
                      valueFormatter={(value) => `${value} events`}
                    />
                  ) : (
                    <EmptyState message="No trend data available" />
                  )}
                </Card>
              </div>
            </TabPanel>

            {/* Camera Performance Tab */}
            <TabPanel>
              <div className="space-y-6">
                {/* Per-Camera Detection Counts */}
                <Card>
                  <Title>Detection Counts by Camera</Title>
                  {prepareCameraActivityData().length > 0 ? (
                    <BarChart
                      className="mt-4 h-72"
                      data={prepareCameraActivityData()}
                      index="camera"
                      categories={['events']}
                      colors={['blue']}
                      valueFormatter={(value) => `${value} detections`}
                      layout="vertical"
                    />
                  ) : (
                    <EmptyState message="No camera detection data available" />
                  )}
                </Card>

                {/* Activity Heatmap */}
                <div>
                  {activityBaseline ? (
                    <ActivityHeatmap
                      entries={activityBaseline.entries}
                      learningComplete={activityBaseline.learning_complete}
                      minSamplesRequired={activityBaseline.min_samples_required}
                    />
                  ) : (
                    <Card>
                      <EmptyState message="No activity baseline data available" />
                    </Card>
                  )}
                </div>

                {/* Pipeline Latency Panel */}
                <PipelineLatencyPanel refreshInterval={60000} />

                {/* Scene Change Detection Panel */}
                {selectedCamera && (
                  <SceneChangePanel
                    cameraId={selectedCameraId}
                    cameraName={selectedCamera.name}
                  />
                )}
              </div>
            </TabPanel>
          </TabPanels>
        </TabGroup>
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
