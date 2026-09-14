/**
 * Tests for Alert Types
 *
 * Tests type guards and utility functions for alert types
 * with optimistic locking support.
 *
 * @see NEM-3626
 */

import { describe, it, expect } from 'vitest';

import { isOptimisticLockError, type OptimisticLockError, type ConflictState } from './alerts';

describe('Alert Types', () => {
  describe('isOptimisticLockError', () => {
    it('returns true for valid optimistic lock errors', () => {
      const error: OptimisticLockError = {
        status: 409,
        detail: 'Alert was modified by another request. Please refresh and retry.',
        isStaleDataError: true,
      };

      expect(isOptimisticLockError(error)).toBe(true);
    });

    it('returns false for non-409 errors', () => {
      const error = {
        status: 404,
        detail: 'Alert not found',
        isStaleDataError: false,
      };

      expect(isOptimisticLockError(error)).toBe(false);
    });

    it('returns false for errors without isStaleDataError flag', () => {
      const error = {
        status: 409,
        detail: 'Alert cannot be acknowledged. Current status: dismissed',
      };

      expect(isOptimisticLockError(error)).toBe(false);
    });

    it('returns false for null', () => {
      expect(isOptimisticLockError(null)).toBe(false);
    });

    it('returns false for undefined', () => {
      expect(isOptimisticLockError(undefined)).toBe(false);
    });

    it('returns false for non-object types', () => {
      expect(isOptimisticLockError('error')).toBe(false);
      expect(isOptimisticLockError(409)).toBe(false);
      expect(isOptimisticLockError(true)).toBe(false);
    });

    it('returns false when isStaleDataError is false', () => {
      const error = {
        status: 409,
        detail: 'Some conflict',
        isStaleDataError: false,
      };

      expect(isOptimisticLockError(error)).toBe(false);
    });
  });

  describe('ConflictState', () => {
    it('has correct default shape', () => {
      const defaultState: ConflictState = {
        hasConflict: false,
        alertId: null,
        action: null,
        errorMessage: null,
      };

      expect(defaultState.hasConflict).toBe(false);
      expect(defaultState.alertId).toBeNull();
      expect(defaultState.action).toBeNull();
      expect(defaultState.errorMessage).toBeNull();
    });

    it('supports acknowledge action', () => {
      const state: ConflictState = {
        hasConflict: true,
        alertId: 'alert-123',
        action: 'acknowledge',
        errorMessage: 'Alert was modified',
      };

      expect(state.action).toBe('acknowledge');
    });

    it('supports dismiss action', () => {
      const state: ConflictState = {
        hasConflict: true,
        alertId: 'alert-123',
        action: 'dismiss',
        errorMessage: 'Alert was modified',
      };

      expect(state.action).toBe('dismiss');
    });
  });
});
