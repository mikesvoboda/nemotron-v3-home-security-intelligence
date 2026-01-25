import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useIntegratedNotifications } from './useIntegratedNotifications';

// Mock the notification preferences API
vi.mock('../services/api', () => ({
  fetchNotificationPreferences: vi.fn().mockResolvedValue({
    id: 1,
    enabled: true,
    sound: 'default',
    risk_filters: ['critical', 'high', 'medium'],
  }),
  updateNotificationPreferences: vi.fn().mockResolvedValue({
    id: 1,
    enabled: false,
    sound: 'default',
    risk_filters: ['critical', 'high', 'medium'],
  }),
}));

describe('useIntegratedNotifications', () => {
  let queryClient: QueryClient;

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    // Mock Notification API
    const mockNotification = vi.fn() as unknown as typeof Notification;
    Object.assign(mockNotification, {
      permission: 'granted' as NotificationPermission,
      requestPermission: vi.fn().mockResolvedValue('granted' as NotificationPermission),
    });
    vi.stubGlobal('Notification', mockNotification);

    // Mock document.hasFocus
    vi.spyOn(document, 'hasFocus').mockReturnValue(false);

    // Mock AudioContext
    const mockGainNode = {
      gain: { value: 0.5 },
      connect: vi.fn(),
    };

    const mockSourceNode = {
      buffer: null,
      connect: vi.fn(),
      start: vi.fn(),
      stop: vi.fn(),
      onended: null,
    };

    class MockAudioContext {
      state = 'running';
      resume = vi.fn().mockResolvedValue(undefined);
      close = vi.fn().mockResolvedValue(undefined);
      createGain = vi.fn().mockReturnValue(mockGainNode);
      createBufferSource = vi.fn().mockReturnValue(mockSourceNode);
      decodeAudioData = vi.fn().mockResolvedValue({ duration: 1 } as AudioBuffer);
      destination = {} as AudioDestinationNode;
    }

    vi.stubGlobal('AudioContext', MockAudioContext);

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        arrayBuffer: vi.fn().mockResolvedValue(new ArrayBuffer(8)),
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    queryClient.clear();
  });

  describe('initialization', () => {
    it('loads preferences and initializes all notification hooks', async () => {
      const { result } = renderHook(() => useIntegratedNotifications(), { wrapper });

      // Initially loading
      expect(result.current.isLoading).toBe(true);

      // Wait for preferences to load
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Check state reflects preferences
      expect(result.current.isEnabled).toBe(true);
      expect(result.current.soundPreference).toBe('default');
      expect(result.current.riskFilters).toEqual(['critical', 'high', 'medium']);
    });

    it('initializes desktop notifications with correct options', async () => {
      const { result } = renderHook(() => useIntegratedNotifications(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.desktopSupported).toBe(true);
      expect(result.current.desktopPermission).toBe('granted');
      expect(result.current.desktopHasPermission).toBe(true);
    });

    it('initializes push notifications', async () => {
      const { result } = renderHook(() => useIntegratedNotifications(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.pushSupported).toBe(true);
      expect(result.current.pushPermission).toBe('granted');
      expect(result.current.pushHasPermission).toBe(true);
    });

    it('initializes audio notifications', async () => {
      const { result } = renderHook(() => useIntegratedNotifications(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.audioVolume).toBe(0.5);
    });
  });

  describe('exports correct functions', () => {
    it('exports showSecurityAlert function', async () => {
      const { result } = renderHook(() => useIntegratedNotifications(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.showSecurityAlert).toBe('function');
    });

    it('exports toggleNotifications function', async () => {
      const { result } = renderHook(() => useIntegratedNotifications(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.toggleNotifications).toBe('function');
    });

    it('exports updatePreferences function', async () => {
      const { result } = renderHook(() => useIntegratedNotifications(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.updatePreferences).toBe('function');
    });

    it('exports closeAllNotifications function', async () => {
      const { result } = renderHook(() => useIntegratedNotifications(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.closeAllNotifications).toBe('function');
    });

    it('exports permission request functions', async () => {
      const { result } = renderHook(() => useIntegratedNotifications(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.requestDesktopPermission).toBe('function');
      expect(typeof result.current.requestPushPermission).toBe('function');
    });

    it('exports audio control functions', async () => {
      const { result } = renderHook(() => useIntegratedNotifications(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.setAudioVolume).toBe('function');
      expect(typeof result.current.resumeAudio).toBe('function');
    });
  });

  describe('custom options', () => {
    it('uses custom initial volume', async () => {
      const { result } = renderHook(
        () => useIntegratedNotifications({ initialVolume: 0.8 }),
        { wrapper }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.audioVolume).toBe(0.8);
    });
  });
});
