/**
 * Tests for EventDeepLinkRedirect (owner ruling 167, F-034).
 *
 * Three separate claims, so three kinds of test:
 * - the id→target mapping (pure function, including which ids it refuses);
 * - the landing a followed `/events/<n>` link produces — asserted with the
 *   `path="*"` catch-all mounted, because a matched route must WIN over it,
 *   and that precedence is exactly why the component takes a `fallback`;
 * - `replace` semantics, so Back does not bounce through the redirect again.
 *
 * Caller coverage lives with the caller: AuditResultsTable.test.tsx follows its
 * own shipped anchor through this route.
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import EventDeepLinkRedirect, { eventRedirectTarget } from './EventDeepLinkRedirect';

import type { ReactNode } from 'react';

/** Where the router ended up — the house pattern for asserting a Navigate target. */
function LocationDisplay() {
  const location = useLocation();
  return (
    <div>
      <div data-testid="current-path">{location.pathname}</div>
      <div data-testid="current-search">{location.search}</div>
    </div>
  );
}

function BackButton() {
  const navigate = useNavigate();
  return (
    <button
      onClick={() => {
        // navigate() returns a Promise; a bare arrow would hand it to onClick
        // and trip @typescript-eslint/no-misused-promises.
        void navigate(-1);
      }}
    >
      go back
    </button>
  );
}

const NotFoundStub = <div data-testid="not-found-page">Not Found</div>;

/**
 * The route shape `App.tsx` mounts: the redirect, its destination, and the
 * catch-all that used to answer `/events/<n>`. Keeping the catch-all in the
 * tree is deliberate — removing it would let a bare `return null` pass as a fix.
 */
function renderAt(initialEntries: string[], fallback?: ReactNode) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route
          path="/timeline"
          element={
            <>
              <LocationDisplay />
              <BackButton />
            </>
          }
        />
        <Route path="/analytics" element={<LocationDisplay />} />
        <Route path="/events/:eventId" element={<EventDeepLinkRedirect fallback={fallback} />} />
        <Route path="*" element={NotFoundStub} />
      </Routes>
    </MemoryRouter>
  );
}

describe('eventRedirectTarget', () => {
  it('maps a numeric id onto the deep link the app actually serves', () => {
    expect(eventRedirectTarget('123')).toBe('/timeline?event=123');
  });

  it('re-serializes the id through parseEventId instead of echoing the raw path segment', () => {
    expect(eventRedirectTarget('007')).toBe('/timeline?event=7');
  });

  // EventTimeline validates `event` with the same parseEventId (NEM-2561), so a
  // non-numeric id sent there would render EVERY event behind a URL that looks
  // like it worked. Refusing is the behavior, not an omission.
  it.each([
    ['a word', 'not-an-id'],
    ['a mixed id', '12abc'],
    ['a negative', '-5'],
    ['a decimal', '1.5'],
    ['empty', ''],
    ['whitespace', ' '],
    ['missing', undefined],
  ])('refuses %s rather than redirecting to an unfiltered timeline', (_label, raw) => {
    expect(eventRedirectTarget(raw)).toBeNull();
  });
});

describe('EventDeepLinkRedirect', () => {
  it('lands a followed /events/<id> on /timeline?event=<id>, not on the catch-all', () => {
    renderAt(['/events/123'], NotFoundStub);

    expect(screen.getByTestId('current-path')).toHaveTextContent('/timeline');
    expect(screen.getByTestId('current-search')).toHaveTextContent('event=123');
    expect(screen.queryByTestId('not-found-page')).not.toBeInTheDocument();
  });

  it('renders the fallback for an unusable id instead of moving the URL', () => {
    renderAt(['/events/not-an-id'], NotFoundStub);

    expect(screen.getByTestId('not-found-page')).toBeInTheDocument();
    expect(screen.queryByTestId('current-path')).not.toBeInTheDocument();
  });

  it('renders nothing with no fallback — which is why App.tsx supplies NotFoundPage', () => {
    // A matched route beats `path="*"`, so the component returning null here is
    // a blank dead end and NOT the 404 the pre-ruling prose described. This pins
    // the default so the App-level wiring stays the load-bearing half.
    const { container } = renderAt(['/events/not-an-id']);

    expect(screen.queryByTestId('not-found-page')).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });

  it('replaces history so Back skips the redirect instead of re-entering it', async () => {
    const user = userEvent.setup();
    renderAt(['/analytics', '/events/123'], NotFoundStub);

    expect(screen.getByTestId('current-path')).toHaveTextContent('/timeline');

    // Under `push` the stack would be /analytics → /events/123 → /timeline, so
    // Back lands on the redirect, which immediately bounces forward again and
    // this assertion reads /timeline instead of /analytics.
    await user.click(screen.getByRole('button', { name: 'go back' }));

    expect(screen.getByTestId('current-path')).toHaveTextContent('/analytics');
  });
});
