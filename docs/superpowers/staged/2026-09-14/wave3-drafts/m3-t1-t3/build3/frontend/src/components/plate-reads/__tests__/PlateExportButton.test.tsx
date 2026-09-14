/**
 * @fileoverview Tests for PlateExportButton component.
 *
 * Tests the export functionality including dropdown menu,
 * progress tracking, and error states.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { fetchPlateReads } from '../../../services/plateReadsApi';
import PlateExportButton from '../PlateExportButton';

import type { PlateReadFilters } from '../../../types/plateRead';

// Mock the API
vi.mock('../../../services/plateReadsApi', () => ({
  fetchPlateReads: vi.fn(),
}));

// Mock the logger
vi.mock('../../../services/logger', () => ({
  logger: {
    info: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
  },
}));

const mockFetchPlateReads = vi.mocked(fetchPlateReads);

describe('PlateExportButton', () => {
  const defaultFilters: PlateReadFilters = {};

  const mockPlateReads = [
    {
      id: 1,
      camera_id: 'cam-1',
      timestamp: '2026-01-31T10:00:00Z',
      plate_text: 'ABC123',
      raw_text: 'ABC-123',
      detection_confidence: 0.95,
      ocr_confidence: 0.92,
      bbox: [100, 100, 200, 150] as [number, number, number, number],
      image_quality_score: 0.88,
      is_enhanced: false,
      is_blurry: false,
      created_at: '2026-01-31T10:00:01Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchPlateReads.mockResolvedValue({
      plate_reads: mockPlateReads,
      total: 1,
      page: 1,
      page_size: 100,
    });

    // Mock URL methods using vi.spyOn to avoid unbound-method lint errors
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial State', () => {
    it('renders export button', () => {
      render(<PlateExportButton filters={defaultFilters} totalCount={10} />);

      expect(screen.getByTestId('export-button')).toBeInTheDocument();
      expect(screen.getByText('Export')).toBeInTheDocument();
    });

    it('disables button when totalCount is 0', () => {
      render(<PlateExportButton filters={defaultFilters} totalCount={0} />);

      expect(screen.getByTestId('export-button')).toBeDisabled();
    });

    it('disables button when disabled prop is true', () => {
      render(<PlateExportButton filters={defaultFilters} totalCount={10} disabled={true} />);

      expect(screen.getByTestId('export-button')).toBeDisabled();
    });
  });

  describe('Dropdown Menu', () => {
    it('opens dropdown menu on button click', async () => {
      const user = userEvent.setup();
      render(<PlateExportButton filters={defaultFilters} totalCount={10} />);

      await user.click(screen.getByTestId('export-button'));

      expect(screen.getByTestId('export-menu')).toBeInTheDocument();
    });

    it('shows CSV export option', async () => {
      const user = userEvent.setup();
      render(<PlateExportButton filters={defaultFilters} totalCount={10} />);

      await user.click(screen.getByTestId('export-button'));

      expect(screen.getByTestId('export-csv-option')).toBeInTheDocument();
      expect(screen.getByText('Export as CSV')).toBeInTheDocument();
    });

    it('shows record count in menu', async () => {
      const user = userEvent.setup();
      render(<PlateExportButton filters={defaultFilters} totalCount={42} />);

      await user.click(screen.getByTestId('export-button'));

      expect(screen.getByText('42 records')).toBeInTheDocument();
    });

    it('closes dropdown when clicking backdrop', async () => {
      const user = userEvent.setup();
      render(<PlateExportButton filters={defaultFilters} totalCount={10} />);

      await user.click(screen.getByTestId('export-button'));
      expect(screen.getByTestId('export-menu')).toBeInTheDocument();

      await user.click(screen.getByTestId('export-menu-backdrop'));

      expect(screen.queryByTestId('export-menu')).not.toBeInTheDocument();
    });
  });

  describe('Export Process', () => {
    it('shows progress during export', async () => {
      const user = userEvent.setup();

      // Make the fetch take longer
      mockFetchPlateReads.mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(
              () =>
                resolve({
                  plate_reads: mockPlateReads,
                  total: 1,
                  page: 1,
                  page_size: 100,
                }),
              100
            )
          )
      );

      render(<PlateExportButton filters={defaultFilters} totalCount={1} />);

      await user.click(screen.getByTestId('export-button'));
      await user.click(screen.getByTestId('export-csv-option'));

      // Should show progress indicator
      await waitFor(() => {
        expect(screen.getByTestId('export-progress')).toBeInTheDocument();
      });

      expect(screen.getByText('Exporting...')).toBeInTheDocument();
    });

    it('shows completed state after successful export', async () => {
      const user = userEvent.setup();
      render(<PlateExportButton filters={defaultFilters} totalCount={1} />);

      await user.click(screen.getByTestId('export-button'));
      await user.click(screen.getByTestId('export-csv-option'));

      await waitFor(() => {
        expect(screen.getByTestId('export-completed')).toBeInTheDocument();
      });

      expect(screen.getByText('Export complete')).toBeInTheDocument();
      expect(screen.getByText('(1 records)')).toBeInTheDocument();
    });

    it('fetches data with correct filters', async () => {
      const user = userEvent.setup();
      const filters: PlateReadFilters = {
        camera_id: 'cam-1',
        min_confidence: 0.8,
      };

      render(<PlateExportButton filters={filters} totalCount={1} />);

      await user.click(screen.getByTestId('export-button'));
      await user.click(screen.getByTestId('export-csv-option'));

      await waitFor(() => {
        expect(mockFetchPlateReads).toHaveBeenCalledWith(
          expect.objectContaining({
            camera_id: 'cam-1',
            min_confidence: 0.8,
            page: 1,
            page_size: 100,
          })
        );
      });
    });

    it('paginates through all results', async () => {
      const user = userEvent.setup();

      // Return 2 pages of results, then empty for any additional requests
      mockFetchPlateReads
        .mockResolvedValueOnce({
          plate_reads: mockPlateReads,
          total: 150,
          page: 1,
          page_size: 100,
        })
        .mockResolvedValueOnce({
          plate_reads: [{ ...mockPlateReads[0], id: 2 }],
          total: 150,
          page: 2,
          page_size: 100,
        })
        .mockResolvedValue({
          plate_reads: [],
          total: 150,
          page: 3,
          page_size: 100,
        });

      render(<PlateExportButton filters={defaultFilters} totalCount={150} />);

      await user.click(screen.getByTestId('export-button'));
      await user.click(screen.getByTestId('export-csv-option'));

      await waitFor(() => {
        expect(screen.getByTestId('export-completed')).toBeInTheDocument();
      });

      // Should have fetched at least 2 pages (may fetch an extra page to confirm no more results)
      expect(mockFetchPlateReads).toHaveBeenCalledWith(expect.objectContaining({ page: 1 }));
      expect(mockFetchPlateReads).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }));
    });
  });

  describe('Error Handling', () => {
    it('shows error state when export fails', async () => {
      const user = userEvent.setup();
      mockFetchPlateReads.mockRejectedValue(new Error('Network error'));

      render(<PlateExportButton filters={defaultFilters} totalCount={1} />);

      await user.click(screen.getByTestId('export-button'));
      await user.click(screen.getByTestId('export-csv-option'));

      await waitFor(() => {
        expect(screen.getByTestId('export-failed')).toBeInTheDocument();
      });

      expect(screen.getByText('Export failed')).toBeInTheDocument();
      expect(screen.getByText('(Network error)')).toBeInTheDocument();
    });

    it('allows retry after failure', async () => {
      const user = userEvent.setup();
      mockFetchPlateReads.mockRejectedValueOnce(new Error('Network error'));

      render(<PlateExportButton filters={defaultFilters} totalCount={1} />);

      await user.click(screen.getByTestId('export-button'));
      await user.click(screen.getByTestId('export-csv-option'));

      await waitFor(() => {
        expect(screen.getByTestId('export-failed')).toBeInTheDocument();
      });

      // Click try again
      mockFetchPlateReads.mockResolvedValue({
        plate_reads: mockPlateReads,
        total: 1,
        page: 1,
        page_size: 100,
      });

      await user.click(screen.getByTestId('retry-export-button'));

      // Should be back to idle state, ready for new export
      await waitFor(() => {
        expect(screen.queryByTestId('export-failed')).not.toBeInTheDocument();
      });
    });
  });

  describe('Cancel Export', () => {
    it('shows cancel button during export', async () => {
      const user = userEvent.setup();

      mockFetchPlateReads.mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(
              () =>
                resolve({
                  plate_reads: mockPlateReads,
                  total: 1,
                  page: 1,
                  page_size: 100,
                }),
              1000
            )
          )
      );

      render(<PlateExportButton filters={defaultFilters} totalCount={1} />);

      await user.click(screen.getByTestId('export-button'));
      await user.click(screen.getByTestId('export-csv-option'));

      await waitFor(() => {
        expect(screen.getByTestId('cancel-export-button')).toBeInTheDocument();
      });
    });

    it('resets state when cancel is clicked', async () => {
      const user = userEvent.setup();

      mockFetchPlateReads.mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(
              () =>
                resolve({
                  plate_reads: mockPlateReads,
                  total: 1,
                  page: 1,
                  page_size: 100,
                }),
              1000
            )
          )
      );

      render(<PlateExportButton filters={defaultFilters} totalCount={1} />);

      await user.click(screen.getByTestId('export-button'));
      await user.click(screen.getByTestId('export-csv-option'));

      await waitFor(() => {
        expect(screen.getByTestId('cancel-export-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('cancel-export-button'));

      // Should be back to idle state
      await waitFor(() => {
        expect(screen.getByTestId('export-button')).toBeInTheDocument();
      });
    });
  });

  describe('New Export', () => {
    it('shows new export button after completion', async () => {
      const user = userEvent.setup();
      render(<PlateExportButton filters={defaultFilters} totalCount={1} />);

      await user.click(screen.getByTestId('export-button'));
      await user.click(screen.getByTestId('export-csv-option'));

      await waitFor(() => {
        expect(screen.getByTestId('export-completed')).toBeInTheDocument();
      });

      expect(screen.getByTestId('new-export-button')).toBeInTheDocument();
    });

    it('resets to idle state when new export is clicked', async () => {
      const user = userEvent.setup();
      render(<PlateExportButton filters={defaultFilters} totalCount={1} />);

      await user.click(screen.getByTestId('export-button'));
      await user.click(screen.getByTestId('export-csv-option'));

      await waitFor(() => {
        expect(screen.getByTestId('new-export-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('new-export-button'));

      // Should be back to idle state
      expect(screen.getByTestId('export-button')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper aria attributes on button', () => {
      render(<PlateExportButton filters={defaultFilters} totalCount={10} />);

      const button = screen.getByTestId('export-button');
      expect(button).toHaveAttribute('aria-haspopup', 'menu');
      expect(button).toHaveAttribute('aria-expanded', 'false');
    });

    it('updates aria-expanded when menu opens', async () => {
      const user = userEvent.setup();
      render(<PlateExportButton filters={defaultFilters} totalCount={10} />);

      const button = screen.getByTestId('export-button');
      await user.click(button);

      expect(button).toHaveAttribute('aria-expanded', 'true');
    });

    it('menu has proper role', async () => {
      const user = userEvent.setup();
      render(<PlateExportButton filters={defaultFilters} totalCount={10} />);

      await user.click(screen.getByTestId('export-button'));

      expect(screen.getByTestId('export-menu')).toHaveAttribute('role', 'menu');
    });

    it('menu items have proper role', async () => {
      const user = userEvent.setup();
      render(<PlateExportButton filters={defaultFilters} totalCount={10} />);

      await user.click(screen.getByTestId('export-button'));

      expect(screen.getByTestId('export-csv-option')).toHaveAttribute('role', 'menuitem');
    });

    it('progress bar has proper aria attributes', async () => {
      const user = userEvent.setup();

      mockFetchPlateReads.mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(
              () =>
                resolve({
                  plate_reads: mockPlateReads,
                  total: 1,
                  page: 1,
                  page_size: 100,
                }),
              500
            )
          )
      );

      render(<PlateExportButton filters={defaultFilters} totalCount={1} />);

      await user.click(screen.getByTestId('export-button'));
      await user.click(screen.getByTestId('export-csv-option'));

      await waitFor(() => {
        const progressBar = screen.getByTestId('export-progress-bar');
        expect(progressBar).toHaveAttribute('role', 'progressbar');
        expect(progressBar).toHaveAttribute('aria-valuemin', '0');
        expect(progressBar).toHaveAttribute('aria-valuemax', '100');
      });
    });
  });
});
