/**
 * Tests for OfflineStatusIndicator component
 * @see NEM-3675 - PWA Offline Caching
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import OfflineStatusIndicator from './OfflineStatusIndicator';
import { useCachedEvents } from '../../hooks/useCachedEvents';
import { useNetworkStatus } from '../../hooks/useNetworkStatus';

vi.mock('../../hooks/useNetworkStatus', () => ({
  useNetworkStatus: vi.fn(() => ({
    isOnline: true,
    isOffline: false,
    lastOnlineAt: new Date(),
    wasOffline: false,
    clearWasOffline: vi.fn(),
  })),
}));

vi.mock('../../hooks/useCachedEvents', () => ({
  useCachedEvents: vi.fn(() => ({
    cachedCount: 0,
    cachedEvents: [],
    isInitialized: true,
    error: null,
    cacheEvent: vi.fn(),
    loadCachedEvents: vi.fn(),
    removeCachedEvent: vi.fn(),
    clearCache: vi.fn(),
  })),
}));

describe('OfflineStatusIndicator', () => {
  const mockUseNetworkStatus = vi.mocked(useNetworkStatus);
  const mockUseCachedEvents = vi.mocked(useCachedEvents);

  beforeEach(() => {
    vi.clearAllMocks();

    mockUseNetworkStatus.mockReturnValue({
      isOnline: true,
      isOffline: false,
      lastOnlineAt: new Date(),
      wasOffline: false,
      clearWasOffline: vi.fn(),
    });

    mockUseCachedEvents.mockReturnValue({
      cachedCount: 0,
      cachedEvents: [],
      isInitialized: true,
      error: null,
      cacheEvent: vi.fn(),
      loadCachedEvents: vi.fn(),
      removeCachedEvent: vi.fn(),
      clearCache: vi.fn(),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('visibility', () => {
    it('does not render when online', () => {
      render(<OfflineStatusIndicator />);
      expect(screen.queryByTestId('offline-indicator')).not.toBeInTheDocument();
    });

    it('renders when offline', () => {
      mockUseNetworkStatus.mockReturnValue({
        isOnline: false,
        isOffline: true,
        lastOnlineAt: new Date(),
        wasOffline: true,
        clearWasOffline: vi.fn(),
      });

      render(<OfflineStatusIndicator />);
      expect(screen.getByTestId('offline-indicator')).toBeInTheDocument();
    });
  });

  describe('cached events', () => {
    it('displays cached events count', () => {
      mockUseNetworkStatus.mockReturnValue({
        isOnline: false,
        isOffline: true,
        lastOnlineAt: new Date(),
        wasOffline: true,
        clearWasOffline: vi.fn(),
      });

      mockUseCachedEvents.mockReturnValue({
        cachedCount: 15,
        cachedEvents: [],
        isInitialized: true,
        error: null,
        cacheEvent: vi.fn(),
        loadCachedEvents: vi.fn(),
        removeCachedEvent: vi.fn(),
        clearCache: vi.fn(),
      });

      render(<OfflineStatusIndicator />);
      expect(screen.getByText(/15 events cached/)).toBeInTheDocument();
    });
  });

  describe('retry functionality', () => {
    beforeEach(() => {
      mockUseNetworkStatus.mockReturnValue({
        isOnline: false,
        isOffline: true,
        lastOnlineAt: new Date(),
        wasOffline: true,
        clearWasOffline: vi.fn(),
      });
    });

    it('calls onRetry when provided', () => {
      const onRetry = vi.fn();
      render(<OfflineStatusIndicator onRetry={onRetry} />);
      const retryButton = screen.getByRole('button', { name: /retry/i });
      fireEvent.click(retryButton);
      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('shows retry button when reloadOnRetry is true', () => {
      render(<OfflineStatusIndicator reloadOnRetry />);
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });
  });
});
