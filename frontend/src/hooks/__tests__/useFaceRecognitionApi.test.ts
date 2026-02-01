/**
 * Tests for useFaceRecognitionApi hooks (NEM-4688 Phase 1)
 *
 * Comprehensive tests for face recognition API hooks including known persons
 * management, face embeddings, face events, and person appearances.
 *
 * @see frontend/src/hooks/useFaceRecognitionApi.ts
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

import { QueryClient } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { server } from '../../mocks/server';
import { createQueryWrapper } from '../../test-utils/renderWithProviders';
import {
  useKnownPersonsQuery,
  useKnownPersonQuery,
  useCreateKnownPerson,
  useUpdateKnownPerson,
  useDeleteKnownPerson,
  usePersonEmbeddingsQuery,
  useEnrollFace,
  useDeleteEmbedding,
  useFaceEventsQuery,
  useUnknownStrangersQuery,
  useIdentifyFace,
  useFaceStatsQuery,
  usePersonAppearancesQuery,
  faceRecognitionQueryKeys,
} from '../useFaceRecognitionApi';

import type {
  KnownPerson,
  KnownPersonCreate,
  KnownPersonUpdate,
  FaceEmbedding,
  FaceDetectionEvent,
  FaceStats,
  PersonAppearance,
  EnrollFaceResponse,
  IdentifyFaceResponse,
  FaceEventsResponse,
  PersonAppearancesResponse,
  UnknownStrangerSummary,
} from '../../types/faceRecognition';

// Base URL from environment
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';

// ============================================================================
// Mock Data
// ============================================================================

const mockKnownPerson: KnownPerson = {
  id: 1,
  name: 'John Doe',
  is_household_member: true,
  notes: 'Primary resident',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  embedding_count: 3,
  household_member_id: 1,
};

const mockKnownPerson2: KnownPerson = {
  id: 2,
  name: 'Jane Smith',
  is_household_member: false,
  notes: null,
  created_at: '2024-01-02T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
  embedding_count: 2,
  household_member_id: null,
};

const mockEmbedding: FaceEmbedding = {
  id: 1,
  person_id: 1,
  quality_score: 0.92,
  source_image_path: '/images/face1.jpg',
  created_at: '2024-01-01T00:00:00Z',
};

const mockEmbedding2: FaceEmbedding = {
  id: 2,
  person_id: 1,
  quality_score: 0.88,
  source_image_path: '/images/face2.jpg',
  created_at: '2024-01-02T00:00:00Z',
};

const mockFaceEvent: FaceDetectionEvent = {
  id: 1,
  camera_id: 1,
  camera_name: 'Front Door',
  timestamp: '2024-01-15T10:32:00Z',
  bbox: [100, 50, 80, 100],
  matched_person_id: 1,
  matched_person_name: 'John Doe',
  match_confidence: 0.95,
  is_unknown: false,
  quality_score: 0.89,
  thumbnail_url: '/thumbnails/face1.jpg',
  detection_id: 'det-123',
  event_id: 100,
};

const mockUnknownFaceEvent: FaceDetectionEvent = {
  id: 2,
  camera_id: 2,
  camera_name: 'Driveway',
  timestamp: '2024-01-15T10:28:00Z',
  bbox: [150, 60, 70, 90],
  matched_person_id: null,
  matched_person_name: null,
  match_confidence: null,
  is_unknown: true,
  quality_score: 0.85,
  thumbnail_url: '/thumbnails/unknown1.jpg',
  detection_id: 'det-124',
  event_id: 101,
};

const mockFaceStats: FaceStats = {
  total_today: 47,
  known_count: 38,
  unknown_count: 9,
  by_camera: {
    'Front Door': { total: 20, known: 18, unknown: 2 },
    Driveway: { total: 15, known: 12, unknown: 3 },
    Backyard: { total: 12, known: 8, unknown: 4 },
  },
  unique_known_persons: 5,
  unique_unknown_faces: 7,
};

const mockAppearance: PersonAppearance = {
  timestamp: '2024-01-15T10:32:00Z',
  camera_id: 1,
  camera_name: 'Front Door',
  detection_id: 'det-123',
  confidence: 0.95,
  thumbnail_url: '/thumbnails/face1.jpg',
  event_id: 100,
};

const mockAppearance2: PersonAppearance = {
  timestamp: '2024-01-15T08:15:00Z',
  camera_id: 2,
  camera_name: 'Driveway',
  detection_id: 'det-120',
  confidence: 0.92,
  thumbnail_url: '/thumbnails/face2.jpg',
  event_id: 98,
};

// ============================================================================
// Tests - Known Persons
// ============================================================================

describe('useKnownPersonsQuery', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE_URL}/api/known-persons`, () => {
        return HttpResponse.json([mockKnownPerson, mockKnownPerson2]);
      })
    );
  });

  it('fetches known persons successfully', async () => {
    const { result } = renderHook(() => useKnownPersonsQuery(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual([mockKnownPerson, mockKnownPerson2]);
    expect(result.current.error).toBeNull();
  });

  it('handles empty persons list', async () => {
    server.use(
      http.get(`${BASE_URL}/api/known-persons`, () => {
        return HttpResponse.json([]);
      })
    );

    const { result } = renderHook(() => useKnownPersonsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual([]);
  });

  it('handles fetch error', async () => {
    server.use(
      http.get(`${BASE_URL}/api/known-persons`, () => {
        return HttpResponse.json({ detail: 'Internal server error' }, { status: 500 });
      })
    );

    const { result } = renderHook(() => useKnownPersonsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.error).not.toBeNull();
      },
      { timeout: 3000 }
    );

    expect(result.current.data).toBeUndefined();
    expect(result.current.error?.message).toContain('Internal server error');
  });
});

describe('useKnownPersonQuery', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE_URL}/api/known-persons/:id`, ({ params }) => {
        const id = Number(params.id);
        if (id === 1) {
          return HttpResponse.json(mockKnownPerson);
        }
        return HttpResponse.json({ detail: 'Person not found' }, { status: 404 });
      })
    );
  });

  it('fetches a single known person successfully', async () => {
    const { result } = renderHook(() => useKnownPersonQuery(1), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockKnownPerson);
    expect(result.current.error).toBeNull();
  });

  it('handles non-existent person', async () => {
    const { result } = renderHook(() => useKnownPersonQuery(999), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.error).not.toBeNull();
      },
      { timeout: 3000 }
    );

    expect(result.current.error?.message).toContain('Person not found');
  });

  it('disables query when id is 0', () => {
    const { result } = renderHook(() => useKnownPersonQuery(0), {
      wrapper: createQueryWrapper(),
    });

    // Should not fetch when disabled
    expect(result.current.isLoading).toBe(false);
    expect(result.current.isFetching).toBe(false);
    expect(result.current.data).toBeUndefined();
  });
});

describe('useCreateKnownPerson', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.post(`${BASE_URL}/api/known-persons`, async ({ request }) => {
        const body = (await request.json()) as KnownPersonCreate;
        return HttpResponse.json({
          id: 3,
          ...body,
          is_household_member: body.is_household_member ?? false,
          embedding_count: 0,
          created_at: '2024-01-03T00:00:00Z',
          updated_at: '2024-01-03T00:00:00Z',
        } as KnownPerson);
      })
    );
  });

  it('creates a new known person successfully', async () => {
    const { result } = renderHook(() => useCreateKnownPerson(), {
      wrapper: createQueryWrapper(queryClient),
    });

    const newPerson: KnownPersonCreate = {
      name: 'Bob Johnson',
      is_household_member: false,
      notes: 'Neighbor',
    };

    let created: KnownPerson | undefined;
    await act(async () => {
      created = await result.current.mutateAsync(newPerson);
    });

    expect(created!.id).toBe(3);
    expect(created!.name).toBe('Bob Johnson');
    expect(created!.embedding_count).toBe(0);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('invalidates known persons cache after creation', async () => {
    queryClient.setQueryData(faceRecognitionQueryKeys.knownPersons(), [mockKnownPerson]);
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useCreateKnownPerson(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({ name: 'New Person' });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: faceRecognitionQueryKeys.knownPersons(),
    });
  });

  it('handles creation error', async () => {
    server.use(
      http.post(`${BASE_URL}/api/known-persons`, () => {
        return HttpResponse.json({ detail: 'Name is required' }, { status: 400 });
      })
    );

    const { result } = renderHook(() => useCreateKnownPerson(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      try {
        await result.current.mutateAsync({ name: '' });
      } catch (error) {
        expect(error).toBeDefined();
      }
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error?.message).toContain('Name is required');
  });
});

describe('useUpdateKnownPerson', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.patch(`${BASE_URL}/api/known-persons/:id`, async ({ request, params }) => {
        const body = (await request.json()) as KnownPersonUpdate;
        const id = Number(params.id);
        return HttpResponse.json({
          ...mockKnownPerson,
          id,
          ...body,
          updated_at: '2024-01-04T00:00:00Z',
        } as KnownPerson);
      })
    );
  });

  it('updates a known person successfully', async () => {
    const { result } = renderHook(() => useUpdateKnownPerson(), {
      wrapper: createQueryWrapper(queryClient),
    });

    const update: KnownPersonUpdate = {
      name: 'John Doe Updated',
      notes: 'Updated notes',
    };

    let updated: KnownPerson | undefined;
    await act(async () => {
      updated = await result.current.mutateAsync({ id: 1, data: update });
    });

    expect(updated!.name).toBe('John Doe Updated');
    expect(updated!.notes).toBe('Updated notes');

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('invalidates known persons cache after update', async () => {
    queryClient.setQueryData(faceRecognitionQueryKeys.knownPersons(), [mockKnownPerson]);
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useUpdateKnownPerson(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({ id: 1, data: { name: 'Updated' } });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: faceRecognitionQueryKeys.knownPersons(),
    });
  });
});

describe('useDeleteKnownPerson', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.delete(`${BASE_URL}/api/known-persons/:id`, () => {
        return new HttpResponse(null, { status: 204 });
      })
    );
  });

  it('deletes a known person successfully', async () => {
    const { result } = renderHook(() => useDeleteKnownPerson(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync(1);
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.error).toBeNull();
  });

  it('invalidates known persons cache after deletion', async () => {
    queryClient.setQueryData(faceRecognitionQueryKeys.knownPersons(), [
      mockKnownPerson,
      mockKnownPerson2,
    ]);
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useDeleteKnownPerson(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync(1);
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: faceRecognitionQueryKeys.knownPersons(),
    });
  });

  it('handles deletion error for non-existent person', async () => {
    server.use(
      http.delete(`${BASE_URL}/api/known-persons/:id`, () => {
        return HttpResponse.json({ detail: 'Person not found' }, { status: 404 });
      })
    );

    const { result } = renderHook(() => useDeleteKnownPerson(), {
      wrapper: createQueryWrapper(queryClient),
    });

    let caughtError: Error | undefined;
    await act(async () => {
      try {
        await result.current.mutateAsync(999);
      } catch (error) {
        caughtError = error as Error;
      }
    });

    expect(caughtError).toBeDefined();
    expect(caughtError!.message).toContain('Person not found');
  });
});

// ============================================================================
// Tests - Face Embeddings
// ============================================================================

describe('usePersonEmbeddingsQuery', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE_URL}/api/known-persons/:id/embeddings`, ({ params }) => {
        const id = Number(params.id);
        if (id === 1) {
          return HttpResponse.json([mockEmbedding, mockEmbedding2]);
        }
        return HttpResponse.json([]);
      })
    );
  });

  it('fetches embeddings for a person successfully', async () => {
    const { result } = renderHook(() => usePersonEmbeddingsQuery(1), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual([mockEmbedding, mockEmbedding2]);
    expect(result.current.error).toBeNull();
  });

  it('handles empty embeddings list', async () => {
    const { result } = renderHook(() => usePersonEmbeddingsQuery(2), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual([]);
  });

  it('disables query when personId is 0', () => {
    const { result } = renderHook(() => usePersonEmbeddingsQuery(0), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.isFetching).toBe(false);
  });
});

describe('useEnrollFace', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.post(`${BASE_URL}/api/known-persons/:id/enroll-from-detection`, () => {
        return HttpResponse.json({
          success: true,
          embedding_id: 3,
          quality_score: 0.85,
          message: 'Face enrolled successfully',
        } as EnrollFaceResponse);
      })
    );
  });

  it('enrolls a face successfully', async () => {
    const { result } = renderHook(() => useEnrollFace(), {
      wrapper: createQueryWrapper(queryClient),
    });

    let response: EnrollFaceResponse | undefined;
    await act(async () => {
      response = await result.current.mutateAsync({
        personId: 1,
        detectionId: 'det-123',
      });
    });

    expect(response!.success).toBe(true);
    expect(response!.embedding_id).toBe(3);
    expect(response!.quality_score).toBe(0.85);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('invalidates person embeddings cache after enrollment', async () => {
    queryClient.setQueryData(faceRecognitionQueryKeys.personEmbeddings(1), [mockEmbedding]);
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useEnrollFace(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({ personId: 1, detectionId: 'det-123' });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: faceRecognitionQueryKeys.knownPerson(1),
    });
  });

  it('handles enrollment error for low quality face', async () => {
    server.use(
      http.post(`${BASE_URL}/api/known-persons/:id/enroll-from-detection`, () => {
        return HttpResponse.json(
          { detail: 'Face quality too low for enrollment (score: 0.5)' },
          { status: 400 }
        );
      })
    );

    const { result } = renderHook(() => useEnrollFace(), {
      wrapper: createQueryWrapper(queryClient),
    });

    let thrownError: Error | undefined;
    await act(async () => {
      try {
        await result.current.mutateAsync({ personId: 1, detectionId: 'det-123' });
      } catch (error) {
        thrownError = error as Error;
      }
    });

    expect(thrownError).toBeDefined();
    expect(thrownError?.message).toContain('Face quality too low');
  });
});

describe('useDeleteEmbedding', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.delete(`${BASE_URL}/api/known-persons/:personId/embeddings/:embeddingId`, () => {
        return new HttpResponse(null, { status: 204 });
      })
    );
  });

  it('deletes an embedding successfully', async () => {
    const { result } = renderHook(() => useDeleteEmbedding(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({ personId: 1, embeddingId: 1 });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('invalidates embeddings cache after deletion', async () => {
    queryClient.setQueryData(faceRecognitionQueryKeys.personEmbeddings(1), [
      mockEmbedding,
      mockEmbedding2,
    ]);
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useDeleteEmbedding(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({ personId: 1, embeddingId: 1 });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: faceRecognitionQueryKeys.personEmbeddings(1),
    });
  });
});

// ============================================================================
// Tests - Face Events
// ============================================================================

describe('useFaceEventsQuery', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE_URL}/api/face-events`, () => {
        return HttpResponse.json({
          items: [mockFaceEvent, mockUnknownFaceEvent],
          next_cursor: null,
          total: 2,
        } as FaceEventsResponse);
      })
    );
  });

  it('fetches face events successfully', async () => {
    const { result } = renderHook(() => useFaceEventsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data?.pages[0].items).toEqual([mockFaceEvent, mockUnknownFaceEvent]);
    expect(result.current.error).toBeNull();
  });

  it('fetches face events with filters', async () => {
    server.use(
      http.get(`${BASE_URL}/api/face-events`, ({ request }) => {
        const url = new URL(request.url);
        const unknownOnly = url.searchParams.get('unknown_only');
        if (unknownOnly === 'true') {
          return HttpResponse.json({
            items: [mockUnknownFaceEvent],
            next_cursor: null,
            total: 1,
          } as FaceEventsResponse);
        }
        return HttpResponse.json({
          items: [mockFaceEvent, mockUnknownFaceEvent],
          next_cursor: null,
          total: 2,
        } as FaceEventsResponse);
      })
    );

    const { result } = renderHook(() => useFaceEventsQuery({ unknown_only: true }), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data?.pages[0].items).toEqual([mockUnknownFaceEvent]);
  });

  it('supports infinite scrolling with pagination', async () => {
    server.use(
      http.get(`${BASE_URL}/api/face-events`, ({ request }) => {
        const url = new URL(request.url);
        const cursor = url.searchParams.get('cursor');
        if (cursor === 'page2') {
          return HttpResponse.json({
            items: [mockUnknownFaceEvent],
            next_cursor: null,
            total: 2,
          } as FaceEventsResponse);
        }
        return HttpResponse.json({
          items: [mockFaceEvent],
          next_cursor: 'page2',
          total: 2,
        } as FaceEventsResponse);
      })
    );

    const { result } = renderHook(() => useFaceEventsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.hasNextPage).toBe(true);

    // Fetch next page
    await act(async () => {
      await result.current.fetchNextPage();
    });

    await waitFor(() => {
      expect(result.current.data?.pages.length).toBe(2);
    });

    expect(result.current.hasNextPage).toBe(false);
  });
});

describe('useUnknownStrangersQuery', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE_URL}/api/face-events/unknown`, () => {
        return HttpResponse.json({
          items: [mockUnknownFaceEvent],
          total: 1,
          has_more: false,
        } as UnknownStrangerSummary);
      })
    );
  });

  it('fetches unknown strangers successfully', async () => {
    const { result } = renderHook(() => useUnknownStrangersQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data?.items).toEqual([mockUnknownFaceEvent]);
    expect(result.current.data?.total).toBe(1);
    expect(result.current.error).toBeNull();
  });

  it('handles empty unknown strangers list', async () => {
    server.use(
      http.get(`${BASE_URL}/api/face-events/unknown`, () => {
        return HttpResponse.json({
          items: [],
          total: 0,
          has_more: false,
        } as UnknownStrangerSummary);
      })
    );

    const { result } = renderHook(() => useUnknownStrangersQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data?.items).toEqual([]);
    expect(result.current.data?.total).toBe(0);
  });
});

describe('useIdentifyFace', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.post(`${BASE_URL}/api/face-events/:eventId/identify`, () => {
        return HttpResponse.json({
          success: true,
          created_embedding: true,
          message: 'Face identified and embedding created',
        } as IdentifyFaceResponse);
      })
    );
  });

  it('identifies a face successfully', async () => {
    const { result } = renderHook(() => useIdentifyFace(), {
      wrapper: createQueryWrapper(queryClient),
    });

    let response: IdentifyFaceResponse | undefined;
    await act(async () => {
      response = await result.current.mutateAsync({
        eventId: 2,
        knownPersonId: 1,
        createEmbedding: true,
      });
    });

    expect(response!.success).toBe(true);
    expect(response!.created_embedding).toBe(true);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('invalidates face events and unknown strangers cache after identification', async () => {
    queryClient.setQueryData(faceRecognitionQueryKeys.faceEvents(), {
      pages: [{ items: [mockFaceEvent, mockUnknownFaceEvent], next_cursor: null, total: 2 }],
      pageParams: [undefined],
    });
    queryClient.setQueryData(faceRecognitionQueryKeys.unknownStrangers(), {
      items: [mockUnknownFaceEvent],
      total: 1,
      has_more: false,
    });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useIdentifyFace(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({ eventId: 2, knownPersonId: 1 });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: faceRecognitionQueryKeys.faceEventsAll(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: faceRecognitionQueryKeys.unknownStrangers(),
    });
  });
});

describe('useFaceStatsQuery', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE_URL}/api/face-events/stats`, () => {
        return HttpResponse.json(mockFaceStats);
      })
    );
  });

  it('fetches face stats successfully', async () => {
    const { result } = renderHook(() => useFaceStatsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockFaceStats);
    expect(result.current.data?.total_today).toBe(47);
    expect(result.current.data?.known_count).toBe(38);
    expect(result.current.data?.unknown_count).toBe(9);
    expect(result.current.error).toBeNull();
  });

  it('handles stats fetch error', async () => {
    server.use(
      http.get(`${BASE_URL}/api/face-events/stats`, () => {
        return HttpResponse.json({ detail: 'Service unavailable' }, { status: 503 });
      })
    );

    const { result } = renderHook(() => useFaceStatsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.error).not.toBeNull();
      },
      { timeout: 3000 }
    );

    expect(result.current.error?.message).toContain('Service unavailable');
  });
});

// ============================================================================
// Tests - Person Appearances
// ============================================================================

describe('usePersonAppearancesQuery', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE_URL}/api/known-persons/:id/appearances`, ({ params }) => {
        const id = Number(params.id);
        if (id === 1) {
          return HttpResponse.json({
            appearances: [mockAppearance, mockAppearance2],
            total: 2,
          } as PersonAppearancesResponse);
        }
        return HttpResponse.json({
          appearances: [],
          total: 0,
        } as PersonAppearancesResponse);
      })
    );
  });

  it('fetches person appearances successfully', async () => {
    const { result } = renderHook(
      () =>
        usePersonAppearancesQuery(1, {
          start_date: '2024-01-01',
          end_date: '2024-01-31',
        }),
      {
        wrapper: createQueryWrapper(),
      }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data?.appearances).toEqual([mockAppearance, mockAppearance2]);
    expect(result.current.data?.total).toBe(2);
    expect(result.current.error).toBeNull();
  });

  it('handles empty appearances list', async () => {
    const { result } = renderHook(
      () =>
        usePersonAppearancesQuery(2, {
          start_date: '2024-01-01',
          end_date: '2024-01-31',
        }),
      {
        wrapper: createQueryWrapper(),
      }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data?.appearances).toEqual([]);
    expect(result.current.data?.total).toBe(0);
  });

  it('disables query when personId is 0', () => {
    const { result } = renderHook(() => usePersonAppearancesQuery(0), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.isFetching).toBe(false);
    expect(result.current.data).toBeUndefined();
  });

  it('passes filter parameters correctly', async () => {
    let capturedUrl: URL | null = null;

    server.use(
      http.get(`${BASE_URL}/api/known-persons/:id/appearances`, ({ request }) => {
        capturedUrl = new URL(request.url);
        return HttpResponse.json({
          appearances: [mockAppearance],
          total: 1,
        } as PersonAppearancesResponse);
      })
    );

    const { result } = renderHook(
      () =>
        usePersonAppearancesQuery(1, {
          start_date: '2024-01-01',
          end_date: '2024-01-31',
          camera_id: 1,
          limit: 50,
        }),
      {
        wrapper: createQueryWrapper(),
      }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(capturedUrl).not.toBeNull();
    expect(capturedUrl!.searchParams.get('start_date')).toBe('2024-01-01');
    expect(capturedUrl!.searchParams.get('end_date')).toBe('2024-01-31');
    expect(capturedUrl!.searchParams.get('camera_id')).toBe('1');
    expect(capturedUrl!.searchParams.get('limit')).toBe('50');
  });
});

// ============================================================================
// Tests - Query Keys
// ============================================================================

describe('faceRecognitionQueryKeys', () => {
  it('generates correct base key', () => {
    expect(faceRecognitionQueryKeys.all).toEqual(['face-recognition']);
  });

  it('generates correct known persons keys', () => {
    expect(faceRecognitionQueryKeys.knownPersons()).toEqual(['face-recognition', 'known-persons']);
    expect(faceRecognitionQueryKeys.knownPerson(1)).toEqual([
      'face-recognition',
      'known-persons',
      1,
    ]);
  });

  it('generates correct embeddings keys', () => {
    expect(faceRecognitionQueryKeys.personEmbeddings(1)).toEqual([
      'face-recognition',
      'known-persons',
      1,
      'embeddings',
    ]);
  });

  it('generates correct face events keys', () => {
    expect(faceRecognitionQueryKeys.faceEventsAll()).toEqual(['face-recognition', 'face-events']);
    expect(faceRecognitionQueryKeys.faceEvents()).toEqual([
      'face-recognition',
      'face-events',
      'list',
      undefined,
    ]);
    expect(faceRecognitionQueryKeys.faceEvents({ unknown_only: true })).toEqual([
      'face-recognition',
      'face-events',
      'list',
      { unknown_only: true },
    ]);
  });

  it('generates correct unknown strangers key', () => {
    expect(faceRecognitionQueryKeys.unknownStrangers()).toEqual([
      'face-recognition',
      'face-events',
      'unknown',
      undefined,
    ]);
    expect(faceRecognitionQueryKeys.unknownStrangers(10)).toEqual([
      'face-recognition',
      'face-events',
      'unknown',
      10,
    ]);
  });

  it('generates correct face stats key', () => {
    expect(faceRecognitionQueryKeys.faceStats()).toEqual([
      'face-recognition',
      'face-events',
      'stats',
    ]);
  });

  it('generates correct appearances keys', () => {
    expect(faceRecognitionQueryKeys.personAppearances(1)).toEqual([
      'face-recognition',
      'known-persons',
      1,
      'appearances',
      undefined,
    ]);
    expect(
      faceRecognitionQueryKeys.personAppearances(1, { start_date: '2024-01-01' })
    ).toEqual([
      'face-recognition',
      'known-persons',
      1,
      'appearances',
      { start_date: '2024-01-01' },
    ]);
  });
});
