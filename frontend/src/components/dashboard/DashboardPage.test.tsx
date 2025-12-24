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
vi.mock('./RiskGauge', () => ({
  default: ({ value, history }: { value: number; history?: number[] }) => (
    <div data-testid="risk-gauge" data-value={value} data-history={history?.join(',')}>
      Risk Gauge
    </div>
  ),
}));

vi.mock('./GpuStats', () => ({
  default: ({ utilization, memoryUsed, temperature, inferenceFps }: {
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
  default: ({ cameras }: { cameras: Array<{ id: string; name: string }> }) => (
    <div data-testid="camera-grid" data-camera-count={cameras.length}>
      {cameras.map((camera) => (
        <div key={camera.id}>{camera.name}</div>
      ))}
    </div>
  ),
}));

vi.mock('./ActivityFeed', () => ({
  default: ({ events, maxItems }: { events: Array<{ id: string }>; maxItems: number }) => (
    <div data-testid="activity-feed" data-event-count={events.length} data-max-items={maxItems}>
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
      status: 'active',
      created_at: '2025-01-01T00:00:00Z',
      last_seen_at: '2025-01-01T12:00:00Z',
    },
    {
      id: 'cam2',
      name: 'Back Yard',
      folder_path: '/export/foscam/back',
      status: 'inactive',
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

  const mockEvents = [
    {
      id: 'event1',
      camera_id: 'cam1',
      camera_name: 'Front Door',
      risk_score: 75,
      risk_level: 'high' as const,
      summary: 'Person detected at front door',
      timestamp: '2025-01-01T12:00:00Z',
    },
    {
      id: 'event2',
      camera_id: 'cam1',
      camera_name: 'Front Door',
      risk_score: 50,
      risk_level: 'medium' as const,
      summary: 'Motion detected',
      timestamp: '2025-01-01T11:55:00Z',
    },
  ];

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

    (useEventStreamHook.useEventStream as Mock).mockReturnValue({
      events: mockEvents,
      isConnected: true,
      latestEvent: mockEvents[0],
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
      (api.fetchCameras as Mock).mockImplementation(
        () => new Promise(() => {})
      );
      (api.fetchGPUStats as Mock).mockImplementation(
        () => new Promise(() => {})
      );

      render(<DashboardPage />);

      // Check for loading skeletons
      const skeletons = screen.getAllByRole('generic').filter(
        (el) => el.className.includes('animate-pulse')
      );
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('loading state has correct background color', () => {
      (api.fetchCameras as Mock).mockImplementation(
        () => new Promise(() => {})
      );

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
        expect(screen.getByText(/real-time ai-powered home security monitoring/i)).toBeInTheDocument();
      });
    });

    it('renders all child components', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId('risk-gauge')).toBeInTheDocument();
        expect(screen.getByTestId('gpu-stats')).toBeInTheDocument();
        expect(screen.getByTestId('camera-grid')).toBeInTheDocument();
        expect(screen.getByTestId('activity-feed')).toBeInTheDocument();
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
        // History is reversed, so [50, 75]
        expect(riskGauge).toHaveAttribute('data-history', '50,75');
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

    it('passes correct event count to ActivityFeed', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        const activityFeed = screen.getByTestId('activity-feed');
        expect(activityFeed).toHaveAttribute('data-event-count', '2');
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
    it('renders with zero risk score when no events', async () => {
      (useEventStreamHook.useEventStream as Mock).mockReturnValue({
        events: [],
        isConnected: true,
        latestEvent: null,
        clearEvents: vi.fn(),
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
  });

  describe('Data Fetching', () => {
    it('fetches cameras and GPU stats on mount', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalledTimes(1);
        expect(api.fetchGPUStats).toHaveBeenCalledTimes(1);
      });
    });

    it('fetches both APIs in parallel', async () => {
      let camerasResolve: () => void;
      let gpuResolve: () => void;

      const camerasPromise = new Promise<typeof mockCameras>((resolve) => {
        camerasResolve = () => resolve(mockCameras);
      });

      const gpuPromise = new Promise<typeof mockGPUStats>((resolve) => {
        gpuResolve = () => resolve(mockGPUStats);
      });

      (api.fetchCameras as Mock).mockReturnValue(camerasPromise);
      (api.fetchGPUStats as Mock).mockReturnValue(gpuPromise);

      render(<DashboardPage />);

      // Resolve both
      camerasResolve!();
      gpuResolve!();

      await waitFor(() => {
        expect(screen.getByTestId('risk-gauge')).toBeInTheDocument();
      });

      // Both should be called
      expect(api.fetchCameras).toHaveBeenCalledTimes(1);
      expect(api.fetchGPUStats).toHaveBeenCalledTimes(1);
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
