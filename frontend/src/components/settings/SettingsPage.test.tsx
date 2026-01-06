import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import SettingsPage from './SettingsPage';

// Mock the settings components
vi.mock('./CamerasSettings', () => ({
  default: () => <div data-testid="cameras-settings">Cameras Settings</div>,
}));

vi.mock('./AlertRulesSettings', () => ({
  default: () => <div data-testid="alert-rules-settings">Alert Rules Settings</div>,
}));

vi.mock('./ProcessingSettings', () => ({
  default: () => <div data-testid="processing-settings">Processing Settings</div>,
}));

vi.mock('./NotificationSettings', () => ({
  default: () => <div data-testid="notification-settings">Notification Settings</div>,
}));

describe('SettingsPage', () => {
  it('should render the page title and description', () => {
    render(<SettingsPage />);

    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByText('Configure your security monitoring system')).toBeInTheDocument();
  });

  it('should render all four tabs', () => {
    render(<SettingsPage />);

    expect(screen.getByRole('tab', { name: /cameras/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /rules/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /processing/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /notifications/i })).toBeInTheDocument();
  });

  it('should show cameras settings by default', () => {
    render(<SettingsPage />);

    expect(screen.getByTestId('cameras-settings')).toBeInTheDocument();
  });

  it('should switch to rules settings when tab is clicked', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    const rulesTab = screen.getByRole('tab', { name: /rules/i });
    await user.click(rulesTab);

    expect(screen.getByTestId('alert-rules-settings')).toBeInTheDocument();
    expect(screen.queryByTestId('cameras-settings')).not.toBeInTheDocument();
  });

  it('should switch to processing settings when tab is clicked', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    const processingTab = screen.getByRole('tab', { name: /processing/i });
    await user.click(processingTab);

    expect(screen.getByTestId('processing-settings')).toBeInTheDocument();
    expect(screen.queryByTestId('cameras-settings')).not.toBeInTheDocument();
  });

  it('should highlight the selected tab', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    const camerasTab = screen.getByRole('tab', { name: /cameras/i });
    const processingTab = screen.getByRole('tab', { name: /processing/i });

    // First tab should be selected by default (Headless UI handles aria-selected)
    // Note: headlessui 2.x may include additional states like "hover" in the attribute
    expect(camerasTab.getAttribute('data-headlessui-state')).toMatch(/selected/);

    // Click processing tab
    await user.click(processingTab);

    // Processing tab should now be selected
    expect(processingTab.getAttribute('data-headlessui-state')).toMatch(/selected/);
  });

  it('should support keyboard navigation between tabs', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    const camerasTab = screen.getByRole('tab', { name: /cameras/i });

    // Focus on the first tab
    camerasTab.focus();
    expect(camerasTab).toHaveFocus();

    // Press arrow right to move to next tab (RULES is now second)
    await user.keyboard('{ArrowRight}');

    const rulesTab = screen.getByRole('tab', { name: /rules/i });
    expect(rulesTab).toHaveFocus();
  });

  it('should cycle tabs with arrow keys', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    const camerasTab = screen.getByRole('tab', { name: /cameras/i });
    const notificationsTab = screen.getByRole('tab', { name: /notifications/i });

    // Focus on the last tab (notifications is now last)
    notificationsTab.focus();
    expect(notificationsTab).toHaveFocus();

    // Press arrow right to cycle to first tab
    await user.keyboard('{ArrowRight}');
    expect(camerasTab).toHaveFocus();
  });

  it('should switch to notification settings when tab is clicked', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    const notificationsTab = screen.getByRole('tab', { name: /notifications/i });
    await user.click(notificationsTab);

    expect(screen.getByTestId('notification-settings')).toBeInTheDocument();
    expect(screen.queryByTestId('cameras-settings')).not.toBeInTheDocument();
  });
});
