import { Tab } from '@headlessui/react';
import { clsx } from 'clsx';
import {
  AlertTriangle,
  Bell,
  Brain,
  Camera,
  ChevronLeft,
  ChevronRight,
  Eye,
  FileText,
  HardDrive,
  Settings as SettingsIcon,
  Shield,
  Sliders,
  Wrench,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

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
import { DebugModeProvider } from '../../contexts/DebugModeContext';
import FileOperationsPanel from '../system/FileOperationsPanel';

/**
 * ScrollableTabList component that handles horizontal tab overflow
 *
 * Features:
 * - Horizontal scrolling when tabs overflow the container
 * - Left/right scroll indicators (chevron buttons) when content is clipped
 * - Fade shadows to indicate scrollable content
 * - Keyboard-accessible scroll buttons
 * - Smooth scroll animation
 *
 * @see NEM-3520 - Fix Settings page tab overflow
 */
interface ScrollableTabListProps {
  children: React.ReactNode;
}

function ScrollableTabList({ children }: ScrollableTabListProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollState = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const { scrollLeft, scrollWidth, clientWidth } = container;
    // Use a small threshold (2px) to account for rounding errors
    setCanScrollLeft(scrollLeft > 2);
    setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 2);
  }, []);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    // Initial check
    updateScrollState();

    // Check on scroll
    container.addEventListener('scroll', updateScrollState);

    // Check on resize
    const resizeObserver = new ResizeObserver(updateScrollState);
    resizeObserver.observe(container);

    return () => {
      container.removeEventListener('scroll', updateScrollState);
      resizeObserver.disconnect();
    };
  }, [updateScrollState]);

  const scroll = (direction: 'left' | 'right') => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const scrollAmount = 200; // pixels to scroll
    const newScrollLeft =
      direction === 'left'
        ? container.scrollLeft - scrollAmount
        : container.scrollLeft + scrollAmount;

    container.scrollTo({
      left: newScrollLeft,
      behavior: 'smooth',
    });
  };

  return (
    <div className="relative mb-8" data-testid="scrollable-tab-container">
      {/* Left scroll indicator */}
      {canScrollLeft && (
        <>
          {/* Fade shadow */}
          <div
            className="pointer-events-none absolute left-0 top-0 z-10 h-full w-12 bg-gradient-to-r from-[#1A1A1A] to-transparent"
            aria-hidden="true"
          />
          {/* Scroll button */}
          <button
            type="button"
            onClick={() => scroll('left')}
            className="absolute left-1 top-1/2 z-20 -translate-y-1/2 rounded-full bg-[#76B900] p-1.5 text-gray-950 shadow-lg transition-all hover:bg-[#8AD000] focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]"
            aria-label="Scroll tabs left"
            data-testid="scroll-left-button"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        </>
      )}

      {/* Scrollable tab container */}
      <div
        ref={scrollContainerRef}
        className="scrollbar-thin scrollbar-track-transparent scrollbar-thumb-gray-700 hover:scrollbar-thumb-gray-600 overflow-x-auto"
      >
        <Tab.List className="flex min-w-max space-x-2 rounded-lg border border-gray-800 bg-[#1A1A1A] p-1">
          {children}
        </Tab.List>
      </div>

      {/* Right scroll indicator */}
      {canScrollRight && (
        <>
          {/* Fade shadow */}
          <div
            className="pointer-events-none absolute right-0 top-0 z-10 h-full w-12 bg-gradient-to-l from-[#1A1A1A] to-transparent"
            aria-hidden="true"
          />
          {/* Scroll button */}
          <button
            type="button"
            onClick={() => scroll('right')}
            className="absolute right-1 top-1/2 z-20 -translate-y-1/2 rounded-full bg-[#76B900] p-1.5 text-gray-950 shadow-lg transition-all hover:bg-[#8AD000] focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]"
            aria-label="Scroll tabs right"
            data-testid="scroll-right-button"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </>
      )}
    </div>
  );
}

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
    <DebugModeProvider>
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
            <ScrollableTabList>
              {tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <Tab
                    key={tab.id}
                    title={tabDescriptions[tab.id]}
                    className={({ selected }) =>
                      clsx(
                        'flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-4 py-3 text-sm font-medium transition-all duration-200',
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
            </ScrollableTabList>

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
    </DebugModeProvider>
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
            Unable to load settings. Please refresh the page or try again later. You can still
            navigate to other sections using the sidebar.
          </p>
        </div>
      }
    >
      <SettingsPage />
    </FeatureErrorBoundary>
  );
}

export { SettingsPageWithErrorBoundary };
