import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import SettingsPage from './SettingsPage';

// Mock the settings components
vi.mock('./CamerasSettings', () => ({
  default: () => <div data-testid="cameras-settings">Cameras Settings</div>,
}));

vi.mock('./ProcessingSettings', () => ({
  default: () => <div data-testid="processing-settings">Processing Settings</div>,
}));

vi.mock('./AIModelsSettings', () => ({
  default: () => <div data-testid="ai-models-settings">AI Models Settings</div>,
}));

describe('SettingsPage', () => {
  it('should render the page title and description', () => {
    render(<SettingsPage />);

    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(
      screen.getByText('Configure your security monitoring system')
    ).toBeInTheDocument();
  });

  it('should render all three tabs', () => {
    render(<SettingsPage />);

    expect(screen.getByRole('tab', { name: /cameras/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /processing/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /ai models/i })).toBeInTheDocument();
  });

  it('should show cameras settings by default', () => {
    render(<SettingsPage />);

    expect(screen.getByTestId('cameras-settings')).toBeInTheDocument();
  });

  it('should switch to processing settings when tab is clicked', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    const processingTab = screen.getByRole('tab', { name: /processing/i });
    await user.click(processingTab);

    expect(screen.getByTestId('processing-settings')).toBeInTheDocument();
    expect(screen.queryByTestId('cameras-settings')).not.toBeInTheDocument();
  });

  it('should switch to ai models settings when tab is clicked', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    const aiModelsTab = screen.getByRole('tab', { name: /ai models/i });
    await user.click(aiModelsTab);

    expect(screen.getByTestId('ai-models-settings')).toBeInTheDocument();
    expect(screen.queryByTestId('cameras-settings')).not.toBeInTheDocument();
  });

  it('should highlight the selected tab', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    const camerasTab = screen.getByRole('tab', { name: /cameras/i });
    const processingTab = screen.getByRole('tab', { name: /processing/i });

    // First tab should be selected by default (Headless UI handles aria-selected)
    expect(camerasTab).toHaveAttribute('data-headlessui-state', 'selected');

    // Click processing tab
    await user.click(processingTab);

    // Processing tab should now be selected
    expect(processingTab).toHaveAttribute('data-headlessui-state', 'selected');
  });

  it('should support keyboard navigation between tabs', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    const camerasTab = screen.getByRole('tab', { name: /cameras/i });

    // Focus on the first tab
    camerasTab.focus();
    expect(camerasTab).toHaveFocus();

    // Press arrow right to move to next tab
    await user.keyboard('{ArrowRight}');

    const processingTab = screen.getByRole('tab', { name: /processing/i });
    expect(processingTab).toHaveFocus();
  });

  it('should cycle tabs with arrow keys', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    const camerasTab = screen.getByRole('tab', { name: /cameras/i });
    const aiModelsTab = screen.getByRole('tab', { name: /ai models/i });

    // Focus on the last tab
    aiModelsTab.focus();
    expect(aiModelsTab).toHaveFocus();

    // Press arrow right to cycle to first tab
    await user.keyboard('{ArrowRight}');
    expect(camerasTab).toHaveFocus();
  });
});
