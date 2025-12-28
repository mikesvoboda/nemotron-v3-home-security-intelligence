import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import Header from './Header';
import * as useHealthStatusModule from '../../hooks/useHealthStatus';
import * as useSystemStatusModule from '../../hooks/useSystemStatus';

describe('Header', () => {
  beforeEach(() => {
    // Mock useSystemStatus to return null status (disconnected state)
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: null,
      isConnected: false,
    });

    // Mock useHealthStatus to return loading state
    vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
      health: null,
      isLoading: true,
      error: null,
      overallStatus: null,
      services: {},
      refresh: vi.fn(),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    render(<Header />);
    expect(screen.getByRole('banner')).toBeInTheDocument();
  });

  it('displays the NVIDIA SECURITY title', () => {
    render(<Header />);
    expect(screen.getByText('NVIDIA SECURITY')).toBeInTheDocument();
  });

  it('displays the POWERED BY NEMOTRON subtitle', () => {
    render(<Header />);
    expect(screen.getByText('POWERED BY NEMOTRON')).toBeInTheDocument();
  });

  it('renders the Activity icon', () => {
    const { container } = render(<Header />);
    // Check for the icon container with NVIDIA green background
    const iconContainer = container.querySelector('.bg-\\[\\#76B900\\]');
    expect(iconContainer).toBeInTheDocument();
  });

  it('displays Connecting status when disconnected', () => {
    render(<Header />);
    expect(screen.getByText('Connecting...')).toBeInTheDocument();
  });

  it('displays Checking status when health is loading', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'healthy',
        gpu_utilization: 45,
        gpu_temperature: 65,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 3,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
      health: null,
      isLoading: true,
      error: null,
      overallStatus: null,
      services: {},
      refresh: vi.fn(),
    });

    render(<Header />);
    expect(screen.getByText('Checking...')).toBeInTheDocument();
  });

  it('displays LIVE MONITORING status when connected and healthy', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'healthy',
        gpu_utilization: 45,
        gpu_temperature: 65,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 3,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
      health: {
        status: 'healthy',
        services: {
          database: { status: 'healthy', message: 'OK' },
        },
        timestamp: '2025-12-23T10:00:00Z',
      },
      isLoading: false,
      error: null,
      overallStatus: 'healthy',
      services: {
        database: { status: 'healthy', message: 'OK' },
      },
      refresh: vi.fn(),
    });

    render(<Header />);
    expect(screen.getByText('LIVE MONITORING')).toBeInTheDocument();
  });

  it('displays GPU stats placeholder when no data', () => {
    render(<Header />);
    expect(screen.getByText('GPU:')).toBeInTheDocument();
    expect(screen.getByText('--')).toBeInTheDocument();
  });

  it('has correct header styling classes', () => {
    render(<Header />);
    const header = screen.getByRole('banner');
    expect(header).toHaveClass('h-16', 'bg-[#1A1A1A]', 'border-b', 'border-gray-800');
  });

  it('renders title with correct styling', () => {
    render(<Header />);
    const title = screen.getByText('NVIDIA SECURITY');
    expect(title).toHaveClass('text-lg', 'font-bold', 'text-white', 'tracking-wide');
  });

  it('renders subtitle with NVIDIA green color', () => {
    render(<Header />);
    const subtitle = screen.getByText('POWERED BY NEMOTRON');
    expect(subtitle).toHaveClass('text-xs', 'text-[#76B900]', 'font-medium', 'tracking-wider');
  });

  it('has proper flex layout structure', () => {
    render(<Header />);
    const header = screen.getByRole('banner');
    expect(header).toHaveClass('flex', 'items-center', 'justify-between');
  });

  it('renders GPU stats with correct styling', () => {
    const { container } = render(<Header />);
    const gpuStats = container.querySelector('.bg-gray-800.rounded-lg');
    expect(gpuStats).toBeInTheDocument();
  });

  it('GPU value has NVIDIA green color', () => {
    render(<Header />);
    const gpuValue = screen.getByText('--');
    expect(gpuValue).toHaveClass('text-[#76B900]');
  });

  it('contains accessibility attributes for header element', () => {
    render(<Header />);
    const header = screen.getByRole('banner');
    expect(header.tagName).toBe('HEADER');
  });

  it('displays GPU utilization when available', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'healthy',
        gpu_utilization: 75.5,
        gpu_temperature: null,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 3,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
      health: null,
      isLoading: false,
      error: null,
      overallStatus: 'healthy',
      services: {},
      refresh: vi.fn(),
    });

    render(<Header />);
    expect(screen.getByText('76%')).toBeInTheDocument();
  });

  it('displays GPU temperature when available', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'healthy',
        gpu_utilization: null,
        gpu_temperature: 65.7,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 3,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
      health: null,
      isLoading: false,
      error: null,
      overallStatus: 'healthy',
      services: {},
      refresh: vi.fn(),
    });

    render(<Header />);
    expect(screen.getByText('66°C')).toBeInTheDocument();
  });

  it('displays both GPU utilization and temperature when available', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'healthy',
        gpu_utilization: 45.2,
        gpu_temperature: 62.8,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 3,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
      health: null,
      isLoading: false,
      error: null,
      overallStatus: 'healthy',
      services: {},
      refresh: vi.fn(),
    });

    render(<Header />);
    expect(screen.getByText('45% | 63°C')).toBeInTheDocument();
  });

  it('displays System Degraded status when system is degraded', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'degraded',
        gpu_utilization: 85,
        gpu_temperature: 75,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 1,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
      health: null,
      isLoading: false,
      error: null,
      overallStatus: 'degraded',
      services: {},
      refresh: vi.fn(),
    });

    render(<Header />);
    expect(screen.getByText('System Degraded')).toBeInTheDocument();
  });

  it('displays System Offline status when system is unhealthy', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'unhealthy',
        gpu_utilization: 100,
        gpu_temperature: 90,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 0,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
      health: null,
      isLoading: false,
      error: null,
      overallStatus: 'unhealthy',
      services: {},
      refresh: vi.fn(),
    });

    render(<Header />);
    expect(screen.getByText('System Offline')).toBeInTheDocument();
  });

  it('shows yellow status dot for degraded system', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'degraded',
        gpu_utilization: 85,
        gpu_temperature: 75,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 1,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
      health: null,
      isLoading: false,
      error: null,
      overallStatus: 'degraded',
      services: {},
      refresh: vi.fn(),
    });

    render(<Header />);
    const statusDot = screen.getByTestId('health-dot');
    expect(statusDot).toHaveClass('bg-yellow-500');
  });

  it('shows red status dot for unhealthy system', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'unhealthy',
        gpu_utilization: 100,
        gpu_temperature: 90,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 0,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
      health: null,
      isLoading: false,
      error: null,
      overallStatus: 'unhealthy',
      services: {},
      refresh: vi.fn(),
    });

    render(<Header />);
    const statusDot = screen.getByTestId('health-dot');
    expect(statusDot).toHaveClass('bg-red-500');
  });

  it('shows green status dot for healthy system', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'healthy',
        gpu_utilization: 45,
        gpu_temperature: 65,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 3,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
      health: null,
      isLoading: false,
      error: null,
      overallStatus: 'healthy',
      services: {},
      refresh: vi.fn(),
    });

    render(<Header />);
    const statusDot = screen.getByTestId('health-dot');
    expect(statusDot).toHaveClass('bg-green-500');
  });

  describe('Health Tooltip', () => {
    it('shows tooltip on hover with service details', () => {
      vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
        status: {
          health: 'healthy',
          gpu_utilization: 45,
          gpu_temperature: 65,
          gpu_memory_used: 8192,
          gpu_memory_total: 24576,
          active_cameras: 3,
          last_update: '2025-12-23T10:00:00Z',
        },
        isConnected: true,
      });

      vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
        health: {
          status: 'healthy',
          services: {
            database: { status: 'healthy', message: 'OK' },
            redis: { status: 'healthy', message: 'Connected' },
            ai: { status: 'healthy', message: 'Running' },
          },
          timestamp: '2025-12-23T10:00:00Z',
        },
        isLoading: false,
        error: null,
        overallStatus: 'healthy',
        services: {
          database: { status: 'healthy', message: 'OK' },
          redis: { status: 'healthy', message: 'Connected' },
          ai: { status: 'healthy', message: 'Running' },
        },
        refresh: vi.fn(),
      });

      render(<Header />);

      // Tooltip should not be visible initially
      expect(screen.queryByTestId('health-tooltip')).not.toBeInTheDocument();

      // Hover over the health indicator
      const healthIndicator = screen.getByTestId('health-indicator');
      fireEvent.mouseEnter(healthIndicator);

      // Tooltip should now be visible
      expect(screen.getByTestId('health-tooltip')).toBeInTheDocument();

      // Check service details are displayed
      expect(screen.getByText('Service Status')).toBeInTheDocument();
      expect(screen.getByText('database')).toBeInTheDocument();
      expect(screen.getByText('redis')).toBeInTheDocument();
      expect(screen.getByText('ai')).toBeInTheDocument();
    });

    it('hides tooltip on mouse leave after delay', async () => {
      vi.useFakeTimers();

      vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
        status: {
          health: 'healthy',
          gpu_utilization: 45,
          gpu_temperature: 65,
          gpu_memory_used: 8192,
          gpu_memory_total: 24576,
          active_cameras: 3,
          last_update: '2025-12-23T10:00:00Z',
        },
        isConnected: true,
      });

      vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
        health: {
          status: 'healthy',
          services: {
            database: { status: 'healthy', message: 'OK' },
          },
          timestamp: '2025-12-23T10:00:00Z',
        },
        isLoading: false,
        error: null,
        overallStatus: 'healthy',
        services: {
          database: { status: 'healthy', message: 'OK' },
        },
        refresh: vi.fn(),
      });

      render(<Header />);

      const healthIndicator = screen.getByTestId('health-indicator');

      // Hover to show tooltip
      fireEvent.mouseEnter(healthIndicator);
      expect(screen.getByTestId('health-tooltip')).toBeInTheDocument();

      // Mouse leave
      fireEvent.mouseLeave(healthIndicator);

      // Tooltip should still be visible (150ms delay)
      expect(screen.getByTestId('health-tooltip')).toBeInTheDocument();

      // Advance timers past the delay
      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });

      // Tooltip should be hidden
      expect(screen.queryByTestId('health-tooltip')).not.toBeInTheDocument();

      vi.useRealTimers();
    });

    it('does not show tooltip when no services available', () => {
      vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
        status: {
          health: 'healthy',
          gpu_utilization: 45,
          gpu_temperature: 65,
          gpu_memory_used: 8192,
          gpu_memory_total: 24576,
          active_cameras: 3,
          last_update: '2025-12-23T10:00:00Z',
        },
        isConnected: true,
      });

      vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
        health: null,
        isLoading: false,
        error: null,
        overallStatus: 'healthy',
        services: {},
        refresh: vi.fn(),
      });

      render(<Header />);

      const healthIndicator = screen.getByTestId('health-indicator');
      fireEvent.mouseEnter(healthIndicator);

      // Even on hover, tooltip should not appear if no services
      expect(screen.queryByTestId('health-tooltip')).not.toBeInTheDocument();
    });

    it('shows correct service status colors in tooltip', () => {
      vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
        status: {
          health: 'degraded',
          gpu_utilization: 45,
          gpu_temperature: 65,
          gpu_memory_used: 8192,
          gpu_memory_total: 24576,
          active_cameras: 3,
          last_update: '2025-12-23T10:00:00Z',
        },
        isConnected: true,
      });

      vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
        health: {
          status: 'degraded',
          services: {
            database: { status: 'healthy', message: 'OK' },
            redis: { status: 'unhealthy', message: 'Connection failed' },
            ai: { status: 'degraded', message: 'High latency' },
          },
          timestamp: '2025-12-23T10:00:00Z',
        },
        isLoading: false,
        error: null,
        overallStatus: 'degraded',
        services: {
          database: { status: 'healthy', message: 'OK' },
          redis: { status: 'unhealthy', message: 'Connection failed' },
          ai: { status: 'degraded', message: 'High latency' },
        },
        refresh: vi.fn(),
      });

      render(<Header />);

      const healthIndicator = screen.getByTestId('health-indicator');
      fireEvent.mouseEnter(healthIndicator);

      expect(screen.getByTestId('health-tooltip')).toBeInTheDocument();

      // Check service dots have correct colors
      const databaseDot = screen.getByTestId('service-dot-database');
      const redisDot = screen.getByTestId('service-dot-redis');
      const aiDot = screen.getByTestId('service-dot-ai');

      expect(databaseDot).toHaveClass('bg-green-500');
      expect(redisDot).toHaveClass('bg-red-500');
      expect(aiDot).toHaveClass('bg-yellow-500');
    });

    it('has cursor-pointer on health indicator', () => {
      vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
        status: {
          health: 'healthy',
          gpu_utilization: 45,
          gpu_temperature: 65,
          gpu_memory_used: 8192,
          gpu_memory_total: 24576,
          active_cameras: 3,
          last_update: '2025-12-23T10:00:00Z',
        },
        isConnected: true,
      });

      vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
        health: null,
        isLoading: false,
        error: null,
        overallStatus: 'healthy',
        services: {},
        refresh: vi.fn(),
      });

      render(<Header />);

      const healthIndicator = screen.getByTestId('health-indicator');
      expect(healthIndicator).toHaveClass('cursor-pointer');
    });
  });

  describe('API health takes precedence over WebSocket health', () => {
    it('uses API health when both are available', () => {
      vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
        status: {
          health: 'healthy', // WebSocket says healthy
          gpu_utilization: 45,
          gpu_temperature: 65,
          gpu_memory_used: 8192,
          gpu_memory_total: 24576,
          active_cameras: 3,
          last_update: '2025-12-23T10:00:00Z',
        },
        isConnected: true,
      });

      vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
        health: {
          status: 'degraded',
          services: {
            database: { status: 'unhealthy', message: 'Error' },
          },
          timestamp: '2025-12-23T10:00:00Z',
        },
        isLoading: false,
        error: null,
        overallStatus: 'degraded', // API says degraded
        services: {
          database: { status: 'unhealthy', message: 'Error' },
        },
        refresh: vi.fn(),
      });

      render(<Header />);

      // Should show degraded status (from API) not healthy (from WebSocket)
      expect(screen.getByText('System Degraded')).toBeInTheDocument();
      const statusDot = screen.getByTestId('health-dot');
      expect(statusDot).toHaveClass('bg-yellow-500');
    });

    it('falls back to WebSocket health when API health is null', () => {
      vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
        status: {
          health: 'healthy',
          gpu_utilization: 45,
          gpu_temperature: 65,
          gpu_memory_used: 8192,
          gpu_memory_total: 24576,
          active_cameras: 3,
          last_update: '2025-12-23T10:00:00Z',
        },
        isConnected: true,
      });

      vi.spyOn(useHealthStatusModule, 'useHealthStatus').mockReturnValue({
        health: null,
        isLoading: false,
        error: 'Failed to fetch',
        overallStatus: null, // API failed
        services: {},
        refresh: vi.fn(),
      });

      render(<Header />);

      // Should fall back to WebSocket healthy status
      expect(screen.getByText('LIVE MONITORING')).toBeInTheDocument();
      const statusDot = screen.getByTestId('health-dot');
      expect(statusDot).toHaveClass('bg-green-500');
    });
  });
});
