/**
 * Tests for Service Worker Registration Module
 * @see NEM-3675 - PWA Offline Caching
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { getServiceWorkerState, getCacheStorageEstimate } from './serviceWorkerRegistration';

describe('serviceWorkerRegistration', () => {
  const originalStorage = navigator.storage;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    Object.defineProperty(navigator, 'storage', {
      value: originalStorage,
      writable: true,
      configurable: true,
    });
  });

  describe('getServiceWorkerState', () => {
    it('returns current service worker state', () => {
      const state = getServiceWorkerState();
      expect(state).toHaveProperty('isActive');
      expect(state).toHaveProperty('isUpdateWaiting');
      expect(state).toHaveProperty('isInstalling');
      expect(state).toHaveProperty('workbox');
    });

    it('returns immutable copy of state', () => {
      const state1 = getServiceWorkerState();
      const state2 = getServiceWorkerState();
      expect(state1).not.toBe(state2);
      expect(state1).toEqual(state2);
    });
  });

  describe('getCacheStorageEstimate', () => {
    it('returns storage estimate with usage percentage', async () => {
      Object.defineProperty(navigator, 'storage', {
        value: {
          estimate: vi.fn().mockResolvedValue({ usage: 1000000, quota: 100000000 }),
        },
        writable: true,
        configurable: true,
      });

      const result = await getCacheStorageEstimate();
      expect(result).toEqual({ usage: 1000000, quota: 100000000, usagePercentage: 1 });
    });

    it('returns null when storage API not available', async () => {
      Object.defineProperty(navigator, 'storage', {
        value: undefined,
        writable: true,
        configurable: true,
      });

      const result = await getCacheStorageEstimate();
      expect(result).toBeNull();
    });

    it('handles zero quota gracefully', async () => {
      Object.defineProperty(navigator, 'storage', {
        value: {
          estimate: vi.fn().mockResolvedValue({ usage: 0, quota: 0 }),
        },
        writable: true,
        configurable: true,
      });

      const result = await getCacheStorageEstimate();
      expect(result).toEqual({ usage: 0, quota: 0, usagePercentage: 0 });
    });
  });
});
