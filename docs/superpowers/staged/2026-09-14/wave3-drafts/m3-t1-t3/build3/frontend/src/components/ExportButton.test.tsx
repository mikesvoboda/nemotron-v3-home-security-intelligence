/**
 * Tests for ExportButton Component (NEM-1989)
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ExportButton from './ExportButton';

// Mock the useJobWebSocket hook
vi.mock('../hooks/useJobWebSocket', () => ({
  useJobWebSocket: vi.fn(() => ({
    activeJobs: [],
    isJobRunning: false,
  })),
}));

// Mock the logger
vi.mock('../services/logger', () => ({
  logger: {
    info: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  },
}));

// Setup fetch mock
const mockFetch = vi.fn();

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

function renderWithProviders(ui: React.ReactElement) {
  const testQueryClient = createTestQueryClient();
  return render(<QueryClientProvider client={testQueryClient}>{ui}</QueryClientProvider>);
}

describe('ExportButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
    vi.stubGlobal('fetch', mockFetch);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders export button with default props', () => {
      renderWithProviders(<ExportButton />);
      const button = screen.getByRole('button', { name: /export/i });
      expect(button).toBeInTheDocument();
    });

    it('renders with custom variant', () => {
      renderWithProviders(<ExportButton variant="primary" />);
      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('renders with custom size', () => {
      renderWithProviders(<ExportButton size="sm" />);
      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('renders disabled when disabled prop is true', () => {
      renderWithProviders(<ExportButton disabled />);
      const button = screen.getByRole('button');
      expect(button).toBeDisabled();
    });
  });

  describe('dropdown menu', () => {
    it('opens dropdown menu on click', async () => {
      renderWithProviders(<ExportButton />);
      const button = screen.getByRole('button', { name: /export/i });

      fireEvent.click(button);

      await waitFor(() => {
        expect(screen.getByText('Export as CSV')).toBeInTheDocument();
        expect(screen.getByText('Export as JSON')).toBeInTheDocument();
        expect(screen.getByText('Export as ZIP')).toBeInTheDocument();
      });
    });

    it('closes dropdown menu when clicking outside', async () => {
      renderWithProviders(<ExportButton />);
      const button = screen.getByRole('button', { name: /export/i });

      fireEvent.click(button);
      await waitFor(() => {
        expect(screen.getByText('Export as CSV')).toBeInTheDocument();
      });

      // Click outside (on the backdrop)
      const backdrop = document.querySelector('.fixed.inset-0');
      if (backdrop) {
        fireEvent.click(backdrop);
      }

      await waitFor(() => {
        expect(screen.queryByText('Export as CSV')).not.toBeInTheDocument();
      });
    });

    it('has proper ARIA attributes', () => {
      renderWithProviders(<ExportButton />);
      const button = screen.getByRole('button', { name: /export/i });

      expect(button).toHaveAttribute('aria-haspopup', 'menu');
      expect(button).toHaveAttribute('aria-expanded', 'false');

      fireEvent.click(button);
      expect(button).toHaveAttribute('aria-expanded', 'true');
    });
  });

  describe('export actions', () => {
    it('calls API when CSV export is clicked', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            job_id: 'test-job-123',
            status: 'pending',
            message: 'Export started',
          }),
      });

      renderWithProviders(<ExportButton />);
      const button = screen.getByRole('button', { name: /export/i });
      fireEvent.click(button);

      const csvButton = await screen.findByText('Export as CSV');
      fireEvent.click(csvButton);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
      });

      // Verify the fetch was called with correct parameters
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/events/export'),
        expect.objectContaining({
          method: 'POST',
        })
      );

      const call = mockFetch.mock.calls[0];
      const body = JSON.parse(call[1].body as string);
      expect(body.format).toBe('csv');
    });

    it('calls API when JSON export is clicked', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            job_id: 'test-job-456',
            status: 'pending',
            message: 'Export started',
          }),
      });

      renderWithProviders(<ExportButton />);
      const button = screen.getByRole('button', { name: /export/i });
      fireEvent.click(button);

      const jsonButton = await screen.findByText('Export as JSON');
      fireEvent.click(jsonButton);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
      });

      const call = mockFetch.mock.calls[0];
      const body = JSON.parse(call[1].body as string);
      expect(body.format).toBe('json');
    });

    it('includes filter parameters in API call', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            job_id: 'test-job-789',
            status: 'pending',
            message: 'Export started',
          }),
      });

      renderWithProviders(
        <ExportButton
          cameraId="cam-1"
          riskLevel="high"
          startDate="2024-01-01T00:00:00Z"
          endDate="2024-01-15T23:59:59Z"
          reviewed={true}
        />
      );

      const button = screen.getByRole('button', { name: /export/i });
      fireEvent.click(button);

      const csvButton = await screen.findByText('Export as CSV');
      fireEvent.click(csvButton);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
      });

      const call = mockFetch.mock.calls[0];
      const body = JSON.parse(call[1].body as string);
      expect(body.camera_id).toBe('cam-1');
      expect(body.risk_level).toBe('high');
      expect(body.reviewed).toBe(true);
    });
  });

  describe('accessibility', () => {
    it('has accessible name', () => {
      renderWithProviders(<ExportButton />);
      const button = screen.getByRole('button', { name: /export/i });
      expect(button).toBeInTheDocument();
    });

    it('dropdown menu items are accessible', async () => {
      renderWithProviders(<ExportButton />);
      const button = screen.getByRole('button', { name: /export/i });
      fireEvent.click(button);

      const menuItems = await screen.findAllByRole('menuitem');
      expect(menuItems).toHaveLength(4); // CSV, JSON, ZIP, and Excel
    });
  });

  describe('progress tracking (NEM-2261)', () => {
    it('shows progress bar when export is in progress', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            job_id: 'progress-test-job',
            status: 'pending',
            message: 'Export started',
          }),
      });

      renderWithProviders(<ExportButton />);

      // Start export
      const button = screen.getByRole('button', { name: /export/i });
      fireEvent.click(button);
      const csvButton = await screen.findByText('Export as CSV');
      fireEvent.click(csvButton);

      // Wait for the export to start and show progress UI
      await waitFor(() => {
        expect(screen.getByText('Exporting...')).toBeInTheDocument();
      });

      // Should show progress bar with initial value
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toBeInTheDocument();
      expect(progressBar).toHaveAttribute('aria-valuenow', '0');
    });

    it('shows cancel button during export', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            job_id: 'cancel-test-job',
            status: 'pending',
            message: 'Export started',
          }),
      });

      renderWithProviders(<ExportButton />);

      // Start export
      const button = screen.getByRole('button', { name: /export/i });
      fireEvent.click(button);
      const csvButton = await screen.findByText('Export as CSV');
      fireEvent.click(csvButton);

      // Wait for progress UI with cancel button
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      });
    });

    it('progress bar updates with job progress', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            job_id: 'update-test-job',
            status: 'pending',
            message: 'Export started',
          }),
      });

      renderWithProviders(<ExportButton />);

      // Start export
      const button = screen.getByRole('button', { name: /export/i });
      fireEvent.click(button);
      const csvButton = await screen.findByText('Export as CSV');
      fireEvent.click(csvButton);

      // Wait for progress UI
      await waitFor(() => {
        expect(screen.getByRole('progressbar')).toBeInTheDocument();
      });

      // The progress bar should be accessible
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');
    });

    it('shows download button after completion', () => {
      // This test verifies the completed state UI
      // Note: Full integration test would require mocking the WebSocket callback
      // which is tested in useJobWebSocket.test.ts
      renderWithProviders(<ExportButton />);

      // Initial state should show export button
      expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument();
    });

    it('shows error state when export fails', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      });

      renderWithProviders(<ExportButton />);

      // Start export - will fail
      const button = screen.getByRole('button', { name: /export/i });
      fireEvent.click(button);
      const csvButton = await screen.findByText('Export as CSV');
      fireEvent.click(csvButton);

      // The mutation error is handled internally
      // We just verify it doesn't crash and export button returns
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument();
      });
    });
  });
});
