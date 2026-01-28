/**
 * Tests for AIPerformancePage component
 * Tests the Grafana iframe embed implementation
 */

import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import AIPerformancePage from './AIPerformancePage';
import * as api from '../../services/api';

// Mock the API functions
vi.mock('../../services/api', () => ({
  fetchConfig: vi.fn(() => Promise.resolve({ grafana_url: '/grafana' })),
  fetchModelZooCompactStatus: vi.fn(() =>
    Promise.resolve({
      models: [
        {
          name: 'yolo11-license-plate',
          display_name: 'YOLO11 License Plate',
          category: 'Detection',
          status: 'loaded',
          vram_mb: 300,
          last_used_at: null,
          enabled: true,
        },
      ],
      total_models: 1,
      loaded_count: 1,
      disabled_count: 0,
      vram_budget_mb: 1650,
      vram_used_mb: 300,
      timestamp: '2026-01-04T12:00:00Z',
    })
  ),
  fetchModelZooLatencyHistory: vi.fn(() =>
    Promise.resolve({
      model_name: 'yolo11-license-plate',
      display_name: 'YOLO11 License Plate',
      snapshots: [],
      window_minutes: 60,
      bucket_seconds: 60,
      has_data: false,
      timestamp: '2026-01-04T12:00:00Z',
    })
  ),
}));

const renderWithRouter = () => {
  return render(
    <MemoryRouter>
      <AIPerformancePage />
    </MemoryRouter>
  );
};

describe('AIPerformancePage', () => {
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
        expect(screen.getByText('AI Performance')).toBeInTheDocument();
      });
    });

    it('renders the refresh button', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      await waitFor(() => {
        expect(screen.getByTestId('ai-performance-refresh-button')).toBeInTheDocument();
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
        expect(screen.getByTestId('ai-performance-page')).toBeInTheDocument();
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
      expect(screen.getByTestId('ai-performance-loading')).toBeInTheDocument();

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
        expect(screen.queryByTestId('ai-performance-loading')).not.toBeInTheDocument();
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

      const loadingContainer = screen.getByTestId('ai-performance-loading');
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
      vi.mocked(api.fetchConfig).mockRejectedValue(new Error('Config fetch failed'));
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('ai-performance-error')).toBeInTheDocument();
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
        expect(screen.getByTestId('ai-performance-page')).toBeInTheDocument();
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
        const iframe = screen.getByTestId('grafana-iframe');
        expect(iframe).toHaveAttribute(
          'src',
          'http://grafana.example.com/d/ai-services/ai-services?orgId=1&kiosk=1&theme=dark&refresh=30s'
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
          '/grafana/d/ai-services/ai-services?orgId=1&kiosk=1&theme=dark&refresh=30s'
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
        const externalLink = screen.getByTestId('grafana-external-link');
        expect(externalLink).toHaveAttribute(
          'href',
          'http://grafana.example.com/d/ai-services/ai-services?orgId=1'
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
        expect(screen.getByTestId('ai-performance-refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('ai-performance-refresh-button');
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
        expect(screen.getByTestId('ai-performance-refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('ai-performance-refresh-button');
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
        expect(screen.getByTestId('ai-performance-refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('ai-performance-refresh-button');
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
        const refreshButton = screen.getByTestId('ai-performance-refresh-button');
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
        expect(heading).toHaveTextContent('AI Performance');
      });
    });

    it('iframe has accessible title', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('grafana-iframe');
        expect(iframe).toHaveAttribute('title', 'AI Performance Dashboard');
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
        expect(iframe).toHaveClass('h-[600px]');
      });
    });

    it('iframe has border styling', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const iframe = screen.getByTestId('grafana-iframe');
        expect(iframe).toHaveClass('border');
        expect(iframe).toHaveClass('border-gray-800');
        expect(iframe).toHaveClass('rounded-lg');
      });
    });
  });

  describe('ModelZooSection integration', () => {
    it('renders ModelZooSection component', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByTestId('model-zoo-section')).toBeInTheDocument();
      });
    });

    it('ModelZooSection is positioned above Grafana iframe', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const modelZooSection = screen.getByTestId('model-zoo-section');
        const iframe = screen.getByTestId('grafana-iframe');
        // Both should be in the document
        expect(modelZooSection).toBeInTheDocument();
        expect(iframe).toBeInTheDocument();
        // ModelZooSection should appear before iframe in DOM order
        // The scrollable container contains ModelZooSection and a div containing the iframe
        const scrollContainer = modelZooSection.parentElement;
        expect(scrollContainer).not.toBeNull();
        const children = scrollContainer ? Array.from(scrollContainer.children) : [];
        // First child is ModelZooSection, second is the iframe container div
        const modelZooIndex = children.findIndex(
          (child) => child === modelZooSection || child.contains(modelZooSection)
        );
        const iframeContainerIndex = children.findIndex((child) => child.contains(iframe));
        expect(modelZooIndex).toBeLessThan(iframeContainerIndex);
      });
    });

    it('ModelZooSection displays Model Zoo title', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(screen.getByText('Model Zoo')).toBeInTheDocument();
      });
    });

    it('ModelZooSection has padding class applied', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const modelZooSection = screen.getByTestId('model-zoo-section');
        expect(modelZooSection).toHaveClass('p-8');
      });
    });

    it('page has scrollable content area containing ModelZooSection and iframe', async () => {
      renderWithRouter();
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        const modelZooSection = screen.getByTestId('model-zoo-section');
        const scrollContainer = modelZooSection.parentElement;
        expect(scrollContainer).toHaveClass('overflow-y-auto');
      });
    });
  });
});
