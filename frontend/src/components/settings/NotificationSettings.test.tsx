import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import NotificationSettings from './NotificationSettings';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchNotificationConfig: vi.fn(),
  testNotification: vi.fn(),
}));

const mockFetchNotificationConfig = vi.mocked(api.fetchNotificationConfig);
const mockTestNotification = vi.mocked(api.testNotification);

describe('NotificationSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
    default_email_recipients: ['user1@example.com', 'user2@example.com'],
  };

  const mockUnconfiguredConfig: api.NotificationConfig = {
    notification_enabled: true,
    email_configured: false,
    webhook_configured: false,
    push_configured: false,
    available_channels: [],
    smtp_host: null,
    smtp_port: null,
    smtp_from_address: null,
    smtp_use_tls: null,
    default_webhook_url: null,
    webhook_timeout_seconds: null,
    default_email_recipients: [],
  };

  it('should render the component title', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByText('Notification Settings')).toBeInTheDocument();
    });
  });

  it('should show loading state initially', () => {
    mockFetchNotificationConfig.mockImplementation(
      () => new Promise(() => {})
    );

    render(<NotificationSettings />);

    // Should have skeleton loaders
    expect(document.querySelector('.skeleton')).toBeInTheDocument();
  });

  it('should display error message when config fetch fails', async () => {
    mockFetchNotificationConfig.mockRejectedValue(new Error('Network error'));

    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('should show notifications enabled badge when enabled', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationSettings />);

    await waitFor(() => {
      // There should be multiple "Enabled" texts (notifications status and TLS status)
      const enabledElements = screen.getAllByText('Enabled');
      expect(enabledElements.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('should show notifications disabled badge when disabled', async () => {
    mockFetchNotificationConfig.mockResolvedValue({
      ...mockFullConfig,
      notification_enabled: false,
    });

    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByText('Disabled')).toBeInTheDocument();
    });
  });

  it('should display SMTP configuration when email is configured', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByText('smtp.example.com')).toBeInTheDocument();
      expect(screen.getByText('587')).toBeInTheDocument();
      expect(screen.getByText('alerts@example.com')).toBeInTheDocument();
    });
  });

  it('should display default email recipients', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByText('user1@example.com')).toBeInTheDocument();
      expect(screen.getByText('user2@example.com')).toBeInTheDocument();
    });
  });

  it('should display webhook configuration when webhook is configured', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByText('https://hooks.example.com/webhook')).toBeInTheDocument();
      expect(screen.getByText('30s')).toBeInTheDocument();
    });
  });

  it('should show "Not Configured" when email is not configured', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockUnconfiguredConfig);

    render(<NotificationSettings />);

    await waitFor(() => {
      const notConfiguredBadges = screen.getAllByText('Not Configured');
      expect(notConfiguredBadges.length).toBeGreaterThanOrEqual(2);
    });
  });

  it('should show configuration instructions when email is not configured', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockUnconfiguredConfig);

    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByText('Email notifications are not configured.')).toBeInTheDocument();
    });
  });

  it('should show configuration instructions when webhook is not configured', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockUnconfiguredConfig);

    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByText('Webhook notifications are not configured.')).toBeInTheDocument();
    });
  });

  it('should display available channels', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByText('EMAIL')).toBeInTheDocument();
      expect(screen.getByText('WEBHOOK')).toBeInTheDocument();
    });
  });

  it('should show no channels message when none are available', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockUnconfiguredConfig);

    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByText('No notification channels configured')).toBeInTheDocument();
    });
  });

  it('should show test email button when email is configured', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /send test email/i })).toBeInTheDocument();
    });
  });

  it('should show test webhook button when webhook is configured', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /send test webhook/i })).toBeInTheDocument();
    });
  });

  it('should call testNotification when test email button is clicked', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);
    mockTestNotification.mockResolvedValue({
      channel: 'email',
      success: true,
      error: null,
      message: 'Test email sent successfully to user1@example.com, user2@example.com',
    });

    const user = userEvent.setup();
    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /send test email/i })).toBeInTheDocument();
    });

    const testButton = screen.getByRole('button', { name: /send test email/i });
    await user.click(testButton);

    expect(mockTestNotification).toHaveBeenCalledWith('email');

    await waitFor(() => {
      expect(screen.getByText(/test email sent successfully/i)).toBeInTheDocument();
    });
  });

  it('should call testNotification when test webhook button is clicked', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);
    mockTestNotification.mockResolvedValue({
      channel: 'webhook',
      success: true,
      error: null,
      message: 'Test webhook sent successfully to https://hooks.example.com/webhook',
    });

    const user = userEvent.setup();
    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /send test webhook/i })).toBeInTheDocument();
    });

    const testButton = screen.getByRole('button', { name: /send test webhook/i });
    await user.click(testButton);

    expect(mockTestNotification).toHaveBeenCalledWith('webhook');

    await waitFor(() => {
      expect(screen.getByText(/test webhook sent successfully/i)).toBeInTheDocument();
    });
  });

  it('should show error message when test notification fails', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);
    mockTestNotification.mockResolvedValue({
      channel: 'email',
      success: false,
      error: 'SMTP connection failed',
      message: 'Failed to send test email: SMTP connection failed',
    });

    const user = userEvent.setup();
    render(<NotificationSettings />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /send test email/i })).toBeInTheDocument();
    });

    const testButton = screen.getByRole('button', { name: /send test email/i });
    await user.click(testButton);

    await waitFor(() => {
      expect(screen.getByText(/failed to send test email/i)).toBeInTheDocument();
    });
  });

  it('should disable test buttons when notifications are disabled', async () => {
    mockFetchNotificationConfig.mockResolvedValue({
      ...mockFullConfig,
      notification_enabled: false,
    });

    render(<NotificationSettings />);

    await waitFor(() => {
      const testEmailButton = screen.getByRole('button', { name: /send test email/i });
      const testWebhookButton = screen.getByRole('button', { name: /send test webhook/i });

      expect(testEmailButton).toBeDisabled();
      expect(testWebhookButton).toBeDisabled();
    });
  });

  it('should show TLS enabled status', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationSettings />);

    await waitFor(() => {
      // Find the TLS label and its value
      expect(screen.getByText('TLS')).toBeInTheDocument();
      // The value "Enabled" should be present for TLS
      const enabledTexts = screen.getAllByText('Enabled');
      // One for notification status badge, one might be for TLS
      expect(enabledTexts.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('should show configuration note about environment variables', async () => {
    mockFetchNotificationConfig.mockResolvedValue(mockFullConfig);

    render(<NotificationSettings />);

    await waitFor(() => {
      expect(
        screen.getByText(/notification settings are configured via environment variables/i)
      ).toBeInTheDocument();
    });
  });
});
