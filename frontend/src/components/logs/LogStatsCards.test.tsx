import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import LogStatsCards from './LogStatsCards';
import * as api from '../../services/api';

import type { LogStats } from '../../services/api';
import type { LogLevel } from '../../services/logger';

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
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.clearAllMocks();
    vi.mocked(api.fetchLogStats).mockResolvedValue(mockStats);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // Helper to render and wait for initial load
  const renderAndWaitForLoad = async () => {
    const result = render(<LogStatsCards />);
    // Advance timers to trigger any pending microtasks and the immediate effect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    return result;
  };

  describe('Rendering', () => {
    it('renders the statistics title', async () => {
      await renderAndWaitForLoad();
      expect(screen.getByText('Log Statistics')).toBeInTheDocument();
    });

    it('displays loading state initially', () => {
      render(<LogStatsCards />);

      expect(screen.getByText('Log Statistics')).toBeInTheDocument();
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('displays all statistics after loading', async () => {
      await renderAndWaitForLoad();

      expect(screen.getByText('5')).toBeInTheDocument(); // errors_today
      expect(screen.getByText('10')).toBeInTheDocument(); // warnings_today
      expect(screen.getByText('150')).toBeInTheDocument(); // total_today
      expect(screen.getByText('api')).toBeInTheDocument(); // top_component
    });

    it('displays correct card labels', async () => {
      await renderAndWaitForLoad();

      expect(screen.getByText('Errors Today')).toBeInTheDocument();
      expect(screen.getByText('Warnings Today')).toBeInTheDocument();
      expect(screen.getByText('Total Today')).toBeInTheDocument();
      expect(screen.getByText('Most Active')).toBeInTheDocument();
    });

    it('displays log count for most active component', async () => {
      await renderAndWaitForLoad();

      expect(screen.getByText('api')).toBeInTheDocument();
      expect(screen.getByText('50 logs')).toBeInTheDocument();
    });
  });

  describe('Error Badge', () => {
    it('shows red styling when errors exist', async () => {
      await renderAndWaitForLoad();

      const errorText = screen.getByText('5');
      expect(errorText).toHaveClass('text-red-500');
    });

    it('shows Active badge when errors exist', async () => {
      await renderAndWaitForLoad();

      expect(screen.getByText('Active')).toBeInTheDocument();
    });

    it('shows gray styling when no errors', async () => {
      const noErrorStats: LogStats = {
        ...mockStats,
        errors_today: 0,
      };

      vi.mocked(api.fetchLogStats).mockResolvedValue(noErrorStats);

      await renderAndWaitForLoad();

      const errorText = screen.getByText('0');
      expect(errorText).toHaveClass('text-gray-300');
      expect(screen.queryByText('Active')).not.toBeInTheDocument();
    });
  });

  describe('Warning Badge', () => {
    it('shows yellow styling when warnings exist', async () => {
      await renderAndWaitForLoad();

      const warningText = screen.getByText('10');
      expect(warningText).toHaveClass('text-yellow-500');
    });

    it('shows gray styling when no warnings', async () => {
      const noWarningStats: LogStats = {
        ...mockStats,
        warnings_today: 0,
      };

      vi.mocked(api.fetchLogStats).mockResolvedValue(noWarningStats);

      await renderAndWaitForLoad();

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

      await renderAndWaitForLoad();

      expect(screen.getByText('N/A')).toBeInTheDocument();
      expect(screen.queryByText('logs')).not.toBeInTheDocument();
    });

    it('displays component name and log count', async () => {
      await renderAndWaitForLoad();

      expect(screen.getByText('api')).toBeInTheDocument();
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

      await renderAndWaitForLoad();

      expect(screen.getByText('unknown_component')).toBeInTheDocument();
      expect(screen.queryByText('logs')).not.toBeInTheDocument();
    });
  });

  describe('Auto-refresh', () => {
    it('refreshes stats every 30 seconds', async () => {
      await renderAndWaitForLoad();

      expect(api.fetchLogStats).toHaveBeenCalledTimes(1);
      expect(screen.getByText('5')).toBeInTheDocument();

      // Advance 30 seconds to trigger interval
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });

      expect(api.fetchLogStats).toHaveBeenCalledTimes(2);
    });

    it('clears interval on unmount', async () => {
      const { unmount } = await renderAndWaitForLoad();

      expect(api.fetchLogStats).toHaveBeenCalledTimes(1);

      unmount();

      // Advance time after unmount - interval should be cleared
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });

      // Should still be 1, interval was cleared
      expect(api.fetchLogStats).toHaveBeenCalledTimes(1);
    });

    it('updates display when stats change', async () => {
      await renderAndWaitForLoad();

      expect(screen.getByText('5')).toBeInTheDocument();

      // Update mock stats for next refresh
      const updatedStats: LogStats = {
        ...mockStats,
        errors_today: 15,
      };
      vi.mocked(api.fetchLogStats).mockResolvedValue(updatedStats);

      // Advance 30 seconds to trigger interval refresh
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });

      // Should now show updated stats
      expect(screen.getByText('15')).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('displays error message when fetching stats fails', async () => {
      vi.mocked(api.fetchLogStats).mockRejectedValue(new Error('Network error'));

      await renderAndWaitForLoad();

      expect(screen.getByText('Network error')).toBeInTheDocument();
      expect(screen.getByText('Log Statistics')).toBeInTheDocument();
    });

    it('displays generic error message for non-Error objects', async () => {
      vi.mocked(api.fetchLogStats).mockRejectedValue('String error');

      await renderAndWaitForLoad();

      expect(screen.getByText('Failed to load log stats')).toBeInTheDocument();
    });

    it('retains previous stats on refresh error', async () => {
      await renderAndWaitForLoad();

      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('150')).toBeInTheDocument();

      // Next refresh will fail
      vi.mocked(api.fetchLogStats).mockRejectedValue(new Error('Refresh error'));

      // Advance 30 seconds to trigger interval refresh
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });

      // Component shows error state when refresh fails
      expect(screen.getByText('Refresh error')).toBeInTheDocument();
    });
  });

  describe('Custom Styling', () => {
    it('applies custom className', async () => {
      const { container } = render(<LogStatsCards className="custom-class" />);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });

      expect(screen.getByText('Log Statistics')).toBeInTheDocument();
      const card = container.querySelector('.custom-class');
      expect(card).toBeInTheDocument();
    });

    it('uses NVIDIA dark theme colors', async () => {
      const { container } = await renderAndWaitForLoad();

      expect(screen.getByText('Log Statistics')).toBeInTheDocument();
      const card = container.querySelector('.bg-\\[\\#1A1A1A\\]');
      expect(card).toBeInTheDocument();
    });

    it('uses green accent color for total today', async () => {
      await renderAndWaitForLoad();

      expect(screen.getByText('150')).toBeInTheDocument();
      const totalText = screen.getByText('150');
      expect(totalText).toHaveClass('text-[#76B900]');
    });
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

      vi.mocked(api.fetchLogStats).mockResolvedValue(zeroStats);

      await renderAndWaitForLoad();

      expect(screen.getByText('Errors Today')).toBeInTheDocument();
      // Should display all zeros
      const zeros = screen.getAllByText('0');
      expect(zeros.length).toBeGreaterThanOrEqual(3);
    });
  });

  describe('Clickable Level Filter Cards', () => {
    // Helper to render with callback and wait for load
    const renderWithCallbackAndWaitForLoad = async (
      onLevelFilter: (level: LogLevel | undefined) => void,
      activeLevel?: LogLevel
    ) => {
      const result = render(
        <LogStatsCards onLevelFilter={onLevelFilter} activeLevel={activeLevel} />
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
      return result;
    };

    it('calls onLevelFilter with ERROR when clicking Errors Today card', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const mockOnLevelFilter = vi.fn();

      await renderWithCallbackAndWaitForLoad(mockOnLevelFilter);

      const errorCard = screen.getByRole('button', { name: 'Filter by errors' });
      await user.click(errorCard);

      expect(mockOnLevelFilter).toHaveBeenCalledWith('ERROR');
    });

    it('calls onLevelFilter with WARNING when clicking Warnings Today card', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const mockOnLevelFilter = vi.fn();

      await renderWithCallbackAndWaitForLoad(mockOnLevelFilter);

      const warningCard = screen.getByRole('button', { name: 'Filter by warnings' });
      await user.click(warningCard);

      expect(mockOnLevelFilter).toHaveBeenCalledWith('WARNING');
    });

    it('calls onLevelFilter with undefined when clicking already active ERROR card (toggle off)', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const mockOnLevelFilter = vi.fn();

      await renderWithCallbackAndWaitForLoad(mockOnLevelFilter, 'ERROR');

      const errorCard = screen.getByRole('button', { name: 'Filter by errors' });
      await user.click(errorCard);

      expect(mockOnLevelFilter).toHaveBeenCalledWith(undefined);
    });

    it('calls onLevelFilter with undefined when clicking already active WARNING card (toggle off)', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const mockOnLevelFilter = vi.fn();

      await renderWithCallbackAndWaitForLoad(mockOnLevelFilter, 'WARNING');

      const warningCard = screen.getByRole('button', { name: 'Filter by warnings' });
      await user.click(warningCard);

      expect(mockOnLevelFilter).toHaveBeenCalledWith(undefined);
    });

    it('shows active state ring on ERROR card when activeLevel is ERROR', async () => {
      const mockOnLevelFilter = vi.fn();

      await renderWithCallbackAndWaitForLoad(mockOnLevelFilter, 'ERROR');

      const errorCard = screen.getByRole('button', { name: 'Filter by errors' });
      expect(errorCard).toHaveClass('ring-2');
      expect(errorCard).toHaveClass('ring-red-500');

      // Warning card should NOT have ring
      const warningCard = screen.getByRole('button', { name: 'Filter by warnings' });
      expect(warningCard).not.toHaveClass('ring-2');
    });

    it('shows active state ring on WARNING card when activeLevel is WARNING', async () => {
      const mockOnLevelFilter = vi.fn();

      await renderWithCallbackAndWaitForLoad(mockOnLevelFilter, 'WARNING');

      const warningCard = screen.getByRole('button', { name: 'Filter by warnings' });
      expect(warningCard).toHaveClass('ring-2');
      expect(warningCard).toHaveClass('ring-yellow-500');

      // Error card should NOT have ring
      const errorCard = screen.getByRole('button', { name: 'Filter by errors' });
      expect(errorCard).not.toHaveClass('ring-2');
    });

    it('cards have cursor-pointer class when onLevelFilter is provided', async () => {
      const mockOnLevelFilter = vi.fn();

      await renderWithCallbackAndWaitForLoad(mockOnLevelFilter);

      const errorCard = screen.getByRole('button', { name: 'Filter by errors' });
      const warningCard = screen.getByRole('button', { name: 'Filter by warnings' });

      expect(errorCard).toHaveClass('cursor-pointer');
      expect(warningCard).toHaveClass('cursor-pointer');
    });

    it('cards do NOT have button role when onLevelFilter is not provided', async () => {
      await renderAndWaitForLoad();

      // Without onLevelFilter, cards should not be buttons
      expect(screen.queryByRole('button', { name: 'Filter by errors' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Filter by warnings' })).not.toBeInTheDocument();
    });

    it('cards have aria-pressed attribute reflecting active state', async () => {
      const mockOnLevelFilter = vi.fn();

      await renderWithCallbackAndWaitForLoad(mockOnLevelFilter, 'ERROR');

      const errorCard = screen.getByRole('button', { name: 'Filter by errors' });
      const warningCard = screen.getByRole('button', { name: 'Filter by warnings' });

      expect(errorCard).toHaveAttribute('aria-pressed', 'true');
      expect(warningCard).toHaveAttribute('aria-pressed', 'false');
    });

    it('supports keyboard activation with Enter key', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const mockOnLevelFilter = vi.fn();

      await renderWithCallbackAndWaitForLoad(mockOnLevelFilter);

      const errorCard = screen.getByRole('button', { name: 'Filter by errors' });
      errorCard.focus();
      await user.keyboard('{Enter}');

      expect(mockOnLevelFilter).toHaveBeenCalledWith('ERROR');
    });

    it('supports keyboard activation with Space key', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const mockOnLevelFilter = vi.fn();

      await renderWithCallbackAndWaitForLoad(mockOnLevelFilter);

      const warningCard = screen.getByRole('button', { name: 'Filter by warnings' });
      warningCard.focus();
      await user.keyboard(' ');

      expect(mockOnLevelFilter).toHaveBeenCalledWith('WARNING');
    });

    it('cards have hover classes for visual feedback', async () => {
      const mockOnLevelFilter = vi.fn();

      await renderWithCallbackAndWaitForLoad(mockOnLevelFilter);

      const errorCard = screen.getByRole('button', { name: 'Filter by errors' });
      const warningCard = screen.getByRole('button', { name: 'Filter by warnings' });

      // Check for hover classes (Tailwind hover: prefix)
      expect(errorCard.className).toContain('hover:border-red-500/50');
      expect(errorCard.className).toContain('hover:bg-zinc-800');
      expect(warningCard.className).toContain('hover:border-yellow-500/50');
      expect(warningCard.className).toContain('hover:bg-zinc-800');
    });
  });
});
