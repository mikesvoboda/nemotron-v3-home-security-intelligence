/**
 * Tests for AnomalyInvestigationModal component (NEM-4714)
 *
 * Tests anomaly investigation modal including:
 * - Modal rendering
 * - Loading state
 * - Error state
 * - Displays anomaly details (zone name, type, severity)
 * - Displays expected vs actual values
 * - Displays associated detections list
 * - Acknowledge button functionality
 * - Close button functionality
 * - View in Timeline link
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';

import AnomalyInvestigationModal from './AnomalyInvestigationModal';

import type { AnomalyContext } from '../../hooks/useAnomalyContext';

// Save original fetch for restoration
const originalFetch = globalThis.fetch;

// Mock fetch globally
const mockFetch = vi.fn();

beforeAll(() => {
  globalThis.fetch = mockFetch as typeof fetch;
});

afterAll(() => {
  globalThis.fetch = originalFetch;
});

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', () => ({
  AnimatePresence: ({ children }: { children: React.ReactNode }) => children,
  motion: {
    div: ({ children, ...props }: { children: React.ReactNode }) => {
      // Filter out framer-motion-specific props
      const {
        initial: _initial,
        animate: _animate,
        exit: _exit,
        variants: _variants,
        transition: _transition,
        ...htmlProps
      } = props as Record<string, unknown>;
      return <div {...htmlProps}>{children}</div>;
    },
  },
  useReducedMotion: () => false,
}));

// Mock useNavigate from react-router-dom
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('AnomalyInvestigationModal', () => {
  // Helper to create mock anomaly context response
  const createMockAnomalyContext = (
    overrides: Partial<AnomalyContext> = {}
  ): AnomalyContext => ({
    id: 'anomaly-123',
    zone_id: 1,
    zone_name: 'Front Yard',
    anomaly_type: 'high_activity',
    severity: 'warning',
    timestamp: '2024-01-15T14:30:00Z',
    expected_value: 5.0,
    actual_value: 15.0,
    explanation: 'Detected unusually high activity compared to baseline',
    detections: [
      {
        id: 'detection-1',
        camera_id: 'cam-123',
        timestamp: '2024-01-15T14:30:00Z',
        object_class: 'person',
        confidence: 0.95,
        risk_score: 65,
        thumbnail_url: '/thumbnails/detection-1.jpg',
      },
      {
        id: 'detection-2',
        camera_id: 'cam-123',
        timestamp: '2024-01-15T14:31:00Z',
        object_class: 'person',
        confidence: 0.88,
        risk_score: 60,
        thumbnail_url: '/thumbnails/detection-2.jpg',
      },
    ],
    acknowledged: false,
    acknowledged_at: null,
    ...overrides,
  });

  // Helper to create a test query client
  function createTestQueryClient() {
    return new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 0,
          staleTime: 0,
        },
        mutations: {
          retry: false,
        },
      },
    });
  }

  // Helper to wrap component with providers
  function renderWithProviders(ui: React.ReactElement) {
    const queryClient = createTestQueryClient();
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{ui}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    anomalyId: 'anomaly-123',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
    mockNavigate.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('renders modal when open', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('anomaly-investigation-modal')).toBeInTheDocument();
      });
    });

    it('does not render modal when closed', () => {
      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} isOpen={false} />);

      expect(screen.queryByTestId('anomaly-investigation-modal')).not.toBeInTheDocument();
    });

    it('displays modal title', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Anomaly Investigation')).toBeInTheDocument();
      });
    });
  });

  describe('Loading State', () => {
    it('shows loading state while fetching', () => {
      mockFetch.mockReturnValue(new Promise(() => {})); // Never resolving

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      expect(screen.getByTestId('investigation-loading')).toBeInTheDocument();
    });

    it('hides loading state after data loads', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.queryByTestId('investigation-loading')).not.toBeInTheDocument();
      });
    });
  });

  describe('Error State', () => {
    it('shows error state on fetch failure', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('investigation-error')).toBeInTheDocument();
      });
    });

    it('displays error message', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Server Error',
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load anomaly details')).toBeInTheDocument();
      });
    });

    it('shows Try Again button in error state', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Server Error',
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Try Again')).toBeInTheDocument();
      });
    });

    it('calls refetch when Try Again is clicked', async () => {
      const user = userEvent.setup();
      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          statusText: 'Server Error',
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockAnomalyContext()),
        });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Try Again')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Try Again'));

      await waitFor(() => {
        expect(screen.queryByTestId('investigation-error')).not.toBeInTheDocument();
      });
    });
  });

  describe('Anomaly Details', () => {
    it('displays zone name', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext({ zone_name: 'Back Yard' })),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-name')).toHaveTextContent('Back Yard');
      });
    });

    it('displays anomaly type', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve(createMockAnomalyContext({ anomaly_type: 'low_activity' })),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('low activity')).toBeInTheDocument();
      });
    });

    it('displays timestamp', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('timestamp')).toBeInTheDocument();
      });
    });
  });

  describe('Severity Badge', () => {
    it('displays warning severity badge', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext({ severity: 'warning' })),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('severity-badge')).toHaveTextContent('Warning');
      });
    });

    it('displays critical severity badge', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext({ severity: 'critical' })),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('severity-badge')).toHaveTextContent('Critical');
      });
    });

    it('displays info severity badge', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext({ severity: 'info' })),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('severity-badge')).toHaveTextContent('Info');
      });
    });
  });

  describe('Value Comparison', () => {
    it('displays value comparison section', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('value-comparison')).toBeInTheDocument();
      });
    });

    it('displays expected value', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve(createMockAnomalyContext({ expected_value: 5.0, actual_value: 15.0 })),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('expected-value')).toHaveTextContent('5.0');
      });
    });

    it('displays actual value', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve(createMockAnomalyContext({ expected_value: 5.0, actual_value: 15.0 })),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('actual-value')).toHaveTextContent('15.0');
      });
    });

    it('displays difference value', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve(createMockAnomalyContext({ expected_value: 5.0, actual_value: 15.0 })),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('difference-value')).toHaveTextContent('+10.0');
      });
    });

    it('handles null expected value', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve(createMockAnomalyContext({ expected_value: null, actual_value: 10.0 })),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.queryByTestId('value-comparison')).toBeInTheDocument();
      });
    });
  });

  describe('AI Analysis', () => {
    it('displays AI explanation', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve(
            createMockAnomalyContext({ explanation: 'Unusual activity detected at this time' })
          ),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('explanation')).toHaveTextContent(
          'Unusual activity detected at this time'
        );
      });
    });

    it('does not display explanation section when explanation is null', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext({ explanation: null })),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.queryByText('AI Analysis')).not.toBeInTheDocument();
      });
    });
  });

  describe('Associated Detections', () => {
    it('displays detections list', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('detections-list')).toBeInTheDocument();
      });
    });

    it('displays detection count', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText(/Associated Detections \(2\)/)).toBeInTheDocument();
      });
    });

    it('displays detection cards', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        const cards = screen.getAllByTestId('detection-card');
        expect(cards).toHaveLength(2);
      });
    });

    it('displays no detections message when empty', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext({ detections: [] })),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(
          screen.getByText('No associated detections found for this anomaly.')
        ).toBeInTheDocument();
      });
    });

    it('displays detection thumbnails', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        const images = screen.getAllByRole('img');
        expect(images.length).toBeGreaterThan(0);
      });
    });

    it('displays view in timeline button for each detection', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        const buttons = screen.getAllByTestId('view-in-timeline-button');
        expect(buttons).toHaveLength(2);
      });
    });

    it('navigates to timeline when view button is clicked', async () => {
      const user = userEvent.setup();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getAllByTestId('view-in-timeline-button')).toHaveLength(2);
      });

      const buttons = screen.getAllByTestId('view-in-timeline-button');
      await user.click(buttons[0]);

      expect(mockNavigate).toHaveBeenCalledWith('/events?detection=detection-1');
    });

    it('closes modal when navigating to timeline', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getAllByTestId('view-in-timeline-button')).toHaveLength(2);
      });

      const buttons = screen.getAllByTestId('view-in-timeline-button');
      await user.click(buttons[0]);

      expect(onClose).toHaveBeenCalled();
    });
  });

  describe('Acknowledge Functionality', () => {
    it('displays acknowledge button when not acknowledged', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext({ acknowledged: false })),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('acknowledge-button')).toBeInTheDocument();
      });
    });

    it('does not display acknowledge button when already acknowledged', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext({ acknowledged: true })),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.queryByTestId('acknowledge-button')).not.toBeInTheDocument();
      });
    });

    it('displays acknowledged status when already acknowledged', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve(
            createMockAnomalyContext({
              acknowledged: true,
              acknowledged_at: '2024-01-15T15:00:00Z',
            })
          ),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('acknowledged-status')).toHaveTextContent('Acknowledged');
      });
    });

    it('calls acknowledge endpoint when button is clicked', async () => {
      const user = userEvent.setup();
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockAnomalyContext({ acknowledged: false })),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () =>
            Promise.resolve({
              acknowledged: true,
              acknowledged_at: '2024-01-15T15:00:00Z',
            }),
        });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('acknowledge-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('acknowledge-button'));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/zones/anomalies/anomaly-123/acknowledge'),
          expect.objectContaining({
            method: 'POST',
          })
        );
      });
    });

    it('shows "Acknowledging..." while mutation is pending', async () => {
      const user = userEvent.setup();
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockAnomalyContext({ acknowledged: false })),
        })
        .mockReturnValueOnce(new Promise(() => {})); // Never resolving

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('acknowledge-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('acknowledge-button'));

      await waitFor(() => {
        expect(screen.getByTestId('acknowledge-button')).toHaveTextContent('Acknowledging...');
      });
    });

    it('disables button while acknowledging', async () => {
      const user = userEvent.setup();
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockAnomalyContext({ acknowledged: false })),
        })
        .mockReturnValueOnce(new Promise(() => {})); // Never resolving

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('acknowledge-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('acknowledge-button'));

      await waitFor(() => {
        expect(screen.getByTestId('acknowledge-button')).toBeDisabled();
      });
    });
  });

  describe('Close Functionality', () => {
    it('displays close button in header', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('close-button')).toBeInTheDocument();
      });
    });

    it('calls onClose when close button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByTestId('close-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('close-button'));

      expect(onClose).toHaveBeenCalled();
    });

    it('displays close action button in footer', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('close-action-button')).toBeInTheDocument();
      });
    });

    it('calls onClose when footer close button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByTestId('close-action-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('close-action-button'));

      expect(onClose).toHaveBeenCalled();
    });
  });

  describe('Modal Not Open', () => {
    it('does not fetch when modal is closed', () => {
      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} isOpen={false} />);

      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('does not fetch when anomaly ID is null', () => {
      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} anomalyId={null} />);

      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('has proper aria-labelledby for modal title', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        const title = screen.getByText('Anomaly Investigation');
        expect(title).toHaveAttribute('id', 'investigation-modal-title');
      });
    });

    it('has proper aria-label for close button', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('close-button')).toHaveAttribute('aria-label', 'Close modal');
      });
    });

    it('has proper aria-label for view in timeline button', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderWithProviders(<AnomalyInvestigationModal {...defaultProps} />);

      await waitFor(() => {
        const buttons = screen.getAllByTestId('view-in-timeline-button');
        expect(buttons[0]).toHaveAttribute('aria-label', 'View detection in timeline');
      });
    });
  });
});
