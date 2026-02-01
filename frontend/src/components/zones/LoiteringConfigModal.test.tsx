/**
 * Tests for LoiteringConfigModal component (NEM-4714)
 *
 * Tests loitering configuration modal including:
 * - Modal rendering
 * - Loading state
 * - Error state
 * - Threshold slider interaction
 * - Alert toggle interaction
 * - Save functionality
 * - Cancel functionality
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';

import LoiteringConfigModal from './LoiteringConfigModal';

import type { LoiteringConfig } from './LoiteringConfigModal';

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

describe('LoiteringConfigModal', () => {
  // Helper to create mock config response
  const createMockConfig = (overrides: Partial<LoiteringConfig> = {}): LoiteringConfig => ({
    zone_id: 1,
    zone_name: 'Front Yard',
    threshold_seconds: 300, // 5 minutes
    alert_enabled: true,
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
    return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
  }

  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    zoneId: 1,
    zoneName: 'Front Yard',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('should render the modal when open', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('loitering-config-modal')).toBeInTheDocument();
      });
    });

    it('should display modal title', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Loitering Configuration')).toBeInTheDocument();
      });
    });

    it('should display zone name', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('zone-name')).toHaveTextContent('Front Yard');
      });
    });
  });

  describe('Loading State', () => {
    it('should show loading spinner while fetching config', () => {
      mockFetch.mockReturnValue(new Promise(() => {})); // Never resolving

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      expect(screen.getByTestId('loading-state')).toBeInTheDocument();
    });

    it('should hide loading state after data loads', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.queryByTestId('loading-state')).not.toBeInTheDocument();
      });
    });
  });

  describe('Error State', () => {
    it('should show error state on fetch failure', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('error-state')).toBeInTheDocument();
      });
    });

    it('should show error message text', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Server Error',
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load configuration')).toBeInTheDocument();
      });
    });
  });

  describe('Threshold Slider', () => {
    it('should display threshold slider', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig({ threshold_seconds: 300 })),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('threshold-slider')).toBeInTheDocument();
      });
    });

    it('should display current threshold value', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig({ threshold_seconds: 300 })),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('threshold-value')).toHaveTextContent('5 min');
      });
    });

    it('should update threshold value on slider change', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig({ threshold_seconds: 300 })),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('threshold-slider')).toBeInTheDocument();
      });

      const slider = screen.getByTestId('threshold-slider');
      fireEvent.change(slider, { target: { value: '10' } });

      expect(screen.getByTestId('threshold-value')).toHaveTextContent('10 min');
    });

    it('should have slider with min 1 and max 60', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        const slider = screen.getByTestId('threshold-slider');
        expect(slider).toHaveAttribute('min', '1');
        expect(slider).toHaveAttribute('max', '60');
      });
    });
  });

  describe('Alert Toggle', () => {
    it('should display alert toggle', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-toggle')).toBeInTheDocument();
      });
    });

    it('should show toggle as checked when alerts enabled', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig({ alert_enabled: true })),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-toggle')).toHaveAttribute('aria-checked', 'true');
      });
    });

    it('should show toggle as unchecked when alerts disabled', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig({ alert_enabled: false })),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-toggle')).toHaveAttribute('aria-checked', 'false');
      });
    });

    it('should toggle alert state on click', async () => {
      const user = userEvent.setup();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig({ alert_enabled: true })),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-toggle')).toHaveAttribute('aria-checked', 'true');
      });

      await user.click(screen.getByTestId('alert-toggle'));

      expect(screen.getByTestId('alert-toggle')).toHaveAttribute('aria-checked', 'false');
    });
  });

  describe('Save Functionality', () => {
    it('should render save button', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('save-button')).toBeInTheDocument();
        expect(screen.getByTestId('save-button')).toHaveTextContent('Save');
      });
    });

    it('should call PATCH endpoint on save', async () => {
      const user = userEvent.setup();
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockConfig()),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockConfig()),
        });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('save-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          '/api/analytics-zones/polygon-zones/1/loitering-config',
          expect.objectContaining({
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
          })
        );
      });
    });

    it('should send correct data on save', async () => {
      const user = userEvent.setup();
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockConfig({ threshold_seconds: 300, alert_enabled: true })),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockConfig()),
        });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('save-button')).toBeInTheDocument();
      });

      // Change threshold to 10 minutes
      fireEvent.change(screen.getByTestId('threshold-slider'), { target: { value: '10' } });

      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        const patchCall = mockFetch.mock.calls.find(
          (call) => call[1]?.method === 'PATCH'
        );
        expect(patchCall).toBeDefined();
        const body = JSON.parse(patchCall![1].body as string);
        expect(body).toEqual({
          threshold_seconds: 600, // 10 minutes
          alert_enabled: true,
        });
      });
    });

    it('should call onClose after successful save', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockConfig()),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockConfig()),
        });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByTestId('save-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(onClose).toHaveBeenCalled();
      });
    });

    it('should show "Saving..." while mutation is pending', async () => {
      const user = userEvent.setup();
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockConfig()),
        })
        .mockReturnValueOnce(new Promise(() => {})); // Never resolving

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('save-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(screen.getByTestId('save-button')).toHaveTextContent('Saving...');
      });
    });

    it('should show error message on save failure', async () => {
      const user = userEvent.setup();
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockConfig()),
        })
        .mockResolvedValueOnce({
          ok: false,
          statusText: 'Server Error',
        });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('save-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(screen.getByTestId('mutation-error')).toBeInTheDocument();
      });
    });
  });

  describe('Cancel Functionality', () => {
    it('should render cancel button', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('cancel-button')).toBeInTheDocument();
        expect(screen.getByTestId('cancel-button')).toHaveTextContent('Cancel');
      });
    });

    it('should call onClose when cancel is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByTestId('cancel-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('cancel-button'));

      expect(onClose).toHaveBeenCalled();
    });
  });

  describe('Close Button', () => {
    it('should render close button in header', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('close-button')).toBeInTheDocument();
      });
    });

    it('should call onClose when close button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByTestId('close-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('close-button'));

      expect(onClose).toHaveBeenCalled();
    });
  });

  describe('Modal Not Open', () => {
    it('should not fetch when modal is closed', () => {
      renderWithProviders(<LoiteringConfigModal {...defaultProps} isOpen={false} />);

      // Should not have called fetch since modal is not open
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('should have proper aria-labelledby for modal title', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        const title = screen.getByText('Loitering Configuration');
        expect(title).toHaveAttribute('id', 'loitering-config-title');
      });
    });

    it('should have proper aria-label for close button', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('close-button')).toHaveAttribute('aria-label', 'Close modal');
      });
    });

    it('should have role="switch" on alert toggle', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-toggle')).toHaveAttribute('role', 'switch');
      });
    });

    it('should have label for threshold slider', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockConfig()),
      });

      renderWithProviders(<LoiteringConfigModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByLabelText('Loitering Threshold')).toBeInTheDocument();
      });
    });
  });
});
