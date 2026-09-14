import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import AmbientStatusSettings from './AmbientStatusSettings';
import { useDesktopNotifications } from '../../hooks/useDesktopNotifications';
import { useSettings } from '../../hooks/useSettings';

// Default mock values
const defaultSettingsReturnValue = {
  ambientEnabled: true,
  setAmbientEnabled: vi.fn(),
  audioEnabled: true,
  setAudioEnabled: vi.fn(),
  audioVolume: 0.5,
  setAudioVolume: vi.fn(),
  desktopNotificationsEnabled: true,
  setDesktopNotificationsEnabled: vi.fn(),
  suppressNotificationsWhenFocused: false,
  setSuppressNotificationsWhenFocused: vi.fn(),
  faviconBadgeEnabled: true,
  setFaviconBadgeEnabled: vi.fn(),
  enableAllAmbientStatus: vi.fn(),
  disableAllAmbientStatus: vi.fn(),
  // Additional required properties from UseSettingsReturn
  settings: {
    ambientStatus: {
      ambient: { enabled: true },
      audio: { enabled: true, volume: 0.5 },
      desktopNotifications: { enabled: true, suppressWhenFocused: false },
      favicon: { enabled: true },
    },
  },
  updateSettings: vi.fn(),
  resetSettings: vi.fn(),
};

const defaultNotificationsReturnValue = {
  permission: 'default' as NotificationPermission,
  hasPermission: false,
  isDenied: false,
  isSupported: true,
  requestPermission: vi.fn().mockResolvedValue('granted'),
  // Additional required properties from UseDesktopNotificationsReturn
  isEnabled: true,
  setEnabled: vi.fn(),
  showNotification: vi.fn(),
  showSecurityAlert: vi.fn(),
  closeAll: vi.fn(),
};

// Mock the hooks
vi.mock('../../hooks/useSettings', () => ({
  useSettings: vi.fn(() => ({ ...defaultSettingsReturnValue })),
}));

vi.mock('../../hooks/useDesktopNotifications', () => ({
  useDesktopNotifications: vi.fn(() => ({ ...defaultNotificationsReturnValue })),
}));

describe('AmbientStatusSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset mocks to default values
    vi.mocked(useSettings).mockReturnValue({ ...defaultSettingsReturnValue });
    vi.mocked(useDesktopNotifications).mockReturnValue({ ...defaultNotificationsReturnValue });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders all setting sections', () => {
      render(<AmbientStatusSettings />);

      expect(screen.getByText('Ambient Status Awareness')).toBeInTheDocument();
      expect(screen.getByText('Ambient Background')).toBeInTheDocument();
      expect(screen.getByText('Audio Alerts')).toBeInTheDocument();
      expect(screen.getByText('Desktop Notifications')).toBeInTheDocument();
      expect(screen.getByText('Favicon Badge')).toBeInTheDocument();
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

      // Tremor's Switch renders a button with role="switch" inside the container
      const switches = screen.getAllByRole('switch');
      // First switch is ambient background
      fireEvent.click(switches[0]);

      expect(mockSetAmbientEnabled).toHaveBeenCalled();
    });
  });

  describe('audio settings', () => {
    it('calls setAudioEnabled when toggled', () => {
      const mockSetAudioEnabled = vi.fn();
      vi.mocked(useSettings).mockReturnValue({
        ...defaultSettingsReturnValue,
        setAudioEnabled: mockSetAudioEnabled,
      });

      render(<AmbientStatusSettings />);

      // Tremor's Switch renders a button with role="switch" inside the container
      const switches = screen.getAllByRole('switch');
      // Second switch is audio
      fireEvent.click(switches[1]);

      expect(mockSetAudioEnabled).toHaveBeenCalled();
    });

    it('shows volume slider when audio is enabled', () => {
      vi.mocked(useSettings).mockReturnValue({
        ...defaultSettingsReturnValue,
        audioEnabled: true,
      });

      render(<AmbientStatusSettings />);

      expect(screen.getByLabelText('Audio volume')).toBeInTheDocument();
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('hides volume slider when audio is disabled', () => {
      vi.mocked(useSettings).mockReturnValue({
        ...defaultSettingsReturnValue,
        audioEnabled: false,
      });

      render(<AmbientStatusSettings />);

      expect(screen.queryByLabelText('Audio volume')).not.toBeInTheDocument();
    });

    it('calls setAudioVolume when slider changes', () => {
      const mockSetAudioVolume = vi.fn();
      vi.mocked(useSettings).mockReturnValue({
        ...defaultSettingsReturnValue,
        audioEnabled: true,
        setAudioVolume: mockSetAudioVolume,
      });

      render(<AmbientStatusSettings />);

      const slider = screen.getByLabelText('Audio volume');
      fireEvent.change(slider, { target: { value: '0.8' } });

      expect(mockSetAudioVolume).toHaveBeenCalledWith(0.8);
    });
  });

  describe('desktop notification settings', () => {
    it('shows permission request button when not granted', () => {
      vi.mocked(useDesktopNotifications).mockReturnValue({
        ...defaultNotificationsReturnValue,
        permission: 'default',
        hasPermission: false,
        isDenied: false,
      });

      render(<AmbientStatusSettings />);

      expect(screen.getByText('Request Permission')).toBeInTheDocument();
    });

    it('hides permission request button when granted', () => {
      vi.mocked(useDesktopNotifications).mockReturnValue({
        ...defaultNotificationsReturnValue,
        permission: 'granted',
        hasPermission: true,
        isDenied: false,
      });

      render(<AmbientStatusSettings />);

      expect(screen.queryByText('Request Permission')).not.toBeInTheDocument();
    });

    it('shows blocked warning when permission is denied', () => {
      vi.mocked(useDesktopNotifications).mockReturnValue({
        ...defaultNotificationsReturnValue,
        permission: 'denied',
        hasPermission: false,
        isDenied: true,
      });

      render(<AmbientStatusSettings />);

      expect(
        screen.getByText(/Notifications are blocked. Please enable them in your browser settings/)
      ).toBeInTheDocument();
    });

    it('shows not supported badge when notifications are not supported', () => {
      vi.mocked(useDesktopNotifications).mockReturnValue({
        ...defaultNotificationsReturnValue,
        isSupported: false,
      });

      render(<AmbientStatusSettings />);

      expect(screen.getByText('Not Supported')).toBeInTheDocument();
    });

    it('shows suppress when focused option when permission is granted', () => {
      vi.mocked(useDesktopNotifications).mockReturnValue({
        ...defaultNotificationsReturnValue,
        permission: 'granted',
        hasPermission: true,
      });

      render(<AmbientStatusSettings />);

      expect(screen.getByText('Suppress when focused')).toBeInTheDocument();
    });

    it('calls requestPermission when button is clicked', async () => {
      const mockRequestPermission = vi.fn().mockResolvedValue('granted');
      vi.mocked(useDesktopNotifications).mockReturnValue({
        ...defaultNotificationsReturnValue,
        requestPermission: mockRequestPermission,
      });

      render(<AmbientStatusSettings />);

      const button = screen.getByText('Request Permission');
      fireEvent.click(button);

      await waitFor(() => {
        expect(mockRequestPermission).toHaveBeenCalled();
      });
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

      // Tremor's Switch renders a button with role="switch" inside the container
      const switches = screen.getAllByRole('switch');
      // Fourth switch is favicon (after ambient, audio, desktop notifications)
      fireEvent.click(switches[3]);

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

  describe('permission badges', () => {
    it('shows Granted badge when permission is granted', () => {
      vi.mocked(useDesktopNotifications).mockReturnValue({
        ...defaultNotificationsReturnValue,
        permission: 'granted',
        hasPermission: true,
        isDenied: false,
      });

      render(<AmbientStatusSettings />);

      expect(screen.getByText('Granted')).toBeInTheDocument();
    });

    it('shows Blocked badge when permission is denied', () => {
      vi.mocked(useDesktopNotifications).mockReturnValue({
        ...defaultNotificationsReturnValue,
        permission: 'denied',
        hasPermission: false,
        isDenied: true,
      });

      render(<AmbientStatusSettings />);

      expect(screen.getByText('Blocked')).toBeInTheDocument();
    });

    it('shows Not Set badge when permission is default', () => {
      vi.mocked(useDesktopNotifications).mockReturnValue({
        ...defaultNotificationsReturnValue,
        permission: 'default',
        hasPermission: false,
        isDenied: false,
      });

      render(<AmbientStatusSettings />);

      expect(screen.getByText('Not Set')).toBeInTheDocument();
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
