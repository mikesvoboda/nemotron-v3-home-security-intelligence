import { Tab } from '@headlessui/react';
import { clsx } from 'clsx';
import {
  Bell,
  Camera,
  Eye,
  FileText,
  HardDrive,
  Settings as SettingsIcon,
  Shield,
  Sliders,
} from 'lucide-react';
import { Fragment } from 'react';

import { SecureContextWarning } from '../common';
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
 * Contains eight settings tabs:
 * - CAMERAS: Camera configuration and management
 * - RULES: Alert rules configuration
 * - PROCESSING: Event processing settings
 * - NOTIFICATIONS: Email and webhook notification settings
 * - AMBIENT: Ambient status awareness settings
 * - CALIBRATION: AI risk sensitivity and feedback calibration
 * - PROMPTS: AI prompt template management and version history
 * - STORAGE: Disk storage usage and file cleanup operations
 *
 * Note: Analytics functionality is available on the dedicated Analytics page (/analytics)
 * Note: AI model information is available on the dedicated AI Performance page (/ai)
 *
 * Features:
 * - Tab navigation with keyboard support (Headless UI)
 * - NVIDIA dark theme styling
 * - Icons for each settings category
 * - Responsive layout
 *
 * @see NEM-2356 - Add CalibrationPanel to Settings page
 * @see NEM-2388 - Add FileOperationsPanel to Settings page
 */
export default function SettingsPage() {
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
  ];

  return (
    <div className="min-h-screen bg-[#121212] p-8" data-testid="settings-page">
      <div className="mx-auto max-w-[1920px]">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-page-title">Settings</h1>
          <p className="text-body-sm mt-2">Configure your security monitoring system</p>
        </div>

        {/* Secure Context Warning - shown when not using HTTPS */}
        <SecureContextWarning className="mb-6" />

        {/* Tabs */}
        <Tab.Group>
          <Tab.List className="mb-8 flex space-x-2 rounded-lg border border-gray-800 bg-[#1A1A1A] p-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <Tab key={tab.id} as={Fragment}>
                  {({ selected }) => (
                    <button
                      className={clsx(
                        'flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-medium transition-all duration-200',
                        'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
                        selected
                          ? 'bg-[#76B900] text-gray-950 shadow-md'
                          : 'text-gray-200 hover:bg-gray-800 hover:text-white'
                      )}
                      data-selected={selected}
                    >
                      <Icon className="h-5 w-5" aria-hidden="true" />
                      <span>{tab.name}</span>
                    </button>
                  )}
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
