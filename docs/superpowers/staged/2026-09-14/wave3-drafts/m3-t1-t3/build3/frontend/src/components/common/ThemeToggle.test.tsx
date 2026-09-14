/**
 * Tests for ThemeToggle component
 *
 * Tests the theme toggle button in both simple toggle and menu modes.
 *
 * @see NEM-3609
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ThemeToggle from './ThemeToggle';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { useLocalStorage } from '../../hooks/useLocalStorage';

// Mock useLocalStorage
vi.mock('../../hooks/useLocalStorage');

const mockedUseLocalStorage = vi.mocked(useLocalStorage);

// Mock matchMedia
const mockMatchMedia = (matches: boolean) => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
};

// Wrapper component with ThemeProvider
function TestWrapper({ children }: { children: React.ReactNode }) {
  return <ThemeProvider>{children}</ThemeProvider>;
}

describe('ThemeToggle', () => {
  const mockSetMode = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);
    mockMatchMedia(true); // System prefers dark
    // Reset document state
    document.documentElement.classList.remove('dark', 'light');
  });

  describe('Simple Toggle Mode', () => {
    it('renders toggle button', () => {
      render(
        <TestWrapper>
          <ThemeToggle />
        </TestWrapper>
      );

      expect(screen.getByTestId('theme-toggle')).toBeInTheDocument();
    });

    it('has correct aria-label for dark mode', () => {
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);

      render(
        <TestWrapper>
          <ThemeToggle />
        </TestWrapper>
      );

      expect(screen.getByTestId('theme-toggle')).toHaveAttribute(
        'aria-label',
        'Switch to light theme'
      );
    });

    it('has correct aria-label for light mode', () => {
      mockedUseLocalStorage.mockReturnValue(['light', mockSetMode]);

      render(
        <TestWrapper>
          <ThemeToggle />
        </TestWrapper>
      );

      expect(screen.getByTestId('theme-toggle')).toHaveAttribute(
        'aria-label',
        'Switch to dark theme'
      );
    });

    it('calls toggle when clicked in dark mode', async () => {
      const user = userEvent.setup();
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);

      render(
        <TestWrapper>
          <ThemeToggle />
        </TestWrapper>
      );

      await user.click(screen.getByTestId('theme-toggle'));

      expect(mockSetMode).toHaveBeenCalledWith('light');
    });

    it('calls toggle when clicked in light mode', async () => {
      const user = userEvent.setup();
      mockedUseLocalStorage.mockReturnValue(['light', mockSetMode]);

      render(
        <TestWrapper>
          <ThemeToggle />
        </TestWrapper>
      );

      await user.click(screen.getByTestId('theme-toggle'));

      expect(mockSetMode).toHaveBeenCalledWith('dark');
    });

    it('calls onThemeChange callback when toggling', async () => {
      const user = userEvent.setup();
      const onThemeChange = vi.fn();
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);

      render(
        <TestWrapper>
          <ThemeToggle onThemeChange={onThemeChange} />
        </TestWrapper>
      );

      await user.click(screen.getByTestId('theme-toggle'));

      expect(onThemeChange).toHaveBeenCalledWith('light');
    });
  });

  describe('Menu Mode', () => {
    it('renders menu button with showMenu prop', () => {
      render(
        <TestWrapper>
          <ThemeToggle showMenu />
        </TestWrapper>
      );

      expect(screen.getByTestId('theme-toggle')).toBeInTheDocument();
      expect(screen.getByTestId('theme-toggle')).toHaveAttribute('aria-label', 'Theme options');
    });

    it('opens menu when clicked', async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <ThemeToggle showMenu />
        </TestWrapper>
      );

      await user.click(screen.getByTestId('theme-toggle'));

      await waitFor(() => {
        expect(screen.getByTestId('theme-menu')).toBeInTheDocument();
      });
    });

    it('shows all theme options in menu', async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <ThemeToggle showMenu />
        </TestWrapper>
      );

      await user.click(screen.getByTestId('theme-toggle'));

      await waitFor(() => {
        expect(screen.getByText('Light')).toBeInTheDocument();
        expect(screen.getByText('Dark')).toBeInTheDocument();
        expect(screen.getByText('System')).toBeInTheDocument();
      });
    });

    it('marks current mode as active', async () => {
      const user = userEvent.setup();
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);

      render(
        <TestWrapper>
          <ThemeToggle showMenu />
        </TestWrapper>
      );

      await user.click(screen.getByTestId('theme-toggle'));

      await waitFor(() => {
        const darkButton = screen.getByText('Dark').closest('button');
        expect(darkButton).toHaveAttribute('aria-checked', 'true');
      });
    });

    it('sets mode to light when Light is clicked', async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <ThemeToggle showMenu />
        </TestWrapper>
      );

      await user.click(screen.getByTestId('theme-toggle'));

      await waitFor(() => {
        expect(screen.getByText('Light')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Light'));

      expect(mockSetMode).toHaveBeenCalledWith('light');
    });

    it('sets mode to system when System is clicked', async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <ThemeToggle showMenu />
        </TestWrapper>
      );

      await user.click(screen.getByTestId('theme-toggle'));

      await waitFor(() => {
        expect(screen.getByText('System')).toBeInTheDocument();
      });

      await user.click(screen.getByText('System'));

      expect(mockSetMode).toHaveBeenCalledWith('system');
    });

    it('calls onThemeChange when mode is selected from menu', async () => {
      const user = userEvent.setup();
      const onThemeChange = vi.fn();

      render(
        <TestWrapper>
          <ThemeToggle showMenu onThemeChange={onThemeChange} />
        </TestWrapper>
      );

      await user.click(screen.getByTestId('theme-toggle'));

      await waitFor(() => {
        expect(screen.getByText('Light')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Light'));

      expect(onThemeChange).toHaveBeenCalledWith('light');
    });
  });

  describe('Size Variants', () => {
    it('applies sm size classes', () => {
      render(
        <TestWrapper>
          <ThemeToggle size="sm" />
        </TestWrapper>
      );

      const button = screen.getByTestId('theme-toggle');
      expect(button.className).toContain('h-8');
      expect(button.className).toContain('w-8');
    });

    it('applies md size classes by default', () => {
      render(
        <TestWrapper>
          <ThemeToggle />
        </TestWrapper>
      );

      const button = screen.getByTestId('theme-toggle');
      expect(button.className).toContain('h-9');
      expect(button.className).toContain('w-9');
    });

    it('applies lg size classes', () => {
      render(
        <TestWrapper>
          <ThemeToggle size="lg" />
        </TestWrapper>
      );

      const button = screen.getByTestId('theme-toggle');
      expect(button.className).toContain('h-10');
      expect(button.className).toContain('w-10');
    });
  });

  describe('Style Variants', () => {
    it('applies default variant classes', () => {
      render(
        <TestWrapper>
          <ThemeToggle variant="default" />
        </TestWrapper>
      );

      const button = screen.getByTestId('theme-toggle');
      expect(button.className).toContain('bg-gray-800');
      expect(button.className).toContain('border');
    });

    it('applies ghost variant classes', () => {
      render(
        <TestWrapper>
          <ThemeToggle variant="ghost" />
        </TestWrapper>
      );

      const button = screen.getByTestId('theme-toggle');
      expect(button.className).toContain('hover:bg-gray-800');
      expect(button.className).not.toContain('border');
    });
  });

  describe('Custom className', () => {
    it('applies custom className', () => {
      render(
        <TestWrapper>
          <ThemeToggle className="custom-class" />
        </TestWrapper>
      );

      const button = screen.getByTestId('theme-toggle');
      expect(button.className).toContain('custom-class');
    });
  });

  describe('Icon Display', () => {
    it('shows moon icon in dark mode', () => {
      mockedUseLocalStorage.mockReturnValue(['dark', mockSetMode]);

      render(
        <TestWrapper>
          <ThemeToggle />
        </TestWrapper>
      );

      // Moon icon should be present (lucide icons render as SVG)
      const button = screen.getByTestId('theme-toggle');
      const svg = button.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });

    it('shows sun icon in light mode', () => {
      mockedUseLocalStorage.mockReturnValue(['light', mockSetMode]);

      render(
        <TestWrapper>
          <ThemeToggle />
        </TestWrapper>
      );

      // Sun icon should be present
      const button = screen.getByTestId('theme-toggle');
      const svg = button.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });

    it('shows monitor icon in system mode', () => {
      mockedUseLocalStorage.mockReturnValue(['system', mockSetMode]);

      render(
        <TestWrapper>
          <ThemeToggle />
        </TestWrapper>
      );

      // Monitor icon should be present
      const button = screen.getByTestId('theme-toggle');
      const svg = button.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });
  });
});
