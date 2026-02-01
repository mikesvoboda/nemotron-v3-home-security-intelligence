/**
 * useFaceRecognitionApi - TanStack Query hooks for face recognition API
 *
 * Provides hooks for managing known persons, face embeddings, face events,
 * and person appearances. Uses the following endpoints:
 *
 * Known Persons:
 * - GET /api/known-persons - List all known persons
 * - POST /api/known-persons - Create new known person
 * - GET /api/known-persons/{id} - Get specific person
 * - PATCH /api/known-persons/{id} - Update person
 * - DELETE /api/known-persons/{id} - Delete person
 *
 * Face Embeddings:
 * - GET /api/known-persons/{id}/embeddings - Get person's embeddings
 * - DELETE /api/known-persons/{id}/embeddings/{embedding_id} - Delete embedding
 * - POST /api/known-persons/{id}/enroll-from-detection - Enroll face from detection
 *
 * Person Appearances:
 * - GET /api/known-persons/{id}/appearances - Get appearance timeline
 *
 * @module hooks/useFaceRecognitionApi
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  useInfiniteQuery,
} from '@tanstack/react-query';

import { REALTIME_STALE_TIME, STATIC_STALE_TIME } from '../services/queryClient';

import type {
  KnownPerson,
  KnownPersonCreate,
  KnownPersonUpdate,
  FaceEmbedding,
  EnrollFaceRequest,
  EnrollFaceResponse,
  AppearancesFilter,
  PersonAppearancesResponse,
  FaceStats,
  UnknownStrangerSummary,
  IdentifyFaceRequest,
  IdentifyFaceResponse,
  FaceEventsFilter,
  FaceEventsResponse,
} from '../types/faceRecognition';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for face recognition API.
 */
export const faceRecognitionQueryKeys = {
  /** Base key for all face recognition queries */
  all: ['face-recognition'] as const,

  /** Known persons list */
  knownPersons: () => [...faceRecognitionQueryKeys.all, 'known-persons'] as const,

  /** Single known person */
  knownPerson: (id: number) => [...faceRecognitionQueryKeys.knownPersons(), id] as const,

  /** Embeddings for a person */
  personEmbeddings: (personId: number) =>
    [...faceRecognitionQueryKeys.knownPerson(personId), 'embeddings'] as const,

  /** Base key for all face events */
  faceEventsAll: () => [...faceRecognitionQueryKeys.all, 'face-events'] as const,

  /** Face events list with optional filters */
  faceEvents: (filters?: FaceEventsFilter) =>
    [...faceRecognitionQueryKeys.faceEventsAll(), 'list', filters] as const,

  /** Unknown strangers list with optional limit */
  unknownStrangers: (limit?: number) =>
    [...faceRecognitionQueryKeys.faceEventsAll(), 'unknown', limit] as const,

  /** Face detection statistics */
  faceStats: () => [...faceRecognitionQueryKeys.faceEventsAll(), 'stats'] as const,

  /** Person appearances with optional filters */
  personAppearances: (personId: number, filters?: AppearancesFilter) =>
    [...faceRecognitionQueryKeys.knownPerson(personId), 'appearances', filters] as const,
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

// --- Face Embeddings API Functions ---

/**
 * Fetch face embeddings for a known person.
 */
export async function fetchPersonEmbeddings(personId: number): Promise<FaceEmbedding[]> {
  const response = await fetch(`${BASE_URL}/api/known-persons/${personId}/embeddings`, {
    method: 'GET',
    headers: buildHeaders(),
  });
  return handleResponse<FaceEmbedding[]>(response);
}

/**
 * Delete a face embedding.
 */
export async function deleteEmbedding(personId: number, embeddingId: number): Promise<void> {
  const response = await fetch(
    `${BASE_URL}/api/known-persons/${personId}/embeddings/${embeddingId}`,
    {
      method: 'DELETE',
      headers: buildHeaders(),
    }
  );
  return handleResponse<void>(response);
}

/**
 * Enroll a face from an existing detection.
 */
export async function enrollFaceFromDetection(
  personId: number,
  data: EnrollFaceRequest
): Promise<EnrollFaceResponse> {
  const response = await fetch(`${BASE_URL}/api/known-persons/${personId}/enroll-from-detection`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse<EnrollFaceResponse>(response);
}

// --- Person Appearances API Functions ---

/**
 * Fetch appearances for a known person.
 */
export async function fetchPersonAppearances(
  personId: number,
  filters?: AppearancesFilter
): Promise<PersonAppearancesResponse> {
  const queryParams = new URLSearchParams();

  if (filters?.start_date) {
    queryParams.set('start_date', filters.start_date);
  }
  if (filters?.end_date) {
    queryParams.set('end_date', filters.end_date);
  }
  if (filters?.camera_id !== undefined) {
    queryParams.set('camera_id', String(filters.camera_id));
  }
  if (filters?.limit !== undefined) {
    queryParams.set('limit', String(filters.limit));
  }
  if (filters?.offset !== undefined) {
    queryParams.set('offset', String(filters.offset));
  }

  const queryString = queryParams.toString();
  const url = `${BASE_URL}/api/known-persons/${personId}/appearances${queryString ? `?${queryString}` : ''}`;

  const response = await fetch(url, {
    method: 'GET',
    headers: buildHeaders(),
  });
  return handleResponse<PersonAppearancesResponse>(response);
}

// --- Unknown Strangers API Functions ---

/**
 * Fetch unknown stranger alerts.
 */
export async function fetchUnknownStrangers(limit?: number): Promise<UnknownStrangerSummary> {
  const params = new URLSearchParams();
  if (limit !== undefined) {
    params.set('limit', String(limit));
  }
  const queryString = params.toString();
  const url = `${BASE_URL}/api/face-events/unknown${queryString ? `?${queryString}` : ''}`;

  const response = await fetch(url, {
    method: 'GET',
    headers: buildHeaders(),
  });
  return handleResponse<UnknownStrangerSummary>(response);
}

// --- Face Events API Functions ---

/**
 * Build query string from filter parameters.
 */
function buildFaceEventsQueryString(filters?: FaceEventsFilter): string {
  if (!filters) return '';

  const params = new URLSearchParams();

  if (filters.camera_id !== undefined) {
    params.set('camera_id', String(filters.camera_id));
  }
  if (filters.person_id !== undefined) {
    params.set('person_id', String(filters.person_id));
  }
  if (filters.unknown_only !== undefined) {
    params.set('unknown_only', String(filters.unknown_only));
  }
  if (filters.start_date) {
    params.set('start_date', filters.start_date);
  }
  if (filters.end_date) {
    params.set('end_date', filters.end_date);
  }
  if (filters.min_quality !== undefined) {
    params.set('min_quality', String(filters.min_quality));
  }
  if (filters.cursor) {
    params.set('cursor', filters.cursor);
  }
  if (filters.limit !== undefined) {
    params.set('limit', String(filters.limit));
  }

  const queryString = params.toString();
  return queryString ? `?${queryString}` : '';
}

/**
 * Fetch face events with optional filters and pagination.
 */
export async function fetchFaceEvents(
  filters?: FaceEventsFilter,
  cursor?: string
): Promise<FaceEventsResponse> {
  const effectiveFilters = cursor ? { ...filters, cursor } : filters;
  const queryString = buildFaceEventsQueryString(effectiveFilters);
  const response = await fetch(`${BASE_URL}/api/face-events${queryString}`, {
    method: 'GET',
    headers: buildHeaders(),
  });
  return handleResponse<FaceEventsResponse>(response);
}

// --- Face Stats API Functions ---

/**
 * Fetch face detection statistics.
 */
export async function fetchFaceStats(): Promise<FaceStats> {
  const response = await fetch(`${BASE_URL}/api/face-events/stats`, {
    method: 'GET',
    headers: buildHeaders(),
  });
  return handleResponse<FaceStats>(response);
}

// --- Face Events Mutation API Functions ---

/**
 * Identify an unknown face event as a known person.
 */
export async function identifyFace(
  eventId: number,
  data: IdentifyFaceRequest
): Promise<IdentifyFaceResponse> {
  const response = await fetch(`${BASE_URL}/api/face-events/${eventId}/identify`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse<IdentifyFaceResponse>(response);
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook to fetch all known persons.
 */
export function useKnownPersonsQuery() {
  return useQuery({
    queryKey: faceRecognitionQueryKeys.knownPersons(),
    queryFn: fetchKnownPersons,
    staleTime: STATIC_STALE_TIME,
  });
}

/**
 * Hook to fetch a single known person.
 */
export function useKnownPersonQuery(id: number | null) {
  return useQuery({
    queryKey: faceRecognitionQueryKeys.knownPerson(id ?? 0),
    queryFn: () => {
      if (id === null || id <= 0) {
        return Promise.reject(new Error('ID is required'));
      }
      return fetchKnownPerson(id);
    },
    staleTime: STATIC_STALE_TIME,
    enabled: id !== null && id > 0,
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
      void queryClient.invalidateQueries({ queryKey: faceRecognitionQueryKeys.knownPersons() });
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
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: faceRecognitionQueryKeys.knownPersons() });
      void queryClient.invalidateQueries({
        queryKey: faceRecognitionQueryKeys.knownPerson(variables.id),
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
      void queryClient.invalidateQueries({ queryKey: faceRecognitionQueryKeys.knownPersons() });
    },
  });
}

/**
 * Hook to fetch face embeddings for a person.
 */
export function usePersonEmbeddingsQuery(personId: number | null) {
  return useQuery({
    queryKey: faceRecognitionQueryKeys.personEmbeddings(personId ?? 0),
    queryFn: () => {
      if (personId === null || personId <= 0) {
        return Promise.reject(new Error('Person ID is required'));
      }
      return fetchPersonEmbeddings(personId);
    },
    staleTime: STATIC_STALE_TIME,
    enabled: personId !== null && personId > 0,
  });
}

/**
 * Hook to delete a face embedding.
 */
export function useDeleteEmbedding() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ personId, embeddingId }: { personId: number; embeddingId: number }) =>
      deleteEmbedding(personId, embeddingId),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: faceRecognitionQueryKeys.personEmbeddings(variables.personId),
      });
      void queryClient.invalidateQueries({
        queryKey: faceRecognitionQueryKeys.knownPerson(variables.personId),
      });
    },
  });
}

/**
 * Hook to enroll a face from a detection.
 */
export function useEnrollFace() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ personId, detectionId }: { personId: number; detectionId: string }) =>
      enrollFaceFromDetection(personId, { detection_id: detectionId }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: faceRecognitionQueryKeys.personEmbeddings(variables.personId),
      });
      void queryClient.invalidateQueries({
        queryKey: faceRecognitionQueryKeys.knownPerson(variables.personId),
      });
    },
  });
}

/**
 * Hook to fetch person appearances.
 */
export function usePersonAppearancesQuery(personId: number | null, filters?: AppearancesFilter) {
  return useQuery({
    queryKey: faceRecognitionQueryKeys.personAppearances(personId ?? 0, filters),
    queryFn: () => {
      if (personId === null || personId <= 0) {
        return Promise.reject(new Error('Person ID is required'));
      }
      return fetchPersonAppearances(personId, filters);
    },
    staleTime: STATIC_STALE_TIME,
    enabled: personId !== null && personId > 0,
  });
}

/**
 * Hook to fetch face events with infinite scroll support.
 */
export function useFaceEventsQuery(filters?: FaceEventsFilter) {
  return useInfiniteQuery({
    queryKey: faceRecognitionQueryKeys.faceEvents(filters),
    queryFn: ({ pageParam }) => fetchFaceEvents(filters, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    staleTime: REALTIME_STALE_TIME,
  });
}

/**
 * Hook to fetch unknown stranger events.
 * Refetches periodically to check for new unknowns.
 *
 * @param limit - Maximum number of unknown strangers to fetch (optional)
 */
export function useUnknownStrangersQuery(limit?: number) {
  return useQuery({
    queryKey: faceRecognitionQueryKeys.unknownStrangers(limit),
    queryFn: () => fetchUnknownStrangers(limit),
    staleTime: REALTIME_STALE_TIME,
    refetchInterval: 30000, // Check for new unknowns every 30 seconds
  });
}

/**
 * Hook to fetch face detection statistics.
 */
export function useFaceStatsQuery() {
  return useQuery({
    queryKey: faceRecognitionQueryKeys.faceStats(),
    queryFn: fetchFaceStats,
    staleTime: REALTIME_STALE_TIME,
  });
}

/**
 * Hook to identify an unknown face as a known person.
 */
export function useIdentifyFace() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      eventId,
      knownPersonId,
      createEmbedding,
    }: {
      eventId: number;
      knownPersonId: number;
      createEmbedding?: boolean;
    }) =>
      identifyFace(eventId, {
        known_person_id: knownPersonId,
        create_embedding: createEmbedding,
      }),
    onSuccess: () => {
      // Invalidate face events cache
      void queryClient.invalidateQueries({
        queryKey: faceRecognitionQueryKeys.faceEventsAll(),
      });
      // Invalidate unknown strangers cache
      void queryClient.invalidateQueries({
        queryKey: faceRecognitionQueryKeys.unknownStrangers(),
      });
      // Also invalidate face stats
      void queryClient.invalidateQueries({
        queryKey: faceRecognitionQueryKeys.faceStats(),
      });
    },
  });
}

// ============================================================================
// Combined Hook
// ============================================================================

/**
 * Combined hook for face recognition API operations.
 *
 * Provides queries for known persons, face events, and stats,
 * along with mutation functions for CRUD operations.
 */
export function useFaceRecognitionApi() {
  const knownPersonsQuery = useKnownPersonsQuery();
  const unknownStrangersQuery = useUnknownStrangersQuery();
  const faceStatsQuery = useFaceStatsQuery();

  const createKnownPersonMutation = useCreateKnownPerson();
  const updateKnownPersonMutation = useUpdateKnownPerson();
  const deleteKnownPersonMutation = useDeleteKnownPerson();

  const enrollFaceMutation = useEnrollFace();
  const deleteEmbeddingMutation = useDeleteEmbedding();
  const identifyFaceMutation = useIdentifyFace();

  return {
    // Known Persons
    knownPersons: knownPersonsQuery.data,
    knownPersonsLoading: knownPersonsQuery.isLoading,
    knownPersonsError: knownPersonsQuery.error,
    refetchKnownPersons: knownPersonsQuery.refetch,
    createKnownPerson: createKnownPersonMutation,
    updateKnownPerson: updateKnownPersonMutation,
    deleteKnownPerson: deleteKnownPersonMutation,

    // Unknown Strangers
    unknownStrangers: unknownStrangersQuery.data,
    unknownStrangersLoading: unknownStrangersQuery.isLoading,
    unknownStrangersError: unknownStrangersQuery.error,
    refetchUnknownStrangers: unknownStrangersQuery.refetch,

    // Face Stats
    faceStats: faceStatsQuery.data,
    faceStatsLoading: faceStatsQuery.isLoading,
    faceStatsError: faceStatsQuery.error,
    refetchFaceStats: faceStatsQuery.refetch,

    // Mutations
    enrollFace: enrollFaceMutation,
    deleteEmbedding: deleteEmbeddingMutation,
    identifyFace: identifyFaceMutation,
  };
}

// Re-export types for convenience
export type {
  KnownPerson,
  KnownPersonCreate,
  KnownPersonUpdate,
  FaceEmbedding,
  FaceStats,
  FaceEventsFilter,
  FaceEventsResponse,
  EnrollFaceRequest,
  EnrollFaceResponse,
  IdentifyFaceRequest,
  IdentifyFaceResponse,
  AppearancesFilter,
  PersonAppearancesResponse,
  UnknownStrangerSummary,
  PersonAppearance,
} from '../types/faceRecognition';

export default useFaceRecognitionApi;
