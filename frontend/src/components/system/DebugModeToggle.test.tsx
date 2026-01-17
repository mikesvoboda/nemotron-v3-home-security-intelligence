/**
 * Tests for DebugModeToggle component
 *
 * Following TDD, these tests define the expected behavior:
 * - Only renders when backend has debug enabled
 * - Persists state to localStorage
 * - Visual indication when debug mode is active (orange highlight)
 * - Accessible toggle control
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, Mock, vi } from 'vitest';

import DebugModeToggle from './DebugModeToggle';
import { useLocalStorage } from '../../hooks/useLocalStorage';
import { useSystemConfigQuery } from '../../hooks/useSystemConfigQuery';

// Mock the hooks
vi.mock('../../hooks/useSystemConfigQuery');
vi.mock('../../hooks/useLocalStorage');

// Type the mocks
const mockedUseSystemConfigQuery = useSystemConfigQuery as Mock;
const mockedUseLocalStorage = useLocalStorage as Mock;

describe('DebugModeToggle', () => {
  const mockSetDebugMode = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    // Default: debug enabled on backend, debug mode off in localStorage
    mockedUseSystemConfigQuery.mockReturnValue({
      data: { debug: true },
      isLoading: false,
      error: null,
      debugEnabled: true,
      refetch: vi.fn(),
    });
    mockedUseLocalStorage.mockReturnValue([false, mockSetDebugMode]);
  });

  describe('Conditional Rendering', () => {
    it('renders toggle when backend debug is enabled', () => {
      render(<DebugModeToggle />);
      expect(screen.getByTestId('debug-mode-toggle')).toBeInTheDocument();
    });

    it('does not render when backend debug is disabled', () => {
      mockedUseSystemConfigQuery.mockReturnValue({
        data: { debug: false },
        isLoading: false,
        error: null,
        debugEnabled: false,
        refetch: vi.fn(),
      });

      render(<DebugModeToggle />);
      expect(screen.queryByTestId('debug-mode-toggle')).not.toBeInTheDocument();
    });

    it('does not render while loading', () => {
      mockedUseSystemConfigQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        debugEnabled: false,
        refetch: vi.fn(),
      });

      render(<DebugModeToggle />);
      expect(screen.queryByTestId('debug-mode-toggle')).not.toBeInTheDocument();
    });

    it('does not render when config fetch fails', () => {
      mockedUseSystemConfigQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to fetch'),
        debugEnabled: false,
        refetch: vi.fn(),
      });

      render(<DebugModeToggle />);
      expect(screen.queryByTestId('debug-mode-toggle')).not.toBeInTheDocument();
    });

    it('does not render when config data is undefined', () => {
      mockedUseSystemConfigQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: null,
        debugEnabled: false,
        refetch: vi.fn(),
      });

      render(<DebugModeToggle />);
      expect(screen.queryByTestId('debug-mode-toggle')).not.toBeInTheDocument();
    });
  });

  describe('Toggle Functionality', () => {
    it('displays correct text label', () => {
      render(<DebugModeToggle />);
      expect(screen.getByText('Debug Mode')).toBeInTheDocument();
    });

    it('displays wrench icon', () => {
      render(<DebugModeToggle />);
      expect(screen.getByTestId('debug-mode-icon')).toBeInTheDocument();
    });

    it('has a switch/toggle control', () => {
      render(<DebugModeToggle />);
      expect(screen.getByRole('switch')).toBeInTheDocument();
    });

    it('toggle is unchecked when debug mode is off', () => {
      mockedUseLocalStorage.mockReturnValue([false, mockSetDebugMode]);

      render(<DebugModeToggle />);
      const toggle = screen.getByRole('switch');
      expect(toggle).toHaveAttribute('aria-checked', 'false');
    });

    it('toggle is checked when debug mode is on', () => {
      mockedUseLocalStorage.mockReturnValue([true, mockSetDebugMode]);

      render(<DebugModeToggle />);
      const toggle = screen.getByRole('switch');
      expect(toggle).toHaveAttribute('aria-checked', 'true');
    });

    it('calls setDebugMode when toggle is clicked', async () => {
      const user = userEvent.setup();
      render(<DebugModeToggle />);

      const toggle = screen.getByRole('switch');
      await user.click(toggle);

      expect(mockSetDebugMode).toHaveBeenCalledTimes(1);
      expect(mockSetDebugMode).toHaveBeenCalledWith(true);
    });

    it('toggles from on to off when clicked', async () => {
      mockedUseLocalStorage.mockReturnValue([true, mockSetDebugMode]);
      const user = userEvent.setup();

      render(<DebugModeToggle />);

      const toggle = screen.getByRole('switch');
      await user.click(toggle);

      expect(mockSetDebugMode).toHaveBeenCalledWith(false);
    });
  });

  describe('LocalStorage Persistence', () => {
    it('uses correct localStorage key', () => {
      render(<DebugModeToggle />);
      expect(mockedUseLocalStorage).toHaveBeenCalledWith('system-debug-mode', false);
    });
  });

  describe('Visual Styling', () => {
    it('has orange/amber highlight when debug mode is active', () => {
      mockedUseLocalStorage.mockReturnValue([true, mockSetDebugMode]);

      render(<DebugModeToggle />);
      const container = screen.getByTestId('debug-mode-toggle');

      // Should have orange-related classes when active
      expect(container).toHaveClass('border-orange-500/50');
      expect(container).toHaveClass('bg-orange-500/10');
    });

    it('has neutral styling when debug mode is inactive', () => {
      mockedUseLocalStorage.mockReturnValue([false, mockSetDebugMode]);

      render(<DebugModeToggle />);
      const container = screen.getByTestId('debug-mode-toggle');

      // Should have neutral/gray styling when inactive
      expect(container).toHaveClass('border-gray-700');
      expect(container).toHaveClass('bg-gray-800/50');
    });

    it('toggle has orange color when checked', () => {
      mockedUseLocalStorage.mockReturnValue([true, mockSetDebugMode]);

      render(<DebugModeToggle />);
      const toggle = screen.getByRole('switch');

      // The switch should have orange background when checked
      expect(toggle).toHaveClass('bg-orange-500');
    });

    it('toggle has gray color when unchecked', () => {
      mockedUseLocalStorage.mockReturnValue([false, mockSetDebugMode]);

      render(<DebugModeToggle />);
      const toggle = screen.getByRole('switch');

      // The switch should have gray background when unchecked
      expect(toggle).toHaveClass('bg-gray-600');
    });
  });

  describe('Accessibility', () => {
    it('has appropriate aria-label for the toggle', () => {
      render(<DebugModeToggle />);
      const toggle = screen.getByRole('switch');
      expect(toggle).toHaveAttribute('aria-label', 'Toggle debug mode');
    });

    it('is keyboard accessible', async () => {
      const user = userEvent.setup();
      render(<DebugModeToggle />);

      const toggle = screen.getByRole('switch');

      // Tab to the switch - verify it's focusable
      await user.tab();
      expect(toggle).toHaveFocus();

      // Verify the toggle has proper ARIA attributes for keyboard accessibility
      // HeadlessUI Switch handles Enter/Space internally - tabIndex ensures it's in tab order
      expect(toggle.tagName).toBe('BUTTON'); // Button is keyboard accessible by default
    });

    it('has focus ring styling', () => {
      render(<DebugModeToggle />);
      const toggle = screen.getByRole('switch');
      expect(toggle).toHaveClass('focus:outline-none');
      expect(toggle).toHaveClass('focus:ring-2');
    });
  });

  describe('Custom className', () => {
    it('applies custom className when provided', () => {
      render(<DebugModeToggle className="custom-class" />);
      const container = screen.getByTestId('debug-mode-toggle');
      expect(container).toHaveClass('custom-class');
    });
  });

  describe('Callback Integration', () => {
    it('calls onChange callback when toggle state changes', async () => {
      const onChange = vi.fn();
      const user = userEvent.setup();

      render(<DebugModeToggle onChange={onChange} />);

      const toggle = screen.getByRole('switch');
      await user.click(toggle);

      expect(onChange).toHaveBeenCalledWith(true);
    });

    it('calls onChange with false when toggled off', async () => {
      mockedUseLocalStorage.mockReturnValue([true, mockSetDebugMode]);
      const onChange = vi.fn();
      const user = userEvent.setup();

      render(<DebugModeToggle onChange={onChange} />);

      const toggle = screen.getByRole('switch');
      await user.click(toggle);

      expect(onChange).toHaveBeenCalledWith(false);
    });
  });
});
