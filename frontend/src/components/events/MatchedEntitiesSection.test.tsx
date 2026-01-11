import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import MatchedEntitiesSection from './MatchedEntitiesSection';
import * as api from '../../services/api';

import type { EventEntityMatchesResponse } from '../../services/api';

// Mock the API
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../../services/api');
  return {
    ...actual,
    fetchEventEntityMatches: vi.fn(),
  };
});

describe('MatchedEntitiesSection', () => {
  const mockPersonMatch = {
    entity_id: 'entity-person-123',
    entity_type: 'person' as const,
    similarity: 0.92,
    time_gap_seconds: 300, // 5 minutes
    last_seen_camera: 'Front Door',
    last_seen_at: '2024-01-15T10:25:00Z',
    thumbnail_url: '/api/detections/123/image',
    attributes: { clothing: 'blue jacket' },
  };

  const mockVehicleMatch = {
    entity_id: 'entity-vehicle-456',
    entity_type: 'vehicle' as const,
    similarity: 0.85,
    time_gap_seconds: 7200, // 2 hours
    last_seen_camera: 'Driveway',
    last_seen_at: '2024-01-15T08:30:00Z',
    thumbnail_url: '/api/detections/456/image',
    attributes: { vehicle_type: 'sedan' },
  };

  const mockMatchResponse: EventEntityMatchesResponse = {
    event_id: 123,
    person_matches: [mockPersonMatch],
    vehicle_matches: [mockVehicleMatch],
    total_matches: 2,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('loading state', () => {
    it('shows loading indicator while fetching matches', async () => {
      // Create a promise that won't resolve immediately
      let resolvePromise: (value: EventEntityMatchesResponse) => void;
      const promise = new Promise<EventEntityMatchesResponse>((resolve) => {
        resolvePromise = resolve;
      });
      vi.mocked(api.fetchEventEntityMatches).mockReturnValue(promise);

      render(<MatchedEntitiesSection eventId={123} />);

      expect(screen.getByTestId('matched-entities-loading')).toBeInTheDocument();
      expect(screen.getByText('Loading matches...')).toBeInTheDocument();

      // Resolve the promise to clean up
      await act(() => {
        resolvePromise!(mockMatchResponse);
        return Promise.resolve();
      });
    });
  });

  describe('empty state', () => {
    it('shows empty state when no matches found', async () => {
      const emptyResponse: EventEntityMatchesResponse = {
        event_id: 123,
        person_matches: [],
        vehicle_matches: [],
        total_matches: 0,
      };
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(emptyResponse);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('matched-entities-empty')).toBeInTheDocument();
      });
      expect(screen.getByText('No entity matches found for this event')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error state when API call fails', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      vi.mocked(api.fetchEventEntityMatches).mockRejectedValue(new Error('API Error'));

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('matched-entities-error')).toBeInTheDocument();
      });
      expect(screen.getByText('Failed to load entity matches')).toBeInTheDocument();

      consoleSpy.mockRestore();
    });
  });

  describe('rendering matches', () => {
    it('renders matched entities section with correct count', async () => {
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(mockMatchResponse);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('matched-entities-section')).toBeInTheDocument();
      });
      expect(screen.getByText('Matched Entities (2)')).toBeInTheDocument();
    });

    it('renders person match with correct details', async () => {
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(mockMatchResponse);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('entity-match-entity-person-123')).toBeInTheDocument();
      });

      // Check entity type label
      expect(screen.getByText('person')).toBeInTheDocument();

      // Check similarity badge (92%)
      expect(screen.getByText('92%')).toBeInTheDocument();

      // Check last seen camera
      expect(screen.getByText(/Last seen: Front Door/)).toBeInTheDocument();
    });

    it('renders vehicle match with correct details', async () => {
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(mockMatchResponse);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('entity-match-entity-vehicle-456')).toBeInTheDocument();
      });

      // Check entity type label
      expect(screen.getByText('vehicle')).toBeInTheDocument();

      // Check similarity badge (85%)
      expect(screen.getByText('85%')).toBeInTheDocument();

      // Check last seen camera
      expect(screen.getByText(/Last seen: Driveway/)).toBeInTheDocument();
    });

    it('displays entity thumbnails when available', async () => {
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(mockMatchResponse);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('matched-entities-section')).toBeInTheDocument();
      });

      const thumbnails = screen.getAllByAltText(/entity/i);
      expect(thumbnails).toHaveLength(2);
    });

    it('sorts matches by similarity (highest first)', async () => {
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(mockMatchResponse);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('matched-entities-section')).toBeInTheDocument();
      });

      const buttons = screen.getAllByRole('button');
      // First button should be person (92%), second should be vehicle (85%)
      expect(buttons[0]).toHaveAttribute('data-testid', 'entity-match-entity-person-123');
      expect(buttons[1]).toHaveAttribute('data-testid', 'entity-match-entity-vehicle-456');
    });
  });

  describe('confidence color coding', () => {
    it('shows green badge for high confidence (>=90%)', async () => {
      const highConfidenceResponse: EventEntityMatchesResponse = {
        event_id: 123,
        person_matches: [{ ...mockPersonMatch, similarity: 0.95 }],
        vehicle_matches: [],
        total_matches: 1,
      };
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(highConfidenceResponse);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        const badge = screen.getByText('95%');
        expect(badge).toHaveClass('text-green-400');
      });
    });

    it('shows yellow badge for medium confidence (>=75%, <90%)', async () => {
      const mediumConfidenceResponse: EventEntityMatchesResponse = {
        event_id: 123,
        person_matches: [{ ...mockPersonMatch, similarity: 0.82 }],
        vehicle_matches: [],
        total_matches: 1,
      };
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(mediumConfidenceResponse);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        const badge = screen.getByText('82%');
        expect(badge).toHaveClass('text-yellow-400');
      });
    });

    it('shows red badge for low confidence (<75%)', async () => {
      const lowConfidenceResponse: EventEntityMatchesResponse = {
        event_id: 123,
        person_matches: [{ ...mockPersonMatch, similarity: 0.65 }],
        vehicle_matches: [],
        total_matches: 1,
      };
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(lowConfidenceResponse);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        const badge = screen.getByText('65%');
        expect(badge).toHaveClass('text-red-400');
      });
    });
  });

  describe('time gap formatting', () => {
    it('formats time gap in seconds', async () => {
      const recentMatch: EventEntityMatchesResponse = {
        event_id: 123,
        person_matches: [{ ...mockPersonMatch, time_gap_seconds: 45 }],
        vehicle_matches: [],
        total_matches: 1,
      };
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(recentMatch);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/45s ago/)).toBeInTheDocument();
      });
    });

    it('formats time gap in minutes', async () => {
      const minutesMatch: EventEntityMatchesResponse = {
        event_id: 123,
        person_matches: [{ ...mockPersonMatch, time_gap_seconds: 300 }], // 5 minutes
        vehicle_matches: [],
        total_matches: 1,
      };
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(minutesMatch);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/5m ago/)).toBeInTheDocument();
      });
    });

    it('formats time gap in hours', async () => {
      const hoursMatch: EventEntityMatchesResponse = {
        event_id: 123,
        person_matches: [{ ...mockPersonMatch, time_gap_seconds: 7200 }], // 2 hours
        vehicle_matches: [],
        total_matches: 1,
      };
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(hoursMatch);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/2h ago/)).toBeInTheDocument();
      });
    });

    it('formats time gap in days', async () => {
      const daysMatch: EventEntityMatchesResponse = {
        event_id: 123,
        person_matches: [{ ...mockPersonMatch, time_gap_seconds: 172800 }], // 2 days
        vehicle_matches: [],
        total_matches: 1,
      };
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(daysMatch);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/2d ago/)).toBeInTheDocument();
      });
    });
  });

  describe('entity click interaction', () => {
    it('calls onEntityClick when entity button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onEntityClick = vi.fn();
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(mockMatchResponse);

      render(<MatchedEntitiesSection eventId={123} onEntityClick={onEntityClick} />);

      await waitFor(() => {
        expect(screen.getByTestId('entity-match-entity-person-123')).toBeInTheDocument();
      });

      const entityButton = screen.getByTestId('entity-match-entity-person-123');
      await user.click(entityButton);

      expect(onEntityClick).toHaveBeenCalledWith('entity-person-123');
    });

    it('does not crash when onEntityClick is not provided', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(mockMatchResponse);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('entity-match-entity-person-123')).toBeInTheDocument();
      });

      const entityButton = screen.getByTestId('entity-match-entity-person-123');
      // Should not throw
      await user.click(entityButton);
    });
  });

  describe('accessibility', () => {
    it('entity buttons have proper aria-labels', async () => {
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(mockMatchResponse);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('matched-entities-section')).toBeInTheDocument();
      });

      const personButton = screen.getByTestId('entity-match-entity-person-123');
      expect(personButton).toHaveAttribute('aria-label', 'View person entity details');

      const vehicleButton = screen.getByTestId('entity-match-entity-vehicle-456');
      expect(vehicleButton).toHaveAttribute('aria-label', 'View vehicle entity details');
    });

    it('confidence badges have title with full percentage', async () => {
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(mockMatchResponse);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        const badge = screen.getByText('92%');
        expect(badge).toHaveAttribute('title', 'Similarity: 92%');
      });
    });
  });

  describe('event ID changes', () => {
    it('refetches matches when eventId prop changes', async () => {
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(mockMatchResponse);

      const { rerender } = render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(api.fetchEventEntityMatches).toHaveBeenCalledWith(123);
      });

      const newResponse: EventEntityMatchesResponse = {
        event_id: 456,
        person_matches: [],
        vehicle_matches: [],
        total_matches: 0,
      };
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(newResponse);

      rerender(<MatchedEntitiesSection eventId={456} />);

      await waitFor(() => {
        expect(api.fetchEventEntityMatches).toHaveBeenCalledWith(456);
      });
    });
  });

  describe('entity without thumbnail', () => {
    it('shows icon when no thumbnail URL is available', async () => {
      const noThumbnailResponse: EventEntityMatchesResponse = {
        event_id: 123,
        person_matches: [{ ...mockPersonMatch, thumbnail_url: null }],
        vehicle_matches: [],
        total_matches: 1,
      };
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(noThumbnailResponse);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('matched-entities-section')).toBeInTheDocument();
      });

      // Should not have an img element (no thumbnail)
      const images = screen.queryAllByRole('img');
      expect(images).toHaveLength(0);
    });
  });

  describe('only person matches', () => {
    it('renders correctly with only person matches', async () => {
      const onlyPersons: EventEntityMatchesResponse = {
        event_id: 123,
        person_matches: [mockPersonMatch],
        vehicle_matches: [],
        total_matches: 1,
      };
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(onlyPersons);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText('Matched Entities (1)')).toBeInTheDocument();
      });
      expect(screen.getByTestId('entity-match-entity-person-123')).toBeInTheDocument();
    });
  });

  describe('only vehicle matches', () => {
    it('renders correctly with only vehicle matches', async () => {
      const onlyVehicles: EventEntityMatchesResponse = {
        event_id: 123,
        person_matches: [],
        vehicle_matches: [mockVehicleMatch],
        total_matches: 1,
      };
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(onlyVehicles);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText('Matched Entities (1)')).toBeInTheDocument();
      });
      expect(screen.getByTestId('entity-match-entity-vehicle-456')).toBeInTheDocument();
    });
  });

  describe('many matches', () => {
    it('renders multiple matches correctly', async () => {
      const manyMatches: EventEntityMatchesResponse = {
        event_id: 123,
        person_matches: [
          { ...mockPersonMatch, entity_id: 'person-1', similarity: 0.95 },
          { ...mockPersonMatch, entity_id: 'person-2', similarity: 0.88 },
          { ...mockPersonMatch, entity_id: 'person-3', similarity: 0.82 },
        ],
        vehicle_matches: [
          { ...mockVehicleMatch, entity_id: 'vehicle-1', similarity: 0.78 },
          { ...mockVehicleMatch, entity_id: 'vehicle-2', similarity: 0.72 },
        ],
        total_matches: 5,
      };
      vi.mocked(api.fetchEventEntityMatches).mockResolvedValue(manyMatches);

      render(<MatchedEntitiesSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText('Matched Entities (5)')).toBeInTheDocument();
      });

      // All matches should be rendered
      expect(screen.getByTestId('entity-match-person-1')).toBeInTheDocument();
      expect(screen.getByTestId('entity-match-person-2')).toBeInTheDocument();
      expect(screen.getByTestId('entity-match-person-3')).toBeInTheDocument();
      expect(screen.getByTestId('entity-match-vehicle-1')).toBeInTheDocument();
      expect(screen.getByTestId('entity-match-vehicle-2')).toBeInTheDocument();
    });
  });
});
