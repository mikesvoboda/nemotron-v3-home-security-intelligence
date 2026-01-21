/**
 * Tests for useHouseholdApi hook (NEM-3204)
 *
 * Comprehensive tests for household member, vehicle, and household CRUD operations
 * using React Query hooks. Tests cover all query hooks, mutation hooks, loading states,
 * error handling, and cache invalidation.
 *
 * @see frontend/src/hooks/useHouseholdApi.ts
 */

import { QueryClient } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { server } from '../../mocks/server';
import { createQueryWrapper } from '../../test-utils/renderWithProviders';
import {
  useMembersQuery,
  useCreateMember,
  useUpdateMember,
  useDeleteMember,
  useVehiclesQuery,
  useCreateVehicle,
  useUpdateVehicle,
  useDeleteVehicle,
  useHouseholdsQuery,
  useCreateHousehold,
  useUpdateHousehold,
  useDeleteHousehold,
  useHouseholdApi,
  householdQueryKeys,
} from '../useHouseholdApi';

import type {
  HouseholdMember,
  HouseholdMemberCreate,
  HouseholdMemberUpdate,
  RegisteredVehicle,
  RegisteredVehicleCreate,
  RegisteredVehicleUpdate,
  Household,
  HouseholdCreate,
  HouseholdUpdate,
  HouseholdListResponse,
} from '../useHouseholdApi';

// Base URL from environment
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';

// ============================================================================
// Mock Data
// ============================================================================

const mockMember: HouseholdMember = {
  id: 1,
  name: 'John Doe',
  role: 'resident',
  trusted_level: 'full',
  notes: 'Primary resident',
  typical_schedule: { monday: '9-17' },
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const mockMember2: HouseholdMember = {
  id: 2,
  name: 'Jane Smith',
  role: 'family',
  trusted_level: 'full',
  notes: null,
  typical_schedule: null,
  created_at: '2024-01-02T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
};

const mockVehicle: RegisteredVehicle = {
  id: 1,
  description: 'Blue Toyota Camry',
  vehicle_type: 'car',
  license_plate: 'ABC123',
  color: 'blue',
  owner_id: 1,
  trusted: true,
  created_at: '2024-01-01T00:00:00Z',
};

const mockVehicle2: RegisteredVehicle = {
  id: 2,
  description: 'Red Honda CR-V',
  vehicle_type: 'suv',
  license_plate: 'XYZ789',
  color: 'red',
  owner_id: null,
  trusted: true,
  created_at: '2024-01-02T00:00:00Z',
};

const mockHousehold: Household = {
  id: 1,
  name: 'Main House',
  created_at: '2024-01-01T00:00:00Z',
};

const mockHousehold2: Household = {
  id: 2,
  name: 'Guest House',
  created_at: '2024-01-02T00:00:00Z',
};

// ============================================================================
// Tests - Household Members
// ============================================================================

describe('useMembersQuery', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE_URL}/api/household/members`, () => {
        return HttpResponse.json([mockMember, mockMember2]);
      })
    );
  });

  it('fetches household members successfully', async () => {
    const { result } = renderHook(() => useMembersQuery(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual([mockMember, mockMember2]);
    expect(result.current.error).toBeNull();
  });

  it('handles empty members list', async () => {
    server.use(
      http.get(`${BASE_URL}/api/household/members`, () => {
        return HttpResponse.json([]);
      })
    );

    const { result } = renderHook(() => useMembersQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual([]);
  });

  it('handles fetch error', async () => {
    server.use(
      http.get(`${BASE_URL}/api/household/members`, () => {
        return HttpResponse.json(
          { detail: 'Internal server error' },
          { status: 500 }
        );
      })
    );

    const { result } = renderHook(() => useMembersQuery(), {
      wrapper: createQueryWrapper(),
    });

    // Wait for retries to complete (retry: 1 means 2 attempts)
    await waitFor(
      () => {
        expect(result.current.error).not.toBeNull();
      },
      { timeout: 3000 }
    );

    expect(result.current.data).toBeUndefined();
    expect(result.current.error?.message).toContain('Internal server error');
  });

  it('retries failed requests once', async () => {
    let callCount = 0;
    server.use(
      http.get(`${BASE_URL}/api/household/members`, () => {
        callCount++;
        return HttpResponse.json(
          { detail: 'Server error' },
          { status: 500 }
        );
      })
    );

    const { result } = renderHook(() => useMembersQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.error).not.toBeNull();
      },
      { timeout: 3000 }
    );

    // Should retry once (2 total attempts)
    expect(callCount).toBe(2);
  });
});

describe('useCreateMember', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.post(`${BASE_URL}/api/household/members`, async ({ request }) => {
        const body = await request.json() as HouseholdMemberCreate;
        return HttpResponse.json({
          id: 3,
          ...body,
          created_at: '2024-01-03T00:00:00Z',
          updated_at: '2024-01-03T00:00:00Z',
        });
      })
    );
  });

  it('creates a new member successfully', async () => {
    const { result } = renderHook(() => useCreateMember(), {
      wrapper: createQueryWrapper(queryClient),
    });

    const newMember: HouseholdMemberCreate = {
      name: 'Bob Johnson',
      role: 'service_worker',
      trusted_level: 'partial',
      notes: 'Delivery person',
    };

    let created: HouseholdMember | undefined;
    await act(async () => {
      created = await result.current.mutateAsync(newMember);
    });

    expect(created!.id).toBe(3);
    expect(created!.name).toBe('Bob Johnson');
    expect(created!.role).toBe('service_worker');

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.error).toBeNull();
  });

  it('invalidates members cache after successful creation', async () => {
    // Pre-populate cache
    queryClient.setQueryData(householdQueryKeys.members(), [mockMember]);

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useCreateMember(), {
      wrapper: createQueryWrapper(queryClient),
    });

    const newMember: HouseholdMemberCreate = {
      name: 'New Member',
      role: 'resident',
      trusted_level: 'full',
    };

    await act(async () => {
      await result.current.mutateAsync(newMember);
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: householdQueryKeys.members(),
    });
  });

  it('handles creation error', async () => {
    server.use(
      http.post(`${BASE_URL}/api/household/members`, () => {
        return HttpResponse.json(
          { detail: 'Validation error' },
          { status: 400 }
        );
      })
    );

    const { result } = renderHook(() => useCreateMember(), {
      wrapper: createQueryWrapper(queryClient),
    });

    const newMember: HouseholdMemberCreate = {
      name: '',
      role: 'resident',
      trusted_level: 'full',
    };

    await act(async () => {
      try {
        await result.current.mutateAsync(newMember);
      } catch (error) {
        expect(error).toBeDefined();
      }
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error?.message).toContain('Validation error');
  });

  it('tracks pending state during mutation', async () => {
    server.use(
      http.post(`${BASE_URL}/api/household/members`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
        return HttpResponse.json(mockMember);
      })
    );

    const { result } = renderHook(() => useCreateMember(), {
      wrapper: createQueryWrapper(queryClient),
    });

    const newMember: HouseholdMemberCreate = {
      name: 'Test',
      role: 'resident',
      trusted_level: 'full',
    };

    let mutationPromise: Promise<HouseholdMember>;
    act(() => {
      mutationPromise = result.current.mutateAsync(newMember);
    });

    // Should be pending immediately after calling mutate
    await waitFor(() => {
      expect(result.current.isPending).toBe(true);
    });

    // Wait for mutation to complete
    await act(async () => {
      await mutationPromise;
    });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });
  });
});

describe('useUpdateMember', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.patch(`${BASE_URL}/api/household/members/:id`, async ({ request, params }) => {
        const body = await request.json() as HouseholdMemberUpdate;
        const id = Number(params.id);
        return HttpResponse.json({
          ...mockMember,
          id,
          ...body,
          updated_at: '2024-01-04T00:00:00Z',
        });
      })
    );
  });

  it('updates a member successfully', async () => {
    const { result } = renderHook(() => useUpdateMember(), {
      wrapper: createQueryWrapper(queryClient),
    });

    const update: HouseholdMemberUpdate = {
      name: 'John Doe Updated',
      notes: 'Updated notes',
    };

    let updated: HouseholdMember | undefined;
    await act(async () => {
      updated = await result.current.mutateAsync({ id: 1, data: update });
    });

    expect(updated!.name).toBe('John Doe Updated');
    expect(updated!.notes).toBe('Updated notes');

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('invalidates members cache after successful update', async () => {
    queryClient.setQueryData(householdQueryKeys.members(), [mockMember]);
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useUpdateMember(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({ id: 1, data: { name: 'Updated' } });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: householdQueryKeys.members(),
    });
  });

  it('handles update error for non-existent member', async () => {
    server.use(
      http.patch(`${BASE_URL}/api/household/members/:id`, () => {
        return HttpResponse.json(
          { detail: 'Member not found' },
          { status: 404 }
        );
      })
    );

    const { result } = renderHook(() => useUpdateMember(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      try {
        await result.current.mutateAsync({ id: 999, data: { name: 'Test' } });
      } catch (error) {
        expect(error).toBeDefined();
      }
    });

    expect(result.current.error?.message).toContain('Member not found');
  });

  it('allows partial updates', async () => {
    const { result } = renderHook(() => useUpdateMember(), {
      wrapper: createQueryWrapper(queryClient),
    });

    // Only update notes
    await act(async () => {
      const updated = await result.current.mutateAsync({
        id: 1,
        data: { notes: 'Only notes updated' },
      });
      expect(updated.notes).toBe('Only notes updated');
    });
  });
});

describe('useDeleteMember', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.delete(`${BASE_URL}/api/household/members/:id`, () => {
        return new HttpResponse(null, { status: 204 });
      })
    );
  });

  it('deletes a member successfully', async () => {
    const { result } = renderHook(() => useDeleteMember(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync(1);
    });

    expect(result.current.isSuccess).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('invalidates members cache after successful deletion', async () => {
    queryClient.setQueryData(householdQueryKeys.members(), [mockMember, mockMember2]);
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useDeleteMember(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync(1);
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: householdQueryKeys.members(),
    });
  });

  it('handles deletion error for non-existent member', async () => {
    server.use(
      http.delete(`${BASE_URL}/api/household/members/:id`, () => {
        return HttpResponse.json(
          { detail: 'Member not found' },
          { status: 404 }
        );
      })
    );

    const { result } = renderHook(() => useDeleteMember(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      try {
        await result.current.mutateAsync(999);
      } catch (error) {
        expect(error).toBeDefined();
      }
    });

    expect(result.current.error?.message).toContain('Member not found');
  });
});

// ============================================================================
// Tests - Registered Vehicles
// ============================================================================

describe('useVehiclesQuery', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE_URL}/api/household/vehicles`, () => {
        return HttpResponse.json([mockVehicle, mockVehicle2]);
      })
    );
  });

  it('fetches vehicles successfully', async () => {
    const { result } = renderHook(() => useVehiclesQuery(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual([mockVehicle, mockVehicle2]);
    expect(result.current.error).toBeNull();
  });

  it('handles empty vehicles list', async () => {
    server.use(
      http.get(`${BASE_URL}/api/household/vehicles`, () => {
        return HttpResponse.json([]);
      })
    );

    const { result } = renderHook(() => useVehiclesQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual([]);
  });

  it('handles fetch error', async () => {
    server.use(
      http.get(`${BASE_URL}/api/household/vehicles`, () => {
        return HttpResponse.json(
          { detail: 'Database error' },
          { status: 500 }
        );
      })
    );

    const { result } = renderHook(() => useVehiclesQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.error).not.toBeNull();
      },
      { timeout: 3000 }
    );

    expect(result.current.error?.message).toContain('Database error');
  });
});

describe('useCreateVehicle', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.post(`${BASE_URL}/api/household/vehicles`, async ({ request }) => {
        const body = await request.json() as RegisteredVehicleCreate;
        return HttpResponse.json({
          id: 3,
          ...body,
          trusted: body.trusted ?? false,
          created_at: '2024-01-03T00:00:00Z',
        });
      })
    );
  });

  it('creates a new vehicle successfully', async () => {
    const { result } = renderHook(() => useCreateVehicle(), {
      wrapper: createQueryWrapper(queryClient),
    });

    const newVehicle: RegisteredVehicleCreate = {
      description: 'Green Tesla Model 3',
      vehicle_type: 'car',
      license_plate: 'EV123',
      color: 'green',
      owner_id: 1,
      trusted: true,
    };

    let created: RegisteredVehicle | undefined;
    await act(async () => {
      created = await result.current.mutateAsync(newVehicle);
    });

    expect(created!.id).toBe(3);
    expect(created!.description).toBe('Green Tesla Model 3');
    expect(created!.trusted).toBe(true);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('creates vehicle with minimal fields', async () => {
    const { result } = renderHook(() => useCreateVehicle(), {
      wrapper: createQueryWrapper(queryClient),
    });

    const newVehicle: RegisteredVehicleCreate = {
      description: 'Unknown car',
      vehicle_type: 'other',
    };

    await act(async () => {
      const created = await result.current.mutateAsync(newVehicle);
      expect(created.description).toBe('Unknown car');
      expect(created.vehicle_type).toBe('other');
      expect(created.trusted).toBe(false);
    });
  });

  it('invalidates vehicles cache after creation', async () => {
    queryClient.setQueryData(householdQueryKeys.vehicles(), [mockVehicle]);
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useCreateVehicle(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({
        description: 'New Vehicle',
        vehicle_type: 'car',
      });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: householdQueryKeys.vehicles(),
    });
  });

  it('handles creation error', async () => {
    server.use(
      http.post(`${BASE_URL}/api/household/vehicles`, () => {
        return HttpResponse.json(
          { detail: 'Invalid vehicle type' },
          { status: 400 }
        );
      })
    );

    const { result } = renderHook(() => useCreateVehicle(), {
      wrapper: createQueryWrapper(queryClient),
    });

    let error: Error | undefined;
    await act(async () => {
      try {
        await result.current.mutateAsync({
          description: 'Test',
          vehicle_type: 'car',
        });
      } catch (e) {
        error = e as Error;
      }
    });

    expect(error).toBeDefined();
    expect(error!.message).toContain('Invalid vehicle type');
  });
});

describe('useUpdateVehicle', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.patch(`${BASE_URL}/api/household/vehicles/:id`, async ({ request, params }) => {
        const body = await request.json() as RegisteredVehicleUpdate;
        const id = Number(params.id);
        return HttpResponse.json({
          ...mockVehicle,
          id,
          ...body,
        });
      })
    );
  });

  it('updates a vehicle successfully', async () => {
    const { result } = renderHook(() => useUpdateVehicle(), {
      wrapper: createQueryWrapper(queryClient),
    });

    const update: RegisteredVehicleUpdate = {
      description: 'Updated vehicle',
      color: 'silver',
    };

    await act(async () => {
      const updated = await result.current.mutateAsync({ id: 1, data: update });
      expect(updated.description).toBe('Updated vehicle');
      expect(updated.color).toBe('silver');
    });

    expect(result.current.isSuccess).toBe(true);
  });

  it('invalidates vehicles cache after update', async () => {
    queryClient.setQueryData(householdQueryKeys.vehicles(), [mockVehicle]);
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useUpdateVehicle(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({ id: 1, data: { trusted: false } });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: householdQueryKeys.vehicles(),
    });
  });

  it('handles update error', async () => {
    server.use(
      http.patch(`${BASE_URL}/api/household/vehicles/:id`, () => {
        return HttpResponse.json(
          { detail: 'Vehicle not found' },
          { status: 404 }
        );
      })
    );

    const { result } = renderHook(() => useUpdateVehicle(), {
      wrapper: createQueryWrapper(queryClient),
    });

    let error: Error | undefined;
    await act(async () => {
      try {
        await result.current.mutateAsync({ id: 999, data: { trusted: false } });
      } catch (e) {
        error = e as Error;
      }
    });

    expect(error).toBeDefined();
    expect(error!.message).toContain('Vehicle not found');
  });
});

describe('useDeleteVehicle', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.delete(`${BASE_URL}/api/household/vehicles/:id`, () => {
        return new HttpResponse(null, { status: 204 });
      })
    );
  });

  it('deletes a vehicle successfully', async () => {
    const { result } = renderHook(() => useDeleteVehicle(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync(1);
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('invalidates vehicles cache after deletion', async () => {
    queryClient.setQueryData(householdQueryKeys.vehicles(), [mockVehicle, mockVehicle2]);
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useDeleteVehicle(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync(1);
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: householdQueryKeys.vehicles(),
    });
  });

  it('handles deletion error', async () => {
    server.use(
      http.delete(`${BASE_URL}/api/household/vehicles/:id`, () => {
        return HttpResponse.json(
          { detail: 'Vehicle not found' },
          { status: 404 }
        );
      })
    );

    const { result } = renderHook(() => useDeleteVehicle(), {
      wrapper: createQueryWrapper(queryClient),
    });

    let error: Error | undefined;
    await act(async () => {
      try {
        await result.current.mutateAsync(999);
      } catch (e) {
        error = e as Error;
      }
    });

    expect(error).toBeDefined();
    expect(error!.message).toContain('Vehicle not found');
  });
});

// ============================================================================
// Tests - Households
// ============================================================================

describe('useHouseholdsQuery', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE_URL}/api/v1/households`, () => {
        return HttpResponse.json({
          items: [mockHousehold, mockHousehold2],
          total: 2,
        } as HouseholdListResponse);
      })
    );
  });

  it('fetches households successfully', async () => {
    const { result } = renderHook(() => useHouseholdsQuery(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data?.items).toEqual([mockHousehold, mockHousehold2]);
    expect(result.current.data?.total).toBe(2);
  });

  it('handles empty households list', async () => {
    server.use(
      http.get(`${BASE_URL}/api/v1/households`, () => {
        return HttpResponse.json({
          items: [],
          total: 0,
        } as HouseholdListResponse);
      })
    );

    const { result } = renderHook(() => useHouseholdsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data?.items).toEqual([]);
    expect(result.current.data?.total).toBe(0);
  });

  it('handles fetch error', async () => {
    server.use(
      http.get(`${BASE_URL}/api/v1/households`, () => {
        return HttpResponse.json(
          { detail: 'Unauthorized' },
          { status: 401 }
        );
      })
    );

    const { result } = renderHook(() => useHouseholdsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.error).not.toBeNull();
      },
      { timeout: 3000 }
    );

    expect(result.current.error?.message).toContain('Unauthorized');
  });
});

describe('useCreateHousehold', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.post(`${BASE_URL}/api/v1/households`, async ({ request }) => {
        const body = await request.json() as HouseholdCreate;
        return HttpResponse.json({
          id: 3,
          name: body.name,
          created_at: '2024-01-03T00:00:00Z',
        } as Household);
      })
    );
  });

  it('creates a new household successfully', async () => {
    const { result } = renderHook(() => useCreateHousehold(), {
      wrapper: createQueryWrapper(queryClient),
    });

    const newHousehold: HouseholdCreate = {
      name: 'Vacation Home',
    };

    let created: Household | undefined;
    await act(async () => {
      created = await result.current.mutateAsync(newHousehold);
    });

    expect(created!.id).toBe(3);
    expect(created!.name).toBe('Vacation Home');

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('invalidates households cache after creation', async () => {
    queryClient.setQueryData(householdQueryKeys.households(), {
      items: [mockHousehold],
      total: 1,
    });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useCreateHousehold(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({ name: 'New Household' });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: householdQueryKeys.households(),
    });
  });

  it('handles creation error for duplicate name', async () => {
    server.use(
      http.post(`${BASE_URL}/api/v1/households`, () => {
        return HttpResponse.json(
          { detail: 'Household with this name already exists' },
          { status: 409 }
        );
      })
    );

    const { result } = renderHook(() => useCreateHousehold(), {
      wrapper: createQueryWrapper(queryClient),
    });

    let error: Error | undefined;
    await act(async () => {
      try {
        await result.current.mutateAsync({ name: 'Duplicate' });
      } catch (e) {
        error = e as Error;
      }
    });

    expect(error).toBeDefined();
    expect(error!.message).toContain('already exists');
  });
});

describe('useUpdateHousehold', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.patch(`${BASE_URL}/api/v1/households/:id`, async ({ request, params }) => {
        const body = await request.json() as HouseholdUpdate;
        const id = Number(params.id);
        return HttpResponse.json({
          ...mockHousehold,
          id,
          ...body,
        } as Household);
      })
    );
  });

  it('updates a household successfully', async () => {
    const { result } = renderHook(() => useUpdateHousehold(), {
      wrapper: createQueryWrapper(queryClient),
    });

    const update: HouseholdUpdate = {
      name: 'Main House Updated',
    };

    let updated: Household | undefined;
    await act(async () => {
      updated = await result.current.mutateAsync({ id: 1, data: update });
    });

    expect(updated!.name).toBe('Main House Updated');

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('invalidates households cache after update', async () => {
    queryClient.setQueryData(householdQueryKeys.households(), {
      items: [mockHousehold],
      total: 1,
    });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useUpdateHousehold(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({ id: 1, data: { name: 'Updated' } });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: householdQueryKeys.households(),
    });
  });

  it('handles update error for non-existent household', async () => {
    server.use(
      http.patch(`${BASE_URL}/api/v1/households/:id`, () => {
        return HttpResponse.json(
          { detail: 'Household not found' },
          { status: 404 }
        );
      })
    );

    const { result } = renderHook(() => useUpdateHousehold(), {
      wrapper: createQueryWrapper(queryClient),
    });

    let error: Error | undefined;
    await act(async () => {
      try {
        await result.current.mutateAsync({ id: 999, data: { name: 'Test' } });
      } catch (e) {
        error = e as Error;
      }
    });

    expect(error).toBeDefined();
    expect(error!.message).toContain('Household not found');
  });
});

describe('useDeleteHousehold', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.delete(`${BASE_URL}/api/v1/households/:id`, () => {
        return new HttpResponse(null, { status: 204 });
      })
    );
  });

  it('deletes a household successfully', async () => {
    const { result } = renderHook(() => useDeleteHousehold(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync(1);
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('invalidates households cache after deletion', async () => {
    queryClient.setQueryData(householdQueryKeys.households(), {
      items: [mockHousehold, mockHousehold2],
      total: 2,
    });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useDeleteHousehold(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync(1);
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: householdQueryKeys.households(),
    });
  });

  it('handles deletion error', async () => {
    server.use(
      http.delete(`${BASE_URL}/api/v1/households/:id`, () => {
        return HttpResponse.json(
          { detail: 'Cannot delete household with active members' },
          { status: 400 }
        );
      })
    );

    const { result } = renderHook(() => useDeleteHousehold(), {
      wrapper: createQueryWrapper(queryClient),
    });

    let error: Error | undefined;
    await act(async () => {
      try {
        await result.current.mutateAsync(1);
      } catch (e) {
        error = e as Error;
      }
    });

    expect(error).toBeDefined();
    expect(error!.message).toContain('active members');
  });
});

// ============================================================================
// Tests - Combined Hook
// ============================================================================

describe('useHouseholdApi', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE_URL}/api/household/members`, () => {
        return HttpResponse.json([mockMember]);
      }),
      http.get(`${BASE_URL}/api/household/vehicles`, () => {
        return HttpResponse.json([mockVehicle]);
      }),
      http.get(`${BASE_URL}/api/v1/households`, () => {
        return HttpResponse.json({
          items: [mockHousehold],
          total: 1,
        } as HouseholdListResponse);
      })
    );
  });

  it('provides access to all queries and mutations', async () => {
    const { result } = renderHook(() => useHouseholdApi(), {
      wrapper: createQueryWrapper(),
    });

    // Wait for queries to resolve
    await waitFor(() => {
      expect(result.current.membersLoading).toBe(false);
      expect(result.current.vehiclesLoading).toBe(false);
      expect(result.current.householdsLoading).toBe(false);
    });

    // Check query results
    expect(result.current.members).toEqual([mockMember]);
    expect(result.current.vehicles).toEqual([mockVehicle]);
    expect(result.current.households?.items).toEqual([mockHousehold]);

    // Check errors are null
    expect(result.current.membersError).toBeNull();
    expect(result.current.vehiclesError).toBeNull();
    expect(result.current.householdsError).toBeNull();

    // Check mutations are available
    expect(result.current.createMember).toBeDefined();
    expect(result.current.updateMember).toBeDefined();
    expect(result.current.deleteMember).toBeDefined();

    expect(result.current.createVehicle).toBeDefined();
    expect(result.current.updateVehicle).toBeDefined();
    expect(result.current.deleteVehicle).toBeDefined();

    expect(result.current.createHousehold).toBeDefined();
    expect(result.current.updateHousehold).toBeDefined();
    expect(result.current.deleteHousehold).toBeDefined();
  });

  it('exposes loading states correctly', async () => {
    server.use(
      http.get(`${BASE_URL}/api/household/members`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
        return HttpResponse.json([mockMember]);
      }),
      http.get(`${BASE_URL}/api/household/vehicles`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
        return HttpResponse.json([mockVehicle]);
      }),
      http.get(`${BASE_URL}/api/v1/households`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
        return HttpResponse.json({
          items: [mockHousehold],
          total: 1,
        } as HouseholdListResponse);
      })
    );

    const { result } = renderHook(() => useHouseholdApi(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.membersLoading).toBe(true);
    expect(result.current.vehiclesLoading).toBe(true);
    expect(result.current.householdsLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.membersLoading).toBe(false);
      expect(result.current.vehiclesLoading).toBe(false);
      expect(result.current.householdsLoading).toBe(false);
    });
  });

  it('exposes error states correctly', async () => {
    server.use(
      http.get(`${BASE_URL}/api/household/members`, () => {
        return HttpResponse.json({ detail: 'Member error' }, { status: 500 });
      }),
      http.get(`${BASE_URL}/api/household/vehicles`, () => {
        return HttpResponse.json({ detail: 'Vehicle error' }, { status: 500 });
      }),
      http.get(`${BASE_URL}/api/v1/households`, () => {
        return HttpResponse.json({ detail: 'Household error' }, { status: 500 });
      })
    );

    const { result } = renderHook(() => useHouseholdApi(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.membersError).not.toBeNull();
        expect(result.current.vehiclesError).not.toBeNull();
        expect(result.current.householdsError).not.toBeNull();
      },
      { timeout: 3000 }
    );

    expect(result.current.membersError?.message).toContain('Member error');
    expect(result.current.vehiclesError?.message).toContain('Vehicle error');
    expect(result.current.householdsError?.message).toContain('Household error');
  });
});

// ============================================================================
// Tests - Query Keys
// ============================================================================

describe('householdQueryKeys', () => {
  it('generates correct base key', () => {
    expect(householdQueryKeys.all).toEqual(['household']);
  });

  it('generates correct members keys', () => {
    expect(householdQueryKeys.members()).toEqual(['household', 'members']);
    expect(householdQueryKeys.member(1)).toEqual(['household', 'members', 1]);
  });

  it('generates correct vehicles keys', () => {
    expect(householdQueryKeys.vehicles()).toEqual(['household', 'vehicles']);
    expect(householdQueryKeys.vehicle(1)).toEqual(['household', 'vehicles', 1]);
  });

  it('generates correct households keys', () => {
    expect(householdQueryKeys.households()).toEqual(['household', 'households']);
    expect(householdQueryKeys.household(1)).toEqual(['household', 'households', 1]);
  });
});
