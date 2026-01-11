/**
 * Tests for ReidMatchesPanel component
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import ReidMatchesPanel from './ReidMatchesPanel';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    fetchEntityMatches: vi.fn(),
  };
});

const mockFetchEntityMatches = vi.mocked(api.fetchEntityMatches);

describe('ReidMatchesPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading state initially', () => {
    mockFetchEntityMatches.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<ReidMatchesPanel detectionId={123} />);

    expect(screen.getByTestId('reid-matches-loading')).toBeInTheDocument();
    expect(screen.getByText(/looking for re-id matches/i)).toBeInTheDocument();
  });

  it('shows empty state when no matches found', async () => {
    mockFetchEntityMatches.mockResolvedValueOnce({
      query_detection_id: '123',
      entity_type: 'person',
      matches: [],
      total_matches: 0,
      threshold: 0.85,
    });

    render(<ReidMatchesPanel detectionId={123} />);

    await waitFor(() => {
      expect(screen.getByTestId('reid-matches-empty')).toBeInTheDocument();
    });

    expect(screen.getByText(/no re-id matches found/i)).toBeInTheDocument();
  });

  it('shows empty state when 404 error (no embedding)', async () => {
    mockFetchEntityMatches.mockRejectedValueOnce(new Error('404 Not Found'));

    render(<ReidMatchesPanel detectionId={123} />);

    await waitFor(() => {
      expect(screen.getByTestId('reid-matches-empty')).toBeInTheDocument();
    });
  });

  it('shows error state when API fails', async () => {
    mockFetchEntityMatches.mockRejectedValueOnce(new Error('Network error'));

    render(<ReidMatchesPanel detectionId={123} />);

    await waitFor(() => {
      expect(screen.getByTestId('reid-matches-error')).toBeInTheDocument();
    });

    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });

  it('renders matches when data is available', async () => {
    const mockMatches = {
      query_detection_id: '123',
      entity_type: 'person',
      matches: [
        {
          entity_id: 'det_001',
          entity_type: 'person' as const,
          camera_id: 'backyard',
          camera_name: 'Backyard',
          timestamp: '2025-12-23T10:00:00Z',
          thumbnail_url: '/api/detections/1/image',
          similarity_score: 0.92,
          time_gap_seconds: 3600,
          attributes: {},
        },
        {
          entity_id: 'det_002',
          entity_type: 'person' as const,
          camera_id: 'front_door',
          camera_name: 'Front Door',
          timestamp: '2025-12-23T09:00:00Z',
          thumbnail_url: '/api/detections/2/image',
          similarity_score: 0.88,
          time_gap_seconds: 7200,
          attributes: {},
        },
      ],
      total_matches: 2,
      threshold: 0.85,
    };

    mockFetchEntityMatches.mockResolvedValueOnce(mockMatches);

    render(<ReidMatchesPanel detectionId={123} />);

    await waitFor(() => {
      expect(screen.getByTestId('reid-matches-panel')).toBeInTheDocument();
    });

    // Check header
    expect(screen.getByText('Re-ID Matches')).toBeInTheDocument();
    expect(screen.getByText('2 matches')).toBeInTheDocument();

    // Check match items
    expect(screen.getByText('Backyard')).toBeInTheDocument();
    expect(screen.getByText('Front Door')).toBeInTheDocument();

    // Check similarity badges
    expect(screen.getByText('92%')).toBeInTheDocument();
    expect(screen.getByText('88%')).toBeInTheDocument();

    // Check threshold footer
    expect(screen.getByText(/85% similarity/)).toBeInTheDocument();
  });

  it('calls onMatchClick when a match is clicked', async () => {
    const mockMatches = {
      query_detection_id: '123',
      entity_type: 'person',
      matches: [
        {
          entity_id: 'det_001',
          entity_type: 'person' as const,
          camera_id: 'backyard',
          camera_name: 'Backyard',
          timestamp: '2025-12-23T10:00:00Z',
          thumbnail_url: '/api/detections/1/image',
          similarity_score: 0.92,
          time_gap_seconds: 3600,
          attributes: {},
        },
      ],
      total_matches: 1,
      threshold: 0.85,
    };

    mockFetchEntityMatches.mockResolvedValueOnce(mockMatches);

    const onMatchClick = vi.fn();
    render(<ReidMatchesPanel detectionId={123} onMatchClick={onMatchClick} />);

    await waitFor(() => {
      expect(screen.getByTestId('reid-matches-panel')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Backyard'));

    expect(onMatchClick).toHaveBeenCalledWith(mockMatches.matches[0]);
  });

  it('allows refreshing matches', async () => {
    const mockMatches = {
      query_detection_id: '123',
      entity_type: 'person',
      matches: [],
      total_matches: 0,
      threshold: 0.85,
    };

    mockFetchEntityMatches.mockResolvedValue(mockMatches);

    render(<ReidMatchesPanel detectionId={123} />);

    await waitFor(() => {
      expect(screen.getByTestId('reid-matches-empty')).toBeInTheDocument();
    });

    // First call on mount
    expect(mockFetchEntityMatches).toHaveBeenCalledTimes(1);

    // Verify initial call was made
    expect(mockFetchEntityMatches).toHaveBeenCalledWith('123', { entity_type: 'person' });
  });

  it('uses vehicle entity type when specified', async () => {
    mockFetchEntityMatches.mockResolvedValueOnce({
      query_detection_id: '123',
      entity_type: 'vehicle',
      matches: [],
      total_matches: 0,
      threshold: 0.85,
    });

    render(<ReidMatchesPanel detectionId={123} entityType="vehicle" />);

    await waitFor(() => {
      expect(mockFetchEntityMatches).toHaveBeenCalledWith('123', { entity_type: 'vehicle' });
    });

    // Should show the empty state panel for vehicle
    expect(screen.getByTestId('reid-matches-empty')).toBeInTheDocument();
  });

  it('refetches when detectionId changes', async () => {
    const mockMatches = {
      query_detection_id: '123',
      entity_type: 'person',
      matches: [],
      total_matches: 0,
      threshold: 0.85,
    };

    mockFetchEntityMatches.mockResolvedValue(mockMatches);

    const { rerender } = render(<ReidMatchesPanel detectionId={123} />);

    await waitFor(() => {
      expect(mockFetchEntityMatches).toHaveBeenCalledWith('123', { entity_type: 'person' });
    });

    rerender(<ReidMatchesPanel detectionId={456} />);

    await waitFor(() => {
      expect(mockFetchEntityMatches).toHaveBeenCalledWith('456', { entity_type: 'person' });
    });
  });

  it('displays singular match text for 1 match', async () => {
    const mockMatches = {
      query_detection_id: '123',
      entity_type: 'person',
      matches: [
        {
          entity_id: 'det_001',
          entity_type: 'person' as const,
          camera_id: 'backyard',
          camera_name: 'Backyard',
          timestamp: '2025-12-23T10:00:00Z',
          thumbnail_url: null,
          similarity_score: 0.92,
          time_gap_seconds: 3600,
          attributes: {},
        },
      ],
      total_matches: 1,
      threshold: 0.85,
    };

    mockFetchEntityMatches.mockResolvedValueOnce(mockMatches);

    render(<ReidMatchesPanel detectionId={123} />);

    await waitFor(() => {
      expect(screen.getByText('1 match')).toBeInTheDocument();
    });
  });
});
