import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import Header from './Header';
import * as useConnectionStatusModule from '../../hooks/useConnectionStatus';
import * as useHealthStatusQueryModule from '../../hooks/useHealthStatusQuery';

import type { ChannelStatus, ConnectionState } from '../../hooks/useWebSocketStatus';

// Helper to render Header with Router context
const renderHeader = (initialRoute: string = '/') => {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <Header />
    </MemoryRouter>
  );
};

// Mock the useSidebarContext hook
const mockToggleMobileMenu = vi.fn();

vi.mock('../../hooks/useSidebarContext', () => ({
  useSidebarContext: () => ({
    isMobileMenuOpen: false,
    setMobileMenuOpen: vi.fn(),
    toggleMobileMenu: mockToggleMobileMenu,
  }),
}));

// Mock the useCommandPaletteContext hook
const mockOpenCommandPalette = vi.fn();

vi.mock('../../hooks/useCommandPaletteContext', () => ({
  useCommandPaletteContext: () => ({
    openCommandPalette: mockOpenCommandPalette,
  }),
}));

// Mock the useAIServiceStatus hook
vi.mock('../../hooks/useAIServiceStatus', () => ({
  useAIServiceStatus: () => ({
    degradationMode: 'normal' as const,
    services: {
      rtdetr: {
        service: 'rtdetr',
        status: 'healthy',
        circuit_state: 'closed',
        last_success: '2024-01-15T12:00:00Z',
        failure_count: 0,
        error_message: null,
        last_check: '2024-01-15T12:00:00Z',
      },
      nemotron: {
        service: 'nemotron',
        status: 'healthy',
        circuit_state: 'closed',
        last_success: '2024-01-15T12:00:00Z',
        failure_count: 0,
        error_message: null,
        last_check: '2024-01-15T12:00:00Z',
      },
      florence: {
        service: 'florence',
        status: 'healthy',
        circuit_state: 'closed',
        last_success: '2024-01-15T12:00:00Z',
        failure_count: 0,
        error_message: null,
        last_check: '2024-01-15T12:00:00Z',
      },
      clip: {
        service: 'clip',
        status: 'healthy',
        circuit_state: 'closed',
        last_success: '2024-01-15T12:00:00Z',
        failure_count: 0,
        error_message: null,
        last_check: '2024-01-15T12:00:00Z',
      },
    },
    availableFeatures: ['object_detection', 'risk_analysis', 'image_captioning', 'entity_tracking'],
    hasUnavailableService: false,
    isOffline: false,
    isDegraded: false,
    getServiceState: vi.fn(),
    isFeatureAvailable: vi.fn(),
    lastUpdate: '2024-01-15T12:00:00Z',
  }),
}));

// Helper to create mock channel status
function createMockChannel(
  name: string,
  state: ConnectionState = 'disconnected',
  reconnectAttempts: number = 0
): ChannelStatus {
  return {
    name,
    state,
    reconnectAttempts,
    maxReconnectAttempts: 5,
    lastMessageTime: state === 'connected' ? new Date() : null,
    hasExhaustedRetries: state === 'failed',
  };
}

// Helper to create mock connection status return value
function createMockConnectionStatus(
  eventsState: ConnectionState = 'disconnected',
  systemState: ConnectionState = 'disconnected',
  systemStatus: ReturnType<
    typeof useConnectionStatusModule.useConnectionStatus
  >['systemStatus'] = null
): ReturnType<typeof useConnectionStatusModule.useConnectionStatus> {
  const eventsChannel = createMockChannel('Events', eventsState);
  const systemChannel = createMockChannel('System', systemState);

  const allConnected = eventsState === 'connected' && systemState === 'connected';
  const anyReconnecting = eventsState === 'reconnecting' || systemState === 'reconnecting';

  let overallState: ConnectionState;
  if (allConnected) {
    overallState = 'connected';
  } else if (anyReconnecting) {
    overallState = 'reconnecting';
  } else {
    overallState = 'disconnected';
  }

  return {
    summary: {
      eventsChannel,
      systemChannel,
      overallState,
      anyReconnecting,
      allConnected,
      totalReconnectAttempts: eventsChannel.reconnectAttempts + systemChannel.reconnectAttempts,
      hasExhaustedRetries: eventsChannel.hasExhaustedRetries || systemChannel.hasExhaustedRetries,
      allFailed: eventsState === 'failed' && systemState === 'failed',
      disconnectedSince: allConnected ? null : new Date(),
    },
    events: [],
    systemStatus,
    clearEvents: vi.fn(),
    isPollingFallback: false,
    retryConnection: vi.fn(),
  };
}

describe('Header', () => {
  beforeEach(() => {
    // Mock useConnectionStatus to return disconnected state
    vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
      createMockConnectionStatus('disconnected', 'disconnected', null)
    );

    // Mock useHealthStatusQuery to return loading state
    vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
      data: undefined,
      isLoading: true,
      isRefetching: false,
      error: null,
      isStale: false,
      overallStatus: null,
      services: {},
      refetch: vi.fn().mockResolvedValue({}),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    renderHeader();
    expect(screen.getByRole('banner')).toBeInTheDocument();
  });

  it('displays the NVIDIA logo with branding text', () => {
    renderHeader();
    expect(screen.getByText('Powered by Nemotron v3 Nano')).toBeInTheDocument();
  });

  it('displays the Powered by text with NVIDIA green color', () => {
    renderHeader();
    const text = screen.getByText('Powered by Nemotron v3 Nano');
    expect(text).toHaveClass('text-[#76B900]');
  });

  it('renders the NVIDIA logo', () => {
    renderHeader();
    const logo = screen.getByAltText('NVIDIA');
    expect(logo).toBeInTheDocument();
    expect(logo).toHaveAttribute('src', '/images/nvidia-logo-white.svg');
  });

  it('displays Connecting status when disconnected', () => {
    renderHeader();
    expect(screen.getByText('Connecting...')).toBeInTheDocument();
  });

  it('displays Checking status when health is loading', () => {
    const systemStatus = {
      type: 'system_status' as const,
      data: {
        gpu: {
          utilization: 45,
          memory_used: 8192,
          memory_total: 24576,
          temperature: 65,
          inference_fps: 30.5,
        },
        cameras: { active: 3, total: 5 },
        queue: { pending: 0, processing: 0 },
        health: 'healthy' as const,
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
      createMockConnectionStatus('connected', 'connected', systemStatus)
    );

    vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
      data: undefined,
      isLoading: true,
      isRefetching: false,
      error: null,
      isStale: false,
      overallStatus: null,
      services: {},
      refetch: vi.fn().mockResolvedValue({}),
    });

    renderHeader();
    expect(screen.getByText('Checking...')).toBeInTheDocument();
  });

  it('displays LIVE MONITORING status when connected and healthy', () => {
    const systemStatus = {
      type: 'system_status' as const,
      data: {
        gpu: {
          utilization: 45,
          memory_used: 8192,
          memory_total: 24576,
          temperature: 65,
          inference_fps: 30.5,
        },
        cameras: { active: 3, total: 5 },
        queue: { pending: 0, processing: 0 },
        health: 'healthy' as const,
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
      createMockConnectionStatus('connected', 'connected', systemStatus)
    );

    vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
      data: {
        status: 'healthy',
        services: {
          database: { status: 'healthy', message: 'OK' },
        },
        timestamp: '2025-12-23T10:00:00Z',
      },
      isLoading: false,
      isRefetching: false,
      error: null,
      isStale: false,
      overallStatus: 'healthy',
      services: {
        database: { status: 'healthy', message: 'OK' },
      },
      refetch: vi.fn().mockResolvedValue({}),
    });

    renderHeader();
    expect(screen.getByText('LIVE MONITORING')).toBeInTheDocument();
  });

  it('displays GPU stats placeholder when no data', () => {
    renderHeader();
    expect(screen.getByText('GPU:')).toBeInTheDocument();
    expect(screen.getByText('--')).toBeInTheDocument();
  });

  it('has correct header styling classes', () => {
    renderHeader();
    const header = screen.getByRole('banner');
    expect(header).toHaveClass('h-16', 'bg-[#1A1A1A]', 'border-b', 'border-gray-800');
  });

  it('renders branding text with correct styling', () => {
    renderHeader();
    const brandingText = screen.getByText('Powered by Nemotron v3 Nano');
    expect(brandingText).toHaveClass('text-[#76B900]', 'font-medium');
    // Has responsive text size classes
    expect(brandingText).toHaveClass('text-[9px]', 'md:text-[10px]');
  });

  it('renders logo with responsive sizing', () => {
    renderHeader();
    const logo = screen.getByAltText('NVIDIA');
    expect(logo).toHaveClass('h-6', 'w-auto', 'md:h-8');
  });

  it('has proper flex layout structure', () => {
    renderHeader();
    const header = screen.getByRole('banner');
    expect(header).toHaveClass('flex', 'items-center', 'justify-between');
  });

  it('renders GPU stats with correct styling', () => {
    const { container } = renderHeader();
    const gpuStats = container.querySelector('.bg-gray-800.rounded-lg');
    expect(gpuStats).toBeInTheDocument();
  });

  it('GPU value has NVIDIA green color', () => {
    renderHeader();
    const gpuValue = screen.getByText('--');
    expect(gpuValue).toHaveClass('text-[#76B900]');
  });

  it('contains accessibility attributes for header element', () => {
    renderHeader();
    const header = screen.getByRole('banner');
    expect(header.tagName).toBe('HEADER');
  });

  it('displays GPU utilization when available', () => {
    const systemStatus = {
      type: 'system_status' as const,
      data: {
        gpu: {
          utilization: 75.5,
          memory_used: 8192,
          memory_total: 24576,
          temperature: null,
          inference_fps: 30.5,
        },
        cameras: { active: 3, total: 5 },
        queue: { pending: 0, processing: 0 },
        health: 'healthy' as const,
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
      createMockConnectionStatus('connected', 'connected', systemStatus)
    );

    vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
      data: undefined,
      isLoading: false,
      isRefetching: false,
      error: null,
      isStale: false,
      overallStatus: 'healthy',
      services: {},
      refetch: vi.fn().mockResolvedValue({}),
    });

    renderHeader();
    expect(screen.getByText('76% | 30.5 FPS')).toBeInTheDocument();
  });

  it('displays GPU temperature when available', () => {
    const systemStatus = {
      type: 'system_status' as const,
      data: {
        gpu: {
          utilization: null,
          memory_used: 8192,
          memory_total: 24576,
          temperature: 65.7,
          inference_fps: 30.5,
        },
        cameras: { active: 3, total: 5 },
        queue: { pending: 0, processing: 0 },
        health: 'healthy' as const,
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
      createMockConnectionStatus('connected', 'connected', systemStatus)
    );

    vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
      data: undefined,
      isLoading: false,
      isRefetching: false,
      error: null,
      isStale: false,
      overallStatus: 'healthy',
      services: {},
      refetch: vi.fn().mockResolvedValue({}),
    });

    renderHeader();
    expect(screen.getByText('66°C | 30.5 FPS')).toBeInTheDocument();
  });

  it('displays both GPU utilization and temperature when available', () => {
    const systemStatus = {
      type: 'system_status' as const,
      data: {
        gpu: {
          utilization: 45.2,
          memory_used: 8192,
          memory_total: 24576,
          temperature: 62.8,
          inference_fps: 30.5,
        },
        cameras: { active: 3, total: 5 },
        queue: { pending: 0, processing: 0 },
        health: 'healthy' as const,
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
      createMockConnectionStatus('connected', 'connected', systemStatus)
    );

    vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
      data: undefined,
      isLoading: false,
      isRefetching: false,
      error: null,
      isStale: false,
      overallStatus: 'healthy',
      services: {},
      refetch: vi.fn().mockResolvedValue({}),
    });

    renderHeader();
    expect(screen.getByText('45% | 63°C | 30.5 FPS')).toBeInTheDocument();
  });

  it('displays System Degraded status when system is degraded', () => {
    const systemStatus = {
      type: 'system_status' as const,
      data: {
        gpu: {
          utilization: 85,
          memory_used: 8192,
          memory_total: 24576,
          temperature: 75,
          inference_fps: 30.5,
        },
        cameras: { active: 1, total: 5 },
        queue: { pending: 0, processing: 0 },
        health: 'degraded' as const,
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
      createMockConnectionStatus('connected', 'connected', systemStatus)
    );

    vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
      data: undefined,
      isLoading: false,
      isRefetching: false,
      error: null,
      isStale: false,
      overallStatus: 'degraded',
      services: {},
      refetch: vi.fn().mockResolvedValue({}),
    });

    renderHeader();
    expect(screen.getByText('System Degraded')).toBeInTheDocument();
  });

  it('displays System Offline status when system is unhealthy', () => {
    const systemStatus = {
      type: 'system_status' as const,
      data: {
        gpu: {
          utilization: 100,
          memory_used: 8192,
          memory_total: 24576,
          temperature: 90,
          inference_fps: 30.5,
        },
        cameras: { active: 0, total: 5 },
        queue: { pending: 0, processing: 0 },
        health: 'unhealthy' as const,
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
      createMockConnectionStatus('connected', 'connected', systemStatus)
    );

    vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
      data: undefined,
      isLoading: false,
      isRefetching: false,
      error: null,
      isStale: false,
      overallStatus: 'unhealthy',
      services: {},
      refetch: vi.fn().mockResolvedValue({}),
    });

    renderHeader();
    expect(screen.getByText('System Offline')).toBeInTheDocument();
  });

  it('shows yellow status dot for degraded system', () => {
    const systemStatus = {
      type: 'system_status' as const,
      data: {
        gpu: {
          utilization: 85,
          memory_used: 8192,
          memory_total: 24576,
          temperature: 75,
          inference_fps: 30.5,
        },
        cameras: { active: 1, total: 5 },
        queue: { pending: 0, processing: 0 },
        health: 'degraded' as const,
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
      createMockConnectionStatus('connected', 'connected', systemStatus)
    );

    vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
      data: undefined,
      isLoading: false,
      isRefetching: false,
      error: null,
      isStale: false,
      overallStatus: 'degraded',
      services: {},
      refetch: vi.fn().mockResolvedValue({}),
    });

    renderHeader();
    const statusDot = screen.getByTestId('health-dot');
    expect(statusDot).toHaveClass('bg-yellow-500');
  });

  it('shows red status dot for unhealthy system', () => {
    const systemStatus = {
      type: 'system_status' as const,
      data: {
        gpu: {
          utilization: 100,
          memory_used: 8192,
          memory_total: 24576,
          temperature: 90,
          inference_fps: 30.5,
        },
        cameras: { active: 0, total: 5 },
        queue: { pending: 0, processing: 0 },
        health: 'unhealthy' as const,
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
      createMockConnectionStatus('connected', 'connected', systemStatus)
    );

    vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
      data: undefined,
      isLoading: false,
      isRefetching: false,
      error: null,
      isStale: false,
      overallStatus: 'unhealthy',
      services: {},
      refetch: vi.fn().mockResolvedValue({}),
    });

    renderHeader();
    const statusDot = screen.getByTestId('health-dot');
    expect(statusDot).toHaveClass('bg-red-500');
  });

  it('shows green status dot for healthy system', () => {
    const systemStatus = {
      type: 'system_status' as const,
      data: {
        gpu: {
          utilization: 45,
          memory_used: 8192,
          memory_total: 24576,
          temperature: 65,
          inference_fps: 30.5,
        },
        cameras: { active: 3, total: 5 },
        queue: { pending: 0, processing: 0 },
        health: 'healthy' as const,
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
      createMockConnectionStatus('connected', 'connected', systemStatus)
    );

    vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
      data: undefined,
      isLoading: false,
      isRefetching: false,
      error: null,
      isStale: false,
      overallStatus: 'healthy',
      services: {},
      refetch: vi.fn().mockResolvedValue({}),
    });

    renderHeader();
    const statusDot = screen.getByTestId('health-dot');
    expect(statusDot).toHaveClass('bg-green-500');
  });

  describe('Health Tooltip', () => {
    it('shows tooltip on hover with service details', () => {
      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: 'healthy' as const,
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: {
          status: 'healthy',
          services: {
            database: { status: 'healthy', message: 'OK' },
            redis: { status: 'healthy', message: 'Connected' },
            ai: { status: 'healthy', message: 'Running' },
          },
          timestamp: '2025-12-23T10:00:00Z',
        },
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: 'healthy',
        services: {
          database: { status: 'healthy', message: 'OK' },
          redis: { status: 'healthy', message: 'Connected' },
          ai: { status: 'healthy', message: 'Running' },
        },
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();

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
      vi.useFakeTimers({ shouldAdvanceTime: true });

      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: 'healthy' as const,
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: {
          status: 'healthy',
          services: {
            database: { status: 'healthy', message: 'OK' },
          },
          timestamp: '2025-12-23T10:00:00Z',
        },
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: 'healthy',
        services: {
          database: { status: 'healthy', message: 'OK' },
        },
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();

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
      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: 'healthy' as const,
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: undefined,
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: 'healthy',
        services: {},
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();

      const healthIndicator = screen.getByTestId('health-indicator');
      fireEvent.mouseEnter(healthIndicator);

      // Even on hover, tooltip should not appear if no services
      expect(screen.queryByTestId('health-tooltip')).not.toBeInTheDocument();
    });

    it('shows correct service status colors in tooltip', () => {
      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: 'degraded' as const,
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: {
          status: 'degraded',
          services: {
            database: { status: 'healthy', message: 'OK' },
            redis: { status: 'unhealthy', message: 'Connection failed' },
            ai: { status: 'degraded', message: 'High latency' },
          },
          timestamp: '2025-12-23T10:00:00Z',
        },
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: 'degraded',
        services: {
          database: { status: 'healthy', message: 'OK' },
          redis: { status: 'unhealthy', message: 'Connection failed' },
          ai: { status: 'degraded', message: 'High latency' },
        },
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();

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
      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: 'healthy' as const,
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: undefined,
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: 'healthy',
        services: {},
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();

      const healthIndicator = screen.getByTestId('health-indicator');
      expect(healthIndicator).toHaveClass('cursor-pointer');
    });
  });

  describe('API health takes precedence over WebSocket health', () => {
    it('uses API health when both are available', () => {
      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: 'healthy' as const, // WebSocket says healthy
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: {
          status: 'degraded',
          services: {
            database: { status: 'unhealthy', message: 'Error' },
          },
          timestamp: '2025-12-23T10:00:00Z',
        },
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: 'degraded', // API says degraded
        services: {
          database: { status: 'unhealthy', message: 'Error' },
        },
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();

      // Should show degraded status (from API) not healthy (from WebSocket)
      expect(screen.getByText('System Degraded')).toBeInTheDocument();
      const statusDot = screen.getByTestId('health-dot');
      expect(statusDot).toHaveClass('bg-yellow-500');
    });

    it('falls back to WebSocket health when API health is null', () => {
      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: 'healthy' as const,
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: undefined,
        isLoading: false,
        isRefetching: false,
        error: new Error('Failed to fetch'),
        isStale: false,
        overallStatus: null, // API failed
        services: {},
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();

      // Should fall back to WebSocket healthy status
      expect(screen.getByText('LIVE MONITORING')).toBeInTheDocument();
      const statusDot = screen.getByTestId('health-dot');
      expect(statusDot).toHaveClass('bg-green-500');
    });
  });

  describe('WebSocket Status Component', () => {
    it('renders WebSocket status indicator', () => {
      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: 'healthy' as const,
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: undefined,
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: 'healthy',
        services: {},
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();

      expect(screen.getByTestId('websocket-status')).toBeInTheDocument();
    });

    it('shows WebSocket status tooltip on hover', () => {
      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: 'healthy' as const,
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: undefined,
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: 'healthy',
        services: {},
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();

      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));

      expect(screen.getByTestId('websocket-tooltip')).toBeInTheDocument();
      expect(screen.getByText('WebSocket Channels')).toBeInTheDocument();
    });
  });

  describe('Status Label Edge Cases', () => {
    it('shows Connecting... when not connected', () => {
      // Already covered by existing test, but adding explicit coverage for line 32
      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('disconnected', 'disconnected', null)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: undefined,
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: null,
        services: {},
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();
      expect(screen.getByText('Connecting...')).toBeInTheDocument();
    });

    it('shows Checking... when connected but health is unknown', () => {
      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: undefined as unknown as 'healthy' | 'degraded' | 'unhealthy',
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: undefined,
        isLoading: true,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: null,
        services: {},
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();
      expect(screen.getByText('Checking...')).toBeInTheDocument();
    });
  });

  describe('Tooltip Timeout Management', () => {
    it('clears existing timeout when mouse re-enters before timeout completes', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });

      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: 'healthy' as const,
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: {
          status: 'healthy',
          services: {
            database: { status: 'healthy', message: 'OK' },
          },
          timestamp: '2025-12-23T10:00:00Z',
        },
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: 'healthy',
        services: {
          database: { status: 'healthy', message: 'OK' },
        },
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();

      const healthIndicator = screen.getByTestId('health-indicator');

      // Show tooltip
      fireEvent.mouseEnter(healthIndicator);
      expect(screen.getByTestId('health-tooltip')).toBeInTheDocument();

      // Mouse leave (starts timeout)
      fireEvent.mouseLeave(healthIndicator);

      // Before timeout completes, mouse re-enters (should clear timeout)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50); // Only advance 50ms of the 150ms delay
      });

      fireEvent.mouseEnter(healthIndicator);

      // Tooltip should still be visible
      expect(screen.getByTestId('health-tooltip')).toBeInTheDocument();

      // Advance past the original timeout period
      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });

      // Tooltip should STILL be visible because the timeout was cleared
      expect(screen.getByTestId('health-tooltip')).toBeInTheDocument();

      vi.useRealTimers();
    });

    it('cleans up timeout on component unmount', () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });

      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: 'healthy' as const,
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: {
          status: 'healthy',
          services: {
            database: { status: 'healthy', message: 'OK' },
          },
          timestamp: '2025-12-23T10:00:00Z',
        },
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: 'healthy',
        services: {
          database: { status: 'healthy', message: 'OK' },
        },
        refetch: vi.fn().mockResolvedValue({}),
      });

      const { unmount } = renderHeader();

      const healthIndicator = screen.getByTestId('health-indicator');

      // Show tooltip and start hide timer
      fireEvent.mouseEnter(healthIndicator);
      fireEvent.mouseLeave(healthIndicator);

      // Unmount component before timeout completes
      unmount();

      // No errors should occur - the cleanup function should clear the timeout
      expect(() => {
        vi.advanceTimersByTime(200);
      }).not.toThrow();

      vi.useRealTimers();
    });
  });

  describe('Polling Fallback Indicator', () => {
    it('shows REST Fallback indicator when polling fallback is active', () => {
      const mockStatus = createMockConnectionStatus('connected', 'connected', null);
      mockStatus.isPollingFallback = true;

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(mockStatus);

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: undefined,
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: 'healthy',
        services: {},
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();

      expect(screen.getByText('REST Fallback')).toBeInTheDocument();
    });

    it('does not show REST Fallback indicator when polling fallback is inactive', () => {
      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: 'healthy' as const,
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: undefined,
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: 'healthy',
        services: {},
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();

      expect(screen.queryByText('REST Fallback')).not.toBeInTheDocument();
    });
  });

  describe('Mobile Hamburger Menu', () => {
    it('renders hamburger menu button', () => {
      renderHeader();
      expect(screen.getByTestId('hamburger-menu')).toBeInTheDocument();
      expect(screen.getByLabelText('Open menu')).toBeInTheDocument();
    });

    it('calls toggleMobileMenu when hamburger button is clicked', () => {
      renderHeader();
      const hamburgerButton = screen.getByTestId('hamburger-menu');
      fireEvent.click(hamburgerButton);
      expect(mockToggleMobileMenu).toHaveBeenCalled();
    });

    it('hamburger button has md:hidden class for mobile-only visibility', () => {
      renderHeader();
      const hamburgerButton = screen.getByTestId('hamburger-menu');
      expect(hamburgerButton).toHaveClass('md:hidden');
    });
  });

  describe('Branding Alignment with Sidebar', () => {
    it('branding container has width matching sidebar (w-64) on desktop', () => {
      renderHeader();
      const brandingContainer = screen.getByTestId('header-branding');
      expect(brandingContainer).toHaveClass('md:w-64');
    });

    it('branding container has padding matching sidebar nav padding (px-4)', () => {
      renderHeader();
      const brandingContainer = screen.getByTestId('header-branding');
      expect(brandingContainer).toHaveClass('px-4');
    });

    it('branding container includes the NVIDIA logo and branding text', () => {
      renderHeader();
      const brandingContainer = screen.getByTestId('header-branding');
      expect(brandingContainer).toContainElement(screen.getByAltText('NVIDIA'));
      expect(brandingContainer).toContainElement(screen.getByText('Powered by Nemotron v3 Nano'));
    });
  });

  describe('Focus and Blur Events', () => {
    it('shows tooltip on focus', () => {
      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: 'healthy' as const,
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: {
          status: 'healthy',
          services: {
            database: { status: 'healthy', message: 'OK' },
          },
          timestamp: '2025-12-23T10:00:00Z',
        },
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: 'healthy',
        services: {
          database: { status: 'healthy', message: 'OK' },
        },
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();

      const healthIndicator = screen.getByTestId('health-indicator');

      // Focus the element
      fireEvent.focus(healthIndicator);

      // Tooltip should appear
      expect(screen.getByTestId('health-tooltip')).toBeInTheDocument();
    });

    it('hides tooltip on blur', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });

      const systemStatus = {
        type: 'system_status' as const,
        data: {
          gpu: {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.5,
          },
          cameras: { active: 3, total: 5 },
          queue: { pending: 0, processing: 0 },
          health: 'healthy' as const,
        },
        timestamp: '2025-12-23T10:00:00Z',
      };

      vi.spyOn(useConnectionStatusModule, 'useConnectionStatus').mockReturnValue(
        createMockConnectionStatus('connected', 'connected', systemStatus)
      );

      vi.spyOn(useHealthStatusQueryModule, 'useHealthStatusQuery').mockReturnValue({
        data: {
          status: 'healthy',
          services: {
            database: { status: 'healthy', message: 'OK' },
          },
          timestamp: '2025-12-23T10:00:00Z',
        },
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        overallStatus: 'healthy',
        services: {
          database: { status: 'healthy', message: 'OK' },
        },
        refetch: vi.fn().mockResolvedValue({}),
      });

      renderHeader();

      const healthIndicator = screen.getByTestId('health-indicator');

      // Focus to show tooltip
      fireEvent.focus(healthIndicator);
      expect(screen.getByTestId('health-tooltip')).toBeInTheDocument();

      // Blur the element
      fireEvent.blur(healthIndicator);

      // Advance timers past the delay
      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });

      // Tooltip should be hidden
      expect(screen.queryByTestId('health-tooltip')).not.toBeInTheDocument();

      vi.useRealTimers();
    });
  });

  describe('PageDocsLink Integration', () => {
    it('renders documentation link in header', () => {
      renderHeader('/');

      const docsLink = screen.getByRole('link', { name: /documentation/i });
      expect(docsLink).toBeInTheDocument();
    });

    it('shows Dashboard Documentation on root route', () => {
      renderHeader('/');

      expect(screen.getByRole('link', { name: /dashboard documentation/i })).toBeInTheDocument();
    });

    it('shows Alerts Documentation on alerts route', () => {
      renderHeader('/alerts');

      expect(screen.getByRole('link', { name: /alerts documentation/i })).toBeInTheDocument();
    });

    it('shows Jobs Documentation on jobs route', () => {
      renderHeader('/jobs');

      expect(screen.getByRole('link', { name: /jobs documentation/i })).toBeInTheDocument();
    });

    it('does not show documentation link on unmapped routes', () => {
      renderHeader('/dev-tools');

      expect(screen.queryByRole('link', { name: /documentation/i })).not.toBeInTheDocument();
    });

    it('documentation link has NVIDIA green styling', () => {
      renderHeader('/');

      const docsLink = screen.getByRole('link', { name: /documentation/i });
      expect(docsLink).toHaveClass('text-[#76B900]');
    });

    it('documentation link opens in new tab', () => {
      renderHeader('/');

      const docsLink = screen.getByRole('link', { name: /documentation/i });
      expect(docsLink).toHaveAttribute('target', '_blank');
      expect(docsLink).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('documentation link points to GitHub', () => {
      renderHeader('/');

      const docsLink = screen.getByRole('link', { name: /documentation/i });
      expect(docsLink).toHaveAttribute(
        'href',
        expect.stringContaining('github.com/mikesvoboda/nemotron-v3-home-security-intelligence')
      );
    });
  });

  describe('Search Trigger Button', () => {
    it('renders search trigger button', () => {
      renderHeader();
      expect(screen.getByTestId('search-trigger')).toBeInTheDocument();
    });

    it('has accessible label', () => {
      renderHeader();
      expect(screen.getByLabelText('Open command palette')).toBeInTheDocument();
    });

    it('calls openCommandPalette when clicked', () => {
      renderHeader();
      const searchButton = screen.getByTestId('search-trigger');
      fireEvent.click(searchButton);
      expect(mockOpenCommandPalette).toHaveBeenCalled();
    });

    it('displays search icon', () => {
      renderHeader();
      const searchButton = screen.getByTestId('search-trigger');
      // The search icon should be a child of the button
      expect(searchButton.querySelector('svg')).toBeInTheDocument();
    });

    it('displays keyboard shortcut hint', () => {
      renderHeader();
      const searchButton = screen.getByTestId('search-trigger');
      // Should contain K for the keyboard shortcut
      expect(searchButton.textContent).toContain('K');
    });

    it('has correct styling classes for dark theme', () => {
      renderHeader();
      const searchButton = screen.getByTestId('search-trigger');
      expect(searchButton).toHaveClass('bg-[#222]');
      expect(searchButton).toHaveClass('border-[#333]');
    });

    it('is hidden on mobile (uses sm:flex)', () => {
      renderHeader();
      const searchButton = screen.getByTestId('search-trigger');
      expect(searchButton).toHaveClass('hidden');
      expect(searchButton).toHaveClass('sm:flex');
    });
  });

  describe('AI Service Status Integration', () => {
    it('renders AI service status badge in header', () => {
      renderHeader();
      expect(screen.getByTestId('ai-service-status')).toBeInTheDocument();
    });

    it('displays AI service status in compact mode', () => {
      renderHeader();
      // The AIServiceStatus component in compact mode shows "All Systems Operational" for normal mode
      expect(screen.getByText('All Systems Operational')).toBeInTheDocument();
    });

    it('AI service status container is hidden on mobile (uses sm:block)', () => {
      renderHeader();
      const aiStatusContainer = screen.getByTestId('ai-service-status');
      expect(aiStatusContainer).toHaveClass('hidden');
      expect(aiStatusContainer).toHaveClass('sm:block');
    });

    it('AI service status badge has appropriate styling', () => {
      renderHeader();
      const aiStatusContainer = screen.getByTestId('ai-service-status');
      // The compact badge should be rendered inside the container
      expect(aiStatusContainer).toBeInTheDocument();
      // The badge should contain the status text
      expect(aiStatusContainer.textContent).toContain('All Systems Operational');
    });
  });
});
