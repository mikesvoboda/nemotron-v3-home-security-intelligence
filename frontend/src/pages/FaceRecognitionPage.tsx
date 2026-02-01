/**
 * FaceRecognitionPage - Face Recognition and Person Re-ID Management
 *
 * Main page for managing face recognition features including:
 * - Known Persons: View and manage known persons database
 * - Face Events: Recent face detections and unknown strangers
 * - Person Tracking: Track person appearances across cameras
 *
 * Features:
 * - Tab navigation using Headless UI TabGroup
 * - NVIDIA dark theme styling with green accents
 * - Real-time unknown stranger alerts with badge indicator (NEM-4688 Phase 4)
 * - Placeholder content for each tab (to be implemented in later phases)
 *
 * @module pages/FaceRecognitionPage
 * @see NEM-4688 Phase 1 - Create Face Recognition Page with Tabs
 * @see NEM-4688 Phase 4 - Real-Time Unknown Stranger Alerts
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

import { Tab } from '@headlessui/react';
import { clsx } from 'clsx';
import { ScanFace, Users, Activity, Wrench } from 'lucide-react';
import { useState, useCallback } from 'react';

import { FaceSimilarityDebugTool } from '../components/face-recognition';
import { useUnknownStrangerAlerts } from '../hooks/useUnknownStrangerAlerts';

// ============================================================================
// Tab Placeholder Components
// ============================================================================

/**
 * Placeholder for Known Persons tab content.
 * Will be replaced with full implementation in Phase 2.
 */
function KnownPersonsTabContent() {
  return (
    <div
      className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-8 text-center"
      data-testid="known-persons-tab-content"
    >
      <Users className="mx-auto mb-4 h-12 w-12 text-gray-600" />
      <h3 className="mb-2 text-lg font-medium text-white">Known Persons</h3>
      <p className="text-sm text-gray-400">
        Manage your database of known persons. Add, edit, and view face embeddings.
      </p>
      <p className="mt-4 text-xs text-gray-500">Coming in Phase 2</p>
    </div>
  );
}

/**
 * Placeholder for Face Events tab content.
 * Will be replaced with full implementation in Phase 3.
 */
function FaceEventsTabContent() {
  return (
    <div
      className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-8 text-center"
      data-testid="face-events-tab-content"
    >
      <ScanFace className="mx-auto mb-4 h-12 w-12 text-gray-600" />
      <h3 className="mb-2 text-lg font-medium text-white">Face Events</h3>
      <p className="text-sm text-gray-400">
        View recent face detections, identify unknown strangers, and review match results.
      </p>
      <p className="mt-4 text-xs text-gray-500">Coming in Phase 3</p>
    </div>
  );
}

/**
 * Placeholder for Person Tracking tab content.
 * Will be replaced with full implementation in Phase 4.
 */
function PersonTrackingTabContent() {
  return (
    <div
      className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-8 text-center"
      data-testid="person-tracking-tab-content"
    >
      <Activity className="mx-auto mb-4 h-12 w-12 text-gray-600" />
      <h3 className="mb-2 text-lg font-medium text-white">Person Tracking</h3>
      <p className="text-sm text-gray-400">
        Track person appearances and journeys across multiple cameras over time.
      </p>
      <p className="mt-4 text-xs text-gray-500">Coming in Phase 4</p>
    </div>
  );
}

/**
 * Debug Tools tab content.
 * Contains developer tools for testing and debugging face recognition features.
 */
function DebugToolsTabContent() {
  return (
    <div data-testid="debug-tools-tab-content">
      <FaceSimilarityDebugTool />
    </div>
  );
}

// ============================================================================
// Tab Configuration
// ============================================================================

interface TabConfig {
  id: string;
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  component: React.ComponentType;
  /** Whether to show the unread badge on this tab */
  showBadge?: boolean;
}

const tabs: TabConfig[] = [
  {
    id: 'known-persons',
    name: 'Known Persons',
    icon: Users,
    component: KnownPersonsTabContent,
  },
  {
    id: 'face-events',
    name: 'Face Events',
    icon: ScanFace,
    component: FaceEventsTabContent,
    showBadge: true,
  },
  {
    id: 'person-tracking',
    name: 'Person Tracking',
    icon: Activity,
    component: PersonTrackingTabContent,
  },
  {
    id: 'debug-tools',
    name: 'Debug Tools',
    icon: Wrench,
    component: DebugToolsTabContent,
  },
];

// ============================================================================
// Badge Component
// ============================================================================

interface UnreadBadgeProps {
  count: number;
}

/**
 * Badge component to display unread count on tabs.
 * Shows count up to 99, then "99+" for larger counts.
 */
function UnreadBadge({ count }: UnreadBadgeProps) {
  if (count <= 0) {
    return null;
  }

  const displayCount = count > 99 ? '99+' : count.toString();

  return (
    <span
      className="ml-1.5 inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-600 px-1.5 text-xs font-semibold text-white"
      data-testid="unread-badge"
      aria-label={`${count} unread alerts`}
    >
      {displayCount}
    </span>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * FaceRecognitionPage - Main page component with tabbed navigation.
 *
 * Integrates real-time unknown stranger alerts via WebSocket subscription.
 * Shows unread badge on Face Events tab when unknown faces are detected.
 */
export default function FaceRecognitionPage() {
  const [selectedTabIndex, setSelectedTabIndex] = useState(0);

  // Subscribe to real-time unknown stranger alerts
  const { unreadCount, markAsRead } = useUnknownStrangerAlerts({
    showToasts: true,
    onView: useCallback(() => {
      // Switch to Face Events tab when user clicks "View" on a toast
      setSelectedTabIndex(1);
    }, []),
  });

  // Handle tab change - mark as read when switching to Face Events tab
  const handleTabChange = useCallback(
    (index: number) => {
      setSelectedTabIndex(index);
      // Mark alerts as read when switching to Face Events tab (index 1)
      if (index === 1 && unreadCount > 0) {
        markAsRead();
      }
    },
    [unreadCount, markAsRead]
  );

  return (
    <div className="min-h-screen bg-[#121212] p-6" data-testid="face-recognition-page">
      <div className="mx-auto max-w-[1400px]">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white">Face Recognition</h1>
          <p className="mt-1 text-sm text-gray-400">
            Manage known persons and track face detections across cameras
          </p>
        </div>

        {/* Tab Navigation */}
        <Tab.Group selectedIndex={selectedTabIndex} onChange={handleTabChange}>
          <Tab.List className="mb-6 flex space-x-2 rounded-lg border border-gray-800 bg-[#1A1A1A] p-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <Tab
                  key={tab.id}
                  className={({ selected }) =>
                    clsx(
                      'flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all duration-200',
                      'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
                      selected
                        ? 'bg-[#76B900] text-gray-950 shadow-md'
                        : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                    )
                  }
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  <span>{tab.name}</span>
                  {tab.showBadge && <UnreadBadge count={unreadCount} />}
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
