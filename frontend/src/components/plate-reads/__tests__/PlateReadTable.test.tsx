/**
 * @fileoverview Tests for PlateReadTable component.
 *
 * Tests the paginated table display including rendering,
 * pagination controls, row interactions, and empty states.
 */
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { server } from '../../../mocks/server';
import { renderWithProviders } from '../../../test-utils/renderWithProviders';
import PlateReadTable from '../PlateReadTable';

import type { PlateRead } from '../../../types/plateRead';

// Base URL from environment
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';

describe('PlateReadTable', () => {
  // Setup mock handlers for vehicle matching
  beforeEach(() => {
    server.use(
      http.get(`${BASE_URL}/api/household/vehicles`, () => {
        return HttpResponse.json([]);
      }),
      http.get(`${BASE_URL}/api/household/members`, () => {
        return HttpResponse.json([]);
      })
    );
  });

  // Mock plate read data
  const mockPlateRead: PlateRead = {
    id: 1,
    camera_id: 'cam-1',
    timestamp: '2026-01-31T10:30:00Z',
    plate_text: 'ABC123',
    raw_text: 'ABC-123',
    detection_confidence: 0.95,
    ocr_confidence: 0.92,
    bbox: [100, 100, 200, 150],
    image_quality_score: 0.88,
    is_enhanced: false,
    is_blurry: false,
    created_at: '2026-01-31T10:30:01Z',
  };

  const mockPlateReads: PlateRead[] = [
    mockPlateRead,
    {
      ...mockPlateRead,
      id: 2,
      plate_text: 'XYZ789',
      ocr_confidence: 0.65,
      image_quality_score: 0.55,
      is_enhanced: true,
    },
    {
      ...mockPlateRead,
      id: 3,
      plate_text: 'DEF456',
      ocr_confidence: 0.45,
      image_quality_score: 0.35,
      is_blurry: true,
    },
  ];

  const defaultProps = {
    plateReads: mockPlateReads,
    total: 100,
    page: 1,
    pageSize: 25,
    onPageChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Table Headers', () => {
    it('renders all column headers', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} />);

      expect(screen.getByText('Timestamp')).toBeInTheDocument();
      expect(screen.getByText('Camera')).toBeInTheDocument();
      expect(screen.getByText('Plate Text')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
      expect(screen.getByText('Confidence')).toBeInTheDocument();
      expect(screen.getByText('Quality')).toBeInTheDocument();
      expect(screen.getByText('Actions')).toBeInTheDocument();
    });
  });

  describe('Table Data Rows', () => {
    it('renders plate reads data', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} />);

      expect(screen.getByText('ABC123')).toBeInTheDocument();
      expect(screen.getByText('XYZ789')).toBeInTheDocument();
      expect(screen.getByText('DEF456')).toBeInTheDocument();
    });

    it('displays camera IDs', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} />);

      expect(screen.getAllByText('cam-1')).toHaveLength(3);
    });

    it('formats timestamps correctly', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} />);

      // Check for formatted timestamp (format: "Jan 31, 10:30:00 AM")
      const timestamps = screen.getAllByText(/Jan 31/);
      expect(timestamps.length).toBeGreaterThan(0);
    });

    it('displays confidence badges with correct styling', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} />);

      // High confidence (92%)
      expect(screen.getByText('92.0%')).toBeInTheDocument();
      // Medium confidence (65%)
      expect(screen.getByText('65.0%')).toBeInTheDocument();
      // Low confidence (45%)
      expect(screen.getByText('45.0%')).toBeInTheDocument();
    });

    it('displays quality labels', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} />);

      expect(screen.getByText('Good')).toBeInTheDocument(); // 0.88 -> Good
      expect(screen.getByText('Fair')).toBeInTheDocument(); // 0.55 -> Fair
      expect(screen.getByText('Poor')).toBeInTheDocument(); // 0.35 -> Poor
    });

    it('shows enhancement indicator for enhanced reads', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} />);

      expect(screen.getByLabelText('Low-light enhanced')).toBeInTheDocument();
    });

    it('shows blur indicator for blurry reads', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} />);

      expect(screen.getByLabelText('Motion blur detected')).toBeInTheDocument();
    });
  });

  describe('Search Text Highlighting', () => {
    it('highlights matching search text', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} searchText="ABC" />);

      // The highlight is rendered as a <mark> element
      const highlight = screen.getByText('ABC');
      expect(highlight.tagName).toBe('MARK');
    });

    it('does not highlight when search text does not match', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} searchText="QQQ" />);

      // ABC123 should not have a <mark> element
      const plateText = screen.getByText('ABC123');
      expect(plateText.tagName).not.toBe('MARK');
    });
  });

  describe('Row Interactions', () => {
    it('calls onRowClick when row is clicked', async () => {
      const onRowClick = vi.fn();
      const user = userEvent.setup();

      renderWithProviders(<PlateReadTable {...defaultProps} onRowClick={onRowClick} />);

      // Click on the first plate text
      const row = screen.getByText('ABC123').closest('tr');
      expect(row).toBeInTheDocument();
      await user.click(row!);

      expect(onRowClick).toHaveBeenCalledWith(mockPlateRead);
    });

    it('calls onRowClick when view button is clicked', async () => {
      const onRowClick = vi.fn();
      const user = userEvent.setup();

      renderWithProviders(<PlateReadTable {...defaultProps} onRowClick={onRowClick} />);

      const viewButtons = screen.getAllByLabelText(/View details for plate/);
      await user.click(viewButtons[0]);

      expect(onRowClick).toHaveBeenCalledWith(mockPlateRead);
    });

    it('supports keyboard navigation with Enter key', async () => {
      const onRowClick = vi.fn();
      const user = userEvent.setup();

      renderWithProviders(<PlateReadTable {...defaultProps} onRowClick={onRowClick} />);

      // Focus on the first row and press Enter
      const row = screen.getByText('ABC123').closest('tr');
      row?.focus();
      await user.keyboard('{Enter}');

      expect(onRowClick).toHaveBeenCalledWith(mockPlateRead);
    });

    it('supports keyboard navigation with Space key', async () => {
      const onRowClick = vi.fn();
      const user = userEvent.setup();

      renderWithProviders(<PlateReadTable {...defaultProps} onRowClick={onRowClick} />);

      const row = screen.getByText('ABC123').closest('tr');
      row?.focus();
      await user.keyboard(' ');

      expect(onRowClick).toHaveBeenCalledWith(mockPlateRead);
    });

    it('rows are focusable when onRowClick is provided', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} onRowClick={vi.fn()} />);

      const row = screen.getByText('ABC123').closest('tr');
      expect(row).toHaveAttribute('tabindex', '0');
      expect(row).toHaveAttribute('role', 'button');
    });

    it('rows are not focusable when onRowClick is not provided', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} />);

      const row = screen.getByText('ABC123').closest('tr');
      expect(row).not.toHaveAttribute('tabindex');
      expect(row).not.toHaveAttribute('role', 'button');
    });
  });

  describe('Empty State', () => {
    it('shows empty state when no plate reads', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} plateReads={[]} total={0} />);

      expect(screen.getByText('No plate reads found')).toBeInTheDocument();
      expect(
        screen.getByText('Try adjusting your filters or check back later')
      ).toBeInTheDocument();
    });

    it('shows search-specific empty message when search text is present', () => {
      renderWithProviders(
        <PlateReadTable {...defaultProps} plateReads={[]} total={0} searchText="XYZ999" />
      );

      expect(screen.getByText('No plate reads found')).toBeInTheDocument();
      expect(screen.getByText('No plates matching "XYZ999"')).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('shows loading skeleton when isLoading is true', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} isLoading={true} />);

      // Should not show actual data
      expect(screen.queryByText('ABC123')).not.toBeInTheDocument();

      // Should show skeleton placeholders (animated divs)
      const skeletonRows = document.querySelectorAll('tr .animate-pulse');
      expect(skeletonRows.length).toBeGreaterThan(0);
    });
  });

  describe('Pagination', () => {
    it('displays pagination info', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} />);

      // Check for pagination info text
      const paginationInfo = screen.getByText(/Showing/).closest('div');
      expect(paginationInfo).toBeInTheDocument();
      expect(paginationInfo?.textContent).toContain('1');
      expect(paginationInfo?.textContent).toContain('25');
      expect(paginationInfo?.textContent).toContain('100');
    });

    it('calculates correct page info', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} page={2} pageSize={25} total={100} />);

      // Check that showing text contains correct range for page 2
      const paginationInfo = screen.getByText(/Showing/).closest('div');
      expect(paginationInfo).toBeInTheDocument();
      expect(paginationInfo?.textContent).toContain('26');
      expect(paginationInfo?.textContent).toContain('50');
    });

    it('handles last page correctly', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} page={4} pageSize={25} total={90} />);

      // On page 4 with 25 per page and 90 total: 76-90
      // The pagination info is in the format: Showing <span>76</span> to <span>90</span> of <span>90</span> results
      const paginationInfo = screen.getByText(/Showing/).closest('div');
      expect(paginationInfo).toBeInTheDocument();
      expect(paginationInfo?.textContent).toContain('76');
      expect(paginationInfo?.textContent).toContain('90');
    });

    it('shows page X of Y', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} page={2} total={100} />);

      expect(screen.getByText(/Page/)).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument(); // 100/25 = 4 pages
    });

    it('calls onPageChange when first page button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateReadTable {...defaultProps} page={3} />);

      await user.click(screen.getByLabelText('First page'));

      expect(defaultProps.onPageChange).toHaveBeenCalledWith(1);
    });

    it('calls onPageChange when previous page button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateReadTable {...defaultProps} page={3} />);

      await user.click(screen.getByLabelText('Previous page'));

      expect(defaultProps.onPageChange).toHaveBeenCalledWith(2);
    });

    it('calls onPageChange when next page button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateReadTable {...defaultProps} page={2} />);

      await user.click(screen.getByLabelText('Next page'));

      expect(defaultProps.onPageChange).toHaveBeenCalledWith(3);
    });

    it('calls onPageChange when last page button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateReadTable {...defaultProps} page={2} />);

      await user.click(screen.getByLabelText('Last page'));

      expect(defaultProps.onPageChange).toHaveBeenCalledWith(4); // 100/25 = 4
    });

    it('disables first and previous buttons on first page', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} page={1} />);

      expect(screen.getByLabelText('First page')).toBeDisabled();
      expect(screen.getByLabelText('Previous page')).toBeDisabled();
    });

    it('disables next and last buttons on last page', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} page={4} total={100} />);

      expect(screen.getByLabelText('Next page')).toBeDisabled();
      expect(screen.getByLabelText('Last page')).toBeDisabled();
    });

    it('does not show pagination when total is 0', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} plateReads={[]} total={0} />);

      expect(screen.queryByLabelText('First page')).not.toBeInTheDocument();
    });
  });

  describe('Page Size Selector', () => {
    it('renders page size selector when onPageSizeChange is provided', () => {
      const onPageSizeChange = vi.fn();
      renderWithProviders(<PlateReadTable {...defaultProps} onPageSizeChange={onPageSizeChange} />);

      expect(screen.getByText('Per page:')).toBeInTheDocument();
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });

    it('does not render page size selector when onPageSizeChange is not provided', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} />);

      expect(screen.queryByText('Per page:')).not.toBeInTheDocument();
    });

    it('calls onPageSizeChange when page size is changed', async () => {
      const user = userEvent.setup();
      const onPageSizeChange = vi.fn();
      renderWithProviders(<PlateReadTable {...defaultProps} onPageSizeChange={onPageSizeChange} />);

      const select = screen.getByRole('combobox');
      await user.selectOptions(select, '50');

      expect(onPageSizeChange).toHaveBeenCalledWith(50);
    });

    it('displays page size options', () => {
      const onPageSizeChange = vi.fn();
      renderWithProviders(<PlateReadTable {...defaultProps} onPageSizeChange={onPageSizeChange} />);

      const select = screen.getByRole('combobox');
      expect(select).toContainHTML('<option value="10">10</option>');
      expect(select).toContainHTML('<option value="25">25</option>');
      expect(select).toContainHTML('<option value="50">50</option>');
      expect(select).toContainHTML('<option value="100">100</option>');
    });
  });

  describe('Accessibility', () => {
    it('has proper table structure', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} />);

      expect(screen.getByRole('table')).toBeInTheDocument();
      expect(screen.getAllByRole('columnheader')).toHaveLength(7);
      expect(screen.getAllByRole('row').length).toBeGreaterThan(1); // Header + data rows
    });

    it('view buttons have proper aria-labels', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} />);

      expect(screen.getByLabelText('View details for plate ABC123')).toBeInTheDocument();
      expect(screen.getByLabelText('View details for plate XYZ789')).toBeInTheDocument();
    });

    it('pagination buttons have proper aria-labels', () => {
      renderWithProviders(<PlateReadTable {...defaultProps} />);

      expect(screen.getByLabelText('First page')).toBeInTheDocument();
      expect(screen.getByLabelText('Previous page')).toBeInTheDocument();
      expect(screen.getByLabelText('Next page')).toBeInTheDocument();
      expect(screen.getByLabelText('Last page')).toBeInTheDocument();
    });
  });
});
