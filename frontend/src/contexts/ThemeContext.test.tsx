/**
 * Tests for ThemeContext
 *
 * The context provides theme state to child components:
 * - mode: ThemeMode - current theme setting (light, dark, system)
 * - resolvedTheme: ResolvedTheme - actual theme being displayed
 * - isDark: boolean - whether dark mode is active
 * - setMode: function - to set theme mode
 * - toggle: function - to toggle between light and dark
 *
 * @see NEM-3609
 */

import { act, render, renderHook, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, Mock, vi } from 'vitest';

import { ThemeProvider, useTheme, useThemeOptional, THEME_STORAGE_KEY } from './ThemeContext';
import { useLocalStorage } from '../hooks/useLocalStorage';

// Mock the useLocalStorage hook
vi.mock('../hooks/useLocalStorage');

const mockedUseLocalStorage = useLocalStorage as Mock;

// Mock matchMedia for system theme detection
const mockMatchMedia = (matches: boolean) => {
  const listeners: Array<(e: MediaQueryListEvent) => void> = [];

  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(), // deprecated
      removeListener: vi.fn(), // deprecated
      addEventListener: vi.fn(
        (_type: string, callback: (e: MediaQueryListEvent) => void) => {
          listeners.push(callback);
        }
      ),
      removeEventListener: vi.fn(
        (_type: string, callback: (e: MediaQueryListEvent) => void) => {
          const index = listeners.indexOf(callback);
          if (index > -1) listeners.splice(index, 1);
        }
      ),
      dispatchEvent: vi.fn(),
    })),
  });

  return {
    triggerChange: (newMatches: boolean) => {
      listeners.forEach((listener) =>
        listener({ matches: newMatches, media: '(prefers-color-scheme: dark)' } as MediaQueryListEvent)
      );
    },
  };
};

// Test component that consumes the context
function TestConsumer() {
  const { mode, resolvedTheme, isDark, setMode, toggle } = useTheme();
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <span data-testid="resolved-theme">{resolvedTheme}</span>
      <span data-testid="is-dark">{isDark.toString()}</span>
      <button data-testid="toggle" onClick={toggle}>
        Toggle
      </button>
      <button data-testid="set-light" onClick={() => setMode('light')}>
        Light
      </button>
      <button data-testid="set-dark" onClick={() => setMode('dark')}>
        Dark
      </button>
      <button data-testid="set-system" onClick={() => setMode('system')}>
        System
      </button>
    </div>
  );
}

describe('ThemeContext', () => {
  const mockSetMode = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    // Default: dark mode
    mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);
    // Default: system prefers dark
    mockMatchMedia(true);
    // Reset document state
    document.documentElement.classList.remove('dark', 'light');
    document.documentElement.style.colorScheme = '';
  });

  describe('ThemeProvider', () => {
    it('provides mode state to children', () => {
      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      expect(screen.getByTestId('mode')).toHaveTextContent('dark');
    });

    it('provides resolved theme based on mode', () => {
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      expect(screen.getByTestId('resolved-theme')).toHaveTextContent('dark');
    });

    it('provides isDark boolean', () => {
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      expect(screen.getByTestId('is-dark')).toHaveTextContent('true');
    });

    it('resolves light mode correctly', () => {
      mockedUseLocalStorage.mockReturnValue(['light', mockSetMode]);

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      expect(screen.getByTestId('resolved-theme')).toHaveTextContent('light');
      expect(screen.getByTestId('is-dark')).toHaveTextContent('false');
    });

    it('resolves system mode based on system preference (dark)', () => {
      mockedUseLocalStorage.mockReturnValue(['system', mockSetMode]);
      mockMatchMedia(true); // System prefers dark

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      expect(screen.getByTestId('mode')).toHaveTextContent('system');
      expect(screen.getByTestId('resolved-theme')).toHaveTextContent('dark');
    });

    it('resolves system mode based on system preference (light)', () => {
      mockedUseLocalStorage.mockReturnValue(['system', mockSetMode]);
      mockMatchMedia(false); // System prefers light

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      expect(screen.getByTestId('mode')).toHaveTextContent('system');
      expect(screen.getByTestId('resolved-theme')).toHaveTextContent('light');
    });

    it('uses custom storage key when provided', () => {
      render(
        <ThemeProvider storageKey="custom-theme-key">
          <TestConsumer />
        </ThemeProvider>
      );

      expect(mockedUseLocalStorage).toHaveBeenCalledWith('custom-theme-key', 'dark');
    });

    it('uses default mode when not stored', () => {
      render(
        <ThemeProvider defaultMode="light">
          <TestConsumer />
        </ThemeProvider>
      );

      expect(mockedUseLocalStorage).toHaveBeenCalledWith(THEME_STORAGE_KEY, 'light');
    });

    it('applies dark class to document when dark mode is active', () => {
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      expect(document.documentElement.classList.contains('dark')).toBe(true);
      expect(document.documentElement.classList.contains('light')).toBe(false);
    });

    it('applies light class to document when light mode is active', () => {
      mockedUseLocalStorage.mockReturnValue(['light', mockSetMode]);

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      expect(document.documentElement.classList.contains('light')).toBe(true);
      expect(document.documentElement.classList.contains('dark')).toBe(false);
    });

    it('sets color-scheme style on document', () => {
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      expect(document.documentElement.style.colorScheme).toBe('dark');
    });
  });

  describe('setMode function', () => {
    it('calls storage setter with new mode', async () => {
      const user = userEvent.setup();
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      await user.click(screen.getByTestId('set-light'));

      expect(mockSetMode).toHaveBeenCalledWith('light');
    });

    it('allows setting to dark mode', async () => {
      const user = userEvent.setup();
      mockedUseLocalStorage.mockReturnValue(['light', mockSetMode]);

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      await user.click(screen.getByTestId('set-dark'));

      expect(mockSetMode).toHaveBeenCalledWith('dark');
    });

    it('allows setting to system mode', async () => {
      const user = userEvent.setup();
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      await user.click(screen.getByTestId('set-system'));

      expect(mockSetMode).toHaveBeenCalledWith('system');
    });
  });

  describe('toggle function', () => {
    it('toggles from dark to light', async () => {
      const user = userEvent.setup();
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      await user.click(screen.getByTestId('toggle'));

      expect(mockSetMode).toHaveBeenCalledWith('light');
    });

    it('toggles from light to dark', async () => {
      const user = userEvent.setup();
      mockedUseLocalStorage.mockReturnValue(['light', mockSetMode]);

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      await user.click(screen.getByTestId('toggle'));

      expect(mockSetMode).toHaveBeenCalledWith('dark');
    });

    it('toggles from system (dark resolved) to light', async () => {
      const user = userEvent.setup();
      mockedUseLocalStorage.mockReturnValue(['system', mockSetMode]);
      mockMatchMedia(true); // System prefers dark

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      await user.click(screen.getByTestId('toggle'));

      // Toggle switches to explicit light since resolved was dark
      expect(mockSetMode).toHaveBeenCalledWith('light');
    });
  });

  describe('useTheme hook', () => {
    it('throws error when used outside provider', () => {
      // Suppress console.error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        render(<TestConsumer />);
      }).toThrow('useTheme must be used within a ThemeProvider');

      consoleSpy.mockRestore();
    });

    it('returns all expected properties', () => {
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);

      const { result } = renderHook(() => useTheme(), {
        wrapper: ({ children }) => <ThemeProvider>{children}</ThemeProvider>,
      });

      expect(result.current).toHaveProperty('mode');
      expect(result.current).toHaveProperty('resolvedTheme');
      expect(result.current).toHaveProperty('isDark');
      expect(result.current).toHaveProperty('setMode');
      expect(result.current).toHaveProperty('toggle');
    });
  });

  describe('useThemeOptional hook', () => {
    it('returns null when used outside provider', () => {
      const { result } = renderHook(() => useThemeOptional());

      expect(result.current).toBeNull();
    });

    it('returns context value when used inside provider', () => {
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);

      const { result } = renderHook(() => useThemeOptional(), {
        wrapper: ({ children }) => <ThemeProvider>{children}</ThemeProvider>,
      });

      expect(result.current).not.toBeNull();
      expect(result.current?.mode).toBe('dark');
    });
  });

  describe('system preference change listener', () => {
    it('updates theme when system preference changes in system mode', () => {
      mockedUseLocalStorage.mockReturnValue(['system', mockSetMode]);
      const { triggerChange } = mockMatchMedia(true); // Initially dark

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      // Verify initial state
      expect(document.documentElement.classList.contains('dark')).toBe(true);

      // Trigger system preference change to light
      act(() => {
        triggerChange(false);
      });

      expect(document.documentElement.classList.contains('light')).toBe(true);
      expect(document.documentElement.classList.contains('dark')).toBe(false);
    });

    it('does not update theme on system change when mode is explicit', () => {
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);
      const { triggerChange } = mockMatchMedia(true);

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      // Verify initial state
      expect(document.documentElement.classList.contains('dark')).toBe(true);

      // Trigger system preference change (should be ignored since mode is 'dark')
      act(() => {
        triggerChange(false);
      });

      // Should still be dark because mode is explicit 'dark', not 'system'
      expect(document.documentElement.classList.contains('dark')).toBe(true);
    });
  });
});
