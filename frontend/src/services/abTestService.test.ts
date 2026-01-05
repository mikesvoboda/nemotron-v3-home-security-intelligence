import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { abTestService, type ModelConfig, type EventSummary } from './abTestService';

// Save original fetch for restoration
const originalFetch = globalThis.fetch;

// ============================================================================
// Mock Data
// ============================================================================

const mockModelConfig: ModelConfig = {
  model: 'nemotron',
  temperature: 0.7,
  maxTokens: 2048,
};

// API response uses snake_case
const mockApiTestPromptResponse = {
  risk_score: 75,
  risk_level: 'high',
  reasoning: 'Suspicious activity detected near entrance',
  summary: 'Person detected at unusual hour',
  processing_time_ms: 150,
  tokens_used: 500,
};

// Note: The API returns snake_case, but the service converts to camelCase
// The TestPromptResponse type uses camelCase for TypeScript consumers

const mockEventSummary: EventSummary = {
  id: 1,
  timestamp: '2025-01-01T10:00:00Z',
  cameraName: 'Front Door',
  detectionCount: 5,
};

const mockEvents = [
  { ...mockEventSummary, id: 1 },
  { ...mockEventSummary, id: 2, cameraName: 'Backyard' },
  { ...mockEventSummary, id: 3, cameraName: 'Driveway' },
];

// ============================================================================
// Helper Functions
// ============================================================================

function createMockResponse<T>(data: T, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(data),
    headers: new Headers({ 'Content-Type': 'application/json' }),
  } as Response;
}


// ============================================================================
// Test Setup
// ============================================================================

describe('abTestService', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    globalThis.fetch = fetchMock as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  // ==========================================================================
  // runTest Tests
  // ==========================================================================

  describe('runTest', () => {
    it('calls API for both prompts', async () => {
      // Arrange: Mock both API calls to return different results (snake_case from API)
      const originalResponse = { ...mockApiTestPromptResponse, risk_score: 50 };
      const modifiedResponse = { ...mockApiTestPromptResponse, risk_score: 75 };

      fetchMock
        .mockResolvedValueOnce(createMockResponse(originalResponse))
        .mockResolvedValueOnce(createMockResponse(modifiedResponse));

      // Act
      await abTestService.runTest(
        1,
        'Original prompt text',
        'Modified prompt text',
        mockModelConfig
      );

      // Assert: Two API calls were made
      expect(fetchMock).toHaveBeenCalledTimes(2);

      // Verify first call is for original prompt
      const firstCall = fetchMock.mock.calls[0];
      expect(firstCall[0]).toContain('/api/ai-audit/test-prompt');
      const firstBody = JSON.parse(firstCall[1]?.body as string);
      expect(firstBody.custom_prompt).toBe('Original prompt text');

      // Verify second call is for modified prompt
      const secondCall = fetchMock.mock.calls[1];
      expect(secondCall[0]).toContain('/api/ai-audit/test-prompt');
      const secondBody = JSON.parse(secondCall[1]?.body as string);
      expect(secondBody.custom_prompt).toBe('Modified prompt text');
    });

    it('calculates correct scoreDelta', async () => {
      // Arrange: Original score 40, Modified score 75 -> delta = 35 (snake_case from API)
      const originalResponse = { ...mockApiTestPromptResponse, risk_score: 40 };
      const modifiedResponse = { ...mockApiTestPromptResponse, risk_score: 75 };

      fetchMock
        .mockResolvedValueOnce(createMockResponse(originalResponse))
        .mockResolvedValueOnce(createMockResponse(modifiedResponse));

      // Act
      const result = await abTestService.runTest(
        1,
        'Original prompt',
        'Modified prompt',
        mockModelConfig
      );

      // Assert
      expect(result.originalResult.riskScore).toBe(40);
      expect(result.modifiedResult.riskScore).toBe(75);
      expect(result.scoreDelta).toBe(35); // 75 - 40 = 35
    });

    it('runs prompts in parallel', async () => {
      // Arrange: Track timing to verify parallel execution
      const callTimes: number[] = [];
      const resolveFunctions: Array<(value: Response) => void> = [];

      fetchMock.mockImplementation(() => {
        callTimes.push(Date.now());
        return new Promise((resolve) => {
          resolveFunctions.push(resolve);
        });
      });

      // Act: Start the test (don't await yet)
      const testPromise = abTestService.runTest(
        1,
        'Original prompt',
        'Modified prompt',
        mockModelConfig
      );

      // Wait for both calls to be initiated
      await new Promise((r) => setTimeout(r, 10));

      // Assert: Both calls should have been made before either resolved
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(resolveFunctions.length).toBe(2);

      // Both calls should happen at nearly the same time (parallel)
      if (callTimes.length === 2) {
        const timeDiff = Math.abs(callTimes[1] - callTimes[0]);
        expect(timeDiff).toBeLessThan(50); // Less than 50ms apart = parallel
      }

      // Cleanup: Resolve the promises
      resolveFunctions.forEach((resolve) => {
        resolve(createMockResponse(mockApiTestPromptResponse));
      });
      await testPromise;
    });

    it('handles API timeout gracefully', async () => {
      // Arrange: Mock a timeout error
      fetchMock.mockRejectedValueOnce(new Error('Request timeout'));
      fetchMock.mockResolvedValueOnce(createMockResponse(mockApiTestPromptResponse));

      // Act
      const result = await abTestService.runTest(
        1,
        'Original prompt',
        'Modified prompt',
        mockModelConfig
      );

      // Assert: Result should contain error information
      expect(result.error).toBeDefined();
      expect(result.error).toContain('timeout');
    });
  });

  // ==========================================================================
  // runRandomTests Tests
  // ==========================================================================

  describe('runRandomTests', () => {
    it('fetches events first', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce(
        createMockResponse({
          events: mockEvents,
          count: 3,
          limit: 10,
          offset: 0,
        })
      );

      // For each event, need two test-prompt calls
      mockEvents.forEach(() => {
        fetchMock
          .mockResolvedValueOnce(createMockResponse(mockApiTestPromptResponse))
          .mockResolvedValueOnce(createMockResponse(mockApiTestPromptResponse));
      });

      // Act
      await abTestService.runRandomTests(
        3,
        'Original prompt',
        'Modified prompt',
        mockModelConfig
      );

      // Assert: First call should be to fetch events
      const firstCall = fetchMock.mock.calls[0];
      expect(firstCall[0]).toContain('/api/events');
    });

    it('handles partial failures', async () => {
      // Arrange: Return 3 events
      fetchMock.mockResolvedValueOnce(
        createMockResponse({
          events: mockEvents,
          count: 3,
          limit: 10,
          offset: 0,
        })
      );

      // First event succeeds (snake_case from API)
      fetchMock
        .mockResolvedValueOnce(createMockResponse({ ...mockApiTestPromptResponse, risk_score: 50 }))
        .mockResolvedValueOnce(createMockResponse({ ...mockApiTestPromptResponse, risk_score: 60 }));

      // Second event fails
      fetchMock
        .mockRejectedValueOnce(new Error('API Error'))
        .mockResolvedValueOnce(createMockResponse(mockApiTestPromptResponse));

      // Third event succeeds (snake_case from API)
      fetchMock
        .mockResolvedValueOnce(createMockResponse({ ...mockApiTestPromptResponse, risk_score: 30 }))
        .mockResolvedValueOnce(createMockResponse({ ...mockApiTestPromptResponse, risk_score: 40 }));

      // Act
      const results = await abTestService.runRandomTests(
        3,
        'Original prompt',
        'Modified prompt',
        mockModelConfig
      );

      // Assert: Should return successful results (may be 2 or 3 depending on error handling)
      expect(results.length).toBeGreaterThanOrEqual(2);
      // All returned results should have valid data
      results.forEach((result) => {
        expect(result.eventId).toBeDefined();
      });
    });

    it('respects count parameter', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce(
        createMockResponse({
          events: mockEvents.slice(0, 2), // Only 2 events
          count: 2,
          limit: 2,
          offset: 0,
        })
      );

      // Mock the test-prompt calls for 2 events (snake_case from API)
      for (let i = 0; i < 2; i++) {
        fetchMock
          .mockResolvedValueOnce(createMockResponse(mockApiTestPromptResponse))
          .mockResolvedValueOnce(createMockResponse(mockApiTestPromptResponse));
      }

      // Act
      const results = await abTestService.runRandomTests(
        2,
        'Original prompt',
        'Modified prompt',
        mockModelConfig
      );

      // Assert: Should respect count and only process 2 events
      expect(results.length).toBeLessThanOrEqual(2);

      // Verify events endpoint was called with limit=2
      const eventsCall = fetchMock.mock.calls[0];
      expect(eventsCall[0]).toContain('limit=2');
    });
  });

  // ==========================================================================
  // getAvailableEvents Tests
  // ==========================================================================

  describe('getAvailableEvents', () => {
    it('returns recent events', async () => {
      // Arrange - Event API returns camera_id, not camera_name
      const eventsResponse = {
        events: mockEvents.map((e) => ({
          id: e.id,
          camera_id: `cam-${e.id}`,
          started_at: e.timestamp,
          detection_count: e.detectionCount,
          reviewed: false,
        })),
        count: 3,
        limit: 50,
        offset: 0,
      };
      fetchMock.mockResolvedValueOnce(createMockResponse(eventsResponse));

      // Act
      const events = await abTestService.getAvailableEvents();

      // Assert - cameraName is derived from camera_id since Event doesn't have camera_name
      expect(events.length).toBe(3);
      expect(events[0].id).toBe(1);
      expect(events[0].cameraName).toBe('cam-1');
    });

    it('API is called correctly with limit', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce(
        createMockResponse({
          events: [],
          count: 0,
          limit: 20,
          offset: 0,
        })
      );

      // Act
      await abTestService.getAvailableEvents(20);

      // Assert
      expect(fetchMock).toHaveBeenCalledTimes(1);
      const call = fetchMock.mock.calls[0];
      expect(call[0]).toContain('/api/events');
      expect(call[0]).toContain('limit=20');
    });
  });

  // ==========================================================================
  // Timeout Handling Tests
  // ==========================================================================

  describe('timeout handling', () => {
    it('handles API timeout gracefully', async () => {
      // Arrange: Create a promise that never resolves to simulate timeout
      const timeoutError = new Error('timeout');
      timeoutError.name = 'AbortError';

      fetchMock.mockRejectedValueOnce(timeoutError);
      fetchMock.mockResolvedValueOnce(createMockResponse(mockApiTestPromptResponse));

      // Act
      const result = await abTestService.runTest(
        1,
        'Original prompt',
        'Modified prompt',
        mockModelConfig
      );

      // Assert: Should return error info rather than throwing
      expect(result.error).toBeDefined();
    });
  });
});
