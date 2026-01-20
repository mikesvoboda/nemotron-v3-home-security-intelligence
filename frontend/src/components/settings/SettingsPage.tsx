import { Tab } from '@headlessui/react';
import { clsx } from 'clsx';
import {
  AlertTriangle,
  Bell,
  Brain,
  Camera,
  Eye,
  FileText,
  HardDrive,
  Settings as SettingsIcon,
  Shield,
  Sliders,
  Wrench,
} from 'lucide-react';

import { FeatureErrorBoundary, SecureContextWarning } from '../common';
import AdminSettings from './AdminSettings';
import AIModelsTab from './AIModelsTab';
import AlertRulesSettings from './AlertRulesSettings';
import AmbientStatusSettings from './AmbientStatusSettings';
import CalibrationPanel from './CalibrationPanel';
import CamerasSettings from './CamerasSettings';
import NotificationSettings from './NotificationSettings';
import ProcessingSettings from './ProcessingSettings';
import { PromptManagementPage } from './prompts';
import FileOperationsPanel from '../system/FileOperationsPanel';

/**
 * SettingsPage component with tabbed interface
 *
 * Contains ten settings tabs:
 * - CAMERAS: Camera configuration and management
 * - RULES: Alert rules configuration
 * - PROCESSING: Event processing settings
 * - NOTIFICATIONS: Email and webhook notification settings
 * - AMBIENT: Ambient status awareness settings
 * - CALIBRATION: AI risk sensitivity and feedback calibration
 * - PROMPTS: AI prompt template management and version history
 * - STORAGE: Disk storage usage and file cleanup operations
 * - AI MODELS: Core AI models (RT-DETRv2, Nemotron) and Model Zoo status
 * - ADMIN: Feature toggles, system config, maintenance actions, dev tools
 *
 * Note: Analytics functionality is available on the dedicated Analytics page (/analytics)
 *
 * Features:
 * - Tab navigation with keyboard support (Headless UI)
 * - NVIDIA dark theme styling
 * - Icons for each settings category
 * - Responsive layout
 *
 * @see NEM-2356 - Add CalibrationPanel to Settings page
 * @see NEM-2388 - Add FileOperationsPanel to Settings page
 * @see NEM-3084 - Add AI MODELS tab integrating AIModelsSettings and ModelZooSection
 * @see NEM-3138 - Add ADMIN tab for AdminSettings component
 */
export default function SettingsPage() {
  /** Tab descriptions shown on hover via tooltips */
  const tabDescriptions: Record<string, string> = {
    cameras: 'Add, remove, and configure security cameras',
    rules: 'Set up automated alert rules and triggers',
    processing: 'Configure detection sensitivity and AI models',
    notifications: 'Email, push, and webhook notification settings',
    ambient: 'Background noise and environmental settings',
    calibration: 'Camera calibration and zone configuration',
    prompts: 'Customize AI analysis prompts',
    storage: 'Media retention and storage management',
    'ai-models': 'View status and performance of all AI models',
    admin: 'Feature toggles, system config, and maintenance actions',
  };

  const tabs = [
    {
      id: 'cameras',
      name: 'CAMERAS',
      icon: Camera,
      component: CamerasSettings,
    },
    {
      id: 'rules',
      name: 'RULES',
      icon: Shield,
      component: AlertRulesSettings,
    },
    {
      id: 'processing',
      name: 'PROCESSING',
      icon: SettingsIcon,
      component: ProcessingSettings,
    },
    {
      id: 'notifications',
      name: 'NOTIFICATIONS',
      icon: Bell,
      component: NotificationSettings,
    },
    {
      id: 'ambient',
      name: 'AMBIENT',
      icon: Eye,
      component: AmbientStatusSettings,
    },
    {
      id: 'calibration',
      name: 'CALIBRATION',
      icon: Sliders,
      component: CalibrationPanel,
    },
    {
      id: 'prompts',
      name: 'PROMPTS',
      icon: FileText,
      component: PromptManagementPage,
    },
    {
      id: 'storage',
      name: 'STORAGE',
      icon: HardDrive,
      component: FileOperationsPanel,
    },
    {
      id: 'ai-models',
      name: 'AI MODELS',
      icon: Brain,
      component: AIModelsTab,
    },
    {
      id: 'admin',
      name: 'ADMIN',
      icon: Wrench,
      component: AdminSettings,
    },
  ];

  return (
    <div className="min-h-screen bg-[#121212] p-8" data-testid="settings-page">
      <div className="mx-auto max-w-[1920px]">
        {/* Header */}
        <div className="mb-8 flex items-start justify-between">
          <div>
            <h1 className="text-page-title">Settings</h1>
            <p className="text-body-sm mt-2">Configure your security monitoring system</p>
          </div>

        </div>

        {/* Secure Context Warning - shown when not using HTTPS */}
        <SecureContextWarning className="mb-6" />

        {/* Tabs */}
        <Tab.Group>
          <Tab.List className="mb-8 flex space-x-2 rounded-lg border border-gray-800 bg-[#1A1A1A] p-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <Tab
                  key={tab.id}
                  title={tabDescriptions[tab.id]}
                  className={({ selected }) =>
                    clsx(
                      'flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-medium transition-all duration-200',
                      'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
                      selected
                        ? 'bg-[#76B900] text-gray-950 shadow-md'
                        : 'text-gray-200 hover:bg-gray-800 hover:text-white'
                    )
                  }
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                  <span>{tab.name}</span>
                </Tab>
              );
            })}
          </Tab.List>

          <Tab.Panels>
            {tabs.map((tab) => {
              const Component = tab.component;
              return (
                <Tab.Panel
                  key={tab.id}
                  className={clsx(
                    'rounded-lg border border-gray-800 bg-[#1A1A1A] p-6',
                    'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]'
                  )}
                >
                  <Component />
                </Tab.Panel>
              );
            })}
          </Tab.Panels>
        </Tab.Group>
      </div>
    </div>
  );
}

/**
 * SettingsPage with FeatureErrorBoundary wrapper.
 *
 * Wraps the SettingsPage component in a FeatureErrorBoundary to prevent
 * errors in the Settings page from crashing the entire application.
 * The navigation should remain functional even if settings fails to load.
 */
function SettingsPageWithErrorBoundary() {
  return (
    <FeatureErrorBoundary
      feature="Settings"
      fallback={
        <div className="flex min-h-screen flex-col items-center justify-center bg-[#121212] p-8">
          <AlertTriangle className="mb-4 h-12 w-12 text-red-400" />
          <h3 className="mb-2 text-lg font-semibold text-red-400">Settings Unavailable</h3>
          <p className="max-w-md text-center text-sm text-gray-400">
            Unable to load settings. Please refresh the page or try again later.
            You can still navigate to other sections using the sidebar.
          </p>
        </div>
      }
    >
      <SettingsPage />
    </FeatureErrorBoundary>
  );
}

export { SettingsPageWithErrorBoundary };
