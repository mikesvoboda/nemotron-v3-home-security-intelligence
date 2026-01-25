/**
 * Tests for useSystemSetting hook (NEM-3638).
 */
/* eslint-disable import/order */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useSystemSetting,
  useSystemSettings,
  systemSettingQueryKeys,
} from './useSystemSetting';

// Mock the API module
vi.mock('../services/systemSettingsApi', () => ({
  fetchSystemSetting: vi.fn(),
  fetchSystemSettings: vi.fn(),
  updateSystemSetting: vi.fn(),
  deleteSystemSetting: vi.fn(),
}));

import {
  fetchSystemSetting,
  fetchSystemSettings,
  updateSystemSetting,
  deleteSystemSetting,
} from '../services/systemSettingsApi';

const mockFetchSystemSetting = vi.mocked(fetchSystemSetting);
const mockFetchSystemSettings = vi.mocked(fetchSystemSettings);
const mockUpdateSystemSetting = vi.mocked(updateSystemSetting);
const mockDeleteSystemSetting = vi.mocked(deleteSystemSetting);

describe('useSystemSetting', () => {
  let queryClient: QueryClient;

  const createWrapper = () => {
    return function Wrapper({ children }: { children: React.ReactNode }) {
      return React.createElement(
        QueryClientProvider,
        { client: queryClient },
        children
      );
    };
  };

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          staleTime: 0,
        },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    queryClient.clear();
  });

  describe('systemSettingQueryKeys', () => {
    it('generates correct query keys', () => {
      expect(systemSettingQueryKeys.all).toEqual(['system-settings']);
      expect(systemSettingQueryKeys.list()).toEqual(['system-settings', 'list']);
      expect(systemSettingQueryKeys.detail('test_key')).toEqual([
        'system-settings',
        'detail',
        'test_key',
      ]);
    });
  });

  describe('useSystemSetting hook', () => {
    it('fetches setting on mount', async () => {
      const mockSetting = {
        key: 'test_setting',
        value: { enabled: true },
        updated_at: '2026-01-25T12:00:00Z',
      };
      mockFetchSystemSetting.mockResolvedValueOnce(mockSetting);

      const { result } = renderHook(
        () => useSystemSetting({ key: 'test_setting' }),
        { wrapper: createWrapper() }
      );

      // Initially loading
      expect(result.current.isLoading).toBe(true);

      // Wait for data
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.setting).toEqual(mockSetting);
      expect(mockFetchSystemSetting).toHaveBeenCalledWith('test_setting');
    });

    it('does not fetch when enabled is false', () => {
      const { result } = renderHook(
        () => useSystemSetting({ key: 'test_setting', enabled: false }),
        { wrapper: createWrapper() }
      );

      expect(result.current.isLoading).toBe(false);
      expect(mockFetchSystemSetting).not.toHaveBeenCalled();
    });

    it('does not fetch when key is empty', () => {
      const { result } = renderHook(
        () => useSystemSetting({ key: '' }),
        { wrapper: createWrapper() }
      );

      expect(result.current.isLoading).toBe(false);
      expect(mockFetchSystemSetting).not.toHaveBeenCalled();
    });

    it('handles 404 error gracefully', async () => {
      const error = new Error('404 Not Found');
      mockFetchSystemSetting.mockRejectedValueOnce(error);

      const { result } = renderHook(
        () => useSystemSetting({ key: 'nonexistent' }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.isNotFound).toBe(true);
      expect(result.current.setting).toBeUndefined();
    });

    it('provides update mutation', async () => {
      const mockSetting = {
        key: 'test_setting',
        value: { enabled: true },
        updated_at: '2026-01-25T12:00:00Z',
      };
      mockFetchSystemSetting.mockResolvedValueOnce(mockSetting);

      const updatedSetting = {
        ...mockSetting,
        value: { enabled: false },
        updated_at: '2026-01-25T13:00:00Z',
      };
      mockUpdateSystemSetting.mockResolvedValueOnce(updatedSetting);

      const { result } = renderHook(
        () => useSystemSetting({ key: 'test_setting' }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Trigger update
      result.current.updateSetting.mutate({ enabled: false });

      await waitFor(() => {
        expect(mockUpdateSystemSetting).toHaveBeenCalledWith('test_setting', {
          enabled: false,
        });
      });
    });

    it('provides delete mutation', async () => {
      const mockSetting = {
        key: 'test_setting',
        value: { enabled: true },
        updated_at: '2026-01-25T12:00:00Z',
      };
      mockFetchSystemSetting.mockResolvedValueOnce(mockSetting);
      mockDeleteSystemSetting.mockResolvedValueOnce(undefined);

      const { result } = renderHook(
        () => useSystemSetting({ key: 'test_setting' }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Trigger delete
      result.current.deleteSetting.mutate();

      await waitFor(() => {
        expect(mockDeleteSystemSetting).toHaveBeenCalledWith('test_setting');
      });
    });
  });

  describe('useSystemSettings hook', () => {
    it('fetches all settings on mount', async () => {
      const mockResponse = {
        items: [
          {
            key: 'setting1',
            value: { a: 1 },
            updated_at: '2026-01-25T12:00:00Z',
          },
          {
            key: 'setting2',
            value: { b: 2 },
            updated_at: '2026-01-25T11:00:00Z',
          },
        ],
        total: 2,
      };
      mockFetchSystemSettings.mockResolvedValueOnce(mockResponse);

      const { result } = renderHook(() => useSystemSettings(), {
        wrapper: createWrapper(),
      });

      // Initially loading
      expect(result.current.isLoading).toBe(true);

      // Wait for data
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.settings).toHaveLength(2);
      expect(result.current.total).toBe(2);
      expect(result.current.settings[0].key).toBe('setting1');
    });

    it('does not fetch when enabled is false', () => {
      const { result } = renderHook(() => useSystemSettings({ enabled: false }), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(mockFetchSystemSettings).not.toHaveBeenCalled();
    });

    it('returns empty array when no data', () => {
      const { result } = renderHook(() => useSystemSettings({ enabled: false }), {
        wrapper: createWrapper(),
      });

      expect(result.current.settings).toEqual([]);
      expect(result.current.total).toBe(0);
    });
  });
});
