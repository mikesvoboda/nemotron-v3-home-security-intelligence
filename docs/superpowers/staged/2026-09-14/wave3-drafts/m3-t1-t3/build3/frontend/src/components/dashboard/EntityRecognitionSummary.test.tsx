/**
 * Unit tests for EntityRecognitionSummary component.
 *
 * Tests cover:
 * - Loading state rendering
 * - Data display for persons and vehicles
 * - Known vs unknown breakdown display
 * - Empty state when no data
 * - Expandable breakdown details
 *
 * Implements NEM-5396: Entity Recognition Summary - Frontend Tests
 *
 * TDD: Tests written BEFORE implementation
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import EntityRecognitionSummary from './EntityRecognitionSummary';
import { fetchEntityRecognitionStats } from '../../services/api';

// Mock the API
vi.mock('../../services/api', () => ({
  fetchEntityRecognitionStats: vi.fn(),
}));

// Helper to create a QueryClient for tests
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
}

// Wrapper component for tests
function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// =============================================================================
// Test Data
// =============================================================================

const mockStats = {
  persons: {
    known: 3,
    unknown: 2,
    total: 5,
    breakdown: '3 known, 2 unknown',
  },
  vehicles: {
    known: 1,
    unknown: 4,
    total: 5,
    breakdown: '1 known, 4 unknown',
  },
  window_start: '2026-02-03T10:00:00+00:00',
  window_end: '2026-02-03T11:00:00+00:00',
};

const emptyStats = {
  persons: {
    known: 0,
    unknown: 0,
    total: 0,
    breakdown: 'No persons detected',
  },
  vehicles: {
    known: 0,
    unknown: 0,
    total: 0,
    breakdown: 'No vehicles detected',
  },
  window_start: '2026-02-03T10:00:00+00:00',
  window_end: '2026-02-03T11:00:00+00:00',
};

// =============================================================================
// Tests
// =============================================================================

describe('EntityRecognitionSummary', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading State', () => {
    it('shows skeleton loader while loading', () => {
      // Mock a delayed response
      vi.mocked(fetchEntityRecognitionStats).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      renderWithProviders(<EntityRecognitionSummary />);

      // Should show loading state
      expect(screen.getByTestId('entity-recognition-loading')).toBeInTheDocument();
    });
  });

  describe('Data Display', () => {
    it('displays person and vehicle counts', async () => {
      vi.mocked(fetchEntityRecognitionStats).mockResolvedValue(mockStats);

      renderWithProviders(<EntityRecognitionSummary />);

      await waitFor(() => {
        expect(screen.getByTestId('entity-recognition-summary')).toBeInTheDocument();
      });

      // Check persons section
      expect(screen.getByTestId('persons-total')).toHaveTextContent('5');
      expect(screen.getByTestId('persons-breakdown')).toHaveTextContent('3 known, 2 unknown');

      // Check vehicles section
      expect(screen.getByTestId('vehicles-total')).toHaveTextContent('5');
      expect(screen.getByTestId('vehicles-breakdown')).toHaveTextContent('1 known, 4 unknown');
    });

    it('displays icons for persons and vehicles', async () => {
      vi.mocked(fetchEntityRecognitionStats).mockResolvedValue(mockStats);

      renderWithProviders(<EntityRecognitionSummary />);

      await waitFor(() => {
        expect(screen.getByTestId('entity-recognition-summary')).toBeInTheDocument();
      });

      // Check for icons (User icon for persons, Car icon for vehicles)
      expect(screen.getByTestId('persons-icon')).toBeInTheDocument();
      expect(screen.getByTestId('vehicles-icon')).toBeInTheDocument();
    });

    it('displays time window information', async () => {
      vi.mocked(fetchEntityRecognitionStats).mockResolvedValue(mockStats);

      renderWithProviders(<EntityRecognitionSummary />);

      await waitFor(() => {
        expect(screen.getByTestId('entity-recognition-summary')).toBeInTheDocument();
      });

      // Check time window (Last 60 minutes)
      expect(screen.getByTestId('time-window')).toHaveTextContent('Last 60 minutes');
    });
  });

  describe('Empty State', () => {
    it('shows empty state message when no entities detected', async () => {
      vi.mocked(fetchEntityRecognitionStats).mockResolvedValue(emptyStats);

      renderWithProviders(<EntityRecognitionSummary />);

      // Wait for the data to load and render - check by text content in document
      await waitFor(() => {
        expect(screen.getByText('No persons detected')).toBeInTheDocument();
      });

      expect(screen.getByText('No vehicles detected')).toBeInTheDocument();
    });

    it('displays zero counts for empty data', async () => {
      vi.mocked(fetchEntityRecognitionStats).mockResolvedValue(emptyStats);

      renderWithProviders(<EntityRecognitionSummary />);

      // Wait for the data to load and render
      await waitFor(() => {
        expect(screen.getByTestId('persons-total')).toBeInTheDocument();
      });

      // Both should show 0
      expect(screen.getByTestId('persons-total')).toHaveTextContent('0');
      expect(screen.getByTestId('vehicles-total')).toHaveTextContent('0');
    });
  });

  describe('Error Handling', () => {
    it('shows error state on fetch failure', async () => {
      vi.mocked(fetchEntityRecognitionStats).mockRejectedValue(new Error('Network error'));

      renderWithProviders(<EntityRecognitionSummary />);

      await waitFor(() => {
        expect(screen.getByTestId('entity-recognition-error')).toBeInTheDocument();
      });
    });

    it('shows retry button on error', async () => {
      vi.mocked(fetchEntityRecognitionStats).mockRejectedValue(new Error('Network error'));

      renderWithProviders(<EntityRecognitionSummary />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
      });
    });
  });

  describe('Expandable Details', () => {
    it('expands to show detailed breakdown on click', async () => {
      vi.mocked(fetchEntityRecognitionStats).mockResolvedValue(mockStats);

      renderWithProviders(<EntityRecognitionSummary />);

      await waitFor(() => {
        expect(screen.getByTestId('entity-recognition-summary')).toBeInTheDocument();
      });

      // Click to expand
      const expandButton = screen.getByTestId('expand-details-button');
      fireEvent.click(expandButton);

      // Check expanded details are shown
      await waitFor(() => {
        expect(screen.getByTestId('expanded-details')).toBeInTheDocument();
      });

      // Check detailed breakdown
      expect(screen.getByTestId('persons-known-count')).toHaveTextContent('3');
      expect(screen.getByTestId('persons-unknown-count')).toHaveTextContent('2');
      expect(screen.getByTestId('vehicles-known-count')).toHaveTextContent('1');
      expect(screen.getByTestId('vehicles-unknown-count')).toHaveTextContent('4');
    });

    it('collapses details on second click', async () => {
      vi.mocked(fetchEntityRecognitionStats).mockResolvedValue(mockStats);

      renderWithProviders(<EntityRecognitionSummary />);

      await waitFor(() => {
        expect(screen.getByTestId('entity-recognition-summary')).toBeInTheDocument();
      });

      // Click to expand
      const expandButton = screen.getByTestId('expand-details-button');
      fireEvent.click(expandButton);

      await waitFor(() => {
        expect(screen.getByTestId('expanded-details')).toBeInTheDocument();
      });

      // Click to collapse
      fireEvent.click(expandButton);

      await waitFor(() => {
        expect(screen.queryByTestId('expanded-details')).not.toBeInTheDocument();
      });
    });
  });

  describe('Visual Indicators', () => {
    it('shows checkmark icon for known entities', async () => {
      vi.mocked(fetchEntityRecognitionStats).mockResolvedValue(mockStats);

      renderWithProviders(<EntityRecognitionSummary />);

      await waitFor(() => {
        expect(screen.getByTestId('entity-recognition-summary')).toBeInTheDocument();
      });

      // Expand to see details
      fireEvent.click(screen.getByTestId('expand-details-button'));

      await waitFor(() => {
        expect(screen.getByTestId('expanded-details')).toBeInTheDocument();
      });

      // Check for visual indicators
      expect(screen.getByTestId('known-indicator')).toBeInTheDocument();
      expect(screen.getByTestId('unknown-indicator')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has accessible labels for screen readers', async () => {
      vi.mocked(fetchEntityRecognitionStats).mockResolvedValue(mockStats);

      renderWithProviders(<EntityRecognitionSummary />);

      await waitFor(() => {
        expect(screen.getByTestId('entity-recognition-summary')).toBeInTheDocument();
      });

      // Check for aria labels
      expect(screen.getByLabelText(/entity recognition summary/i)).toBeInTheDocument();
    });

    it('expand button has accessible name', async () => {
      vi.mocked(fetchEntityRecognitionStats).mockResolvedValue(mockStats);

      renderWithProviders(<EntityRecognitionSummary />);

      await waitFor(() => {
        expect(screen.getByTestId('entity-recognition-summary')).toBeInTheDocument();
      });

      expect(screen.getByTestId('expand-details-button')).toHaveAccessibleName();
    });
  });
});
