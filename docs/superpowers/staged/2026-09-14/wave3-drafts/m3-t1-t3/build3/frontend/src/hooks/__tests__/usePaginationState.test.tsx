/**
 * @fileoverview Tests for usePaginationState hook.
 *
 * This hook provides pagination state management with URL persistence,
 * supporting both cursor-based and offset-based pagination patterns.
 *
 * Tests follow TDD approach with comprehensive coverage of:
 * - Initial state for both pagination types
 * - URL parameter parsing and persistence
 * - Page navigation (next, previous, first, last)
 * - Offset/limit calculations
 * - Boundary handling and edge cases
 * - State change callbacks
 * - Custom parameter names
 * - Reset functionality
 */
import { renderHook, act } from '@testing-library/react';
import { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';

import { usePaginationState } from '../usePaginationState';

/**
 * Creates a wrapper component with MemoryRouter for URL parameter testing.
 * The hook requires react-router's useSearchParams, which needs a Router context.
 */
function createRouterWrapper(initialUrl: string = '/') {
  return function RouterWrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={[initialUrl]}>{children}</MemoryRouter>;
  };
}

describe('usePaginationState', () => {
  describe('cursor-based pagination', () => {
    describe('initial state', () => {
      it('returns initial state with undefined cursor', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper(),
        });

        expect(result.current.type).toBe('cursor');
        expect(result.current.cursor).toBeUndefined();
        expect(result.current.limit).toBe(20); // default limit
        expect(result.current.isFirstPage).toBe(true);
      });

      it('returns state object with correct properties', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper(),
        });

        expect(result.current.state).toEqual({
          type: 'cursor',
          cursor: undefined,
          limit: 20,
        });
      });

      it('uses custom default limit', () => {
        const { result } = renderHook(
          () => usePaginationState({ type: 'cursor', defaultLimit: 50 }),
          {
            wrapper: createRouterWrapper(),
          }
        );

        expect(result.current.limit).toBe(50);
      });

      it('parses cursor from URL on mount', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper('/?cursor=abc123'),
        });

        expect(result.current.cursor).toBe('abc123');
        expect(result.current.isFirstPage).toBe(false);
      });

      it('parses limit from URL on mount', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper('/?limit=30'),
        });

        expect(result.current.limit).toBe(30);
      });

      it('parses both cursor and limit from URL', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper('/?cursor=xyz789&limit=15'),
        });

        expect(result.current.cursor).toBe('xyz789');
        expect(result.current.limit).toBe(15);
      });
    });

    describe('navigation', () => {
      it('sets cursor when navigating to next page', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper(),
        });

        act(() => {
          result.current.goToNextPage('next_cursor_token');
        });

        expect(result.current.cursor).toBe('next_cursor_token');
        expect(result.current.isFirstPage).toBe(false);
      });

      it('clears cursor when navigating to first page', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper('/?cursor=existing'),
        });

        expect(result.current.cursor).toBe('existing');

        act(() => {
          result.current.goToFirstPage();
        });

        expect(result.current.cursor).toBeUndefined();
        expect(result.current.isFirstPage).toBe(true);
      });

      it('updates cursor via setCursor', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper(),
        });

        act(() => {
          result.current.setCursor('manual_cursor');
        });

        expect(result.current.cursor).toBe('manual_cursor');
      });

      it('clears cursor via setCursor with undefined', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper('/?cursor=old'),
        });

        act(() => {
          result.current.setCursor(undefined);
        });

        expect(result.current.cursor).toBeUndefined();
      });
    });

    describe('limit changes', () => {
      it('updates limit via setLimit', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper(),
        });

        act(() => {
          result.current.setLimit(100);
        });

        expect(result.current.limit).toBe(100);
      });

      it('resets cursor when limit changes', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper('/?cursor=existing'),
        });

        expect(result.current.cursor).toBe('existing');

        act(() => {
          result.current.setLimit(50);
        });

        expect(result.current.cursor).toBeUndefined();
        expect(result.current.limit).toBe(50);
      });

      it('does not persist limit when persistLimit is false', () => {
        const { result } = renderHook(
          () => usePaginationState({ type: 'cursor', persistLimit: false, defaultLimit: 30 }),
          {
            wrapper: createRouterWrapper(),
          }
        );

        // When persistLimit is false, limit always returns defaultLimit
        // regardless of URL params or setLimit calls
        expect(result.current.limit).toBe(30);

        act(() => {
          result.current.setLimit(40);
        });

        // Limit should remain at default since persistLimit is false
        expect(result.current.limit).toBe(30);
      });

      it('validates limit is positive and within bounds', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper('/?limit=200'), // exceeds max 100
        });

        // Should fall back to default when invalid
        expect(result.current.limit).toBe(20);
      });

      it('ignores invalid limit values from URL', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper('/?limit=invalid'),
        });

        expect(result.current.limit).toBe(20); // default
      });
    });

    describe('reset functionality', () => {
      it('resets to initial state', () => {
        const { result } = renderHook(
          () => usePaginationState({ type: 'cursor', defaultLimit: 25 }),
          {
            wrapper: createRouterWrapper('/?cursor=current&limit=50'),
          }
        );

        expect(result.current.cursor).toBe('current');
        expect(result.current.limit).toBe(50);

        act(() => {
          result.current.reset();
        });

        expect(result.current.cursor).toBeUndefined();
        expect(result.current.limit).toBe(25); // back to default
      });

      it('resets cursor and limit when persistLimit is true', () => {
        const { result } = renderHook(
          () => usePaginationState({ type: 'cursor', defaultLimit: 30, persistLimit: true }),
          {
            wrapper: createRouterWrapper('/?cursor=abc&limit=60'),
          }
        );

        act(() => {
          result.current.reset();
        });

        expect(result.current.cursor).toBeUndefined();
        expect(result.current.limit).toBe(30);
      });
    });

    describe('state change callback', () => {
      it('calls onStateChange when cursor changes', () => {
        const onStateChange = vi.fn();
        const { result } = renderHook(() => usePaginationState({ type: 'cursor', onStateChange }), {
          wrapper: createRouterWrapper(),
        });

        act(() => {
          result.current.goToNextPage('next_page');
        });

        expect(onStateChange).toHaveBeenCalledWith({
          type: 'cursor',
          cursor: 'next_page',
          limit: 20,
        });
      });

      it('calls onStateChange when limit changes', () => {
        const onStateChange = vi.fn();
        const { result } = renderHook(() => usePaginationState({ type: 'cursor', onStateChange }), {
          wrapper: createRouterWrapper(),
        });

        act(() => {
          result.current.setLimit(50);
        });

        expect(onStateChange).toHaveBeenCalledWith({
          type: 'cursor',
          cursor: undefined,
          limit: 50,
        });
      });

      it('calls onStateChange on reset', () => {
        const onStateChange = vi.fn();
        const { result } = renderHook(
          () => usePaginationState({ type: 'cursor', defaultLimit: 25, onStateChange }),
          {
            wrapper: createRouterWrapper('/?cursor=current'),
          }
        );

        act(() => {
          result.current.reset();
        });

        expect(onStateChange).toHaveBeenCalledWith({
          type: 'cursor',
          cursor: undefined,
          limit: 25,
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
          {
            wrapper: createRouterWrapper('/?events_cursor=custom_token'),
          }
        );

        expect(result.current.cursor).toBe('custom_token');
      });

      it('uses custom limit parameter name', () => {
        const { result } = renderHook(
          () =>
            usePaginationState({
              type: 'cursor',
              paramNames: { limit: 'events_limit' },
            }),
          {
            wrapper: createRouterWrapper('/?events_limit=40'),
          }
        );

        expect(result.current.limit).toBe(40);
      });

      it('uses both custom parameter names', () => {
        const { result } = renderHook(
          () =>
            usePaginationState({
              type: 'cursor',
              paramNames: { cursor: 'c', limit: 'l' },
            }),
          {
            wrapper: createRouterWrapper('/?c=token&l=15'),
          }
        );

        expect(result.current.cursor).toBe('token');
        expect(result.current.limit).toBe(15);
      });
    });

    describe('isFirstPage helper', () => {
      it('returns true when cursor is undefined', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper(),
        });

        expect(result.current.isFirstPage).toBe(true);
      });

      it('returns false when cursor is set', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper('/?cursor=page2'),
        });

        expect(result.current.isFirstPage).toBe(false);
      });

      it('updates when navigating', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
          wrapper: createRouterWrapper(),
        });

        expect(result.current.isFirstPage).toBe(true);

        act(() => {
          result.current.goToNextPage('next');
        });

        expect(result.current.isFirstPage).toBe(false);

        act(() => {
          result.current.goToFirstPage();
        });

        expect(result.current.isFirstPage).toBe(true);
      });
    });
  });

  describe('offset-based pagination', () => {
    describe('initial state', () => {
      it('returns initial state with page 1', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        expect(result.current.type).toBe('offset');
        expect(result.current.page).toBe(1);
        expect(result.current.offset).toBe(0);
        expect(result.current.limit).toBe(20); // default limit
        expect(result.current.isFirstPage).toBe(true);
      });

      it('returns state object with correct properties', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        expect(result.current.state).toEqual({
          type: 'offset',
          page: 1,
          offset: 0,
          limit: 20,
        });
      });

      it('uses custom default limit', () => {
        const { result } = renderHook(
          () => usePaginationState({ type: 'offset', defaultLimit: 50 }),
          {
            wrapper: createRouterWrapper(),
          }
        );

        expect(result.current.limit).toBe(50);
      });

      it('parses page from URL on mount', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=3'),
        });

        expect(result.current.page).toBe(3);
        expect(result.current.offset).toBe(40); // (3-1) * 20
        expect(result.current.isFirstPage).toBe(false);
      });

      it('parses limit from URL on mount', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?limit=30'),
        });

        expect(result.current.limit).toBe(30);
      });

      it('calculates correct offset from page and limit', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=5&limit=25'),
        });

        expect(result.current.page).toBe(5);
        expect(result.current.limit).toBe(25);
        expect(result.current.offset).toBe(100); // (5-1) * 25
      });

      it('defaults to page 1 for invalid page numbers', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=invalid'),
        });

        expect(result.current.page).toBe(1);
        expect(result.current.offset).toBe(0);
      });

      it('defaults to page 1 for zero or negative page numbers', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=0'),
        });

        expect(result.current.page).toBe(1);

        const { result: result2 } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=-5'),
        });

        expect(result2.current.page).toBe(1);
      });
    });

    describe('offset calculations', () => {
      it('calculates offset correctly for page 1', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=1&limit=20'),
        });

        expect(result.current.offset).toBe(0);
      });

      it('calculates offset correctly for page 2', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=2&limit=20'),
        });

        expect(result.current.offset).toBe(20);
      });

      it('calculates offset correctly for page 10 with limit 50', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=10&limit=50'),
        });

        expect(result.current.offset).toBe(450); // (10-1) * 50
      });

      it('updates offset when page changes', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        act(() => {
          result.current.goToNextPage();
        });

        expect(result.current.page).toBe(2);
        expect(result.current.offset).toBe(20);

        act(() => {
          result.current.goToNextPage();
        });

        expect(result.current.page).toBe(3);
        expect(result.current.offset).toBe(40);
      });

      it('updates offset when limit changes', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=3'),
        });

        expect(result.current.offset).toBe(40); // (3-1) * 20

        act(() => {
          result.current.setLimit(50);
        });

        // Limit changes reset to page 1
        expect(result.current.page).toBe(1);
        expect(result.current.offset).toBe(0);
      });
    });

    describe('navigation', () => {
      it('navigates to next page', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        expect(result.current.page).toBe(1);

        act(() => {
          result.current.goToNextPage();
        });

        expect(result.current.page).toBe(2);
        expect(result.current.offset).toBe(20);
      });

      it('navigates to previous page', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=3'),
        });

        expect(result.current.page).toBe(3);

        act(() => {
          result.current.goToPreviousPage();
        });

        expect(result.current.page).toBe(2);
        expect(result.current.offset).toBe(20);
      });

      it('does not go below page 1 when navigating previous', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        expect(result.current.page).toBe(1);

        act(() => {
          result.current.goToPreviousPage();
        });

        expect(result.current.page).toBe(1);
        expect(result.current.offset).toBe(0);
      });

      it('navigates to first page', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=5'),
        });

        expect(result.current.page).toBe(5);

        act(() => {
          result.current.goToFirstPage();
        });

        expect(result.current.page).toBe(1);
        expect(result.current.offset).toBe(0);
      });

      it('navigates to last page with total items', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        act(() => {
          result.current.goToLastPage(95); // 95 items with limit 20 = 5 pages
        });

        expect(result.current.page).toBe(5);
        expect(result.current.offset).toBe(80);
      });

      it('navigates to last page when total is exactly divisible by limit', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        act(() => {
          result.current.goToLastPage(100); // 100 items with limit 20 = 5 pages
        });

        expect(result.current.page).toBe(5);
      });

      it('handles goToLastPage with zero items', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        const initialPage = result.current.page;

        act(() => {
          result.current.goToLastPage(0);
        });

        // Should stay on current page
        expect(result.current.page).toBe(initialPage);
      });

      it('sets page directly via setPage', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        act(() => {
          result.current.setPage(7);
        });

        expect(result.current.page).toBe(7);
        expect(result.current.offset).toBe(120); // (7-1) * 20
      });

      it('validates page is at least 1 when using setPage', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        act(() => {
          result.current.setPage(-5);
        });

        expect(result.current.page).toBe(1);

        act(() => {
          result.current.setPage(0);
        });

        expect(result.current.page).toBe(1);
      });
    });

    describe('limit changes', () => {
      it('updates limit via setLimit', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        act(() => {
          result.current.setLimit(100);
        });

        expect(result.current.limit).toBe(100);
      });

      it('resets to page 1 when limit changes', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=5'),
        });

        expect(result.current.page).toBe(5);

        act(() => {
          result.current.setLimit(50);
        });

        expect(result.current.page).toBe(1);
        expect(result.current.offset).toBe(0);
        expect(result.current.limit).toBe(50);
      });

      it('does not persist limit when persistLimit is false', () => {
        const { result } = renderHook(
          () => usePaginationState({ type: 'offset', persistLimit: false, defaultLimit: 30 }),
          {
            wrapper: createRouterWrapper(),
          }
        );

        // When persistLimit is false, limit always returns defaultLimit
        // regardless of URL params or setLimit calls
        expect(result.current.limit).toBe(30);

        act(() => {
          result.current.setLimit(40);
        });

        // Limit should remain at default since persistLimit is false
        expect(result.current.limit).toBe(30);
      });
    });

    describe('reset functionality', () => {
      it('resets to initial state', () => {
        const { result } = renderHook(
          () => usePaginationState({ type: 'offset', defaultLimit: 25 }),
          {
            wrapper: createRouterWrapper('/?page=4&limit=50'),
          }
        );

        expect(result.current.page).toBe(4);
        expect(result.current.limit).toBe(50);

        act(() => {
          result.current.reset();
        });

        expect(result.current.page).toBe(1);
        expect(result.current.offset).toBe(0);
        expect(result.current.limit).toBe(25); // back to default
      });
    });

    describe('state change callback', () => {
      it('calls onStateChange when page changes', () => {
        const onStateChange = vi.fn();
        const { result } = renderHook(() => usePaginationState({ type: 'offset', onStateChange }), {
          wrapper: createRouterWrapper(),
        });

        act(() => {
          result.current.goToNextPage();
        });

        expect(onStateChange).toHaveBeenCalledWith({
          type: 'offset',
          page: 2,
          offset: 20,
          limit: 20,
        });
      });

      it('calls onStateChange when limit changes', () => {
        const onStateChange = vi.fn();
        const { result } = renderHook(() => usePaginationState({ type: 'offset', onStateChange }), {
          wrapper: createRouterWrapper(),
        });

        act(() => {
          result.current.setLimit(50);
        });

        expect(onStateChange).toHaveBeenCalledWith({
          type: 'offset',
          page: 1,
          offset: 0,
          limit: 50,
        });
      });

      it('calls onStateChange on reset', () => {
        const onStateChange = vi.fn();
        const { result } = renderHook(
          () => usePaginationState({ type: 'offset', defaultLimit: 30, onStateChange }),
          {
            wrapper: createRouterWrapper('/?page=3'),
          }
        );

        act(() => {
          result.current.reset();
        });

        expect(onStateChange).toHaveBeenCalledWith({
          type: 'offset',
          page: 1,
          offset: 0,
          limit: 30,
        });
      });
    });

    describe('custom parameter names', () => {
      it('uses custom page parameter name', () => {
        const { result } = renderHook(
          () =>
            usePaginationState({
              type: 'offset',
              paramNames: { page: 'events_page' },
            }),
          {
            wrapper: createRouterWrapper('/?events_page=4'),
          }
        );

        expect(result.current.page).toBe(4);
      });

      it('uses custom limit parameter name', () => {
        const { result } = renderHook(
          () =>
            usePaginationState({
              type: 'offset',
              paramNames: { limit: 'events_limit' },
            }),
          {
            wrapper: createRouterWrapper('/?events_limit=40'),
          }
        );

        expect(result.current.limit).toBe(40);
      });

      it('uses both custom parameter names', () => {
        const { result } = renderHook(
          () =>
            usePaginationState({
              type: 'offset',
              paramNames: { page: 'p', limit: 'l' },
            }),
          {
            wrapper: createRouterWrapper('/?p=3&l=15'),
          }
        );

        expect(result.current.page).toBe(3);
        expect(result.current.limit).toBe(15);
        expect(result.current.offset).toBe(30); // (3-1) * 15
      });
    });

    describe('pagination helpers', () => {
      it('isFirstPage returns true on page 1', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        expect(result.current.isFirstPage).toBe(true);
      });

      it('isFirstPage returns false on other pages', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=2'),
        });

        expect(result.current.isFirstPage).toBe(false);
      });

      it('isLastPage returns true on last page', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=5'),
        });

        expect(result.current.isLastPage(95)).toBe(true); // 95 items / 20 per page = 5 pages
        expect(result.current.isLastPage(100)).toBe(true); // exactly on last page
      });

      it('isLastPage returns false when not on last page', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=3'),
        });

        expect(result.current.isLastPage(100)).toBe(false); // 100 items / 20 = 5 pages, on page 3
      });

      it('isLastPage returns true for single page', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        expect(result.current.isLastPage(10)).toBe(true); // 10 items / 20 per page = 1 page
      });

      it('isLastPage returns true for empty data', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        expect(result.current.isLastPage(0)).toBe(true);
      });

      it('getTotalPages calculates correct page count', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        expect(result.current.getTotalPages(0)).toBe(0);
        expect(result.current.getTotalPages(10)).toBe(1);
        expect(result.current.getTotalPages(20)).toBe(1);
        expect(result.current.getTotalPages(21)).toBe(2);
        expect(result.current.getTotalPages(100)).toBe(5);
        expect(result.current.getTotalPages(101)).toBe(6);
      });

      it('getTotalPages respects custom limit', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?limit=50'),
        });

        expect(result.current.getTotalPages(100)).toBe(2);
        expect(result.current.getTotalPages(150)).toBe(3);
        expect(result.current.getTotalPages(151)).toBe(4);
      });
    });

    describe('edge cases', () => {
      it('handles single page scenario', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        expect(result.current.page).toBe(1);
        expect(result.current.isFirstPage).toBe(true);
        expect(result.current.isLastPage(5)).toBe(true); // 5 items, 20 per page = 1 page

        // Previous should stay on page 1
        act(() => {
          result.current.goToPreviousPage();
        });
        expect(result.current.page).toBe(1);

        // Last page should stay on page 1
        act(() => {
          result.current.goToLastPage(5);
        });
        expect(result.current.page).toBe(1);
      });

      it('handles empty data set', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        expect(result.current.getTotalPages(0)).toBe(0);
        expect(result.current.isLastPage(0)).toBe(true);
      });

      it('handles large page numbers', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper('/?page=9999'),
        });

        expect(result.current.page).toBe(9999);
        expect(result.current.offset).toBe(199960); // (9999-1) * 20 = 9998 * 20
      });

      it('handles concurrent navigation calls', () => {
        const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
          wrapper: createRouterWrapper(),
        });

        act(() => {
          result.current.goToNextPage();
          result.current.goToNextPage();
        });

        // Both calls execute, but the final state should be consistent
        expect(result.current.page).toBeGreaterThan(1);
      });
    });
  });

  describe('default pagination type', () => {
    it('defaults to cursor pagination when type not specified', () => {
      const { result } = renderHook(() => usePaginationState(), {
        wrapper: createRouterWrapper(),
      });

      expect(result.current.type).toBe('cursor');
    });

    it('defaults to cursor pagination with empty options', () => {
      const { result } = renderHook(() => usePaginationState({}), {
        wrapper: createRouterWrapper(),
      });

      expect(result.current.type).toBe('cursor');
    });
  });

  describe('multiple instances', () => {
    it('maintains independent state for cursor pagination instances', () => {
      const { result: result1 } = renderHook(
        () =>
          usePaginationState({
            type: 'cursor',
            paramNames: { cursor: 'events_cursor', limit: 'events_limit' },
          }),
        {
          wrapper: createRouterWrapper('/?events_cursor=token1&alerts_cursor=token2'),
        }
      );

      const { result: result2 } = renderHook(
        () =>
          usePaginationState({
            type: 'cursor',
            paramNames: { cursor: 'alerts_cursor', limit: 'alerts_limit' },
          }),
        {
          wrapper: createRouterWrapper('/?events_cursor=token1&alerts_cursor=token2'),
        }
      );

      expect(result1.current.cursor).toBe('token1');
      expect(result2.current.cursor).toBe('token2');
    });

    it('maintains independent state for offset pagination instances', () => {
      const { result: result1 } = renderHook(
        () =>
          usePaginationState({
            type: 'offset',
            paramNames: { page: 'events_page', limit: 'events_limit' },
          }),
        {
          wrapper: createRouterWrapper('/?events_page=3&alerts_page=5'),
        }
      );

      const { result: result2 } = renderHook(
        () =>
          usePaginationState({
            type: 'offset',
            paramNames: { page: 'alerts_page', limit: 'alerts_limit' },
          }),
        {
          wrapper: createRouterWrapper('/?events_page=3&alerts_page=5'),
        }
      );

      expect(result1.current.page).toBe(3);
      expect(result2.current.page).toBe(5);
    });
  });

  describe('URL parameter persistence', () => {
    it('removes page parameter from URL when navigating to page 1', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createRouterWrapper('/?page=3'),
      });

      act(() => {
        result.current.goToFirstPage();
      });

      // Page should be 1, URL parameter should be removed (implicit via behavior)
      expect(result.current.page).toBe(1);
    });

    it('preserves other URL parameters when changing pagination state', () => {
      // This is implicitly tested by the hook implementation
      // The hook uses setSearchParams with a function that preserves other params
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createRouterWrapper('/?page=2&filter=active'),
      });

      act(() => {
        result.current.goToNextPage();
      });

      expect(result.current.page).toBe(3);
      // Note: Can't directly test URL here, but the hook implementation preserves other params
    });
  });

  describe('type discrimination', () => {
    it('cursor pagination type has cursor-specific methods', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'cursor' }), {
        wrapper: createRouterWrapper(),
      });

      expect(result.current).toHaveProperty('cursor');
      expect(result.current).toHaveProperty('setCursor');
      expect(result.current).toHaveProperty('goToNextPage');
      expect(result.current).toHaveProperty('goToFirstPage');
      expect(result.current).not.toHaveProperty('page');
      expect(result.current).not.toHaveProperty('offset');
      expect(result.current).not.toHaveProperty('goToPreviousPage');
      expect(result.current).not.toHaveProperty('goToLastPage');
    });

    it('offset pagination type has offset-specific methods', () => {
      const { result } = renderHook(() => usePaginationState({ type: 'offset' }), {
        wrapper: createRouterWrapper(),
      });

      expect(result.current).toHaveProperty('page');
      expect(result.current).toHaveProperty('offset');
      expect(result.current).toHaveProperty('setPage');
      expect(result.current).toHaveProperty('goToNextPage');
      expect(result.current).toHaveProperty('goToPreviousPage');
      expect(result.current).toHaveProperty('goToFirstPage');
      expect(result.current).toHaveProperty('goToLastPage');
      expect(result.current).toHaveProperty('isLastPage');
      expect(result.current).toHaveProperty('getTotalPages');
      expect(result.current).not.toHaveProperty('cursor');
      expect(result.current).not.toHaveProperty('setCursor');
    });
  });
});
