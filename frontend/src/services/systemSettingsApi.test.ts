/**
 * Tests for SystemSetting Key-Value Store API client (NEM-3638).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchSystemSettings,
  fetchSystemSetting,
  updateSystemSetting,
  deleteSystemSetting,
  type SystemSettingResponse,
  type SystemSettingListResponse,
} from './systemSettingsApi';

// Mock the fetchApi function
vi.mock('./api', () => ({
  fetchApi: vi.fn(),
}));

import { fetchApi } from './api';
const mockFetchApi = vi.mocked(fetchApi);

describe('systemSettingsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('fetchSystemSettings', () => {
    it('calls the correct endpoint', async () => {
      const mockResponse: SystemSettingListResponse = {
        items: [],
        total: 0,
      };
      mockFetchApi.mockResolvedValueOnce(mockResponse);

      await fetchSystemSettings();

      expect(mockFetchApi).toHaveBeenCalledWith('/api/v1/system-settings');
    });

    it('returns list of settings', async () => {
      const mockResponse: SystemSettingListResponse = {
        items: [
          {
            key: 'setting1',
            value: { enabled: true },
            updated_at: '2026-01-25T12:00:00Z',
          },
          {
            key: 'setting2',
            value: { threshold: 0.5 },
            updated_at: '2026-01-25T11:00:00Z',
          },
        ],
        total: 2,
      };
      mockFetchApi.mockResolvedValueOnce(mockResponse);

      const result = await fetchSystemSettings();

      expect(result.items).toHaveLength(2);
      expect(result.total).toBe(2);
      expect(result.items[0].key).toBe('setting1');
    });
  });

  describe('fetchSystemSetting', () => {
    it('calls the correct endpoint with key', async () => {
      const mockResponse: SystemSettingResponse = {
        key: 'test_setting',
        value: { data: 'value' },
        updated_at: '2026-01-25T12:00:00Z',
      };
      mockFetchApi.mockResolvedValueOnce(mockResponse);

      await fetchSystemSetting('test_setting');

      expect(mockFetchApi).toHaveBeenCalledWith('/api/v1/system-settings/test_setting');
    });

    it('encodes special characters in key', async () => {
      const mockResponse: SystemSettingResponse = {
        key: 'test_setting',
        value: {},
        updated_at: '2026-01-25T12:00:00Z',
      };
      mockFetchApi.mockResolvedValueOnce(mockResponse);

      // Keys with special characters should be encoded
      await fetchSystemSetting('test/setting');

      expect(mockFetchApi).toHaveBeenCalledWith('/api/v1/system-settings/test%2Fsetting');
    });

    it('returns the setting', async () => {
      const mockResponse: SystemSettingResponse = {
        key: 'test_setting',
        value: { enabled: true, threshold: 0.75 },
        updated_at: '2026-01-25T12:00:00Z',
      };
      mockFetchApi.mockResolvedValueOnce(mockResponse);

      const result = await fetchSystemSetting('test_setting');

      expect(result.key).toBe('test_setting');
      expect(result.value).toEqual({ enabled: true, threshold: 0.75 });
    });
  });

  describe('updateSystemSetting', () => {
    it('calls the correct endpoint with PATCH method', async () => {
      const mockResponse: SystemSettingResponse = {
        key: 'test_setting',
        value: { new: 'value' },
        updated_at: '2026-01-25T12:00:00Z',
      };
      mockFetchApi.mockResolvedValueOnce(mockResponse);

      await updateSystemSetting('test_setting', { new: 'value' });

      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/v1/system-settings/test_setting',
        {
          method: 'PATCH',
          body: JSON.stringify({ value: { new: 'value' } }),
        }
      );
    });

    it('returns the updated setting', async () => {
      const mockResponse: SystemSettingResponse = {
        key: 'test_setting',
        value: { updated: true },
        updated_at: '2026-01-25T12:00:00Z',
      };
      mockFetchApi.mockResolvedValueOnce(mockResponse);

      const result = await updateSystemSetting('test_setting', { updated: true });

      expect(result.value).toEqual({ updated: true });
    });

    it('encodes special characters in key', async () => {
      const mockResponse: SystemSettingResponse = {
        key: 'test_setting',
        value: {},
        updated_at: '2026-01-25T12:00:00Z',
      };
      mockFetchApi.mockResolvedValueOnce(mockResponse);

      await updateSystemSetting('test/setting', {});

      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/v1/system-settings/test%2Fsetting',
        expect.any(Object)
      );
    });
  });

  describe('deleteSystemSetting', () => {
    it('calls the correct endpoint with DELETE method', async () => {
      mockFetchApi.mockResolvedValueOnce(undefined);

      await deleteSystemSetting('test_setting');

      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/v1/system-settings/test_setting',
        {
          method: 'DELETE',
        }
      );
    });

    it('encodes special characters in key', async () => {
      mockFetchApi.mockResolvedValueOnce(undefined);

      await deleteSystemSetting('test/setting');

      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/v1/system-settings/test%2Fsetting',
        {
          method: 'DELETE',
        }
      );
    });
  });
});
