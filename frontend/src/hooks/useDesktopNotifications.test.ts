import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useDesktopNotifications } from './useDesktopNotifications';

describe('useDesktopNotifications', () => {

  let notificationSpyMock: any;

  let notificationCloseMock: any;

  beforeEach(() => {
    vi.useFakeTimers();

    notificationSpyMock = vi.fn();
    notificationCloseMock = vi.fn();

    // Create Notification mock class with local references
    class MockNotification {
      close = (): void => {
        notificationCloseMock();
      };
      onclick: ((event: Event) => void) | null = null;
      onclose: (() => void) | null = null;

      constructor(title: string, options?: NotificationOptions) {
        notificationSpyMock(title, options);
      }

      static permission: NotificationPermission = 'default';
      static requestPermission = vi.fn().mockResolvedValue('granted' as NotificationPermission);
    }

    vi.stubGlobal('Notification', MockNotification);

    // Mock document.hasFocus
    vi.spyOn(document, 'hasFocus').mockReturnValue(true);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // Helper to set permission
  const setPermission = (permission: NotificationPermission) => {
    (Notification as unknown as { permission: NotificationPermission }).permission = permission;
  };

  describe('initialization', () => {
    it('initializes with default permission state', () => {
      const { result } = renderHook(() => useDesktopNotifications());

      expect(result.current.permission).toBe('default');
      expect(result.current.isSupported).toBe(true);
      expect(result.current.hasPermission).toBe(false);
      expect(result.current.isDenied).toBe(false);
    });

    it('initializes with granted permission', () => {
      setPermission('granted');

      const { result } = renderHook(() => useDesktopNotifications());

      expect(result.current.permission).toBe('granted');
      expect(result.current.hasPermission).toBe(true);
    });

    it('initializes with denied permission', () => {
      setPermission('denied');

      const { result } = renderHook(() => useDesktopNotifications());

      expect(result.current.permission).toBe('denied');
      expect(result.current.isDenied).toBe(true);
    });

    it('handles missing Notification API', () => {
      vi.stubGlobal('Notification', undefined);

      const { result } = renderHook(() => useDesktopNotifications());

      expect(result.current.isSupported).toBe(false);
      expect(result.current.permission).toBe('denied');
    });
  });

  describe('requestPermission', () => {
    it('requests permission and updates state', async () => {
      const { result } = renderHook(() => useDesktopNotifications());

      let permissionResult: NotificationPermission = 'default';
      await act(async () => {
        permissionResult = await result.current.requestPermission();
      });

      expect(permissionResult).toBe('granted');
      expect(result.current.permission).toBe('granted');
      expect(result.current.hasPermission).toBe(true);
    });

    it('handles denied permission', async () => {
      (Notification.requestPermission as ReturnType<typeof vi.fn>).mockResolvedValue('denied');

      const { result } = renderHook(() => useDesktopNotifications());

      await act(async () => {
        await result.current.requestPermission();
      });

      expect(result.current.permission).toBe('denied');
      expect(result.current.isDenied).toBe(true);
    });

    it('returns denied when Notification is not supported', async () => {
      vi.stubGlobal('Notification', undefined);

      const { result } = renderHook(() => useDesktopNotifications());

      let permissionResult: NotificationPermission = 'default';
      await act(async () => {
        permissionResult = await result.current.requestPermission();
      });

      expect(permissionResult).toBe('denied');
    });
  });

  describe('showNotification', () => {
    it('shows notification when permission is granted', () => {
      setPermission('granted');

      const { result } = renderHook(() => useDesktopNotifications());

      act(() => {
        result.current.showNotification({
          title: 'Test Title',
          body: 'Test Body',
        });
      });

      expect(notificationSpyMock).toHaveBeenCalledWith(
        'Test Title',
        expect.objectContaining({
          body: 'Test Body',
        })
      );
    });

    it('does not show notification when permission is not granted', () => {
      const { result } = renderHook(() => useDesktopNotifications());

      act(() => {
        result.current.showNotification({
          title: 'Test Title',
        });
      });

      expect(notificationSpyMock).not.toHaveBeenCalled();
    });

    it('does not show notification when disabled', () => {
      setPermission('granted');

      const { result } = renderHook(() => useDesktopNotifications({ enabled: false }));

      act(() => {
        result.current.showNotification({
          title: 'Test Title',
        });
      });

      expect(notificationSpyMock).not.toHaveBeenCalled();
    });

    it('auto-closes notification after timeout', () => {
      setPermission('granted');

      const { result } = renderHook(() => useDesktopNotifications());

      act(() => {
        result.current.showNotification({
          title: 'Test Title',
          autoCloseMs: 3000,
        });
      });

      expect(notificationCloseMock).not.toHaveBeenCalled();

      act(() => {
        vi.advanceTimersByTime(3000);
      });

      expect(notificationCloseMock).toHaveBeenCalled();
    });

    it('does not auto-close when requireInteraction is true', () => {
      setPermission('granted');

      const { result } = renderHook(() => useDesktopNotifications());

      act(() => {
        result.current.showNotification({
          title: 'Test Title',
          requireInteraction: true,
        });
      });

      act(() => {
        vi.advanceTimersByTime(10000);
      });

      expect(notificationCloseMock).not.toHaveBeenCalled();
    });

    it('suppresses notification when window has focus and option is enabled', () => {
      setPermission('granted');
      vi.spyOn(document, 'hasFocus').mockReturnValue(true);

      const { result } = renderHook(() =>
        useDesktopNotifications({ suppressWhenFocused: true })
      );

      act(() => {
        result.current.showNotification({
          title: 'Test Title',
        });
      });

      expect(notificationSpyMock).not.toHaveBeenCalled();
    });
  });

  describe('showSecurityAlert', () => {
    beforeEach(() => {
      setPermission('granted');
    });

    it('shows security alert with correct formatting', () => {
      const { result } = renderHook(() => useDesktopNotifications());

      act(() => {
        result.current.showSecurityAlert({
          camera: 'Front Door',
          riskLevel: 'high',
          summary: 'Motion detected',
        });
      });

      expect(notificationSpyMock).toHaveBeenCalledWith(
        '[HIGH] Front Door',
        expect.objectContaining({
          body: 'Motion detected',
          requireInteraction: true,
        })
      );
    });

    it('uses correct prefix for each risk level', () => {
      const riskLevels = [
        { level: 'low' as const, prefix: '[LOW]' },
        { level: 'medium' as const, prefix: '[MEDIUM]' },
        { level: 'high' as const, prefix: '[HIGH]' },
        { level: 'critical' as const, prefix: '[CRITICAL]' },
      ];

      riskLevels.forEach(({ level, prefix }) => {
        notificationSpyMock.mockClear();

        const { result } = renderHook(() => useDesktopNotifications());

        act(() => {
          result.current.showSecurityAlert({
            camera: 'Test Camera',
            riskLevel: level,
            summary: 'Test summary',
          });
        });

        expect(notificationSpyMock).toHaveBeenCalledWith(
          `${prefix} Test Camera`,
          expect.anything()
        );
      });
    });

    it('sets requireInteraction for high and critical risk levels', () => {
      ['high', 'critical'].forEach((level) => {
        notificationSpyMock.mockClear();

        const { result } = renderHook(() => useDesktopNotifications());

        act(() => {
          result.current.showSecurityAlert({
            camera: 'Test Camera',
            riskLevel: level as 'high' | 'critical',
            summary: 'Test summary',
          });
        });

        expect(notificationSpyMock).toHaveBeenCalledWith(
          expect.any(String),
          expect.objectContaining({
            requireInteraction: true,
          })
        );
      });
    });

    it('sets silent for low risk level', () => {
      const { result } = renderHook(() => useDesktopNotifications());

      act(() => {
        result.current.showSecurityAlert({
          camera: 'Test Camera',
          riskLevel: 'low',
          summary: 'Test summary',
        });
      });

      expect(notificationSpyMock).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          silent: true,
        })
      );
    });

    it('uses eventId for notification tag', () => {
      const { result } = renderHook(() => useDesktopNotifications());

      act(() => {
        result.current.showSecurityAlert({
          camera: 'Test Camera',
          riskLevel: 'medium',
          summary: 'Test summary',
          eventId: 'event-123',
        });
      });

      expect(notificationSpyMock).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          tag: 'event-123',
        })
      );
    });
  });

  describe('closeAll', () => {
    it('closes all active notifications', () => {
      setPermission('granted');

      const { result } = renderHook(() => useDesktopNotifications());

      // Show multiple notifications
      act(() => {
        result.current.showNotification({ title: 'Test 1' });
        result.current.showNotification({ title: 'Test 2' });
      });

      act(() => {
        result.current.closeAll();
      });

      expect(notificationCloseMock).toHaveBeenCalledTimes(2);
    });
  });

  describe('setEnabled', () => {
    it('enables and disables notifications', () => {
      const { result } = renderHook(() => useDesktopNotifications());

      expect(result.current.isEnabled).toBe(true);

      act(() => {
        result.current.setEnabled(false);
      });

      expect(result.current.isEnabled).toBe(false);
    });

    it('closes active notifications when disabled', () => {
      setPermission('granted');

      const { result } = renderHook(() => useDesktopNotifications());

      act(() => {
        result.current.showNotification({ title: 'Test' });
      });

      act(() => {
        result.current.setEnabled(false);
      });

      expect(notificationCloseMock).toHaveBeenCalled();
    });
  });

  describe('window focus tracking', () => {
    it('tracks window focus state', () => {
      const { result } = renderHook(() => useDesktopNotifications());

      // Initial state based on document.hasFocus()
      expect(result.current.isEnabled).toBe(true);

      // Simulate blur event
      act(() => {
        window.dispatchEvent(new Event('blur'));
      });

      // Focus state should update (internal, not exposed)
      // This affects suppressWhenFocused behavior
    });
  });

  describe('cleanup', () => {
    it('clears timers on unmount', () => {
      setPermission('granted');

      const { result, unmount } = renderHook(() => useDesktopNotifications());

      act(() => {
        result.current.showNotification({
          title: 'Test',
          autoCloseMs: 5000,
        });
      });

      unmount();

      // Advancing timers should not cause issues
      act(() => {
        vi.advanceTimersByTime(5000);
      });
    });

    it('closes notifications on unmount', () => {
      setPermission('granted');

      const { result, unmount } = renderHook(() => useDesktopNotifications());

      act(() => {
        result.current.showNotification({ title: 'Test' });
      });

      unmount();

      expect(notificationCloseMock).toHaveBeenCalled();
    });
  });
});
