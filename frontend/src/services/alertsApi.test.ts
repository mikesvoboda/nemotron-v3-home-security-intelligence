/**
 * Tests for Alerts API Client
 *
 * Tests the alert mutation endpoints (acknowledge, dismiss) with
 * comprehensive coverage of success cases, error handling, and
 * optimistic locking conflict detection.
 *
 * @see NEM-3626
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  AlertsApiError,
  acknowledgeAlert,
  dismissAlert,
  isConflictError,
  type AlertResponse,
} from './alertsApi';

// ============================================================================
// Mock Data
// ============================================================================

const mockAlertResponse: AlertResponse = {
  id: '550e8400-e29b-41d4-a716-446655440001',
  event_id: 123,
  rule_id: '550e8400-e29b-41d4-a716-446655440000',
  severity: 'high',
  status: 'acknowledged',
  created_at: '2025-12-28T12:00:00Z',
  updated_at: '2025-12-28T12:01:00Z',
  delivered_at: '2025-12-28T12:00:30Z',
  channels: ['pushover'],
  dedup_key: 'front_door:person:entry_zone',
  metadata: { camera_name: 'Front Door' },
  version_id: 2,
};

const mockDismissedAlertResponse: AlertResponse = {
  ...mockAlertResponse,
  status: 'dismissed',
  version_id: 3,
};

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

function createMockErrorResponse(status: number, statusText: string, detail?: string): Response {
  const errorBody = detail ? { detail } : null;
  return {
    ok: false,
    status,
    statusText,
    json: () => Promise.resolve(errorBody),
    headers: new Headers({ 'Content-Type': 'application/json' }),
  } as Response;
}

// ============================================================================
// Tests
// ============================================================================

describe('alertsApi', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('acknowledgeAlert', () => {
    it('successfully acknowledges an alert', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockAlertResponse));

      const result = await acknowledgeAlert('550e8400-e29b-41d4-a716-446655440001');

      expect(result).toEqual(mockAlertResponse);
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/alerts/550e8400-e29b-41d4-a716-446655440001/acknowledge'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
    });

    it('returns the updated alert with new version_id', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockAlertResponse));

      const result = await acknowledgeAlert('alert-123');

      expect(result.version_id).toBe(2);
      expect(result.status).toBe('acknowledged');
    });

    it('throws AlertsApiError on 404 not found', async () => {
      fetchSpy.mockResolvedValueOnce(
        createMockErrorResponse(404, 'Not Found', 'Alert alert-not-found not found')
      );

      await expect(acknowledgeAlert('alert-not-found')).rejects.toThrow(AlertsApiError);
      await expect(acknowledgeAlert('alert-not-found')).rejects.toThrow('Alert not found');
    });

    it('throws AlertsApiError with isConflict flag on 409 conflict', async () => {
      fetchSpy.mockResolvedValue(
        createMockErrorResponse(
          409,
          'Conflict',
          'Alert was modified by another request. Please refresh and retry.'
        )
      );

      try {
        await acknowledgeAlert('alert-123');
        expect.fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(AlertsApiError);
        expect((error as AlertsApiError).isConflict).toBe(true);
        expect((error as AlertsApiError).status).toBe(409);
      }
    });

    it('throws AlertsApiError on 409 when alert cannot be acknowledged', async () => {
      fetchSpy.mockResolvedValue(
        createMockErrorResponse(
          409,
          'Conflict',
          'Alert cannot be acknowledged. Current status: dismissed'
        )
      );

      try {
        await acknowledgeAlert('alert-dismissed');
        expect.fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(AlertsApiError);
        expect((error as AlertsApiError).isConflict).toBe(true);
      }
    });

    it('throws AlertsApiError on server error', async () => {
      fetchSpy.mockResolvedValue(
        createMockErrorResponse(500, 'Internal Server Error', 'Database connection failed')
      );

      try {
        await acknowledgeAlert('alert-123');
        expect.fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(AlertsApiError);
        expect((error as AlertsApiError).isConflict).toBe(false);
        expect((error as AlertsApiError).status).toBe(500);
      }
    });

    it('throws AlertsApiError on network failure', async () => {
      fetchSpy.mockRejectedValue(new Error('Network error'));

      try {
        await acknowledgeAlert('alert-123');
        expect.fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(AlertsApiError);
        expect((error as AlertsApiError).message).toBe('Network error');
      }
    });
  });

  describe('dismissAlert', () => {
    it('successfully dismisses an alert', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockDismissedAlertResponse));

      const result = await dismissAlert('550e8400-e29b-41d4-a716-446655440001');

      expect(result).toEqual(mockDismissedAlertResponse);
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/alerts/550e8400-e29b-41d4-a716-446655440001/dismiss'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
    });

    it('returns the updated alert with new version_id', async () => {
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockDismissedAlertResponse));

      const result = await dismissAlert('alert-123');

      expect(result.version_id).toBe(3);
      expect(result.status).toBe('dismissed');
    });

    it('throws AlertsApiError on 404 not found', async () => {
      fetchSpy.mockResolvedValueOnce(
        createMockErrorResponse(404, 'Not Found', 'Alert alert-not-found not found')
      );

      await expect(dismissAlert('alert-not-found')).rejects.toThrow(AlertsApiError);
      await expect(dismissAlert('alert-not-found')).rejects.toThrow('Alert not found');
    });

    it('throws AlertsApiError with isConflict flag on 409 conflict', async () => {
      fetchSpy.mockResolvedValue(
        createMockErrorResponse(
          409,
          'Conflict',
          'Alert was modified by another request. Please refresh and retry.'
        )
      );

      try {
        await dismissAlert('alert-123');
        expect.fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(AlertsApiError);
        expect((error as AlertsApiError).isConflict).toBe(true);
        expect((error as AlertsApiError).status).toBe(409);
      }
    });

    it('throws AlertsApiError on 409 when alert is already dismissed', async () => {
      fetchSpy.mockResolvedValue(
        createMockErrorResponse(409, 'Conflict', 'Alert is already dismissed')
      );

      try {
        await dismissAlert('alert-dismissed');
        expect.fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(AlertsApiError);
        expect((error as AlertsApiError).isConflict).toBe(true);
      }
    });

    it('throws AlertsApiError on server error', async () => {
      fetchSpy.mockResolvedValue(
        createMockErrorResponse(500, 'Internal Server Error', 'Database connection failed')
      );

      try {
        await dismissAlert('alert-123');
        expect.fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(AlertsApiError);
        expect((error as AlertsApiError).isConflict).toBe(false);
        expect((error as AlertsApiError).status).toBe(500);
      }
    });

    it('throws AlertsApiError on network failure', async () => {
      fetchSpy.mockRejectedValue(new Error('Network error'));

      try {
        await dismissAlert('alert-123');
        expect.fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(AlertsApiError);
        expect((error as AlertsApiError).message).toBe('Network error');
      }
    });
  });

  describe('isConflictError', () => {
    it('returns true for AlertsApiError with isConflict flag', () => {
      const error = new AlertsApiError('Conflict', 409, true);
      expect(isConflictError(error)).toBe(true);
    });

    it('returns false for AlertsApiError without isConflict flag', () => {
      const error = new AlertsApiError('Not found', 404, false);
      expect(isConflictError(error)).toBe(false);
    });

    it('returns false for regular Error', () => {
      const error = new Error('Something went wrong');
      expect(isConflictError(error)).toBe(false);
    });

    it('returns false for null', () => {
      expect(isConflictError(null)).toBe(false);
    });

    it('returns false for undefined', () => {
      expect(isConflictError(undefined)).toBe(false);
    });

    it('returns false for non-Error objects', () => {
      expect(isConflictError({ isConflict: true })).toBe(false);
      expect(isConflictError('error')).toBe(false);
      expect(isConflictError(409)).toBe(false);
    });
  });

  describe('AlertsApiError', () => {
    it('has correct name property', () => {
      const error = new AlertsApiError('Test error', 500, false);
      expect(error.name).toBe('AlertsApiError');
    });

    it('preserves error message', () => {
      const error = new AlertsApiError('Custom error message', 500, false);
      expect(error.message).toBe('Custom error message');
    });

    it('preserves status code', () => {
      const error = new AlertsApiError('Test error', 404, false);
      expect(error.status).toBe(404);
    });

    it('preserves isConflict flag', () => {
      const conflictError = new AlertsApiError('Conflict', 409, true);
      const normalError = new AlertsApiError('Error', 500, false);

      expect(conflictError.isConflict).toBe(true);
      expect(normalError.isConflict).toBe(false);
    });

    it('is instanceof Error', () => {
      const error = new AlertsApiError('Test', 500, false);
      expect(error).toBeInstanceOf(Error);
    });

    it('is instanceof AlertsApiError', () => {
      const error = new AlertsApiError('Test', 500, false);
      expect(error).toBeInstanceOf(AlertsApiError);
    });
  });
});
