/**
 * Tests for NotificationPreferencesPage component
 *
 * @module pages/NotificationPreferencesPage.test
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import NotificationPreferencesPage, {
  NotificationPreferencesPageWithErrorBoundary,
} from './NotificationPreferencesPage';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchNotificationConfig: vi.fn(),
  testNotification: vi.fn(),
  fetchNotificationPreferences: vi.fn(),
  updateNotificationPreferences: vi.fn(),
  fetchCameraNotificationSettings: vi.fn(),
  updateCameraNotificationSetting: vi.fn(),
  fetchQuietHoursPeriods: vi.fn(),
  createQuietHoursPeriod: vi.fn(),
  deleteQuietHoursPeriod: vi.fn(),
  fetchCameras: vi.fn(),
}));

// Mock the useCamerasQuery hook
vi.mock('../hooks/useCamerasQuery', () => ({
  useCamerasQuery: vi.fn(() => ({
    cameras: [],
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  })),
}));

const mockFetchNotificationConfig = vi.mocked(api.fetchNotificationConfig);
const mockFetchNotificationPreferences = vi.mocked(api.fetchNotificationPreferences);
const mockFetchCameraNotificationSettings = vi.mocked(api.fetchCameraNotificationSettings);
const mockFetchQuietHoursPeriods = vi.mocked(api.fetchQuietHoursPeriods);

// Helper to create a wrapper with QueryClient and Router
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
};

describe('NotificationPreferencesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Setup default mocks for notification preferences
    mockFetchNotificationPreferences.mockResolvedValue({
      id: 1,
      enabled: true,
      sound: 'default',
      risk_filters: ['critical', 'high', 'medium'],
    });

    mockFetchCameraNotificationSettings.mockResolvedValue({
      items: [],
      pagination: { total: 0, limit: 50, offset: 0, has_more: false },
    });

    mockFetchQuietHoursPeriods.mockResolvedValue({
      items: [],
      pagination: { total: 0, limit: 50, offset: 0, has_more: false },
    });
  });

  const mockFullConfig: api.NotificationConfig = {
    notification_enabled: true,
    email_configured: true,
    webhook_configured: true,
    push_configured: false,
    available_channels: ['email', 'webhook'],
    smtp_host: 'smtp.example.com',
    smtp_port: 587,
    smtp_from_address: 'alerts@example.com',
    smtp_use_tls: true,
    default_webhook_url: 'https://hooks.example.com/webhook',
    webhook_timeout_seconds: 30,
    default_email_recipients: ['user1@example.com'],
  };

  it('should render the page with correct title', () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationPreferencesPage />, { wrapper: createWrapper() });

    expect(screen.getByText('Notification Preferences')).toBeInTheDocument();
    expect(screen.getByText('Manage how and when you receive security alerts')).toBeInTheDocument();
  });

  it('should have testid for the page', () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationPreferencesPage />, { wrapper: createWrapper() });

    expect(screen.getByTestId('notification-preferences-page')).toBeInTheDocument();
  });

  it('should show back to settings link', () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationPreferencesPage />, { wrapper: createWrapper() });

    const backLink = screen.getByText('Back to Settings');
    expect(backLink).toBeInTheDocument();
    expect(backLink.closest('a')).toHaveAttribute('href', '/settings');
  });

  it('should render NotificationSettings component', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationPreferencesPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      // The NotificationSettings component renders this text
      expect(screen.getByText('Notification Settings')).toBeInTheDocument();
    });
  });

  it('should render bell icon in header', () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationPreferencesPage />, { wrapper: createWrapper() });

    // The page header has a Bell icon container with NVIDIA green background
    const iconContainer = document.querySelector('.bg-\\[\\#76B900\\]\\/20');
    expect(iconContainer).toBeInTheDocument();
  });

  it('should show loading state while fetching preferences', async () => {
    mockFetchNotificationConfig.mockImplementation(() => new Promise(() => {}));

    render(<NotificationPreferencesPage />, { wrapper: createWrapper() });

    // Should show the page structure immediately
    expect(screen.getByText('Notification Preferences')).toBeInTheDocument();

    // NotificationSettings shows skeleton loaders when loading
    await waitFor(() => {
      expect(document.querySelector('.skeleton')).toBeInTheDocument();
    });
  });

  it('should show notification settings content after loading', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationPreferencesPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      // Global Preferences section from NotificationSettings
      expect(screen.getByText('Global Preferences')).toBeInTheDocument();
      // Quiet Hours section
      expect(screen.getByText('Quiet Hours')).toBeInTheDocument();
      // Camera Notifications section
      expect(screen.getByText('Camera Notifications')).toBeInTheDocument();
    });
  });
});

describe('NotificationPreferencesPageWithErrorBoundary', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Setup default mocks
    mockFetchNotificationPreferences.mockResolvedValue({
      id: 1,
      enabled: true,
      sound: 'default',
      risk_filters: ['critical', 'high', 'medium'],
    });

    mockFetchCameraNotificationSettings.mockResolvedValue({
      items: [],
      pagination: { total: 0, limit: 50, offset: 0, has_more: false },
    });

    mockFetchQuietHoursPeriods.mockResolvedValue({
      items: [],
      pagination: { total: 0, limit: 50, offset: 0, has_more: false },
    });
  });

  const mockFullConfig: api.NotificationConfig = {
    notification_enabled: true,
    email_configured: true,
    webhook_configured: true,
    push_configured: false,
    available_channels: ['email', 'webhook'],
    smtp_host: 'smtp.example.com',
    smtp_port: 587,
    smtp_from_address: 'alerts@example.com',
    smtp_use_tls: true,
    default_webhook_url: 'https://hooks.example.com/webhook',
    webhook_timeout_seconds: 30,
    default_email_recipients: ['user1@example.com'],
  };

  it('should render wrapped component successfully', () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationPreferencesPageWithErrorBoundary />, { wrapper: createWrapper() });

    expect(screen.getByText('Notification Preferences')).toBeInTheDocument();
  });

  it('should wrap page in FeatureErrorBoundary for resilience', () => {
    // Verify the error boundary wrapper is exported and can be used
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    // Just verify the component renders without throwing
    const { container } = render(<NotificationPreferencesPageWithErrorBoundary />, {
      wrapper: createWrapper(),
    });

    // The page should render within the error boundary
    expect(
      container.querySelector('[data-testid="notification-preferences-page"]')
    ).toBeInTheDocument();
  });
});
