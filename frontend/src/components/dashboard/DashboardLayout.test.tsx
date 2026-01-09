import { beforeEach, describe, expect, it, vi } from 'vitest';

import DashboardLayout, { type WidgetProps } from './DashboardLayout';
import { DEFAULT_WIDGETS, type DashboardConfig } from '../../stores/dashboardConfig';
import { renderWithProviders, screen, waitFor } from '../../test-utils/renderWithProviders';

// Mock framer-motion to avoid animation timing issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: ({
      children,
      className,
      'data-testid': testId,
      onClick,
      role,
      'aria-modal': ariaModal,
      'aria-labelledby': ariaLabelledby,
      'aria-describedby': ariaDescribedby,
      tabIndex,
    }: {
      children?: React.ReactNode;
      className?: string;
      'data-testid'?: string;
      onClick?: () => void;
      role?: string;
      'aria-modal'?: boolean;
      'aria-labelledby'?: string;
      'aria-describedby'?: string;
      tabIndex?: number;
    }) => (
      // eslint-disable-next-line jsx-a11y/no-static-element-interactions, jsx-a11y/click-events-have-key-events -- mock for framer-motion
      <div
        className={className}
        data-testid={testId}
        onClick={onClick}
        role={role || 'presentation'}
        aria-modal={ariaModal}
        aria-labelledby={ariaLabelledby}
        aria-describedby={ariaDescribedby}
        tabIndex={tabIndex}
      >
        {children}
      </div>
    ),
  },
  AnimatePresence: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  useReducedMotion: vi.fn(() => false),
}));

// Mock localStorage
const mockStorage: Record<string, string> = {};

beforeEach(() => {
  Object.keys(mockStorage).forEach((key) => delete mockStorage[key]);
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key: string) => mockStorage[key] ?? null);
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key: string, value: string) => {
    mockStorage[key] = value;
  });
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((key: string) => {
    delete mockStorage[key];
  });
});

describe('DashboardLayout', () => {
  // Mock render functions
  const mockRenderStatsRow = vi.fn((props) => (
    <div data-testid="mock-stats-row">Stats Row - {props.activeCameras} cameras</div>
  ));
  const mockRenderCameraGrid = vi.fn((props) => (
    <div data-testid="mock-camera-grid">Camera Grid - {props?.cameras?.length ?? 0} cameras</div>
  ));
  const mockRenderActivityFeed = vi.fn((props) => (
    <div data-testid="mock-activity-feed">Activity Feed - {props?.events?.length ?? 0} events</div>
  ));
  const mockRenderGpuStats = vi.fn(() => <div data-testid="mock-gpu-stats">GPU Stats</div>);
  const mockRenderPipelineTelemetry = vi.fn(() => (
    <div data-testid="mock-pipeline-telemetry">Pipeline Telemetry</div>
  ));
  const mockRenderPipelineQueues = vi.fn(() => (
    <div data-testid="mock-pipeline-queues">Pipeline Queues</div>
  ));
  const mockRenderLoadingSkeleton = vi.fn(() => (
    <div data-testid="mock-loading-skeleton">Loading...</div>
  ));

  const defaultWidgetProps: WidgetProps = {
    statsRow: {
      activeCameras: 4,
      eventsToday: 10,
      currentRiskScore: 25,
      systemStatus: 'healthy',
    },
    cameraGrid: {
      cameras: [
        { id: 'cam1', name: 'Front Door', status: 'online' },
        { id: 'cam2', name: 'Back Yard', status: 'online' },
      ],
      onCameraClick: vi.fn(),
    },
    activityFeed: {
      events: [
        {
          id: 'event1',
          timestamp: new Date().toISOString(),
          camera_name: 'Front Door',
          risk_score: 25,
          summary: 'Motion detected',
        },
      ],
      maxItems: 10,
      onEventClick: vi.fn(),
    },
    gpuStats: {
      gpuName: 'NVIDIA RTX A5500',
      utilization: 50,
      temperature: 65,
    },
    pipelineTelemetry: {
      pollingInterval: 5000,
    },
    pipelineQueues: {
      detectionQueue: 0,
      analysisQueue: 0,
      warningThreshold: 10,
    },
  };

  const defaultProps = {
    widgetProps: defaultWidgetProps,
    renderStatsRow: mockRenderStatsRow,
    renderCameraGrid: mockRenderCameraGrid,
    renderActivityFeed: mockRenderActivityFeed,
    renderGpuStats: mockRenderGpuStats,
    renderPipelineTelemetry: mockRenderPipelineTelemetry,
    renderPipelineQueues: mockRenderPipelineQueues,
    renderLoadingSkeleton: mockRenderLoadingSkeleton,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders dashboard layout container', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.getByTestId('dashboard-layout')).toBeInTheDocument();
    });

    it('renders dashboard title', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.getByRole('heading', { name: /security dashboard/i })).toBeInTheDocument();
    });

    it('renders dashboard subtitle', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.getByText(/real-time ai-powered home security monitoring/i)).toBeInTheDocument();
    });

    it('renders configure button', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.getByTestId('configure-dashboard-button')).toBeInTheDocument();
    });
  });

  describe('default widget rendering', () => {
    it('renders stats row by default', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.getByTestId('mock-stats-row')).toBeInTheDocument();
    });

    it('renders camera grid by default', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.getByTestId('mock-camera-grid')).toBeInTheDocument();
    });

    it('renders activity feed by default', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.getByTestId('mock-activity-feed')).toBeInTheDocument();
    });

    it('does not render gpu stats by default (hidden)', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.queryByTestId('mock-gpu-stats')).not.toBeInTheDocument();
    });

    it('does not render pipeline telemetry by default (hidden)', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.queryByTestId('mock-pipeline-telemetry')).not.toBeInTheDocument();
    });
  });

  describe('configuration modal', () => {
    it('opens config modal when configure button is clicked', async () => {
      const { user } = renderWithProviders(<DashboardLayout {...defaultProps} />);

      await user.click(screen.getByTestId('configure-dashboard-button'));

      expect(screen.getByText('Customize Dashboard')).toBeInTheDocument();
    });

    it('closes config modal when cancel is clicked', async () => {
      const { user } = renderWithProviders(<DashboardLayout {...defaultProps} />);

      await user.click(screen.getByTestId('configure-dashboard-button'));
      expect(screen.getByText('Customize Dashboard')).toBeInTheDocument();

      await user.click(screen.getByTestId('cancel-button'));

      await waitFor(() => {
        expect(screen.queryByText('Customize Dashboard')).not.toBeInTheDocument();
      });
    });

    it('updates layout when configuration is saved', async () => {
      const { user } = renderWithProviders(<DashboardLayout {...defaultProps} />);

      // Initially gpu-stats should not be visible
      expect(screen.queryByTestId('mock-gpu-stats')).not.toBeInTheDocument();

      // Open config modal
      await user.click(screen.getByTestId('configure-dashboard-button'));

      // Toggle gpu-stats visibility
      await user.click(screen.getByTestId('widget-toggle-gpu-stats'));

      // Save changes
      await user.click(screen.getByTestId('save-button'));

      // Now gpu-stats should be visible
      await waitFor(() => {
        expect(screen.getByTestId('mock-gpu-stats')).toBeInTheDocument();
      });
    });

    it('hides widget when visibility is toggled off', async () => {
      const { user } = renderWithProviders(<DashboardLayout {...defaultProps} />);

      // Initially stats-row should be visible
      expect(screen.getByTestId('mock-stats-row')).toBeInTheDocument();

      // Open config modal
      await user.click(screen.getByTestId('configure-dashboard-button'));

      // Toggle stats-row visibility off
      await user.click(screen.getByTestId('widget-toggle-stats-row'));

      // Save changes
      await user.click(screen.getByTestId('save-button'));

      // Now stats-row should be hidden
      await waitFor(() => {
        expect(screen.queryByTestId('mock-stats-row')).not.toBeInTheDocument();
      });
    });
  });

  describe('loading state', () => {
    it('renders loading skeleton when isLoading is true', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} isLoading={true} />);

      expect(screen.getByTestId('mock-loading-skeleton')).toBeInTheDocument();
    });

    it('does not render widgets when loading', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} isLoading={true} />);

      expect(screen.queryByTestId('mock-stats-row')).not.toBeInTheDocument();
      expect(screen.queryByTestId('mock-camera-grid')).not.toBeInTheDocument();
    });

    it('renders widgets after loading completes', () => {
      const { rerender } = renderWithProviders(
        <DashboardLayout {...defaultProps} isLoading={true} />
      );

      expect(screen.queryByTestId('mock-stats-row')).not.toBeInTheDocument();

      rerender(<DashboardLayout {...defaultProps} isLoading={false} />);

      expect(screen.getByTestId('mock-stats-row')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows empty state when all widgets are hidden', () => {
      // Set up config with all widgets hidden
      const allHiddenConfig: DashboardConfig = {
        widgets: DEFAULT_WIDGETS.map((w) => ({ ...w, visible: false })),
        version: 1,
      };
      mockStorage['dashboard-config'] = JSON.stringify(allHiddenConfig);

      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.getByTestId('empty-dashboard')).toBeInTheDocument();
      expect(screen.getByText('No Widgets Visible')).toBeInTheDocument();
    });

    it('empty state has configure button', () => {
      const allHiddenConfig: DashboardConfig = {
        widgets: DEFAULT_WIDGETS.map((w) => ({ ...w, visible: false })),
        version: 1,
      };
      mockStorage['dashboard-config'] = JSON.stringify(allHiddenConfig);

      renderWithProviders(<DashboardLayout {...defaultProps} />);

      // Empty state has its own configure button within the empty-dashboard area
      const emptyDashboard = screen.getByTestId('empty-dashboard');
      const configureButton = emptyDashboard.querySelector('button');
      expect(configureButton).toBeInTheDocument();
      expect(configureButton?.textContent).toBe('Configure Dashboard');
    });

    it('can open config modal from empty state', async () => {
      const allHiddenConfig: DashboardConfig = {
        widgets: DEFAULT_WIDGETS.map((w) => ({ ...w, visible: false })),
        version: 1,
      };
      mockStorage['dashboard-config'] = JSON.stringify(allHiddenConfig);

      const { user } = renderWithProviders(<DashboardLayout {...defaultProps} />);

      // Click the configure button within the empty state area
      const emptyDashboard = screen.getByTestId('empty-dashboard');
      const configureButton = emptyDashboard.querySelector('button');
      expect(configureButton).not.toBeNull();
      await user.click(configureButton!);

      expect(screen.getByText('Customize Dashboard')).toBeInTheDocument();
    });
  });

  describe('localStorage persistence', () => {
    it('loads config from localStorage on mount', () => {
      // Set up custom config in localStorage
      const customConfig: DashboardConfig = {
        widgets: DEFAULT_WIDGETS.map((w) => ({
          ...w,
          visible: w.id === 'gpu-stats', // Only gpu-stats visible
        })),
        version: 1,
      };
      mockStorage['dashboard-config'] = JSON.stringify(customConfig);

      renderWithProviders(<DashboardLayout {...defaultProps} />);

      // Only gpu-stats should be visible
      expect(screen.getByTestId('mock-gpu-stats')).toBeInTheDocument();
      expect(screen.queryByTestId('mock-stats-row')).not.toBeInTheDocument();
    });

    it('saves config to localStorage when changed', async () => {
      const { user } = renderWithProviders(<DashboardLayout {...defaultProps} />);

      // Open config modal and make a change
      await user.click(screen.getByTestId('configure-dashboard-button'));
      await user.click(screen.getByTestId('widget-toggle-gpu-stats'));
      await user.click(screen.getByTestId('save-button'));

      // Check that localStorage was updated
      const savedConfig = JSON.parse(mockStorage['dashboard-config']);
      const gpuStats = savedConfig.widgets.find((w: { id: string }) => w.id === 'gpu-stats');
      expect(gpuStats.visible).toBe(true);
    });
  });

  describe('two-column layout', () => {
    it('uses two-column layout when both camera-grid and activity-feed are visible', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      const mainContent = screen.getByTestId('main-content-area');
      expect(mainContent).toHaveClass('lg:grid-cols-[2fr,1fr]');
    });

    it('uses single column when only camera-grid is visible', () => {
      const config: DashboardConfig = {
        widgets: DEFAULT_WIDGETS.map((w) => ({
          ...w,
          visible: w.id === 'stats-row' || w.id === 'camera-grid',
        })),
        version: 1,
      };
      mockStorage['dashboard-config'] = JSON.stringify(config);

      renderWithProviders(<DashboardLayout {...defaultProps} />);

      // Should still have main content area but not the two-column class
      const mainContent = screen.getByTestId('main-content-area');
      expect(mainContent).not.toHaveClass('lg:grid-cols-[2fr,1fr]');
      expect(mainContent).toHaveClass('space-y-6');
    });
  });

  describe('render function calls', () => {
    it('calls renderStatsRow with correct props', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(mockRenderStatsRow).toHaveBeenCalledWith(defaultWidgetProps.statsRow);
    });

    it('calls renderCameraGrid with correct props', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(mockRenderCameraGrid).toHaveBeenCalledWith(defaultWidgetProps.cameraGrid);
    });

    it('calls renderActivityFeed with correct props', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(mockRenderActivityFeed).toHaveBeenCalledWith(defaultWidgetProps.activityFeed);
    });

    it('does not call renderGpuStats when hidden', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(mockRenderGpuStats).not.toHaveBeenCalled();
    });
  });

  describe('widget containers', () => {
    it('wraps stats-row in container with testid', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.getByTestId('widget-stats-row')).toBeInTheDocument();
    });

    it('wraps camera-grid in container with testid', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.getByTestId('widget-camera-grid')).toBeInTheDocument();
    });

    it('wraps activity-feed in container with testid', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.getByTestId('widget-activity-feed')).toBeInTheDocument();
    });
  });

  describe('section headers', () => {
    it('renders Camera Status header for camera grid', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.getByRole('heading', { name: /camera status/i })).toBeInTheDocument();
    });

    it('renders Live Activity header for activity feed', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.getByRole('heading', { name: /live activity/i })).toBeInTheDocument();
    });
  });

  describe('className prop', () => {
    it('applies custom className to layout', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} className="custom-class" />);

      const layout = screen.getByTestId('dashboard-layout');
      expect(layout).toHaveClass('custom-class');
    });
  });

  describe('accessibility', () => {
    it('has accessible configure button', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      expect(screen.getByLabelText(/configure dashboard/i)).toBeInTheDocument();
    });

    it('configure button is keyboard accessible', () => {
      renderWithProviders(<DashboardLayout {...defaultProps} />);

      const button = screen.getByTestId('configure-dashboard-button');
      expect(button).not.toHaveAttribute('tabindex', '-1');
    });
  });
});
