/**
 * Tests for useVehicleMatchQuery hook (NEM-4865)
 *
 * Tests for the vehicle matching query that finds registered vehicles by plate text.
 * Performs case-insensitive matching against the household vehicle registry.
 *
 * @see frontend/src/hooks/useVehicleMatchQuery.ts
 */

import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, beforeEach } from 'vitest';

import { server } from '../../mocks/server';
import { createQueryWrapper } from '../../test-utils/renderWithProviders';
import { useVehicleMatchQuery, vehicleMatchQueryKeys } from '../useVehicleMatchQuery';

import type { RegisteredVehicle, HouseholdMember } from '../useHouseholdApi';

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
  typical_schedule: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const mockMember2: HouseholdMember = {
  id: 2,
  name: 'Jane Smith',
  role: 'family',
  trusted_level: 'partial',
  notes: null,
  typical_schedule: null,
  created_at: '2024-01-02T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
};

const mockVehicle: RegisteredVehicle = {
  id: 1,
  description: 'Silver Tesla Model 3',
  vehicle_type: 'car',
  license_plate: 'ABC123',
  color: 'silver',
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
  owner_id: 2,
  trusted: true,
  created_at: '2024-01-02T00:00:00Z',
};

const mockVehicleNoOwner: RegisteredVehicle = {
  id: 3,
  description: 'Blue Ford F-150',
  vehicle_type: 'truck',
  license_plate: 'TRK456',
  color: 'blue',
  owner_id: null,
  trusted: false,
  created_at: '2024-01-03T00:00:00Z',
};

// ============================================================================
// Tests
// ============================================================================

describe('useVehicleMatchQuery', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE_URL}/api/household/vehicles`, () => {
        return HttpResponse.json([mockVehicle, mockVehicle2, mockVehicleNoOwner]);
      }),
      http.get(`${BASE_URL}/api/household/members`, () => {
        return HttpResponse.json([mockMember, mockMember2]);
      })
    );
  });

  describe('plate matching', () => {
    it('returns matching vehicle when plate text matches exactly', async () => {
      const { result } = renderHook(() => useVehicleMatchQuery('ABC123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.match).toBeDefined();
      expect(result.current.match?.vehicle.id).toBe(1);
      expect(result.current.match?.vehicle.description).toBe('Silver Tesla Model 3');
      expect(result.current.error).toBeNull();
    });

    it('performs case-insensitive matching', async () => {
      const { result } = renderHook(() => useVehicleMatchQuery('abc123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.match).toBeDefined();
      expect(result.current.match?.vehicle.id).toBe(1);
    });

    it('performs case-insensitive matching with mixed case', async () => {
      const { result } = renderHook(() => useVehicleMatchQuery('AbC123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.match).toBeDefined();
      expect(result.current.match?.vehicle.id).toBe(1);
    });

    it('returns null match when plate text does not match any vehicle', async () => {
      const { result } = renderHook(() => useVehicleMatchQuery('UNKNOWN'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.match).toBeNull();
      expect(result.current.error).toBeNull();
    });

    it('matches second vehicle correctly', async () => {
      const { result } = renderHook(() => useVehicleMatchQuery('XYZ789'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.match?.vehicle.id).toBe(2);
      expect(result.current.match?.vehicle.description).toBe('Red Honda CR-V');
    });
  });

  describe('owner resolution', () => {
    it('includes owner when vehicle has owner_id', async () => {
      const { result } = renderHook(() => useVehicleMatchQuery('ABC123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.match?.owner).toBeDefined();
      expect(result.current.match?.owner?.id).toBe(1);
      expect(result.current.match?.owner?.name).toBe('John Doe');
    });

    it('includes correct owner for second vehicle', async () => {
      const { result } = renderHook(() => useVehicleMatchQuery('XYZ789'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.match?.owner).toBeDefined();
      expect(result.current.match?.owner?.id).toBe(2);
      expect(result.current.match?.owner?.name).toBe('Jane Smith');
    });

    it('returns undefined owner when vehicle has no owner_id', async () => {
      const { result } = renderHook(() => useVehicleMatchQuery('TRK456'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.match?.vehicle.id).toBe(3);
      expect(result.current.match?.owner).toBeUndefined();
    });
  });

  describe('null/empty plate handling', () => {
    it('returns null match when plate text is null', () => {
      const { result } = renderHook(() => useVehicleMatchQuery(null), {
        wrapper: createQueryWrapper(),
      });

      // Should not be loading when query is disabled
      expect(result.current.isLoading).toBe(false);
      expect(result.current.match).toBeNull();
    });

    it('returns null match when plate text is empty string', () => {
      const { result } = renderHook(() => useVehicleMatchQuery(''), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.match).toBeNull();
    });

    it('returns null match when plate text is whitespace only', () => {
      const { result } = renderHook(() => useVehicleMatchQuery('   '), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.match).toBeNull();
    });
  });

  describe('loading states', () => {
    it('shows loading state while fetching', async () => {
      server.use(
        http.get(`${BASE_URL}/api/household/vehicles`, async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json([mockVehicle]);
        }),
        http.get(`${BASE_URL}/api/household/members`, async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json([mockMember]);
        })
      );

      const { result } = renderHook(() => useVehicleMatchQuery('ABC123'), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.match).toBeNull();

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('error handling', () => {
    it('handles vehicle fetch error gracefully', async () => {
      server.use(
        http.get(`${BASE_URL}/api/household/vehicles`, () => {
          return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
        })
      );

      const { result } = renderHook(() => useVehicleMatchQuery('ABC123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).not.toBeNull();
        },
        { timeout: 3000 }
      );

      expect(result.current.match).toBeNull();
    });

    it('handles member fetch error gracefully', async () => {
      server.use(
        http.get(`${BASE_URL}/api/household/vehicles`, () => {
          return HttpResponse.json([mockVehicle]);
        }),
        http.get(`${BASE_URL}/api/household/members`, () => {
          return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
        })
      );

      const { result } = renderHook(() => useVehicleMatchQuery('ABC123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).not.toBeNull();
        },
        { timeout: 3000 }
      );
    });
  });

  describe('empty data handling', () => {
    it('handles empty vehicles list', async () => {
      server.use(
        http.get(`${BASE_URL}/api/household/vehicles`, () => {
          return HttpResponse.json([]);
        })
      );

      const { result } = renderHook(() => useVehicleMatchQuery('ABC123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.match).toBeNull();
    });

    it('handles empty members list (vehicle still matches but no owner)', async () => {
      server.use(
        http.get(`${BASE_URL}/api/household/vehicles`, () => {
          return HttpResponse.json([mockVehicle]);
        }),
        http.get(`${BASE_URL}/api/household/members`, () => {
          return HttpResponse.json([]);
        })
      );

      const { result } = renderHook(() => useVehicleMatchQuery('ABC123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.match?.vehicle).toBeDefined();
      expect(result.current.match?.owner).toBeUndefined();
    });
  });
});

describe('vehicleMatchQueryKeys', () => {
  it('generates correct base key', () => {
    expect(vehicleMatchQueryKeys.all).toEqual(['vehicleMatch']);
  });

  it('generates correct match key', () => {
    expect(vehicleMatchQueryKeys.match('ABC123')).toEqual(['vehicleMatch', 'match', 'ABC123']);
  });

  it('generates correct match key with null', () => {
    expect(vehicleMatchQueryKeys.match(null)).toEqual(['vehicleMatch', 'match', null]);
  });
});
