/**
 * SettingsPage Tests (F4.9 — docs/uplevel/4n-modes.md).
 *
 * Tests for the SettingsPage routing shell: its heading comes from `hubForPath`,
 * its tab bar is `HubTabBar`, and its panel is labelled by `HubTabBar`'s active tab.
 */

import { screen, waitFor } from '@testing-library/react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';

import SettingsPage from './SettingsPage';
import { HUBS } from '../../config/surfaces';
import { renderWithNavigation } from '../../test-utils';

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

const settingsHub = HUBS.find((h) => h.id === 'settings')!;

interface RenderOptions {
  route?: string;
}

function renderWithProviders(ui: React.ReactElement, options: RenderOptions = {}) {
  const { route = '/settings/cameras' } = options;

  return renderWithNavigation(
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
        <Route path="ai-models" element={<div data-testid="ai-models-tab">AI Models Tab</div>} />
        <Route path="admin" element={<div data-testid="admin-settings">Admin Settings</div>} />
        <Route path="gpu" element={<div data-testid="gpu-settings">GPU Settings</div>} />
      </Route>
      <Route path="/data" element={<div data-testid="data-page">Data Page</div>} />
      <Route path="/webhooks" element={<div data-testid="webhooks-page">Webhooks Page</div>} />
      <Route path="/audit" element={<div data-testid="audit-page">Audit Page</div>} />
      <Route
        path="/notifications"
        element={<div data-testid="notifications-page">Notification History Page</div>}
      />
    </Routes>,
    { route }
  );
}

describe('SettingsPage', () => {
  describe('Settings hub configuration in surfaces.ts', () => {
    it('defines the 10 Settings hub tabs (Rules, Prompts, AI Models, and Admin moved to their own hubs)', () => {
      expect(settingsHub.tabs).toHaveLength(10);
      expect(settingsHub.tabs.map((t) => t.id)).toEqual([
        'cameras',
        'processing',
        'notifications',
        'ambient',
        'access',
        'storage',
        'data',
        'webhooks',
        'audit',
        'notification-history',
      ]);
    });
  });

  describe('rendering', () => {
    it('renders the hub heading and description', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByRole('heading', { name: 'Settings', level: 1 })).toBeInTheDocument();
      expect(screen.getByText('Configure your security monitoring system')).toBeInTheDocument();
    });

    it('renders all Settings hub tabs on /settings/cameras', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByTestId('settings-tab-cameras')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-processing')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-notifications')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-ambient')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-access')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-storage')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-data')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-webhooks')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-audit')).toBeInTheDocument();
      expect(screen.getByTestId('settings-tab-notification-history')).toBeInTheDocument();
    });

    it('renders content panel with Cameras settings by default', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByTestId('settings-content-panel')).toBeInTheDocument();
      expect(screen.getByTestId('cameras-settings')).toBeInTheDocument();
    });
  });

  describe('navigation within Settings hub', () => {
    it('navigates to processing settings when processing tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      await user.click(screen.getByTestId('settings-tab-processing'));

      await waitFor(() => {
        expect(screen.getByTestId('processing-settings')).toBeInTheDocument();
      });
    });

    it('navigates to notification settings when notifications tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      await user.click(screen.getByTestId('settings-tab-notifications'));

      await waitFor(() => {
        expect(screen.getByTestId('notification-settings')).toBeInTheDocument();
      });
    });

    it('navigates to ambient settings when ambient tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      await user.click(screen.getByTestId('settings-tab-ambient'));

      await waitFor(() => {
        expect(screen.getByTestId('ambient-settings')).toBeInTheDocument();
      });
    });

    it('navigates to access settings when access tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      await user.click(screen.getByTestId('settings-tab-access'));

      await waitFor(() => {
        expect(screen.getByTestId('access-control-settings')).toBeInTheDocument();
      });
    });

    it('navigates to storage settings when storage tab is clicked', async () => {
      const { user } = renderWithProviders(<SettingsPage />);

      await user.click(screen.getByTestId('settings-tab-storage'));

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });
    });
  });

  describe('hub headings and active state across hubs (MO9)', () => {
    it('highlights cameras tab on /settings/cameras with Settings heading', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/cameras' });

      expect(screen.getByRole('heading', { name: 'Settings', level: 1 })).toBeInTheDocument();
      const camerasTab = screen.getByTestId('settings-tab-cameras');
      expect(camerasTab).toHaveAttribute('aria-selected', 'true');
      expect(camerasTab).toHaveClass('bg-[#76B900]');
    });

    it('renders Alerts & Rules heading and highlights rules tab on /settings/rules', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/rules' });

      expect(screen.getByRole('heading', { name: 'Alerts & Rules', level: 1 })).toBeInTheDocument();
      const rulesTab = screen.getByTestId('settings-tab-rules');
      expect(rulesTab).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByTestId('alert-rules-settings')).toBeInTheDocument();
    });

    it('renders AI Workbench heading and highlights prompts tab on /settings/prompts', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/prompts' });

      expect(screen.getByRole('heading', { name: 'AI Workbench', level: 1 })).toBeInTheDocument();
      const promptsTab = screen.getByTestId('settings-tab-prompts');
      expect(promptsTab).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByTestId('prompt-management')).toBeInTheDocument();
    });

    it('renders GPU & Models heading and highlights ai-models tab on /settings/ai-models', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/ai-models' });

      expect(screen.getByRole('heading', { name: 'GPU & Models', level: 1 })).toBeInTheDocument();
      const aiModelsTab = screen.getByTestId('settings-tab-ai-models');
      expect(aiModelsTab).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByTestId('ai-models-tab')).toBeInTheDocument();
    });

    it('renders Operations & Monitoring heading and highlights admin tab on /settings/admin', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/admin' });

      expect(
        screen.getByRole('heading', { name: 'Operations & Monitoring', level: 1 })
      ).toBeInTheDocument();
      const adminTab = screen.getByTestId('settings-tab-admin');
      expect(adminTab).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByTestId('admin-settings')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('wires role="tablist", role="tab", role="tabpanel", and aria-labelledby/aria-controls', () => {
      renderWithProviders(<SettingsPage />, { route: '/settings/cameras' });

      const tablist = screen.getByRole('tablist');
      expect(tablist).toHaveAttribute('aria-label', 'Settings sections');

      const camerasTab = screen.getByTestId('settings-tab-cameras');
      expect(camerasTab).toHaveAttribute('aria-controls', 'settings-panel-cameras');

      const panel = screen.getByRole('tabpanel');
      expect(panel).toHaveAttribute('id', 'settings-panel-cameras');
      expect(panel).toHaveAttribute('aria-labelledby', 'settings-tab-cameras');
    });
  });
});
