/**
 * Tests for Action Events API client
 *
 * Linear issue: NEM-5024 (Phase 7)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  fetchActionEvents,
  fetchSuspiciousActions,
  fetchActionEvent,
  fetchActionEventsForCamera,
  fetchActionEventsForEvent,
  SUSPICIOUS_ACTIONS,
  NORMAL_ACTIONS,
  ALL_ACTION_TYPES,
  type ActionEvent,
  type ActionEventListResponse,
  type SuspiciousActionsResponse,
} from './actionEventsApi';

// ============================================================================
// Helper Functions
// ============================================================================

function createMockResponse<T>(data: T, status = 200, statusText = 'OK'): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText,
    json: () => Promise.resolve(data),
    headers: new Headers({ 'Content-Type': 'application/json' }),
  } as Response;
}

function createMockErrorResponse(status: number, statusText: string): Response {
  return {
    ok: false,
    status,
    statusText,
    json: () => Promise.resolve(null),
    headers: new Headers({ 'Content-Type': 'application/json' }),
  } as Response;
}

// ============================================================================
// Tests
// ============================================================================

describe('actionEventsApi', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ============================================================================
  // Constants Tests
  // ============================================================================

  describe('action type constants', () => {
    it('defines suspicious actions', () => {
      expect(SUSPICIOUS_ACTIONS).toContain('climbing');
      expect(SUSPICIOUS_ACTIONS).toContain('fighting');
      expect(SUSPICIOUS_ACTIONS).toContain('loitering');
      expect(SUSPICIOUS_ACTIONS.length).toBeGreaterThan(0);
    });

    it('defines normal actions', () => {
      expect(NORMAL_ACTIONS).toContain('walking normally');
      expect(NORMAL_ACTIONS).toContain('running');
      expect(NORMAL_ACTIONS.length).toBeGreaterThan(0);
    });

    it('combines all action types', () => {
      expect(ALL_ACTION_TYPES.length).toBe(SUSPICIOUS_ACTIONS.length + NORMAL_ACTIONS.length);
      expect(ALL_ACTION_TYPES).toContain('climbing');
      expect(ALL_ACTION_TYPES).toContain('walking normally');
    });
  });

  // ============================================================================
  // fetchActionEvents Tests
  // ============================================================================

  describe('fetchActionEvents', () => {
    const mockResponse: ActionEventListResponse = {
      items: [
        {
          id: 1,
          camera_id: 'front_door',
          track_id: 42,
          action: 'walking normally',
          confidence: 0.89,
          is_suspicious: false,
          timestamp: '2026-01-26T12:00:00Z',
          frame_count: 8,
          all_scores: {
            'walking normally': 0.89,
            running: 0.05,
            climbing: 0.02,
            loitering: 0.04,
          },
          created_at: '2026-01-26T12:00:00Z',
        },
      ],
      pagination: {
        total: 1,
        limit: 50,
        offset: 0,
        has_more: false,
      },
    };

    it('fetches action events successfully', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse));

      const result = await fetchActionEvents();

      expect(fetchSpy).toHaveBeenCalledWith('/api/action-events');
      expect(result).toEqual(mockResponse);
      expect(result.items).toHaveLength(1);
      expect(result.items[0].action).toBe('walking normally');
    });

    it('fetches action events with query parameters', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse));

      await fetchActionEvents({
        camera_id: 'front_door',
        is_suspicious: true,
        min_confidence: 0.8,
        limit: 20,
        offset: 10,
      });

      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/action-events?camera_id=front_door&is_suspicious=true&min_confidence=0.8&limit=20&offset=10'
      );
    });

    it('handles action filter parameter', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse));

      await fetchActionEvents({ action: 'climbing' });

      expect(fetchSpy).toHaveBeenCalledWith('/api/action-events?action=climbing');
    });

    it('handles date range parameters', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse));

      await fetchActionEvents({
        start_time: '2026-01-01T00:00:00Z',
        end_time: '2026-01-31T23:59:59Z',
      });

      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/action-events?start_time=2026-01-01T00%3A00%3A00Z&end_time=2026-01-31T23%3A59%3A59Z'
      );
    });

    it('throws error on failed request', async () => {
      fetchSpy.mockResolvedValueOnce(createMockErrorResponse(500, 'Internal Server Error'));

      await expect(fetchActionEvents()).rejects.toThrow(
        'Failed to fetch action events: 500 Internal Server Error'
      );
    });

    it('omits undefined and null parameters', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse));

      await fetchActionEvents({
        camera_id: 'front_door',
        track_id: undefined,
        action: undefined,
      });

      expect(fetchSpy).toHaveBeenCalledWith('/api/action-events?camera_id=front_door');
    });
  });

  // ============================================================================
  // fetchSuspiciousActions Tests
  // ============================================================================

  describe('fetchSuspiciousActions', () => {
    const mockResponse: SuspiciousActionsResponse = {
      items: [
        {
          id: 5,
          camera_id: 'back_yard',
          track_id: 17,
          action: 'climbing',
          confidence: 0.92,
          is_suspicious: true,
          timestamp: '2026-01-26T14:30:00Z',
          frame_count: 8,
          all_scores: { climbing: 0.92, 'walking normally': 0.05 },
          created_at: '2026-01-26T14:30:00Z',
        },
      ],
      pagination: {
        total: 1,
        limit: 50,
        offset: 0,
        has_more: false,
      },
      suspicious_count: 1,
      total_count: 25,
    };

    it('fetches suspicious actions successfully', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse));

      const result = await fetchSuspiciousActions();

      expect(fetchSpy).toHaveBeenCalledWith('/api/action-events/suspicious');
      expect(result).toEqual(mockResponse);
      expect(result.suspicious_count).toBe(1);
      expect(result.total_count).toBe(25);
      expect(result.items[0].is_suspicious).toBe(true);
    });

    it('fetches suspicious actions with filters', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse));

      await fetchSuspiciousActions({
        camera_id: 'back_yard',
        min_confidence: 0.9,
        limit: 10,
      });

      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/action-events/suspicious?camera_id=back_yard&min_confidence=0.9&limit=10'
      );
    });

    it('throws error on failed request', async () => {
      fetchSpy.mockResolvedValueOnce(createMockErrorResponse(503, 'Service Unavailable'));

      await expect(fetchSuspiciousActions()).rejects.toThrow(
        'Failed to fetch suspicious actions: 503 Service Unavailable'
      );
    });
  });

  // ============================================================================
  // fetchActionEvent Tests
  // ============================================================================

  describe('fetchActionEvent', () => {
    const mockEvent: ActionEvent = {
      id: 1,
      camera_id: 'front_door',
      track_id: 42,
      action: 'walking normally',
      confidence: 0.89,
      is_suspicious: false,
      timestamp: '2026-01-26T12:00:00Z',
      frame_count: 8,
      all_scores: { 'walking normally': 0.89 },
      created_at: '2026-01-26T12:00:00Z',
    };

    it('fetches a single action event by ID', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockEvent));

      const result = await fetchActionEvent(1);

      expect(fetchSpy).toHaveBeenCalledWith('/api/action-events/1');
      expect(result).toEqual(mockEvent);
    });

    it('throws specific error for 404', async () => {
      fetchSpy.mockResolvedValueOnce(createMockErrorResponse(404, 'Not Found'));

      await expect(fetchActionEvent(999)).rejects.toThrow('Action event 999 not found');
    });

    it('throws generic error for other failures', async () => {
      fetchSpy.mockResolvedValueOnce(createMockErrorResponse(500, 'Internal Server Error'));

      await expect(fetchActionEvent(1)).rejects.toThrow(
        'Failed to fetch action event: 500 Internal Server Error'
      );
    });
  });

  // ============================================================================
  // fetchActionEventsForCamera Tests
  // ============================================================================

  describe('fetchActionEventsForCamera', () => {
    const mockResponse: ActionEventListResponse = {
      items: [],
      pagination: {
        total: 0,
        limit: 50,
        offset: 0,
        has_more: false,
      },
    };

    it('fetches action events for a specific camera', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse));

      const result = await fetchActionEventsForCamera('front_door');

      expect(fetchSpy).toHaveBeenCalledWith('/api/action-events/camera/front_door');
      expect(result).toEqual(mockResponse);
    });

    it('includes optional parameters', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse));

      await fetchActionEventsForCamera('back_yard', {
        start_time: '2026-01-01T00:00:00Z',
        end_time: '2026-01-31T23:59:59Z',
        limit: 20,
        offset: 0,
      });

      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/action-events/camera/back_yard?start_time=2026-01-01T00%3A00%3A00Z&end_time=2026-01-31T23%3A59%3A59Z&limit=20&offset=0'
      );
    });

    it('throws error on failed request', async () => {
      fetchSpy.mockResolvedValueOnce(createMockErrorResponse(400, 'Bad Request'));

      await expect(fetchActionEventsForCamera('invalid')).rejects.toThrow(
        'Failed to fetch action events for camera: 400 Bad Request'
      );
    });
  });

  // ============================================================================
  // fetchActionEventsForEvent Tests
  // ============================================================================

  describe('fetchActionEventsForEvent', () => {
    const mockResponse: ActionEventListResponse = {
      items: [
        {
          id: 1,
          camera_id: 'front_door',
          track_id: null,
          action: 'walking normally',
          confidence: 0.85,
          is_suspicious: false,
          timestamp: '2026-01-26T12:01:00Z',
          frame_count: 8,
          all_scores: null,
          created_at: '2026-01-26T12:01:00Z',
        },
      ],
      pagination: {
        total: 1,
        limit: 50,
        offset: 0,
        has_more: false,
      },
    };

    it('fetches action events for an event with end time', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse));

      const result = await fetchActionEventsForEvent(
        123,
        'front_door',
        '2026-01-26T12:00:00Z',
        '2026-01-26T12:05:00Z'
      );

      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/action-events?camera_id=front_door')
      );
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('start_time=2026-01-26T12%3A00%3A00Z')
      );
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('end_time=2026-01-26T12%3A05%3A00Z')
      );
      expect(result).toEqual(mockResponse);
    });

    it('calculates end time for ongoing events (no end_time)', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse));

      await fetchActionEventsForEvent(123, 'front_door', '2026-01-26T12:00:00Z', null);

      // Should calculate end_time as 5 minutes after start
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('end_time=2026-01-26T12%3A05%3A00')
      );
    });

    it('uses custom limit', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse));

      await fetchActionEventsForEvent(
        123,
        'front_door',
        '2026-01-26T12:00:00Z',
        '2026-01-26T12:05:00Z',
        10
      );

      expect(fetchSpy).toHaveBeenCalledWith(expect.stringContaining('limit=10'));
    });
  });
});
