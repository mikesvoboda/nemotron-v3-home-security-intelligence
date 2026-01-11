/**
 * useNotificationPreferencesQuery - TanStack Query hooks for notification preferences
 *
 * This module provides hooks for fetching and mutating notification preferences data
 * using TanStack Query. It includes:
 * - useGlobalNotificationPreferencesQuery: Fetch global preferences
 * - useCameraNotificationSettingsQuery: Fetch all camera settings
 * - useQuietHoursPeriodsQuery: Fetch quiet hours periods
 * - useNotificationPreferencesMutation: Create, update, and delete operations
 *
 * @module hooks/useNotificationPreferencesQuery
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import { DEFAULT_STALE_TIME } from '../services/queryClient';

import type {
  NotificationPreferences,
  NotificationPreferencesUpdate,
  CameraNotificationSetting,
  CameraNotificationSettingUpdate,
  CameraNotificationSettingsListResponse,
  QuietHoursPeriod,
  QuietHoursPeriodCreate,
  QuietHoursPeriodsListResponse,
} from '../types/notificationPreferences';

// ============================================================================
// Query Keys
// ============================================================================

export const notificationPreferencesKeys = {
  all: ['notification-preferences'] as const,
  global: () => [...notificationPreferencesKeys.all, 'global'] as const,
  cameras: () => [...notificationPreferencesKeys.all, 'cameras'] as const,
  camera: (cameraId: string) => [...notificationPreferencesKeys.cameras(), cameraId] as const,
  quietHours: () => [...notificationPreferencesKeys.all, 'quiet-hours'] as const,
};

// ============================================================================
// API Functions
// ============================================================================

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `HTTP ${response.status}`);
  }
  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function fetchGlobalPreferences(): Promise<NotificationPreferences> {
  const response = await fetch(`${API_BASE_URL}/api/notification-preferences/`);
  return handleResponse<NotificationPreferences>(response);
}

async function updateGlobalPreferences(
  data: NotificationPreferencesUpdate
): Promise<NotificationPreferences> {
  const response = await fetch(`${API_BASE_URL}/api/notification-preferences/`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse<NotificationPreferences>(response);
}

async function fetchCameraSettings(): Promise<CameraNotificationSettingsListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/notification-preferences/cameras`);
  return handleResponse<CameraNotificationSettingsListResponse>(response);
}

async function updateCameraSetting(
  cameraId: string,
  data: CameraNotificationSettingUpdate
): Promise<CameraNotificationSetting> {
  const response = await fetch(`${API_BASE_URL}/api/notification-preferences/cameras/${cameraId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse<CameraNotificationSetting>(response);
}

async function fetchQuietHours(): Promise<QuietHoursPeriodsListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/notification-preferences/quiet-hours`);
  return handleResponse<QuietHoursPeriodsListResponse>(response);
}

async function createQuietHours(data: QuietHoursPeriodCreate): Promise<QuietHoursPeriod> {
  const response = await fetch(`${API_BASE_URL}/api/notification-preferences/quiet-hours`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse<QuietHoursPeriod>(response);
}

async function deleteQuietHours(periodId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/notification-preferences/quiet-hours/${periodId}`, {
    method: 'DELETE',
  });
  return handleResponse<void>(response);
}

// ============================================================================
// useGlobalNotificationPreferencesQuery - Fetch global preferences
// ============================================================================

export interface UseGlobalNotificationPreferencesQueryOptions {
  enabled?: boolean;
  staleTime?: number;
}

export interface UseGlobalNotificationPreferencesQueryReturn {
  preferences: NotificationPreferences | undefined;
  isLoading: boolean;
  isRefetching: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch global notification preferences using TanStack Query.
 */
export function useGlobalNotificationPreferencesQuery(
  options: UseGlobalNotificationPreferencesQueryOptions = {}
): UseGlobalNotificationPreferencesQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: notificationPreferencesKeys.global(),
    queryFn: fetchGlobalPreferences,
    enabled,
    staleTime,
    retry: 1,
  });

  return {
    preferences: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useCameraNotificationSettingsQuery - Fetch all camera settings
// ============================================================================

export interface UseCameraNotificationSettingsQueryOptions {
  enabled?: boolean;
  staleTime?: number;
}

export interface UseCameraNotificationSettingsQueryReturn {
  settings: CameraNotificationSetting[];
  isLoading: boolean;
  isRefetching: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch all camera notification settings using TanStack Query.
 */
export function useCameraNotificationSettingsQuery(
  options: UseCameraNotificationSettingsQueryOptions = {}
): UseCameraNotificationSettingsQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: notificationPreferencesKeys.cameras(),
    queryFn: fetchCameraSettings,
    enabled,
    staleTime,
    retry: 1,
  });

  const settings = useMemo(() => query.data?.items ?? [], [query.data]);

  return {
    settings,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useQuietHoursPeriodsQuery - Fetch quiet hours periods
// ============================================================================

export interface UseQuietHoursPeriodsQueryOptions {
  enabled?: boolean;
  staleTime?: number;
}

export interface UseQuietHoursPeriodsQueryReturn {
  periods: QuietHoursPeriod[];
  isLoading: boolean;
  isRefetching: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch all quiet hours periods using TanStack Query.
 */
export function useQuietHoursPeriodsQuery(
  options: UseQuietHoursPeriodsQueryOptions = {}
): UseQuietHoursPeriodsQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: notificationPreferencesKeys.quietHours(),
    queryFn: fetchQuietHours,
    enabled,
    staleTime,
    retry: 1,
  });

  const periods = useMemo(() => query.data?.items ?? [], [query.data]);

  return {
    periods,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useNotificationPreferencesMutation - All mutation operations
// ============================================================================

export interface UseNotificationPreferencesMutationReturn {
  /** Mutation for updating global preferences */
  updateGlobalMutation: ReturnType<
    typeof useMutation<NotificationPreferences, Error, NotificationPreferencesUpdate>
  >;
  /** Mutation for updating camera settings */
  updateCameraMutation: ReturnType<
    typeof useMutation<
      CameraNotificationSetting,
      Error,
      { cameraId: string; data: CameraNotificationSettingUpdate }
    >
  >;
  /** Mutation for creating quiet hours period */
  createQuietHoursMutation: ReturnType<
    typeof useMutation<QuietHoursPeriod, Error, QuietHoursPeriodCreate>
  >;
  /** Mutation for deleting quiet hours period */
  deleteQuietHoursMutation: ReturnType<typeof useMutation<void, Error, string>>;
}

/**
 * Hook providing mutations for notification preferences CRUD operations.
 */
export function useNotificationPreferencesMutation(): UseNotificationPreferencesMutationReturn {
  const queryClient = useQueryClient();

  const updateGlobalMutation = useMutation({
    mutationFn: (data: NotificationPreferencesUpdate) => updateGlobalPreferences(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: notificationPreferencesKeys.global() });
    },
  });

  const updateCameraMutation = useMutation({
    mutationFn: ({ cameraId, data }: { cameraId: string; data: CameraNotificationSettingUpdate }) =>
      updateCameraSetting(cameraId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: notificationPreferencesKeys.cameras() });
    },
  });

  const createQuietHoursMutation = useMutation({
    mutationFn: (data: QuietHoursPeriodCreate) => createQuietHours(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: notificationPreferencesKeys.quietHours() });
    },
  });

  const deleteQuietHoursMutation = useMutation({
    mutationFn: (periodId: string) => deleteQuietHours(periodId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: notificationPreferencesKeys.quietHours() });
    },
  });

  return {
    updateGlobalMutation,
    updateCameraMutation,
    createQuietHoursMutation,
    deleteQuietHoursMutation,
  };
}
