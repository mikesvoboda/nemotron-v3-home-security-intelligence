/**
 * ZonesPage - Zone Intelligence Dashboard
 *
 * Comprehensive dashboard for viewing and managing all zone intelligence.
 * Provides a unified view of zones across all cameras with filtering,
 * time range selection, and data export capabilities.
 *
 * Features:
 * - Zone Overview Grid with status cards
 * - Zone Trust Matrix for household member/vehicle access
 * - Activity Timeline with zone filtering
 * - Anomaly Alert Feed
 * - System Health Indicator
 * - Zone type filtering
 * - Time range selection
 * - CSV export
 * - Full-screen panel mode
 *
 * @module pages/ZonesPage
 * @see NEM-3201 Phase 5.2 - Zone Intelligence Dashboard Page
 */

import { Tab } from '@headlessui/react';
import { clsx } from 'clsx';
import {
  AlertTriangle,
  BarChart3,
  Clock,
  Download,
  Filter,
  GitCompare,
  Grid,
  LayoutGrid,
  MapPin,
  Maximize2,
  Minimize2,
  RefreshCw,
  Shield,
} from 'lucide-react';
import { memo, useCallback, useMemo, useState } from 'react';

import Button from '../components/common/Button';
import EmptyState from '../components/common/EmptyState';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ActiveDwellersPanel from '../components/zones/ActiveDwellersPanel';
import ComparisonTab from '../components/zones/ComparisonTab';
import CrossingTrendsChart from '../components/zones/CrossingTrendsChart';
import DwellStatisticsCard from '../components/zones/DwellStatisticsCard';
import LineZoneCrossingCard from '../components/zones/LineZoneCrossingCard';
import LoiteringConfigModal from '../components/zones/LoiteringConfigModal';
import ZoneAnomalyFeed from '../components/zones/ZoneAnomalyFeed';
import ZoneEntityDistributionPanel from '../components/zones/ZoneEntityDistributionPanel';
import ZoneTrustMatrix from '../components/zones/ZoneTrustMatrix';
import { useCamerasQuery } from '../hooks/useCamerasQuery';
import {
  usePolygonZones,
  useDwellStatistics,
  useActiveDwellers,
} from '../hooks/useDwellTimeAnalytics';
import {
  useLineZoneAnalytics,
  useCrossingTrends,
  useResetCrossingCounts,
} from '../hooks/useLineZoneAnalytics';
import { useZonesQuery } from '../hooks/useZones';
import { ZONE_TABS } from '../types/zoneAnalytics';

import type { Zone, ZoneType } from '../types/generated';
import type { ZoneAnalyticsTab } from '../types/zoneAnalytics';

// ============================================================================
// Types
// ============================================================================

/**
 * Time range options for filtering zone data.
 */
type ZoneTimeRange = '1h' | '6h' | '24h' | '7d';

/**
 * Panel types for full-screen mode.
 */
type PanelType = 'overview' | 'trust' | 'timeline' | 'alerts' | null;

/**
 * Zone health status derived from activity and alerts.
 */
type ZoneHealthStatus = 'healthy' | 'warning' | 'critical' | 'unknown';

// ============================================================================
// Constants
// ============================================================================

/**
 * Available zone types for filtering.
 */
const ZONE_TYPE_OPTIONS: { value: ZoneType | 'all'; label: string }[] = [
  { value: 'all', label: 'All Types' },
  { value: 'entry_point', label: 'Entry Point' },
  { value: 'driveway', label: 'Driveway' },
  { value: 'sidewalk', label: 'Sidewalk' },
  { value: 'yard', label: 'Yard' },
  { value: 'other', label: 'Other' },
];

/**
 * Available time range options.
 */
const TIME_RANGE_OPTIONS: { value: ZoneTimeRange; label: string }[] = [
  { value: '1h', label: '1h' },
  { value: '6h', label: '6h' },
  { value: '24h', label: '24h' },
  { value: '7d', label: '7d' },
];

/**
 * Convert time range to hours for API lookback.
 */
const TIME_RANGE_HOURS: Record<ZoneTimeRange, number> = {
  '1h': 1,
  '6h': 6,
  '24h': 24,
  '7d': 168,
};

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Header with zone count and health summary.
 */
interface PageHeaderProps {
  zoneCount: number;
  healthSummary: {
    healthy: number;
    warning: number;
    critical: number;
    unknown: number;
  };
  isRefetching: boolean;
  onRefresh: () => void;
}

function PageHeader({ zoneCount, healthSummary, isRefetching, onRefresh }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-page-title">Zone Intelligence</h1>
        <p className="text-body-sm mt-1">
          Monitor and manage {zoneCount} {zoneCount === 1 ? 'zone' : 'zones'} across your property
        </p>
      </div>

      <div className="flex items-center gap-4">
        {/* Health Summary */}
        <div className="flex items-center gap-3 rounded-lg bg-gray-800/50 px-4 py-2">
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-green-500" />
            <span className="text-sm text-gray-300">{healthSummary.healthy}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-yellow-500" />
            <span className="text-sm text-gray-300">{healthSummary.warning}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-red-500" />
            <span className="text-sm text-gray-300">{healthSummary.critical}</span>
          </div>
        </div>

        {/* Refresh Button */}
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<RefreshCw className={clsx('h-4 w-4', isRefetching && 'animate-spin')} />}
          onClick={onRefresh}
          disabled={isRefetching}
        >
          Refresh
        </Button>
      </div>
    </div>
  );
}

/**
 * Filter bar for zone type and time range.
 */
interface FilterBarProps {
  zoneTypeFilter: ZoneType | 'all';
  onZoneTypeChange: (type: ZoneType | 'all') => void;
  timeRange: ZoneTimeRange;
  onTimeRangeChange: (range: ZoneTimeRange) => void;
  onExport: () => void;
  isExporting: boolean;
}

function FilterBar({
  zoneTypeFilter,
  onZoneTypeChange,
  timeRange,
  onTimeRangeChange,
  onExport,
  isExporting,
}: FilterBarProps) {
  return (
    <div
      className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-lg bg-gray-800/50 p-4"
      data-testid="zone-filter-bar"
    >
      <div className="flex flex-wrap items-center gap-4">
        {/* Zone Type Filter */}
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-gray-400" />
          <label htmlFor="zone-type-filter" className="sr-only">
            Zone Type
          </label>
          <select
            id="zone-type-filter"
            value={zoneTypeFilter}
            onChange={(e) => onZoneTypeChange(e.target.value as ZoneType | 'all')}
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            data-testid="zone-type-select"
          >
            {ZONE_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {/* Time Range Selector */}
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-gray-400" />
          <div
            className="flex rounded-lg border border-gray-700 p-0.5"
            role="group"
            aria-label="Time range selection"
            data-testid="time-range-selector"
          >
            {TIME_RANGE_OPTIONS.map(({ value, label }) => (
              <button
                key={value}
                type="button"
                onClick={() => onTimeRangeChange(value)}
                aria-pressed={timeRange === value}
                className={clsx(
                  'rounded-md px-3 py-1.5 text-sm font-medium transition-all',
                  timeRange === value
                    ? 'bg-primary text-white'
                    : 'text-gray-400 hover:bg-gray-700 hover:text-gray-200'
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Export Button */}
      <Button
        variant="outline-primary"
        size="sm"
        leftIcon={<Download className="h-4 w-4" />}
        onClick={onExport}
        disabled={isExporting}
        data-testid="export-button"
      >
        {isExporting ? 'Exporting...' : 'Export CSV'}
      </Button>
    </div>
  );
}

/**
 * Zone status card displaying zone information.
 */
interface ZoneStatusCardProps {
  zone: Zone;
  healthStatus: ZoneHealthStatus;
}

function ZoneStatusCard({ zone, healthStatus }: ZoneStatusCardProps) {
  const healthConfig: Record<ZoneHealthStatus, { color: string; bg: string; label: string }> = {
    healthy: { color: 'text-green-400', bg: 'bg-green-500/20', label: 'Healthy' },
    warning: { color: 'text-yellow-400', bg: 'bg-yellow-500/20', label: 'Warning' },
    critical: { color: 'text-red-400', bg: 'bg-red-500/20', label: 'Critical' },
    unknown: { color: 'text-gray-400', bg: 'bg-gray-500/20', label: 'Unknown' },
  };

  const config = healthConfig[healthStatus];

  const zoneTypeLabels: Record<string, string> = {
    entry_point: 'Entry Point',
    driveway: 'Driveway',
    sidewalk: 'Sidewalk',
    yard: 'Yard',
    other: 'Other',
  };

  return (
    <div
      className="rounded-lg border border-gray-700 bg-gray-800/50 p-4 transition-all hover:border-gray-600"
      data-testid={`zone-card-${zone.id}`}
    >
      <div className="mb-3 flex items-start justify-between">
        <div className="flex items-center gap-2">
          <div
            className="h-3 w-3 rounded-full"
            style={{ backgroundColor: zone.color }}
            aria-hidden="true"
          />
          <h3 className="font-medium text-white">{zone.name}</h3>
        </div>
        <span
          className={clsx('rounded-full px-2 py-0.5 text-xs font-medium', config.bg, config.color)}
        >
          {config.label}
        </span>
      </div>

      <div className="space-y-1.5 text-sm text-gray-400">
        <div className="flex items-center justify-between">
          <span>Type</span>
          <span className="text-gray-300">{zoneTypeLabels[zone.zone_type] || zone.zone_type}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Status</span>
          <span className={zone.enabled ? 'text-green-400' : 'text-gray-500'}>
            {zone.enabled ? 'Active' : 'Inactive'}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span>Priority</span>
          <span className="text-gray-300">{zone.priority}</span>
        </div>
      </div>
    </div>
  );
}

/**
 * Panel wrapper with header and full-screen toggle.
 */
interface PanelWrapperProps {
  title: string;
  icon: React.ReactNode;
  panelType: PanelType;
  isFullScreen: boolean;
  onToggleFullScreen: (panel: PanelType) => void;
  children: React.ReactNode;
  className?: string;
}

function PanelWrapper({
  title,
  icon,
  panelType,
  isFullScreen,
  onToggleFullScreen,
  children,
  className,
}: PanelWrapperProps) {
  const isThisFullScreen = isFullScreen && panelType !== null;

  return (
    <div
      className={clsx(
        'rounded-lg border border-gray-700 bg-gray-800/50',
        isThisFullScreen && 'fixed inset-4 z-50 overflow-auto',
        className
      )}
      data-testid={`panel-${panelType}`}
    >
      <div className="flex items-center justify-between border-b border-gray-700 px-4 py-3">
        <div className="flex items-center gap-2">
          {icon}
          <h2 className="font-semibold text-white">{title}</h2>
        </div>
        <button
          type="button"
          onClick={() => onToggleFullScreen(isThisFullScreen ? null : panelType)}
          className="rounded p-1.5 text-gray-400 hover:bg-gray-700 hover:text-white"
          aria-label={isThisFullScreen ? 'Exit full screen' : 'Enter full screen'}
        >
          {isThisFullScreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </button>
      </div>
      <div className={clsx('p-4', isThisFullScreen && 'h-[calc(100%-60px)] overflow-auto')}>
        {children}
      </div>
    </div>
  );
}

// ============================================================================
// Custom Hook for All Zones
// ============================================================================

/**
 * Hook to fetch zones from all cameras.
 */
function useAllZones() {
  const {
    cameras,
    isLoading: isCamerasLoading,
    error: camerasError,
    refetch: refetchCameras,
  } = useCamerasQuery();

  // For simplicity, we'll query zones for the first camera if available
  // In a real app, we'd want a backend endpoint for all zones
  const firstCameraId = cameras[0]?.id;

  const {
    zones,
    isLoading: isZonesLoading,
    error: zonesError,
    refetch: refetchZones,
  } = useZonesQuery(firstCameraId, { enabled: !!firstCameraId });

  // Aggregate zones from all cameras by querying each
  // For MVP, we use the first camera's zones; full implementation would need backend support
  const allZones = zones;

  const isLoading = isCamerasLoading || (!!firstCameraId && isZonesLoading);
  const error = camerasError ?? zonesError;

  const refetch = useCallback(async () => {
    await refetchCameras();
    if (firstCameraId) {
      await refetchZones();
    }
  }, [refetchCameras, refetchZones, firstCameraId]);

  return {
    zones: allZones,
    cameras,
    isLoading,
    isRefetching: isCamerasLoading || isZonesLoading,
    error,
    refetch,
  };
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZonesPage provides a comprehensive dashboard for zone intelligence.
 */
function ZonesPageComponent() {
  // State
  const [zoneTypeFilter, setZoneTypeFilter] = useState<ZoneType | 'all'>('all');
  const [timeRange, setTimeRange] = useState<ZoneTimeRange>('24h');
  const [fullScreenPanel, setFullScreenPanel] = useState<PanelType>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [activeTab, setActiveTab] = useState<ZoneAnalyticsTab>('overview');
  const [selectedLineZoneId, setSelectedLineZoneId] = useState<number | undefined>(undefined);
  const [trendsInterval, setTrendsInterval] = useState<'hour' | 'day'>('hour');
  const [selectedPolygonZoneId, setSelectedPolygonZoneId] = useState<number | undefined>(undefined);
  const [loiteringModalZone, setLoiteringModalZone] = useState<{ id: number; name: string } | null>(null);

  // Data fetching
  const { zones, cameras, isLoading, isRefetching, error, refetch } = useAllZones();

  // Line zone analytics
  const firstCameraId = cameras[0]?.id;
  const { lineZones, isLoading: isLineZonesLoading } = useLineZoneAnalytics({
    cameraId: firstCameraId,
    enabled: !!firstCameraId && activeTab === 'analytics',
  });

  const { data: crossingTrendsData, isLoading: isTrendsLoading } = useCrossingTrends({
    zoneId: selectedLineZoneId,
    interval: trendsInterval,
    enabled: selectedLineZoneId !== undefined && activeTab === 'analytics',
  });

  const resetCrossingCountsMutation = useResetCrossingCounts();

  // Polygon zone / dwell time analytics
  const { polygonZones, isLoading: isPolygonZonesLoading } = usePolygonZones({
    cameraId: firstCameraId,
    enabled: !!firstCameraId && activeTab === 'analytics',
  });

  const { statistics: dwellStatistics, isLoading: isDwellStatsLoading } = useDwellStatistics({
    zoneId: selectedPolygonZoneId,
    enabled: selectedPolygonZoneId !== undefined && activeTab === 'analytics',
  });

  // Active dwellers for selected polygon zone
  const { data: activeDwellersData, isLoading: isActiveDwellersLoading } = useActiveDwellers({
    zoneId: selectedPolygonZoneId,
    enabled: selectedPolygonZoneId !== undefined && activeTab === 'analytics',
    enablePolling: true,
  });

  // Filter zones by type
  const filteredZones = useMemo(() => {
    if (zoneTypeFilter === 'all') {
      return zones;
    }
    return zones.filter((zone) => zone.zone_type === zoneTypeFilter);
  }, [zones, zoneTypeFilter]);

  // Calculate health summary (simplified - in real app, would use actual health data)
  const healthSummary = useMemo(() => {
    const summary = { healthy: 0, warning: 0, critical: 0, unknown: 0 };
    filteredZones.forEach((zone) => {
      if (zone.enabled) {
        summary.healthy++;
      } else {
        summary.unknown++;
      }
    });
    return summary;
  }, [filteredZones]);

  // Get zone health status (simplified)
  const getZoneHealth = useCallback((zone: Zone): ZoneHealthStatus => {
    if (!zone.enabled) return 'unknown';
    return 'healthy';
  }, []);

  // Handle export
  const handleExport = useCallback(() => {
    setIsExporting(true);
    try {
      // Generate CSV content
      const headers = ['ID', 'Name', 'Type', 'Enabled', 'Priority', 'Color', 'Created At'];
      const rows = filteredZones.map((zone) => [
        zone.id,
        zone.name,
        zone.zone_type,
        zone.enabled ? 'Yes' : 'No',
        zone.priority.toString(),
        zone.color,
        zone.created_at,
      ]);

      const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');

      // Create and download file
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `zones-export-${new Date().toISOString().split('T')[0]}.csv`;
      link.click();
      URL.revokeObjectURL(link.href);
    } finally {
      setIsExporting(false);
    }
  }, [filteredZones]);

  // Handle refresh
  const handleRefresh = useCallback(() => {
    void refetch();
  }, [refetch]);

  // Handle line zone selection
  const handleLineZoneSelect = useCallback((zoneId: number) => {
    setSelectedLineZoneId((prev) => (prev === zoneId ? undefined : zoneId));
  }, []);

  // Handle reset crossing counts
  const handleResetCounts = useCallback(
    (zoneId: number) => {
      void resetCrossingCountsMutation.mutateAsync(zoneId);
    },
    [resetCrossingCountsMutation]
  );

  // Handle polygon zone selection
  const handlePolygonZoneSelect = useCallback((zoneId: number) => {
    setSelectedPolygonZoneId((prev) => (prev === zoneId ? undefined : zoneId));
  }, []);

  // Handle configure threshold - opens loitering config modal
  const handleConfigureThreshold = useCallback((zoneId: number) => {
    // Find the zone name for the modal
    const zone = polygonZones.find((z) => z.id === zoneId);
    if (zone) {
      setLoiteringModalZone({ id: zoneId, name: zone.name });
    }
  }, [polygonZones]);

  // Handle close loitering modal
  const handleCloseLoiteringModal = useCallback(() => {
    setLoiteringModalZone(null);
  }, []);

  // Loading state
  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center" data-testid="zones-loading">
        <LoadingSpinner />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-[#121212] p-6" data-testid="zones-page">
        <div className="mx-auto max-w-[1400px]">
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-6">
            <div className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="h-5 w-5" />
              <span className="font-medium">Failed to load zones</span>
            </div>
            <p className="mt-2 text-sm text-red-300">{error.message}</p>
            <Button
              variant="outline-primary"
              size="sm"
              onClick={handleRefresh}
              className="mt-4"
              leftIcon={<RefreshCw className="h-4 w-4" />}
            >
              Try Again
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Empty state
  if (zones.length === 0) {
    return (
      <div className="min-h-screen bg-[#121212] p-6" data-testid="zones-page">
        <div className="mx-auto max-w-[1400px]">
          <PageHeader
            zoneCount={0}
            healthSummary={{ healthy: 0, warning: 0, critical: 0, unknown: 0 }}
            isRefetching={isRefetching}
            onRefresh={handleRefresh}
          />
          <EmptyState
            icon={Shield}
            title="No zones configured"
            description="Create zones in the camera settings to monitor specific areas of your property."
            variant="muted"
          />
        </div>
      </div>
    );
  }

  const hoursLookback = TIME_RANGE_HOURS[timeRange];
  const isFullScreen = fullScreenPanel !== null;

  return (
    <div className="min-h-screen bg-[#121212] p-6" data-testid="zones-page">
      {/* Full-screen overlay backdrop */}
      {isFullScreen && (
        <div
          className="fixed inset-0 z-40 bg-black/80"
          onClick={() => setFullScreenPanel(null)}
          aria-hidden="true"
        />
      )}

      <div className="mx-auto max-w-[1400px]">
        {/* Header */}
        <PageHeader
          zoneCount={filteredZones.length}
          healthSummary={healthSummary}
          isRefetching={isRefetching}
          onRefresh={handleRefresh}
        />

        {/* Filter Bar */}
        <FilterBar
          zoneTypeFilter={zoneTypeFilter}
          onZoneTypeChange={setZoneTypeFilter}
          timeRange={timeRange}
          onTimeRangeChange={setTimeRange}
          onExport={handleExport}
          isExporting={isExporting}
        />

        {/* Tab Navigation */}
        <Tab.Group
          selectedIndex={ZONE_TABS.findIndex((tab) => tab.id === activeTab)}
          onChange={(index) => setActiveTab(ZONE_TABS[index].id)}
        >
          <Tab.List
            className="mb-6 flex rounded-lg border border-gray-700 p-1"
            data-testid="zone-tab-list"
          >
            {ZONE_TABS.map((tab) => {
              // Map icon string to component
              const IconComponent =
                tab.icon === 'LayoutGrid'
                  ? LayoutGrid
                  : tab.icon === 'BarChart3'
                    ? BarChart3
                    : GitCompare;
              return (
                <Tab
                  key={tab.id}
                  data-testid={`zone-tab-${tab.id}`}
                  className={({ selected }) =>
                    clsx(
                      'flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors',
                      'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-[#121212]',
                      selected
                        ? 'bg-primary text-white'
                        : 'text-gray-400 hover:bg-gray-700 hover:text-gray-200'
                    )
                  }
                >
                  <IconComponent className="h-4 w-4" aria-hidden="true" />
                  {tab.label}
                </Tab>
              );
            })}
          </Tab.List>

          <Tab.Panels>
            {/* Overview Tab Panel */}
            <Tab.Panel data-testid="zone-panel-overview">
              {/* Dashboard Grid - Responsive Layout */}
              <div className={clsx('grid gap-6', !isFullScreen && 'lg:grid-cols-2')}>
                {/* Zone Overview Grid */}
                {(fullScreenPanel === null || fullScreenPanel === 'overview') && (
                  <PanelWrapper
                    title="Zone Overview"
                    icon={<Grid className="h-5 w-5 text-primary" />}
                    panelType="overview"
                    isFullScreen={fullScreenPanel === 'overview'}
                    onToggleFullScreen={setFullScreenPanel}
                    className="lg:col-span-2"
                  >
                    {filteredZones.length === 0 ? (
                      <p className="py-8 text-center text-gray-400">
                        No zones match the selected filter.
                      </p>
                    ) : (
                      <div
                        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
                        data-testid="zone-grid"
                      >
                        {filteredZones.map((zone) => (
                          <ZoneStatusCard
                            key={zone.id}
                            zone={zone}
                            healthStatus={getZoneHealth(zone)}
                          />
                        ))}
                      </div>
                    )}
                  </PanelWrapper>
                )}

                {/* Trust Matrix */}
                {(fullScreenPanel === null || fullScreenPanel === 'trust') && (
                  <PanelWrapper
                    title="Trust Matrix"
                    icon={<Shield className="h-5 w-5 text-blue-400" />}
                    panelType="trust"
                    isFullScreen={fullScreenPanel === 'trust'}
                    onToggleFullScreen={setFullScreenPanel}
                  >
                    <ZoneTrustMatrix zones={filteredZones} className="min-h-[300px]" />
                  </PanelWrapper>
                )}

                {/* Alert Feed */}
                {(fullScreenPanel === null || fullScreenPanel === 'alerts') && (
                  <PanelWrapper
                    title="Zone Anomalies"
                    icon={<AlertTriangle className="h-5 w-5 text-yellow-400" />}
                    panelType="alerts"
                    isFullScreen={fullScreenPanel === 'alerts'}
                    onToggleFullScreen={setFullScreenPanel}
                  >
                    <ZoneAnomalyFeed
                      hoursLookback={hoursLookback}
                      maxHeight={fullScreenPanel === 'alerts' ? 'calc(100vh - 200px)' : '400px'}
                      enableRealtime
                    />
                  </PanelWrapper>
                )}
              </div>
            </Tab.Panel>

            {/* Analytics Tab Panel */}
            <Tab.Panel data-testid="zone-panel-analytics">
              <div className="space-y-6">
                {/* Interval Selector */}
                <div className="flex items-center justify-between rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5 text-[#76B900]" />
                    <h3 className="font-medium text-white">Line Zone Analytics</h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-400">Interval:</span>
                    <div
                      className="flex rounded-lg border border-gray-700 p-0.5"
                      role="group"
                      aria-label="Trends interval selection"
                    >
                      <button
                        type="button"
                        onClick={() => setTrendsInterval('hour')}
                        aria-pressed={trendsInterval === 'hour'}
                        className={clsx(
                          'rounded-md px-3 py-1.5 text-sm font-medium transition-all',
                          trendsInterval === 'hour'
                            ? 'bg-primary text-white'
                            : 'text-gray-400 hover:bg-gray-700 hover:text-gray-200'
                        )}
                        data-testid="interval-hour-button"
                      >
                        Hourly
                      </button>
                      <button
                        type="button"
                        onClick={() => setTrendsInterval('day')}
                        aria-pressed={trendsInterval === 'day'}
                        className={clsx(
                          'rounded-md px-3 py-1.5 text-sm font-medium transition-all',
                          trendsInterval === 'day'
                            ? 'bg-primary text-white'
                            : 'text-gray-400 hover:bg-gray-700 hover:text-gray-200'
                        )}
                        data-testid="interval-day-button"
                      >
                        Daily
                      </button>
                    </div>
                  </div>
                </div>

                {/* Line Zone Cards Grid */}
                {isLineZonesLoading ? (
                  <div className="flex min-h-[200px] items-center justify-center">
                    <LoadingSpinner />
                  </div>
                ) : lineZones.length === 0 ? (
                  <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6">
                    <EmptyState
                      icon={BarChart3}
                      title="No line zones configured"
                      description="Create line zones in the camera settings to track crossings and flow patterns."
                      variant="muted"
                    />
                  </div>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {lineZones.map((zone) => (
                      <div
                        key={zone.id}
                        onClick={() => handleLineZoneSelect(zone.id)}
                        className={clsx(
                          'cursor-pointer transition-all',
                          selectedLineZoneId === zone.id && 'ring-2 ring-[#76B900] ring-offset-2 ring-offset-[#121212] rounded-lg'
                        )}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            handleLineZoneSelect(zone.id);
                          }
                        }}
                        aria-pressed={selectedLineZoneId === zone.id}
                        data-testid={`line-zone-selector-${zone.id}`}
                      >
                        <LineZoneCrossingCard
                          zone={zone}
                          onReset={handleResetCounts}
                          isResetting={resetCrossingCountsMutation.isPending}
                        />
                      </div>
                    ))}
                  </div>
                )}

                {/* Crossing Trends Chart */}
                {selectedLineZoneId !== undefined && (
                  <CrossingTrendsChart
                    data={crossingTrendsData}
                    isLoading={isTrendsLoading}
                  />
                )}

                {/* Help text when no zone selected */}
                {lineZones.length > 0 && selectedLineZoneId === undefined && (
                  <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6 text-center">
                    <p className="text-sm text-gray-400">
                      Select a line zone above to view crossing trends over time.
                    </p>
                  </div>
                )}

                {/* Polygon Zone Section Divider */}
                <div className="flex items-center gap-4 pt-4">
                  <div className="h-px flex-1 bg-gray-700" />
                  <span className="text-sm text-gray-500">Polygon Zones</span>
                  <div className="h-px flex-1 bg-gray-700" />
                </div>

                {/* Polygon Zone Header */}
                <div className="flex items-center justify-between rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                  <div className="flex items-center gap-2">
                    <MapPin className="h-5 w-5 text-blue-400" />
                    <h3 className="font-medium text-white">Dwell Time Analytics</h3>
                  </div>
                  <span className="text-sm text-gray-400">
                    {polygonZones.length} polygon zone{polygonZones.length !== 1 ? 's' : ''}
                  </span>
                </div>

                {/* Polygon Zone Cards Grid */}
                {isPolygonZonesLoading ? (
                  <div className="flex min-h-[200px] items-center justify-center" data-testid="polygon-zones-loading">
                    <LoadingSpinner />
                  </div>
                ) : polygonZones.length === 0 ? (
                  <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6" data-testid="polygon-zones-empty">
                    <EmptyState
                      icon={MapPin}
                      title="No polygon zones configured"
                      description="Create polygon zones in the camera settings to track dwell times and loitering."
                      variant="muted"
                    />
                  </div>
                ) : (
                  <div
                    className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
                    data-testid="polygon-zones-grid"
                  >
                    {polygonZones.map((zone) => (
                      <div
                        key={zone.id}
                        onClick={() => handlePolygonZoneSelect(zone.id)}
                        className={clsx(
                          'cursor-pointer transition-all',
                          selectedPolygonZoneId === zone.id && 'ring-2 ring-blue-400 ring-offset-2 ring-offset-[#121212] rounded-lg'
                        )}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            handlePolygonZoneSelect(zone.id);
                          }
                        }}
                        aria-pressed={selectedPolygonZoneId === zone.id}
                        data-testid={`polygon-zone-selector-${zone.id}`}
                      >
                        <DwellStatisticsCard
                          zone={zone}
                          statistics={selectedPolygonZoneId === zone.id ? dwellStatistics : undefined}
                          isLoading={selectedPolygonZoneId === zone.id && isDwellStatsLoading}
                          onConfigure={handleConfigureThreshold}
                        />
                      </div>
                    ))}
                  </div>
                )}

                {/* Active Dwellers Panel - shown when a polygon zone is selected */}
                {selectedPolygonZoneId !== undefined && (
                  <ActiveDwellersPanel
                    dwellers={activeDwellersData?.dwellers ?? []}
                    isLoading={isActiveDwellersLoading}
                    isConnected={false}
                    className="mt-4"
                    data-testid="active-dwellers-panel-container"
                  />
                )}

                {/* Help text when no polygon zone selected */}
                {polygonZones.length > 0 && selectedPolygonZoneId === undefined && (
                  <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6 text-center" data-testid="polygon-zone-help-text">
                    <p className="text-sm text-gray-400">
                      Select a polygon zone above to view dwell time statistics.
                    </p>
                  </div>
                )}

                {/* Entity Distribution Section (NEM-4937) */}
                <div className="flex items-center gap-4 pt-4">
                  <div className="h-px flex-1 bg-gray-700" />
                  <span className="text-sm text-gray-500">Entity Distribution</span>
                  <div className="h-px flex-1 bg-gray-700" />
                </div>

                <ZoneEntityDistributionPanel
                  cameraId={firstCameraId}
                  data-testid="entity-distribution-panel"
                />
              </div>
            </Tab.Panel>

            {/* Comparison Tab Panel */}
            <Tab.Panel data-testid="zone-panel-comparison">
              <ComparisonTab
                zones={filteredZones}
                isLoadingZones={isLoading}
              />
            </Tab.Panel>
          </Tab.Panels>
        </Tab.Group>
      </div>

      {/* Loitering Configuration Modal */}
      {loiteringModalZone && (
        <LoiteringConfigModal
          isOpen={true}
          onClose={handleCloseLoiteringModal}
          zoneId={loiteringModalZone.id}
          zoneName={loiteringModalZone.name}
        />
      )}
    </div>
  );
}

/**
 * Memoized ZonesPage for performance.
 */
export const ZonesPage = memo(ZonesPageComponent);

export default ZonesPage;
