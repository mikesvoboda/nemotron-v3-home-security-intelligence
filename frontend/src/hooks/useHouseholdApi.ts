/**
 * useHouseholdApi - TanStack Query hooks for household organization API
 *
 * Provides hooks for managing household members, vehicles, and the household
 * organization hierarchy. Uses the following endpoints:
 *
 * Household Members (existing endpoints):
 * - GET /api/household/members - List all household members
 * - POST /api/household/members - Create new member
 * - GET /api/household/members/{member_id} - Get specific member
 * - PATCH /api/household/members/{member_id} - Update member
 * - DELETE /api/household/members/{member_id} - Delete member
 *
 * Registered Vehicles (existing endpoints):
 * - GET /api/household/vehicles - List all registered vehicles
 * - POST /api/household/vehicles - Create new vehicle
 * - GET /api/household/vehicles/{vehicle_id} - Get specific vehicle
 * - PATCH /api/household/vehicles/{vehicle_id} - Update vehicle
 * - DELETE /api/household/vehicles/{vehicle_id} - Delete vehicle
 *
 * Household Hierarchy (Phase 6 endpoints):
 * - GET /api/v1/households - List all households
 * - POST /api/v1/households - Create household
 * - PATCH /api/v1/households/{id} - Update household
 * - DELETE /api/v1/households/{id} - Delete household
 *
 * Phase 7.1: Create HouseholdSettings component (NEM-3134)
 * Part of the Orphaned Infrastructure Integration epic (NEM-3113).
 *
 * @module hooks/useHouseholdApi
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { STATIC_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Type Definitions (matching backend schemas)
// ============================================================================

/**
 * Member role for household members.
 */
export type MemberRole = 'resident' | 'family' | 'service_worker' | 'frequent_visitor';

/**
 * Trust level for household members.
 */
export type TrustLevel = 'full' | 'partial' | 'monitor';

/**
 * Vehicle type for categorization.
 */
export type VehicleType = 'car' | 'truck' | 'motorcycle' | 'suv' | 'van' | 'other';

/**
 * Household member response from the API.
 */
export interface HouseholdMember {
  id: number;
  name: string;
  role: MemberRole;
  trusted_level: TrustLevel;
  notes?: string | null;
  typical_schedule?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

/**
 * Request payload for creating a household member.
 */
export interface HouseholdMemberCreate {
  name: string;
  role: MemberRole;
  trusted_level: TrustLevel;
  notes?: string | null;
  typical_schedule?: Record<string, unknown> | null;
}

/**
 * Request payload for updating a household member.
 */
export interface HouseholdMemberUpdate {
  name?: string | null;
  role?: MemberRole | null;
  trusted_level?: TrustLevel | null;
  notes?: string | null;
  typical_schedule?: Record<string, unknown> | null;
}

/**
 * Registered vehicle response from the API.
 */
export interface RegisteredVehicle {
  id: number;
  description: string;
  vehicle_type: VehicleType;
  license_plate?: string | null;
  color?: string | null;
  owner_id?: number | null;
  trusted: boolean;
  created_at: string;
}

/**
 * Request payload for creating a registered vehicle.
 */
export interface RegisteredVehicleCreate {
  description: string;
  vehicle_type: VehicleType;
  license_plate?: string | null;
  color?: string | null;
  owner_id?: number | null;
  trusted?: boolean;
}

/**
 * Request payload for updating a registered vehicle.
 */
export interface RegisteredVehicleUpdate {
  description?: string | null;
  vehicle_type?: VehicleType | null;
  license_plate?: string | null;
  color?: string | null;
  owner_id?: number | null;
  trusted?: boolean | null;
}

/**
 * Household organization response from the API.
 */
export interface Household {
  id: number;
  name: string;
  created_at: string;
}

/**
 * Request payload for creating a household.
 */
export interface HouseholdCreate {
  name: string;
}

/**
 * Request payload for updating a household.
 */
export interface HouseholdUpdate {
  name?: string | null;
}

/**
 * Household list response from the API.
 */
export interface HouseholdListResponse {
  items: Household[];
  total: number;
}

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for household API.
 */
export const householdQueryKeys = {
  /** Base key for all household queries */
  all: ['household'] as const,
  /** Household members list */
  members: () => [...householdQueryKeys.all, 'members'] as const,
  /** Single household member */
  member: (id: number) => [...householdQueryKeys.members(), id] as const,
  /** Registered vehicles list */
  vehicles: () => [...householdQueryKeys.all, 'vehicles'] as const,
  /** Single registered vehicle */
  vehicle: (id: number) => [...householdQueryKeys.vehicles(), id] as const,
  /** Households list */
  households: () => [...householdQueryKeys.all, 'households'] as const,
  /** Single household */
  household: (id: number) => [...householdQueryKeys.households(), id] as const,
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

// --- Household Members API Functions ---

/**
 * Fetch all household members.
 */
export async function fetchMembers(): Promise<HouseholdMember[]> {
  const response = await fetch(`${BASE_URL}/api/household/members`, {
    method: 'GET',
    headers: buildHeaders(),
  });
  return handleResponse<HouseholdMember[]>(response);
}

/**
 * Create a new household member.
 */
export async function createMember(data: HouseholdMemberCreate): Promise<HouseholdMember> {
  const response = await fetch(`${BASE_URL}/api/household/members`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse<HouseholdMember>(response);
}

/**
 * Update an existing household member.
 */
export async function updateMember(
  id: number,
  data: HouseholdMemberUpdate
): Promise<HouseholdMember> {
  const response = await fetch(`${BASE_URL}/api/household/members/${id}`, {
    method: 'PATCH',
    headers: buildHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse<HouseholdMember>(response);
}

/**
 * Delete a household member.
 */
export async function deleteMember(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/household/members/${id}`, {
    method: 'DELETE',
    headers: buildHeaders(),
  });
  return handleResponse<void>(response);
}

// --- Registered Vehicles API Functions ---

/**
 * Fetch all registered vehicles.
 */
export async function fetchVehicles(): Promise<RegisteredVehicle[]> {
  const response = await fetch(`${BASE_URL}/api/household/vehicles`, {
    method: 'GET',
    headers: buildHeaders(),
  });
  return handleResponse<RegisteredVehicle[]>(response);
}

/**
 * Create a new registered vehicle.
 */
export async function createVehicle(data: RegisteredVehicleCreate): Promise<RegisteredVehicle> {
  const response = await fetch(`${BASE_URL}/api/household/vehicles`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse<RegisteredVehicle>(response);
}

/**
 * Update an existing registered vehicle.
 */
export async function updateVehicle(
  id: number,
  data: RegisteredVehicleUpdate
): Promise<RegisteredVehicle> {
  const response = await fetch(`${BASE_URL}/api/household/vehicles/${id}`, {
    method: 'PATCH',
    headers: buildHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse<RegisteredVehicle>(response);
}

/**
 * Delete a registered vehicle.
 */
export async function deleteVehicle(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/household/vehicles/${id}`, {
    method: 'DELETE',
    headers: buildHeaders(),
  });
  return handleResponse<void>(response);
}

// --- Household Organization API Functions ---

/**
 * Fetch all households.
 */
export async function fetchHouseholds(): Promise<HouseholdListResponse> {
  const response = await fetch(`${BASE_URL}/api/v1/households`, {
    method: 'GET',
    headers: buildHeaders(),
  });
  return handleResponse<HouseholdListResponse>(response);
}

/**
 * Create a new household.
 */
export async function createHousehold(data: HouseholdCreate): Promise<Household> {
  const response = await fetch(`${BASE_URL}/api/v1/households`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse<Household>(response);
}

/**
 * Update an existing household.
 */
export async function updateHousehold(id: number, data: HouseholdUpdate): Promise<Household> {
  const response = await fetch(`${BASE_URL}/api/v1/households/${id}`, {
    method: 'PATCH',
    headers: buildHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse<Household>(response);
}

/**
 * Delete a household.
 */
export async function deleteHousehold(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/v1/households/${id}`, {
    method: 'DELETE',
    headers: buildHeaders(),
  });
  return handleResponse<void>(response);
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook to fetch all household members.
 */
export function useMembersQuery() {
  return useQuery({
    queryKey: householdQueryKeys.members(),
    queryFn: fetchMembers,
    staleTime: STATIC_STALE_TIME,
    retry: 1,
  });
}

/**
 * Hook to create a household member.
 */
export function useCreateMember() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createMember,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: householdQueryKeys.members() });
    },
  });
}

/**
 * Hook to update a household member.
 */
export function useUpdateMember() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: HouseholdMemberUpdate }) =>
      updateMember(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: householdQueryKeys.members() });
    },
  });
}

/**
 * Hook to delete a household member.
 */
export function useDeleteMember() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteMember,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: householdQueryKeys.members() });
    },
  });
}

/**
 * Hook to fetch all registered vehicles.
 */
export function useVehiclesQuery() {
  return useQuery({
    queryKey: householdQueryKeys.vehicles(),
    queryFn: fetchVehicles,
    staleTime: STATIC_STALE_TIME,
    retry: 1,
  });
}

/**
 * Hook to create a registered vehicle.
 */
export function useCreateVehicle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createVehicle,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: householdQueryKeys.vehicles() });
    },
  });
}

/**
 * Hook to update a registered vehicle.
 */
export function useUpdateVehicle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: RegisteredVehicleUpdate }) =>
      updateVehicle(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: householdQueryKeys.vehicles() });
    },
  });
}

/**
 * Hook to delete a registered vehicle.
 */
export function useDeleteVehicle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteVehicle,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: householdQueryKeys.vehicles() });
    },
  });
}

/**
 * Hook to fetch all households.
 */
export function useHouseholdsQuery() {
  return useQuery({
    queryKey: householdQueryKeys.households(),
    queryFn: fetchHouseholds,
    staleTime: STATIC_STALE_TIME,
    retry: 1,
  });
}

/**
 * Hook to create a household.
 */
export function useCreateHousehold() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createHousehold,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: householdQueryKeys.households() });
    },
  });
}

/**
 * Hook to update a household.
 */
export function useUpdateHousehold() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: HouseholdUpdate }) => updateHousehold(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: householdQueryKeys.households() });
    },
  });
}

/**
 * Hook to delete a household.
 */
export function useDeleteHousehold() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteHousehold,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: householdQueryKeys.households() });
    },
  });
}

/**
 * Combined hook for household API operations.
 *
 * Provides queries for members, vehicles, and households,
 * along with mutation functions for CRUD operations.
 */
export function useHouseholdApi() {
  const membersQuery = useMembersQuery();
  const vehiclesQuery = useVehiclesQuery();
  const householdsQuery = useHouseholdsQuery();

  const createMemberMutation = useCreateMember();
  const updateMemberMutation = useUpdateMember();
  const deleteMemberMutation = useDeleteMember();

  const createVehicleMutation = useCreateVehicle();
  const updateVehicleMutation = useUpdateVehicle();
  const deleteVehicleMutation = useDeleteVehicle();

  const createHouseholdMutation = useCreateHousehold();
  const updateHouseholdMutation = useUpdateHousehold();
  const deleteHouseholdMutation = useDeleteHousehold();

  return {
    // Members
    members: membersQuery.data,
    membersLoading: membersQuery.isLoading,
    membersError: membersQuery.error,
    refetchMembers: membersQuery.refetch,
    createMember: createMemberMutation,
    updateMember: updateMemberMutation,
    deleteMember: deleteMemberMutation,

    // Vehicles
    vehicles: vehiclesQuery.data,
    vehiclesLoading: vehiclesQuery.isLoading,
    vehiclesError: vehiclesQuery.error,
    refetchVehicles: vehiclesQuery.refetch,
    createVehicle: createVehicleMutation,
    updateVehicle: updateVehicleMutation,
    deleteVehicle: deleteVehicleMutation,

    // Households
    households: householdsQuery.data,
    householdsLoading: householdsQuery.isLoading,
    householdsError: householdsQuery.error,
    refetchHouseholds: householdsQuery.refetch,
    createHousehold: createHouseholdMutation,
    updateHousehold: updateHouseholdMutation,
    deleteHousehold: deleteHouseholdMutation,
  };
}

export default useHouseholdApi;
