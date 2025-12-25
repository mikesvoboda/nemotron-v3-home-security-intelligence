import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import LogStatsCards from './LogStatsCards';
import * as api from '../../services/api';

import type { LogStats } from '../../services/api';

// Mock API module
vi.mock('../../services/api');

describe('LogStatsCards', () => {
  const mockStats: LogStats = {
    total_today: 150,
    errors_today: 5,
    warnings_today: 10,
    by_component: {
      api: 50,
      detector: 40,
      frontend: 30,
      file_watcher: 30,
    },
    by_level: {
      ERROR: 5,
      WARNING: 10,
      INFO: 100,
      DEBUG: 35,
    },
    top_component: 'api',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchLogStats).mockResolvedValue(mockStats);
  });

  describe('Rendering', () => {
    it('renders the statistics title', async () => {
      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('Log Statistics')).toBeInTheDocument();
      });
    });

    it('displays loading state initially', () => {
      render(<LogStatsCards />);

      expect(screen.getByText('Log Statistics')).toBeInTheDocument();
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('displays all statistics after loading', async () => {
      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('5')).toBeInTheDocument(); // errors_today
      });

      expect(screen.getByText('10')).toBeInTheDocument(); // warnings_today
      expect(screen.getByText('150')).toBeInTheDocument(); // total_today
      expect(screen.getByText('api')).toBeInTheDocument(); // top_component
    });

    it('displays correct card labels', async () => {
      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('Errors Today')).toBeInTheDocument();
      });

      expect(screen.getByText('Warnings Today')).toBeInTheDocument();
      expect(screen.getByText('Total Today')).toBeInTheDocument();
      expect(screen.getByText('Most Active')).toBeInTheDocument();
    });

    it('displays log count for most active component', async () => {
      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('api')).toBeInTheDocument();
      });

      expect(screen.getByText('50 logs')).toBeInTheDocument();
    });
  });

  describe('Error Badge', () => {
    it('shows red styling when errors exist', async () => {
      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('5')).toBeInTheDocument();
      });

      const errorText = screen.getByText('5');
      expect(errorText).toHaveClass('text-red-500');
    });

    it('shows Active badge when errors exist', async () => {
      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('Active')).toBeInTheDocument();
      });
    });

    it('shows gray styling when no errors', async () => {
      const noErrorStats: LogStats = {
        ...mockStats,
        errors_today: 0,
      };

      vi.mocked(api.fetchLogStats).mockResolvedValue(noErrorStats);

      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('0')).toBeInTheDocument();
      });

      const errorText = screen.getByText('0');
      expect(errorText).toHaveClass('text-gray-300');
      expect(screen.queryByText('Active')).not.toBeInTheDocument();
    });
  });

  describe('Warning Badge', () => {
    it('shows yellow styling when warnings exist', async () => {
      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('10')).toBeInTheDocument();
      });

      const warningText = screen.getByText('10');
      expect(warningText).toHaveClass('text-yellow-500');
    });

    it('shows gray styling when no warnings', async () => {
      const noWarningStats: LogStats = {
        ...mockStats,
        warnings_today: 0,
      };

      vi.mocked(api.fetchLogStats).mockResolvedValue(noWarningStats);

      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('Warnings Today')).toBeInTheDocument();
      });

      const warningText = screen.getByText('0');
      expect(warningText).toHaveClass('text-gray-300');
    });
  });

  describe('Most Active Component', () => {
    it('displays N/A when no top component', async () => {
      const noTopComponentStats: LogStats = {
        ...mockStats,
        top_component: null,
      };

      vi.mocked(api.fetchLogStats).mockResolvedValue(noTopComponentStats);

      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('N/A')).toBeInTheDocument();
      });

      expect(screen.queryByText('logs')).not.toBeInTheDocument();
    });

    it('displays component name and log count', async () => {
      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('api')).toBeInTheDocument();
      });

      expect(screen.getByText('50 logs')).toBeInTheDocument();
    });

    it('handles missing component count', async () => {
      const statsWithoutCount: LogStats = {
        ...mockStats,
        top_component: 'unknown_component',
        by_component: {
          api: 50,
          detector: 40,
        },
      };

      vi.mocked(api.fetchLogStats).mockResolvedValue(statsWithoutCount);

      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('unknown_component')).toBeInTheDocument();
      });

      expect(screen.queryByText('logs')).not.toBeInTheDocument();
    });
  });

  describe('Auto-refresh', () => {
    it('refreshes stats every 30 seconds', async () => {
      vi.useFakeTimers();
      vi.clearAllMocks();
      vi.mocked(api.fetchLogStats).mockResolvedValue(mockStats);

      render(<LogStatsCards />);

      // Initial load
      await waitFor(() => {
        expect(api.fetchLogStats).toHaveBeenCalledTimes(1);
      }, { timeout: 10000 });

      // Fast-forward 30 seconds
      await vi.advanceTimersByTimeAsync(30000);

      await waitFor(() => {
        expect(api.fetchLogStats).toHaveBeenCalledTimes(2);
      }, { timeout: 10000 });

      // Fast-forward another 30 seconds
      await vi.advanceTimersByTimeAsync(30000);

      await waitFor(() => {
        expect(api.fetchLogStats).toHaveBeenCalledTimes(3);
      }, { timeout: 10000 });

      vi.useRealTimers();
    }, 15000);

    it('clears interval on unmount', async () => {
      vi.useFakeTimers();
      vi.clearAllMocks();
      vi.mocked(api.fetchLogStats).mockResolvedValue(mockStats);

      const { unmount } = render(<LogStatsCards />);

      await waitFor(() => {
        expect(api.fetchLogStats).toHaveBeenCalledTimes(1);
      }, { timeout: 10000 });

      unmount();

      // Fast-forward 30 seconds after unmount
      await vi.advanceTimersByTimeAsync(30000);

      // Should not have been called again
      expect(api.fetchLogStats).toHaveBeenCalledTimes(1);

      vi.useRealTimers();
    }, 15000);

    it('updates display when stats change', async () => {
      vi.useFakeTimers();
      vi.clearAllMocks();
      vi.mocked(api.fetchLogStats).mockResolvedValue(mockStats);

      const { rerender } = render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('5')).toBeInTheDocument();
      }, { timeout: 10000 });

      // Update mock stats
      const updatedStats: LogStats = {
        ...mockStats,
        errors_today: 15,
      };

      vi.mocked(api.fetchLogStats).mockResolvedValue(updatedStats);

      // Fast-forward to trigger refresh
      await vi.advanceTimersByTimeAsync(30000);

      rerender(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('15')).toBeInTheDocument();
      }, { timeout: 10000 });

      vi.useRealTimers();
    }, 15000);
  });

  describe('Error Handling', () => {
    it('displays error message when fetching stats fails', async () => {
      vi.clearAllMocks();
      vi.mocked(api.fetchLogStats).mockRejectedValue(new Error('Network error'));

      render(<LogStatsCards />);

      await waitFor(
        () => {
          expect(screen.getByText('Network error')).toBeInTheDocument();
        },
        { timeout: 10000 }
      );

      expect(screen.getByText('Log Statistics')).toBeInTheDocument();
    }, 15000);

    it('displays generic error message for non-Error objects', async () => {
      vi.clearAllMocks();
      vi.mocked(api.fetchLogStats).mockRejectedValue('String error');

      render(<LogStatsCards />);

      await waitFor(
        () => {
          expect(screen.getByText('Failed to load log stats')).toBeInTheDocument();
        },
        { timeout: 10000 }
      );
    }, 15000);

    it('retains previous stats on refresh error', async () => {
      vi.useFakeTimers();
      vi.clearAllMocks();
      vi.mocked(api.fetchLogStats).mockResolvedValue(mockStats);

      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('5')).toBeInTheDocument();
      }, { timeout: 10000 });

      // Simulate error on refresh
      vi.mocked(api.fetchLogStats).mockRejectedValue(new Error('Network error'));

      await vi.advanceTimersByTimeAsync(30000);

      // Should still show previous stats
      await waitFor(() => {
        expect(screen.getByText('5')).toBeInTheDocument();
      }, { timeout: 10000 });

      vi.useRealTimers();
    }, 15000);
  });

  describe('Custom Styling', () => {
    it('applies custom className', async () => {
      vi.clearAllMocks();
      vi.mocked(api.fetchLogStats).mockResolvedValue(mockStats);

      const { container } = render(<LogStatsCards className="custom-class" />);

      await waitFor(() => {
        expect(screen.getByText('Log Statistics')).toBeInTheDocument();
      }, { timeout: 10000 });

      const card = container.querySelector('.custom-class');
      expect(card).toBeInTheDocument();
    }, 15000);

    it('uses NVIDIA dark theme colors', async () => {
      vi.clearAllMocks();
      vi.mocked(api.fetchLogStats).mockResolvedValue(mockStats);

      const { container } = render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('Log Statistics')).toBeInTheDocument();
      }, { timeout: 10000 });

      const card = container.querySelector('.bg-\\[\\#1A1A1A\\]');
      expect(card).toBeInTheDocument();
    }, 15000);

    it('uses green accent color for total today', async () => {
      vi.clearAllMocks();
      vi.mocked(api.fetchLogStats).mockResolvedValue(mockStats);

      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('150')).toBeInTheDocument();
      }, { timeout: 10000 });

      const totalText = screen.getByText('150');
      expect(totalText).toHaveClass('text-[#76B900]');
    }, 15000);
  });

  describe('Zero Stats', () => {
    it('handles all zeros gracefully', async () => {
      const zeroStats: LogStats = {
        total_today: 0,
        errors_today: 0,
        warnings_today: 0,
        by_component: {},
        by_level: {},
        top_component: null,
      };

      vi.clearAllMocks();
      vi.mocked(api.fetchLogStats).mockResolvedValue(zeroStats);

      render(<LogStatsCards />);

      await waitFor(() => {
        expect(screen.getByText('Errors Today')).toBeInTheDocument();
      }, { timeout: 10000 });

      // Should display all zeros
      const zeros = screen.getAllByText('0');
      expect(zeros.length).toBeGreaterThanOrEqual(3);
    }, 15000);
  });
});
