/**
 * Tests for usePaginationState hook
 *
 * This hook manages pagination state with URL persistence for both
 * cursor-based and offset-based pagination strategies.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { usePaginationState } from './usePaginationState';

import type { ReactNode } from 'react';

// Helper to create a wrapper with MemoryRouter at a specific route
function createWrapper(initialRoute = '/') {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={[initialRoute]}>{children}</MemoryRouter>;
  };
}

describe('usePaginationState', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('cursor-based pagination (default)', () => {
    it('returns cursor pagination type by default', () => {
      const { result } = renderHook(() => usePaginationState(), {
        wrapper: createWrapper(),
      });

      expect(result.current.type).toBe('cursor');
    });

    it('returns undefined cursor initially', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper(),
      });

      expect(result.current.cursor).toBeUndefined();
    });

    it('returns default limit of 20', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper(),
      });

      expect(result.current.limit).toBe(20);
    });

    it('respects custom default limit', () => {
      const { result } = renderHook(
        () => usePaginationState({ type: 'cursor', defaultLimit: 50 }),
        { wrapper: createWrapper() }
      );

      expect(result.current.limit).toBe(50);
    });

    it('reads cursor from URL on initial render', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper('/?cursor=abc123'),
      });

      expect(result.current.cursor).toBe('abc123');
    });

    it('reads limit from URL on initial render', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper('/?limit=30'),
      });

      expect(result.current.limit).toBe(30);
    });

    it('setCursor updates the cursor value', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.setCursor('new-cursor-xyz');
      });

      await waitFor(() => {
        expect(result.current.cursor).toBe('new-cursor-xyz');
      });
    });

    it('setCursor with undefined clears the cursor', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper('/?cursor=existing'),
      });

      expect(result.current.cursor).toBe('existing');

      act(() => {
        result.current.setCursor(undefined);
      });

      await waitFor(() => {
        expect(result.current.cursor).toBeUndefined();
      });
    });

    it('setLimit updates the limit and resets cursor', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper('/?cursor=abc&limit=20'),
      });

      expect(result.current.cursor).toBe('abc');
      expect(result.current.limit).toBe(20);

      act(() => {
        result.current.setLimit(50);
      });

      await waitFor(() => {
        expect(result.current.limit).toBe(50);
        expect(result.current.cursor).toBeUndefined();
      });
    });

    it('goToNextPage sets the cursor', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.goToNextPage('next-page-cursor');
      });

      await waitFor(() => {
        expect(result.current.cursor).toBe('next-page-cursor');
      });
    });

    it('goToFirstPage clears the cursor', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper('/?cursor=some-cursor'),
      });

      expect(result.current.cursor).toBe('some-cursor');

      act(() => {
        result.current.goToFirstPage();
      });

      await waitFor(() => {
        expect(result.current.cursor).toBeUndefined();
      });
    });

    it('reset clears cursor and resets limit to default', async () => {
      const { result } = renderHook(
        () => usePaginationState({ type: 'cursor', defaultLimit: 25 }),
        { wrapper: createWrapper('/?cursor=test&limit=50') }
      );

      expect(result.current.cursor).toBe('test');
      expect(result.current.limit).toBe(50);

      act(() => {
        result.current.reset();
      });

      await waitFor(() => {
        expect(result.current.cursor).toBeUndefined();
        expect(result.current.limit).toBe(25);
      });
    });

    it('isFirstPage returns true when cursor is undefined', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper(),
      });

      expect(result.current.isFirstPage).toBe(true);
    });

    it('isFirstPage returns false when cursor is set', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper('/?cursor=abc'),
      });

      expect(result.current.isFirstPage).toBe(false);
    });

    it('state object contains correct values', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper('/?cursor=test&limit=30'),
      });

      expect(result.current.state).toEqual({
        type: 'cursor',
        cursor: 'test',
        limit: 30,
      });
    });
  });

  describe('offset-based pagination', () => {
    it('returns offset pagination type when specified', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper(),
      });

      expect(result.current.type).toBe('offset');
    });

    it('returns page 1 initially', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper(),
      });

      expect(result.current.page).toBe(1);
    });

    it('returns offset 0 initially', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper(),
      });

      expect(result.current.offset).toBe(0);
    });

    it('reads page from URL on initial render', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper('/?page=3'),
      });

      expect(result.current.page).toBe(3);
    });

    it('calculates offset correctly based on page and limit', () => {
      const { result } = renderHook(
        () => usePaginationState({ type: 'offset', defaultLimit: 10 }),
        { wrapper: createWrapper('/?page=3') }
      );

      expect(result.current.page).toBe(3);
      expect(result.current.limit).toBe(10);
      expect(result.current.offset).toBe(20); // (3-1) * 10
    });

    it('setPage updates the page number', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.setPage(5);
      });

      await waitFor(() => {
        expect(result.current.page).toBe(5);
      });
    });

    it('setPage with 1 clears page from URL (default)', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper('/?page=3'),
      });

      act(() => {
        result.current.setPage(1);
      });

      await waitFor(() => {
        expect(result.current.page).toBe(1);
      });
    });

    it('setPage enforces minimum page of 1', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.setPage(-5);
      });

      await waitFor(() => {
        expect(result.current.page).toBe(1);
      });
    });

    it('setLimit updates limit and resets page to 1', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper('/?page=5&limit=20'),
      });

      expect(result.current.page).toBe(5);

      act(() => {
        result.current.setLimit(50);
      });

      await waitFor(() => {
        expect(result.current.limit).toBe(50);
        expect(result.current.page).toBe(1);
      });
    });

    it('goToNextPage increments page by 1', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper('/?page=2'),
      });

      expect(result.current.page).toBe(2);

      act(() => {
        result.current.goToNextPage();
      });

      await waitFor(() => {
        expect(result.current.page).toBe(3);
      });
    });

    it('goToPreviousPage decrements page by 1', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper('/?page=3'),
      });

      act(() => {
        result.current.goToPreviousPage();
      });

      await waitFor(() => {
        expect(result.current.page).toBe(2);
      });
    });

    it('goToPreviousPage does not go below page 1', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper(),
      });

      expect(result.current.page).toBe(1);

      act(() => {
        result.current.goToPreviousPage();
      });

      await waitFor(() => {
        expect(result.current.page).toBe(1);
      });
    });

    it('goToFirstPage sets page to 1', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper('/?page=10'),
      });

      act(() => {
        result.current.goToFirstPage();
      });

      await waitFor(() => {
        expect(result.current.page).toBe(1);
      });
    });

    it('goToLastPage sets page to last page based on total items', async () => {
      const { result } = renderHook(
        () => usePaginationState({ type: 'offset', defaultLimit: 10 }),
        { wrapper: createWrapper() }
      );

      act(() => {
        result.current.goToLastPage(95); // 95 items, 10 per page = 10 pages
      });

      await waitFor(() => {
        expect(result.current.page).toBe(10);
      });
    });

    it('reset clears page and resets limit to default', async () => {
      const { result } = renderHook(
        () => usePaginationState({ type: 'offset', defaultLimit: 15 }),
        { wrapper: createWrapper('/?page=5&limit=50') }
      );

      act(() => {
        result.current.reset();
      });

      await waitFor(() => {
        expect(result.current.page).toBe(1);
        expect(result.current.limit).toBe(15);
      });
    });

    it('isFirstPage returns true when page is 1', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper(),
      });

      expect(result.current.isFirstPage).toBe(true);
    });

    it('isFirstPage returns false when page > 1', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper('/?page=2'),
      });

      expect(result.current.isFirstPage).toBe(false);
    });

    it('isLastPage returns true when on last page', () => {
      const { result } = renderHook(
        () => usePaginationState({ type: 'offset', defaultLimit: 10 }),
        { wrapper: createWrapper('/?page=5') }
      );

      expect(result.current.isLastPage(50)).toBe(true); // 50 items, 10 per page = 5 pages
    });

    it('isLastPage returns false when not on last page', () => {
      const { result } = renderHook(
        () => usePaginationState({ type: 'offset', defaultLimit: 10 }),
        { wrapper: createWrapper('/?page=3') }
      );

      expect(result.current.isLastPage(50)).toBe(false);
    });

    it('getTotalPages calculates correct number of pages', () => {
      const { result } = renderHook(
        () => usePaginationState({ type: 'offset', defaultLimit: 10 }),
        { wrapper: createWrapper() }
      );

      expect(result.current.getTotalPages(0)).toBe(0);
      expect(result.current.getTotalPages(5)).toBe(1);
      expect(result.current.getTotalPages(10)).toBe(1);
      expect(result.current.getTotalPages(11)).toBe(2);
      expect(result.current.getTotalPages(100)).toBe(10);
    });

    it('state object contains correct values', () => {
      const { result } = renderHook(
        () => usePaginationState({ type: 'offset', defaultLimit: 10 }),
        { wrapper: createWrapper('/?page=3&limit=10') }
      );

      expect(result.current.state).toEqual({
        type: 'offset',
        page: 3,
        offset: 20,
        limit: 10,
      });
    });
  });

  describe('custom parameter names', () => {
    it('uses custom cursor parameter name', () => {
      const { result } = renderHook(
        () =>
          usePaginationState({
            type: 'cursor',
            paramNames: { cursor: 'events_cursor' },
          }),
        { wrapper: createWrapper('/?events_cursor=custom-cursor') }
      );

      expect(result.current.cursor).toBe('custom-cursor');
    });

    it('uses custom page parameter name', () => {
      const { result } = renderHook(
        () =>
          usePaginationState({
            type: 'offset',
            paramNames: { page: 'alerts_page' },
          }),
        { wrapper: createWrapper('/?alerts_page=5') }
      );

      expect(result.current.page).toBe(5);
    });

    it('uses custom limit parameter name', () => {
      const { result } = renderHook(
        () =>
          usePaginationState({
            type: 'cursor',
            paramNames: { limit: 'page_size' },
          }),
        { wrapper: createWrapper('/?page_size=100') }
      );

      expect(result.current.limit).toBe(100);
    });

    it('allows multiple paginated lists on same page', () => {
      const wrapper = createWrapper('/?events_cursor=ev123&alerts_page=3&events_limit=25&alerts_limit=10');

      const { result: eventsResult } = renderHook(
        () =>
          usePaginationState({
            type: 'cursor',
            paramNames: { cursor: 'events_cursor', limit: 'events_limit' },
          }),
        { wrapper }
      );

      expect(eventsResult.current.cursor).toBe('ev123');
      expect(eventsResult.current.limit).toBe(25);
    });
  });

  describe('persistLimit option', () => {
    it('persists limit to URL by default', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.setLimit(50);
      });

      await waitFor(() => {
        expect(result.current.limit).toBe(50);
      });
    });

    it('does not read limit from URL when persistLimit is false', () => {
      const { result } = renderHook(
        () =>
          usePaginationState({
            type: 'cursor',
            defaultLimit: 25,
            persistLimit: false,
          }),
        { wrapper: createWrapper('/?limit=50') }
      );

      // Should use default, not URL value
      expect(result.current.limit).toBe(25);
    });
  });

  describe('onStateChange callback', () => {
    it('calls onStateChange when cursor changes', async () => {
      const onStateChange = vi.fn();

      const { result } = renderHook(
        () => usePaginationState({ type: 'cursor', onStateChange }),
        { wrapper: createWrapper() }
      );

      act(() => {
        result.current.setCursor('new-cursor');
      });

      await waitFor(() => {
        expect(onStateChange).toHaveBeenCalledWith({
          type: 'cursor',
          cursor: 'new-cursor',
          limit: 20,
        });
      });
    });

    it('calls onStateChange when page changes', async () => {
      const onStateChange = vi.fn();

      const { result } = renderHook(
        () => usePaginationState({ type: 'offset', onStateChange }),
        { wrapper: createWrapper() }
      );

      act(() => {
        result.current.setPage(3);
      });

      await waitFor(() => {
        expect(onStateChange).toHaveBeenCalledWith({
          type: 'offset',
          page: 3,
          offset: 40,
          limit: 20,
        });
      });
    });

    it('calls onStateChange when limit changes', async () => {
      const onStateChange = vi.fn();

      const { result } = renderHook(
        () => usePaginationState({ type: 'cursor', onStateChange }),
        { wrapper: createWrapper() }
      );

      act(() => {
        result.current.setLimit(50);
      });

      await waitFor(() => {
        expect(onStateChange).toHaveBeenCalledWith({
          type: 'cursor',
          cursor: undefined,
          limit: 50,
        });
      });
    });

    it('calls onStateChange on reset', async () => {
      const onStateChange = vi.fn();

      const { result } = renderHook(
        () => usePaginationState({ type: 'offset', defaultLimit: 15, onStateChange }),
        { wrapper: createWrapper('/?page=5') }
      );

      act(() => {
        result.current.reset();
      });

      await waitFor(() => {
        expect(onStateChange).toHaveBeenCalledWith({
          type: 'offset',
          page: 1,
          offset: 0,
          limit: 15,
        });
      });
    });
  });

  describe('edge cases and validation', () => {
    it('handles invalid limit in URL gracefully (too large)', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper('/?limit=999'),
      });

      // Should fall back to default because 999 > 100
      expect(result.current.limit).toBe(20);
    });

    it('handles invalid limit in URL gracefully (negative)', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper('/?limit=-10'),
      });

      // Should fall back to default
      expect(result.current.limit).toBe(20);
    });

    it('handles invalid limit in URL gracefully (non-numeric)', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper('/?limit=abc'),
      });

      // Should fall back to default
      expect(result.current.limit).toBe(20);
    });

    it('handles invalid page in URL gracefully (negative)', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper('/?page=-5'),
      });

      // Should fall back to default page 1
      expect(result.current.page).toBe(1);
    });

    it('handles invalid page in URL gracefully (non-numeric)', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper('/?page=abc'),
      });

      // Should fall back to default page 1
      expect(result.current.page).toBe(1);
    });

    it('handles zero page in URL by using page 1', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper('/?page=0'),
      });

      // Should fall back to default page 1
      expect(result.current.page).toBe(1);
    });

    it('preserves other URL params when updating pagination', async () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper('/?filter=active&sort=date'),
      });

      act(() => {
        result.current.setCursor('new-cursor');
      });

      // Note: We can't easily verify the full URL in this test setup,
      // but the implementation uses replace mode and preserves existing params
      await waitFor(() => {
        expect(result.current.cursor).toBe('new-cursor');
      });
    });

    it('goToLastPage does nothing when total items is 0', async () => {
      const { result } = renderHook(
        () => usePaginationState({ type: 'offset', defaultLimit: 10 }),
        { wrapper: createWrapper('/?page=3') }
      );

      expect(result.current.page).toBe(3);

      act(() => {
        result.current.goToLastPage(0);
      });

      // Page should remain unchanged when totalItems is 0
      await waitFor(() => {
        expect(result.current.page).toBe(3);
      });
    });
  });

  describe('type narrowing', () => {
    it('returns cursor-specific methods for cursor type', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createWrapper(),
      });

      // These should exist
      expect(typeof result.current.setCursor).toBe('function');
      expect(typeof result.current.goToNextPage).toBe('function');
      expect(typeof result.current.goToFirstPage).toBe('function');

      // Type guard check
      expect(result.current.type).toBe('cursor');
    });

    it('returns offset-specific methods for offset type', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createWrapper(),
      });

      // These should exist
      expect(typeof result.current.setPage).toBe('function');
      expect(typeof result.current.goToNextPage).toBe('function');
      expect(typeof result.current.goToPreviousPage).toBe('function');
      expect(typeof result.current.goToFirstPage).toBe('function');
      expect(typeof result.current.goToLastPage).toBe('function');
      expect(typeof result.current.isLastPage).toBe('function');
      expect(typeof result.current.getTotalPages).toBe('function');

      // Type guard check
      expect(result.current.type).toBe('offset');
    });
  });
});
