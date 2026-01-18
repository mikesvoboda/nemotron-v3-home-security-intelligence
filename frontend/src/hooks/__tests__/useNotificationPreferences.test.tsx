/**
 * Unit tests for useNotificationPreferences hooks
 *
 * Tests TanStack Query integration for notification preference management:
 * - useNotificationPreferences: Global notification preferences
 * - useCameraNotificationSettings: Camera-specific notification settings
 * - useCameraNotificationSettingMutation: Update camera notification settings
 * - useQuietHoursPeriods: Quiet hours periods
 * - useQuietHoursPeriodMutations: Create and delete quiet hours periods
 *
 * @module hooks/__tests__/useNotificationPreferences
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  useNotificationPreferences,
  useCameraNotificationSettings,
  useCameraNotificationSettingMutation,
  useQuietHoursPeriods,
  useQuietHoursPeriodMutations,
} from '../useNotificationPreferences';

import type {
  NotificationPreferences,
  CameraNotificationSetting,
  CameraNotificationSettingsListResponse,
  QuietHoursPeriod,
  QuietHoursPeriodsListResponse,
  NotificationPreferencesUpdate,
  CameraNotificationSettingUpdate,
  QuietHoursPeriodCreate,
} from '../../types/notificationPreferences';

// ============================================================================
// Mock API Functions
// ============================================================================

const mockFetchNotificationPreferences = vi.fn();
const mockUpdateNotificationPreferences = vi.fn();
const mockFetchCameraNotificationSettings = vi.fn();
const mockUpdateCameraNotificationSetting = vi.fn();
const mockFetchQuietHoursPeriods = vi.fn();
const mockCreateQuietHoursPeriod = vi.fn();
const mockDeleteQuietHoursPeriod = vi.fn();

vi.mock('../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/api')>();
  return {
    ...actual,
    fetchNotificationPreferences: (...args: unknown[]) =>
      mockFetchNotificationPreferences(...args),
    updateNotificationPreferences: (...args: unknown[]) =>
      mockUpdateNotificationPreferences(...args),
    fetchCameraNotificationSettings: (...args: unknown[]) =>
      mockFetchCameraNotificationSettings(...args),
    updateCameraNotificationSetting: (...args: unknown[]) =>
      mockUpdateCameraNotificationSetting(...args),
    fetchQuietHoursPeriods: (...args: unknown[]) => mockFetchQuietHoursPeriods(...args),
    createQuietHoursPeriod: (...args: unknown[]) => mockCreateQuietHoursPeriod(...args),
    deleteQuietHoursPeriod: (...args: unknown[]) => mockDeleteQuietHoursPeriod(...args),
  };
});

// ============================================================================
// Test Utilities
// ============================================================================

/**
 * Create a test wrapper with a fresh QueryClient for each test.
 * Disables retries and caching to ensure tests are isolated.
 */
function createTestWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// ============================================================================
// Test Data Fixtures
// ============================================================================

const mockNotificationPreferences: NotificationPreferences = {
  id: 1,
  enabled: true,
  sound: 'default',
  risk_filters: ['critical', 'high'],
};

const mockCameraSettings: CameraNotificationSetting[] = [
  {
    id: 'setting-1',
    camera_id: 'front_door',
    enabled: true,
    risk_threshold: 70,
  },
  {
    id: 'setting-2',
    camera_id: 'backyard',
    enabled: false,
    risk_threshold: 50,
  },
];

const mockCameraSettingsResponse: CameraNotificationSettingsListResponse = {
  items: mockCameraSettings,
  pagination: {
    total: 2,
    limit: 50,
    offset: 0,
    has_more: false,
  },
};

const mockQuietHoursPeriods: QuietHoursPeriod[] = [
  {
    id: 'period-1',
    label: 'Night Time',
    start_time: '22:00:00',
    end_time: '06:00:00',
    days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
  },
  {
    id: 'period-2',
    label: 'Weekend Mornings',
    start_time: '08:00:00',
    end_time: '10:00:00',
    days: ['saturday', 'sunday'],
  },
];

const mockQuietHoursResponse: QuietHoursPeriodsListResponse = {
  items: mockQuietHoursPeriods,
  pagination: {
    total: 2,
    limit: 50,
    offset: 0,
    has_more: false,
  },
};

// ============================================================================
// useNotificationPreferences Tests
// ============================================================================

describe('useNotificationPreferences', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchNotificationPreferences.mockResolvedValue(mockNotificationPreferences);
  });

  it('fetches notification preferences on mount', async () => {
    const { result } = renderHook(() => useNotificationPreferences(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.preferences).toBeNull();

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.preferences).toEqual(mockNotificationPreferences);
    expect(mockFetchNotificationPreferences).toHaveBeenCalledTimes(1);
  });

  it('handles loading state correctly', async () => {
    const { result } = renderHook(() => useNotificationPreferences(), {
      wrapper: createTestWrapper(),
    });

    // Initial loading state
    expect(result.current.isLoading).toBe(true);
    expect(result.current.preferences).toBeNull();

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // After loading completes
    expect(result.current.isLoading).toBe(false);
    expect(result.current.preferences).toEqual(mockNotificationPreferences);
  });

  it('handles API errors', async () => {
    const mockError = new Error('API request failed');
    mockFetchNotificationPreferences.mockRejectedValue(mockError);

    const { result } = renderHook(() => useNotificationPreferences(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.isLoading).toBe(false);
      },
      { timeout: 2000 }
    );

    expect(result.current.error).toEqual(mockError);
    expect(result.current.preferences).toBeNull();
  });

  it('respects enabled option', async () => {
    renderHook(() => useNotificationPreferences({ enabled: false }), {
      wrapper: createTestWrapper(),
    });

    // Give time for potential fetch
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(mockFetchNotificationPreferences).not.toHaveBeenCalled();
  });

  it('can manually refetch preferences', async () => {
    const { result } = renderHook(() => useNotificationPreferences(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetchNotificationPreferences).toHaveBeenCalledTimes(1);

    // Manually trigger refetch
    void result.current.refetch();

    await waitFor(() => {
      expect(mockFetchNotificationPreferences).toHaveBeenCalledTimes(2);
    });
  });

  it('updates preferences via mutation', async () => {
    const updatedPreferences: NotificationPreferences = {
      ...mockNotificationPreferences,
      enabled: false,
    };
    mockUpdateNotificationPreferences.mockResolvedValue(updatedPreferences);

    const { result } = renderHook(() => useNotificationPreferences(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const update: NotificationPreferencesUpdate = { enabled: false };
    result.current.updateMutation.mutate(update);

    await waitFor(() => {
      expect(result.current.updateMutation.isSuccess).toBe(true);
    });

    expect(mockUpdateNotificationPreferences).toHaveBeenCalledWith(update);
  });

  it('invalidates cache after successful mutation', async () => {
    const updatedPreferences: NotificationPreferences = {
      ...mockNotificationPreferences,
      sound: 'urgent',
    };
    mockUpdateNotificationPreferences.mockResolvedValue(updatedPreferences);

    const { result } = renderHook(() => useNotificationPreferences(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Initial fetch
    expect(mockFetchNotificationPreferences).toHaveBeenCalledTimes(1);

    // Update preferences
    const update: NotificationPreferencesUpdate = { sound: 'urgent' };
    result.current.updateMutation.mutate(update);

    await waitFor(() => {
      expect(result.current.updateMutation.isSuccess).toBe(true);
    });

    // Cache should be invalidated and refetch triggered
    await waitFor(() => {
      expect(mockFetchNotificationPreferences).toHaveBeenCalledTimes(2);
    });
  });

  it('handles mutation errors', async () => {
    const mockError = new Error('Update failed');
    mockUpdateNotificationPreferences.mockRejectedValue(mockError);

    const { result } = renderHook(() => useNotificationPreferences(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const update: NotificationPreferencesUpdate = { enabled: false };
    result.current.updateMutation.mutate(update);

    await waitFor(() => {
      expect(result.current.updateMutation.isError).toBe(true);
    });

    expect(result.current.updateMutation.error).toEqual(mockError);
  });

  it('shows mutation loading state', async () => {
    mockUpdateNotificationPreferences.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(mockNotificationPreferences), 100))
    );

    const { result } = renderHook(() => useNotificationPreferences(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const update: NotificationPreferencesUpdate = { enabled: false };
    result.current.updateMutation.mutate(update);

    // Should show loading state during mutation
    await waitFor(() => {
      expect(result.current.updateMutation.isPending).toBe(true);
    });

    await waitFor(() => {
      expect(result.current.updateMutation.isSuccess).toBe(true);
    });

    expect(result.current.updateMutation.isPending).toBe(false);
  });
});

// ============================================================================
// useCameraNotificationSettings Tests
// ============================================================================

describe('useCameraNotificationSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchCameraNotificationSettings.mockResolvedValue(mockCameraSettingsResponse);
  });

  it('fetches camera notification settings on mount', async () => {
    const { result } = renderHook(() => useCameraNotificationSettings(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.settings).toEqual([]);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.settings).toEqual(mockCameraSettings);
    expect(result.current.count).toBe(2);
    expect(mockFetchCameraNotificationSettings).toHaveBeenCalledTimes(1);
  });

  it('returns empty array when no settings', async () => {
    const emptyResponse: CameraNotificationSettingsListResponse = {
      items: [],
      pagination: {
        total: 0,
        limit: 50,
        offset: 0,
        has_more: false,
      },
    };
    mockFetchCameraNotificationSettings.mockResolvedValue(emptyResponse);

    const { result } = renderHook(() => useCameraNotificationSettings(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.settings).toEqual([]);
    expect(result.current.count).toBe(0);
  });

  it('handles API errors', async () => {
    const mockError = new Error('Failed to fetch settings');
    mockFetchCameraNotificationSettings.mockRejectedValue(mockError);

    const { result } = renderHook(() => useCameraNotificationSettings(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.isLoading).toBe(false);
      },
      { timeout: 2000 }
    );

    expect(result.current.error).toEqual(mockError);
    expect(result.current.settings).toEqual([]);
  });

  it('respects enabled option', async () => {
    renderHook(() => useCameraNotificationSettings({ enabled: false }), {
      wrapper: createTestWrapper(),
    });

    // Give time for potential fetch
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(mockFetchCameraNotificationSettings).not.toHaveBeenCalled();
  });

  it('can manually refetch settings', async () => {
    const { result } = renderHook(() => useCameraNotificationSettings(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetchCameraNotificationSettings).toHaveBeenCalledTimes(1);

    // Manually trigger refetch
    void result.current.refetch();

    await waitFor(() => {
      expect(mockFetchCameraNotificationSettings).toHaveBeenCalledTimes(2);
    });
  });

  it('handles refetching state', async () => {
    // Use a slow response to better observe the refetching state
    mockFetchCameraNotificationSettings.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(mockCameraSettingsResponse), 50))
    );

    const { result } = renderHook(() => useCameraNotificationSettings(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isRefetching).toBe(false);

    // Trigger refetch
    const refetchPromise = result.current.refetch();

    // Wait for refetching to start
    await waitFor(
      () => {
        expect(result.current.isRefetching).toBe(true);
      },
      { timeout: 100 }
    );

    // Wait for refetch to complete
    await refetchPromise;

    await waitFor(() => {
      expect(result.current.isRefetching).toBe(false);
    });
  });
});

// ============================================================================
// useCameraNotificationSettingMutation Tests
// ============================================================================

describe('useCameraNotificationSettingMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('updates camera notification setting', async () => {
    const updatedSetting: CameraNotificationSetting = {
      ...mockCameraSettings[0],
      enabled: false,
      risk_threshold: 80,
    };
    mockUpdateCameraNotificationSetting.mockResolvedValue(updatedSetting);

    const { result } = renderHook(() => useCameraNotificationSettingMutation(), {
      wrapper: createTestWrapper(),
    });

    const update: CameraNotificationSettingUpdate = {
      enabled: false,
      risk_threshold: 80,
    };

    result.current.updateMutation.mutate({
      cameraId: 'front_door',
      update,
    });

    await waitFor(() => {
      expect(result.current.updateMutation.isSuccess).toBe(true);
    });

    expect(mockUpdateCameraNotificationSetting).toHaveBeenCalledWith('front_door', update);
    expect(result.current.updateMutation.data).toEqual(updatedSetting);
  });

  it('handles mutation errors', async () => {
    const mockError = new Error('Update failed');
    mockUpdateCameraNotificationSetting.mockRejectedValue(mockError);

    const { result } = renderHook(() => useCameraNotificationSettingMutation(), {
      wrapper: createTestWrapper(),
    });

    result.current.updateMutation.mutate({
      cameraId: 'front_door',
      update: { enabled: false },
    });

    await waitFor(() => {
      expect(result.current.updateMutation.isError).toBe(true);
    });

    expect(result.current.updateMutation.error).toEqual(mockError);
  });

  it('shows mutation loading state', async () => {
    mockUpdateCameraNotificationSetting.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(mockCameraSettings[0]), 100))
    );

    const { result } = renderHook(() => useCameraNotificationSettingMutation(), {
      wrapper: createTestWrapper(),
    });

    result.current.updateMutation.mutate({
      cameraId: 'front_door',
      update: { enabled: false },
    });

    // Should show loading state during mutation
    await waitFor(() => {
      expect(result.current.updateMutation.isPending).toBe(true);
    });

    await waitFor(() => {
      expect(result.current.updateMutation.isSuccess).toBe(true);
    });

    expect(result.current.updateMutation.isPending).toBe(false);
  });

  it('invalidates camera settings cache after update', async () => {
    mockUpdateCameraNotificationSetting.mockResolvedValue(mockCameraSettings[0]);
    mockFetchCameraNotificationSettings.mockResolvedValue(mockCameraSettingsResponse);

    const wrapper = createTestWrapper();

    // First render the list hook to populate cache
    const { result: listResult } = renderHook(() => useCameraNotificationSettings(), {
      wrapper,
    });

    await waitFor(() => {
      expect(listResult.current.isLoading).toBe(false);
    });

    expect(mockFetchCameraNotificationSettings).toHaveBeenCalledTimes(1);

    // Then render the mutation hook
    const { result: mutationResult } = renderHook(() => useCameraNotificationSettingMutation(), {
      wrapper,
    });

    // Perform update
    mutationResult.current.updateMutation.mutate({
      cameraId: 'front_door',
      update: { enabled: false },
    });

    await waitFor(() => {
      expect(mutationResult.current.updateMutation.isSuccess).toBe(true);
    });

    // Cache should be invalidated and list refetched
    await waitFor(() => {
      expect(mockFetchCameraNotificationSettings).toHaveBeenCalledTimes(2);
    });
  });
});

// ============================================================================
// useQuietHoursPeriods Tests
// ============================================================================

describe('useQuietHoursPeriods', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchQuietHoursPeriods.mockResolvedValue(mockQuietHoursResponse);
  });

  it('fetches quiet hours periods on mount', async () => {
    const { result } = renderHook(() => useQuietHoursPeriods(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.periods).toEqual([]);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.periods).toEqual(mockQuietHoursPeriods);
    expect(result.current.count).toBe(2);
    expect(mockFetchQuietHoursPeriods).toHaveBeenCalledTimes(1);
  });

  it('returns empty array when no periods', async () => {
    const emptyResponse: QuietHoursPeriodsListResponse = {
      items: [],
      pagination: {
        total: 0,
        limit: 50,
        offset: 0,
        has_more: false,
      },
    };
    mockFetchQuietHoursPeriods.mockResolvedValue(emptyResponse);

    const { result } = renderHook(() => useQuietHoursPeriods(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.periods).toEqual([]);
    expect(result.current.count).toBe(0);
  });

  it('handles API errors', async () => {
    const mockError = new Error('Failed to fetch periods');
    mockFetchQuietHoursPeriods.mockRejectedValue(mockError);

    const { result } = renderHook(() => useQuietHoursPeriods(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.isLoading).toBe(false);
      },
      { timeout: 2000 }
    );

    expect(result.current.error).toEqual(mockError);
    expect(result.current.periods).toEqual([]);
  });

  it('respects enabled option', async () => {
    renderHook(() => useQuietHoursPeriods({ enabled: false }), {
      wrapper: createTestWrapper(),
    });

    // Give time for potential fetch
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(mockFetchQuietHoursPeriods).not.toHaveBeenCalled();
  });

  it('can manually refetch periods', async () => {
    const { result } = renderHook(() => useQuietHoursPeriods(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetchQuietHoursPeriods).toHaveBeenCalledTimes(1);

    // Manually trigger refetch
    void result.current.refetch();

    await waitFor(() => {
      expect(mockFetchQuietHoursPeriods).toHaveBeenCalledTimes(2);
    });
  });
});

// ============================================================================
// useQuietHoursPeriodMutations Tests
// ============================================================================

describe('useQuietHoursPeriodMutations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('createMutation', () => {
    it('creates a new quiet hours period', async () => {
      const newPeriod: QuietHoursPeriod = {
        id: 'period-3',
        label: 'Work Hours',
        start_time: '09:00:00',
        end_time: '17:00:00',
        days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
      };
      mockCreateQuietHoursPeriod.mockResolvedValue(newPeriod);

      const { result } = renderHook(() => useQuietHoursPeriodMutations(), {
        wrapper: createTestWrapper(),
      });

      const create: QuietHoursPeriodCreate = {
        label: 'Work Hours',
        start_time: '09:00:00',
        end_time: '17:00:00',
        days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
      };

      result.current.createMutation.mutate(create);

      await waitFor(() => {
        expect(result.current.createMutation.isSuccess).toBe(true);
      });

      expect(mockCreateQuietHoursPeriod).toHaveBeenCalledWith(create);
      expect(result.current.createMutation.data).toEqual(newPeriod);
    });

    it('handles create mutation errors', async () => {
      const mockError = new Error('Create failed');
      mockCreateQuietHoursPeriod.mockRejectedValue(mockError);

      const { result } = renderHook(() => useQuietHoursPeriodMutations(), {
        wrapper: createTestWrapper(),
      });

      const create: QuietHoursPeriodCreate = {
        label: 'Work Hours',
        start_time: '09:00:00',
        end_time: '17:00:00',
        days: ['monday'],
      };

      result.current.createMutation.mutate(create);

      await waitFor(() => {
        expect(result.current.createMutation.isError).toBe(true);
      });

      expect(result.current.createMutation.error).toEqual(mockError);
    });

    it('invalidates cache after successful create', async () => {
      const newPeriod: QuietHoursPeriod = {
        id: 'period-3',
        label: 'New Period',
        start_time: '12:00:00',
        end_time: '13:00:00',
        days: ['monday'],
      };
      mockCreateQuietHoursPeriod.mockResolvedValue(newPeriod);
      mockFetchQuietHoursPeriods.mockResolvedValue(mockQuietHoursResponse);

      const wrapper = createTestWrapper();

      // First render the list hook to populate cache
      const { result: listResult } = renderHook(() => useQuietHoursPeriods(), {
        wrapper,
      });

      await waitFor(() => {
        expect(listResult.current.isLoading).toBe(false);
      });

      expect(mockFetchQuietHoursPeriods).toHaveBeenCalledTimes(1);

      // Then render the mutation hook
      const { result: mutationResult } = renderHook(() => useQuietHoursPeriodMutations(), {
        wrapper,
      });

      // Create new period
      const create: QuietHoursPeriodCreate = {
        label: 'New Period',
        start_time: '12:00:00',
        end_time: '13:00:00',
        days: ['monday'],
      };

      mutationResult.current.createMutation.mutate(create);

      await waitFor(() => {
        expect(mutationResult.current.createMutation.isSuccess).toBe(true);
      });

      // Cache should be invalidated and list refetched
      await waitFor(() => {
        expect(mockFetchQuietHoursPeriods).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('deleteMutation', () => {
    it('deletes a quiet hours period', async () => {
      mockDeleteQuietHoursPeriod.mockResolvedValue(undefined);

      const { result } = renderHook(() => useQuietHoursPeriodMutations(), {
        wrapper: createTestWrapper(),
      });

      result.current.deleteMutation.mutate('period-1');

      await waitFor(() => {
        expect(result.current.deleteMutation.isSuccess).toBe(true);
      });

      expect(mockDeleteQuietHoursPeriod).toHaveBeenCalledWith('period-1');
    });

    it('handles delete mutation errors', async () => {
      const mockError = new Error('Delete failed');
      mockDeleteQuietHoursPeriod.mockRejectedValue(mockError);

      const { result } = renderHook(() => useQuietHoursPeriodMutations(), {
        wrapper: createTestWrapper(),
      });

      result.current.deleteMutation.mutate('period-1');

      await waitFor(() => {
        expect(result.current.deleteMutation.isError).toBe(true);
      });

      expect(result.current.deleteMutation.error).toEqual(mockError);
    });

    it('invalidates cache after successful delete', async () => {
      mockDeleteQuietHoursPeriod.mockResolvedValue(undefined);
      mockFetchQuietHoursPeriods.mockResolvedValue(mockQuietHoursResponse);

      const wrapper = createTestWrapper();

      // First render the list hook to populate cache
      const { result: listResult } = renderHook(() => useQuietHoursPeriods(), {
        wrapper,
      });

      await waitFor(() => {
        expect(listResult.current.isLoading).toBe(false);
      });

      expect(mockFetchQuietHoursPeriods).toHaveBeenCalledTimes(1);

      // Then render the mutation hook
      const { result: mutationResult } = renderHook(() => useQuietHoursPeriodMutations(), {
        wrapper,
      });

      // Delete period
      mutationResult.current.deleteMutation.mutate('period-1');

      await waitFor(() => {
        expect(mutationResult.current.deleteMutation.isSuccess).toBe(true);
      });

      // Cache should be invalidated and list refetched
      await waitFor(() => {
        expect(mockFetchQuietHoursPeriods).toHaveBeenCalledTimes(2);
      });
    });
  });
});
