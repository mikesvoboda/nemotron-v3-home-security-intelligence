import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import SettingsPage from './SettingsPage';
import { server } from '../../mocks/server';

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

vi.mock('./AmbientStatusSettings', () => ({
  default: () => <div data-testid="ambient-settings">Ambient Status Settings</div>,
}));

vi.mock('./CalibrationPanel', () => ({
  default: () => <div data-testid="calibration-panel">Calibration Panel</div>,
}));

vi.mock('./PromptManagementPanel', () => ({
  default: () => <div data-testid="prompt-management">Prompt Management</div>,
}));

vi.mock('../system/FileOperationsPanel', () => ({
  default: () => <div data-testid="file-operations-panel">File Operations Panel</div>,
}));

vi.mock('./AIModelsTab', () => ({
  default: () => <div data-testid="ai-models-tab">AI Models Tab</div>,
}));

// Helper to create a fresh QueryClient for each test
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
}

// Helper to render with all required providers
function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('SettingsPage', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('should render the page title and description', () => {
    renderWithProviders(<SettingsPage />);

    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByText('Configure your security monitoring system')).toBeInTheDocument();
  });

  it('should render all nine tabs', () => {
    renderWithProviders(<SettingsPage />);

    expect(screen.getByRole('tab', { name: /cameras/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /rules/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /processing/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /notifications/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /ambient/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /calibration/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /prompts/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /storage/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /ai models/i })).toBeInTheDocument();
  });

  it('should show cameras settings by default', () => {
    renderWithProviders(<SettingsPage />);

    expect(screen.getByTestId('cameras-settings')).toBeInTheDocument();
  });

  it('should switch to rules settings when tab is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    const rulesTab = screen.getByRole('tab', { name: /rules/i });
    await user.click(rulesTab);

    expect(screen.getByTestId('alert-rules-settings')).toBeInTheDocument();
    expect(screen.queryByTestId('cameras-settings')).not.toBeInTheDocument();
  });

  it('should switch to processing settings when tab is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    const processingTab = screen.getByRole('tab', { name: /processing/i });
    await user.click(processingTab);

    expect(screen.getByTestId('processing-settings')).toBeInTheDocument();
    expect(screen.queryByTestId('cameras-settings')).not.toBeInTheDocument();
  });

  it('should highlight the selected tab', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

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
    renderWithProviders(<SettingsPage />);

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
    renderWithProviders(<SettingsPage />);

    const camerasTab = screen.getByRole('tab', { name: /cameras/i });
    const aiModelsTab = screen.getByRole('tab', { name: /ai models/i });

    // Focus on the last tab (AI MODELS is now last)
    aiModelsTab.focus();
    expect(aiModelsTab).toHaveFocus();

    // Press arrow right to cycle to first tab
    await user.keyboard('{ArrowRight}');
    expect(camerasTab).toHaveFocus();
  });

  it('should switch to notification settings when tab is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    const notificationsTab = screen.getByRole('tab', { name: /notifications/i });
    await user.click(notificationsTab);

    expect(screen.getByTestId('notification-settings')).toBeInTheDocument();
    expect(screen.queryByTestId('cameras-settings')).not.toBeInTheDocument();
  });

  it('should switch to calibration panel when tab is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    const calibrationTab = screen.getByRole('tab', { name: /calibration/i });
    await user.click(calibrationTab);

    expect(screen.getByTestId('calibration-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('cameras-settings')).not.toBeInTheDocument();
  });

  it('should switch to ambient settings when tab is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    const ambientTab = screen.getByRole('tab', { name: /ambient/i });
    await user.click(ambientTab);

    expect(screen.getByTestId('ambient-settings')).toBeInTheDocument();
    expect(screen.queryByTestId('cameras-settings')).not.toBeInTheDocument();
  });

  it('should switch to storage settings when tab is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    const storageTab = screen.getByRole('tab', { name: /storage/i });
    await user.click(storageTab);

    expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('cameras-settings')).not.toBeInTheDocument();
  });

  it('should switch to AI models tab when tab is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    const aiModelsTab = screen.getByRole('tab', { name: /ai models/i });
    await user.click(aiModelsTab);

    expect(screen.getByTestId('ai-models-tab')).toBeInTheDocument();
    expect(screen.queryByTestId('cameras-settings')).not.toBeInTheDocument();
  });

  describe('Tab descriptions', () => {
    it('should have title attribute with description on cameras tab', () => {
      renderWithProviders(<SettingsPage />);

      const camerasTab = screen.getByRole('tab', { name: /cameras/i });
      expect(camerasTab).toHaveAttribute('title', 'Add, remove, and configure security cameras');
    });

    it('should have title attribute with description on rules tab', () => {
      renderWithProviders(<SettingsPage />);

      const rulesTab = screen.getByRole('tab', { name: /rules/i });
      expect(rulesTab).toHaveAttribute('title', 'Set up automated alert rules and triggers');
    });

    it('should have title attribute with description on processing tab', () => {
      renderWithProviders(<SettingsPage />);

      const processingTab = screen.getByRole('tab', { name: /processing/i });
      expect(processingTab).toHaveAttribute(
        'title',
        'Configure detection sensitivity and AI models'
      );
    });

    it('should have title attribute with description on notifications tab', () => {
      renderWithProviders(<SettingsPage />);

      const notificationsTab = screen.getByRole('tab', { name: /notifications/i });
      expect(notificationsTab).toHaveAttribute(
        'title',
        'Email, push, and webhook notification settings'
      );
    });

    it('should have title attribute with description on ambient tab', () => {
      renderWithProviders(<SettingsPage />);

      const ambientTab = screen.getByRole('tab', { name: /ambient/i });
      expect(ambientTab).toHaveAttribute(
        'title',
        'Background noise and environmental settings'
      );
    });

    it('should have title attribute with description on storage tab', () => {
      renderWithProviders(<SettingsPage />);

      const storageTab = screen.getByRole('tab', { name: /storage/i });
      expect(storageTab).toHaveAttribute('title', 'Media retention and storage management');
    });

    it('should have title attribute with description on ai-models tab', () => {
      renderWithProviders(<SettingsPage />);

      const aiModelsTab = screen.getByRole('tab', { name: /ai models/i });
      expect(aiModelsTab).toHaveAttribute(
        'title',
        'View status and performance of all AI models'
      );
    });
  });

  describe('Developer Tools link', () => {
    it('should show Developer Tools link when debug mode is enabled', async () => {
      server.use(
        http.get('/api/system/config', () => {
          return HttpResponse.json({
            app_name: 'Home Security Intelligence',
            version: '0.1.0',
            retention_days: 30,
            batch_window_seconds: 90,
            batch_idle_timeout_seconds: 30,
            detection_confidence_threshold: 0.5,
            grafana_url: 'http://localhost:3002',
            debug: true,
          });
        })
      );

      renderWithProviders(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('dev-tools-link')).toBeInTheDocument();
      });

      const link = screen.getByTestId('dev-tools-link');
      expect(link).toHaveAttribute('href', '/dev-tools');
      expect(link).toHaveTextContent('Developer Tools');
    });

    it('should not show Developer Tools link when debug mode is disabled', async () => {
      server.use(
        http.get('/api/system/config', () => {
          return HttpResponse.json({
            app_name: 'Home Security Intelligence',
            version: '0.1.0',
            retention_days: 30,
            batch_window_seconds: 90,
            batch_idle_timeout_seconds: 30,
            detection_confidence_threshold: 0.5,
            grafana_url: 'http://localhost:3002',
            debug: false,
          });
        })
      );

      renderWithProviders(<SettingsPage />);

      // Wait for query to complete
      await waitFor(() => {
        expect(screen.getByTestId('settings-page')).toBeInTheDocument();
      });

      // Give it a moment to render based on config
      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(screen.queryByTestId('dev-tools-link')).not.toBeInTheDocument();
    });
  });
});
