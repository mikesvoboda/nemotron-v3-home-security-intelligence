/**
 * Tests for AnalyticsPage component
 * Tests the Grafana iframe embed implementation
 */

import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import AnalyticsPage from './AnalyticsPage';
import * as api from '../../services/api';

// Mock the fetchConfig API
vi.mock('../../services/api', () => ({
  fetchConfig: vi.fn(() => Promise.resolve({ grafana_url: '/grafana' })),
}));

// Mock native analytics components to avoid their dependencies
vi.mock('./CameraUptimeCard', () => ({
  default: ({ dateRange }: { dateRange: { startDate: string; endDate: string } }) => (
    <div
      data-testid="camera-uptime-card"
      data-start={dateRange.startDate}
      data-end={dateRange.endDate}
    >
      Camera Uptime Mock
    </div>
  ),
}));

vi.mock('./DetectionTrendsCard', () => ({
  default: ({ dateRange }: { dateRange: { startDate: string; endDate: string } }) => (
    <div
      data-testid="detection-trends-card"
      data-start={dateRange.startDate}
      data-end={dateRange.endDate}
    >
      Detection Trends Mock
    </div>
  ),
}));

vi.mock('./RiskHistoryCard', () => ({
  default: ({ dateRange }: { dateRange: { startDate: string; endDate: string } }) => (
    <div
      data-testid="risk-history-card"
      data-start={dateRange.startDate}
      data-end={dateRange.endDate}
    >
      Risk History Mock
    </div>
  ),
}));

vi.mock('./ObjectDistributionCard', () => ({
  default: ({ dateRange }: { dateRange: { startDate: string; endDate: string } }) => (
    <div
      data-testid="object-distribution-card"
      data-start={dateRange.startDate}
      data-end={dateRange.endDate}
    >
      Object Distribution Mock
    </div>
  ),
}));

vi.mock('./PipelineLatencyPanel', () => ({
  default: ({ refreshInterval }: { refreshInterval?: number }) => (
    <div data-testid="pipeline-latency-panel" data-refresh={refreshInterval}>
      Pipeline Latency Mock
    </div>
  ),
}));

const renderWithRouter = () => {
  return render(
    <MemoryRouter>
      <AnalyticsPage />
    </MemoryRouter>
  );
};

describe('AnalyticsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe('basic rendering', () => {
    it('renders the page title', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByText('Analytics')).toBeInTheDocument();
      });
    });

    it('renders the refresh button', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('analytics-refresh-button')).toBeInTheDocument();
      });
    });

    it('renders the Grafana external link', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('grafana-external-link')).toBeInTheDocument();
      });
    });

    it('renders the Grafana iframe', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('grafana-iframe')).toBeInTheDocument();
      });
    });

    it('has correct data-testid for the page', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('analytics-page')).toBeInTheDocument();
      });
    });
  });

  describe('loading state', () => {
    it('shows loading skeleton when config is loading', async () => {
      // Create a promise that won't resolve immediately
      let resolveConfig: (
        value: ReturnType<typeof api.fetchConfig> extends Promise<infer T> ? T : never
      ) => void;
      const configPromise = new Promise<
        ReturnType<typeof api.fetchConfig> extends Promise<infer T> ? T : never
      >((resolve) => {
        resolveConfig = resolve;
      });
      vi.mocked(api.fetchConfig).mockReturnValue(configPromise);

      renderWithRouter();

      // Should show loading state initially
      expect(screen.getByTestId('analytics-loading')).toBeInTheDocument();

      // Resolve the config
      await act(async () => {
        resolveConfig!({
          app_name: 'Test App',
          version: '1.0.0',
          retention_days: 30,
          batch_window_seconds: 90,
          batch_idle_timeout_seconds: 30,
          detection_confidence_threshold: 0.5,
          grafana_url: '/grafana',
          debug: false,
        });
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.queryByTestId('analytics-loading')).not.toBeInTheDocument();
      });
    });

    it('loading skeleton contains animated pulse elements', async () => {
      let resolveConfig: (
        value: ReturnType<typeof api.fetchConfig> extends Promise<infer T> ? T : never
      ) => void;
      const configPromise = new Promise<
        ReturnType<typeof api.fetchConfig> extends Promise<infer T> ? T : never
      >((resolve) => {
        resolveConfig = resolve;
      });
      vi.mocked(api.fetchConfig).mockReturnValue(configPromise);

      renderWithRouter();

      const loadingContainer = screen.getByTestId('analytics-loading');
      const pulseElements = loadingContainer.querySelectorAll('.animate-pulse');
      expect(pulseElements.length).toBeGreaterThan(0);

      // Clean up
      await act(async () => {
        resolveConfig!({
          app_name: 'Test App',
          version: '1.0.0',
          retention_days: 30,
          batch_window_seconds: 90,
          batch_idle_timeout_seconds: 30,
          detection_confidence_threshold: 0.5,
          grafana_url: '/grafana',
          debug: false,
        });
        await vi.runAllTimersAsync();
      });
    });
  });

  describe('error states', () => {
    it('shows error message when config fetch fails', async () => {
      vi.mocked(api.fetchConfig).mockRejectedValue(new Error('Config fetch failed'));
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('analytics-error')).toBeInTheDocument();
        expect(screen.getByText(/Failed to load configuration/)).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });

    it('still renders the page when config fetch fails', async () => {
      vi.mocked(api.fetchConfig).mockRejectedValue(new Error('Config fetch failed'));
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('analytics-page')).toBeInTheDocument();
        expect(screen.getByTestId('grafana-iframe')).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });
  });

  describe('Grafana integration', () => {
    it('renders iframe with correct Grafana URL in kiosk mode', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue({
        app_name: 'Test App',
        version: '1.0.0',
        retention_days: 30,
        batch_window_seconds: 90,
        batch_idle_timeout_seconds: 30,
        detection_confidence_threshold: 0.5,
        grafana_url: 'http://grafana.example.com',
        debug: false,
      });

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('grafana-iframe');
        expect(iframe).toHaveAttribute(
          'src',
          'http://grafana.example.com/d/hsi-analytics?orgId=1&kiosk=1&theme=dark&refresh=30s'
        );
      });
    });

    it('uses default Grafana URL when config fetch fails', async () => {
      vi.mocked(api.fetchConfig).mockRejectedValue(new Error('Config fetch failed'));
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('grafana-iframe');
        expect(iframe).toHaveAttribute(
          'src',
          '/grafana/d/hsi-analytics?orgId=1&kiosk=1&theme=dark&refresh=30s'
        );
      });

      consoleSpy.mockRestore();
    });

    it('external link opens in new tab', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const externalLink = screen.getByTestId('grafana-external-link');
        expect(externalLink).toHaveAttribute('target', '_blank');
        expect(externalLink).toHaveAttribute('rel', 'noopener noreferrer');
      });
    });

    it('external link has correct URL without kiosk mode', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue({
        app_name: 'Test App',
        version: '1.0.0',
        retention_days: 30,
        batch_window_seconds: 90,
        batch_idle_timeout_seconds: 30,
        detection_confidence_threshold: 0.5,
        grafana_url: 'http://grafana.example.com',
        debug: false,
      });

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const externalLink = screen.getByTestId('grafana-external-link');
        expect(externalLink).toHaveAttribute(
          'href',
          'http://grafana.example.com/d/hsi-analytics?orgId=1'
        );
      });
    });

    it('renders Open in Grafana text with external link icon', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const externalLink = screen.getByTestId('grafana-external-link');
        expect(externalLink).toHaveTextContent('Open in Grafana');
        // ExternalLink icon should be present as SVG
        expect(externalLink.querySelector('svg')).toBeInTheDocument();
      });
    });
  });

  describe('refresh functionality', () => {
    it('refresh button reloads the iframe', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('analytics-refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('analytics-refresh-button');
      const iframe = screen.getByTestId<HTMLIFrameElement>('grafana-iframe');
      const originalSrc = iframe.src;

      await user.click(refreshButton);

      // The src should be cleared and then restored
      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });

      await waitFor(() => {
        expect(iframe.src).toBe(originalSrc);
      });
    });

    it('disables refresh button while refreshing', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('analytics-refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('analytics-refresh-button');
      await user.click(refreshButton);

      // Button should be disabled during refresh
      expect(refreshButton).toBeDisabled();

      // Advance past the timeout
      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });

      await waitFor(() => {
        expect(refreshButton).not.toBeDisabled();
      });
    });

    it('shows spinning icon while refreshing', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('analytics-refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('analytics-refresh-button');
      await user.click(refreshButton);

      // Check for spinning animation class
      const icon = refreshButton.querySelector('svg');
      expect(icon).toHaveClass('animate-spin');

      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });

      await waitFor(() => {
        const iconAfter = refreshButton.querySelector('svg');
        expect(iconAfter).not.toHaveClass('animate-spin');
      });
    });
  });

  describe('accessibility', () => {
    it('refresh button has accessible name', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const refreshButton = screen.getByTestId('analytics-refresh-button');
        expect(refreshButton).toHaveTextContent('Refresh');
      });
    });

    it('external link has accessible name', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const externalLink = screen.getByTestId('grafana-external-link');
        expect(externalLink).toHaveTextContent('Open in Grafana');
      });
    });

    it('page has semantic heading structure', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const heading = screen.getByRole('heading', { level: 1 });
        expect(heading).toHaveTextContent('Analytics');
      });
    });

    it('iframe has accessible title', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('grafana-iframe');
        expect(iframe).toHaveAttribute('title', 'Analytics Dashboard');
      });
    });
  });

  describe('iframe properties', () => {
    it('iframe has full width', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('grafana-iframe');
        expect(iframe).toHaveClass('w-full');
      });
    });

    it('iframe has correct height class', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('grafana-iframe');
        expect(iframe).toHaveClass('h-[calc(100vh-73px)]');
      });
    });

    it('iframe has no border', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('grafana-iframe');
        expect(iframe).toHaveClass('border-0');
      });
    });
  });

  describe('view mode toggle', () => {
    it('renders view mode toggle buttons', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('view-mode-toggle')).toBeInTheDocument();
        expect(screen.getByTestId('view-mode-grafana')).toBeInTheDocument();
        expect(screen.getByTestId('view-mode-native')).toBeInTheDocument();
      });
    });

    it('defaults to Grafana view', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('grafana-iframe')).toBeInTheDocument();
        expect(screen.queryByTestId('native-analytics-view')).not.toBeInTheDocument();
      });
    });

    it('switches to native view when Native button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('view-mode-native')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('view-mode-native'));

      await waitFor(() => {
        expect(screen.getByTestId('native-analytics-view')).toBeInTheDocument();
        expect(screen.queryByTestId('grafana-iframe')).not.toBeInTheDocument();
      });
    });

    it('switches back to Grafana view when Grafana button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      // Switch to native first
      await user.click(screen.getByTestId('view-mode-native'));
      await waitFor(() => {
        expect(screen.getByTestId('native-analytics-view')).toBeInTheDocument();
      });

      // Switch back to Grafana
      await user.click(screen.getByTestId('view-mode-grafana'));
      await waitFor(() => {
        expect(screen.getByTestId('grafana-iframe')).toBeInTheDocument();
        expect(screen.queryByTestId('native-analytics-view')).not.toBeInTheDocument();
      });
    });

    it('hides Grafana external link in native view', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      // Verify external link is visible in Grafana view
      await waitFor(() => {
        expect(screen.getByTestId('grafana-external-link')).toBeInTheDocument();
      });

      // Switch to native view
      await user.click(screen.getByTestId('view-mode-native'));

      await waitFor(() => {
        expect(screen.queryByTestId('grafana-external-link')).not.toBeInTheDocument();
      });
    });

    it('hides refresh button in native view', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      // Verify refresh button is visible in Grafana view
      await waitFor(() => {
        expect(screen.getByTestId('analytics-refresh-button')).toBeInTheDocument();
      });

      // Switch to native view
      await user.click(screen.getByTestId('view-mode-native'));

      await waitFor(() => {
        expect(screen.queryByTestId('analytics-refresh-button')).not.toBeInTheDocument();
      });
    });

    it('has correct styling for active view mode button', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const grafanaButton = screen.getByTestId('view-mode-grafana');
        const nativeButton = screen.getByTestId('view-mode-native');

        // Grafana button should have active style (bg-[#76B900])
        expect(grafanaButton).toHaveClass('bg-[#76B900]');
        // Native button should have inactive style (bg-gray-800)
        expect(nativeButton).toHaveClass('bg-gray-800');
      });
    });
  });
});
