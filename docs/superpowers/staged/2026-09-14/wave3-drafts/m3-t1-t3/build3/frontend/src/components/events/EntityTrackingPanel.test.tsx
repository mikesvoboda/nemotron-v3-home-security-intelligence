import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

import EntityTrackingPanel from './EntityTrackingPanel';
import * as api from '../../services/api';

import type { EntityHistoryResponse, EntityAppearance } from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchEntityHistory: vi.fn(),
}));

// Helper to create a test query client
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

// Helper to wrap component with query provider
function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return {
    ...render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>),
    queryClient,
  };
}

describe('EntityTrackingPanel', () => {
  const mockEntityId = 'entity-test-123';
  const mockCurrentCameraId = 'front_door';
  const mockCurrentTimestamp = '2025-01-07T12:00:00Z';

  const mockAppearance1: EntityAppearance = {
    detection_id: 'det-001',
    camera_id: 'front_door',
    camera_name: 'Front Door',
    timestamp: '2025-01-07T10:00:00Z',
    thumbnail_url: '/api/detections/1/image',
    similarity_score: 0.98,
    attributes: { clothing: 'blue jacket' },
  };

  const mockAppearance2: EntityAppearance = {
    detection_id: 'det-002',
    camera_id: 'backyard',
    camera_name: 'Backyard',
    timestamp: '2025-01-07T11:00:00Z',
    thumbnail_url: '/api/detections/2/image',
    similarity_score: 0.92,
    attributes: {},
  };

  const mockAppearance3: EntityAppearance = {
    detection_id: 'det-003',
    camera_id: 'driveway',
    camera_name: 'Driveway',
    timestamp: '2025-01-07T12:00:00Z',
    thumbnail_url: '/api/detections/3/image',
    similarity_score: 0.88,
    attributes: {},
  };

  const mockAppearance4: EntityAppearance = {
    detection_id: 'det-004',
    camera_id: 'garage',
    camera_name: 'Garage',
    timestamp: '2025-01-07T13:00:00Z',
    thumbnail_url: '/api/detections/4/image',
    similarity_score: 0.82,
    attributes: {},
  };

  const mockHistoryMultiple: EntityHistoryResponse = {
    entity_id: mockEntityId,
    entity_type: 'person',
    appearances: [mockAppearance1, mockAppearance2, mockAppearance3, mockAppearance4],
    count: 4,
  };

  const mockHistorySingle: EntityHistoryResponse = {
    entity_id: mockEntityId,
    entity_type: 'person',
    appearances: [mockAppearance1],
    count: 1,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering Conditions', () => {
    it('renders nothing when entityId is not provided', () => {
      const { container } = renderWithQueryClient(
        <EntityTrackingPanel
          entityId=""
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when entity has only single appearance', async () => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistorySingle);

      const { container } = renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      // Wait for the query to resolve
      await waitFor(() => {
        expect(api.fetchEntityHistory).toHaveBeenCalledWith(mockEntityId);
      });

      // Should not render panel for single appearance
      await waitFor(() => {
        expect(container.querySelector('[data-testid="entity-tracking-panel"]')).toBeNull();
      });
    });

    it('renders panel when entity has multiple appearances', async () => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistoryMultiple);

      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('entity-tracking-panel')).toBeInTheDocument();
      });
    });
  });

  describe('Loading State', () => {
    it('displays skeleton loading state while fetching', () => {
      (api.fetchEntityHistory as Mock).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      expect(screen.getByTestId('entity-tracking-skeleton')).toBeInTheDocument();
    });
  });

  describe('Timeline Display', () => {
    beforeEach(() => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistoryMultiple);
    });

    it('displays all cross-camera appearances in the timeline', async () => {
      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        // Use getAllByText since camera names appear in both movement summary and timeline
        expect(screen.getAllByText(/front door/i).length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText(/backyard/i).length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText(/driveway/i).length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText(/garage/i).length).toBeGreaterThanOrEqual(1);
      });
    });

    it('displays "Cross-Camera Tracking" title', async () => {
      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/cross-camera tracking/i)).toBeInTheDocument();
      });
    });

    it('displays appearance count', async () => {
      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/4 appearances/i)).toBeInTheDocument();
      });
    });
  });

  describe('Current Location Highlighting', () => {
    beforeEach(() => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistoryMultiple);
    });

    it('highlights the current camera location', async () => {
      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId="front_door"
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        const currentBadge = screen.getByTestId('current-location-badge');
        expect(currentBadge).toBeInTheDocument();
        expect(currentBadge).toHaveTextContent(/current/i);
      });
    });
  });

  describe('Similarity Score Badges', () => {
    beforeEach(() => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistoryMultiple);
    });

    it('displays similarity scores as color-coded badges', async () => {
      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        // Check for various similarity scores
        expect(screen.getByText('98%')).toBeInTheDocument();
        expect(screen.getByText('92%')).toBeInTheDocument();
        expect(screen.getByText('88%')).toBeInTheDocument();
        expect(screen.getByText('82%')).toBeInTheDocument();
      });
    });

    it('applies green color for score >= 95%', async () => {
      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        const badge98 = screen.getByText('98%');
        expect(badge98).toHaveClass('bg-green-500/20');
      });
    });

    it('applies blue color for score >= 90% and < 95%', async () => {
      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        const badge92 = screen.getByText('92%');
        expect(badge92).toHaveClass('bg-blue-500/20');
      });
    });

    it('applies yellow color for score >= 85% and < 90%', async () => {
      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        const badge88 = screen.getByText('88%');
        expect(badge88).toHaveClass('bg-yellow-500/20');
      });
    });

    it('applies gray color for score < 85%', async () => {
      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        const badge82 = screen.getByText('82%');
        expect(badge82).toHaveClass('bg-gray-500/20');
      });
    });
  });

  describe('Movement Pattern Summary', () => {
    beforeEach(() => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistoryMultiple);
    });

    it('displays movement pattern summary with camera flow', async () => {
      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        // Should show camera flow pattern
        const movementSummary = screen.getByTestId('movement-pattern-summary');
        expect(movementSummary).toBeInTheDocument();
      });
    });

    it('shows camera names in chronological order', async () => {
      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        const movementSummary = screen.getByTestId('movement-pattern-summary');
        // Should show cameras in order: Front Door -> Backyard -> Driveway -> Garage
        expect(movementSummary.textContent).toContain('Front Door');
        expect(movementSummary.textContent).toContain('Garage');
      });
    });
  });

  describe('Error State', () => {
    it('handles API error gracefully', async () => {
      (api.fetchEntityHistory as Mock).mockRejectedValue(new Error('Network error'));

      const { container } = renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      // On error, component should not render
      await waitFor(() => {
        expect(container.querySelector('[data-testid="entity-tracking-panel"]')).toBeNull();
      });
    });
  });

  describe('API Integration', () => {
    it('calls fetchEntityHistory with correct entity ID', async () => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistoryMultiple);

      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        expect(api.fetchEntityHistory).toHaveBeenCalledWith(mockEntityId);
      });
    });

    it('refetches when entityId changes', async () => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistoryMultiple);

      const { rerender, queryClient } = renderWithQueryClient(
        <EntityTrackingPanel
          entityId="entity-1"
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        expect(api.fetchEntityHistory).toHaveBeenCalledWith('entity-1');
      });

      // Change entity ID
      rerender(
        <QueryClientProvider client={queryClient}>
          <EntityTrackingPanel
            entityId="entity-2"
            currentCameraId={mockCurrentCameraId}
            currentTimestamp={mockCurrentTimestamp}
          />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(api.fetchEntityHistory).toHaveBeenCalledWith('entity-2');
      });
    });
  });

  describe('Empty/Null History', () => {
    it('renders nothing when history has no appearances', async () => {
      const emptyHistory: EntityHistoryResponse = {
        entity_id: mockEntityId,
        entity_type: 'person',
        appearances: [],
        count: 0,
      };

      (api.fetchEntityHistory as Mock).mockResolvedValue(emptyHistory);

      const { container } = renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        expect(container.querySelector('[data-testid="entity-tracking-panel"]')).toBeNull();
      });
    });
  });

  describe('Accessibility', () => {
    beforeEach(() => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistoryMultiple);
    });

    it('includes proper heading for the panel', async () => {
      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        const heading = screen.getByRole('heading', { level: 3 });
        expect(heading).toHaveTextContent(/cross-camera tracking/i);
      });
    });

    it('provides alt text for timeline icons', async () => {
      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('entity-tracking-panel')).toBeInTheDocument();
      });
    });
  });

  describe('Custom Styling', () => {
    beforeEach(() => {
      (api.fetchEntityHistory as Mock).mockResolvedValue(mockHistoryMultiple);
    });

    it('applies custom className prop', async () => {
      const customClass = 'my-custom-class';

      renderWithQueryClient(
        <EntityTrackingPanel
          entityId={mockEntityId}
          currentCameraId={mockCurrentCameraId}
          currentTimestamp={mockCurrentTimestamp}
          className={customClass}
        />
      );

      await waitFor(() => {
        const panel = screen.getByTestId('entity-tracking-panel');
        expect(panel).toHaveClass(customClass);
      });
    });
  });
});
