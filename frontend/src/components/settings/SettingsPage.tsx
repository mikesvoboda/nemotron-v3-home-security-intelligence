import { Tab } from '@headlessui/react';
import { clsx } from 'clsx';
import { Bell, Camera, Cpu, Settings as SettingsIcon } from 'lucide-react';
import { Fragment } from 'react';

import { SecureContextWarning } from '../common';
import AIModelsSettings from './AIModelsSettings';
import CamerasSettings from './CamerasSettings';
import NotificationSettings from './NotificationSettings';
import ProcessingSettings from './ProcessingSettings';

/**
 * SettingsPage component with tabbed interface
 *
 * Contains four settings tabs:
 * - CAMERAS: Camera configuration and management
 * - PROCESSING: Event processing settings
 * - AI MODELS: AI model status and information
 * - NOTIFICATIONS: Email and webhook notification settings
 *
 * Features:
 * - Tab navigation with keyboard support (Headless UI)
 * - NVIDIA dark theme styling
 * - Icons for each settings category
 * - Responsive layout
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
      id: 'processing',
      name: 'PROCESSING',
      icon: SettingsIcon,
      component: ProcessingSettings,
    },
    {
      id: 'ai-models',
      name: 'AI MODELS',
      icon: Cpu,
      component: AIModelsSettings,
    },
    {
      id: 'notifications',
      name: 'NOTIFICATIONS',
      icon: Bell,
      component: NotificationSettings,
    },
  ];

  return (
    <div className="min-h-screen bg-[#121212] p-8">
      <div className="mx-auto max-w-[1920px]">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white">Settings</h1>
          <p className="mt-2 text-sm text-gray-400">Configure your security monitoring system</p>
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
                          ? 'bg-[#76B900] text-black shadow-md'
                          : 'text-gray-300 hover:bg-gray-800 hover:text-white'
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
