/**
 * SettingsPage Tests
 *
 * Tests for the Settings page with nested route-based navigation.
 *
 * @see NEM-4938 - Convert Settings page to nested sub-routes
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route, Navigate } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';

import SettingsPage from './SettingsPage';
import { settingsTabs } from './settingsTabsConfig';

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

vi.mock('./AccessControlSettings', () => ({
  default: () => <div data-testid="access-control-settings">Access Control Settings</div>,
}));

vi.mock('./prompts', () => ({
  PromptManagementPage: () => <div data-testid="prompt-management">Prompt Management</div>,
}));

vi.mock('../system/FileOperationsPanel', () => ({
  default: () => <div data-testid="file-operations-panel">File Operations Panel</div>,
}));

vi.mock('./AIModelsTab', () => ({
  default: () => <div data-testid="ai-models-tab">AI Models Tab</div>,
}));

vi.mock('./AdminSettings', () => ({
  default: () => <div data-testid="admin-settings">Admin Settings</div>,
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

// Helper to render with all required providers and routing
interface RenderOptions {
  route?: string;
}

function renderWithProviders(ui: React.ReactElement, options: RenderOptions = {}) {
  const { route = '/settings/cameras' } = options;
  const queryClient = createTestQueryClient();
  const user = userEvent.setup();

  return {
    user,
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path="/settings" element={ui}>
              <Route index element={<Navigate to="cameras" replace />} />
              <Route
                path="cameras"
                element={<div data-testid="cameras-settings">Cameras Settings</div>}
              />
              <Route
                path="rules"
                element={<div data-testid="alert-rules-settings">Alert Rules Settings</div>}
              />
              <Route
                path="processing"
                element={<div data-testid="processing-settings">Processing Settings</div>}
              />
              <Route
                path="notifications"
                element={<div data-testid="notification-settings">Notification Settings</div>}
              />
              <Route
                path="ambient"
                element={<div data-testid="ambient-settings">Ambient Status Settings</div>}
              />
              <Route
                path="calibration"
                element={<div data-testid="calibration-panel">Calibration Panel</div>}
              />
              <Route
                path="access"
                element={<div data-testid="access-control-settings">Access Control Settings</div>}
              />
              <Route
                path="prompts"
                element={<div data-testid="prompt-management">Prompt Management</div>}
              />
              <Route
                path="storage"
                element={<div data-testid="file-operations-panel">File Operations Panel</div>}
              />
              <Route
                path="ai-models"
                element={<div data-testid="ai-models-tab">AI Models Tab</div>}
              />
              <Route
                path="admin"
                element={<div data-testid="admin-settings">Admin Settings</div>}
              />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    ),
  };
}

describe('SettingsPage', () => {
  describe('settingsTabs configuration', () => {
    it('should export all 11 settings tabs', () => {
      expect(settingsTabs).toHaveLength(11);
    });

    it('should have correct tab IDs', () => {
      const tabIds = settingsTabs.map((tab) => tab.id);
      expect(tabIds).toEqual([
        'cameras',
        'rules',
        'processing',
        'notifications',
        'ambient',
        'calibration',
        'access',
        'prompts',
        'storage',
        'ai-models',
        'admin',
      ]);
    });

    it('should have correct paths for each tab', () => {
      const paths = settingsTabs.map((tab) => tab.path);
      expect(paths).toEqual([
        '/settings/cameras',
        '/settings/rules',
        '/settings/processing',
        '/settings/notifications',
        '/settings/ambient',
        '/settings/calibration',
        '/settings/access',
        '/settings/prompts',
        '/settings/storage',
        '/settings/ai-models',
        '/settings/admin',
      ]);
    });

    it('should have descriptions for all tabs', () => {
      settingsTabs.forEach((tab) => {
        expect(tab.description).toBeDefined();
        expect(tab.description.length).toBeGreaterThan(0);
      });
    });
  });

  describe('rendering', () => {
    it('should render the page title and description', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByText('Settings')).toBeInTheDocument();
      expect(screen.getByText('Configure your security monitoring system')).toBeInTheDocument();
    });

    it('should render all navigation tabs', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByTestId('settings-tab-cameras')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-rules')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-processing')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-notifications')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-ambient')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-calibration')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-access')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-prompts')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-storage')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-ai-models')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-admin')).toBeInTheDocument();
    });

    it('should render content panel', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByTestId('settings-content-panel')).toBeInTheDocument();
    });

    it('should show cameras settings content by default', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByTestId('cameras-settings')).toBeInTheDocument();
    });
  });

  describe('navigation', () => {
    it('should navigate to rules settings when rules tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      const rulesTab = screen.getByTestId('settings-tab-rules');
      await user.click(rulesTab);

      await waitFor(() => {
        expect(screen.getByTestId('alert-rules-settings')).toBeInTheDocument();
      });
    });

    it('should navigate to processing settings when processing tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      const processingTab = screen.getByTestId('settings-tab-processing');
      await user.click(processingTab);

      await waitFor(() => {
        expect(screen.getByTestId('processing-settings')).toBeInTheDocument();
      });
    });

    it('should navigate to notification settings when notifications tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      const notificationsTab = screen.getByTestId('settings-tab-notifications');
      await user.click(notificationsTab);

      await waitFor(() => {
        expect(screen.getByTestId('notification-settings')).toBeInTheDocument();
      });
    });

    it('should navigate to calibration panel when calibration tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      const calibrationTab = screen.getByTestId('settings-tab-calibration');
      await user.click(calibrationTab);

      await waitFor(() => {
        expect(screen.getByTestId('calibration-panel')).toBeInTheDocument();
      });
    });

    it('should navigate to ambient settings when ambient tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      const ambientTab = screen.getByTestId('settings-tab-ambient');
      await user.click(ambientTab);

      await waitFor(() => {
        expect(screen.getByTestId('ambient-settings')).toBeInTheDocument();
      });
    });

    it('should navigate to storage settings when storage tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      const storageTab = screen.getByTestId('settings-tab-storage');
      await user.click(storageTab);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });
    });

    it('should navigate to AI models tab when AI models tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      const aiModelsTab = screen.getByTestId('settings-tab-ai-models');
      await user.click(aiModelsTab);

      await waitFor(() => {
        expect(screen.getByTestId('ai-models-tab')).toBeInTheDocument();
      });
    });

    it('should navigate to admin settings when admin tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      const adminTab = screen.getByTestId('settings-tab-admin');
      await user.click(adminTab);

      await waitFor(() => {
        expect(screen.getByTestId('admin-settings')).toBeInTheDocument();
      });
    });

    it('should navigate to access settings when access tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      const accessTab = screen.getByTestId('settings-tab-access');
      await user.click(accessTab);

      await waitFor(() => {
        expect(screen.getByTestId('access-control-settings')).toBeInTheDocument();
      });
    });

    it('should navigate to prompts settings when prompts tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      const promptsTab = screen.getByTestId('settings-tab-prompts');
      await user.click(promptsTab);

      await waitFor(() => {
        expect(screen.getByTestId('prompt-management')).toBeInTheDocument();
      });
    });
  });

  describe('active state styling', () => {
    it('should highlight the cameras tab when on cameras route', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/cameras' });

      const camerasTab = screen.getByTestId('settings-tab-cameras');
      expect(camerasTab).toHaveAttribute('aria-selected', 'true');
      expect(camerasTab).toHaveClass('bg-[#76B900]');
    });

    it('should highlight the rules tab when on rules route', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/rules' });

      const rulesTab = screen.getByTestId('settings-tab-rules');
      expect(rulesTab).toHaveAttribute('aria-selected', 'true');
      expect(rulesTab).toHaveClass('bg-[#76B900]');
    });

    it('should highlight the admin tab when on admin route', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/admin' });

      const adminTab = screen.getByTestId('settings-tab-admin');
      expect(adminTab).toHaveAttribute('aria-selected', 'true');
      expect(adminTab).toHaveClass('bg-[#76B900]');
    });

    it('should not highlight inactive tabs', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/cameras' });

      const rulesTab = screen.getByTestId('settings-tab-rules');
      expect(rulesTab).toHaveAttribute('aria-selected', 'false');
      expect(rulesTab).not.toHaveClass('bg-[#76B900]');
    });
  });

  describe('tab descriptions', () => {
    it('should have title attribute with description on cameras tab', () => {
      renderWithProviders(<SettingsPage />);

      const camerasTab = screen.getByTestId('settings-tab-cameras');
      expect(camerasTab).toHaveAttribute('title', 'Add, remove, and configure security cameras');
    });

    it('should have title attribute with description on rules tab', () => {
      renderWithProviders(<SettingsPage />);

      const rulesTab = screen.getByTestId('settings-tab-rules');
      expect(rulesTab).toHaveAttribute('title', 'Set up automated alert rules and triggers');
    });

    it('should have title attribute with description on processing tab', () => {
      renderWithProviders(<SettingsPage />);

      const processingTab = screen.getByTestId('settings-tab-processing');
      expect(processingTab).toHaveAttribute(
        'title',
        'Configure detection sensitivity and AI models'
      );
    });

    it('should have title attribute with description on notifications tab', () => {
      renderWithProviders(<SettingsPage />);

      const notificationsTab = screen.getByTestId('settings-tab-notifications');
      expect(notificationsTab).toHaveAttribute(
        'title',
        'Email, push, and webhook notification settings'
      );
    });

    it('should have title attribute with description on ambient tab', () => {
      renderWithProviders(<SettingsPage />);

      const ambientTab = screen.getByTestId('settings-tab-ambient');
      expect(ambientTab).toHaveAttribute('title', 'Background noise and environmental settings');
    });

    it('should have title attribute with description on storage tab', () => {
      renderWithProviders(<SettingsPage />);

      const storageTab = screen.getByTestId('settings-tab-storage');
      expect(storageTab).toHaveAttribute('title', 'Media retention and storage management');
    });

    it('should have title attribute with description on ai-models tab', () => {
      renderWithProviders(<SettingsPage />);

      const aiModelsTab = screen.getByTestId('settings-tab-ai-models');
      expect(aiModelsTab).toHaveAttribute('title', 'View status and performance of all AI models');
    });

    it('should have title attribute with description on admin tab', () => {
      renderWithProviders(<SettingsPage />);

      const adminTab = screen.getByTestId('settings-tab-admin');
      expect(adminTab).toHaveAttribute(
        'title',
        'Feature toggles, system config, and maintenance actions'
      );
    });
  });

  describe('accessibility', () => {
    it('should have role="tablist" on navigation', () => {
      renderWithProviders(<SettingsPage />);

      const tablist = screen.getByRole('tablist');
      expect(tablist).toBeInTheDocument();
      expect(tablist).toHaveAttribute('aria-label', 'Settings sections');
    });

    it('should have role="tab" on all navigation items', () => {
      renderWithProviders(<SettingsPage />);

      const tabs = screen.getAllByRole('tab');
      expect(tabs).toHaveLength(11);
    });

    it('should have role="tabpanel" on content panel', () => {
      renderWithProviders(<SettingsPage />);

      const panel = screen.getByRole('tabpanel');
      expect(panel).toBeInTheDocument();
    });

    it('should have aria-controls linking tab to panel', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/cameras' });

      const camerasTab = screen.getByTestId('settings-tab-cameras');
      expect(camerasTab).toHaveAttribute('aria-controls', 'settings-panel-cameras');
    });
  });

  describe('direct URL navigation', () => {
    it('should show rules settings when navigating directly to /settings/rules', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/rules' });

      expect(screen.getByTestId('alert-rules-settings')).toBeInTheDocument();
    });

    it('should show admin settings when navigating directly to /settings/admin', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/admin' });

      expect(screen.getByTestId('admin-settings')).toBeInTheDocument();
    });

    it('should show ai-models settings when navigating directly to /settings/ai-models', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/ai-models' });

      expect(screen.getByTestId('ai-models-tab')).toBeInTheDocument();
    });

    it('should show prompts settings when navigating directly to /settings/prompts', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/prompts' });

      expect(screen.getByTestId('prompt-management')).toBeInTheDocument();
    });
  });

});
