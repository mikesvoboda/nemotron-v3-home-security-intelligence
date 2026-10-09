/**
 * F1.3: the `fetchApi` 401 seam.
 *
 * Today `handleResponse` (api.ts:1203-1234 at origin/main e9ec74ef) throws
 * `ApiError(401)` and nothing routes the session-invalidated state anywhere —
 * a mid-session 401 from the B1.5 gate renders a toast, not a login.
 *
 * The seam is deliberately policy-free: api.ts stays auth-agnostic (it knew
 * nothing about auth before F1.3). It only notifies a registered handler that
 * a call came back 401; `AuthContext` decides what that means. `authApi.ts`
 * calls (login, logout, /me) bypass `fetchApi` entirely, so the handler can
 * never fire on auth's own deliberate 401s.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, fetchApi, setUnauthorizedHandler } from './api';

/**
 * Build a Response-shaped object for the gate's exact refusal body
 * (backend/api/middleware/auth.py:405-408: 401 {"detail": "Authentication required"}).
 */
function gateRefusal(status = 401, detail = 'Authentication required'): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 401 ? 'Unauthorized' : 'Error',
    headers: new Headers(),
    json: () => Promise.resolve({ detail }),
  } as unknown as Response;
}

describe('fetchApi 401 seam (F1.3)', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    setUnauthorizedHandler(null);
    vi.unstubAllGlobals();
  });

  it('still rejects with ApiError(401) carrying the gate detail', async () => {
    fetchMock.mockResolvedValue(gateRefusal());

    const error = await fetchApi('/api/events').catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(401);
    expect((error as ApiError).message).toBe('Authentication required');
  });

  it('notifies a registered handler when a call comes back 401', async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    fetchMock.mockResolvedValue(gateRefusal());

    await expect(fetchApi('/api/events')).rejects.toBeInstanceOf(ApiError);

    expect(handler).toHaveBeenCalledTimes(1);
    const passed = handler.mock.calls[0][0] as ApiError;
    expect(passed).toBeInstanceOf(ApiError);
    expect(passed.status).toBe(401);
  });

  it('does not notify for 403 (permission, not session)', async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    fetchMock.mockResolvedValue(gateRefusal(403, 'Not enough privileges'));

    await expect(fetchApi('/api/admin/keys')).rejects.toBeInstanceOf(ApiError);

    expect(handler).not.toHaveBeenCalled();
  });

  it('does not notify for a 404', async () => {
    // (A transport failure exhausting retries surfaces as ApiError(0) and also
    // must not notify, but that path sleeps through ~7s of backoff; the seam
    // fires only at the status-401 throw site, so 4xx coverage here is complete.)
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    fetchMock.mockResolvedValue(gateRefusal(404, 'Event not found'));

    await expect(fetchApi('/api/events/999')).rejects.toBeInstanceOf(ApiError);

    expect(handler).not.toHaveBeenCalled();
  });

  it('a throwing handler never masks the ApiError reaching the caller', async () => {
    setUnauthorizedHandler(() => {
      throw new Error('handler exploded');
    });
    fetchMock.mockResolvedValue(gateRefusal());

    const error = await fetchApi('/api/events').catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(401);
  });

  it('the returned unregister function detaches the handler', async () => {
    const handler = vi.fn();
    const unregister = setUnauthorizedHandler(handler);
    unregister();
    fetchMock.mockResolvedValue(gateRefusal());

    await expect(fetchApi('/api/events')).rejects.toBeInstanceOf(ApiError);

    expect(handler).not.toHaveBeenCalled();
  });

  it('GET dedup fires the handler once for concurrent waiters of one request', async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    fetchMock.mockResolvedValue(gateRefusal());

    // Identical in-flight GETs without a signal share one promise
    // (api.ts:1360-1383): the seam must fire per underlying request, not per waiter.
    const results = await Promise.allSettled([fetchApi('/api/events'), fetchApi('/api/events')]);

    expect(results.every((r) => r.status === 'rejected')).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledTimes(1);
  });
});
