import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';

import { useSummaryExpansion } from './useSummaryExpansion';

describe('useSummaryExpansion', () => {
  beforeEach(() => {
    // Clear sessionStorage before each test
    sessionStorage.clear();
  });

  afterEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('returns defaultExpanded=false by default', () => {
      const { result } = renderHook(() => useSummaryExpansion({ summaryId: 'test-1' }));

      expect(result.current.isExpanded).toBe(false);
    });

    it('respects defaultExpanded=true option', () => {
      const { result } = renderHook(() =>
        useSummaryExpansion({ summaryId: 'test-1', defaultExpanded: true })
      );

      expect(result.current.isExpanded).toBe(true);
    });

    it('restores state from sessionStorage', () => {
      sessionStorage.setItem('summary-expansion-test-1', 'true');

      const { result } = renderHook(() => useSummaryExpansion({ summaryId: 'test-1' }));

      expect(result.current.isExpanded).toBe(true);
    });

    it('prefers sessionStorage over defaultExpanded', () => {
      sessionStorage.setItem('summary-expansion-test-1', 'false');

      const { result } = renderHook(() =>
        useSummaryExpansion({ summaryId: 'test-1', defaultExpanded: true })
      );

      expect(result.current.isExpanded).toBe(false);
    });
  });

  describe('toggle', () => {
    it('toggles from false to true', () => {
      const { result } = renderHook(() => useSummaryExpansion({ summaryId: 'test-1' }));

      expect(result.current.isExpanded).toBe(false);

      act(() => {
        result.current.toggle();
      });

      expect(result.current.isExpanded).toBe(true);
    });

    it('toggles from true to false', () => {
      const { result } = renderHook(() =>
        useSummaryExpansion({ summaryId: 'test-1', defaultExpanded: true })
      );

      expect(result.current.isExpanded).toBe(true);

      act(() => {
        result.current.toggle();
      });

      expect(result.current.isExpanded).toBe(false);
    });

    it('persists toggled state to sessionStorage', () => {
      const { result } = renderHook(() => useSummaryExpansion({ summaryId: 'test-1' }));

      act(() => {
        result.current.toggle();
      });

      expect(sessionStorage.getItem('summary-expansion-test-1')).toBe('true');

      act(() => {
        result.current.toggle();
      });

      expect(sessionStorage.getItem('summary-expansion-test-1')).toBe('false');
    });
  });

  describe('setExpanded', () => {
    it('sets expanded to true', () => {
      const { result } = renderHook(() => useSummaryExpansion({ summaryId: 'test-1' }));

      act(() => {
        result.current.setExpanded(true);
      });

      expect(result.current.isExpanded).toBe(true);
    });

    it('sets expanded to false', () => {
      const { result } = renderHook(() =>
        useSummaryExpansion({ summaryId: 'test-1', defaultExpanded: true })
      );

      act(() => {
        result.current.setExpanded(false);
      });

      expect(result.current.isExpanded).toBe(false);
    });

    it('persists state to sessionStorage', () => {
      const { result } = renderHook(() => useSummaryExpansion({ summaryId: 'test-1' }));

      act(() => {
        result.current.setExpanded(true);
      });

      expect(sessionStorage.getItem('summary-expansion-test-1')).toBe('true');
    });
  });

  describe('clearStorage', () => {
    it('removes item from sessionStorage', () => {
      const { result } = renderHook(() => useSummaryExpansion({ summaryId: 'test-1' }));

      act(() => {
        result.current.setExpanded(true);
      });

      expect(sessionStorage.getItem('summary-expansion-test-1')).toBe('true');

      act(() => {
        result.current.clearStorage();
      });

      expect(sessionStorage.getItem('summary-expansion-test-1')).toBeNull();
    });
  });

  describe('summaryId changes', () => {
    it('updates state when summaryId changes', () => {
      // Set up different values for different IDs
      sessionStorage.setItem('summary-expansion-test-1', 'true');
      sessionStorage.setItem('summary-expansion-test-2', 'false');

      const { result, rerender } = renderHook(
        ({ summaryId }) => useSummaryExpansion({ summaryId }),
        { initialProps: { summaryId: 'test-1' } }
      );

      expect(result.current.isExpanded).toBe(true);

      rerender({ summaryId: 'test-2' });

      expect(result.current.isExpanded).toBe(false);
    });

    it('uses defaultExpanded for new summaryId without storage', () => {
      sessionStorage.setItem('summary-expansion-test-1', 'true');

      const { result, rerender } = renderHook(
        ({ summaryId }) => useSummaryExpansion({ summaryId, defaultExpanded: false }),
        { initialProps: { summaryId: 'test-1' } }
      );

      expect(result.current.isExpanded).toBe(true);

      rerender({ summaryId: 'test-new' });

      expect(result.current.isExpanded).toBe(false);
    });
  });

  describe('storage key format', () => {
    it('uses correct storage key prefix', () => {
      const { result } = renderHook(() => useSummaryExpansion({ summaryId: 'hourly-123' }));

      act(() => {
        result.current.setExpanded(true);
      });

      expect(sessionStorage.getItem('summary-expansion-hourly-123')).toBe('true');
    });

    it('handles complex summaryIds', () => {
      const { result } = renderHook(() =>
        useSummaryExpansion({ summaryId: 'daily-2024-01-18-456' })
      );

      act(() => {
        result.current.setExpanded(true);
      });

      expect(sessionStorage.getItem('summary-expansion-daily-2024-01-18-456')).toBe('true');
    });
  });

  describe('error handling', () => {
    it('handles sessionStorage errors gracefully on read', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const getItemSpy = vi.spyOn(Storage.prototype, 'getItem');
      getItemSpy.mockImplementation(() => {
        throw new Error('Storage error');
      });

      const { result } = renderHook(() =>
        useSummaryExpansion({ summaryId: 'test-1', defaultExpanded: true })
      );

      // Should fall back to defaultExpanded
      expect(result.current.isExpanded).toBe(true);
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
      getItemSpy.mockRestore();
    });

    it('handles sessionStorage errors gracefully on write', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');
      setItemSpy.mockImplementation(() => {
        throw new Error('Storage error');
      });

      const { result } = renderHook(() => useSummaryExpansion({ summaryId: 'test-1' }));

      // Should still update state even if storage fails
      act(() => {
        result.current.toggle();
      });

      expect(result.current.isExpanded).toBe(true);
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
      setItemSpy.mockRestore();
    });

    it('handles sessionStorage errors gracefully on clear', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem');
      removeItemSpy.mockImplementation(() => {
        throw new Error('Storage error');
      });

      const { result } = renderHook(() => useSummaryExpansion({ summaryId: 'test-1' }));

      // Should not throw
      act(() => {
        result.current.clearStorage();
      });

      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
      removeItemSpy.mockRestore();
    });
  });

  describe('multiple instances', () => {
    it('maintains independent state for different summaryIds', () => {
      const { result: result1 } = renderHook(() => useSummaryExpansion({ summaryId: 'test-1' }));

      const { result: result2 } = renderHook(() => useSummaryExpansion({ summaryId: 'test-2' }));

      act(() => {
        result1.current.setExpanded(true);
      });

      expect(result1.current.isExpanded).toBe(true);
      expect(result2.current.isExpanded).toBe(false);
    });

    it('shares state for same summaryId across instances', () => {
      sessionStorage.setItem('summary-expansion-test-1', 'true');

      const { result: result1 } = renderHook(() => useSummaryExpansion({ summaryId: 'test-1' }));

      const { result: result2 } = renderHook(() => useSummaryExpansion({ summaryId: 'test-1' }));

      expect(result1.current.isExpanded).toBe(true);
      expect(result2.current.isExpanded).toBe(true);
    });
  });
});
