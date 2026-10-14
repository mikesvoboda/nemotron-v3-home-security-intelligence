/**
 * EventDeepLinkRedirect - /events/:id -> /timeline?event=:id (ruling 167)
 *
 * The backend's summary-detail payload stores each timeline row's link as
 * `/events/{id}` (`backend/services/summary_detail_service.py:147`) and the
 * dashboard panel renders that value verbatim as an anchor href. The SPA route
 * table routed no `/events/:id`, so every one of those links fell to the
 * catch-all and answered the app's own NotFoundPage. Ruling 167 settles the
 * split: the backend keeps emitting `/events/{id}` ("One side changes, not
 * both") and the frontend adds the redirect.
 *
 * Mounted inside `<Layout />`, so a followed link keeps the shell chrome
 * instead of swapping to a bare page.
 *
 * An id the app cannot use is NOT redirected onto an unfiltered timeline:
 * `EventTimeline` validates its `event` param with `parseEventId` (digits only,
 * NEM-2561), and a junk id there would look like a working link while showing
 * every event. Such a path renders `fallback` — the same NotFoundPage the
 * catch-all answers with, which `App.tsx` supplies because a matched route
 * wins over `path="*"` and rendering nothing here would be a blank dead end.
 *
 * @example
 * <Route path="/events/:eventId" element={<EventDeepLinkRedirect fallback={<NotFoundPage />} />} />
 */

import { Navigate, useParams } from 'react-router-dom';

import { parseEventId } from '../../utils/validation';

import type { ReactNode } from 'react';

export interface EventDeepLinkRedirectProps {
  /** Rendered when the path id cannot be used as a timeline deep link. */
  fallback?: ReactNode;
}

/**
 * Maps a raw `/events/:id` path param to the deep link the app actually serves
 * (`/timeline?event=<id>`), or null when the id is unusable. Exported for unit
 * coverage of the two shipped callers, whose ids are not guaranteed to be the
 * numeric ids the timeline accepts.
 */
export function eventRedirectTarget(eventId: string | undefined): string | null {
  const { eventId: parsed, isValid } = parseEventId(eventId);
  // `ParseEventIdResult` declares the two fields independently (`eventId: number | null`,
  // `isValid: boolean`), so the type cannot narrow `parsed` from `isValid` — and a
  // `{ isValid: true, eventId: null }` would otherwise serialize into
  // `/timeline?event=null`. Both legs are checked today; every invalid input ships
  // them together, which is why a mutation of either alone still passes the tests.
  if (!isValid || parsed === null) return null;
  return `/timeline?event=${String(parsed)}`;
}

export default function EventDeepLinkRedirect({ fallback = null }: EventDeepLinkRedirectProps) {
  const { eventId } = useParams<{ eventId: string }>();
  const target = eventRedirectTarget(eventId);
  if (target === null) return <>{fallback}</>;
  // `replace` so a followed link does not leave a history entry for the
  // redirect itself, only for the timeline it lands on.
  return <Navigate to={target} replace />;
}
