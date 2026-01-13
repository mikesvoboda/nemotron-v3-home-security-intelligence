/**
 * Tests for useZones hooks (NEM-2552)
 *
 * This module tests the zone CRUD hooks:
 * - useZonesQuery: Fetch all zones for a camera
 * - useZoneQuery: Fetch a single zone by ID
 * - useZoneMutation: Create, update, and delete zones with optimistic updates
 */
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useZonesQuery,
  useZoneQuery,
  useZoneMutation,
} from './useZones';
import * as api from '../services/api';
import { createQueryClient, queryKeys } from '../services/queryClient';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { Zone, ZoneCreate, ZoneUpdate, ZoneListResponse } from '../services/api';

// Mock the API module - include all exports used by queryClient.ts
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    fetchZones: vi.fn(),
    fetchZone: vi.fn(),
    createZone: vi.fn(),
    updateZone: vi.fn(),
    deleteZone: vi.fn(),
  };
});

describe('useZonesQuery', () => {
  // Helper to create mock zone data
  const createMockZone = (overrides: Partial<Zone> = {}): Zone => ({
    id: 'zone-' + Math.random().toString(36).slice(2, 9),
    camera_id: 'cam-123',
    name: 'Test Zone',
    zone_type: 'entry_point',
    coordinates: [
      [0, 0],
      [100, 0],
      [100, 100],
      [0, 100],
    ],
    shape: 'polygon',
    color: '#FF0000',
    enabled: true,
    priority: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  });

  // Helper to create mock zone list response
  const createMockZoneListResponse = (
    zones: Zone[],
    pagination?: Partial<ZoneListResponse['pagination']>
  ): ZoneListResponse => ({
    items: zones,
    pagination: {
      total: zones.length,
      limit: 50,
      has_more: false,
      ...pagination,
    },
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true when fetching', () => {
      (api.fetchZones as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {}) // Never resolving
      );

      const { result } = renderHook(() => useZonesQuery('cam-123'), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.zones).toEqual([]);
    });

    it('starts with empty zones array', () => {
      (api.fetchZones as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => useZonesQuery('cam-123'), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.zones).toEqual([]);
      expect(result.current.total).toBe(0);
    });
  });

  describe('fetching data', () => {
    it('fetches zones for camera on mount', async () => {
      const mockZones = [createMockZone()];
      (api.fetchZones as ReturnType<typeof vi.fn>).mockResolvedValue(
        createMockZoneListResponse(mockZones)
      );

      renderHook(() => useZonesQuery('cam-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchZones).toHaveBeenCalledWith('cam-123', undefined);
      });
    });

    it('updates zones after successful fetch', async () => {
      const mockZones = [
        createMockZone({ id: 'zone-1', name: 'Entry Zone' }),
        createMockZone({ id: 'zone-2', name: 'Parking Zone' }),
      ];
      (api.fetchZones as ReturnType<typeof vi.fn>).mockResolvedValue(
        createMockZoneListResponse(mockZones)
      );

      const { result } = renderHook(() => useZonesQuery('cam-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.zones).toEqual(mockZones);
      });

      expect(result.current.total).toBe(2);
    });

    it('sets isLoading false after fetch', async () => {
      (api.fetchZones as ReturnType<typeof vi.fn>).mockResolvedValue(
        createMockZoneListResponse([])
      );

      const { result } = renderHook(() => useZonesQuery('cam-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch zones';
      (api.fetchZones as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useZonesQuery('cam-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useZonesQuery('cam-123', { enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchZones).not.toHaveBeenCalled();
    });

    it('does not fetch when cameraId is undefined', async () => {
      renderHook(() => useZonesQuery(undefined), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchZones).not.toHaveBeenCalled();
    });
  });

  describe('enabledFilter option', () => {
    it('passes enabled filter to API', async () => {
      (api.fetchZones as ReturnType<typeof vi.fn>).mockResolvedValue(
        createMockZoneListResponse([])
      );

      renderHook(() => useZonesQuery('cam-123', { enabledFilter: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchZones).toHaveBeenCalledWith('cam-123', true);
      });
    });
  });

  describe('refetch function', () => {
    it('provides refetch function', async () => {
      (api.fetchZones as ReturnType<typeof vi.fn>).mockResolvedValue(
        createMockZoneListResponse([])
      );

      const { result } = renderHook(() => useZonesQuery('cam-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });
});

describe('useZoneQuery', () => {
  const createMockZone = (overrides: Partial<Zone> = {}): Zone => ({
    id: 'zone-123',
    camera_id: 'cam-123',
    name: 'Test Zone',
    zone_type: 'entry_point',
    coordinates: [[0, 0], [100, 100], [100, 0]],
    shape: 'polygon',
    color: '#FF0000',
    enabled: true,
    priority: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches single zone by ID', async () => {
    const mockZone = createMockZone();
    (api.fetchZone as ReturnType<typeof vi.fn>).mockResolvedValue(mockZone);

    renderHook(() => useZoneQuery('cam-123', 'zone-123'), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(api.fetchZone).toHaveBeenCalledWith('cam-123', 'zone-123');
    });
  });

  it('returns zone data', async () => {
    const mockZone = createMockZone({ name: 'Front Door Zone' });
    (api.fetchZone as ReturnType<typeof vi.fn>).mockResolvedValue(mockZone);

    const { result } = renderHook(() => useZoneQuery('cam-123', 'zone-123'), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockZone);
    });
  });

  it('does not fetch when cameraId is undefined', async () => {
    renderHook(() => useZoneQuery(undefined, 'zone-123'), {
      wrapper: createQueryWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(api.fetchZone).not.toHaveBeenCalled();
  });

  it('does not fetch when zoneId is undefined', async () => {
    renderHook(() => useZoneQuery('cam-123', undefined), {
      wrapper: createQueryWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(api.fetchZone).not.toHaveBeenCalled();
  });
});

describe('useZoneMutation', () => {
  // Helper to create mock zone data
  const createMockZone = (overrides: Partial<Zone> = {}): Zone => ({
    id: 'zone-' + Math.random().toString(36).slice(2, 9),
    camera_id: 'cam-123',
    name: 'Test Zone',
    zone_type: 'entry_point',
    coordinates: [
      [0, 0],
      [100, 0],
      [100, 100],
      [0, 100],
    ],
    shape: 'polygon',
    color: '#FF0000',
    enabled: true,
    priority: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  });

  // Helper to create mock zone list response
  const createMockZoneListResponse = (zones: Zone[]): ZoneListResponse => ({
    items: zones,
    pagination: {
      total: zones.length,
      limit: 50,
      has_more: false,
    },
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('createMutation', () => {
    it('creates a new zone', async () => {
      const newZone = createMockZone({ id: 'zone-new', name: 'New Zone' });
      (api.createZone as ReturnType<typeof vi.fn>).mockResolvedValue(newZone);

      const queryClient = createQueryClient();
      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      const zoneData: ZoneCreate = {
        name: 'New Zone',
        zone_type: 'entry_point',
        coordinates: [[0, 0], [100, 100], [100, 0]],
        color: '#3B82F6',
        enabled: true,
        priority: 0,
        shape: 'polygon',
      };

      await act(async () => {
        await result.current.createMutation.mutateAsync({
          cameraId: 'cam-123',
          data: zoneData,
        });
      });

      expect(api.createZone).toHaveBeenCalledWith('cam-123', zoneData);
    });

    it('applies optimistic update with temporary ID', async () => {
      // Slow down the API response to observe optimistic update
      let resolveCreate: (zone: Zone) => void;
      const createPromise = new Promise<Zone>((resolve) => {
        resolveCreate = resolve;
      });
      (api.createZone as ReturnType<typeof vi.fn>).mockReturnValue(createPromise);

      const queryClient = createQueryClient();
      // Pre-populate cache with existing zones
      const existingZone = createMockZone({ id: 'zone-existing' });
      queryClient.setQueryData(
        queryKeys.cameras.zones('cam-123'),
        createMockZoneListResponse([existingZone])
      );

      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      const zoneData: ZoneCreate = {
        name: 'New Zone',
        zone_type: 'entry_point',
        coordinates: [[0, 0], [100, 100], [100, 0]],
        color: '#3B82F6',
        enabled: true,
        priority: 0,
        shape: 'polygon',
      };

      // Start the mutation
      act(() => {
        result.current.createMutation.mutate({
          cameraId: 'cam-123',
          data: zoneData,
        });
      });

      // Check optimistic update happened
      await waitFor(() => {
        const cacheData = queryClient.getQueryData<ZoneListResponse>(
          queryKeys.cameras.zones('cam-123')
        );
        // Should have 2 zones now (existing + optimistic)
        expect(cacheData?.items).toHaveLength(2);
        // The new zone should have a temp ID
        const newZone = cacheData?.items.find((z) => z.name === 'New Zone');
        expect(newZone?.id).toMatch(/^temp-/);
      });

      // Resolve the promise
      const createdZone = createMockZone({ id: 'zone-real-id', name: 'New Zone' });
      act(() => {
        resolveCreate!(createdZone);
      });

      await waitFor(() => {
        expect(result.current.createMutation.isSuccess).toBe(true);
      });
    });

    it('invalidates zones cache after create', async () => {
      const newZone = createMockZone({ id: 'zone-new' });
      (api.createZone as ReturnType<typeof vi.fn>).mockResolvedValue(newZone);

      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.createMutation.mutateAsync({
          cameraId: 'cam-123',
          data: {
            name: 'Test',
            zone_type: 'entry_point',
            coordinates: [[0, 0], [100, 0], [100, 100]],
            color: '#3B82F6',
            enabled: true,
            priority: 0,
            shape: 'polygon',
          },
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.cameras.zones('cam-123'),
      });
    });

    it('rolls back optimistic update on error', async () => {
      const error = new Error('Create failed');
      (api.createZone as ReturnType<typeof vi.fn>).mockRejectedValue(error);

      const queryClient = createQueryClient();
      const existingZone = createMockZone({ id: 'zone-existing' });
      queryClient.setQueryData(
        queryKeys.cameras.zones('cam-123'),
        createMockZoneListResponse([existingZone])
      );

      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        try {
          await result.current.createMutation.mutateAsync({
            cameraId: 'cam-123',
            data: {
              name: 'New Zone',
              zone_type: 'entry_point',
              coordinates: [[0, 0], [100, 0], [100, 100]],
              color: '#3B82F6',
              enabled: true,
              priority: 0,
              shape: 'polygon',
            },
          });
        } catch {
          // Expected to throw
        }
      });

      // Should have rolled back to only the existing zone
      await waitFor(() => {
        const cacheData = queryClient.getQueryData<ZoneListResponse>(
          queryKeys.cameras.zones('cam-123')
        );
        expect(cacheData?.items).toHaveLength(1);
        expect(cacheData?.items[0].id).toBe('zone-existing');
      });
    });
  });

  describe('updateMutation', () => {
    it('updates an existing zone', async () => {
      const updatedZone = createMockZone({ id: 'zone-123', name: 'Updated Name' });
      (api.updateZone as ReturnType<typeof vi.fn>).mockResolvedValue(updatedZone);

      const queryClient = createQueryClient();
      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      const updateData: ZoneUpdate = { name: 'Updated Name' };

      await act(async () => {
        await result.current.updateMutation.mutateAsync({
          cameraId: 'cam-123',
          zoneId: 'zone-123',
          data: updateData,
        });
      });

      expect(api.updateZone).toHaveBeenCalledWith('cam-123', 'zone-123', updateData);
    });

    it('applies optimistic update for partial updates', async () => {
      let resolveUpdate: (zone: Zone) => void;
      const updatePromise = new Promise<Zone>((resolve) => {
        resolveUpdate = resolve;
      });
      (api.updateZone as ReturnType<typeof vi.fn>).mockReturnValue(updatePromise);

      const queryClient = createQueryClient();
      const existingZone = createMockZone({
        id: 'zone-123',
        name: 'Original Name',
        enabled: true,
      });
      queryClient.setQueryData(
        queryKeys.cameras.zones('cam-123'),
        createMockZoneListResponse([existingZone])
      );

      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Start the mutation with partial update
      act(() => {
        result.current.updateMutation.mutate({
          cameraId: 'cam-123',
          zoneId: 'zone-123',
          data: { name: 'New Name' },
        });
      });

      // Check optimistic update happened
      await waitFor(() => {
        const cacheData = queryClient.getQueryData<ZoneListResponse>(
          queryKeys.cameras.zones('cam-123')
        );
        expect(cacheData?.items[0].name).toBe('New Name');
        // Other fields should remain unchanged
        expect(cacheData?.items[0].enabled).toBe(true);
      });

      // Resolve
      const updatedZone = createMockZone({ id: 'zone-123', name: 'New Name' });
      act(() => {
        resolveUpdate!(updatedZone);
      });

      await waitFor(() => {
        expect(result.current.updateMutation.isSuccess).toBe(true);
      });
    });

    it('supports coordinate updates for redrawing zone boundaries', async () => {
      const newCoordinates: number[][] = [
        [10, 10],
        [200, 10],
        [200, 200],
        [10, 200],
      ];

      const updatedZone = createMockZone({
        id: 'zone-123',
        coordinates: newCoordinates,
      });
      (api.updateZone as ReturnType<typeof vi.fn>).mockResolvedValue(updatedZone);

      const queryClient = createQueryClient();
      const existingZone = createMockZone({
        id: 'zone-123',
        coordinates: [[0, 0], [100, 100], [100, 0]],
      });
      queryClient.setQueryData(
        queryKeys.cameras.zones('cam-123'),
        createMockZoneListResponse([existingZone])
      );

      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.updateMutation.mutateAsync({
          cameraId: 'cam-123',
          zoneId: 'zone-123',
          data: { coordinates: newCoordinates },
        });
      });

      expect(api.updateZone).toHaveBeenCalledWith('cam-123', 'zone-123', {
        coordinates: newCoordinates,
      });
    });

    it('invalidates zones cache after update', async () => {
      const updatedZone = createMockZone({ id: 'zone-123' });
      (api.updateZone as ReturnType<typeof vi.fn>).mockResolvedValue(updatedZone);

      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.updateMutation.mutateAsync({
          cameraId: 'cam-123',
          zoneId: 'zone-123',
          data: { name: 'Updated' },
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.cameras.zones('cam-123'),
      });
    });

    it('rolls back optimistic update on error', async () => {
      const error = new Error('Update failed');
      (api.updateZone as ReturnType<typeof vi.fn>).mockRejectedValue(error);

      const queryClient = createQueryClient();
      const existingZone = createMockZone({
        id: 'zone-123',
        name: 'Original Name',
      });
      queryClient.setQueryData(
        queryKeys.cameras.zones('cam-123'),
        createMockZoneListResponse([existingZone])
      );

      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        try {
          await result.current.updateMutation.mutateAsync({
            cameraId: 'cam-123',
            zoneId: 'zone-123',
            data: { name: 'New Name' },
          });
        } catch {
          // Expected to throw
        }
      });

      // Should have rolled back
      await waitFor(() => {
        const cacheData = queryClient.getQueryData<ZoneListResponse>(
          queryKeys.cameras.zones('cam-123')
        );
        expect(cacheData?.items[0].name).toBe('Original Name');
      });
    });
  });

  describe('deleteMutation', () => {
    it('deletes a zone', async () => {
      (api.deleteZone as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);

      const queryClient = createQueryClient();
      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.deleteMutation.mutateAsync({
          cameraId: 'cam-123',
          zoneId: 'zone-123',
        });
      });

      expect(api.deleteZone).toHaveBeenCalledWith('cam-123', 'zone-123');
    });

    it('applies optimistic update with immediate removal', async () => {
      let resolveDelete: () => void;
      const deletePromise = new Promise<void>((resolve) => {
        resolveDelete = resolve;
      });
      (api.deleteZone as ReturnType<typeof vi.fn>).mockReturnValue(deletePromise);

      const queryClient = createQueryClient();
      const zone1 = createMockZone({ id: 'zone-1', name: 'Zone 1' });
      const zone2 = createMockZone({ id: 'zone-2', name: 'Zone 2' });
      queryClient.setQueryData(
        queryKeys.cameras.zones('cam-123'),
        createMockZoneListResponse([zone1, zone2])
      );

      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Start the delete mutation
      act(() => {
        result.current.deleteMutation.mutate({
          cameraId: 'cam-123',
          zoneId: 'zone-1',
        });
      });

      // Check optimistic removal happened
      await waitFor(() => {
        const cacheData = queryClient.getQueryData<ZoneListResponse>(
          queryKeys.cameras.zones('cam-123')
        );
        expect(cacheData?.items).toHaveLength(1);
        expect(cacheData?.items[0].id).toBe('zone-2');
      });

      // Resolve
      act(() => {
        resolveDelete!();
      });

      await waitFor(() => {
        expect(result.current.deleteMutation.isSuccess).toBe(true);
      });
    });

    it('invalidates zones cache after delete', async () => {
      (api.deleteZone as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);

      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.deleteMutation.mutateAsync({
          cameraId: 'cam-123',
          zoneId: 'zone-123',
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.cameras.zones('cam-123'),
      });
    });

    it('rolls back deletion on error', async () => {
      const error = new Error('Delete failed');
      (api.deleteZone as ReturnType<typeof vi.fn>).mockRejectedValue(error);

      const queryClient = createQueryClient();
      const zone1 = createMockZone({ id: 'zone-1' });
      const zone2 = createMockZone({ id: 'zone-2' });
      queryClient.setQueryData(
        queryKeys.cameras.zones('cam-123'),
        createMockZoneListResponse([zone1, zone2])
      );

      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        try {
          await result.current.deleteMutation.mutateAsync({
            cameraId: 'cam-123',
            zoneId: 'zone-1',
          });
        } catch {
          // Expected to throw
        }
      });

      // Should have rolled back to include deleted zone
      await waitFor(() => {
        const cacheData = queryClient.getQueryData<ZoneListResponse>(
          queryKeys.cameras.zones('cam-123')
        );
        expect(cacheData?.items).toHaveLength(2);
      });
    });
  });

  describe('mutation lifecycle callbacks', () => {
    it('onMutate cancels outgoing queries', async () => {
      (api.createZone as ReturnType<typeof vi.fn>).mockResolvedValue(
        createMockZone()
      );

      const queryClient = createQueryClient();
      const cancelSpy = vi.spyOn(queryClient, 'cancelQueries');

      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.createMutation.mutateAsync({
          cameraId: 'cam-123',
          data: {
            name: 'Test',
            zone_type: 'entry_point',
            coordinates: [[0, 0], [100, 0], [100, 100]],
            color: '#3B82F6',
            enabled: true,
            priority: 0,
            shape: 'polygon',
          },
        });
      });

      expect(cancelSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.cameras.zones('cam-123'),
      });
    });

    it('onSettled always invalidates cache', async () => {
      const error = new Error('Failed');
      (api.createZone as ReturnType<typeof vi.fn>).mockRejectedValue(error);

      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useZoneMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        try {
          await result.current.createMutation.mutateAsync({
            cameraId: 'cam-123',
            data: {
              name: 'Test',
              zone_type: 'entry_point',
              coordinates: [[0, 0], [100, 0], [100, 100]],
              color: '#3B82F6',
              enabled: true,
              priority: 0,
              shape: 'polygon',
            },
          });
        } catch {
          // Expected
        }
      });

      // onSettled should still invalidate even on error
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.cameras.zones('cam-123'),
      });
    });
  });
});
