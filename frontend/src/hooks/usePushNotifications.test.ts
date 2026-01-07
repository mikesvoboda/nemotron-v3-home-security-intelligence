/**
 * Tests for usePushNotifications hook
 * TDD: Tests for browser push notification functionality
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';

// Direct import to avoid barrel file memory issues
import { usePushNotifications } from './usePushNotifications';

// Mock Notification API
const mockNotification = vi.fn();
let mockPermission: NotificationPermission = 'default';

describe('usePushNotifications', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPermission = 'default';

    // Mock Notification constructor
    vi.stubGlobal('Notification', class MockNotification {
      static permission = mockPermission;
      static requestPermission = vi.fn().mockImplementation(() => {
        mockPermission = 'granted';
        MockNotification.permission = 'granted';
        return Promise.resolve('granted');
      });
      constructor(title: string, options?: NotificationOptions) {
        mockNotification(title, options);
      }
      onclick: (() => void) | null = null;
      close = vi.fn();
    });

    // Mock service worker
    vi.stubGlobal('navigator', {
      ...navigator,
      serviceWorker: {
        ready: Promise.resolve({
          pushManager: {
            getSubscription: vi.fn().mockResolvedValue(null),
            subscribe: vi.fn().mockResolvedValue({
              toJSON: () => ({
                endpoint: 'https://push.example.com/endpoint',
                keys: { p256dh: 'key1', auth: 'key2' },
              }),
            }),
          },
        }),
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('initializes with default permission state', () => {
    const { result } = renderHook(() => usePushNotifications());

    expect(result.current.permission).toBe('default');
    expect(result.current.isSupported).toBe(true);
    expect(result.current.isSubscribed).toBe(false);
  });

  it('detects when notifications are not supported', () => {
    vi.stubGlobal('Notification', undefined);

    const { result } = renderHook(() => usePushNotifications());

    expect(result.current.isSupported).toBe(false);
  });

  it('requests notification permission', async () => {
    const { result } = renderHook(() => usePushNotifications());

    expect(result.current.permission).toBe('default');

    await act(async () => {
      await result.current.requestPermission();
    });

    await waitFor(() => {
      expect(result.current.permission).toBe('granted');
    });
  });

  it('handles denied permission', async () => {
    // Mock denied permission
    vi.stubGlobal('Notification', class MockNotification {
      static permission = 'default' as NotificationPermission;
      static requestPermission = vi.fn().mockImplementation(() => {
        MockNotification.permission = 'denied';
        return Promise.resolve('denied');
      });
      constructor() { /* empty */ }
    });

    const { result } = renderHook(() => usePushNotifications());

    await act(async () => {
      await result.current.requestPermission();
    });

    await waitFor(() => {
      expect(result.current.permission).toBe('denied');
    });
  });

  it('shows a notification when permission is granted', async () => {
    // Set permission to granted
    vi.stubGlobal('Notification', class MockNotification {
      static permission = 'granted' as NotificationPermission;
      static requestPermission = vi.fn().mockResolvedValue('granted');
      constructor(title: string, options?: NotificationOptions) {
        mockNotification(title, options);
      }
      onclick: (() => void) | null = null;
      close = vi.fn();
    });

    const { result } = renderHook(() => usePushNotifications());

    await act(async () => {
      await result.current.showNotification('Test Title', {
        body: 'Test body',
        icon: '/icons/icon-192.png',
      });
    });

    expect(mockNotification).toHaveBeenCalledWith('Test Title', {
      body: 'Test body',
      icon: '/icons/icon-192.png',
    });
  });

  it('does not show notification when permission is denied', async () => {
    // Set permission to denied
    vi.stubGlobal('Notification', class MockNotification {
      static permission = 'denied' as NotificationPermission;
      static requestPermission = vi.fn().mockResolvedValue('denied');
      constructor(title: string, options?: NotificationOptions) {
        mockNotification(title, options);
      }
      onclick: (() => void) | null = null;
      close = vi.fn();
    });

    const { result } = renderHook(() => usePushNotifications());

    await act(async () => {
      await result.current.showNotification('Test Title', {
        body: 'Test body',
      });
    });

    // Should not have called the notification constructor
    expect(mockNotification).not.toHaveBeenCalled();
  });

  it('provides hasPermission boolean helper', () => {
    const { result } = renderHook(() => usePushNotifications());

    expect(result.current.hasPermission).toBe(false);

    // Mock granted permission
    vi.stubGlobal('Notification', class MockNotification {
      static permission = 'granted' as NotificationPermission;
      static requestPermission = vi.fn().mockResolvedValue('granted');
      constructor() { /* empty */ }
    });

    // Re-render with new permission
    const { result: newResult } = renderHook(() => usePushNotifications());

    expect(newResult.current.hasPermission).toBe(true);
  });

  it('detects if user has interacted with permission prompt', () => {
    const { result } = renderHook(() => usePushNotifications());

    // Default means user hasn't interacted
    expect(result.current.hasInteracted).toBe(false);

    // Mock granted permission (user has interacted)
    vi.stubGlobal('Notification', class MockNotification {
      static permission = 'granted' as NotificationPermission;
      static requestPermission = vi.fn().mockResolvedValue('granted');
      constructor() { /* empty */ }
    });

    const { result: grantedResult } = renderHook(() => usePushNotifications());
    expect(grantedResult.current.hasInteracted).toBe(true);

    // Mock denied permission (user has interacted)
    vi.stubGlobal('Notification', class MockNotification {
      static permission = 'denied' as NotificationPermission;
      static requestPermission = vi.fn().mockResolvedValue('denied');
      constructor() { /* empty */ }
    });

    const { result: deniedResult } = renderHook(() => usePushNotifications());
    expect(deniedResult.current.hasInteracted).toBe(true);
  });

  it('provides showSecurityAlert convenience method', async () => {
    // Set permission to granted
    vi.stubGlobal('Notification', class MockNotification {
      static permission = 'granted' as NotificationPermission;
      static requestPermission = vi.fn().mockResolvedValue('granted');
      constructor(title: string, options?: NotificationOptions) {
        mockNotification(title, options);
      }
      onclick: (() => void) | null = null;
      close = vi.fn();
    });

    const { result } = renderHook(() => usePushNotifications());

    await act(async () => {
      await result.current.showSecurityAlert({
        camera: 'Front Door',
        riskLevel: 'high',
        summary: 'Person detected',
      });
    });

    expect(mockNotification).toHaveBeenCalledWith(
      expect.stringContaining('Front Door'),
      expect.objectContaining({
        body: expect.stringContaining('Person detected'),
        tag: expect.any(String),
        requireInteraction: true,
      })
    );
  });
});
