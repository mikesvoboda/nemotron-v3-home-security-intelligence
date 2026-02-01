/**
 * useVehicleMatchQuery - Query hook for matching plate text to registered vehicles
 *
 * Provides a TanStack Query hook that finds registered vehicles by license plate text.
 * Performs case-insensitive matching and resolves the vehicle owner if available.
 *
 * Phase 3: RegisteredVehicle matching integration for LPR UI (NEM-4865)
 *
 * @module hooks/useVehicleMatchQuery
 * @see frontend/src/hooks/useHouseholdApi.ts - Underlying vehicle/member queries
 */

import { useMemo } from 'react';

import {
  useVehiclesQuery,
  useMembersQuery,
  type RegisteredVehicle,
  type HouseholdMember,
} from './useHouseholdApi';

// ============================================================================
// Types
// ============================================================================

/**
 * Represents a matched vehicle with optional owner information.
 */
export interface VehicleMatch {
  /** The matched registered vehicle */
  vehicle: RegisteredVehicle;
  /** The vehicle owner, if owner_id is set and member exists */
  owner?: HouseholdMember;
}

/**
 * Return type for the useVehicleMatchQuery hook.
 */
export interface VehicleMatchQueryResult {
  /** The matched vehicle and owner, or null if no match */
  match: VehicleMatch | null;
  /** Whether the query is currently loading */
  isLoading: boolean;
  /** Any error that occurred during the query */
  error: Error | null;
  /** Whether the query is enabled (plate text is valid) */
  isEnabled: boolean;
}

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for vehicle match queries.
 */
export const vehicleMatchQueryKeys = {
  /** Base key for all vehicle match queries */
  all: ['vehicleMatch'] as const,
  /** Key for a specific plate match query */
  match: (plateText: string | null) => [...vehicleMatchQueryKeys.all, 'match', plateText] as const,
};

// ============================================================================
// Hook
// ============================================================================

/**
 * Query hook to find a matching registered vehicle by license plate text.
 *
 * Performs case-insensitive matching against the household vehicle registry.
 * If a match is found, resolves the vehicle owner from the household members.
 *
 * @param plateText - The license plate text to search for (case-insensitive)
 * @returns Query result with match, loading state, and error
 *
 * @example
 * ```tsx
 * function PlateDetail({ plateText }: { plateText: string }) {
 *   const { match, isLoading, error } = useVehicleMatchQuery(plateText);
 *
 *   if (isLoading) return <Spinner />;
 *   if (error) return <Error message={error.message} />;
 *
 *   if (match) {
 *     return (
 *       <div>
 *         <p>Vehicle: {match.vehicle.description}</p>
 *         {match.owner && <p>Owner: {match.owner.name}</p>}
 *       </div>
 *     );
 *   }
 *
 *   return <p>Unknown vehicle</p>;
 * }
 * ```
 */
export function useVehicleMatchQuery(plateText: string | null): VehicleMatchQueryResult {
  // Determine if query should be enabled
  const normalizedPlate = plateText?.trim() || null;
  const isEnabled = normalizedPlate !== null && normalizedPlate.length > 0;

  // Fetch vehicles and members
  const vehiclesQuery = useVehiclesQuery();
  const membersQuery = useMembersQuery();

  // Compute the match
  const match = useMemo(() => {
    // If disabled or no data, return null
    if (!isEnabled) {
      return null;
    }

    const vehicles = vehiclesQuery.data;
    const members = membersQuery.data;

    if (!vehicles) {
      return null;
    }

    // Find matching vehicle (case-insensitive)
    const normalizedSearch = normalizedPlate.toUpperCase();
    const matchedVehicle = vehicles.find(
      (v) => v.license_plate?.toUpperCase() === normalizedSearch
    );

    if (!matchedVehicle) {
      return null;
    }

    // Resolve owner if available
    let owner: HouseholdMember | undefined;
    if (matchedVehicle.owner_id && members) {
      owner = members.find((m) => m.id === matchedVehicle.owner_id);
    }

    return {
      vehicle: matchedVehicle,
      owner,
    };
  }, [isEnabled, normalizedPlate, vehiclesQuery.data, membersQuery.data]);

  // Compute loading state - only loading if enabled and queries are loading
  const isLoading = isEnabled && (vehiclesQuery.isLoading || membersQuery.isLoading);

  // Compute error - return first error encountered
  const error = vehiclesQuery.error || membersQuery.error;

  return {
    match,
    isLoading,
    error,
    isEnabled,
  };
}

export default useVehicleMatchQuery;
