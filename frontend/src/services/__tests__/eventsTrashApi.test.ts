/**
 * Tests for the trash (soft-delete) event API functions — F4.3 The Trash UI.
 *
 * F-087: a Delete action (soft delete) in the event detail modal and a bulk Delete on the
 * timeline, both calling the existing soft-delete routes (ruling 131 — reversible, so no
 * confirmation; the Undo toast replaces it).
 * F-088: permanentlyDeleteEvent sends `?permanent=true` (B4.4 hard-delete route; the legacy
 * `{ soft_delete: false }` body is retired), and the bulk delete route is
 * `DELETE /api/events/bulk` with `{ event_ids, soft_delete: true }` (207 Multi-Status).
 *
 * Uses MSW to mock the backend and asserts on the actual wire requests.
 */

import { http, HttpResponse } from 'msw';
import { describe, it, expect, afterEach } from 'vitest';

import { server } from '../../mocks/server';
import {
  softDeleteEvent,
  bulkSoftDeleteEvents,
  permanentlyDeleteEvent,
} from '../api';

interface CapturedRequest {
  url: URL;
  method: string;
  body: unknown;
}

describe('Trash event API (F4.3)', () => {
  const captured: CapturedRequest[] = [];

  // NOTE: setup.ts (global setupFiles) already calls server.listen()/close()
  // around every test file. Calling listen() again here would re-apply MSW's
  // fetch interceptor and each request would hit its handler TWICE — invisible
  // to response-asserting tests, but this file asserts captured-request COUNTS.
  afterEach(() => {
    server.resetHandlers();
    captured.length = 0;
  });

  describe('softDeleteEvent (F-087)', () => {
    it('sends DELETE to /api/events/{id} with no body and no query params', async () => {
      server.use(
        http.delete('*/api/events/:id', async (info) => {
          captured.push({
            url: new URL(info.request.url),
            method: info.request.method,
            body: await info.request.text(),
          });
          return HttpResponse.json({ status: 'ok' });
        })
      );

      await softDeleteEvent(42);

      expect(captured).toHaveLength(1);
      expect(captured[0].method).toBe('DELETE');
      expect(captured[0].url.pathname).toBe('/api/events/42');
      // Ruling 131: no confirmation dialog precedes this call, so no body is sent —
      // the bare DELETE is the soft delete on the existing route.
      expect(captured[0].body).toBe('');
      expect(captured[0].url.search).toBe('');
    });

    it('propagates a 409 refusal as an error', async () => {
      server.use(
        http.delete('*/api/events/:id', () =>
          HttpResponse.json({ detail: 'Event not found' }, { status: 404 })
        )
      );

      await expect(softDeleteEvent(42)).rejects.toThrow();
    });
  });

  describe('bulkSoftDeleteEvents (F-087 bulk Delete on the timeline)', () => {
    it('sends DELETE /api/events/bulk with { event_ids, soft_delete: true }', async () => {
      server.use(
        http.delete('*/api/events/bulk', async (info) => {
          captured.push({
            url: new URL(info.request.url),
            method: info.request.method,
            body: JSON.parse(await info.request.text()),
          });
          return HttpResponse.json(
            {
              total: 2,
              succeeded: 2,
              failed: 0,
              skipped: 0,
              results: [
                { index: 0, status: 'success', id: 7, error: null },
                { index: 1, status: 'success', id: 8, error: null },
              ],
            },
            { status: 207 }
          );
        })
      );

      const result = await bulkSoftDeleteEvents([7, 8]);

      expect(captured).toHaveLength(1);
      expect(captured[0].method).toBe('DELETE');
      expect(captured[0].url.pathname).toBe('/api/events/bulk');
      expect(captured[0].body).toEqual({ event_ids: [7, 8], soft_delete: true });
      expect(result.total).toBe(2);
      expect(result.succeeded).toBe(2);
      expect(result.failed).toBe(0);
    });

    it('surfaces the 207 partial-failure shape to the caller', async () => {
      server.use(
        http.delete('*/api/events/bulk', () =>
          HttpResponse.json(
            {
              total: 2,
              succeeded: 1,
              failed: 1,
              skipped: 0,
              results: [
                { index: 0, status: 'success', id: 7, error: null },
                { index: 1, status: 'failed', id: null, error: 'Event not in Trash: 8' },
              ],
            },
            { status: 207 }
          )
        )
      );

      const result = await bulkSoftDeleteEvents([7, 8]);

      expect(result.succeeded).toBe(1);
      expect(result.failed).toBe(1);
      const second = result.results?.[1];
      expect(second?.status).toBe('failed');
      expect(second?.error).toContain('Event not in Trash');
    });

    it('rejects an empty id list client-side without a network call', async () => {
      await expect(bulkSoftDeleteEvents([])).rejects.toThrow();
      expect(captured).toHaveLength(0);
    });
  });

  describe('permanentlyDeleteEvent (F-088, B4.4 hard-delete route)', () => {
    it('sends DELETE /api/events/{id}?permanent=true with no legacy body', async () => {
      server.use(
        http.delete('*/api/events/:id', async (info) => {
          captured.push({
            url: new URL(info.request.url),
            method: info.request.method,
            body: await info.request.text(),
          });
          return HttpResponse.json({ status: 'ok' });
        })
      );

      await permanentlyDeleteEvent(42);

      expect(captured).toHaveLength(1);
      expect(captured[0].url.pathname).toBe('/api/events/42');
      // B4.4: ?permanent=true is the hard-delete signal; the legacy
      // { soft_delete: false } body is retired (the route ignored it).
      expect(captured[0].url.searchParams.get('permanent')).toBe('true');
      expect(captured[0].body).toBe('');
    });
  });
});
