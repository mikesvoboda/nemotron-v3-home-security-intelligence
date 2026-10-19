import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import AmbientStatusSettings from './AmbientStatusSettings';
import { useSettings } from '../../hooks/useSettings';

// Default mock values
const defaultSettingsReturnValue = {
  ambientEnabled: true,
  setAmbientEnabled: vi.fn(),
  faviconBadgeEnabled: true,
  setFaviconBadgeEnabled: vi.fn(),
  enableAllAmbientStatus: vi.fn(),
  disableAllAmbientStatus: vi.fn(),
  // Additional required properties from UseSettingsReturn
  settings: {
    ambientStatus: {
      ambient: { enabled: true },
      favicon: { enabled: true },
    },
  },
  updateSettings: vi.fn(),
  resetSettings: vi.fn(),
};

// Mock the hook
vi.mock('../../hooks/useSettings', () => ({
  useSettings: vi.fn(() => ({ ...defaultSettingsReturnValue })),
}));

describe('AmbientStatusSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useSettings).mockReturnValue({ ...defaultSettingsReturnValue });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders ambient background and favicon badge sections without retired audio/desktop sections (F-239)', () => {
      render(<AmbientStatusSettings />);

      expect(screen.getByText('Ambient Status Awareness')).toBeInTheDocument();
      expect(screen.getByText('Ambient Background')).toBeInTheDocument();
      expect(screen.getByText('Favicon Badge')).toBeInTheDocument();
      expect(screen.queryByText('Audio Alerts')).not.toBeInTheDocument();
      expect(screen.queryByText('Desktop Notifications')).not.toBeInTheDocument();
      expect(screen.queryByText('Suppress when focused')).not.toBeInTheDocument();
    });

    it('renders enable/disable all buttons', () => {
      render(<AmbientStatusSettings />);

      expect(screen.getByText('Enable All')).toBeInTheDocument();
      expect(screen.getByText('Disable All')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<AmbientStatusSettings className="custom-class" />);

      expect(screen.getByTestId('ambient-status-settings')).toHaveClass('custom-class');
    });
  });

  describe('ambient background toggle', () => {
    it('calls setAmbientEnabled when toggled', () => {
      const mockSetAmbientEnabled = vi.fn();
      vi.mocked(useSettings).mockReturnValue({
        ...defaultSettingsReturnValue,
        setAmbientEnabled: mockSetAmbientEnabled,
      });

      render(<AmbientStatusSettings />);

      const switches = screen.getAllByRole('switch');
      fireEvent.click(switches[0]);

      expect(mockSetAmbientEnabled).toHaveBeenCalled();
    });
  });

  describe('favicon badge toggle', () => {
    it('calls setFaviconBadgeEnabled when toggled', () => {
      const mockSetFaviconBadgeEnabled = vi.fn();
      vi.mocked(useSettings).mockReturnValue({
        ...defaultSettingsReturnValue,
        setFaviconBadgeEnabled: mockSetFaviconBadgeEnabled,
      });

      render(<AmbientStatusSettings />);

      const switches = screen.getAllByRole('switch');
      fireEvent.click(switches[1]);

      expect(mockSetFaviconBadgeEnabled).toHaveBeenCalled();
    });
  });

  describe('bulk operations', () => {
    it('calls enableAllAmbientStatus when Enable All is clicked', () => {
      const mockEnableAll = vi.fn();
      vi.mocked(useSettings).mockReturnValue({
        ...defaultSettingsReturnValue,
        enableAllAmbientStatus: mockEnableAll,
      });

      render(<AmbientStatusSettings />);

      const button = screen.getByText('Enable All');
      fireEvent.click(button);

      expect(mockEnableAll).toHaveBeenCalled();
    });

    it('calls disableAllAmbientStatus when Disable All is clicked', () => {
      const mockDisableAll = vi.fn();
      vi.mocked(useSettings).mockReturnValue({
        ...defaultSettingsReturnValue,
        disableAllAmbientStatus: mockDisableAll,
      });

      render(<AmbientStatusSettings />);

      const button = screen.getByText('Disable All');
      fireEvent.click(button);

      expect(mockDisableAll).toHaveBeenCalled();
    });
  });

  describe('info note', () => {
    it('shows reduced motion note', () => {
      render(<AmbientStatusSettings />);

      expect(
        screen.getByText(/Ambient features respect your system's reduced motion preferences/)
      ).toBeInTheDocument();
    });
  });
});
