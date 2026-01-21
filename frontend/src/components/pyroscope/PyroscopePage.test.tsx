/**
 * Tests for PyroscopePage component
 * Tests the Grafana HSI Profiling dashboard iframe embed
 */

import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import PyroscopePage from './PyroscopePage';
import * as api from '../../services/api';

// Mock the fetchConfig API
vi.mock('../../services/api', () => ({
  fetchConfig: vi.fn(),
}));

const renderWithRouter = () => {
  return render(
    <MemoryRouter>
      <PyroscopePage />
    </MemoryRouter>
  );
};

describe('PyroscopePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    // Set default mock implementation
    (api.fetchConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
      app_name: 'Test App',
      version: '1.0.0',
      retention_days: 30,
      batch_window_seconds: 90,
      batch_idle_timeout_seconds: 30,
      detection_confidence_threshold: 0.5,
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
        expect(screen.getByText('Profiling')).toBeInTheDocument();
      });
    });

    it('renders the refresh button', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('pyroscope-refresh-button')).toBeInTheDocument();
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

    it('renders the Explore link', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('explore-link')).toBeInTheDocument();
      });
    });

    it('renders the Open Pyroscope link', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('pyroscope-external-link')).toBeInTheDocument();
      });
    });

    it('renders the pyroscope iframe', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('pyroscope-iframe')).toBeInTheDocument();
      });
    });

    it('has correct data-testid for the page', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('pyroscope-page')).toBeInTheDocument();
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
      expect(screen.getByTestId('pyroscope-loading')).toBeInTheDocument();

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
        expect(screen.queryByTestId('pyroscope-loading')).not.toBeInTheDocument();
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

      const loadingContainer = screen.getByTestId('pyroscope-loading');
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
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Config fetch failed'));
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('pyroscope-error')).toBeInTheDocument();
        expect(screen.getByText(/Failed to load configuration/)).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });

    it('still renders the page when config fetch fails', async () => {
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Config fetch failed'));
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('pyroscope-page')).toBeInTheDocument();
        expect(screen.getByTestId('pyroscope-iframe')).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });
  });

  describe('Grafana dashboard integration', () => {
    it('uses default Grafana URL when config does not include grafana_url', async () => {
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
        app_name: 'Test App',
        version: '1.0.0',
        retention_days: 30,
        batch_window_seconds: 90,
        batch_idle_timeout_seconds: 30,
        detection_confidence_threshold: 0.5,
        debug: false,
        // No grafana_url provided
      });

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('pyroscope-iframe');
        const src = iframe.getAttribute('src');
        // Should use default /grafana
        expect(src).toContain('/grafana/d/hsi-profiling/hsi-profiling');
      });
    });

    it('renders iframe with correct HSI Profiling dashboard URL', async () => {
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
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
        const iframe = screen.getByTestId('pyroscope-iframe');
        const src = iframe.getAttribute('src');
        expect(src).toContain('http://grafana.example.com/d/hsi-profiling/hsi-profiling');
        expect(src).toContain('orgId=1');
        expect(src).toContain('kiosk=1');
        expect(src).toContain('theme=dark');
        expect(src).toContain('refresh=30s');
      });
    });

    it('uses default Grafana URL when config fetch fails', async () => {
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Config fetch failed'));
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('pyroscope-iframe');
        expect(iframe).toHaveAttribute('src', expect.stringContaining('/grafana/d/hsi-profiling'));
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
        const grafanaLink = screen.getByTestId('grafana-external-link');
        expect(grafanaLink).toHaveAttribute(
          'href',
          'http://grafana.example.com/d/hsi-profiling/hsi-profiling?orgId=1&theme=dark'
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

    it('Explore link opens in new tab', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const exploreLink = screen.getByTestId('explore-link');
        expect(exploreLink).toHaveAttribute('target', '_blank');
        expect(exploreLink).toHaveAttribute('rel', 'noopener noreferrer');
      });
    });

    it('Explore link has correct URL with Pyroscope datasource', async () => {
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
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
        const exploreLink = screen.getByTestId('explore-link');
        const href = exploreLink.getAttribute('href');
        expect(href).toContain('http://grafana.example.com/explore');
        expect(href).toContain('orgId=1');
        expect(href).toContain('theme=dark');
        expect(href).toContain('"datasource":"Pyroscope"');
      });
    });

    it('renders Explore text with icon', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const exploreLink = screen.getByTestId('explore-link');
        expect(exploreLink).toHaveTextContent('Explore');
        expect(exploreLink.querySelector('svg')).toBeInTheDocument();
      });
    });

    it('Open Pyroscope link opens in new tab', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const pyroscopeLink = screen.getByTestId('pyroscope-external-link');
        expect(pyroscopeLink).toHaveAttribute('target', '_blank');
        expect(pyroscopeLink).toHaveAttribute('rel', 'noopener noreferrer');
      });
    });

    it('Open Pyroscope link has correct URL', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const pyroscopeLink = screen.getByTestId('pyroscope-external-link');
        expect(pyroscopeLink).toHaveAttribute('href', 'http://localhost:4040');
      });
    });

    it('renders Open Pyroscope text with icon', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const pyroscopeLink = screen.getByTestId('pyroscope-external-link');
        expect(pyroscopeLink).toHaveTextContent('Open Pyroscope');
        expect(pyroscopeLink.querySelector('svg')).toBeInTheDocument();
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
        expect(screen.getByTestId('pyroscope-refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('pyroscope-refresh-button');
      const iframe = screen.getByTestId<HTMLIFrameElement>('pyroscope-iframe');
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

    it('handles refresh when iframe ref is null', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('pyroscope-refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('pyroscope-refresh-button');
      const iframe = screen.getByTestId<HTMLIFrameElement>('pyroscope-iframe');

      // Remove iframe from DOM to simulate null ref
      iframe.remove();

      await user.click(refreshButton);

      // Should not throw error
      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });

      expect(refreshButton).not.toBeDisabled();
    });

    it('disables refresh button while refreshing', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('pyroscope-refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('pyroscope-refresh-button');
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
        expect(screen.getByTestId('pyroscope-refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('pyroscope-refresh-button');
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
        const refreshButton = screen.getByTestId('pyroscope-refresh-button');
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

    it('Explore link has accessible name', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const exploreLink = screen.getByTestId('explore-link');
        expect(exploreLink).toHaveTextContent('Explore');
      });
    });

    it('Open Pyroscope link has accessible name', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const pyroscopeLink = screen.getByTestId('pyroscope-external-link');
        expect(pyroscopeLink).toHaveTextContent('Open Pyroscope');
      });
    });

    it('page has semantic heading structure', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const heading = screen.getByRole('heading', { level: 1 });
        expect(heading).toHaveTextContent('Profiling');
      });
    });

    it('iframe has accessible title', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('pyroscope-iframe');
        expect(iframe).toHaveAttribute('title', 'Profiling');
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
        const iframe = screen.getByTestId('pyroscope-iframe');
        expect(iframe).toHaveClass('w-full');
      });
    });

    it('iframe has correct height class', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('pyroscope-iframe');
        expect(iframe).toHaveClass('h-[calc(100vh-73px)]');
      });
    });

    it('iframe has no border', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('pyroscope-iframe');
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
        batch_window_seconds: 90,
        batch_idle_timeout_seconds: 30,
        detection_confidence_threshold: 0.5,
        grafana_url: '/grafana',
        debug: false,
      });

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('pyroscope-iframe');
        const src = iframe.getAttribute('src');
        // Verify URL structure
        expect(src).toContain('/grafana/d/hsi-profiling/hsi-profiling?');
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
        batch_window_seconds: 90,
        batch_idle_timeout_seconds: 30,
        detection_confidence_threshold: 0.5,
        grafana_url: 'http://localhost:3002',
        debug: false,
      });

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('pyroscope-iframe');
        const src = iframe.getAttribute('src');
        // Should resolve localhost to current hostname (in tests, it's empty/localhost)
        expect(src).toContain('/d/hsi-profiling/hsi-profiling?');
      });
    });
  });
});
