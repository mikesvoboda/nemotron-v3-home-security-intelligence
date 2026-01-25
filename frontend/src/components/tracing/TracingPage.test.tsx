/**
 * Tests for TracingPage component
 * Tests the Grafana HSI Distributed Tracing dashboard iframe embed
 */

import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import TracingPage from './TracingPage';
import * as api from '../../services/api';

// Mock the fetchConfig API
vi.mock('../../services/api', () => ({
  fetchConfig: vi.fn(),
}));

const renderWithRouter = () => {
  return render(
    <MemoryRouter>
      <TracingPage />
    </MemoryRouter>
  );
};

describe('TracingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    // Set default mock implementation
    (api.fetchConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
      app_name: 'Test App',
      version: '1.0.0',
      retention_days: 30,
        log_retention_days: 7,
      batch_window_seconds: 90,
      batch_idle_timeout_seconds: 30,
      detection_confidence_threshold: 0.5,
        fast_path_confidence_threshold: 0.9,
      grafana_url: '/grafana',
      debug: false,
    });
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
        expect(screen.getByText('Distributed Tracing')).toBeInTheDocument();
      });
    });

    it('renders the refresh button', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('tracing-refresh-button')).toBeInTheDocument();
      });
    });

    it('renders the Open in Grafana link', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('grafana-external-link')).toBeInTheDocument();
      });
    });

    it('renders the Open Jaeger link', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('jaeger-external-link')).toBeInTheDocument();
      });
    });

    it('renders the tracing iframe', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('tracing-iframe')).toBeInTheDocument();
      });
    });

    it('has correct data-testid for the page', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('tracing-page')).toBeInTheDocument();
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
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockReturnValue(configPromise);

      renderWithRouter();

      // Should show loading state initially
      expect(screen.getByTestId('tracing-loading')).toBeInTheDocument();

      // Resolve the config
      await act(async () => {
        resolveConfig!({
          app_name: 'Test App',
          version: '1.0.0',
          retention_days: 30,
        log_retention_days: 7,
          batch_window_seconds: 90,
          batch_idle_timeout_seconds: 30,
          detection_confidence_threshold: 0.5,
        fast_path_confidence_threshold: 0.9,
          grafana_url: '/grafana',
          debug: false,
        });
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.queryByTestId('tracing-loading')).not.toBeInTheDocument();
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
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockReturnValue(configPromise);

      renderWithRouter();

      const loadingContainer = screen.getByTestId('tracing-loading');
      const pulseElements = loadingContainer.querySelectorAll('.animate-pulse');
      expect(pulseElements.length).toBeGreaterThan(0);

      // Clean up
      await act(async () => {
        resolveConfig!({
          app_name: 'Test App',
          version: '1.0.0',
          retention_days: 30,
        log_retention_days: 7,
          batch_window_seconds: 90,
          batch_idle_timeout_seconds: 30,
          detection_confidence_threshold: 0.5,
        fast_path_confidence_threshold: 0.9,
          grafana_url: '/grafana',
          debug: false,
        });
        await vi.runAllTimersAsync();
      });
    });
  });

  describe('error states', () => {
    it('shows error message when config fetch fails', async () => {
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Config fetch failed')
      );
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('tracing-error')).toBeInTheDocument();
        expect(screen.getByText(/Failed to load configuration/)).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });

    it('still renders the page when config fetch fails', async () => {
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Config fetch failed')
      );
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('tracing-page')).toBeInTheDocument();
        expect(screen.getByTestId('tracing-iframe')).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });
  });

  describe('Grafana dashboard integration', () => {
    it('renders iframe with correct HSI Distributed Tracing dashboard URL', async () => {
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
        app_name: 'Test App',
        version: '1.0.0',
        retention_days: 30,
        log_retention_days: 7,
        batch_window_seconds: 90,
        batch_idle_timeout_seconds: 30,
        detection_confidence_threshold: 0.5,
        fast_path_confidence_threshold: 0.9,
        grafana_url: 'http://grafana.example.com',
        debug: false,
      });

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('tracing-iframe');
        const src = iframe.getAttribute('src');
        expect(src).toContain('http://grafana.example.com/d/hsi-tracing/hsi-distributed-tracing');
        expect(src).toContain('orgId=1');
        expect(src).toContain('kiosk=1');
        expect(src).toContain('theme=dark');
        expect(src).toContain('refresh=30s');
      });
    });

    it('uses default Grafana URL when config fetch fails', async () => {
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Config fetch failed')
      );
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('tracing-iframe');
        expect(iframe).toHaveAttribute('src', expect.stringContaining('/grafana/d/hsi-tracing'));
      });

      consoleSpy.mockRestore();
    });

    it('Open in Grafana link opens in new tab', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-external-link');
        expect(grafanaLink).toHaveAttribute('target', '_blank');
        expect(grafanaLink).toHaveAttribute('rel', 'noopener noreferrer');
      });
    });

    it('Open in Grafana link has correct dashboard URL', async () => {
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
        app_name: 'Test App',
        version: '1.0.0',
        retention_days: 30,
        log_retention_days: 7,
        batch_window_seconds: 90,
        batch_idle_timeout_seconds: 30,
        detection_confidence_threshold: 0.5,
        fast_path_confidence_threshold: 0.9,
        grafana_url: 'http://grafana.example.com',
        debug: false,
      });

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-external-link');
        expect(grafanaLink).toHaveAttribute(
          'href',
          'http://grafana.example.com/d/hsi-tracing/hsi-distributed-tracing?orgId=1&theme=dark'
        );
      });
    });

    it('renders Open in Grafana text with icon', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-external-link');
        expect(grafanaLink).toHaveTextContent('Open in Grafana');
        expect(grafanaLink.querySelector('svg')).toBeInTheDocument();
      });
    });

    it('Open Jaeger link opens in new tab', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const jaegerLink = screen.getByTestId('jaeger-external-link');
        expect(jaegerLink).toHaveAttribute('target', '_blank');
        expect(jaegerLink).toHaveAttribute('rel', 'noopener noreferrer');
      });
    });

    it('Open Jaeger link has correct URL', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const jaegerLink = screen.getByTestId('jaeger-external-link');
        expect(jaegerLink).toHaveAttribute('href', 'http://localhost:16686');
      });
    });

    it('renders Open Jaeger text with icon', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const jaegerLink = screen.getByTestId('jaeger-external-link');
        expect(jaegerLink).toHaveTextContent('Open Jaeger');
        expect(jaegerLink.querySelector('svg')).toBeInTheDocument();
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
        expect(screen.getByTestId('tracing-refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('tracing-refresh-button');
      const iframe = screen.getByTestId<HTMLIFrameElement>('tracing-iframe');
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
        expect(screen.getByTestId('tracing-refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('tracing-refresh-button');
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
        expect(screen.getByTestId('tracing-refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('tracing-refresh-button');
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
        const refreshButton = screen.getByTestId('tracing-refresh-button');
        expect(refreshButton).toHaveTextContent('Refresh');
      });
    });

    it('Open in Grafana link has accessible name', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-external-link');
        expect(grafanaLink).toHaveTextContent('Open in Grafana');
      });
    });

    it('Open Jaeger link has accessible name', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const jaegerLink = screen.getByTestId('jaeger-external-link');
        expect(jaegerLink).toHaveTextContent('Open Jaeger');
      });
    });

    it('page has semantic heading structure', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const heading = screen.getByRole('heading', { level: 1 });
        expect(heading).toHaveTextContent('Distributed Tracing');
      });
    });

    it('iframe has accessible title', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('tracing-iframe');
        expect(iframe).toHaveAttribute('title', 'Distributed Tracing');
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
        const iframe = screen.getByTestId('tracing-iframe');
        expect(iframe).toHaveClass('w-full');
      });
    });

    it('iframe has correct height class', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('tracing-iframe');
        expect(iframe).toHaveClass('h-[calc(100vh-73px)]');
      });
    });

    it('iframe has no border', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('tracing-iframe');
        expect(iframe).toHaveClass('border-0');
      });
    });
  });

  describe('URL construction', () => {
    it('constructs proper dashboard URL with all parameters', async () => {
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
        app_name: 'Test App',
        version: '1.0.0',
        retention_days: 30,
        log_retention_days: 7,
        batch_window_seconds: 90,
        batch_idle_timeout_seconds: 30,
        detection_confidence_threshold: 0.5,
        fast_path_confidence_threshold: 0.9,
        grafana_url: '/grafana',
        debug: false,
      });

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('tracing-iframe');
        const src = iframe.getAttribute('src');
        // Verify URL structure
        expect(src).toContain('/grafana/d/hsi-tracing/hsi-distributed-tracing?');
        expect(src).toContain('orgId=1');
        expect(src).toContain('kiosk=1');
        expect(src).toContain('theme=dark');
        expect(src).toContain('refresh=30s');
      });
    });

    it('uses resolveGrafanaUrl for localhost URLs', async () => {
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
        app_name: 'Test App',
        version: '1.0.0',
        retention_days: 30,
        log_retention_days: 7,
        batch_window_seconds: 90,
        batch_idle_timeout_seconds: 30,
        detection_confidence_threshold: 0.5,
        fast_path_confidence_threshold: 0.9,
        grafana_url: 'http://localhost:3002',
        debug: false,
      });

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('tracing-iframe');
        const src = iframe.getAttribute('src');
        // Should resolve localhost to current hostname (in tests, it's empty/localhost)
        expect(src).toContain('/d/hsi-tracing/hsi-distributed-tracing?');
      });
    });
  });
});
