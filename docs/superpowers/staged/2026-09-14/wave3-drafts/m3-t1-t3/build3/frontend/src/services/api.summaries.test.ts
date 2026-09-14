/**
 * Tests for Summary API endpoints
 *
 * @see NEM-3261 - Bug fix for undefined event_count handling
 */

import { describe, expect, it, vi, beforeAll, beforeEach, afterEach, afterAll } from 'vitest';

import { fetchSummaries } from './api';
import { server } from '../mocks/server';

// Mock fetch globally - must be done at module level before MSW starts
const mockFetch = vi.fn();

/**
 * Helper to create a mock Response object with proper headers
 */
function createMockResponse(data: unknown, status = 200, ok = true): Partial<Response> {
  return {
    ok,
    status,
    json: () => Promise.resolve(data),
    headers: new Headers(),
  };
}

describe('fetchSummaries', () => {
  // Temporarily close MSW for these unit tests since we're testing the fetch wrapper directly
  beforeAll(() => {
    server.close();
  });

  afterAll(() => {
    server.listen({ onUnhandledRequest: 'bypass' });
  });

  beforeEach(() => {
    mockFetch.mockClear();
    vi.stubGlobal('fetch', mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('should fetch and transform summaries with valid data', async () => {
    const mockBackendResponse = {
      hourly: {
        id: 1,
        content: 'One critical event at 2:15 PM at the front door.',
        event_count: 1,
        window_start: '2026-01-18T14:00:00Z',
        window_end: '2026-01-18T15:00:00Z',
        generated_at: '2026-01-18T14:55:00Z',
        structured: null,
      },
      daily: {
        id: 2,
        content: 'No high-priority events today. Property is quiet.',
        event_count: 0,
        window_start: '2026-01-18T00:00:00Z',
        window_end: '2026-01-18T15:00:00Z',
        generated_at: '2026-01-18T14:55:00Z',
        structured: null,
      },
    };

    mockFetch.mockResolvedValueOnce(createMockResponse(mockBackendResponse));

    const result = await fetchSummaries();

    expect(result.hourly).not.toBeNull();
    expect(result.hourly?.eventCount).toBe(1);
    expect(result.hourly?.content).toBe('One critical event at 2:15 PM at the front door.');

    expect(result.daily).not.toBeNull();
    expect(result.daily?.eventCount).toBe(0);
    expect(result.daily?.content).toBe('No high-priority events today. Property is quiet.');
  });

  it('should handle missing event_count by defaulting to 0 (NEM-3261)', async () => {
    const mockBackendResponse = {
      hourly: {
        id: 1,
        content: 'One critical event at 2:15 PM at the front door.',
        // event_count is missing (undefined)
        window_start: '2026-01-18T14:00:00Z',
        window_end: '2026-01-18T15:00:00Z',
        generated_at: '2026-01-18T14:55:00Z',
        structured: null,
      },
      daily: null,
    };

    mockFetch.mockResolvedValueOnce(createMockResponse(mockBackendResponse));

    const result = await fetchSummaries();

    expect(result.hourly).not.toBeNull();
    expect(result.hourly?.eventCount).toBe(0); // Should default to 0
    expect(result.hourly?.content).toBe('One critical event at 2:15 PM at the front door.');
  });

  it('should handle null event_count by defaulting to 0 (NEM-3261)', async () => {
    const mockBackendResponse = {
      hourly: {
        id: 1,
        content: 'One critical event at 2:15 PM at the front door.',
        event_count: null, // Explicitly null
        window_start: '2026-01-18T14:00:00Z',
        window_end: '2026-01-18T15:00:00Z',
        generated_at: '2026-01-18T14:55:00Z',
        structured: null,
      },
      daily: null,
    };

    mockFetch.mockResolvedValueOnce(createMockResponse(mockBackendResponse));

    const result = await fetchSummaries();

    expect(result.hourly).not.toBeNull();
    expect(result.hourly?.eventCount).toBe(0); // Should default to 0
  });

  it('should handle both summaries being null', async () => {
    const mockBackendResponse = {
      hourly: null,
      daily: null,
    };

    mockFetch.mockResolvedValueOnce(createMockResponse(mockBackendResponse));

    const result = await fetchSummaries();

    expect(result.hourly).toBeNull();
    expect(result.daily).toBeNull();
  });

  it('should transform structured data when present', async () => {
    const mockBackendResponse = {
      hourly: {
        id: 1,
        content: 'One critical event at 2:15 PM at the front door.',
        event_count: 1,
        window_start: '2026-01-18T14:00:00Z',
        window_end: '2026-01-18T15:00:00Z',
        generated_at: '2026-01-18T14:55:00Z',
        structured: {
          bullet_points: [
            {
              icon: 'alert',
              text: 'Person at front door',
              severity: '85',
            },
          ],
          focus_areas: ['Front Door'],
          dominant_patterns: ['person'],
          max_risk_score: 85,
          weather_conditions: ['clear'],
        },
      },
      daily: null,
    };

    mockFetch.mockResolvedValueOnce(createMockResponse(mockBackendResponse));

    const result = await fetchSummaries();

    expect(result.hourly).not.toBeNull();
    expect(result.hourly?.bulletPoints).toHaveLength(1);
    expect(result.hourly?.bulletPoints?.[0].icon).toBe('alert');
    expect(result.hourly?.bulletPoints?.[0].text).toBe('Person at front door');
    expect(result.hourly?.bulletPoints?.[0].severity).toBe(85);
    expect(result.hourly?.focusAreas).toEqual(['Front Door']);
    expect(result.hourly?.dominantPatterns).toEqual(['person']);
    expect(result.hourly?.maxRiskScore).toBe(85);
    expect(result.hourly?.weatherConditions).toBe('clear');
  });

  it('should format time range correctly', async () => {
    const mockBackendResponse = {
      hourly: {
        id: 1,
        content: 'Event during afternoon.',
        event_count: 1,
        window_start: '2026-01-18T14:30:00Z',
        window_end: '2026-01-18T15:45:00Z',
        generated_at: '2026-01-18T15:00:00Z',
        structured: null,
      },
      daily: null,
    };

    mockFetch.mockResolvedValueOnce(createMockResponse(mockBackendResponse));

    const result = await fetchSummaries();

    expect(result.hourly).not.toBeNull();
    // Time range should be formatted (implementation depends on formatTimeRange function)
    expect(result.hourly?.timeRangeFormatted).toBeDefined();
  });
});
