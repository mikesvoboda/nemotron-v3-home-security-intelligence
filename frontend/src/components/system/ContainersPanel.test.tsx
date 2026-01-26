import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ContainersPanel, { type ContainersPanelProps } from './ContainersPanel';

// Mock the API function
const mockFetchContainerServices = vi.fn();
vi.mock('../../services/api', () => ({
  fetchContainerServices: () => mockFetchContainerServices(),
}));

describe('ContainersPanel', () => {
  // Default mock container services response
  const mockContainerServicesResponse = {
    services: [
      {
        name: 'postgres',
        display_name: 'PostgreSQL',
        category: 'infrastructure',
        status: 'running',
        enabled: true,
        container_id: 'abc123def',
        image: 'postgres:16-alpine',
        port: 5432,
        failure_count: 0,
        restart_count: 0,
        last_restart_at: null,
        uptime_seconds: 86400,
      },
      {
        name: 'redis',
        display_name: 'Redis',
        category: 'infrastructure',
        status: 'running',
        enabled: true,
        container_id: 'def456ghi',
        image: 'redis:7-alpine',
        port: 6379,
        failure_count: 0,
        restart_count: 2,
        last_restart_at: '2026-01-25T10:00:00Z',
        uptime_seconds: 3600,
      },
      {
        name: 'rtdetr',
        display_name: 'RT-DETRv2',
        category: 'ai',
        status: 'running',
        enabled: true,
        container_id: 'ghi789jkl',
        image: 'ghcr.io/project/rtdetr:latest',
        port: 8001,
        failure_count: 0,
        restart_count: 1,
        last_restart_at: '2026-01-25T09:00:00Z',
        uptime_seconds: 7200,
      },
      {
        name: 'nemotron',
        display_name: 'Nemotron',
        category: 'ai',
        status: 'unhealthy',
        enabled: true,
        container_id: 'jkl012mno',
        image: 'ghcr.io/project/nemotron:latest',
        port: 8002,
        failure_count: 3,
        restart_count: 5,
        last_restart_at: '2026-01-25T11:00:00Z',
        uptime_seconds: 1800,
      },
      {
        name: 'grafana',
        display_name: 'Grafana',
        category: 'monitoring',
        status: 'running',
        enabled: true,
        container_id: 'mno345pqr',
        image: 'grafana/grafana:latest',
        port: 3000,
        failure_count: 0,
        restart_count: 0,
        last_restart_at: null,
        uptime_seconds: 172800,
      },
    ],
    by_category: {
      infrastructure: { total: 2, healthy: 2, unhealthy: 0 },
      ai: { total: 2, healthy: 1, unhealthy: 1 },
      monitoring: { total: 1, healthy: 1, unhealthy: 0 },
    },
    timestamp: '2026-01-25T12:00:00Z',
  };

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockFetchContainerServices.mockResolvedValue(mockContainerServicesResponse);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  const defaultProps: ContainersPanelProps = {
    pollingInterval: 30000,
  };

  describe('rendering', () => {
    it('renders the component with title', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('containers-panel')).toBeInTheDocument();
      });

      expect(screen.getByText('Containers')).toBeInTheDocument();
    });

    it('renders loading state initially', () => {
      // Make fetchContainerServices pending
      mockFetchContainerServices.mockImplementation(() => new Promise(() => {}));

      render(<ContainersPanel {...defaultProps} />);

      expect(screen.getByTestId('containers-panel-loading')).toBeInTheDocument();
    });

    it('renders error state when API fails', async () => {
      mockFetchContainerServices.mockRejectedValue(new Error('Network error'));

      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('containers-panel-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Failed to load containers')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('renders total running badge', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('containers-total-badge')).toBeInTheDocument();
      });

      // 4 running, 1 unhealthy = 4/5
      expect(screen.getByTestId('containers-total-badge')).toHaveTextContent('4/5 Running');
    });
  });

  describe('category grouping', () => {
    it('renders all three category groups', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('category-group-infrastructure')).toBeInTheDocument();
      });

      expect(screen.getByTestId('category-group-ai')).toBeInTheDocument();
      expect(screen.getByTestId('category-group-monitoring')).toBeInTheDocument();
    });

    it('renders category labels', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getAllByText('Infrastructure').length).toBeGreaterThanOrEqual(1);
      });

      expect(screen.getAllByText('AI Services').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Monitoring').length).toBeGreaterThanOrEqual(1);
    });

    it('renders category summary bar', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('category-summary-bar')).toBeInTheDocument();
      });

      expect(screen.getByTestId('category-summary-infrastructure')).toBeInTheDocument();
      expect(screen.getByTestId('category-summary-ai')).toBeInTheDocument();
      expect(screen.getByTestId('category-summary-monitoring')).toBeInTheDocument();
    });

    it('displays correct health counts per category', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('category-badge-infrastructure')).toBeInTheDocument();
      });

      // Infrastructure: 2 healthy, 0 unhealthy
      expect(screen.getByTestId('category-badge-infrastructure')).toHaveTextContent('2/2');

      // AI: 1 healthy, 1 unhealthy
      expect(screen.getByTestId('category-badge-ai')).toHaveTextContent('1/2');

      // Monitoring: 1 healthy, 0 unhealthy
      expect(screen.getByTestId('category-badge-monitoring')).toHaveTextContent('1/1');
    });
  });

  describe('container cards', () => {
    it('renders container cards for all containers', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-card-postgres')).toBeInTheDocument();
      });

      expect(screen.getByTestId('container-card-redis')).toBeInTheDocument();
      expect(screen.getByTestId('container-card-rtdetr')).toBeInTheDocument();
      expect(screen.getByTestId('container-card-nemotron')).toBeInTheDocument();
      expect(screen.getByTestId('container-card-grafana')).toBeInTheDocument();
    });

    it('displays container names', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('PostgreSQL')).toBeInTheDocument();
      });

      expect(screen.getByText('Redis')).toBeInTheDocument();
      expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
      expect(screen.getByText('Nemotron')).toBeInTheDocument();
      expect(screen.getByText('Grafana')).toBeInTheDocument();
    });

    it('displays container ports', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText(':5432')).toBeInTheDocument();
      });

      expect(screen.getByText(':6379')).toBeInTheDocument();
      expect(screen.getByText(':8001')).toBeInTheDocument();
      expect(screen.getByText(':8002')).toBeInTheDocument();
      expect(screen.getByText(':3000')).toBeInTheDocument();
    });

    it('displays container IDs', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-card-postgres')).toBeInTheDocument();
      });

      // Container ID is conditionally rendered when present
      // Use getByText since Tremor Text doesn't pass through data-testid
      expect(screen.getByText('ID: abc123def')).toBeInTheDocument();
    });

    it('displays status badges for each container', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-status-badge-postgres')).toBeInTheDocument();
      });

      expect(screen.getByTestId('container-status-badge-redis')).toBeInTheDocument();
      expect(screen.getByTestId('container-status-badge-rtdetr')).toBeInTheDocument();
      expect(screen.getByTestId('container-status-badge-nemotron')).toBeInTheDocument();
    });
  });

  describe('status indicators', () => {
    it('shows running status correctly', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-status-badge-postgres')).toHaveTextContent('Running');
      });
    });

    it('shows unhealthy status correctly', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-status-badge-nemotron')).toHaveTextContent('Unhealthy');
      });
    });

    it('shows starting status correctly', async () => {
      mockFetchContainerServices.mockResolvedValue({
        ...mockContainerServicesResponse,
        services: [
          {
            ...mockContainerServicesResponse.services[0],
            status: 'starting',
            uptime_seconds: null,
          },
        ],
        by_category: {
          infrastructure: { total: 1, healthy: 0, unhealthy: 1 },
          ai: { total: 0, healthy: 0, unhealthy: 0 },
          monitoring: { total: 0, healthy: 0, unhealthy: 0 },
        },
      });

      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-status-badge-postgres')).toHaveTextContent('Starting');
      });
    });

    it('shows stopped status correctly', async () => {
      mockFetchContainerServices.mockResolvedValue({
        ...mockContainerServicesResponse,
        services: [
          {
            ...mockContainerServicesResponse.services[0],
            status: 'stopped',
            uptime_seconds: null,
          },
        ],
        by_category: {
          infrastructure: { total: 1, healthy: 0, unhealthy: 1 },
          ai: { total: 0, healthy: 0, unhealthy: 0 },
          monitoring: { total: 0, healthy: 0, unhealthy: 0 },
        },
      });

      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-status-badge-postgres')).toHaveTextContent('Stopped');
      });
    });

    it('shows disabled status correctly', async () => {
      mockFetchContainerServices.mockResolvedValue({
        ...mockContainerServicesResponse,
        services: [
          {
            ...mockContainerServicesResponse.services[0],
            status: 'disabled',
            uptime_seconds: null,
            enabled: false,
          },
        ],
        by_category: {
          infrastructure: { total: 1, healthy: 0, unhealthy: 1 },
          ai: { total: 0, healthy: 0, unhealthy: 0 },
          monitoring: { total: 0, healthy: 0, unhealthy: 0 },
        },
      });

      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-status-badge-postgres')).toHaveTextContent('Disabled');
      });
    });
  });

  describe('uptime display', () => {
    it('displays uptime in days and hours format', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-card-postgres')).toBeInTheDocument();
      });

      // postgres has 86400 seconds = 1d 0h
      // Use getByText since Tremor Text doesn't pass through data-testid
      expect(screen.getByText('1d 0h')).toBeInTheDocument();
    });

    it('displays uptime in hours and minutes format', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-card-redis')).toBeInTheDocument();
      });

      // redis has 3600 seconds = 1h 0m
      expect(screen.getByText('1h 0m')).toBeInTheDocument();
    });

    it('displays uptime in minutes format', async () => {
      mockFetchContainerServices.mockResolvedValue({
        ...mockContainerServicesResponse,
        services: [
          {
            ...mockContainerServicesResponse.services[0],
            uptime_seconds: 300,
          },
        ],
        by_category: {
          infrastructure: { total: 1, healthy: 1, unhealthy: 0 },
          ai: { total: 0, healthy: 0, unhealthy: 0 },
          monitoring: { total: 0, healthy: 0, unhealthy: 0 },
        },
      });

      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-card-postgres')).toBeInTheDocument();
      });

      expect(screen.getByText('5m')).toBeInTheDocument();
    });

    it('does not display uptime when null', async () => {
      mockFetchContainerServices.mockResolvedValue({
        ...mockContainerServicesResponse,
        services: [
          {
            ...mockContainerServicesResponse.services[0],
            status: 'stopped',
            uptime_seconds: null,
          },
        ],
        by_category: {
          infrastructure: { total: 1, healthy: 0, unhealthy: 1 },
          ai: { total: 0, healthy: 0, unhealthy: 0 },
          monitoring: { total: 0, healthy: 0, unhealthy: 0 },
        },
      });

      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-card-postgres')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('container-uptime-postgres')).not.toBeInTheDocument();
    });
  });

  describe('restart count display', () => {
    it('displays restart count when greater than 0', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-card-redis')).toBeInTheDocument();
      });

      // redis has 2 restarts
      // Use getByText since Tremor Text doesn't pass through data-testid
      expect(screen.getByText('2 restarts')).toBeInTheDocument();
    });

    it('does not display restart count when 0', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-card-postgres')).toBeInTheDocument();
      });

      // postgres has 0 restarts
      expect(screen.queryByTestId('container-restarts-postgres')).not.toBeInTheDocument();
    });
  });

  describe('failure count display', () => {
    it('displays failure count badge when greater than 0', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        // nemotron has 3 failures
        expect(screen.getByTestId('container-failures-nemotron')).toHaveTextContent('3 failures');
      });
    });

    it('does not display failure count when 0', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-card-postgres')).toBeInTheDocument();
      });

      // postgres has 0 failures
      expect(screen.queryByTestId('container-failures-postgres')).not.toBeInTheDocument();
    });
  });

  describe('polling', () => {
    it('polls container data at specified interval', async () => {
      render(<ContainersPanel {...defaultProps} pollingInterval={5000} />);

      await waitFor(() => {
        expect(screen.getByTestId('containers-panel')).toBeInTheDocument();
      });

      // Initial fetch
      expect(mockFetchContainerServices).toHaveBeenCalledTimes(1);

      // Advance timer by polling interval
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      expect(mockFetchContainerServices).toHaveBeenCalledTimes(2);

      // Advance again
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      expect(mockFetchContainerServices).toHaveBeenCalledTimes(3);
    });

    it('does not poll when pollingInterval is 0', async () => {
      render(<ContainersPanel {...defaultProps} pollingInterval={0} />);

      await waitFor(() => {
        expect(screen.getByTestId('containers-panel')).toBeInTheDocument();
      });

      // Initial fetch
      expect(mockFetchContainerServices).toHaveBeenCalledTimes(1);

      // Advance timer
      act(() => {
        vi.advanceTimersByTime(60000);
      });

      // Still only 1 call (no polling)
      expect(mockFetchContainerServices).toHaveBeenCalledTimes(1);
    });
  });

  describe('timestamp display', () => {
    it('renders timestamp when present', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('containers-panel')).toBeInTheDocument();
      });

      // Timestamp is rendered when data is present
      // Use regex since the exact time varies
      expect(screen.getByText(/Last updated:/)).toBeInTheDocument();
    });
  });

  describe('className prop', () => {
    it('applies custom className', async () => {
      render(<ContainersPanel {...defaultProps} className="custom-class" />);

      await waitFor(() => {
        expect(screen.getByTestId('containers-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('containers-panel')).toHaveClass('custom-class');
    });
  });

  describe('empty categories', () => {
    it('does not render empty category groups', async () => {
      mockFetchContainerServices.mockResolvedValue({
        services: [mockContainerServicesResponse.services[0]], // Only postgres (infrastructure)
        by_category: {
          infrastructure: { total: 1, healthy: 1, unhealthy: 0 },
          ai: { total: 0, healthy: 0, unhealthy: 0 },
          monitoring: { total: 0, healthy: 0, unhealthy: 0 },
        },
        timestamp: '2026-01-25T12:00:00Z',
      });

      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('category-group-infrastructure')).toBeInTheDocument();
      });

      // AI and monitoring groups should not be rendered since they have no containers
      expect(screen.queryByTestId('category-group-ai')).not.toBeInTheDocument();
      expect(screen.queryByTestId('category-group-monitoring')).not.toBeInTheDocument();
    });
  });

  describe('mixed status scenarios', () => {
    it('displays mixed health states correctly', async () => {
      render(<ContainersPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('container-status-badge-postgres')).toHaveTextContent('Running');
      });

      expect(screen.getByTestId('container-status-badge-nemotron')).toHaveTextContent('Unhealthy');

      // Total badge should reflect 4/5 running
      expect(screen.getByTestId('containers-total-badge')).toHaveTextContent('4/5 Running');

      // AI category should show 1/2 healthy
      expect(screen.getByTestId('category-badge-ai')).toHaveTextContent('1/2');
    });
  });

  describe('data-testid prop', () => {
    it('uses custom data-testid when provided', async () => {
      render(<ContainersPanel {...defaultProps} data-testid="custom-containers-panel" />);

      await waitFor(() => {
        expect(screen.getByTestId('custom-containers-panel')).toBeInTheDocument();
      });
    });
  });
});
