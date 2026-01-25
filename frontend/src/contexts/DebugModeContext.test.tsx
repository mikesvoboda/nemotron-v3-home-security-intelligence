/**
 * Tests for DebugModeContext
 *
 * The context provides debug mode state to child components:
 * - debugMode: boolean - current debug mode state
 * - setDebugMode: function - to update the state
 * - isDebugAvailable: boolean - whether backend has debug enabled
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, Mock, vi } from 'vitest';

import { DebugModeProvider, useDebugMode } from './DebugModeContext';
import { useLocalStorage } from '../hooks/useLocalStorage';
import { useSystemConfigQuery } from '../hooks/useSystemConfigQuery';

// Mock the hooks
vi.mock('../hooks/useSystemConfigQuery');
vi.mock('../hooks/useLocalStorage');

const mockedUseSystemConfigQuery = useSystemConfigQuery as Mock;
const mockedUseLocalStorage = useLocalStorage as Mock;

// Test component that consumes the context
function TestConsumer() {
  const { debugMode, setDebugMode, isDebugAvailable } = useDebugMode();
  return (
    <div>
      <span data-testid="debug-mode">{debugMode.toString()}</span>
      <span data-testid="debug-available">{isDebugAvailable.toString()}</span>
      <button data-testid="toggle-debug" onClick={() => setDebugMode(!debugMode)}>
        Toggle
      </button>
    </div>
  );
}

describe('DebugModeContext', () => {
  const mockSetDebugMode = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    // Default: debug enabled on backend, debug mode off
    mockedUseSystemConfigQuery.mockReturnValue({
      data: { debug: true },
      isLoading: false,
      error: null,
      debugEnabled: true,
      refetch: vi.fn(),
    });
    mockedUseLocalStorage.mockReturnValue([false, mockSetDebugMode]);
  });

  describe('DebugModeProvider', () => {
    it('provides debugMode state to children', () => {
      render(
        <DebugModeProvider>
          <TestConsumer />
        </DebugModeProvider>
      );

      expect(screen.getByTestId('debug-mode')).toHaveTextContent('false');
    });

    it('provides isDebugAvailable based on backend config', () => {
      render(
        <DebugModeProvider>
          <TestConsumer />
        </DebugModeProvider>
      );

      expect(screen.getByTestId('debug-available')).toHaveTextContent('true');
    });

    it('provides setDebugMode function to update state', async () => {
      const user = userEvent.setup();

      render(
        <DebugModeProvider>
          <TestConsumer />
        </DebugModeProvider>
      );

      await user.click(screen.getByTestId('toggle-debug'));

      expect(mockSetDebugMode).toHaveBeenCalledWith(true);
    });

    it('reflects debug mode from localStorage', () => {
      mockedUseLocalStorage.mockReturnValue([true, mockSetDebugMode]);

      render(
        <DebugModeProvider>
          <TestConsumer />
        </DebugModeProvider>
      );

      expect(screen.getByTestId('debug-mode')).toHaveTextContent('true');
    });

    it('isDebugAvailable is false when backend debug is disabled', () => {
      mockedUseSystemConfigQuery.mockReturnValue({
        data: { debug: false },
        isLoading: false,
        error: null,
        debugEnabled: false,
        refetch: vi.fn(),
      });

      render(
        <DebugModeProvider>
          <TestConsumer />
        </DebugModeProvider>
      );

      expect(screen.getByTestId('debug-available')).toHaveTextContent('false');
    });

    it('isDebugAvailable is false while loading', () => {
      mockedUseSystemConfigQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        debugEnabled: false,
        refetch: vi.fn(),
      });

      render(
        <DebugModeProvider>
          <TestConsumer />
        </DebugModeProvider>
      );

      expect(screen.getByTestId('debug-available')).toHaveTextContent('false');
    });

    it('uses correct localStorage key', () => {
      render(
        <DebugModeProvider>
          <TestConsumer />
        </DebugModeProvider>
      );

      expect(mockedUseLocalStorage).toHaveBeenCalledWith('system-debug-mode', false);
    });
  });

  describe('useDebugMode hook', () => {
    it('throws error when used outside provider', () => {
      // Suppress console.error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        render(<TestConsumer />);
      }).toThrow('useDebugMode must be used within a DebugModeProvider');

      consoleSpy.mockRestore();
    });
  });

  describe('Debug mode state', () => {
    it('debug mode is false even when available but not toggled', () => {
      mockedUseSystemConfigQuery.mockReturnValue({
        data: { debug: true },
        isLoading: false,
        error: null,
        debugEnabled: true,
        refetch: vi.fn(),
      });
      mockedUseLocalStorage.mockReturnValue([false, mockSetDebugMode]);

      render(
        <DebugModeProvider>
          <TestConsumer />
        </DebugModeProvider>
      );

      // Available but not active
      expect(screen.getByTestId('debug-available')).toHaveTextContent('true');
      expect(screen.getByTestId('debug-mode')).toHaveTextContent('false');
    });

    it('debug mode can be true when available and toggled on', () => {
      mockedUseSystemConfigQuery.mockReturnValue({
        data: { debug: true },
        isLoading: false,
        error: null,
        debugEnabled: true,
        refetch: vi.fn(),
      });
      mockedUseLocalStorage.mockReturnValue([true, mockSetDebugMode]);

      render(
        <DebugModeProvider>
          <TestConsumer />
        </DebugModeProvider>
      );

      expect(screen.getByTestId('debug-available')).toHaveTextContent('true');
      expect(screen.getByTestId('debug-mode')).toHaveTextContent('true');
    });

    it('debug mode is false when not available even if localStorage says true', () => {
      mockedUseSystemConfigQuery.mockReturnValue({
        data: { debug: false },
        isLoading: false,
        error: null,
        debugEnabled: false,
        refetch: vi.fn(),
      });
      // Even though localStorage has it as true
      mockedUseLocalStorage.mockReturnValue([true, mockSetDebugMode]);

      render(
        <DebugModeProvider>
          <TestConsumer />
        </DebugModeProvider>
      );

      // Not available means debug mode should be false
      expect(screen.getByTestId('debug-available')).toHaveTextContent('false');
      // When not available, debugMode should be forced to false
      expect(screen.getByTestId('debug-mode')).toHaveTextContent('false');
    });
  });
});
