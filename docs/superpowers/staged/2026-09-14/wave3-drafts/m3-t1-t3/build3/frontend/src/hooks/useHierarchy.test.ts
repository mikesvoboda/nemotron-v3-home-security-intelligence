/**
 * Tests for useHierarchy hooks.
 *
 * Tests all hierarchy-related hooks including:
 * - Household CRUD operations
 * - Property CRUD operations
 * - Area CRUD operations
 * - Camera linking/unlinking
 *
 * @module hooks/useHierarchy.test
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useHouseholdsQuery,
  useHouseholdQuery,
  useHouseholdMutation,
  usePropertiesQuery,
  usePropertyQuery,
  usePropertyMutation,
  useAreasQuery,
  useAreaQuery,
  useAreaMutation,
  useAreaCamerasQuery,
  useCameraLinkMutation,
} from './useHierarchy';
import * as api from '../services/api';
import { createQueryClient, queryKeys } from '../services/queryClient';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  // Household API
  fetchHouseholds: vi.fn(),
  fetchHousehold: vi.fn(),
  createHousehold: vi.fn(),
  updateHousehold: vi.fn(),
  deleteHousehold: vi.fn(),
  // Property API
  fetchProperties: vi.fn(),
  fetchProperty: vi.fn(),
  createProperty: vi.fn(),
  updateProperty: vi.fn(),
  deleteProperty: vi.fn(),
  // Area API
  fetchAreas: vi.fn(),
  fetchArea: vi.fn(),
  createArea: vi.fn(),
  updateArea: vi.fn(),
  deleteArea: vi.fn(),
  // Camera linking API
  fetchAreaCameras: vi.fn(),
  linkCameraToArea: vi.fn(),
  unlinkCameraFromArea: vi.fn(),
}));

// ============================================================================
// Test Data
// ============================================================================

const mockHouseholds = [
  {
    id: 1,
    name: 'Svoboda Family',
    created_at: '2026-01-20T10:00:00Z',
  },
  {
    id: 2,
    name: 'Smith Family',
    created_at: '2026-01-20T11:00:00Z',
  },
];

const mockProperties = [
  {
    id: 1,
    household_id: 1,
    name: 'Main House',
    address: '123 Main St',
    timezone: 'America/New_York',
    created_at: '2026-01-20T10:00:00Z',
  },
  {
    id: 2,
    household_id: 1,
    name: 'Beach House',
    address: '456 Beach Rd',
    timezone: 'America/Los_Angeles',
    created_at: '2026-01-20T11:00:00Z',
  },
];

const mockAreas = [
  {
    id: 1,
    property_id: 1,
    name: 'Front Yard',
    description: 'Main entrance area',
    color: '#10B981',
    created_at: '2026-01-20T10:00:00Z',
  },
  {
    id: 2,
    property_id: 1,
    name: 'Backyard',
    description: 'Pool and patio area',
    color: '#3B82F6',
    created_at: '2026-01-20T11:00:00Z',
  },
];

const mockAreaCameras = {
  area_id: 1,
  area_name: 'Front Yard',
  cameras: [
    { id: 'cam-1', name: 'Front Door Camera', status: 'online' },
    { id: 'cam-2', name: 'Driveway Camera', status: 'online' },
  ],
  count: 2,
};

// ============================================================================
// Household Tests
// ============================================================================

describe('useHouseholdsQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchHouseholds as ReturnType<typeof vi.fn>).mockResolvedValue(mockHouseholds);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchHouseholds as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useHouseholdsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with empty households array', () => {
      (api.fetchHouseholds as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useHouseholdsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.households).toEqual([]);
    });
  });

  describe('fetching data', () => {
    it('fetches households on mount', async () => {
      renderHook(() => useHouseholdsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchHouseholds).toHaveBeenCalledTimes(1);
      });
    });

    it('updates households after successful fetch', async () => {
      const { result } = renderHook(() => useHouseholdsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.households).toEqual(mockHouseholds);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useHouseholdsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch households';
      (api.fetchHouseholds as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useHouseholdsQuery(), {
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
      renderHook(() => useHouseholdsQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchHouseholds).not.toHaveBeenCalled();
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useHouseholdsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });
});

describe('useHouseholdQuery', () => {
  const mockHousehold = mockHouseholds[0];

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchHousehold as ReturnType<typeof vi.fn>).mockResolvedValue(mockHousehold);
  });

  it('fetches single household by ID', async () => {
    renderHook(() => useHouseholdQuery(1), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(api.fetchHousehold).toHaveBeenCalledWith(1);
    });
  });

  it('returns household data', async () => {
    const { result } = renderHook(() => useHouseholdQuery(1), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockHousehold);
    });
  });

  it('does not fetch when id is undefined', async () => {
    renderHook(() => useHouseholdQuery(undefined), {
      wrapper: createQueryWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(api.fetchHousehold).not.toHaveBeenCalled();
  });
});

describe('useHouseholdMutation', () => {
  const mockCreatedHousehold = {
    id: 3,
    name: 'New Family',
    created_at: '2026-01-20T12:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.createHousehold as ReturnType<typeof vi.fn>).mockResolvedValue(mockCreatedHousehold);
    (api.updateHousehold as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...mockHouseholds[0],
      name: 'Updated Family',
    });
    (api.deleteHousehold as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    (api.fetchHouseholds as ReturnType<typeof vi.fn>).mockResolvedValue(mockHouseholds);
  });

  describe('createMutation', () => {
    it('creates a new household', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => useHouseholdMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.createMutation.mutateAsync({ name: 'New Family' });
      });

      expect(api.createHousehold).toHaveBeenCalledWith({ name: 'New Family' });
    });

    it('invalidates households query after create', async () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useHouseholdMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.createMutation.mutateAsync({ name: 'New Family' });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.hierarchy.households.all,
      });
    });
  });

  describe('updateMutation', () => {
    it('updates a household', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => useHouseholdMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.updateMutation.mutateAsync({
          id: 1,
          data: { name: 'Updated Family' },
        });
      });

      expect(api.updateHousehold).toHaveBeenCalledWith(1, { name: 'Updated Family' });
    });

    it('invalidates queries after update', async () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useHouseholdMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.updateMutation.mutateAsync({
          id: 1,
          data: { name: 'Updated Family' },
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.hierarchy.households.all,
      });
    });
  });

  describe('deleteMutation', () => {
    it('deletes a household', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => useHouseholdMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.deleteMutation.mutateAsync(1);
      });

      expect(api.deleteHousehold).toHaveBeenCalledWith(1);
    });

    it('invalidates households query after delete', async () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useHouseholdMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.deleteMutation.mutateAsync(1);
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.hierarchy.households.all,
      });
    });
  });
});

// ============================================================================
// Property Tests
// ============================================================================

describe('usePropertiesQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchProperties as ReturnType<typeof vi.fn>).mockResolvedValue(mockProperties);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true when householdId is provided', () => {
      (api.fetchProperties as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => usePropertiesQuery(1), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with empty properties array', () => {
      (api.fetchProperties as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => usePropertiesQuery(1), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.properties).toEqual([]);
    });
  });

  describe('fetching data', () => {
    it('fetches properties on mount', async () => {
      renderHook(() => usePropertiesQuery(1), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchProperties).toHaveBeenCalledWith(1);
      });
    });

    it('updates properties after successful fetch', async () => {
      const { result } = renderHook(() => usePropertiesQuery(1), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.properties).toEqual(mockProperties);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch properties';
      (api.fetchProperties as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => usePropertiesQuery(1), {
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
    it('does not fetch when householdId is undefined', async () => {
      renderHook(() => usePropertiesQuery(undefined), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchProperties).not.toHaveBeenCalled();
    });
  });
});

describe('usePropertyQuery', () => {
  const mockProperty = mockProperties[0];

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchProperty as ReturnType<typeof vi.fn>).mockResolvedValue(mockProperty);
  });

  it('fetches single property by ID', async () => {
    renderHook(() => usePropertyQuery(1), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(api.fetchProperty).toHaveBeenCalledWith(1);
    });
  });

  it('returns property data', async () => {
    const { result } = renderHook(() => usePropertyQuery(1), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockProperty);
    });
  });

  it('does not fetch when id is undefined', async () => {
    renderHook(() => usePropertyQuery(undefined), {
      wrapper: createQueryWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(api.fetchProperty).not.toHaveBeenCalled();
  });
});

describe('usePropertyMutation', () => {
  const mockCreatedProperty = {
    id: 3,
    household_id: 1,
    name: 'Lake House',
    address: '789 Lake Dr',
    timezone: 'America/Chicago',
    created_at: '2026-01-20T12:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.createProperty as ReturnType<typeof vi.fn>).mockResolvedValue(mockCreatedProperty);
    (api.updateProperty as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...mockProperties[0],
      name: 'Updated House',
    });
    (api.deleteProperty as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
  });

  describe('createMutation', () => {
    it('creates a new property', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => usePropertyMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.createMutation.mutateAsync({
          householdId: 1,
          data: { name: 'Lake House', address: '789 Lake Dr' },
        });
      });

      expect(api.createProperty).toHaveBeenCalledWith(1, {
        name: 'Lake House',
        address: '789 Lake Dr',
      });
    });

    it('invalidates properties query after create', async () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => usePropertyMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.createMutation.mutateAsync({
          householdId: 1,
          data: { name: 'Lake House' },
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.hierarchy.properties.all,
      });
    });
  });

  describe('updateMutation', () => {
    it('updates a property', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => usePropertyMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.updateMutation.mutateAsync({
          id: 1,
          data: { name: 'Updated House' },
        });
      });

      expect(api.updateProperty).toHaveBeenCalledWith(1, { name: 'Updated House' });
    });
  });

  describe('deleteMutation', () => {
    it('deletes a property', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => usePropertyMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.deleteMutation.mutateAsync(1);
      });

      expect(api.deleteProperty).toHaveBeenCalledWith(1);
    });

    it('invalidates properties and areas queries after delete', async () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => usePropertyMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.deleteMutation.mutateAsync(1);
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.hierarchy.properties.all,
      });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.hierarchy.areas.all,
      });
    });
  });
});

// ============================================================================
// Area Tests
// ============================================================================

describe('useAreasQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchAreas as ReturnType<typeof vi.fn>).mockResolvedValue(mockAreas);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true when propertyId is provided', () => {
      (api.fetchAreas as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useAreasQuery(1), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with empty areas array', () => {
      (api.fetchAreas as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useAreasQuery(1), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.areas).toEqual([]);
    });
  });

  describe('fetching data', () => {
    it('fetches areas on mount', async () => {
      renderHook(() => useAreasQuery(1), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchAreas).toHaveBeenCalledWith(1);
      });
    });

    it('updates areas after successful fetch', async () => {
      const { result } = renderHook(() => useAreasQuery(1), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.areas).toEqual(mockAreas);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch areas';
      (api.fetchAreas as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useAreasQuery(1), {
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
    it('does not fetch when propertyId is undefined', async () => {
      renderHook(() => useAreasQuery(undefined), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchAreas).not.toHaveBeenCalled();
    });
  });
});

describe('useAreaQuery', () => {
  const mockArea = mockAreas[0];

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchArea as ReturnType<typeof vi.fn>).mockResolvedValue(mockArea);
  });

  it('fetches single area by ID', async () => {
    renderHook(() => useAreaQuery(1), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(api.fetchArea).toHaveBeenCalledWith(1);
    });
  });

  it('returns area data', async () => {
    const { result } = renderHook(() => useAreaQuery(1), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockArea);
    });
  });

  it('does not fetch when id is undefined', async () => {
    renderHook(() => useAreaQuery(undefined), {
      wrapper: createQueryWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(api.fetchArea).not.toHaveBeenCalled();
  });
});

describe('useAreaMutation', () => {
  const mockCreatedArea = {
    id: 3,
    property_id: 1,
    name: 'Garage',
    description: 'Car garage area',
    color: '#F59E0B',
    created_at: '2026-01-20T12:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.createArea as ReturnType<typeof vi.fn>).mockResolvedValue(mockCreatedArea);
    (api.updateArea as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...mockAreas[0],
      name: 'Updated Area',
    });
    (api.deleteArea as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
  });

  describe('createMutation', () => {
    it('creates a new area', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => useAreaMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.createMutation.mutateAsync({
          propertyId: 1,
          data: { name: 'Garage', description: 'Car garage area' },
        });
      });

      expect(api.createArea).toHaveBeenCalledWith(1, {
        name: 'Garage',
        description: 'Car garage area',
      });
    });

    it('invalidates areas query after create', async () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useAreaMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.createMutation.mutateAsync({
          propertyId: 1,
          data: { name: 'Garage' },
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.hierarchy.areas.all,
      });
    });
  });

  describe('updateMutation', () => {
    it('updates an area', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => useAreaMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.updateMutation.mutateAsync({
          id: 1,
          data: { name: 'Updated Area' },
        });
      });

      expect(api.updateArea).toHaveBeenCalledWith(1, { name: 'Updated Area' });
    });
  });

  describe('deleteMutation', () => {
    it('deletes an area', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => useAreaMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.deleteMutation.mutateAsync(1);
      });

      expect(api.deleteArea).toHaveBeenCalledWith(1);
    });

    it('invalidates areas query after delete', async () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useAreaMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.deleteMutation.mutateAsync(1);
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.hierarchy.areas.all,
      });
    });
  });
});

// ============================================================================
// Camera Linking Tests
// ============================================================================

describe('useAreaCamerasQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchAreaCameras as ReturnType<typeof vi.fn>).mockResolvedValue(mockAreaCameras);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true when areaId is provided', () => {
      (api.fetchAreaCameras as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useAreaCamerasQuery(1), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchAreaCameras as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useAreaCamerasQuery(1), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
    });
  });

  describe('fetching data', () => {
    it('fetches area cameras on mount', async () => {
      renderHook(() => useAreaCamerasQuery(1), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchAreaCameras).toHaveBeenCalledWith(1);
      });
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useAreaCamerasQuery(1), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockAreaCameras);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch area cameras';
      (api.fetchAreaCameras as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useAreaCamerasQuery(1), {
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
    it('does not fetch when areaId is undefined', async () => {
      renderHook(() => useAreaCamerasQuery(undefined), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchAreaCameras).not.toHaveBeenCalled();
    });
  });
});

describe('useCameraLinkMutation', () => {
  const mockLinkResponse = {
    area_id: 1,
    camera_id: 'cam-3',
    linked: true,
  };

  const mockUnlinkResponse = {
    area_id: 1,
    camera_id: 'cam-1',
    linked: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.linkCameraToArea as ReturnType<typeof vi.fn>).mockResolvedValue(mockLinkResponse);
    (api.unlinkCameraFromArea as ReturnType<typeof vi.fn>).mockResolvedValue(mockUnlinkResponse);
  });

  describe('linkMutation', () => {
    it('links a camera to an area', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => useCameraLinkMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.linkMutation.mutateAsync({
          areaId: 1,
          cameraId: 'cam-3',
        });
      });

      expect(api.linkCameraToArea).toHaveBeenCalledWith(1, 'cam-3');
    });

    it('invalidates area cameras query after link', async () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCameraLinkMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.linkMutation.mutateAsync({
          areaId: 1,
          cameraId: 'cam-3',
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.hierarchy.areas.cameras(1),
      });
    });

    it('returns correct link response', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => useCameraLinkMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      let response;
      await act(async () => {
        response = await result.current.linkMutation.mutateAsync({
          areaId: 1,
          cameraId: 'cam-3',
        });
      });

      expect(response).toEqual(mockLinkResponse);
    });
  });

  describe('unlinkMutation', () => {
    it('unlinks a camera from an area', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => useCameraLinkMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.unlinkMutation.mutateAsync({
          areaId: 1,
          cameraId: 'cam-1',
        });
      });

      expect(api.unlinkCameraFromArea).toHaveBeenCalledWith(1, 'cam-1');
    });

    it('invalidates area cameras query after unlink', async () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCameraLinkMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.unlinkMutation.mutateAsync({
          areaId: 1,
          cameraId: 'cam-1',
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.hierarchy.areas.cameras(1),
      });
    });

    it('returns correct unlink response', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => useCameraLinkMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      let response;
      await act(async () => {
        response = await result.current.unlinkMutation.mutateAsync({
          areaId: 1,
          cameraId: 'cam-1',
        });
      });

      expect(response).toEqual(mockUnlinkResponse);
    });
  });
});

// ============================================================================
// Integration-style Tests
// ============================================================================

describe('Hierarchy hooks integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchHouseholds as ReturnType<typeof vi.fn>).mockResolvedValue(mockHouseholds);
    (api.fetchProperties as ReturnType<typeof vi.fn>).mockResolvedValue(mockProperties);
    (api.fetchAreas as ReturnType<typeof vi.fn>).mockResolvedValue(mockAreas);
  });

  it('allows fetching full hierarchy', async () => {
    const queryClient = createQueryClient();

    // Fetch households
    const { result: householdsResult } = renderHook(() => useHouseholdsQuery(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(householdsResult.current.households).toHaveLength(2);
    });

    // Fetch properties for first household
    const { result: propertiesResult } = renderHook(() => usePropertiesQuery(1), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(propertiesResult.current.properties).toHaveLength(2);
    });

    // Fetch areas for first property
    const { result: areasResult } = renderHook(() => useAreasQuery(1), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(areasResult.current.areas).toHaveLength(2);
    });
  });

  it('handles loading states correctly', async () => {
    (api.fetchHouseholds as ReturnType<typeof vi.fn>).mockImplementation(
      // eslint-disable-next-line @typescript-eslint/no-misused-promises
      () =>
        new Promise((resolve) => {
          setTimeout(() => {
            resolve(mockHouseholds);
          }, 100);
        })
    );

    const { result } = renderHook(() => useHouseholdsQuery(), {
      wrapper: createQueryWrapper(),
    });

    // Initially loading
    expect(result.current.isLoading).toBe(true);
    expect(result.current.households).toEqual([]);

    // After fetch completes
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.households).toEqual(mockHouseholds);
    });
  });

  it('handles errors gracefully', async () => {
    (api.fetchHouseholds as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useHouseholdsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.error).toBeInstanceOf(Error);
        expect(result.current.error?.message).toBe('Network error');
      },
      { timeout: 5000 }
    );
  });
});
