import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import CleanupStatusCard from './CleanupStatusCard';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchCleanupStatus: vi.fn(),
}));

const mockFetchCleanupStatus = vi.mocked(api.fetchCleanupStatus);

describe('CleanupStatusCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    mockFetchCleanupStatus.mockImplementation(() => new Promise(() => {}));

    render(<CleanupStatusCard />);

    expect(screen.getByTestId('cleanup-status-card-loading')).toBeInTheDocument();
    expect(screen.getByText('Cleanup Service')).toBeInTheDocument();
  });

  it('renders running service status', async () => {
    mockFetchCleanupStatus.mockResolvedValue({
      running: true,
      retention_days: 30,
      cleanup_time: '03:00',
      delete_images: false,
      next_cleanup: '2025-12-31T03:00:00Z',
      timestamp: '2025-12-30T10:30:00Z',
    });

    render(<CleanupStatusCard />);

    await waitFor(() => {
      expect(screen.getByTestId('cleanup-status-card')).toBeInTheDocument();
    });

    expect(screen.getByTestId('running-status-badge')).toHaveTextContent('Running');
    expect(screen.getByTestId('retention-days')).toHaveTextContent('30 days');
    expect(screen.getByTestId('cleanup-time')).toHaveTextContent('3:00 AM');
    expect(screen.getByTestId('delete-images-badge')).toHaveTextContent('Disabled');
  });

  it('renders stopped service status with warning', async () => {
    mockFetchCleanupStatus.mockResolvedValue({
      running: false,
      retention_days: 14,
      cleanup_time: '02:00',
      delete_images: true,
      next_cleanup: null,
      timestamp: '2025-12-30T10:30:00Z',
    });

    render(<CleanupStatusCard />);

    await waitFor(() => {
      expect(screen.getByTestId('cleanup-status-card')).toBeInTheDocument();
    });

    expect(screen.getByTestId('running-status-badge')).toHaveTextContent('Stopped');
    expect(screen.getByTestId('retention-days')).toHaveTextContent('14 days');
    expect(screen.getByTestId('delete-images-badge')).toHaveTextContent('Enabled');
    expect(screen.getByText(/Cleanup service is not running/i)).toBeInTheDocument();
  });

  it('renders error state when fetch fails', async () => {
    mockFetchCleanupStatus.mockRejectedValue(new Error('Network error'));

    render(<CleanupStatusCard />);

    await waitFor(() => {
      expect(screen.getByTestId('cleanup-status-card-error')).toBeInTheDocument();
    });

    expect(screen.getByText('Failed to load cleanup status')).toBeInTheDocument();
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('handles retry button click after error', async () => {
    mockFetchCleanupStatus.mockRejectedValueOnce(new Error('Network error'));

    render(<CleanupStatusCard />);

    await waitFor(() => {
      expect(screen.getByTestId('cleanup-status-card-error')).toBeInTheDocument();
    });

    // Second call succeeds
    mockFetchCleanupStatus.mockResolvedValue({
      running: true,
      retention_days: 30,
      cleanup_time: '03:00',
      delete_images: false,
      next_cleanup: '2025-12-31T03:00:00Z',
      timestamp: '2025-12-30T10:30:00Z',
    });

    fireEvent.click(screen.getByText('Retry'));

    await waitFor(() => {
      expect(screen.getByTestId('cleanup-status-card')).toBeInTheDocument();
    });
  });

  it('calls onStatusChange when status updates', async () => {
    const onStatusChange = vi.fn();

    mockFetchCleanupStatus.mockResolvedValue({
      running: true,
      retention_days: 30,
      cleanup_time: '03:00',
      delete_images: false,
      next_cleanup: '2025-12-31T03:00:00Z',
      timestamp: '2025-12-30T10:30:00Z',
    });

    render(<CleanupStatusCard onStatusChange={onStatusChange} />);

    await waitFor(() => {
      expect(onStatusChange).toHaveBeenCalledWith(
        expect.objectContaining({
          running: true,
          retention_days: 30,
        })
      );
    });
  });

  it('displays delete images enabled status correctly', async () => {
    mockFetchCleanupStatus.mockResolvedValue({
      running: true,
      retention_days: 7,
      cleanup_time: '04:00',
      delete_images: true,
      next_cleanup: '2025-12-31T04:00:00Z',
      timestamp: '2025-12-30T10:30:00Z',
    });

    render(<CleanupStatusCard />);

    await waitFor(() => {
      expect(screen.getByTestId('cleanup-status-card')).toBeInTheDocument();
    });

    expect(screen.getByTestId('delete-images-badge')).toHaveTextContent('Enabled');
    expect(screen.getByTestId('retention-days')).toHaveTextContent('7 days');
  });

  it('formats PM cleanup times correctly', async () => {
    mockFetchCleanupStatus.mockResolvedValue({
      running: true,
      retention_days: 30,
      cleanup_time: '15:30',
      delete_images: false,
      next_cleanup: '2025-12-30T15:30:00Z',
      timestamp: '2025-12-30T10:30:00Z',
    });

    render(<CleanupStatusCard />);

    await waitFor(() => {
      expect(screen.getByTestId('cleanup-status-card')).toBeInTheDocument();
    });

    // Check for PM format - the exact text may vary by locale
    expect(screen.getByTestId('cleanup-time')).toHaveTextContent(/3:30.*PM/i);
  });

  it('displays last updated timestamp', async () => {
    mockFetchCleanupStatus.mockResolvedValue({
      running: true,
      retention_days: 30,
      cleanup_time: '03:00',
      delete_images: false,
      next_cleanup: '2025-12-31T03:00:00Z',
      timestamp: '2025-12-30T10:30:00Z',
    });

    render(<CleanupStatusCard />);

    await waitFor(() => {
      expect(screen.getByTestId('cleanup-status-card')).toBeInTheDocument();
    });

    expect(screen.getByTestId('last-updated')).toHaveTextContent('Last updated:');
  });

  it('handles midnight cleanup time', async () => {
    mockFetchCleanupStatus.mockResolvedValue({
      running: true,
      retention_days: 30,
      cleanup_time: '00:00',
      delete_images: false,
      next_cleanup: '2025-12-31T00:00:00Z',
      timestamp: '2025-12-30T10:30:00Z',
    });

    render(<CleanupStatusCard />);

    await waitFor(() => {
      expect(screen.getByTestId('cleanup-status-card')).toBeInTheDocument();
    });

    // Check for midnight format - the exact text may vary by locale
    expect(screen.getByTestId('cleanup-time')).toHaveTextContent(/12:00.*AM/i);
  });

  it('handles noon cleanup time', async () => {
    mockFetchCleanupStatus.mockResolvedValue({
      running: true,
      retention_days: 30,
      cleanup_time: '12:00',
      delete_images: false,
      next_cleanup: '2025-12-31T12:00:00Z',
      timestamp: '2025-12-30T10:30:00Z',
    });

    render(<CleanupStatusCard />);

    await waitFor(() => {
      expect(screen.getByTestId('cleanup-status-card')).toBeInTheDocument();
    });

    // Check for noon format (12:00 PM) - need to verify the element exists and contains time
    const cleanupTime = screen.getByTestId('cleanup-time');
    expect(cleanupTime).toBeInTheDocument();
    // The time should contain 12:00
    expect(cleanupTime.textContent).toContain('12:00');
  });
});
