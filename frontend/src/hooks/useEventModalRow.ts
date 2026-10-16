/**
 * useEventModalRow — the row the event modal renders, resolved by id.
 *
 * `EventTimeline` used to resolve its selected id against the BROWSE list alone.
 * That is only sound for a click that came out of the browse list: the other
 * surfaces that set the selection — the search panel (which paginates
 * server-side, so it advertises rows the loaded browse pages never fetched),
 * the live-activity feed, and a `?event=<id>` deep link — can name a row the
 * browse cache does not hold, and the modal then rendered nothing over an open
 * dialog. `GET /api/events/{id}` already serves that row, so the lookup is
 * completed with that request instead of leaving the click dead.
 *
 * The browse list stays the first choice, not the fallback: its items and the
 * detail route share the generated `EventResponse` type, so a browse hit is
 * returned unchanged and no browse-mode click issues a request it didn't used
 * to. Only a miss fetches.
 *
 * The key comes from `eventsQueryKeys.detail` (`useEventsQuery.ts:58`), which
 * the repo already reserved and unit-tested for this lookup
 * (`useEventsQuery.test.ts:458`) but had no product caller before this hook.
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';

import { eventsQueryKeys } from './useEventsQuery';
import { fetchEvent } from '../services/api';

import type { Event } from '../types/generated';

export interface UseEventModalRowResult {
  /** The resolved row, or null while it is unknown or unresolvable. */
  row: Event | null;
  /**
   * Drop the fetched cache entry. The modal's write handlers (`flag`, `notes`,
   * `reviewed`) report success against a fetched row while the cache under it
   * still holds the pre-write row, so the modal must not reopen onto it: the
   * timeline calls this on close, and the next open refetches.
   */
  discard: () => void;
}

export function useEventModalRow(
  eventId: number | null,
  browseEvents: readonly Event[]
): UseEventModalRowResult {
  const queryClient = useQueryClient();
  // A browse hit never enables the query, so browse-mode clicks keep the exact
  // request count they had before this hook existed.
  const browseRow = eventId === null ? undefined : browseEvents.find((e) => e.id === eventId);
  const needsFetch = eventId !== null && browseRow === undefined;

  const query = useQuery<Event>({
    // The `?? 0` only keys a disabled query; `enabled` gates the fetch.
    queryKey: eventsQueryKeys.detail(eventId ?? 0),
    queryFn: () => fetchEvent(eventId as number),
    enabled: needsFetch,
    staleTime: 30_000,
    retry: 1,
  });

  // Stable identity: the timeline passes this to an effect keyed on it, so an
  // inline arrow would re-run that effect on every render.
  const discard = useCallback(() => {
    if (eventId === null) return;
    queryClient.removeQueries({ queryKey: eventsQueryKeys.detail(eventId) });
  }, [queryClient, eventId]);

  return {
    row: browseRow ?? query.data ?? null,
    discard,
  };
}

/**
 * Refresh everything a write to one event can have changed.
 *
 * `eventsQueryKeys.all` is `['events']`, the prefix every event cache registers
 * under: the browse read (`['events','infinite',{…}]`) and this hook's `detail`
 * entry that the callers used to `refetch()`, plus the `top`/`recent`/`deleted`
 * caches. The narrower `lists()` key (`['events','list']`) is NOT a prefix of the
 * infinite key, so using it here would silently stop refreshing the browse list.
 */
export function useEventWriteInvalidation() {
  const queryClient = useQueryClient();
  return useCallback(() => {
    // `void`: invalidateQueries returns a promise; nothing here awaits it, and the
    // callers' handlers are not async. The refetch it triggers surfaces through
    // the queries themselves, not through this return value.
    void queryClient.invalidateQueries({ queryKey: eventsQueryKeys.all });
  }, [queryClient]);
}
