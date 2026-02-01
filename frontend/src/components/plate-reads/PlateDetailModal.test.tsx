/**
 * Tests for PlateDetailModal component
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { describe, expect, it, vi, beforeAll, afterAll, afterEach } from 'vitest';

import PlateDetailModal from './PlateDetailModal';

import type { PlateRead, PlateReadListResponse } from '../../types/plateRead';

// ============================================================================
// Test Data
// ============================================================================

const mockPlateReads: PlateRead[] = [
  {
    id: 1,
    camera_id: 'front_gate',
    timestamp: '2024-01-15T10:30:00Z',
    plate_text: 'ABC123',
    raw_text: 'ABC-123',
    detection_confidence: 0.95,
    ocr_confidence: 0.92,
    bbox: [100, 200, 300, 250],
    image_quality_score: 0.88,
    is_enhanced: false,
    is_blurry: false,
    created_at: '2024-01-15T10:30:01Z',
  },
  {
    id: 2,
    camera_id: 'back_parking',
    timestamp: '2024-01-15T14:45:00Z',
    plate_text: 'ABC123',
    raw_text: 'ABC-123',
    detection_confidence: 0.88,
    ocr_confidence: 0.85,
    bbox: [150, 180, 350, 230],
    image_quality_score: 0.72,
    is_enhanced: true,
    is_blurry: false,
    created_at: '2024-01-15T14:45:01Z',
  },
  {
    id: 3,
    camera_id: 'front_gate',
    timestamp: '2024-01-16T08:15:00Z',
    plate_text: 'ABC123',
    raw_text: 'ABC123',
    detection_confidence: 0.78,
    ocr_confidence: 0.65,
    bbox: [120, 190, 320, 240],
    image_quality_score: 0.45,
    is_enhanced: false,
    is_blurry: true,
    created_at: '2024-01-16T08:15:01Z',
  },
];

const mockResponse: PlateReadListResponse = {
  plate_reads: mockPlateReads,
  total: 3,
  page: 1,
  page_size: 20,
};

const emptyResponse: PlateReadListResponse = {
  plate_reads: [],
  total: 0,
  page: 1,
  page_size: 20,
};

// ============================================================================
// MSW Setup
// ============================================================================

const server = setupServer(
  http.get('*/api/plate-reads/search', ({ request }) => {
    const url = new URL(request.url);
    const text = url.searchParams.get('text');

    if (text === 'ABC123') {
      return HttpResponse.json(mockResponse);
    }
    if (text === 'NOTFOUND') {
      return HttpResponse.json(emptyResponse);
    }
    if (text === 'ERROR') {
      return new HttpResponse(null, { status: 500, statusText: 'Server Error' });
    }

    return HttpResponse.json(emptyResponse);
  })
);

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

// ============================================================================
// Test Helpers
// ============================================================================

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
    },
  });
}

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return {
    ...render(
      <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
    ),
    queryClient,
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('PlateDetailModal', () => {
  describe('rendering', () => {
    it('renders modal when plateText is provided', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('plate-detail-modal')).toBeInTheDocument();
      });
    });

    it('does not render when plateText is null', () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText={null} onClose={onClose} />
      );

      expect(screen.queryByTestId('plate-detail-modal')).not.toBeInTheDocument();
    });

    it('displays the plate text prominently in header', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('plate-text-display')).toHaveTextContent('ABC123');
      });
    });
  });

  describe('loading state', () => {
    it('shows loading skeleton while fetching data', () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      expect(screen.getByTestId('plate-detail-loading')).toBeInTheDocument();
    });
  });

  describe('data display', () => {
    it('displays summary statistics after loading', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('plate-summary')).toBeInTheDocument();
      });

      expect(screen.getByTestId('first-seen')).toBeInTheDocument();
      expect(screen.getByTestId('last-seen')).toBeInTheDocument();
      expect(screen.getByTestId('total-count')).toHaveTextContent('3');
      expect(screen.getByTestId('avg-confidence')).toBeInTheDocument();
    });

    it('displays camera breakdown', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('camera-breakdown')).toBeInTheDocument();
      });

      // Check camera names are displayed (may appear multiple times in breakdown and timeline)
      expect(screen.getAllByText('front_gate').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('back_parking').length).toBeGreaterThanOrEqual(1);
    });

    it('displays plate reads timeline', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('plate-reads-timeline')).toBeInTheDocument();
      });

      // Check all plate reads are rendered
      expect(screen.getByTestId('plate-read-item-1')).toBeInTheDocument();
      expect(screen.getByTestId('plate-read-item-2')).toBeInTheDocument();
      expect(screen.getByTestId('plate-read-item-3')).toBeInTheDocument();
    });

    it('displays enhanced badge for enhanced reads', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByText('Enhanced')).toBeInTheDocument();
      });
    });

    it('displays blurry badge for blurry reads', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByText('Blurry')).toBeInTheDocument();
      });
    });
  });

  describe('empty state', () => {
    it('shows empty state when no plate reads found', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="NOTFOUND" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('plate-detail-empty')).toBeInTheDocument();
      });

      expect(screen.getByText('No detections found')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error state when API fails', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ERROR" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('plate-detail-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Failed to load plate history')).toBeInTheDocument();
    });
  });

  describe('close behavior', () => {
    it('calls onClose when X button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('close-modal-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('close-modal-button'));

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when footer close button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('footer-close-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('footer-close-button'));

      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('pagination', () => {
    it('shows pagination controls when more than one page', async () => {
      // Override the handler to return paginated results
      server.use(
        http.get('*/api/plate-reads/search', () => {
          return HttpResponse.json({
            plate_reads: mockPlateReads,
            total: 50,
            page: 1,
            page_size: 20,
          });
        })
      );

      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('pagination-controls')).toBeInTheDocument();
      });

      expect(screen.getByTestId('prev-page-button')).toBeInTheDocument();
      expect(screen.getByTestId('next-page-button')).toBeInTheDocument();
      expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
    });

    it('disables prev button on first page', async () => {
      server.use(
        http.get('*/api/plate-reads/search', () => {
          return HttpResponse.json({
            plate_reads: mockPlateReads,
            total: 50,
            page: 1,
            page_size: 20,
          });
        })
      );

      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('prev-page-button')).toBeDisabled();
      });
    });

    it('navigates to next page when next button is clicked', async () => {
      let requestedPage = 1;
      server.use(
        http.get('*/api/plate-reads/search', ({ request }) => {
          const url = new URL(request.url);
          requestedPage = parseInt(url.searchParams.get('page') ?? '1');
          return HttpResponse.json({
            plate_reads: mockPlateReads,
            total: 50,
            page: requestedPage,
            page_size: 20,
          });
        })
      );

      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('next-page-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('next-page-button'));

      await waitFor(() => {
        expect(requestedPage).toBe(2);
      });
    });
  });

  describe('accessibility', () => {
    it('has accessible dialog role', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    it('has accessible dialog title', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('plate-detail-title')).toBeInTheDocument();
      });
    });

    it('close button has accessible label', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        expect(screen.getByLabelText('Close modal')).toBeInTheDocument();
      });
    });
  });

  describe('confidence display', () => {
    it('displays confidence badges for plate reads', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        // ConfidenceBadge has role="status" with aria-label containing confidence
        const confidenceBadges = screen.getAllByRole('status');
        expect(confidenceBadges.length).toBeGreaterThan(0);
      });
    });

    it('displays average confidence in summary', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        const avgConfidence = screen.getByTestId('avg-confidence');
        expect(avgConfidence).toBeInTheDocument();
        // Average of 0.92, 0.85, 0.65 = 0.8067 = 80.7%
        expect(avgConfidence.textContent).toMatch(/80\.\d%/);
      });
    });
  });

  describe('quality indicators', () => {
    it('displays quality labels for plate reads', async () => {
      const onClose = vi.fn();
      renderWithQueryClient(
        <PlateDetailModal plateText="ABC123" onClose={onClose} />
      );

      await waitFor(() => {
        // Quality labels: Excellent (>90), Good (>70), Fair (>50), Poor (<50)
        // Our mock data has 0.88 (Good), 0.72 (Good), 0.45 (Poor)
        expect(screen.getAllByText('Good').length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText('Poor')).toBeInTheDocument();
      });
    });
  });
});
