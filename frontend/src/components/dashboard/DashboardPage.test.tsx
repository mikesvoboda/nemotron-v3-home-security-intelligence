import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';

import DashboardPage from './DashboardPage';
import * as useAIMetricsHook from '../../hooks/useAIMetrics';
import * as useEventStreamHook from '../../hooks/useEventStream';
import * as useSummariesHook from '../../hooks/useSummaries';
import * as useSystemStatusHook from '../../hooks/useSystemStatus';
import * as useThreatDetectionHook from '../../hooks/useThreatDetection';
import * as api from '../../services/api';
import { renderWithProviders, screen, waitFor } from '../../test-utils/renderWithProviders';

// Mock useNavigate from react-router-dom
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock the API and hooks
vi.mock('../../services/api', () => ({
  fetchCameras: vi.fn(),
  fetchEvents: vi.fn(),
  fetchEventStats: vi.fn(),
  fetchSummaryDetail: vi.fn(),
  getCameraSnapshotUrl: vi.fn(),
  buildWebSocketOptions: vi.fn(() => ({ url: 'ws://localhost:8000/ws/events', protocols: [] })),
}));
vi.mock('../../hooks/useEventStream', () => ({
  useEventStream: vi.fn(),
}));
vi.mock('../../hooks/useSummaries', () => ({
  useSummaries: vi.fn(),
}));
vi.mock('../../hooks/useSystemStatus', () => ({
  useSystemStatus: vi.fn(),
}));
vi.mock('../../hooks/useAIMetrics', () => ({
  useAIMetrics: vi.fn(),
}));
vi.mock('../../hooks/useSceneChangeEvents', () => ({
  useSceneChangeEvents: vi.fn(() => ({
    cameraActivity: {},
    activeCameraIds: [],
    recentEvents: [],
    isConnected: true,
    totalEventCount: 0,
    hasRecentActivity: () => false,
    getActivityState: () => undefined,
    clearActivity: vi.fn(),
    clearAllActivity: vi.fn(),
  })),
}));

// Mock useThreatDetection hook (NEM-5024)
vi.mock('../../hooks/useThreatDetection', () => ({
  useThreatDetection: vi.fn(),
}));

// Mock child components
vi.mock('./StatsRow', () => ({
  default: ({
    activeCameras,
    eventsToday,
    currentRiskScore,
    systemStatus,
    riskHistory,
  }: {
    activeCameras: number;
    eventsToday: number;
    currentRiskScore: number;
    systemStatus: string;
    riskHistory?: number[];
  }) => (
    <div
      data-testid="stats-row"
      data-active-cameras={activeCameras}
      data-events-today={eventsToday}
      data-risk-score={currentRiskScore}
      data-system-status={systemStatus}
      data-risk-history={riskHistory?.join(',')}
    >
      Stats Row
    </div>
  ),
}));

vi.mock('./CameraGrid', () => ({
  default: ({
    cameras,
    onCameraClick,
  }: {
    cameras: Array<{ id: string; name: string; thumbnail_url?: string }>;
    onCameraClick?: (cameraId: string) => void;
  }) => (
    <div
      data-testid="camera-grid"
      data-camera-count={cameras.length}
      data-has-click-handler={onCameraClick ? 'true' : 'false'}
    >
      {cameras.map((camera) => (
        <button
          key={camera.id}
          data-thumbnail-url={camera.thumbnail_url}
          onClick={() => onCameraClick?.(camera.id)}
        >
          {camera.name}
        </button>
      ))}
    </div>
  ),
}));

vi.mock('./ActivityFeed', () => ({
  default: ({
    events,
    maxItems,
    onEventClick,
  }: {
    events: Array<{ id: string; camera_name: string }>;
    maxItems?: number;
    onEventClick?: (eventId: string) => void;
  }) => (
    <div
      data-testid="activity-feed"
      data-event-count={events.length}
      data-max-items={maxItems}
      data-has-click-handler={onEventClick ? 'true' : 'false'}
    >
      {events.slice(0, maxItems || 10).map((event) => (
        <button key={event.id} onClick={() => onEventClick?.(event.id)}>
          {event.camera_name}
        </button>
      ))}
    </div>
  ),
}));

// Mock DashboardLayout to pass through to child components for existing test compatibility
vi.mock('./DashboardLayout', () => ({
  default: ({
    widgetProps,
    renderStatsRow,
    renderCameraGrid,
    renderActivityFeed,
    isLoading,
    renderLoadingSkeleton,
  }: {
    widgetProps: {
      statsRow?: {
        activeCameras: number;
        eventsToday: number;
        currentRiskScore: number;
        systemStatus: string;
        riskHistory?: number[];
      };
      cameraGrid?: {
        cameras: Array<{ id: string; name: string; thumbnail_url?: string }>;
        onCameraClick?: (cameraId: string) => void;
      };
      activityFeed?: {
        events: Array<{ id: string; camera_name: string }>;
        maxItems?: number;
        onEventClick?: (eventId: string) => void;
        className?: string;
      };
    };
    renderStatsRow: (props: unknown) => React.ReactNode;
    renderCameraGrid: (props: unknown) => React.ReactNode;
    renderActivityFeed: (props: unknown) => React.ReactNode;
    isLoading?: boolean;
    renderLoadingSkeleton?: () => React.ReactNode;
  }) => {
    if (isLoading && renderLoadingSkeleton) {
      return (
        <div className="min-h-screen bg-[#121212] p-4 md:p-8">
          <div className="mx-auto max-w-[1920px]">{renderLoadingSkeleton()}</div>
        </div>
      );
    }

    return (
      <div data-testid="dashboard-layout" className="min-h-screen bg-[#121212] p-4 md:p-8">
        <div className="mx-auto max-w-[1920px]">
          {/* Header */}
          <div className="mb-6 md:mb-8">
            <h1>Security Dashboard</h1>
            <p>Real-time AI-powered home security monitoring</p>
          </div>

          {/* Stats Row */}
          {widgetProps.statsRow && (
            <div className="mb-6 md:mb-8">{renderStatsRow(widgetProps.statsRow)}</div>
          )}

          {/* 2-Column Layout */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr,1fr] xl:grid-cols-[2.5fr,1fr]">
            {/* Camera Grid */}
            {widgetProps.cameraGrid && (
              <div>
                <h2>Camera Status</h2>
                {renderCameraGrid(widgetProps.cameraGrid)}
              </div>
            )}

            {/* Activity Feed */}
            {widgetProps.activityFeed && (
              <div>
                <h2>Live Activity</h2>
                {renderActivityFeed(widgetProps.activityFeed)}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  },
}));

// Mock GpuStats, PipelineTelemetry, and PipelineQueues (not rendered by default)
vi.mock('./GpuStats', () => ({
  default: () => <div data-testid="gpu-stats">GPU Stats</div>,
}));

vi.mock('./PipelineTelemetry', () => ({
  default: () => <div data-testid="pipeline-telemetry">Pipeline Telemetry</div>,
}));

vi.mock('./PipelineQueues', () => ({
  default: () => <div data-testid="pipeline-queues">Pipeline Queues</div>,
}));

vi.mock('./SummaryCards', () => ({
  SummaryCards: ({
    hourly,
    daily,
    isLoading,
    onViewFull,
  }: {
    hourly: { id: number; content: string; eventCount: number } | null;
    daily: { id: number; content: string; eventCount: number } | null;
    isLoading?: boolean;
    onViewFull?: (summary: { id: number; content: string; eventCount: number }) => void;
  }) => (
    <div
      data-testid="summary-cards"
      data-is-loading={isLoading ? 'true' : 'false'}
      data-has-hourly={hourly ? 'true' : 'false'}
      data-has-daily={daily ? 'true' : 'false'}
      data-hourly-content={hourly?.content ?? ''}
      data-daily-content={daily?.content ?? ''}
      data-has-view-full={onViewFull ? 'true' : 'false'}
    >
      Summary Cards
      {onViewFull && hourly && (
        <button
          data-testid="view-full-hourly"
          onClick={() => onViewFull(hourly)}
        >
          View Full Hourly
        </button>
      )}
      {onViewFull && daily && (
        <button
          data-testid="view-full-daily"
          onClick={() => onViewFull(daily)}
        >
          View Full Daily
        </button>
      )}
    </div>
  ),
}));

vi.mock('./ExpandableDetailPanel', () => ({
  ExpandableDetailPanel: ({
    detail,
    isOpen,
    onClose,
  }: {
    detail: { id: number; summaryType: string; content: string; eventCount: number };
    isOpen: boolean;
    onClose: () => void;
  }) =>
    isOpen ? (
      <div
        data-testid="expandable-detail-panel"
        data-detail-id={detail.id}
        data-summary-type={detail.summaryType}
        data-event-count={detail.eventCount}
      >
        <div data-testid="detail-narrative">{detail.content}</div>
        <button data-testid="detail-panel-close" onClick={onClose}>
          Close
        </button>
      </div>
    ) : null,
}));

vi.mock('../ai-performance/AIPerformanceSummaryRow', () => ({
  default: ({
    rtdetr,
    nemotron,
    detectionQueueDepth,
    analysisQueueDepth,
    totalDetections,
    totalEvents,
    totalErrors,
  }: {
    rtdetr: { name: string; status: string };
    nemotron: { name: string; status: string };
    detectionLatency?: unknown;
    analysisLatency?: unknown;
    detectionQueueDepth: number;
    analysisQueueDepth: number;
    totalDetections: number;
    totalEvents: number;
    totalErrors: number;
    throughputPerMinute?: number;
    sectionRefs?: unknown;
    onIndicatorClick?: unknown;
    className?: string;
  }) => (
    <div
      data-testid="ai-summary-row"
      data-rtdetr-status={rtdetr.status}
      data-nemotron-status={nemotron.status}
      data-detection-queue={detectionQueueDepth}
      data-analysis-queue={analysisQueueDepth}
      data-total-detections={totalDetections}
      data-total-events={totalEvents}
      data-total-errors={totalErrors}
    >
      AI Performance Summary Row
    </div>
  ),
}));

describe('DashboardPage', () => {
  const mockCameras = [
    {
      id: 'cam1',
      name: 'Front Door',
      folder_path: '/export/foscam/front',
      status: 'online',
      created_at: '2025-01-01T00:00:00Z',
      last_seen_at: '2025-01-01T12:00:00Z',
    },
    {
      id: 'cam2',
      name: 'Back Yard',
      folder_path: '/export/foscam/back',
      status: 'offline',
      created_at: '2025-01-01T00:00:00Z',
      last_seen_at: null,
    },
  ];

  // Get today's date for WebSocket event timestamps
  const today = new Date();
  const todayISOString = today.toISOString().slice(0, 10); // YYYY-MM-DD

  // WebSocket events (real-time) - use today's date so they count as "events today"
  const mockWsEvents = [
    {
      id: 'event1',
      camera_id: 'cam1',
      camera_name: 'Front Door',
      risk_score: 75,
      risk_level: 'high' as const,
      summary: 'Person detected at front door',
      timestamp: `${todayISOString}T12:00:00Z`,
    },
    {
      id: 'event2',
      camera_id: 'cam1',
      camera_name: 'Front Door',
      risk_score: 50,
      risk_level: 'medium' as const,
      summary: 'Motion detected',
      timestamp: `${todayISOString}T11:55:00Z`,
    },
  ];

  // Initial events from REST API
  const mockInitialEvents = [
    {
      id: 3,
      camera_id: 'cam1',
      started_at: '2025-01-01T11:50:00Z',
      ended_at: '2025-01-01T11:52:00Z',
      risk_score: 40,
      risk_level: 'medium',
      summary: 'Vehicle detected in driveway',
      reviewed: false,
      notes: null,
      detection_count: 3,
    },
    {
      id: 4,
      camera_id: 'cam2',
      started_at: '2025-01-01T11:45:00Z',
      ended_at: '2025-01-01T11:47:00Z',
      risk_score: 20,
      risk_level: 'low',
      summary: 'Animal detected',
      reviewed: true,
      notes: null,
      detection_count: 2,
    },
  ];

  const mockEventListResponse = {
    items: mockInitialEvents,
    pagination: {
      total: 2,
      limit: 50,
      offset: 0,
      has_more: false,
    },
  };

  const mockEventStats = {
    total_events: 10,
    events_by_risk_level: {
      critical: 1,
      high: 2,
      medium: 4,
      low: 3,
    },
    events_by_camera: [
      { camera_id: 'cam1', camera_name: 'Front Door', event_count: 7 },
      { camera_id: 'cam2', camera_name: 'Back Yard', event_count: 3 },
    ],
  };

  const mockSystemStatus = {
    health: 'healthy' as const,
    gpu_utilization: 75,
    active_cameras: 2,
    last_update: '2025-01-01T12:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockClear();

    // Setup default mock implementations
    (api.fetchCameras as Mock).mockResolvedValue(mockCameras);
    (api.fetchEvents as Mock).mockResolvedValue(mockEventListResponse);
    (api.fetchEventStats as Mock).mockResolvedValue(mockEventStats);

    // Mock getCameraSnapshotUrl to return the expected URL pattern
    (api.getCameraSnapshotUrl as Mock).mockImplementation(
      (cameraId: string) => `/api/cameras/${cameraId}/snapshot`
    );

    (useEventStreamHook.useEventStream as Mock).mockReturnValue({
      events: mockWsEvents,
      isConnected: true,
      latestEvent: mockWsEvents[0],
      clearEvents: vi.fn(),
    });

    (useSystemStatusHook.useSystemStatus as Mock).mockReturnValue({
      status: mockSystemStatus,
      isConnected: true,
    });

    (useSummariesHook.useSummaries as Mock).mockReturnValue({
      hourly: null,
      daily: null,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    (useAIMetricsHook.useAIMetrics as Mock).mockReturnValue({
      data: {
        rtdetr: { name: 'RT-DETRv2', status: 'healthy' },
        nemotron: { name: 'Nemotron', status: 'healthy' },
        detectionLatency: { avg_ms: 25, p50_ms: 20, p95_ms: 45, p99_ms: 60, sample_count: 100 },
        analysisLatency: {
          avg_ms: 3500,
          p50_ms: 3000,
          p95_ms: 5500,
          p99_ms: 7000,
          sample_count: 50,
        },
        pipelineLatency: null,
        totalDetections: 150,
        totalEvents: 45,
        detectionQueueDepth: 2,
        analysisQueueDepth: 1,
        pipelineErrors: {},
        queueOverflows: {},
        dlqItems: {},
        detectionsByClass: { person: 100, vehicle: 40, animal: 10 },
        lastUpdated: '2025-01-01T12:00:00Z',
      },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    // Default: no active threats (NEM-5024)
    (useThreatDetectionHook.useThreatDetection as Mock).mockReturnValue({
      threatSummary: {
        hasActiveThreats: false,
        totalThreats: 0,
        maxSeverity: null,
        threats: [],
        criticalCount: 0,
        highCount: 0,
        mediumCount: 0,
        latestThreat: null,
        threatTypes: [],
        affectedCameras: [],
      },
      isLoading: false,
      dismissedIds: new Set(),
      addThreat: vi.fn(),
      removeThreat: vi.fn(),
      clearThreats: vi.fn(),
      dismissThreat: vi.fn(),
      clearDismissed: vi.fn(),
    });
  });

  describe('Loading State', () => {
    it('renders loading skeletons while fetching initial data', () => {
      // Make API call hang
      (api.fetchCameras as Mock).mockImplementation(() => new Promise(() => {}));

      renderWithProviders(<DashboardPage />);

      // Check for stats card skeletons and camera card skeletons
      expect(screen.getAllByTestId('stats-card-skeleton').length).toBeGreaterThan(0);
      expect(screen.getAllByTestId('camera-card-skeleton').length).toBeGreaterThan(0);
    });

    it('loading state has correct background color', () => {
      (api.fetchCameras as Mock).mockImplementation(() => new Promise(() => {}));

      const { container } = renderWithProviders(<DashboardPage />);
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass('bg-[#121212]');
    });
  });

  describe('Error State', () => {
    it('renders error message when API fails', async () => {
      const errorMessage = 'Failed to fetch cameras';
      (api.fetchCameras as Mock).mockRejectedValue(new Error(errorMessage));

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Error Loading Dashboard')).toBeInTheDocument();
      });

      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });

    it('renders reload button in error state', async () => {
      (api.fetchCameras as Mock).mockRejectedValue(new Error('API Error'));

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /reload page/i })).toBeInTheDocument();
      });
    });

    it('reloads page when reload button is clicked', async () => {
      (api.fetchCameras as Mock).mockRejectedValue(new Error('API Error'));

      // Mock window.location.reload
      const reloadMock = vi.fn();
      Object.defineProperty(window, 'location', {
        value: { reload: reloadMock },
        writable: true,
      });

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /reload page/i })).toBeInTheDocument();
      });

      const reloadButton = screen.getByRole('button', { name: /reload page/i });
      reloadButton.click();

      expect(reloadMock).toHaveBeenCalled();
    });

    it('error state has correct styling', async () => {
      (api.fetchCameras as Mock).mockRejectedValue(new Error('API Error'));

      const { container } = renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const errorContainer = container.querySelector('.bg-red-500\\/10');
        expect(errorContainer).toBeInTheDocument();
      });
    });
  });

  describe('Successful Render', () => {
    it('renders dashboard header', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /security dashboard/i })).toBeInTheDocument();
      });
    });

    it('renders subtitle with correct text', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(
          screen.getByText(/real-time ai-powered home security monitoring/i)
        ).toBeInTheDocument();
      });
    });

    it('renders all child components including activity feed', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('stats-row')).toBeInTheDocument();
        expect(screen.getByTestId('camera-grid')).toBeInTheDocument();
        expect(screen.getByTestId('activity-feed')).toBeInTheDocument();
      });
    });

    it('renders dashboard with 2-column grid layout', async () => {
      const { container } = renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('stats-row')).toBeInTheDocument();
      });

      // Check for grid layout container
      const gridContainer = container.querySelector('[class*="grid-cols"]');
      expect(gridContainer).toBeInTheDocument();
    });

    it('passes correct props to StatsRow', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const statsRow = screen.getByTestId('stats-row');
        expect(statsRow).toHaveAttribute('data-active-cameras', '1'); // Only cam1 is active
        // Events today comes from stats API - WS events may or may not be counted
        // depending on timezone (UTC timestamps vs local date comparison)
        const eventsToday = statsRow.getAttribute('data-events-today');
        expect(Number(eventsToday)).toBeGreaterThanOrEqual(10); // At least from stats
        expect(Number(eventsToday)).toBeLessThanOrEqual(12); // At most stats + WS events
        expect(statsRow).toHaveAttribute('data-risk-score', '75'); // Latest event risk score
        expect(statsRow).toHaveAttribute('data-system-status', 'healthy');
      });
    });

    it('passes risk history to StatsRow', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const statsRow = screen.getByTestId('stats-row');
        // History is reversed (oldest to newest) from first 10 merged events
        // WS events: [75, 50], Initial events: [40, 20]
        // Merged: [75, 50, 40, 20], reversed for history: [20, 40, 50, 75]
        expect(statsRow).toHaveAttribute('data-risk-history', '20,40,50,75');
      });
    });

    it('passes correct camera count to CameraGrid', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const cameraGrid = screen.getByTestId('camera-grid');
        expect(cameraGrid).toHaveAttribute('data-camera-count', '2');
      });
    });

    it('converts camera status correctly', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const cameraGrid = screen.getByTestId('camera-grid');
        expect(cameraGrid).toBeInTheDocument();
        // Cameras should be in the grid
        expect(screen.getAllByText('Front Door').length).toBeGreaterThan(0);
        expect(screen.getAllByText('Back Yard').length).toBeGreaterThan(0);
      });
    });

    it('passes thumbnail_url to CameraGrid using getCameraSnapshotUrl', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const cameraGrid = screen.getByTestId('camera-grid');
        expect(cameraGrid).toBeInTheDocument();

        // Get all buttons with these names (could be in camera grid or activity feed)
        const frontDoorButtons = screen.getAllByRole('button', { name: 'Front Door' });
        const backYardButtons = screen.getAllByRole('button', { name: 'Back Yard' });

        // At least one should have the thumbnail URL attribute (from camera grid)
        const frontDoorWithThumbnail = frontDoorButtons.find(
          (btn) => btn.getAttribute('data-thumbnail-url') === '/api/cameras/cam1/snapshot'
        );
        const backYardWithThumbnail = backYardButtons.find(
          (btn) => btn.getAttribute('data-thumbnail-url') === '/api/cameras/cam2/snapshot'
        );

        expect(frontDoorWithThumbnail).toBeDefined();
        expect(backYardWithThumbnail).toBeDefined();
      });
    });

    it('renders section headers', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /camera status/i })).toBeInTheDocument();
      });
    });

    it('passes onCameraClick handler to CameraGrid', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const cameraGrid = screen.getByTestId('camera-grid');
        // Verify the click handler is provided
        expect(cameraGrid).toHaveAttribute('data-has-click-handler', 'true');
      });
    });

    it('navigates to timeline with camera filter when camera card is clicked', async () => {
      const { user } = renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('camera-grid')).toBeInTheDocument();
      });

      // Get all Front Door buttons and find the one in the camera grid (has thumbnail URL)
      const frontDoorButtons = screen.getAllByRole('button', { name: 'Front Door' });
      const cameraGridButton = frontDoorButtons.find(
        (btn) => btn.getAttribute('data-thumbnail-url') === '/api/cameras/cam1/snapshot'
      );

      expect(cameraGridButton).toBeDefined();
      await user.click(cameraGridButton!);

      // Check that navigate was called with the correct path
      expect(mockNavigate).toHaveBeenCalledWith('/timeline?camera=cam1');
    });

    it('navigates to timeline with correct camera ID for each camera', async () => {
      const { user } = renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('camera-grid')).toBeInTheDocument();
      });

      // Get all Back Yard buttons and find the one in the camera grid (has thumbnail URL)
      const backYardButtons = screen.getAllByRole('button', { name: 'Back Yard' });
      const cameraGridButton = backYardButtons.find(
        (btn) => btn.getAttribute('data-thumbnail-url') === '/api/cameras/cam2/snapshot'
      );

      expect(cameraGridButton).toBeDefined();
      await user.click(cameraGridButton!);

      // Check that navigate was called with the correct camera ID
      expect(mockNavigate).toHaveBeenCalledWith('/timeline?camera=cam2');
    });
  });

  describe('WebSocket Connection Status', () => {
    it('shows disconnected indicator when WebSocket is not connected', async () => {
      (useEventStreamHook.useEventStream as Mock).mockReturnValue({
        events: [],
        isConnected: false,
        latestEvent: null,
        clearEvents: vi.fn(),
      });

      (useSystemStatusHook.useSystemStatus as Mock).mockReturnValue({
        status: null,
        isConnected: false,
      });

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText(/disconnected/i)).toBeInTheDocument();
      });
    });

    it('does not show disconnected indicator when connected', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.queryByText(/disconnected/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Empty Data States', () => {
    it('renders with zero risk score when no events (both WS and initial)', async () => {
      (useEventStreamHook.useEventStream as Mock).mockReturnValue({
        events: [],
        isConnected: true,
        latestEvent: null,
        clearEvents: vi.fn(),
      });

      (api.fetchEvents as Mock).mockResolvedValue({
        items: [],
        pagination: {
          total: 0,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      });

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const statsRow = screen.getByTestId('stats-row');
        expect(statsRow).toHaveAttribute('data-risk-score', '0');
      });
    });

    it('renders with empty camera list', async () => {
      (api.fetchCameras as Mock).mockResolvedValue([]);

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const cameraGrid = screen.getByTestId('camera-grid');
        expect(cameraGrid).toHaveAttribute('data-camera-count', '0');
      });
    });

    it('handles empty event stats gracefully', async () => {
      (api.fetchEventStats as Mock).mockResolvedValue({
        total_events: 0,
        events_by_risk_level: {
          critical: 0,
          high: 0,
          medium: 0,
          low: 0,
        },
        events_by_camera: [],
      });

      (useEventStreamHook.useEventStream as Mock).mockReturnValue({
        events: [],
        isConnected: true,
        latestEvent: null,
        clearEvents: vi.fn(),
      });

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const statsRow = screen.getByTestId('stats-row');
        expect(statsRow).toHaveAttribute('data-events-today', '0');
      });
    });
  });

  describe('Data Fetching', () => {
    it('fetches cameras, events, and event stats on mount', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalledTimes(1);
        expect(api.fetchEvents).toHaveBeenCalledTimes(1);
        expect(api.fetchEventStats).toHaveBeenCalledTimes(1);
      });
    });

    it('fetches events with limit parameter', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith({ limit: 50 });
      });
    });

    it('fetches event stats with start_date for today', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(api.fetchEventStats).toHaveBeenCalledWith(
          expect.objectContaining({
            // The start_date should be an ISO string for today's start (may vary by timezone)
            start_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/),
          })
        );
      });
    });

    it('fetches all APIs in parallel', async () => {
      let camerasResolve: () => void;
      let eventsResolve: () => void;
      let statsResolve: () => void;

      const camerasPromise = new Promise<typeof mockCameras>((resolve) => {
        camerasResolve = () => resolve(mockCameras);
      });

      const eventsPromise = new Promise<typeof mockEventListResponse>((resolve) => {
        eventsResolve = () => resolve(mockEventListResponse);
      });

      const statsPromise = new Promise<typeof mockEventStats>((resolve) => {
        statsResolve = () => resolve(mockEventStats);
      });

      (api.fetchCameras as Mock).mockReturnValue(camerasPromise);
      (api.fetchEvents as Mock).mockReturnValue(eventsPromise);
      (api.fetchEventStats as Mock).mockReturnValue(statsPromise);

      renderWithProviders(<DashboardPage />);

      // Resolve all
      camerasResolve!();
      eventsResolve!();
      statsResolve!();

      await waitFor(() => {
        expect(screen.getByTestId('stats-row')).toBeInTheDocument();
      });

      // All should be called
      expect(api.fetchCameras).toHaveBeenCalledTimes(1);
      expect(api.fetchEvents).toHaveBeenCalledTimes(1);
      expect(api.fetchEventStats).toHaveBeenCalledTimes(1);
    });
  });

  describe('Initial Events and Stats', () => {
    it('uses event stats for events today count', async () => {
      // Set stats to a specific value
      (api.fetchEventStats as Mock).mockResolvedValue({
        ...mockEventStats,
        total_events: 25,
      });

      // Set no WebSocket events to test base case
      (useEventStreamHook.useEventStream as Mock).mockReturnValue({
        events: [],
        isConnected: true,
        latestEvent: null,
        clearEvents: vi.fn(),
      });

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const statsRow = screen.getByTestId('stats-row');
        expect(statsRow).toHaveAttribute('data-events-today', '25');
      });
    });

    it('uses latest event risk score from merged events for stats row', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const statsRow = screen.getByTestId('stats-row');
        // Latest WS event has risk_score 75
        expect(statsRow).toHaveAttribute('data-risk-score', '75');
      });
    });
  });

  describe('Activity Feed Integration', () => {
    it('renders ActivityFeed with recent events', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const activityFeed = screen.getByTestId('activity-feed');
        expect(activityFeed).toBeInTheDocument();
      });
    });

    it('passes maxItems=10 to ActivityFeed', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const activityFeed = screen.getByTestId('activity-feed');
        expect(activityFeed).toHaveAttribute('data-max-items', '10');
      });
    });

    it('passes merged events to ActivityFeed', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const activityFeed = screen.getByTestId('activity-feed');
        // Should have WS events + initial events (deduplicated)
        const eventCount = activityFeed.getAttribute('data-event-count');
        expect(Number(eventCount)).toBeGreaterThan(0);
      });
    });

    it('passes onEventClick handler to ActivityFeed', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const activityFeed = screen.getByTestId('activity-feed');
        expect(activityFeed).toHaveAttribute('data-has-click-handler', 'true');
      });
    });

    it('navigates to timeline with event when activity item is clicked', async () => {
      const { user } = renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('activity-feed')).toBeInTheDocument();
      });

      // Click on an activity item (Front Door event)
      const frontDoorEvent = screen.getAllByRole('button', { name: 'Front Door' })[0];
      await user.click(frontDoorEvent);

      // Check that navigate was called (to timeline or event detail)
      expect(mockNavigate).toHaveBeenCalled();
    });
  });

  describe('Summary Cards Integration', () => {
    it('renders SummaryCards component on the dashboard', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('summary-cards')).toBeInTheDocument();
      });
    });

    it('passes loading state to SummaryCards', async () => {
      (useSummariesHook.useSummaries as Mock).mockReturnValue({
        hourly: null,
        daily: null,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
      });

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const summaryCards = screen.getByTestId('summary-cards');
        expect(summaryCards).toHaveAttribute('data-is-loading', 'true');
      });
    });

    it('passes hourly summary data to SummaryCards', async () => {
      const mockHourlySummary = {
        id: 1,
        content: 'One critical event at 2:15 PM at front door.',
        eventCount: 1,
        windowStart: '2026-01-18T14:00:00Z',
        windowEnd: '2026-01-18T15:00:00Z',
        generatedAt: '2026-01-18T14:55:00Z',
      };

      (useSummariesHook.useSummaries as Mock).mockReturnValue({
        hourly: mockHourlySummary,
        daily: null,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const summaryCards = screen.getByTestId('summary-cards');
        expect(summaryCards).toHaveAttribute('data-has-hourly', 'true');
        expect(summaryCards).toHaveAttribute(
          'data-hourly-content',
          'One critical event at 2:15 PM at front door.'
        );
      });
    });

    it('passes daily summary data to SummaryCards', async () => {
      const mockDailySummary = {
        id: 2,
        content: 'Minimal activity today with one event at 2:15 PM.',
        eventCount: 1,
        windowStart: '2026-01-18T00:00:00Z',
        windowEnd: '2026-01-18T15:00:00Z',
        generatedAt: '2026-01-18T14:55:00Z',
      };

      (useSummariesHook.useSummaries as Mock).mockReturnValue({
        hourly: null,
        daily: mockDailySummary,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const summaryCards = screen.getByTestId('summary-cards');
        expect(summaryCards).toHaveAttribute('data-has-daily', 'true');
        expect(summaryCards).toHaveAttribute(
          'data-daily-content',
          'Minimal activity today with one event at 2:15 PM.'
        );
      });
    });

    it('passes both hourly and daily summaries to SummaryCards', async () => {
      const mockHourlySummary = {
        id: 1,
        content: 'Hourly: one event at front door.',
        eventCount: 1,
        windowStart: '2026-01-18T14:00:00Z',
        windowEnd: '2026-01-18T15:00:00Z',
        generatedAt: '2026-01-18T14:55:00Z',
      };

      const mockDailySummary = {
        id: 2,
        content: 'Daily: total three events today.',
        eventCount: 3,
        windowStart: '2026-01-18T00:00:00Z',
        windowEnd: '2026-01-18T15:00:00Z',
        generatedAt: '2026-01-18T14:55:00Z',
      };

      (useSummariesHook.useSummaries as Mock).mockReturnValue({
        hourly: mockHourlySummary,
        daily: mockDailySummary,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const summaryCards = screen.getByTestId('summary-cards');
        expect(summaryCards).toHaveAttribute('data-has-hourly', 'true');
        expect(summaryCards).toHaveAttribute('data-has-daily', 'true');
        expect(summaryCards).toHaveAttribute('data-is-loading', 'false');
      });
    });
  });

  describe('Expandable Detail Panel Integration (NEM-5526)', () => {
    const mockHourlySummary = {
      id: 10,
      content: 'Hourly summary for detail panel test.',
      eventCount: 2,
      windowStart: '2026-01-18T14:00:00Z',
      windowEnd: '2026-01-18T15:00:00Z',
      generatedAt: '2026-01-18T14:55:00Z',
    };

    const mockDetailResponse = {
      id: 10,
      summaryType: 'hourly' as const,
      content: 'Hourly summary for detail panel test.',
      eventCount: 2,
      windowStart: '2026-01-18T14:00:00Z',
      windowEnd: '2026-01-18T15:00:00Z',
      generatedAt: '2026-01-18T14:55:00Z',
      timeline: [
        {
          eventId: 101,
          timestamp: '2026-01-18T14:10:00Z',
          cameraName: 'Front Door',
          summary: 'Person detected',
          riskScore: 75,
          riskLevel: 'high',
          eventUrl: '/events/101',
        },
      ],
      exportFormats: ['json', 'csv', 'pdf'],
      focusAreas: ['Front Door'],
      maxRiskScore: 75,
    };

    it('passes onViewFull handler to SummaryCards', async () => {
      (useSummariesHook.useSummaries as Mock).mockReturnValue({
        hourly: mockHourlySummary,
        daily: null,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const summaryCards = screen.getByTestId('summary-cards');
        expect(summaryCards).toHaveAttribute('data-has-view-full', 'true');
      });
    });

    it('opens detail panel when View Full Summary is clicked', async () => {
      (useSummariesHook.useSummaries as Mock).mockReturnValue({
        hourly: mockHourlySummary,
        daily: null,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });

      (api.fetchSummaryDetail as Mock).mockResolvedValue(mockDetailResponse);

      const { user } = renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('view-full-hourly')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('view-full-hourly'));

      await waitFor(() => {
        expect(screen.getByTestId('expandable-detail-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('expandable-detail-panel')).toHaveAttribute(
        'data-detail-id',
        '10'
      );
      expect(screen.getByTestId('expandable-detail-panel')).toHaveAttribute(
        'data-summary-type',
        'hourly'
      );
    });

    it('closes detail panel when close button is clicked', async () => {
      (useSummariesHook.useSummaries as Mock).mockReturnValue({
        hourly: mockHourlySummary,
        daily: null,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });

      (api.fetchSummaryDetail as Mock).mockResolvedValue(mockDetailResponse);

      const { user } = renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('view-full-hourly')).toBeInTheDocument();
      });

      // Open the panel
      await user.click(screen.getByTestId('view-full-hourly'));

      await waitFor(() => {
        expect(screen.getByTestId('expandable-detail-panel')).toBeInTheDocument();
      });

      // Close the panel
      await user.click(screen.getByTestId('detail-panel-close'));

      await waitFor(() => {
        expect(screen.queryByTestId('expandable-detail-panel')).not.toBeInTheDocument();
      });
    });

    it('shows panel with fallback data when detail API fails', async () => {
      (useSummariesHook.useSummaries as Mock).mockReturnValue({
        hourly: mockHourlySummary,
        daily: null,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });

      (api.fetchSummaryDetail as Mock).mockRejectedValue(new Error('API Error'));

      const { user } = renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('view-full-hourly')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('view-full-hourly'));

      // Panel should still open with fallback data
      await waitFor(() => {
        expect(screen.getByTestId('expandable-detail-panel')).toBeInTheDocument();
      });

      // Should show the summary content from the basic summary data
      expect(screen.getByTestId('detail-narrative')).toHaveTextContent(
        'Hourly summary for detail panel test.'
      );
    });

    it('does not render detail panel when no summary is selected', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('summary-cards')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('expandable-detail-panel')).not.toBeInTheDocument();
    });
  });

  describe('Styling and Layout', () => {
    it('has correct dashboard structure and styling', async () => {
      const { container } = renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /security dashboard/i })).toBeInTheDocument();
      });

      // Check for dark theme background
      const darkBg = container.querySelector('[class*="bg-"]');
      expect(darkBg).toBeTruthy();

      // Check for responsive design classes (md: breakpoint is used for spacing and typography)
      const responsiveElements = container.querySelectorAll('[class*="md:"]');
      expect(responsiveElements.length).toBeGreaterThan(0);
    });
  });

  describe('Threat Detection Banner (NEM-5024)', () => {
    it('does not render threat banner when no active threats', async () => {
      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('stats-row')).toBeInTheDocument();
      });

      // Banner should not be present
      expect(screen.queryByTestId('threat-detection-banner')).not.toBeInTheDocument();
    });

    it('renders threat banner when threats are active', async () => {
      const mockThreat = {
        id: 1,
        threat_type: 'gun',
        confidence: 0.95,
        severity: 'critical' as const,
        camera_id: 'front_door',
        event_id: 123,
        created_at: new Date().toISOString(),
      };

      (useThreatDetectionHook.useThreatDetection as Mock).mockReturnValue({
        threatSummary: {
          hasActiveThreats: true,
          totalThreats: 1,
          maxSeverity: 'critical',
          threats: [mockThreat],
          criticalCount: 1,
          highCount: 0,
          mediumCount: 0,
          latestThreat: mockThreat,
          threatTypes: ['gun'],
          affectedCameras: ['front_door'],
        },
        isLoading: false,
        dismissedIds: new Set(),
        addThreat: vi.fn(),
        removeThreat: vi.fn(),
        clearThreats: vi.fn(),
        dismissThreat: vi.fn(),
        clearDismissed: vi.fn(),
      });

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('threat-detection-banner')).toBeInTheDocument();
      });

      // Should show threat detected text
      expect(screen.getByText(/THREAT DETECTED/i)).toBeInTheDocument();
      // Should show threat type
      expect(screen.getByText(/Firearm/i)).toBeInTheDocument();
      // Should show confidence
      expect(screen.getByText(/95%/)).toBeInTheDocument();
    });

    it('shows critical styling for critical threats', async () => {
      const mockThreat = {
        id: 1,
        threat_type: 'gun',
        confidence: 0.95,
        severity: 'critical' as const,
        camera_id: 'front_door',
        event_id: 123,
        created_at: new Date().toISOString(),
      };

      (useThreatDetectionHook.useThreatDetection as Mock).mockReturnValue({
        threatSummary: {
          hasActiveThreats: true,
          totalThreats: 1,
          maxSeverity: 'critical',
          threats: [mockThreat],
          criticalCount: 1,
          highCount: 0,
          mediumCount: 0,
          latestThreat: mockThreat,
          threatTypes: ['gun'],
          affectedCameras: ['front_door'],
        },
        isLoading: false,
        dismissedIds: new Set(),
        addThreat: vi.fn(),
        removeThreat: vi.fn(),
        clearThreats: vi.fn(),
        dismissThreat: vi.fn(),
        clearDismissed: vi.fn(),
      });

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        const banner = screen.getByTestId('threat-detection-banner');
        expect(banner).toHaveClass('border-red-500');
      });
    });

    it('navigates to timeline when View button is clicked', async () => {
      const mockThreat = {
        id: 1,
        threat_type: 'gun',
        confidence: 0.95,
        severity: 'critical' as const,
        camera_id: 'front_door',
        event_id: 456,
        created_at: new Date().toISOString(),
      };

      (useThreatDetectionHook.useThreatDetection as Mock).mockReturnValue({
        threatSummary: {
          hasActiveThreats: true,
          totalThreats: 1,
          maxSeverity: 'critical',
          threats: [mockThreat],
          criticalCount: 1,
          highCount: 0,
          mediumCount: 0,
          latestThreat: mockThreat,
          threatTypes: ['gun'],
          affectedCameras: ['front_door'],
        },
        isLoading: false,
        dismissedIds: new Set(),
        addThreat: vi.fn(),
        removeThreat: vi.fn(),
        clearThreats: vi.fn(),
        dismissThreat: vi.fn(),
        clearDismissed: vi.fn(),
      });

      const { user } = renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('threat-detection-banner')).toBeInTheDocument();
      });

      const viewButton = screen.getByRole('button', { name: /view/i });
      await user.click(viewButton);

      expect(mockNavigate).toHaveBeenCalledWith('/timeline?event=456');
    });

    it('calls dismissThreat when dismiss button is clicked', async () => {
      const mockDismissThreat = vi.fn();
      const mockThreat = {
        id: 789,
        threat_type: 'knife',
        confidence: 0.8,
        severity: 'high' as const,
        camera_id: 'back_yard',
        event_id: 999,
        created_at: new Date().toISOString(),
      };

      (useThreatDetectionHook.useThreatDetection as Mock).mockReturnValue({
        threatSummary: {
          hasActiveThreats: true,
          totalThreats: 1,
          maxSeverity: 'high',
          threats: [mockThreat],
          criticalCount: 0,
          highCount: 1,
          mediumCount: 0,
          latestThreat: mockThreat,
          threatTypes: ['knife'],
          affectedCameras: ['back_yard'],
        },
        isLoading: false,
        dismissedIds: new Set(),
        addThreat: vi.fn(),
        removeThreat: vi.fn(),
        clearThreats: vi.fn(),
        dismissThreat: mockDismissThreat,
        clearDismissed: vi.fn(),
      });

      const { user } = renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('threat-detection-banner')).toBeInTheDocument();
      });

      const dismissButton = screen.getByRole('button', { name: /dismiss/i });
      await user.click(dismissButton);

      expect(mockDismissThreat).toHaveBeenCalledWith(789);
    });

    it('shows multiple threat count when multiple threats are active', async () => {
      const mockThreats = [
        {
          id: 1,
          threat_type: 'gun',
          confidence: 0.95,
          severity: 'critical' as const,
          camera_id: 'front_door',
          event_id: 123,
          created_at: new Date().toISOString(),
        },
        {
          id: 2,
          threat_type: 'knife',
          confidence: 0.8,
          severity: 'high' as const,
          camera_id: 'back_yard',
          event_id: 124,
          created_at: new Date().toISOString(),
        },
      ];

      (useThreatDetectionHook.useThreatDetection as Mock).mockReturnValue({
        threatSummary: {
          hasActiveThreats: true,
          totalThreats: 2,
          maxSeverity: 'critical',
          threats: mockThreats,
          criticalCount: 1,
          highCount: 1,
          mediumCount: 0,
          latestThreat: mockThreats[0],
          threatTypes: ['gun', 'knife'],
          affectedCameras: ['front_door', 'back_yard'],
        },
        isLoading: false,
        dismissedIds: new Set(),
        addThreat: vi.fn(),
        removeThreat: vi.fn(),
        clearThreats: vi.fn(),
        dismissThreat: vi.fn(),
        clearDismissed: vi.fn(),
      });

      renderWithProviders(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('threat-detection-banner')).toBeInTheDocument();
      });

      // Should show threat count
      expect(screen.getByText(/2 threats/i)).toBeInTheDocument();
      // Should show multiple cameras
      expect(screen.getByText(/2 cameras/i)).toBeInTheDocument();
    });
  });
});
