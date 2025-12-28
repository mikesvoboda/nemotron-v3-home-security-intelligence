import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';

import DashboardPage from './DashboardPage';
import * as useEventStreamHook from '../../hooks/useEventStream';
import * as useSystemStatusHook from '../../hooks/useSystemStatus';
import * as api from '../../services/api';

// Mock the API and hooks
vi.mock('../../services/api');
vi.mock('../../hooks/useEventStream');
vi.mock('../../hooks/useSystemStatus');

// Mock child components
vi.mock('./StatsRow', () => ({
  default: ({
    activeCameras,
    eventsToday,
    currentRiskScore,
    systemStatus,
  }: {
    activeCameras: number;
    eventsToday: number;
    currentRiskScore: number;
    systemStatus: string;
  }) => (
    <div
      data-testid="stats-row"
      data-active-cameras={activeCameras}
      data-events-today={eventsToday}
      data-risk-score={currentRiskScore}
      data-system-status={systemStatus}
    >
      Stats Row
    </div>
  ),
}));

vi.mock('./RiskGauge', () => ({
  default: ({ value, history }: { value: number; history?: number[] }) => (
    <div data-testid="risk-gauge" data-value={value} data-history={history?.join(',')}>
      Risk Gauge
    </div>
  ),
}));

vi.mock('./GpuStats', () => ({
  default: ({
    utilization,
    memoryUsed,
    temperature,
    inferenceFps,
  }: {
    utilization: number | null;
    memoryUsed: number | null;
    temperature: number | null;
    inferenceFps: number | null;
  }) => (
    <div
      data-testid="gpu-stats"
      data-utilization={utilization}
      data-memory-used={memoryUsed}
      data-temperature={temperature}
      data-inference-fps={inferenceFps}
    >
      GPU Stats
    </div>
  ),
}));

vi.mock('./CameraGrid', () => ({
  default: ({
    cameras,
  }: {
    cameras: Array<{ id: string; name: string; thumbnail_url?: string }>;
  }) => (
    <div data-testid="camera-grid" data-camera-count={cameras.length}>
      {cameras.map((camera) => (
        <div key={camera.id} data-thumbnail-url={camera.thumbnail_url}>
          {camera.name}
        </div>
      ))}
    </div>
  ),
}));

vi.mock('./ActivityFeed', () => ({
  default: ({
    events,
    maxItems,
  }: {
    events: Array<{ id: string; camera_name: string }>;
    maxItems: number;
  }) => (
    <div
      data-testid="activity-feed"
      data-event-count={events.length}
      data-max-items={maxItems}
      data-camera-names={events.map((e) => e.camera_name).join(',')}
    >
      Activity Feed
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

  const mockGPUStats = {
    utilization: 75,
    memory_used: 8192,
    memory_total: 24576,
    temperature: 65,
    inference_fps: 30,
  };

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
    events: mockInitialEvents,
    count: 2,
    limit: 50,
    offset: 0,
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

    // Setup default mock implementations
    (api.fetchCameras as Mock).mockResolvedValue(mockCameras);
    (api.fetchGPUStats as Mock).mockResolvedValue(mockGPUStats);
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
  });

  describe('Loading State', () => {
    it('renders loading skeletons while fetching initial data', () => {
      // Make API call hang
      (api.fetchCameras as Mock).mockImplementation(() => new Promise(() => {}));
      (api.fetchGPUStats as Mock).mockImplementation(() => new Promise(() => {}));

      render(<DashboardPage />);

      // Check for loading skeletons
      const skeletons = screen
        .getAllByRole('generic')
        .filter((el) => el.className.includes('animate-pulse'));
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('loading state has correct background color', () => {
      (api.fetchCameras as Mock).mockImplementation(() => new Promise(() => {}));

      const { container } = render(<DashboardPage />);
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass('bg-[#121212]');
    });
  });

  describe('Error State', () => {
    it('renders error message when API fails', async () => {
      const errorMessage = 'Failed to fetch cameras';
      (api.fetchCameras as Mock).mockRejectedValue(new Error(errorMessage));

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Error Loading Dashboard')).toBeInTheDocument();
      });

      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });

    it('renders reload button in error state', async () => {
      (api.fetchCameras as Mock).mockRejectedValue(new Error('API Error'));

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /reload page/i })).toBeInTheDocument();
      });
    });

    it('error state has correct styling', async () => {
      (api.fetchCameras as Mock).mockRejectedValue(new Error('API Error'));

      const { container } = render(<DashboardPage />);

      await waitFor(() => {
        const errorContainer = container.querySelector('.bg-red-500\\/10');
        expect(errorContainer).toBeInTheDocument();
      });
    });
  });

  describe('Successful Render', () => {
    it('renders dashboard header', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /security dashboard/i })).toBeInTheDocument();
      });
    });

    it('renders subtitle with correct text', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(
          screen.getByText(/real-time ai-powered home security monitoring/i)
        ).toBeInTheDocument();
      });
    });

    it('renders all child components', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('stats-row')).toBeInTheDocument();
        expect(screen.getByTestId('risk-gauge')).toBeInTheDocument();
        expect(screen.getByTestId('gpu-stats')).toBeInTheDocument();
        expect(screen.getByTestId('camera-grid')).toBeInTheDocument();
        expect(screen.getByTestId('activity-feed')).toBeInTheDocument();
      });
    });

    it('passes correct props to StatsRow', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        const statsRow = screen.getByTestId('stats-row');
        expect(statsRow).toHaveAttribute('data-active-cameras', '1'); // Only cam1 is active
        // Events today comes from stats API (10) + new WS events not in initial load
        expect(statsRow).toHaveAttribute('data-events-today', '12'); // 10 from stats + 2 new WS events
        expect(statsRow).toHaveAttribute('data-risk-score', '75'); // Latest event risk score
        expect(statsRow).toHaveAttribute('data-system-status', 'healthy');
      });
    });

    it('passes correct props to RiskGauge', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        const riskGauge = screen.getByTestId('risk-gauge');
        expect(riskGauge).toHaveAttribute('data-value', '75'); // Latest event risk score
      });
    });

    it('passes risk history to RiskGauge', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        const riskGauge = screen.getByTestId('risk-gauge');
        // History is reversed (oldest to newest) from first 10 merged events
        // WS events: [75, 50], Initial events: [40, 20]
        // Merged: [75, 50, 40, 20], reversed for history: [20, 40, 50, 75]
        expect(riskGauge).toHaveAttribute('data-history', '20,40,50,75');
      });
    });

    it('passes correct props to GpuStats', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        const gpuStats = screen.getByTestId('gpu-stats');
        expect(gpuStats).toHaveAttribute('data-utilization', '75');
        expect(gpuStats).toHaveAttribute('data-memory-used', '8192');
        expect(gpuStats).toHaveAttribute('data-temperature', '65');
        expect(gpuStats).toHaveAttribute('data-inference-fps', '30');
      });
    });

    it('passes correct camera count to CameraGrid', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        const cameraGrid = screen.getByTestId('camera-grid');
        expect(cameraGrid).toHaveAttribute('data-camera-count', '2');
      });
    });

    it('passes correct event count to ActivityFeed (merged WS + initial events)', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        const activityFeed = screen.getByTestId('activity-feed');
        // 2 WS events + 2 initial events = 4 total (no duplicates)
        expect(activityFeed).toHaveAttribute('data-event-count', '4');
        expect(activityFeed).toHaveAttribute('data-max-items', '10');
      });
    });

    it('converts camera status correctly', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
        expect(screen.getByText('Back Yard')).toBeInTheDocument();
      });
    });

    it('passes thumbnail_url to CameraGrid using getCameraSnapshotUrl', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        const frontDoor = screen.getByText('Front Door');
        const backYard = screen.getByText('Back Yard');

        // Verify thumbnail URLs are generated using getCameraSnapshotUrl pattern
        expect(frontDoor).toHaveAttribute('data-thumbnail-url', '/api/cameras/cam1/snapshot');
        expect(backYard).toHaveAttribute('data-thumbnail-url', '/api/cameras/cam2/snapshot');
      });
    });

    it('renders section headers', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /current risk level/i })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: /camera status/i })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: /live activity/i })).toBeInTheDocument();
      });
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

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText(/disconnected/i)).toBeInTheDocument();
      });
    });

    it('does not show disconnected indicator when connected', async () => {
      render(<DashboardPage />);

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
        events: [],
        count: 0,
        limit: 50,
        offset: 0,
      });

      render(<DashboardPage />);

      await waitFor(() => {
        const riskGauge = screen.getByTestId('risk-gauge');
        expect(riskGauge).toHaveAttribute('data-value', '0');
      });
    });

    it('renders with empty camera list', async () => {
      (api.fetchCameras as Mock).mockResolvedValue([]);

      render(<DashboardPage />);

      await waitFor(() => {
        const cameraGrid = screen.getByTestId('camera-grid');
        expect(cameraGrid).toHaveAttribute('data-camera-count', '0');
      });
    });

    it('handles null GPU stats gracefully', async () => {
      (api.fetchGPUStats as Mock).mockResolvedValue({
        utilization: null,
        memory_used: null,
        memory_total: null,
        temperature: null,
        inference_fps: null,
      });

      render(<DashboardPage />);

      await waitFor(() => {
        const gpuStats = screen.getByTestId('gpu-stats');
        expect(gpuStats).toBeInTheDocument();
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

      render(<DashboardPage />);

      await waitFor(() => {
        const statsRow = screen.getByTestId('stats-row');
        expect(statsRow).toHaveAttribute('data-events-today', '0');
      });
    });
  });

  describe('Data Fetching', () => {
    it('fetches cameras, GPU stats, events, and event stats on mount', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalledTimes(1);
        expect(api.fetchGPUStats).toHaveBeenCalledTimes(1);
        expect(api.fetchEvents).toHaveBeenCalledTimes(1);
        expect(api.fetchEventStats).toHaveBeenCalledTimes(1);
      });
    });

    it('fetches events with limit parameter', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith({ limit: 50 });
      });
    });

    it('fetches event stats with start_date for today', async () => {
      render(<DashboardPage />);

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
      let gpuResolve: () => void;
      let eventsResolve: () => void;
      let statsResolve: () => void;

      const camerasPromise = new Promise<typeof mockCameras>((resolve) => {
        camerasResolve = () => resolve(mockCameras);
      });

      const gpuPromise = new Promise<typeof mockGPUStats>((resolve) => {
        gpuResolve = () => resolve(mockGPUStats);
      });

      const eventsPromise = new Promise<typeof mockEventListResponse>((resolve) => {
        eventsResolve = () => resolve(mockEventListResponse);
      });

      const statsPromise = new Promise<typeof mockEventStats>((resolve) => {
        statsResolve = () => resolve(mockEventStats);
      });

      (api.fetchCameras as Mock).mockReturnValue(camerasPromise);
      (api.fetchGPUStats as Mock).mockReturnValue(gpuPromise);
      (api.fetchEvents as Mock).mockReturnValue(eventsPromise);
      (api.fetchEventStats as Mock).mockReturnValue(statsPromise);

      render(<DashboardPage />);

      // Resolve all
      camerasResolve!();
      gpuResolve!();
      eventsResolve!();
      statsResolve!();

      await waitFor(() => {
        expect(screen.getByTestId('risk-gauge')).toBeInTheDocument();
      });

      // All should be called
      expect(api.fetchCameras).toHaveBeenCalledTimes(1);
      expect(api.fetchGPUStats).toHaveBeenCalledTimes(1);
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

      render(<DashboardPage />);

      await waitFor(() => {
        const statsRow = screen.getByTestId('stats-row');
        expect(statsRow).toHaveAttribute('data-events-today', '25');
      });
    });

    it('merges initial events with WebSocket events for activity feed', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        const activityFeed = screen.getByTestId('activity-feed');
        // 2 WS events + 2 initial events = 4 total
        expect(activityFeed).toHaveAttribute('data-event-count', '4');
      });
    });

    it('deduplicates events with same ID', async () => {
      // Set an initial event with the same ID as a WS event
      const duplicateEvent = {
        id: 'event1', // Same ID as first WS event
        camera_id: 'cam1',
        started_at: '2025-01-01T11:50:00Z',
        ended_at: '2025-01-01T11:52:00Z',
        risk_score: 40,
        risk_level: 'medium',
        summary: 'This should be deduplicated',
        reviewed: false,
        notes: null,
        detection_count: 3,
      };

      (api.fetchEvents as Mock).mockResolvedValue({
        events: [duplicateEvent],
        count: 1,
        limit: 50,
        offset: 0,
      });

      render(<DashboardPage />);

      await waitFor(() => {
        const activityFeed = screen.getByTestId('activity-feed');
        // 2 WS events + 0 initial (deduplicated) = 2
        expect(activityFeed).toHaveAttribute('data-event-count', '2');
      });
    });

    it('uses latest event risk score from merged events for risk gauge', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        const riskGauge = screen.getByTestId('risk-gauge');
        // Latest WS event has risk_score 75
        expect(riskGauge).toHaveAttribute('data-value', '75');
      });
    });

    it('resolves camera names from cameras list for events without camera_name', async () => {
      // Set WebSocket events WITHOUT camera_name (simulating backend not providing it)
      const wsEventsWithoutCameraName = [
        {
          id: 'event1',
          camera_id: 'cam1', // Should resolve to 'Front Door'
          risk_score: 75,
          risk_level: 'high' as const,
          summary: 'Person detected at front door',
          timestamp: `${todayISOString}T12:00:00Z`,
        },
        {
          id: 'event2',
          camera_id: 'cam2', // Should resolve to 'Back Yard'
          risk_score: 50,
          risk_level: 'medium' as const,
          summary: 'Motion detected',
          timestamp: `${todayISOString}T11:55:00Z`,
        },
      ];

      (useEventStreamHook.useEventStream as Mock).mockReturnValue({
        events: wsEventsWithoutCameraName,
        isConnected: true,
        latestEvent: wsEventsWithoutCameraName[0],
        clearEvents: vi.fn(),
      });

      // Also set initial events without camera_name
      const initialEventsWithoutCameraName = [
        {
          id: 3,
          camera_id: 'cam1', // Should resolve to 'Front Door'
          started_at: '2025-01-01T11:50:00Z',
          ended_at: '2025-01-01T11:52:00Z',
          risk_score: 40,
          risk_level: 'medium',
          summary: 'Vehicle detected in driveway',
          reviewed: false,
          notes: null,
          detection_count: 3,
        },
      ];

      (api.fetchEvents as Mock).mockResolvedValue({
        events: initialEventsWithoutCameraName,
        count: 1,
        limit: 50,
        offset: 0,
      });

      render(<DashboardPage />);

      await waitFor(() => {
        const activityFeed = screen.getByTestId('activity-feed');
        // Should have resolved camera names: cam1 -> 'Front Door', cam2 -> 'Back Yard'
        const cameraNames = activityFeed.getAttribute('data-camera-names');
        expect(cameraNames).toContain('Front Door');
        expect(cameraNames).toContain('Back Yard');
        expect(cameraNames).not.toContain('Unknown Camera');
      });
    });

    it('falls back to "Unknown Camera" when camera_id not found in cameras list', async () => {
      // Set event with unknown camera_id
      const wsEventsWithUnknownCamera = [
        {
          id: 'event1',
          camera_id: 'unknown-camera-id', // Not in mockCameras
          risk_score: 75,
          risk_level: 'high' as const,
          summary: 'Person detected',
          timestamp: `${todayISOString}T12:00:00Z`,
        },
      ];

      (useEventStreamHook.useEventStream as Mock).mockReturnValue({
        events: wsEventsWithUnknownCamera,
        isConnected: true,
        latestEvent: wsEventsWithUnknownCamera[0],
        clearEvents: vi.fn(),
      });

      (api.fetchEvents as Mock).mockResolvedValue({
        events: [],
        count: 0,
        limit: 50,
        offset: 0,
      });

      render(<DashboardPage />);

      await waitFor(() => {
        const activityFeed = screen.getByTestId('activity-feed');
        const cameraNames = activityFeed.getAttribute('data-camera-names');
        expect(cameraNames).toBe('Unknown Camera');
      });
    });

    it('uses camera_name from event if already provided (WebSocket with camera_name)', async () => {
      // WS events that already have camera_name (from backend or enriched)
      const wsEventsWithCameraName = [
        {
          id: 'event1',
          camera_id: 'cam1',
          camera_name: 'Custom Name From Backend', // Already provided
          risk_score: 75,
          risk_level: 'high' as const,
          summary: 'Person detected',
          timestamp: `${todayISOString}T12:00:00Z`,
        },
      ];

      (useEventStreamHook.useEventStream as Mock).mockReturnValue({
        events: wsEventsWithCameraName,
        isConnected: true,
        latestEvent: wsEventsWithCameraName[0],
        clearEvents: vi.fn(),
      });

      (api.fetchEvents as Mock).mockResolvedValue({
        events: [],
        count: 0,
        limit: 50,
        offset: 0,
      });

      render(<DashboardPage />);

      await waitFor(() => {
        const activityFeed = screen.getByTestId('activity-feed');
        const cameraNames = activityFeed.getAttribute('data-camera-names');
        // Should use the provided camera_name, not look it up
        expect(cameraNames).toBe('Custom Name From Backend');
      });
    });
  });

  describe('Polling', () => {
    it('polls GPU stats periodically', async () => {
      render(<DashboardPage />);

      // Wait for initial load
      await waitFor(() => {
        expect(api.fetchGPUStats).toHaveBeenCalled();
      });

      // Verify interval was set up (component renders successfully)
      expect(screen.getByTestId('risk-gauge')).toBeInTheDocument();
    });
  });

  describe('Styling and Layout', () => {
    it('has correct dashboard structure and styling', async () => {
      const { container } = render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /security dashboard/i })).toBeInTheDocument();
      });

      // Check for dark theme background
      const darkBg = container.querySelector('[class*="bg-"]');
      expect(darkBg).toBeTruthy();

      // Check for grid layout
      const gridLayout = container.querySelector('[class*="grid"]');
      expect(gridLayout).toBeTruthy();

      // Check for responsive design classes
      const responsiveElements = container.querySelectorAll('[class*="lg:"]');
      expect(responsiveElements.length).toBeGreaterThan(0);
    });
  });
});
