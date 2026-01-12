import { describe, it, expect, beforeEach } from 'vitest';

import {
  useStorageStatusStore,
  CRITICAL_USAGE_THRESHOLD,
  HIGH_USAGE_THRESHOLD,
  selectFormattedUsage,
} from './storage-status-store';

describe('storage-status-store', () => {
  beforeEach(() => {
    // Reset store state before each test
    useStorageStatusStore.getState().clear();
  });

  describe('initial state', () => {
    it('has null status initially', () => {
      const state = useStorageStatusStore.getState();
      expect(state.status).toBeNull();
      expect(state.isCritical).toBe(false);
      expect(state.isHigh).toBe(false);
    });
  });

  describe('update', () => {
    it('updates status with provided values', () => {
      const { update } = useStorageStatusStore.getState();

      update(50, 50_000_000_000, 100_000_000_000, 50_000_000_000);

      const state = useStorageStatusStore.getState();
      expect(state.status).not.toBeNull();
      expect(state.status?.usagePercent).toBe(50);
      expect(state.status?.usedBytes).toBe(50_000_000_000);
      expect(state.status?.totalBytes).toBe(100_000_000_000);
      expect(state.status?.freeBytes).toBe(50_000_000_000);
      expect(state.status?.lastUpdated).toBeInstanceOf(Date);
    });

    it('sets isCritical true when usage >= 90%', () => {
      const { update } = useStorageStatusStore.getState();

      update(CRITICAL_USAGE_THRESHOLD, 90_000_000_000, 100_000_000_000, 10_000_000_000);

      const state = useStorageStatusStore.getState();
      expect(state.isCritical).toBe(true);
    });

    it('sets isCritical false when usage < 90%', () => {
      const { update } = useStorageStatusStore.getState();

      update(CRITICAL_USAGE_THRESHOLD - 1, 89_000_000_000, 100_000_000_000, 11_000_000_000);

      const state = useStorageStatusStore.getState();
      expect(state.isCritical).toBe(false);
    });

    it('sets isHigh true when usage >= 85%', () => {
      const { update } = useStorageStatusStore.getState();

      update(HIGH_USAGE_THRESHOLD, 85_000_000_000, 100_000_000_000, 15_000_000_000);

      const state = useStorageStatusStore.getState();
      expect(state.isHigh).toBe(true);
    });

    it('sets isHigh false when usage < 85%', () => {
      const { update } = useStorageStatusStore.getState();

      update(HIGH_USAGE_THRESHOLD - 1, 84_000_000_000, 100_000_000_000, 16_000_000_000);

      const state = useStorageStatusStore.getState();
      expect(state.isHigh).toBe(false);
    });
  });

  describe('clear', () => {
    it('resets all state to initial values', () => {
      const { update, clear } = useStorageStatusStore.getState();

      // First update to set some values
      update(95, 95_000_000_000, 100_000_000_000, 5_000_000_000);

      // Verify values are set
      let state = useStorageStatusStore.getState();
      expect(state.isCritical).toBe(true);

      // Clear
      clear();

      // Verify reset
      state = useStorageStatusStore.getState();
      expect(state.status).toBeNull();
      expect(state.isCritical).toBe(false);
      expect(state.isHigh).toBe(false);
    });
  });

  describe('selectFormattedUsage', () => {
    it('returns null when status is null', () => {
      const state = useStorageStatusStore.getState();
      expect(selectFormattedUsage(state)).toBeNull();
    });

    it('returns formatted usage string', () => {
      const { update } = useStorageStatusStore.getState();

      // 50 GB used of 100 GB total
      update(50, 50_000_000_000, 100_000_000_000, 50_000_000_000);

      const state = useStorageStatusStore.getState();
      const formatted = selectFormattedUsage(state);

      expect(formatted).toContain('GB');
      expect(formatted).toContain('/');
    });

    it('formats TB values correctly', () => {
      const { update } = useStorageStatusStore.getState();

      // Use values > 1TB (binary: 1TB = 1024^4 = 1099511627776 bytes)
      // 1.5TB used of 3TB total
      const TB = 1024 * 1024 * 1024 * 1024;
      update(50, 1.5 * TB, 3 * TB, 1.5 * TB);

      const state = useStorageStatusStore.getState();
      const formatted = selectFormattedUsage(state);

      expect(formatted).toContain('TB');
    });
  });

  describe('constants', () => {
    it('has correct CRITICAL_USAGE_THRESHOLD', () => {
      expect(CRITICAL_USAGE_THRESHOLD).toBe(90);
    });

    it('has correct HIGH_USAGE_THRESHOLD', () => {
      expect(HIGH_USAGE_THRESHOLD).toBe(85);
    });
  });
});
