import { Settings2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import DashboardConfigModal from './DashboardConfigModal';
import {
  loadDashboardConfig,
  saveDashboardConfig,
  type DashboardConfig,
  type WidgetId,
} from '../../stores/dashboardConfig';

import type { ActivityEvent } from './ActivityFeed';
import type { CameraStatus } from './CameraGrid';
import type { StatsRowProps } from './StatsRow';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for individual widget components.
 * Each widget receives its specific props through the layout.
 */
export interface WidgetProps {
  /** Props for StatsRow widget */
  statsRow?: StatsRowProps;
  /** Props for CameraGrid widget */
  cameraGrid?: {
    cameras: CameraStatus[];
    onCameraClick?: (cameraId: string) => void;
  };
  /** Props for ActivityFeed widget */
  activityFeed?: {
    events: ActivityEvent[];
    maxItems?: number;
    onEventClick?: (eventId: string) => void;
    className?: string;
  };
  /** Props for GpuStats widget */
  gpuStats?: {
    gpuName?: string | null;
    utilization?: number | null;
    memoryUsed?: number | null;
    memoryTotal?: number | null;
    temperature?: number | null;
    powerUsage?: number | null;
    inferenceFps?: number | null;
  };
  /** Props for PipelineTelemetry widget */
  pipelineTelemetry?: {
    pollingInterval?: number;
    queueWarningThreshold?: number;
    latencyWarningThreshold?: number;
  };
  /** Props for PipelineQueues widget */
  pipelineQueues?: {
    detectionQueue: number;
    analysisQueue: number;
    warningThreshold?: number;
    className?: string;
  };
}

export interface DashboardLayoutProps {
  /** Widget-specific props */
  widgetProps: WidgetProps;
  /** Render function for StatsRow */
  renderStatsRow: (props: StatsRowProps) => React.ReactNode;
  /** Render function for CameraGrid */
  renderCameraGrid: (props: WidgetProps['cameraGrid']) => React.ReactNode;
  /** Render function for ActivityFeed */
  renderActivityFeed: (props: WidgetProps['activityFeed']) => React.ReactNode;
  /** Render function for GpuStats (optional) */
  renderGpuStats?: (props: WidgetProps['gpuStats']) => React.ReactNode;
  /** Render function for PipelineTelemetry (optional) */
  renderPipelineTelemetry?: (props: WidgetProps['pipelineTelemetry']) => React.ReactNode;
  /** Render function for PipelineQueues (optional) */
  renderPipelineQueues?: (props: WidgetProps['pipelineQueues']) => React.ReactNode;
  /** Whether loading state is active */
  isLoading?: boolean;
  /** Render function for loading skeleton */
  renderLoadingSkeleton?: () => React.ReactNode;
  /** Additional CSS classes for the layout */
  className?: string;
}

// ============================================================================
// Component
// ============================================================================

/**
 * DashboardLayout manages the rendering of dashboard widgets based on user configuration.
 *
 * Features:
 * - Reads and saves widget configuration from localStorage
 * - Renders visible widgets in user-defined order
 * - Provides configuration modal for customization
 * - Uses render props pattern for flexible widget rendering
 *
 * @example
 * ```tsx
 * <DashboardLayout
 *   widgetProps={{
 *     statsRow: { activeCameras: 4, eventsToday: 10, ... },
 *     cameraGrid: { cameras: cameraList, onCameraClick: handleClick },
 *   }}
 *   renderStatsRow={(props) => <StatsRow {...props} />}
 *   renderCameraGrid={(props) => <CameraGrid {...props} />}
 *   renderActivityFeed={(props) => <ActivityFeed {...props} />}
 * />
 * ```
 */
export default function DashboardLayout({
  widgetProps,
  renderStatsRow,
  renderCameraGrid,
  renderActivityFeed,
  renderGpuStats,
  renderPipelineTelemetry,
  renderPipelineQueues,
  isLoading = false,
  renderLoadingSkeleton,
  className = '',
}: DashboardLayoutProps) {
  // Dashboard configuration state
  const [config, setConfig] = useState<DashboardConfig>(() => loadDashboardConfig());
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);

  // Persist configuration changes
  useEffect(() => {
    saveDashboardConfig(config);
  }, [config]);

  // Handle configuration changes from modal
  const handleConfigChange = useCallback((newConfig: DashboardConfig) => {
    setConfig(newConfig);
  }, []);

  // Open configuration modal
  const openConfigModal = useCallback(() => {
    setIsConfigModalOpen(true);
  }, []);

  // Close configuration modal
  const closeConfigModal = useCallback(() => {
    setIsConfigModalOpen(false);
  }, []);

  // Render a widget by its ID
  const renderWidget = useCallback(
    (widgetId: WidgetId): React.ReactNode => {
      switch (widgetId) {
        case 'stats-row':
          if (widgetProps.statsRow) {
            return (
              <div key={widgetId} className="mb-6 md:mb-8" data-testid="widget-stats-row">
                {renderStatsRow(widgetProps.statsRow)}
              </div>
            );
          }
          return null;

        case 'camera-grid':
          if (widgetProps.cameraGrid) {
            return (
              <div key={widgetId} data-testid="widget-camera-grid">
                <h2 className="text-section-title mb-3 md:mb-4">Camera Status</h2>
                {renderCameraGrid(widgetProps.cameraGrid)}
              </div>
            );
          }
          return null;

        case 'activity-feed':
          if (widgetProps.activityFeed) {
            return (
              <div key={widgetId} data-testid="widget-activity-feed">
                <h2 className="text-section-title mb-3 md:mb-4">Live Activity</h2>
                {renderActivityFeed(widgetProps.activityFeed)}
              </div>
            );
          }
          return null;

        case 'gpu-stats':
          if (renderGpuStats && widgetProps.gpuStats) {
            return (
              <div key={widgetId} data-testid="widget-gpu-stats">
                {renderGpuStats(widgetProps.gpuStats)}
              </div>
            );
          }
          return null;

        case 'pipeline-telemetry':
          if (renderPipelineTelemetry && widgetProps.pipelineTelemetry) {
            return (
              <div key={widgetId} data-testid="widget-pipeline-telemetry">
                {renderPipelineTelemetry(widgetProps.pipelineTelemetry)}
              </div>
            );
          }
          return null;

        case 'pipeline-queues':
          if (renderPipelineQueues && widgetProps.pipelineQueues) {
            return (
              <div key={widgetId} data-testid="widget-pipeline-queues">
                {renderPipelineQueues(widgetProps.pipelineQueues)}
              </div>
            );
          }
          return null;

        default:
          return null;
      }
    },
    [
      widgetProps,
      renderStatsRow,
      renderCameraGrid,
      renderActivityFeed,
      renderGpuStats,
      renderPipelineTelemetry,
      renderPipelineQueues,
    ]
  );

  // Get visible widgets in order
  const visibleWidgets = config.widgets.filter((w) => w.visible);

  // Determine layout structure based on visible widgets
  // If camera-grid and activity-feed are both visible, use 2-column layout
  const hasCameraGrid = visibleWidgets.some((w) => w.id === 'camera-grid');
  const hasActivityFeed = visibleWidgets.some((w) => w.id === 'activity-feed');
  const useTwoColumnLayout = hasCameraGrid && hasActivityFeed;

  // Separate widgets for layout
  const topWidgets = visibleWidgets.filter(
    (w) => w.id !== 'camera-grid' && w.id !== 'activity-feed'
  );
  const mainWidgets = visibleWidgets.filter(
    (w) => w.id === 'camera-grid' || w.id === 'activity-feed'
  );

  // Show loading skeleton if loading
  if (isLoading && renderLoadingSkeleton) {
    return (
      <div className={`min-h-screen bg-[#121212] p-4 md:p-8 ${className}`}>
        <div className="mx-auto max-w-[1920px]">{renderLoadingSkeleton()}</div>
      </div>
    );
  }

  return (
    <>
      <div
        className={`min-h-screen bg-[#121212] p-4 md:p-8 ${className}`}
        data-testid="dashboard-layout"
      >
        <div className="mx-auto max-w-[1920px]">
          {/* Header with Configure Button */}
          <div className="mb-6 flex items-center justify-between md:mb-8">
            <div>
              <h1 className="text-page-title">Security Dashboard</h1>
              <p className="text-body-sm mt-1 sm:mt-2">
                Real-time AI-powered home security monitoring
              </p>
            </div>
            <button
              onClick={openConfigModal}
              className="flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800/50 px-3 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-[#76B900] hover:bg-gray-800 hover:text-white"
              aria-label="Configure dashboard"
              data-testid="configure-dashboard-button"
            >
              <Settings2 className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Configure</span>
            </button>
          </div>

          {/* Top Widgets (full width) */}
          {topWidgets
            .filter(
              (w) =>
                w.id !== 'gpu-stats' && w.id !== 'pipeline-telemetry' && w.id !== 'pipeline-queues'
            )
            .map((widget) => renderWidget(widget.id))}

          {/* Main Content Area */}
          {mainWidgets.length > 0 && (
            <div
              className={
                useTwoColumnLayout
                  ? 'grid grid-cols-1 gap-6 lg:grid-cols-[2fr,1fr] xl:grid-cols-[2.5fr,1fr]'
                  : 'space-y-6'
              }
              data-testid="main-content-area"
            >
              {/* Camera Grid Column */}
              {hasCameraGrid && renderWidget('camera-grid')}

              {/* Activity Feed Column */}
              {hasActivityFeed && renderWidget('activity-feed')}
            </div>
          )}

          {/* System Widgets (GPU Stats, Pipeline Telemetry, etc.) */}
          {topWidgets.some(
            (w) =>
              w.id === 'gpu-stats' || w.id === 'pipeline-telemetry' || w.id === 'pipeline-queues'
          ) && (
            <div
              className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3"
              data-testid="system-widgets-area"
            >
              {topWidgets
                .filter(
                  (w) =>
                    w.id === 'gpu-stats' ||
                    w.id === 'pipeline-telemetry' ||
                    w.id === 'pipeline-queues'
                )
                .map((widget) => renderWidget(widget.id))}
            </div>
          )}

          {/* Empty State */}
          {visibleWidgets.length === 0 && (
            <div
              className="flex flex-col items-center justify-center rounded-lg border border-dashed border-gray-700 p-12 text-center"
              data-testid="empty-dashboard"
            >
              <Settings2 className="mb-4 h-12 w-12 text-gray-600" />
              <h3 className="mb-2 text-lg font-medium text-gray-400">No Widgets Visible</h3>
              <p className="mb-4 text-sm text-gray-500">
                Click the Configure button to add widgets to your dashboard.
              </p>
              <button
                onClick={openConfigModal}
                className="rounded-lg bg-[#76B900] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#8BC727]"
              >
                Configure Dashboard
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Configuration Modal */}
      <DashboardConfigModal
        isOpen={isConfigModalOpen}
        onClose={closeConfigModal}
        config={config}
        onConfigChange={handleConfigChange}
      />
    </>
  );
}
