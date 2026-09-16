/**
 * Tests for useHouseholdApi (WP0.6 CI-truth follow-up).
 *
 * Surfaced by PR #6549: the WP0.1-repaired coverage gate (first run in which
 * get_changed_files actually parsed anything) reported this hook file
 * MISSING TESTS — it shipped on main while the gate's parser was blind.
 * Pinned here is the SHIPPED contract: query keys, endpoint/method shape,
 * invalidation on mutation success, and handleResponse's error semantics
 * (detail extraction, HTTP fallback, 204-as-undefined).
 */

import { QueryClient } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  householdQueryKeys,
  useMembersQuery,
  useCreateMember,
  useDeleteMember,
  useVehiclesQuery,
  useHouseholdsQuery,
  fetchMembers,
  createMember,
  deleteMember,
  getMemberDetections,
} from './useHouseholdApi';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// ---------------------------------------------------------------------------
// fetch mock: a queue of [status, body] responses + call recorder
// ---------------------------------------------------------------------------

interface RecordedCall {
  url: string;
  method: string;
  body?: string;
}

let calls: RecordedCall[] = [];
let responses: { ok: boolean; status: number; statusText: string; body: unknown }[] = [];

function jsonResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, statusText: 'Status', body };
}

beforeEach(() => {
  calls = [];
  responses = [];
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init: RequestInit = {}) => {
      calls.push({
        url,
        method: init.method ?? 'GET',
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

describe('householdQueryKeys', () => {
  it('builds the nested key hierarchy the cache invalidation relies on', () => {
    expect(householdQueryKeys.all).toEqual(['household']);
    expect(householdQueryKeys.members()).toEqual(['household', 'members']);
    expect(householdQueryKeys.member(7)).toEqual(['household', 'members', 7]);
    expect(householdQueryKeys.vehicles()).toEqual(['household', 'vehicles']);
    expect(householdQueryKeys.households()).toEqual(['household', 'households']);
  });
});

describe('household API functions (endpoint contract)', () => {
  it('fetchMembers GETs the members collection', async () => {
    responses = [jsonResponse([{ id: 1, name: 'A' }])];
    await expect(fetchMembers()).resolves.toEqual([{ id: 1, name: 'A' }]);
    expect(calls[0]).toMatchObject({ url: '/api/household/members', method: 'GET' });
  });

  it('createMember POSTs the JSON payload', async () => {
    responses = [jsonResponse({ id: 2 })];
    await createMember({ name: 'B', role: 'family', trusted_level: 'partial' });
    expect(calls[0].method).toBe('POST');
    expect(JSON.parse(calls[0].body!)).toEqual({
      name: 'B',
      role: 'family',
      trusted_level: 'partial',
    });
  });

  it('deleteMember hits the member path and maps 204 to undefined', async () => {
    responses = [jsonResponse(undefined, 204)];
    await expect(deleteMember(3)).resolves.toBeUndefined();
    expect(calls[0]).toMatchObject({ url: '/api/household/members/3', method: 'DELETE' });
  });

  it('getMemberDetections maps filter params onto the query string', async () => {
    responses = [jsonResponse({ detections: [], total: 0 })];
    await getMemberDetections(5, {
      limit: 10,
      offset: 20,
      camera: 'Front_Door',
      sort: 'confidence_desc',
    });
    const url = new URL(calls[0].url, 'http://x');
    expect(url.pathname).toBe('/api/household/members/5/detections');
    expect(url.searchParams.get('limit')).toBe('10');
    expect(url.searchParams.get('offset')).toBe('20');
    // camera ids are lower-cased by the shipped mapping
    expect(url.searchParams.get('camera_id')).toBe('front_door');
    expect(url.searchParams.get('sort_by')).toBe('confidence');
    expect(url.searchParams.get('sort_order')).toBe('desc');
  });

  it('error responses surface the backend detail message', async () => {
    responses = [
      { ok: false, status: 400, statusText: 'Bad Request', body: { detail: 'name required' } },
    ];
    await expect(fetchMembers()).rejects.toThrow('name required');
  });

  it('error responses with unparseable bodies fall back to the HTTP line', async () => {
    responses = [{ ok: false, status: 502, statusText: 'Bad Gateway', body: undefined }];
    await expect(fetchMembers()).rejects.toThrow('HTTP 502: Bad Gateway');
  });
});

describe('household query hooks', () => {
  // Shared client, retries OFF: the production client's retry policy would
  // re-issue fetches and drain the mocked response queue under test.
  // refetchOnWindowFocus OFF too — jsdom focus events between renders would
  // add GETs the invalidation assertion doesn't own.
  function freshWrapper() {
    const qc = new QueryClient({
      defaultOptions: {
        queries: { retry: false, refetchOnWindowFocus: false },
        mutations: { retry: false },
      },
    });
    return createQueryWrapper(qc);
  }

  it('useMembersQuery resolves through the react-query cache', async () => {
    responses = [jsonResponse([{ id: 1 }])];
    const { result } = renderHook(() => useMembersQuery(), {
      wrapper: freshWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ id: 1 }]);
  });

  it('useVehiclesQuery and useHouseholdsQuery hit their collections', async () => {
    responses = [jsonResponse([{ id: 9 }]), jsonResponse({ households: [], total: 0 })];
    const v = renderHook(() => useVehiclesQuery(), { wrapper: freshWrapper() });
    await waitFor(() => expect(v.result.current.isSuccess).toBe(true));
    expect(calls[0].url).toBe('/api/household/vehicles');

    const h = renderHook(() => useHouseholdsQuery(), { wrapper: freshWrapper() });
    await waitFor(() => expect(h.result.current.isSuccess).toBe(true));
    expect(calls[1].url).toBe('/api/v1/households');
  });

  it('useCreateMember invalidates the members list after success', async () => {
    const wrapper = freshWrapper();
    // Prime the list query so its invalidation is observable via isFetching.
    responses = [jsonResponse([{ id: 1 }])];
    const list = renderHook(() => useMembersQuery(), { wrapper });
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true));

    responses = [jsonResponse({ id: 2 })];
    const mutation = renderHook(() => useCreateMember(), { wrapper });
    await mutation.result.current.mutateAsync({
      name: 'C',
      role: 'resident',
      trusted_level: 'full',
    });
    // Observe the invalidation at the fetch layer: the refetch GET lands
    // after the POST (same URL — filter on method), and isFetching can flip
    // back to false before waitFor ever polls.
    await waitFor(() =>
      expect(
        calls.filter((c) => c.url === '/api/household/members' && c.method === 'GET').length
      ).toBe(2)
    );
  });

  it('useDeleteMember surfaces a failed mutation instead of invalidating', async () => {
    responses = [
      { ok: false, status: 404, statusText: 'Not Found', body: { detail: 'no member' } },
    ];
    const { result } = renderHook(() => useDeleteMember(), {
      wrapper: freshWrapper(),
    });
    await expect(result.current.mutateAsync(99)).rejects.toThrow('no member');
  });
});
