/**
 * useKnownPersonsApi - TanStack Query hooks for known persons API
 *
 * Provides hooks for managing known persons in the face recognition system.
 * Uses the following endpoints:
 *
 * Known Persons:
 * - GET /api/known-persons - List all known persons
 * - POST /api/known-persons - Create new person
 * - GET /api/known-persons/{id} - Get specific person
 * - PATCH /api/known-persons/{id} - Update person
 * - DELETE /api/known-persons/{id} - Delete person
 *
 * @module hooks/useKnownPersonsApi
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { STATIC_STALE_TIME } from '../services/queryClient';

import type { KnownPerson, KnownPersonCreate, KnownPersonUpdate } from '../types/faceRecognition';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for known persons API.
 */
export const knownPersonsQueryKeys = {
  /** Base key for all known persons queries */
  all: ['known-persons'] as const,
  /** Known persons list */
  list: () => [...knownPersonsQueryKeys.all, 'list'] as const,
  /** Single known person */
  detail: (id: number) => [...knownPersonsQueryKeys.all, 'detail', id] as const,
};

// ============================================================================
// API Functions
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

/**
 * Build headers for API requests.
 */
function buildHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return headers;
}

/**
 * Handle API response and extract error message on failure.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorBody = (await response.json()) as { detail?: string };
      if (errorBody.detail) {
        errorMessage = errorBody.detail;
      }
    } catch {
      // Use default error message if JSON parsing fails
    }
    throw new Error(errorMessage);
  }
  // Handle 204 No Content responses
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

// --- Known Persons API Functions ---

/**
 * Fetch all known persons.
 */
export async function fetchKnownPersons(): Promise<KnownPerson[]> {
  const response = await fetch(`${BASE_URL}/api/known-persons`, {
    method: 'GET',
    headers: buildHeaders(),
  });
  return handleResponse<KnownPerson[]>(response);
}

/**
 * Fetch a single known person by ID.
 */
export async function fetchKnownPerson(id: number): Promise<KnownPerson> {
  const response = await fetch(`${BASE_URL}/api/known-persons/${id}`, {
    method: 'GET',
    headers: buildHeaders(),
  });
  return handleResponse<KnownPerson>(response);
}

/**
 * Create a new known person.
 */
export async function createKnownPerson(data: KnownPersonCreate): Promise<KnownPerson> {
  const response = await fetch(`${BASE_URL}/api/known-persons`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse<KnownPerson>(response);
}

/**
 * Update an existing known person.
 */
export async function updateKnownPerson(id: number, data: KnownPersonUpdate): Promise<KnownPerson> {
  const response = await fetch(`${BASE_URL}/api/known-persons/${id}`, {
    method: 'PATCH',
    headers: buildHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse<KnownPerson>(response);
}

/**
 * Delete a known person.
 */
export async function deleteKnownPerson(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/known-persons/${id}`, {
    method: 'DELETE',
    headers: buildHeaders(),
  });
  return handleResponse<void>(response);
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook to fetch all known persons.
 */
export function useKnownPersonsQuery() {
  return useQuery({
    queryKey: knownPersonsQueryKeys.list(),
    queryFn: fetchKnownPersons,
    staleTime: STATIC_STALE_TIME,
  });
}

/**
 * Hook to fetch a single known person.
 */
export function useKnownPersonQuery(id: number) {
  return useQuery({
    queryKey: knownPersonsQueryKeys.detail(id),
    queryFn: () => fetchKnownPerson(id),
    staleTime: STATIC_STALE_TIME,
    enabled: id > 0,
  });
}

/**
 * Hook to create a known person.
 */
export function useCreateKnownPerson() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createKnownPerson,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: knownPersonsQueryKeys.list() });
    },
  });
}

/**
 * Hook to update a known person.
 */
export function useUpdateKnownPerson() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: KnownPersonUpdate }) =>
      updateKnownPerson(id, data),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: knownPersonsQueryKeys.list() });
      void queryClient.invalidateQueries({
        queryKey: knownPersonsQueryKeys.detail(variables.id),
      });
    },
  });
}

/**
 * Hook to delete a known person.
 */
export function useDeleteKnownPerson() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteKnownPerson,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: knownPersonsQueryKeys.list() });
    },
  });
}

export default {
  useKnownPersonsQuery,
  useKnownPersonQuery,
  useCreateKnownPerson,
  useUpdateKnownPerson,
  useDeleteKnownPerson,
};
