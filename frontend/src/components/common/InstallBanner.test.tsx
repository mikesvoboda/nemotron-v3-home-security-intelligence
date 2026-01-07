/**
 * Tests for InstallBanner component
 * TDD: Tests for PWA install prompt banner
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import InstallBanner from './InstallBanner';

// Mock BeforeInstallPromptEvent
interface MockBeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

describe('InstallBanner', () => {
  // Mock localStorage
  const mockLocalStorage = new Map<string, string>();

  beforeEach(() => {
    vi.clearAllMocks();
    mockLocalStorage.clear();

    // Mock localStorage
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => mockLocalStorage.get(key) ?? null,
      setItem: (key: string, value: string) => mockLocalStorage.set(key, value),
      removeItem: (key: string) => mockLocalStorage.delete(key),
      clear: () => mockLocalStorage.clear(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('does not render when deferredPrompt is not provided', () => {
    render(<InstallBanner deferredPrompt={null} onDismiss={vi.fn()} />);

    expect(screen.queryByTestId('install-banner')).not.toBeInTheDocument();
  });

  it('renders when deferredPrompt is provided', () => {
    const mockPrompt: MockBeforeInstallPromptEvent = {
      ...new Event('beforeinstallprompt'),
      prompt: vi.fn().mockResolvedValue(undefined),
      userChoice: Promise.resolve({ outcome: 'dismissed' }),
    };

    render(<InstallBanner deferredPrompt={mockPrompt} onDismiss={vi.fn()} />);

    expect(screen.getByTestId('install-banner')).toBeInTheDocument();
  });

  it('displays install message', () => {
    const mockPrompt: MockBeforeInstallPromptEvent = {
      ...new Event('beforeinstallprompt'),
      prompt: vi.fn().mockResolvedValue(undefined),
      userChoice: Promise.resolve({ outcome: 'dismissed' }),
    };

    render(<InstallBanner deferredPrompt={mockPrompt} onDismiss={vi.fn()} />);

    expect(screen.getByText('Install Nemotron Security')).toBeInTheDocument();
  });

  it('calls prompt when install button is clicked', async () => {
    const mockPrompt: MockBeforeInstallPromptEvent = {
      ...new Event('beforeinstallprompt'),
      prompt: vi.fn().mockResolvedValue(undefined),
      userChoice: Promise.resolve({ outcome: 'accepted' }),
    };

    const onDismiss = vi.fn();
    render(<InstallBanner deferredPrompt={mockPrompt} onDismiss={onDismiss} />);

    // Find the Install button (which has exact text "Install")
    const installButton = screen.getByRole('button', { name: /^Install$/ });
    fireEvent.click(installButton);

    await waitFor(() => {
      expect(mockPrompt.prompt).toHaveBeenCalled();
    });
  });

  it('calls onDismiss when user accepts install', async () => {
    const mockPrompt: MockBeforeInstallPromptEvent = {
      ...new Event('beforeinstallprompt'),
      prompt: vi.fn().mockResolvedValue(undefined),
      userChoice: Promise.resolve({ outcome: 'accepted' }),
    };

    const onDismiss = vi.fn();
    render(<InstallBanner deferredPrompt={mockPrompt} onDismiss={onDismiss} />);

    // Find the Install button (which has exact text "Install")
    const installButton = screen.getByRole('button', { name: /^Install$/ });
    fireEvent.click(installButton);

    await waitFor(() => {
      expect(onDismiss).toHaveBeenCalled();
    });
  });

  it('calls onDismiss when dismiss button is clicked', () => {
    const mockPrompt: MockBeforeInstallPromptEvent = {
      ...new Event('beforeinstallprompt'),
      prompt: vi.fn().mockResolvedValue(undefined),
      userChoice: Promise.resolve({ outcome: 'dismissed' }),
    };

    const onDismiss = vi.fn();
    render(<InstallBanner deferredPrompt={mockPrompt} onDismiss={onDismiss} />);

    const dismissButton = screen.getByRole('button', { name: /dismiss|close|later/i });
    fireEvent.click(dismissButton);

    expect(onDismiss).toHaveBeenCalled();
  });

  it('saves dismissal to localStorage when dismissed', () => {
    const mockPrompt: MockBeforeInstallPromptEvent = {
      ...new Event('beforeinstallprompt'),
      prompt: vi.fn().mockResolvedValue(undefined),
      userChoice: Promise.resolve({ outcome: 'dismissed' }),
    };

    render(<InstallBanner deferredPrompt={mockPrompt} onDismiss={vi.fn()} />);

    const dismissButton = screen.getByRole('button', { name: /dismiss|close|later/i });
    fireEvent.click(dismissButton);

    expect(mockLocalStorage.get('pwa-install-dismissed')).toBeDefined();
  });

  it('does not render if previously dismissed within timeout period', () => {
    // Set dismissal timestamp to recent past
    mockLocalStorage.set('pwa-install-dismissed', String(Date.now() - 1000));

    const mockPrompt: MockBeforeInstallPromptEvent = {
      ...new Event('beforeinstallprompt'),
      prompt: vi.fn().mockResolvedValue(undefined),
      userChoice: Promise.resolve({ outcome: 'dismissed' }),
    };

    render(<InstallBanner deferredPrompt={mockPrompt} onDismiss={vi.fn()} />);

    expect(screen.queryByTestId('install-banner')).not.toBeInTheDocument();
  });

  it('renders if dismissal timeout has expired', () => {
    // Set dismissal timestamp to 8 days ago (default timeout is 7 days)
    const eightDaysAgo = Date.now() - 8 * 24 * 60 * 60 * 1000;
    mockLocalStorage.set('pwa-install-dismissed', String(eightDaysAgo));

    const mockPrompt: MockBeforeInstallPromptEvent = {
      ...new Event('beforeinstallprompt'),
      prompt: vi.fn().mockResolvedValue(undefined),
      userChoice: Promise.resolve({ outcome: 'dismissed' }),
    };

    render(<InstallBanner deferredPrompt={mockPrompt} onDismiss={vi.fn()} />);

    expect(screen.getByTestId('install-banner')).toBeInTheDocument();
  });

  it('has correct accessibility attributes', () => {
    const mockPrompt: MockBeforeInstallPromptEvent = {
      ...new Event('beforeinstallprompt'),
      prompt: vi.fn().mockResolvedValue(undefined),
      userChoice: Promise.resolve({ outcome: 'dismissed' }),
    };

    render(<InstallBanner deferredPrompt={mockPrompt} onDismiss={vi.fn()} />);

    const banner = screen.getByTestId('install-banner');
    expect(banner).toHaveAttribute('role', 'banner');
  });

  it('renders with custom dismissal timeout', () => {
    // Set dismissal timestamp to 2 days ago
    const twoDaysAgo = Date.now() - 2 * 24 * 60 * 60 * 1000;
    mockLocalStorage.set('pwa-install-dismissed', String(twoDaysAgo));

    const mockPrompt: MockBeforeInstallPromptEvent = {
      ...new Event('beforeinstallprompt'),
      prompt: vi.fn().mockResolvedValue(undefined),
      userChoice: Promise.resolve({ outcome: 'dismissed' }),
    };

    // With 1 day timeout, banner should show (2 days > 1 day)
    render(
      <InstallBanner
        deferredPrompt={mockPrompt}
        onDismiss={vi.fn()}
        dismissalTimeoutDays={1}
      />
    );

    expect(screen.getByTestId('install-banner')).toBeInTheDocument();
  });

  it('applies dark theme styling', () => {
    const mockPrompt: MockBeforeInstallPromptEvent = {
      ...new Event('beforeinstallprompt'),
      prompt: vi.fn().mockResolvedValue(undefined),
      userChoice: Promise.resolve({ outcome: 'dismissed' }),
    };

    render(<InstallBanner deferredPrompt={mockPrompt} onDismiss={vi.fn()} />);

    const banner = screen.getByTestId('install-banner');
    // Should have dark background
    expect(banner.className).toMatch(/bg-/);
  });
});
