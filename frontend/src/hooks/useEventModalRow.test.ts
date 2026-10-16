/**
 * Unit tests for `useEventModalRow` / `useEventWriteInvalidation`.
 *
 * The defect these pin is a lookup, not a render: `EventTimeline` resolved its
 * selected id against the BROWSE list only, so a selection made by the search
 * panel, the live feed, or a `?event=<id>` deep link could name a row no loaded
 * page holds, and the modal stayed empty over an open dialog. So the tests here
 * are about WHICH row comes back and WHAT requests it costs:
 *
 *  - a browse hit is returned unchanged and issues no request at all (the
 *    no-regression half: browse-mode clicks keep their old request count);
 *  - a miss is completed by `GET /api/events/{id}`, once, for that id;
 *  - a fetched row is dropped on close, because the modal's flag/notes/reviewed
 *    writes report success against it while the cache under it holds the
 *    pre-write row;
 *  - a write invalidation reaches every event cache, because `all` is `['events']`
 *    and all of them register under it. The easy claim to fake is the KEY shape:
 *    `lists()` looks plausible but is not a prefix of the infinite browse key, so
 *    the negative control pins that and a companion test proves an actual refetch.
 */
import { QueryClient, useQuery } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useEventModalRow, useEventWriteInvalidation } from './useEventModalRow';
import { eventsQueryKeys } from './useEventsQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { Event } from '../types/generated';

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    fetchEvent: vi.fn(),
  };
});

const mockedFetchEvent = vi.mocked(api.fetchEvent);

/** A row with every `EventResponse` field the generated type requires. */
function makeEvent(id: number, summary = `row ${id}`): Event {
  return {
    id,
    camera_id: 'front_door',
    started_at: '2026-10-16T09:00:00Z',
    ended_at: '2026-10-16T09:01:00Z',
    risk_score: 75,
    risk_level: 'high',
    summary,
    reasoning: 'Motion detected with high confidence',
    reviewed: false,
    flagged: false,
    notes: null,
    detection_count: 1,
    detection_ids: [id * 10],
    version: 3,
  };
}

/**
 * A client of our own, so `discard` and the invalidation can be read back from
 * the cache instead of inferred from what the hook returns.
 */
let queryClient: QueryClient;

function renderRow(eventId: number | null, browseEvents: readonly Event[]) {
  return renderHook(() => useEventModalRow(eventId, browseEvents), {
    wrapper: createQueryWrapper(queryClient),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
});

afterEach(() => {
  queryClient.clear();
});

describe('useEventModalRow', () => {
  it('returns the browse row and issues no request when the browse list holds the id', () => {
    const row = makeEvent(7);

    const { result } = renderRow(7, [row]);

    // Identity, not equality: the timeline hands this to an effect, and a
    // re-derived object would re-run it.
    expect(result.current.row).toBe(row);
    expect(mockedFetchEvent).not.toHaveBeenCalled();
  });

  it('completes the lookup with GET /api/events/{id} when the browse list lacks the id', async () => {
    const fetched = makeEvent(42, 'a search result no browse page fetched');
    mockedFetchEvent.mockResolvedValue(fetched);

    const { result } = renderRow(42, []);

    expect(result.current.row).toBeNull();
    await waitFor(() => expect(result.current.row).toBe(fetched));
    expect(mockedFetchEvent).toHaveBeenCalledTimes(1);
    expect(mockedFetchEvent).toHaveBeenCalledWith(42);
  });

  it('fetches nothing at all while no row is selected', () => {
    const { result } = renderRow(null, []);

    expect(result.current.row).toBeNull();
    expect(mockedFetchEvent).not.toHaveBeenCalled();
  });

  it('prefers the browse copy over a cached fetch for the same id', () => {
    const browseRow = makeEvent(9, 'browse copy');
    const cachedCopy = makeEvent(9, 'stale detail copy');
    queryClient.setQueryData(eventsQueryKeys.detail(9), cachedCopy);

    const { result } = renderRow(9, [browseRow]);

    expect(result.current.row).toBe(browseRow);
    expect(mockedFetchEvent).not.toHaveBeenCalled();
  });

  it('discards only the fetched detail entry so the next open re-reads', async () => {
    const fetched = makeEvent(42, 'written to while the modal was open');
    mockedFetchEvent.mockResolvedValue(fetched);

    const { result } = renderRow(42, []);
    await waitFor(() => expect(result.current.row).toBe(fetched));
    expect(queryClient.getQueryData(eventsQueryKeys.detail(42))).toBe(fetched);

    result.current.discard();

    expect(queryClient.getQueryData(eventsQueryKeys.detail(42))).toBeUndefined();
  });

  it('keeps a stable discard identity across re-renders', () => {
    const browseRow = makeEvent(7);
    const { result, rerender } = renderRow(7, [browseRow]);
    const first = result.current.discard;

    rerender();

    // The timeline keys an effect on this, so a fresh arrow every render would
    // re-run that effect indefinitely.
    expect(result.current.discard).toBe(first);
  });

  it('makes discard a no-op when no row is selected', () => {
    queryClient.setQueryData(eventsQueryKeys.detail(5), makeEvent(5));
    const { result } = renderRow(null, []);

    expect(() => result.current.discard()).not.toThrow();
    // An id-less close must not blank out rows another surface is showing.
    expect(queryClient.getQueryData(eventsQueryKeys.detail(5))).toBeDefined();
  });
});

describe('useEventWriteInvalidation', () => {
  const infiniteKey = eventsQueryKeys.infinite({ camera_id: 'front_door' }, 25);

  it('refetches the live browse query — the behaviour a stale flag alone would not prove', async () => {
    const browseFetch = vi.fn(() => Promise.resolve({ items: [], next_cursor: null }));
    const probe = renderHook(() => useQuery({ queryKey: infiniteKey, queryFn: browseFetch }), {
      wrapper: createQueryWrapper(queryClient),
    });
    await waitFor(() => expect(probe.result.current.isSuccess).toBe(true));
    expect(browseFetch).toHaveBeenCalledTimes(1);

    const { result } = renderHook(() => useEventWriteInvalidation(), {
      wrapper: createQueryWrapper(queryClient),
    });
    result.current();

    // The synchronously-set flag: invalidate() marks it before any refetch.
    const marked = queryClient.getQueryCache().find({ queryKey: infiniteKey });
    expect(marked?.state.isInvalidated).toBe(true);

    // And the claim behind the flag: a write to ONE event refreshes the browse
    // list the user is looking at. `lists()` would leave this at 1 call.
    await waitFor(() => expect(browseFetch).toHaveBeenCalledTimes(2));
  });

  it('would MISS the browse query if it keyed on lists() — the negative control', () => {
    const listsKey = eventsQueryKeys.lists();

    // Compare SEGMENTS structurally, the way QueryClient does. `join()` is the
    // trap here: the third segment of an infinite key is an object, so
    // String() gives '[object Object]' and both comparisons below would pass
    // for a reason that has nothing to do with the key shape.
    expect(infiniteKey.slice(0, listsKey.length)).not.toEqual(listsKey);
    // And `all` DOES prefix-match it, which is why the product code uses `all`.
    expect(infiniteKey.slice(0, eventsQueryKeys.all.length)).toEqual(eventsQueryKeys.all);
  });
});
