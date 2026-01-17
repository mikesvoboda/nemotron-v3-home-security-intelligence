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
  BarChart,
  BarList,
  ProgressBar,
  Badge,
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
} from '@tremor/react';
import {
  BarChart3,
  AlertCircle,
  Camera,
  RefreshCw,
  TrendingUp,
  Shield,
  Activity,
} from 'lucide-react';
import { useState, useEffect, useCallback, useMemo } from 'react';

import ActivityHeatmap from './ActivityHeatmap';
import CameraUptimeCard from './CameraUptimeCard';
import DateRangeDropdown from './DateRangeDropdown';
import { ChartSkeleton, Skeleton } from '../common';
import AnomalyConfigPanel from './AnomalyConfigPanel';
import ClassFrequencyChart from './ClassFrequencyChart';
import PipelineLatencyPanel from './PipelineLatencyPanel';
import SceneChangePanel from './SceneChangePanel';
import { useDateRangeState } from '../../hooks/useDateRangeState';
import { useDetectionTrendsQuery } from '../../hooks/useDetectionTrendsQuery';
import { useRiskHistoryQuery } from '../../hooks/useRiskHistoryQuery';
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
// Special value for "All Cameras" option - empty string
const ALL_CAMERAS_VALUE = '';

export default function AnalyticsPage() {
  // State
  const [cameras, setCameras] = useState<CameraType[]>([]);
  // Empty string means "All Cameras", non-empty means specific camera
  const [selectedCameraId, setSelectedCameraId] = useState<string>(ALL_CAMERAS_VALUE);
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

  // Global date range state with URL persistence
  const {
    preset: dateRangePreset,
    presetLabel: dateRangeLabel,
    isCustom: isCustomDateRange,
    range: dateRange,
    apiParams: dateRangeApiParams,
    setPreset: setDateRangePreset,
    setCustomRange: setDateRangeCustom,
  } = useDateRangeState({
    defaultPreset: '7d',
    urlParam: 'range',
  });

  // Calculate date range for detection trends using the global date range
  const detectionTrendsDateRange = useMemo(() => {
    return {
      start_date: dateRangeApiParams.start_date,
      end_date: dateRangeApiParams.end_date,
    };
  }, [dateRangeApiParams]);

  // Calculate date range for camera uptime (last 30 days)
  const cameraUptimeDateRange = useMemo(() => {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 29); // 30 days including today

    return {
      startDate: startDate.toISOString().split('T')[0],
      endDate: endDate.toISOString().split('T')[0],
    };
  }, []);

  // Fetch detection trends using TanStack Query hook
  const {
    dataPoints: detectionTrendDataPoints,
    isLoading: isDetectionTrendsLoading,
    isError: isDetectionTrendsError,
  } = useDetectionTrendsQuery(detectionTrendsDateRange);

  // Fetch risk history using TanStack Query hook
  const {
    dataPoints: riskHistoryDataPoints,
    isLoading: isRiskHistoryLoading,
    isError: isRiskHistoryError,
  } = useRiskHistoryQuery(detectionTrendsDateRange);

  // Helper to check if "All Cameras" is selected
  const isAllCamerasSelected = selectedCameraId === ALL_CAMERAS_VALUE;

  // Load cameras on mount
  useEffect(() => {
    const loadCameras = async () => {
      try {
        const camerasData = await fetchCameras();
        setCameras(camerasData);
        // Default to "All Cameras" view for aggregate stats
        // Don't change selectedCameraId - it's already set to ALL_CAMERAS_VALUE
        if (camerasData.length === 0) {
          // No cameras available, but still allow loading aggregate stats
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

  // Load analytics data when camera or date range changes
  // cameraId can be empty string for "All Cameras" or a specific camera ID
  const loadAnalyticsData = useCallback(
    async (cameraId: string) => {
      setIsLoading(true);
      setError(null);

      // Determine if this is "All Cameras" view
      const isAllCameras = cameraId === ALL_CAMERAS_VALUE;
      // Only pass camera_id to API when a specific camera is selected
      const cameraIdParam = isAllCameras ? undefined : cameraId;

      try {
        // Prepare API calls - camera-specific baselines only when a camera is selected
        const apiCalls: Promise<unknown>[] = [
          // Always fetch anomaly config (global setting)
          fetchAnomalyConfig(),
          // Always fetch event stats with consistent camera filtering
          // Use date range from global state
          fetchEventStats({
            start_date: dateRangeApiParams.start_date,
            end_date: dateRangeApiParams.end_date,
            camera_id: cameraIdParam,
          }),
          // Always fetch detection stats with consistent camera filtering
          fetchDetectionStats({ camera_id: cameraIdParam }),
          // Always fetch high risk events with consistent camera filtering
          fetchEvents({ risk_level: 'high', limit: 10, camera_id: cameraIdParam }),
        ];

      // Camera-specific baselines only when a specific camera is selected
      if (!isAllCameras) {
        apiCalls.push(fetchCameraActivityBaseline(cameraId), fetchCameraClassBaseline(cameraId));
      }

      const results = await Promise.all(apiCalls);

      // Extract results based on whether all cameras or specific camera
      const config = results[0] as AnomalyConfig;
      const stats = results[1] as EventStatsResponse;
      const detStats = results[2] as DetectionStatsResponse;
      const eventsResult = results[3] as { items: Event[] };

      setAnomalyConfig(config);
      setEventStats(stats);
      setDetectionStats(detStats);
      setHighRiskEvents(eventsResult.items);

      if (!isAllCameras) {
        const activity = results[4] as ActivityBaselineResponse;
        const classes = results[5] as ClassBaselineResponse;
        setActivityBaseline(activity);
        setClassBaseline(classes);
      } else {
        // Clear camera-specific data when "All Cameras" is selected
        setActivityBaseline(null);
        setClassBaseline(null);
      }
    } catch (err) {
      setError('Failed to load analytics data');
      console.error('Failed to load analytics data:', err);
    } finally {
      setIsLoading(false);
    }
  },
  [dateRangeApiParams.start_date, dateRangeApiParams.end_date]
);

  // Load data when selected camera or date range changes
  useEffect(() => {
    // Always load analytics data - even for "All Cameras" (empty string)
    void loadAnalyticsData(selectedCameraId);
  }, [selectedCameraId, loadAnalyticsData, dateRangeApiParams]);

  // Handle refresh
  const handleRefresh = useCallback(async () => {
    if (isRefreshing) return;

    setIsRefreshing(true);
    try {
      await loadAnalyticsData(selectedCameraId);
    } finally {
      setIsRefreshing(false);
    }
  }, [selectedCameraId, isRefreshing, loadAnalyticsData]);

  // Handle camera change
  const handleCameraChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedCameraId(e.target.value);
  };

  // Handle config update
  const handleConfigUpdated = (updatedConfig: AnomalyConfig) => {
    setAnomalyConfig(updatedConfig);
  };

  // Get selected camera (null when "All Cameras" is selected)
  const selectedCamera = isAllCamerasSelected
    ? null
    : cameras.find((c) => c.id === selectedCameraId);

  // Empty state component
  const EmptyState = ({ message }: { message: string }) => (
    <div className="flex min-h-[300px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
      <div className="text-center">
        <AlertCircle className="mx-auto mb-4 h-12 w-12 text-gray-600" />
        <p className="text-gray-400">{message}</p>
        <p className="mt-2 text-sm text-gray-500">
          Try selecting a different time period or camera
        </p>
      </div>
    </div>
  );

  // Prepare chart data from real detection trends API
  const prepareDetectionTrendData = () => {
    // Convert API data points to chart format
    // API returns: { date: "2026-01-10", count: 45 }
    // Chart expects: { date: "Jan 10", detections: 45 }
    return detectionTrendDataPoints.map((point) => {
      const date = new Date(point.date);
      const formattedDate = date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
      return {
        date: formattedDate,
        detections: point.count,
      };
    });
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
      { name: 'Medium (31-60)', value: riskLevels.medium || 0 },
      { name: 'High (61-80)', value: riskLevels.high || 0 },
      { name: 'Critical (81+)', value: riskLevels.critical || 0 },
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

  // Prepare chart data from risk history API for stacked area chart
  const prepareRiskHistoryChartData = () => {
    // Convert API data points to chart format
    // API returns: { date: "2026-01-10", low: 12, medium: 8, high: 3, critical: 1 }
    // Chart expects same structure with formatted date
    return riskHistoryDataPoints.map((point) => {
      const date = new Date(point.date);
      const formattedDate = date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
      return {
        date: formattedDate,
        critical: point.critical,
        high: point.high,
        medium: point.medium,
        low: point.low,
      };
    });
  };

  return (
    <div className="flex flex-col">
      {/* Header with Date Range Dropdown */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart3 className="h-8 w-8 text-[#76B900]" />
            <h1 className="text-page-title">Analytics</h1>
          </div>
          <DateRangeDropdown
            preset={dateRangePreset}
            presetLabel={dateRangeLabel}
            isCustom={isCustomDateRange}
            range={dateRange}
            setPreset={setDateRangePreset}
            setCustomRange={setDateRangeCustom}
          />
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
            value={selectedCameraId}
            onChange={handleCameraChange}
            className="rounded border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-[#76B900] focus:outline-none"
            data-testid="camera-selector"
          >
            {/* "All Cameras" option for aggregate view */}
            <option value={ALL_CAMERAS_VALUE}>All Cameras</option>
            {cameras.map((camera) => (
              <option key={camera.id} value={camera.id}>
                {camera.name || camera.id}
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={() => void handleRefresh()}
          disabled={isRefreshing}
          className="flex items-center gap-2 rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-300 transition-colors hover:bg-gray-700 disabled:opacity-50"
          data-testid="analytics-refresh-button"
        >
          <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>

        {/* Show baseline learning status only when a specific camera is selected */}
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

        {/* Show indicator when viewing all cameras */}
        {isAllCamerasSelected && (
          <span className="text-sm text-gray-400">Showing aggregate stats across all cameras</span>
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

      {/* Content - show when not loading and no error */}
      {!isLoading && !error && (
        <TabGroup index={selectedTab} onIndexChange={setSelectedTab}>
          <TabList className="mb-6">
            <Tab
              className="bg-transparent text-gray-400 data-[selected]:bg-[#76B900] data-[selected]:text-white"
              data-testid="analytics-tab-overview"
            >
              <div className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4" />
                Overview
              </div>
            </Tab>
            <Tab
              className="bg-transparent text-gray-400 data-[selected]:bg-[#76B900] data-[selected]:text-white"
              data-testid="analytics-tab-detections"
            >
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4" />
                Detections
              </div>
            </Tab>
            <Tab
              className="bg-transparent text-gray-400 data-[selected]:bg-[#76B900] data-[selected]:text-white"
              data-testid="analytics-tab-risk"
            >
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4" />
                Risk Analysis
              </div>
            </Tab>
            <Tab
              className="bg-transparent text-gray-400 data-[selected]:bg-[#76B900] data-[selected]:text-white"
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
                  <Title>
                    Detection Trend ({detectionTrendsDateRange.start_date} to{' '}
                    {detectionTrendsDateRange.end_date})
                  </Title>
                  {isDetectionTrendsLoading ? (
                    <div className="mt-4">
                      <ChartSkeleton height={288} />
                    </div>
                  ) : isDetectionTrendsError ? (
                    <EmptyState message="Failed to load detection trend data" />
                  ) : prepareDetectionTrendData().length > 0 ? (
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
                      <div className="mt-4">
                        <div className="mb-4 flex items-center justify-between">
                          <Text className="text-gray-400">Detection counts by object type</Text>
                          <Text className="font-semibold text-white">
                            {detectionStats?.total_detections || 0} total
                          </Text>
                        </div>
                        <BarList
                          data={prepareObjectDistributionData().map((item, index) => {
                            const colors = ['cyan', 'violet', 'amber', 'rose', 'emerald', 'fuchsia'];
                            return {
                              name: item.name,
                              value: item.value,
                              color: colors[index % colors.length],
                            };
                          })}
                          valueFormatter={(value: number) => `${value} detections`}
                          className="mt-2"
                        />
                      </div>
                    ) : (
                      <EmptyState message="No detection class data available" />
                    )}
                  </Card>

                  {/* Class Frequency Chart - Camera-specific baseline */}
                  <div>
                    {classBaseline ? (
                      <ClassFrequencyChart
                        entries={classBaseline.entries}
                        uniqueClasses={classBaseline.unique_classes}
                        mostCommonClass={classBaseline.most_common_class}
                      />
                    ) : (
                      <Card>
                        <EmptyState
                          message={
                            isAllCamerasSelected
                              ? 'Select a specific camera to view class frequency baseline'
                              : 'No class baseline data available'
                          }
                        />
                      </Card>
                    )}
                  </div>
                </div>

                {/* Detections Over Time */}
                <Card>
                  <Title>Detections Over Time</Title>
                  {isDetectionTrendsLoading ? (
                    <div className="mt-4">
                      <ChartSkeleton height={288} />
                    </div>
                  ) : isDetectionTrendsError ? (
                    <EmptyState message="Failed to load detection trend data" />
                  ) : prepareDetectionTrendData().length > 0 ? (
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
                      <div className="mt-4">
                        <div className="mb-4 flex items-center justify-between">
                          <Text className="text-gray-400">Events by risk level</Text>
                          <Text className="font-semibold text-white">
                            {eventStats?.total_events || 0} total
                          </Text>
                        </div>
                        <BarList
                          data={prepareRiskDistributionData().map((item, index) => {
                            const colors = ['emerald', 'amber', 'orange', 'rose'];
                            return {
                              name: item.name,
                              value: item.value,
                              color: colors[index % colors.length],
                            };
                          })}
                          valueFormatter={(value: number) => `${value} events`}
                          className="mt-2"
                        />
                      </div>
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
                            <TableCell>{new Date(event.started_at).toLocaleString()}</TableCell>
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

                {/* Risk History Stacked Area Chart (NEM-2704) */}
                <Card data-testid="risk-history-chart-card">
                  <Title>
                    Risk Level Breakdown ({detectionTrendsDateRange.start_date} to{' '}
                    {detectionTrendsDateRange.end_date})
                  </Title>
                  {isRiskHistoryLoading ? (
                    <div className="mt-4">
                      <ChartSkeleton height={288} />
                    </div>
                  ) : isRiskHistoryError ? (
                    <EmptyState message="Failed to load risk history data" />
                  ) : prepareRiskHistoryChartData().length > 0 ? (
                    <>
                      <AreaChart
                        className="mt-4 h-72"
                        data={prepareRiskHistoryChartData()}
                        index="date"
                        categories={['critical', 'high', 'medium', 'low']}
                        colors={['red', 'orange', 'yellow', 'emerald']}
                        stack={true}
                        valueFormatter={(value) => `${value} events`}
                        showAnimation={true}
                        data-testid="risk-history-area-chart"
                      />
                      {/* Legend */}
                      <div
                        className="mt-4 flex flex-wrap items-center justify-center gap-4"
                        data-testid="risk-history-legend"
                      >
                        <div className="flex items-center gap-2">
                          <div className="h-3 w-3 rounded-full bg-red-500" />
                          <Text className="text-sm text-gray-400">Critical (81+)</Text>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="h-3 w-3 rounded-full bg-orange-500" />
                          <Text className="text-sm text-gray-400">High (61-80)</Text>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="h-3 w-3 rounded-full bg-yellow-500" />
                          <Text className="text-sm text-gray-400">Medium (31-60)</Text>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="h-3 w-3 rounded-full bg-emerald-500" />
                          <Text className="text-sm text-gray-400">Low (0-30)</Text>
                        </div>
                      </div>
                    </>
                  ) : (
                    <EmptyState message="No risk history data available" />
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
                    <div className="mt-4">
                      <div className="mb-4 flex items-center justify-between">
                        <Text className="text-gray-400">Events per camera</Text>
                        <Text className="font-semibold text-white">
                          {prepareCameraActivityData().reduce((sum, item) => sum + item.events, 0)} total
                        </Text>
                      </div>
                      <BarList
                        data={prepareCameraActivityData().map((item) => ({
                          name: item.camera,
                          value: item.events,
                          color: 'blue',
                        }))}
                        valueFormatter={(value: number) => `${value} events`}
                        className="mt-2"
                      />
                    </div>
                  ) : (
                    <EmptyState message="No camera detection data available" />
                  )}
                </Card>

                {/* Camera Uptime Card */}
                <CameraUptimeCard dateRange={cameraUptimeDateRange} />

                {/* Activity Heatmap - Camera-specific, only shown when a camera is selected */}
                <div>
                  {activityBaseline ? (
                    <ActivityHeatmap
                      entries={activityBaseline.entries}
                      learningComplete={activityBaseline.learning_complete}
                      minSamplesRequired={activityBaseline.min_samples_required}
                    />
                  ) : (
                    <Card>
                      <EmptyState
                        message={
                          isAllCamerasSelected
                            ? 'Select a specific camera to view activity heatmap'
                            : 'No activity baseline data available'
                        }
                      />
                    </Card>
                  )}
                </div>

                {/* Pipeline Latency Panel */}
                <PipelineLatencyPanel refreshInterval={60000} />

                {/* Scene Change Detection Panel - Camera-specific */}
                {selectedCamera ? (
                  <SceneChangePanel cameraId={selectedCameraId} cameraName={selectedCamera.name} />
                ) : isAllCamerasSelected ? (
                  <Card>
                    <Title>Scene Changes</Title>
                    <EmptyState message="Select a specific camera to view scene changes" />
                  </Card>
                ) : null}
              </div>
            </TabPanel>
          </TabPanels>
        </TabGroup>
      )}
    </div>
  );
}
