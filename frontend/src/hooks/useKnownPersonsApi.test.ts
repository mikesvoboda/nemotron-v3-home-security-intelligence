/**
 * Tests for useKnownPersonsApi.
 *
 * Two reasons this file exists, and the assertions serve both:
 *
 * 1. The test-coverage gate (`scripts/check-test-coverage-gate.py`, rule
 *    `frontend/src/hooks/*.ts` -> unit test required) reported this hook
 *    MISSING TESTS once ruling 44 touched it — the same trap that surfaced
 *    `useHouseholdApi.test.ts`. Pinned here is the SHIPPED contract: query-key
 *    hierarchy, endpoint/method shape, `enabled: id > 0`, invalidation on
 *    mutation success, and handleResponse's error semantics (detail
 *    extraction, HTTP fallback, 204-as-undefined).
 * 2. Ruling 44 removed this hook's credential header. Every request it makes is
 *    recorded and checked, so a credential re-attaching itself here — from any
 *    source — fails the "no request carries a credential" test.
 */

import { QueryClient } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  knownPersonsQueryKeys,
  fetchKnownPersons,
  fetchKnownPerson,
  createKnownPerson,
  updateKnownPerson,
  deleteKnownPerson,
  useKnownPersonsQuery,
  useKnownPersonQuery,
  useCreateKnownPerson,
  useUpdateKnownPerson,
  useDeleteKnownPerson,
} from './useKnownPersonsApi';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// ---------------------------------------------------------------------------
// fetch mock: a queue of responses + a recorder for url/method/headers
// ---------------------------------------------------------------------------

interface RecordedCall {
  url: string;
  method: string;
  headers: Record<string, string>;
  body?: string;
}

let calls: RecordedCall[] = [];
let responses: { ok: boolean; status: number; statusText: string; body: unknown }[] = [];

function jsonResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, statusText: 'Status', body };
}

const person = {
  id: 1,
  name: 'Ada',
  is_household_member: true,
  notes: null,
  created_at: '2026-10-09T00:00:00Z',
  updated_at: '2026-10-09T00:00:00Z',
  embedding_count: 2,
  household_member_id: null,
};

beforeEach(() => {
  calls = [];
  responses = [];
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init: RequestInit = {}) => {
      calls.push({
        url,
        method: init.method ?? 'GET',
        headers: (init.headers ?? {}) as Record<string, string>,
        body: typeof init.body === 'string' ? init.body : undefined,
      });
      const next = responses.shift() ?? jsonResponse([]);
      return Promise.resolve({
        ok: next.ok,
        status: next.status,
        statusText: next.statusText,
        json: () => {
          if (next.body === undefined) return Promise.reject(new TypeError('no body'));
          return Promise.resolve(next.body);
        },
      });
    })
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('knownPersonsQueryKeys', () => {
  it('builds the key hierarchy the invalidations rely on', () => {
    expect(knownPersonsQueryKeys.all).toEqual(['known-persons']);
    expect(knownPersonsQueryKeys.list()).toEqual(['known-persons', 'list']);
    expect(knownPersonsQueryKeys.detail(7)).toEqual(['known-persons', 'detail', 7]);
  });
});

describe('known-persons API functions (endpoint contract)', () => {
  it('fetchKnownPersons GETs the collection', async () => {
    responses = [jsonResponse([person])];
    await expect(fetchKnownPersons()).resolves.toEqual([person]);
    expect(calls[0]).toMatchObject({ url: '/api/known-persons', method: 'GET' });
  });

  it('fetchKnownPerson GETs the person path', async () => {
    responses = [jsonResponse(person)];
    await expect(fetchKnownPerson(4)).resolves.toEqual(person);
    expect(calls[0]).toMatchObject({ url: '/api/known-persons/4', method: 'GET' });
  });

  it('createKnownPerson POSTs the JSON payload', async () => {
    responses = [jsonResponse(person)];
    await createKnownPerson({ name: 'Ada', is_household_member: true });
    expect(calls[0].method).toBe('POST');
    expect(JSON.parse(calls[0].body!)).toEqual({ name: 'Ada', is_household_member: true });
  });

  it('updateKnownPerson PATCHes the person path', async () => {
    responses = [jsonResponse({ ...person, name: 'Ada L.' })];
    await updateKnownPerson(4, { name: 'Ada L.' });
    expect(calls[0].method).toBe('PATCH');
    expect(calls[0].url).toBe('/api/known-persons/4');
    expect(JSON.parse(calls[0].body!)).toEqual({ name: 'Ada L.' });
  });

  it('deleteKnownPerson DELETEs and maps 204 to undefined', async () => {
    responses = [jsonResponse(undefined, 204)];
    await expect(deleteKnownPerson(4)).resolves.toBeUndefined();
    expect(calls[0]).toMatchObject({ url: '/api/known-persons/4', method: 'DELETE' });
  });

  it('a failed response surfaces the backend detail message', async () => {
    responses = [
      { ok: false, status: 400, statusText: 'Bad Request', body: { detail: 'name required' } },
    ];
    await expect(fetchKnownPersons()).rejects.toThrow('name required');
  });

  it('an unparseable error body falls back to the HTTP line', async () => {
    responses = [{ ok: false, status: 502, statusText: 'Bad Gateway', body: undefined }];
    await expect(fetchKnownPersons()).rejects.toThrow('HTTP 502: Bad Gateway');
  });
});

describe('ruling 44: every known-persons request is credential-free', () => {
  it('sends only Content-Type — no key header, from any source', async () => {
    responses = [
      jsonResponse([person]),
      jsonResponse(person),
      jsonResponse(person),
      jsonResponse(undefined, 204),
    ];
    await fetchKnownPersons();
    await fetchKnownPerson(1);
    await createKnownPerson({ name: 'Ada' });
    await deleteKnownPerson(1);

    expect(calls).toHaveLength(4);
    for (const call of calls) {
      expect(Object.keys(call.headers).map((h) => h.toLowerCase())).toEqual(['content-type']);
    }
  });

  it('no request puts a credential in the URL either', async () => {
    responses = [jsonResponse(person)];
    await updateKnownPerson(2, { notes: 'x' });
    expect(calls[0].url).not.toMatch(/api_key|apikey/);
  });
});

describe('known-persons hooks', () => {
  // Retries and refetchOnWindowFocus OFF (as in useHouseholdApi.test.ts): the
  // production client's retry policy would re-issue fetches and drain the
  // mocked queue, and jsdom focus events would add GETs these tests don't own.
  function freshWrapper() {
    const qc = new QueryClient({
      defaultOptions: {
        queries: { retry: false, refetchOnWindowFocus: false },
        mutations: { retry: false },
      },
    });
    return createQueryWrapper(qc);
  }

  it('useKnownPersonsQuery resolves through the cache', async () => {
    responses = [jsonResponse([person])];
    const { result } = renderHook(() => useKnownPersonsQuery(), { wrapper: freshWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([person]);
    expect(calls[0].url).toBe('/api/known-persons');
  });

  it('useKnownPersonQuery is disabled at id 0 and issues no request', () => {
    const { result } = renderHook(() => useKnownPersonQuery(0), { wrapper: freshWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
    expect(calls).toHaveLength(0);
  });

  it('useKnownPersonQuery fetches the detail path for a real id', async () => {
    responses = [jsonResponse(person)];
    const { result } = renderHook(() => useKnownPersonQuery(5), { wrapper: freshWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls[0].url).toBe('/api/known-persons/5');
  });

  it('useCreateKnownPerson refetches the list after success', async () => {
    const wrapper = freshWrapper();
    responses = [jsonResponse([person])];
    const list = renderHook(() => useKnownPersonsQuery(), { wrapper });
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true));

    responses = [jsonResponse(person)];
    const mutation = renderHook(() => useCreateKnownPerson(), { wrapper });
    await mutation.result.current.mutateAsync({ name: 'Grace' });

    // Observe the invalidation at the fetch layer: isFetching can clear before
    // waitFor ever polls, but the refetch GET (same URL, GET method) cannot.
    await waitFor(() =>
      expect(calls.filter((c) => c.url === '/api/known-persons' && c.method === 'GET').length).toBe(
        2
      )
    );
  });

  it('useUpdateKnownPerson invalidates the list and the edited detail', async () => {
    const wrapper = freshWrapper();
    responses = [jsonResponse([person]), jsonResponse(person)];
    const list = renderHook(() => useKnownPersonsQuery(), { wrapper });
    const detail = renderHook(() => useKnownPersonQuery(3), { wrapper });
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(detail.result.current.isSuccess).toBe(true));

    responses = [jsonResponse({ ...person, name: 'Ada L.' })];
    const mutation = renderHook(() => useUpdateKnownPerson(), { wrapper });
    await mutation.result.current.mutateAsync({ id: 3, data: { name: 'Ada L.' } });

    await waitFor(() =>
      expect(calls.filter((c) => c.url === '/api/known-persons' && c.method === 'GET').length).toBe(
        2
      )
    );
    await waitFor(() =>
      expect(
        calls.filter((c) => c.url === '/api/known-persons/3' && c.method === 'GET').length
      ).toBe(2)
    );
  });

  it('useDeleteKnownPerson surfaces a failed mutation instead of invalidating', async () => {
    responses = [
      { ok: false, status: 404, statusText: 'Not Found', body: { detail: 'no such person' } },
    ];
    const { result } = renderHook(() => useDeleteKnownPerson(), { wrapper: freshWrapper() });
    await expect(result.current.mutateAsync(99)).rejects.toThrow('no such person');
    expect(calls.filter((c) => c.method === 'GET')).toHaveLength(0);
  });
});
