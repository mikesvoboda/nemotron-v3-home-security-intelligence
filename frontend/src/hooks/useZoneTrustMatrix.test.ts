/**
 * Tests for useZoneTrustMatrix hooks (NEM-3192)
 *
 * This module tests the zone trust matrix hooks:
 * - useZoneHouseholdConfigQuery: Fetch household config for a zone
 * - useTrustCheckQuery: Check trust level for an entity in a zone
 * - useZoneTrustMatrix: Main hook for aggregating matrix data
 * - useUpdateMemberTrust: Update member trust level
 * - useUpdateVehicleTrust: Update vehicle trust level
 */
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';

import * as householdApi from './useHouseholdApi';
import {
  useTrustCheckQuery,
  useUpdateMemberTrust,
  useUpdateVehicleTrust,
  useUpdateZoneHouseholdConfig,
  useZoneHouseholdConfigQuery,
  useZoneTrustMatrix,
  zoneTrustQueryKeys,
  type AccessSchedule,
  type TrustCheckResponse,
  type ZoneHouseholdConfig,
} from './useZoneTrustMatrix';
import { createQueryClient } from '../services/queryClient';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { HouseholdMember, RegisteredVehicle } from './useHouseholdApi';
import type { Zone } from '../types/generated';

// ============================================================================
// Mock Setup
// ============================================================================

// Mock fetch globally for API tests
const mockFetch = vi.fn();

// Store original fetch - use globalThis for TypeScript compatibility
const originalFetch = globalThis.fetch;

// Mock household API hooks
vi.mock('./useHouseholdApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./useHouseholdApi')>();
  return {
    ...actual,
    useMembersQuery: vi.fn(),
    useVehiclesQuery: vi.fn(),
  };
});

// Setup global fetch mock
beforeAll(() => {
  globalThis.fetch = mockFetch as typeof fetch;
});

afterAll(() => {
  globalThis.fetch = originalFetch;
});

// ============================================================================
// Test Data Factories
// ============================================================================

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

const createMockMember = (overrides: Partial<HouseholdMember> = {}): HouseholdMember => ({
  id: Math.floor(Math.random() * 1000),
  name: 'Test Member',
  role: 'resident',
  trusted_level: 'full',
  notes: null,
  typical_schedule: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
});

const createMockVehicle = (overrides: Partial<RegisteredVehicle> = {}): RegisteredVehicle => ({
  id: Math.floor(Math.random() * 1000),
  description: 'Test Vehicle',
  vehicle_type: 'car',
  license_plate: 'ABC123',
  color: 'Blue',
  owner_id: null,
  trusted: true,
  created_at: new Date().toISOString(),
  ...overrides,
});

const createMockConfig = (
  zoneId: string,
  overrides: Partial<ZoneHouseholdConfig> = {}
): ZoneHouseholdConfig => ({
  id: 1,
  zone_id: zoneId,
  owner_id: null,
  allowed_member_ids: [],
  allowed_vehicle_ids: [],
  access_schedules: [],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
});

const createMockTrustResponse = (
  overrides: Partial<TrustCheckResponse> = {}
): TrustCheckResponse => ({
  zone_id: 'zone-123',
  entity_id: 1,
  entity_type: 'member',
  trust_level: 'none',
  reason: 'No trust configured',
  ...overrides,
});

// ============================================================================
// Tests
// ============================================================================

describe('zoneTrustQueryKeys', () => {
  it('generates correct base key', () => {
    expect(zoneTrustQueryKeys.all).toEqual(['zoneTrust']);
  });

  it('generates correct config key', () => {
    expect(zoneTrustQueryKeys.config('zone-123')).toEqual(['zoneTrust', 'config', 'zone-123']);
  });

  it('generates correct trust key', () => {
    expect(zoneTrustQueryKeys.trust('zone-123', 'member', 1)).toEqual([
      'zoneTrust',
      'trust',
      'zone-123',
      'member',
      1,
    ]);
  });

  it('generates correct matrix key', () => {
    expect(zoneTrustQueryKeys.matrix(['zone-1', 'zone-2'])).toEqual([
      'zoneTrust',
      'matrix',
      'zone-1',
      'zone-2',
    ]);
  });
});

describe('useZoneHouseholdConfigQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches config when zone ID is provided', async () => {
    const mockConfig = createMockConfig('zone-123');
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockConfig),
    });

    const { result } = renderHook(() => useZoneHouseholdConfigQuery('zone-123'), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockConfig);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/zones/zone-123/household'),
      expect.any(Object)
    );
  });

  it('does not fetch when zone ID is undefined', async () => {
    const { result } = renderHook(() => useZoneHouseholdConfigQuery(undefined), {
      wrapper: createQueryWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));

    expect(result.current.isLoading).toBe(false);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('handles error state', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({ detail: 'Server error' }),
    });

    const { result } = renderHook(() => useZoneHouseholdConfigQuery('zone-123'), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.error).toBeTruthy();
      },
      { timeout: 5000 }
    );
  });

  it('returns null for zones without config (404)', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
    });

    const { result } = renderHook(() => useZoneHouseholdConfigQuery('zone-empty'), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toBeNull();
    });
  });
});

describe('useTrustCheckQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('checks trust when all params are provided', async () => {
    const mockResponse = createMockTrustResponse({ trust_level: 'partial' });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockResponse),
    });

    const { result } = renderHook(() => useTrustCheckQuery('zone-123', 'member', 1), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockResponse);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/zones/zone-123/household/trust/member/1'),
      expect.any(Object)
    );
  });

  it('does not fetch when zone ID is undefined', async () => {
    const { result } = renderHook(() => useTrustCheckQuery(undefined, 'member', 1), {
      wrapper: createQueryWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(result.current.isLoading).toBe(false);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('respects enabled option', async () => {
    const { result } = renderHook(
      () => useTrustCheckQuery('zone-123', 'member', 1, { enabled: false }),
      { wrapper: createQueryWrapper() }
    );

    await new Promise((r) => setTimeout(r, 100));
    expect(result.current.isLoading).toBe(false);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('passes atTime option to API', async () => {
    const mockResponse = createMockTrustResponse();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockResponse),
    });

    const testTime = new Date('2026-01-21T10:00:00Z');
    const { result } = renderHook(
      () => useTrustCheckQuery('zone-123', 'member', 1, { atTime: testTime }),
      { wrapper: createQueryWrapper() }
    );

    await waitFor(() => {
      expect(result.current.data).toBeTruthy();
    });

    expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('at_time='), expect.any(Object));
  });
});

describe('useZoneTrustMatrix', () => {
  const mockZones = [
    createMockZone({ id: 'zone-1', name: 'Front Door', zone_type: 'entry_point' }),
    createMockZone({ id: 'zone-2', name: 'Driveway', zone_type: 'driveway' }),
  ];

  const mockMembers = [
    createMockMember({ id: 1, name: 'John' }),
    createMockMember({ id: 2, name: 'Jane' }),
  ];

  const mockVehicles = [
    createMockVehicle({ id: 1, description: 'Red Car' }),
    createMockVehicle({ id: 2, description: 'Blue Truck' }),
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();

    // Mock household hooks
    (householdApi.useMembersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockMembers,
      isLoading: false,
      error: null,
    });

    (householdApi.useVehiclesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockVehicles,
      isLoading: false,
      error: null,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns loading state initially', () => {
    // Make fetch hang to observe loading state
    mockFetch.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useZoneTrustMatrix(mockZones), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
  });

  it('returns zones, members, and vehicles', async () => {
    // Mock config fetches for all zones
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(createMockConfig('zone-1')),
    });

    const { result } = renderHook(() => useZoneTrustMatrix(mockZones), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.zones).toHaveLength(2);
    expect(result.current.members).toHaveLength(2);
    expect(result.current.vehicles).toHaveLength(2);
  });

  it('filters zones by zone type', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(createMockConfig('zone-1')),
    });

    const { result } = renderHook(
      () => useZoneTrustMatrix(mockZones, { zoneType: 'entry_point' }),
      { wrapper: createQueryWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.zones).toHaveLength(1);
    expect(result.current.zones[0].name).toBe('Front Door');
  });

  it('filters members by member IDs', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(createMockConfig('zone-1')),
    });

    const { result } = renderHook(() => useZoneTrustMatrix(mockZones, { memberIds: [1] }), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.members).toHaveLength(1);
    expect(result.current.members[0].name).toBe('John');
  });

  it('computes trust levels from config - owner', async () => {
    mockFetch.mockImplementation((url: string) => {
      const config = url.includes('zone-1')
        ? createMockConfig('zone-1', { owner_id: 1 })
        : createMockConfig('zone-2');
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(config),
      });
    });

    const { result } = renderHook(() => useZoneTrustMatrix(mockZones), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Check that John (id=1) has full trust in zone-1 as owner
    const zone1Cells = result.current.cells.get('zone-1');
    const johnCell = zone1Cells?.get(1);
    expect(johnCell?.trustLevel).toBe('full');
    expect(johnCell?.isOwner).toBe(true);
  });

  it('computes trust levels from config - allowed member', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(createMockConfig('zone-1', { allowed_member_ids: [2] })),
    });

    const { result } = renderHook(() => useZoneTrustMatrix(mockZones), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const zone1Cells = result.current.cells.get('zone-1');
    const janeCell = zone1Cells?.get(2);
    expect(janeCell?.trustLevel).toBe('partial');
  });

  it('computes trust levels from config - scheduled access', async () => {
    const schedules: AccessSchedule[] = [
      { member_ids: [1], cron_expression: '0 9-17 * * 1-5', description: 'Business hours' },
    ];
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(createMockConfig('zone-1', { access_schedules: schedules })),
    });

    const { result } = renderHook(() => useZoneTrustMatrix(mockZones), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const zone1Cells = result.current.cells.get('zone-1');
    const johnCell = zone1Cells?.get(1);
    expect(johnCell?.trustLevel).toBe('monitor');
    expect(johnCell?.accessSchedules).toHaveLength(1);
  });

  it('computes trust levels for vehicles', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(createMockConfig('zone-1', { allowed_vehicle_ids: [1] })),
    });

    const { result } = renderHook(() => useZoneTrustMatrix(mockZones), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const zone1Cells = result.current.cells.get('zone-1');
    // Vehicles use negative IDs in the map
    const vehicle1Cell = zone1Cells?.get(-1);
    expect(vehicle1Cell?.trustLevel).toBe('partial');
    expect(vehicle1Cell?.entityType).toBe('vehicle');
  });

  it('handles error from members query', () => {
    const mockError = new Error('Failed to load members');
    (householdApi.useMembersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: mockError,
    });

    const { result } = renderHook(() => useZoneTrustMatrix(mockZones), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.error).toBe(mockError);
  });

  it('handles empty zones array', () => {
    const { result } = renderHook(() => useZoneTrustMatrix([]), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.zones).toHaveLength(0);
    expect(result.current.cells.size).toBe(0);
  });

  it('filters by trust level', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(createMockConfig('zone-1', { owner_id: 1 })),
    });

    const { result } = renderHook(() => useZoneTrustMatrix(mockZones, { trustLevel: 'full' }), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Only cells with full trust should be included
    const zone1Cells = result.current.cells.get('zone-1');
    expect(zone1Cells?.size).toBe(1); // Only John with full trust
  });
});

describe('useUpdateZoneHouseholdConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('updates config successfully', async () => {
    const mockConfig = createMockConfig('zone-123', { owner_id: 1 });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockConfig),
    });

    const queryClient = createQueryClient();
    const { result } = renderHook(() => useUpdateZoneHouseholdConfig(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({
        zoneId: 'zone-123',
        config: { owner_id: 1 },
      });
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/zones/zone-123/household'),
      expect.objectContaining({
        method: 'PUT',
        body: expect.stringContaining('"owner_id":1'),
      })
    );
  });

  it('invalidates config cache after update', async () => {
    const mockConfig = createMockConfig('zone-123');
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockConfig),
    });

    const queryClient = createQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useUpdateZoneHouseholdConfig(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({
        zoneId: 'zone-123',
        config: { owner_id: 2 },
      });
    });

    expect(invalidateSpy).toHaveBeenCalled();
  });

  it('handles error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({ detail: 'Update failed' }),
    });

    const queryClient = createQueryClient();
    const { result } = renderHook(() => useUpdateZoneHouseholdConfig(), {
      wrapper: createQueryWrapper(queryClient),
    });

    let thrownError: Error | null = null;
    await act(async () => {
      try {
        await result.current.mutateAsync({
          zoneId: 'zone-123',
          config: { owner_id: 1 },
        });
      } catch (err) {
        thrownError = err as Error;
      }
    });

    // The mutation should have thrown an error
    expect(thrownError).toBeTruthy();
    expect(thrownError).toBeInstanceOf(Error);
    expect((thrownError as unknown as Error).message).toContain('Update failed');
  });
});

describe('useUpdateMemberTrust', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('updates member to full trust (owner)', async () => {
    const mockConfig = createMockConfig('zone-123', { owner_id: 1 });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockConfig),
    });

    const queryClient = createQueryClient();
    const { result } = renderHook(() => useUpdateMemberTrust(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.updateMemberTrust('zone-123', 1, 'full', null);
    });

    // Verify the config was updated with owner_id set
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/zones/zone-123/household'),
      expect.objectContaining({
        method: 'PUT',
        body: expect.stringContaining('"owner_id":1'),
      })
    );
  });

  it('updates member to partial trust', async () => {
    const mockConfig = createMockConfig('zone-123', { allowed_member_ids: [1] });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockConfig),
    });

    const queryClient = createQueryClient();
    const { result } = renderHook(() => useUpdateMemberTrust(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.updateMemberTrust('zone-123', 1, 'partial', null);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: expect.stringContaining('"allowed_member_ids":[1]'),
      })
    );
  });

  it('updates member to monitor trust', async () => {
    const mockConfig = createMockConfig('zone-123');
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockConfig),
    });

    const queryClient = createQueryClient();
    const { result } = renderHook(() => useUpdateMemberTrust(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.updateMemberTrust('zone-123', 1, 'monitor', null);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: expect.stringContaining('access_schedules'),
      })
    );
  });

  it('removes member from all lists when setting to none', async () => {
    const existingConfig = createMockConfig('zone-123', {
      owner_id: 1,
      allowed_member_ids: [1, 2],
    });
    const resultConfig = createMockConfig('zone-123', {
      owner_id: null,
      allowed_member_ids: [2],
    });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(resultConfig),
    });

    const queryClient = createQueryClient();
    const { result } = renderHook(() => useUpdateMemberTrust(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.updateMemberTrust('zone-123', 1, 'none', existingConfig);
    });

    // Verify member 1 was removed from owner and allowed lists
    const callBody = mockFetch.mock.calls[0][1].body as string;
    expect(callBody).toContain('"owner_id":null');
    expect(callBody).toContain('"allowed_member_ids":[2]');
  });

  it('tracks loading state', async () => {
    let resolvePromise: (value: Response) => void;
    mockFetch.mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePromise = resolve;
      })
    );

    const queryClient = createQueryClient();
    const { result } = renderHook(() => useUpdateMemberTrust(), {
      wrapper: createQueryWrapper(queryClient),
    });

    expect(result.current.isLoading).toBe(false);

    void act(() => {
      void result.current.updateMemberTrust('zone-123', 1, 'full', null);
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    act(() => {
      resolvePromise!({
        ok: true,
        status: 200,
        json: () => Promise.resolve(createMockConfig('zone-123')),
      } as Response);
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });
});

describe('useUpdateVehicleTrust', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('updates vehicle to partial trust', async () => {
    const mockConfig = createMockConfig('zone-123', { allowed_vehicle_ids: [1] });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockConfig),
    });

    const queryClient = createQueryClient();
    const { result } = renderHook(() => useUpdateVehicleTrust(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.updateVehicleTrust('zone-123', 1, 'partial', null);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/zones/zone-123/household'),
      expect.objectContaining({
        method: 'PUT',
        body: expect.stringContaining('"allowed_vehicle_ids":[1]'),
      })
    );
  });

  it('removes vehicle when setting to none', async () => {
    const existingConfig = createMockConfig('zone-123', { allowed_vehicle_ids: [1, 2] });
    const resultConfig = createMockConfig('zone-123', { allowed_vehicle_ids: [2] });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(resultConfig),
    });

    const queryClient = createQueryClient();
    const { result } = renderHook(() => useUpdateVehicleTrust(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.updateVehicleTrust('zone-123', 1, 'none', existingConfig);
    });

    // Verify vehicle 1 was removed
    const callBody = mockFetch.mock.calls[0][1].body as string;
    expect(callBody).toContain('"allowed_vehicle_ids":[2]');
  });

  it('treats full trust same as partial for vehicles', async () => {
    const mockConfig = createMockConfig('zone-123', { allowed_vehicle_ids: [1] });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockConfig),
    });

    const queryClient = createQueryClient();
    const { result } = renderHook(() => useUpdateVehicleTrust(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.updateVehicleTrust('zone-123', 1, 'full', null);
    });

    // Full trust for vehicles adds to allowed_vehicle_ids (same as partial)
    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: expect.stringContaining('"allowed_vehicle_ids":[1]'),
      })
    );
  });

  it('tracks loading state', async () => {
    let resolvePromise: (value: Response) => void;
    mockFetch.mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePromise = resolve;
      })
    );

    const queryClient = createQueryClient();
    const { result } = renderHook(() => useUpdateVehicleTrust(), {
      wrapper: createQueryWrapper(queryClient),
    });

    expect(result.current.isLoading).toBe(false);

    void act(() => {
      void result.current.updateVehicleTrust('zone-123', 1, 'partial', null);
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    act(() => {
      resolvePromise!({
        ok: true,
        status: 200,
        json: () => Promise.resolve(createMockConfig('zone-123')),
      } as Response);
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });
});
