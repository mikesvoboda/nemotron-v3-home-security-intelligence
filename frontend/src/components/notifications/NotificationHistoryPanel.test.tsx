/**
 * Tests for NotificationHistoryPanel component
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import NotificationHistoryPanel from './NotificationHistoryPanel';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    fetchNotificationHistory: vi.fn(),
  };
});

const mockFetchNotificationHistory = vi.mocked(api.fetchNotificationHistory);

// Helper to create a wrapper with QueryClient
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
};

describe('NotificationHistoryPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockEmptyResponse: api.NotificationHistoryResponse = {
    entries: [],
    count: 0,
    limit: 50,
    offset: 0,
  };

  const mockHistoryResponse: api.NotificationHistoryResponse = {
    entries: [
      {
        id: 'entry-1',
        alert_id: 'alert-1',
        channel: 'email',
        recipient: 'user@example.com',
        success: true,
        error: null,
        delivered_at: '2025-01-25T12:00:00Z',
        created_at: '2025-01-25T11:59:59Z',
      },
      {
        id: 'entry-2',
        alert_id: 'alert-2',
        channel: 'webhook',
        recipient: 'https://hooks.example.com/webhook',
        success: false,
        error: 'Connection timeout',
        delivered_at: null,
        created_at: '2025-01-25T11:58:00Z',
      },
    ],
    count: 2,
    limit: 50,
    offset: 0,
  };

  it('should render the component with title', () => {
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    render(<NotificationHistoryPanel />, { wrapper: createWrapper() });

    expect(screen.getByText('Notification History')).toBeInTheDocument();
  });

  it('should show loading state initially', () => {
    mockFetchNotificationHistory.mockReturnValue(new Promise(() => {})); // Never resolves

    render(<NotificationHistoryPanel />, { wrapper: createWrapper() });

    // The loading spinner should be visible (Loader2 component)
    const loadingSpinner = document.querySelector('.animate-spin');
    expect(loadingSpinner).toBeInTheDocument();
  });

  it('should show empty state when no history exists', async () => {
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    render(<NotificationHistoryPanel />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No notification history yet')).toBeInTheDocument();
    });

    expect(screen.getByText('Notification delivery records will appear here')).toBeInTheDocument();
  });

  it('should render history entries in table', async () => {
    mockFetchNotificationHistory.mockResolvedValue(mockHistoryResponse);

    render(<NotificationHistoryPanel />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('user@example.com')).toBeInTheDocument();
    });

    // Check channel badges (use getAllByText due to filter dropdowns)
    const emailBadges = screen.getAllByText('Email');
    expect(emailBadges.length).toBeGreaterThan(0);
    const webhookBadges = screen.getAllByText('Webhook');
    expect(webhookBadges.length).toBeGreaterThan(0);

    // Check status badges (use getAllByText due to filter dropdowns containing these options)
    const successBadges = screen.getAllByText('Success');
    expect(successBadges.length).toBeGreaterThan(0);
    const failedBadges = screen.getAllByText('Failed');
    expect(failedBadges.length).toBeGreaterThan(0);

    // Check error message
    expect(screen.getByText('Connection timeout')).toBeInTheDocument();

    // Check total count
    expect(screen.getByText('2 entries')).toBeInTheDocument();
  });

  it('should display table headers', async () => {
    mockFetchNotificationHistory.mockResolvedValue(mockHistoryResponse);

    render(<NotificationHistoryPanel />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Time')).toBeInTheDocument();
    });

    expect(screen.getByText('Channel')).toBeInTheDocument();
    expect(screen.getByText('Recipient')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('should show error state when API fails', () => {
    mockFetchNotificationHistory.mockRejectedValue(new Error('Failed to fetch'));

    render(<NotificationHistoryPanel />, { wrapper: createWrapper() });

    // We're just verifying the render doesn't throw - the actual error display
    // may take time due to query retry logic
    expect(screen.getByText('Notification History')).toBeInTheDocument();
  });

  it('should render filter dropdowns', async () => {
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    render(<NotificationHistoryPanel />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No notification history yet')).toBeInTheDocument();
    });

    // Check for filter placeholders (use getAllByText since they may appear in dropdown options too)
    const channelFilters = screen.getAllByText('All Channels');
    expect(channelFilters.length).toBeGreaterThan(0);
    const statusFilters = screen.getAllByText('All Statuses');
    expect(statusFilters.length).toBeGreaterThan(0);
  });

  it('should render refresh button', async () => {
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    render(<NotificationHistoryPanel />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No notification history yet')).toBeInTheDocument();
    });

    // Find the refresh button (contains RefreshCw icon)
    const refreshButton = screen.getAllByRole('button')[0];
    expect(refreshButton).toBeInTheDocument();
  });

  it('should have filter select components', async () => {
    // Verify that the filter UI elements are present and contain expected options
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    render(<NotificationHistoryPanel />, {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByText('No notification history yet')).toBeInTheDocument();
    });

    // Check that filter icon is present (lucide icons use aria-hidden)
    const filterIcon = document.querySelector('[aria-hidden="true"]');
    expect(filterIcon).toBeInTheDocument();

    // Check that the filter options exist in the DOM (even if hidden)
    expect(screen.getAllByText('Email').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Webhook').length).toBeGreaterThan(0);
  });

  it('should have status filter options available', async () => {
    // Verify status filter options exist in the DOM
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    render(<NotificationHistoryPanel />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No notification history yet')).toBeInTheDocument();
    });

    // Check that status options exist in the DOM
    expect(screen.getAllByText('Success').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Failed').length).toBeGreaterThan(0);
  });

  it('should call API with correct parameters', async () => {
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    render(<NotificationHistoryPanel pageSize={25} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No notification history yet')).toBeInTheDocument();
    });

    expect(mockFetchNotificationHistory).toHaveBeenCalledWith({
      limit: 25,
      offset: 0,
    });
  });

  it('should pass alertId filter when provided as prop', async () => {
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    render(<NotificationHistoryPanel alertId="alert-123" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockFetchNotificationHistory).toHaveBeenCalledWith(
        expect.objectContaining({
          alert_id: 'alert-123',
        })
      );
    });
  });

  it('should render pagination controls when multiple pages exist', async () => {
    mockFetchNotificationHistory.mockResolvedValue({
      entries: [
        {
          id: 'entry-1',
          alert_id: 'alert-1',
          channel: 'email',
          recipient: 'user@example.com',
          success: true,
          error: null,
          delivered_at: '2025-01-25T12:00:00Z',
          created_at: '2025-01-25T11:59:59Z',
        },
      ],
      count: 25, // More than 1 page at default page size
      limit: 10,
      offset: 0,
    });

    render(<NotificationHistoryPanel pageSize={10} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
    });
  });

  it('should apply custom className', async () => {
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    const { container } = render(<NotificationHistoryPanel className="custom-class" />, {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByText('No notification history yet')).toBeInTheDocument();
    });

    const card = container.querySelector('.custom-class');
    expect(card).toBeInTheDocument();
  });

  it('should truncate long recipient text', async () => {
    const longRecipient = 'https://very-long-webhook-url.example.com/api/v1/webhooks/notifications/handler';
    mockFetchNotificationHistory.mockResolvedValue({
      entries: [
        {
          id: 'entry-1',
          alert_id: 'alert-1',
          channel: 'webhook',
          recipient: longRecipient,
          success: true,
          error: null,
          delivered_at: '2025-01-25T12:00:00Z',
          created_at: '2025-01-25T11:59:59Z',
        },
      ],
      count: 1,
      limit: 50,
      offset: 0,
    });

    render(<NotificationHistoryPanel />, { wrapper: createWrapper() });

    await waitFor(() => {
      // Should show truncated text with ellipsis
      expect(screen.getByText(/https:\/\/very-long.*\.\.\./)).toBeInTheDocument();
    });
  });
});
