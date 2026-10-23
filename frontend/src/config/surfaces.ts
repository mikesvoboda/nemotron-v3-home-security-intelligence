/**
 * Single registry of hubs, tabs, and view modes (F4.9 — docs/uplevel/4n-modes.md).
 *
 * Every navigation surface in the application — Sidebar, MobileBottomNav,
 * CommandPalette, useKeyboardShortcuts, ShortcutsHelpModal, HubTabBar,
 * SettingsPage, and AdvancedBanner — derives from this registry so they cannot
 * drift apart.
 */

import {
  Activity,
  BarChart3,
  Bell,
  BellRing,
  Brain,
  Briefcase,
  Camera,
  Car,
  ClipboardCheck,
  Clock,
  Cpu,
  Database,
  Eye,
  FileText,
  Fingerprint,
  Flame,
  Gauge,
  Grid3X3,
  HardDrive,
  Home,
  LayoutDashboard,
  MapPin,
  Route,
  ScanFace,
  ScrollText,
  Server,
  Settings,
  Shield,
  Trash2,
  Users,
  Video,
  Webhook,
  Workflow,
  Wrench,
} from 'lucide-react';

import type { ComponentType } from 'react';

export type ViewMode = 'easy' | 'advanced';

export interface HubTab {
  id: string;
  path: string;
  label: string;
  testId: string;
  keywords?: string[];
  shortcut?: string;
  /** Route navigated by the keyboard chord when it differs from `path` (e.g. `g s` -> `/settings`). */
  shortcutPath?: string;
  /** Description used by ShortcutsHelpModal (e.g. `Go to Dashboard`). */
  shortcutLabel?: string;
  exact?: boolean;
  icon?: ComponentType<{ className?: string }>;
  description?: string;
}

export interface Hub {
  id: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  mode: ViewMode;
  tabs: HubTab[];
  dataTour?: string;
  badge?: string;
  /** Exact paths that belong to this hub without rendering a separate tab (e.g. `/settings`). */
  exactPaths?: string[];
}

export const HUBS: readonly Hub[] = [
  // ── Easy Mode (5 hubs) ────────────────────────────────────────────────────
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: Home,
    mode: 'easy',
    tabs: [
      {
        id: 'overview',
        path: '/',
        label: 'Overview',
        testId: 'hub-tab-overview',
        exact: true,
        shortcut: 'g d',
        shortcutLabel: 'Go to Dashboard',
        icon: Home,
        keywords: ['home', 'main', 'overview', 'cameras', 'dashboard'],
      },
      {
        id: 'trends',
        path: '/analytics',
        label: 'Trends',
        testId: 'hub-tab-trends',
        shortcut: 'g n',
        shortcutLabel: 'Go to Analytics',
        icon: BarChart3,
        keywords: ['analytics', 'trends', 'charts', 'graphs', 'statistics', 'stats'],
      },
    ],
  },
  {
    id: 'timeline-search',
    label: 'Timeline & Search',
    icon: Clock,
    mode: 'easy',
    dataTour: 'timeline-link',
    tabs: [
      {
        id: 'timeline',
        path: '/timeline',
        label: 'Timeline',
        testId: 'hub-tab-timeline',
        shortcut: 'g t',
        shortcutLabel: 'Go to Timeline',
        icon: Clock,
        keywords: ['events', 'history', 'time', 'timeline', 'search'],
      },
      {
        id: 'trash',
        path: '/trash',
        label: 'Trash',
        testId: 'hub-tab-trash',
        icon: Trash2,
        keywords: ['deleted', 'restore', 'purge', 'trash'],
      },
    ],
  },
  {
    id: 'alerts-rules',
    label: 'Alerts & Rules',
    icon: Bell,
    mode: 'easy',
    badge: 'open_alerts',
    tabs: [
      {
        id: 'alerts',
        path: '/alerts',
        label: 'Alerts',
        testId: 'hub-tab-alerts',
        shortcut: 'g a',
        shortcutLabel: 'Go to Alerts',
        icon: Bell,
        keywords: ['notifications', 'warnings', 'alerts'],
      },
      {
        id: 'scene-changes',
        path: '/scene-changes',
        label: 'Scene changes',
        testId: 'hub-tab-scene-changes',
        icon: Eye,
        keywords: ['tamper', 'blocked', 'moved', 'scene', 'camera', 'scene changes'],
      },
      {
        id: 'rules',
        path: '/settings/rules',
        label: 'Rules',
        testId: 'settings-tab-rules',
        icon: Shield,
        description: 'Set up automated alert rules and triggers',
        keywords: ['triggers', 'conditions', 'alert rules', 'rules'],
      },
    ],
  },
  {
    id: 'household',
    label: 'Household',
    icon: Users,
    mode: 'easy',
    tabs: [
      {
        id: 'members',
        path: '/household',
        label: 'Members',
        testId: 'hub-tab-members',
        icon: Users,
        keywords: ['members', 'family', 'trust', 'household'],
      },
      {
        id: 'people-faces',
        path: '/face-recognition',
        label: 'People & faces',
        testId: 'hub-tab-people-faces',
        icon: ScanFace,
        keywords: ['faces', 'known persons', 'recognition', 'people', 'face recognition'],
      },
      {
        id: 'vehicles-plates',
        path: '/plate-reads',
        label: 'Vehicles & plates',
        testId: 'hub-tab-vehicles-plates',
        icon: Car,
        keywords: ['cars', 'license', 'plates', 'vehicles', 'alpr', 'plate reads'],
      },
      {
        id: 'zones',
        path: '/zones',
        label: 'Zones',
        testId: 'hub-tab-zones',
        icon: MapPin,
        keywords: ['polygons', 'areas', 'boundaries', 'zones'],
      },
    ],
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    mode: 'easy',
    dataTour: 'settings-link',
    exactPaths: ['/settings'],
    tabs: [
      {
        id: 'cameras',
        path: '/settings/cameras',
        label: 'Cameras',
        testId: 'settings-tab-cameras',
        shortcut: 'g s',
        shortcutPath: '/settings',
        shortcutLabel: 'Go to Settings',
        icon: Camera,
        description: 'Add, remove, and configure security cameras',
        keywords: ['preferences', 'configuration', 'options', 'cameras', 'settings'],
      },
      {
        id: 'processing',
        path: '/settings/processing',
        label: 'Processing',
        testId: 'settings-tab-processing',
        icon: Settings,
        description: 'Configure detection sensitivity and AI models',
        keywords: ['sensitivity', 'batch', 'retention', 'processing'],
      },
      {
        id: 'notifications',
        path: '/settings/notifications',
        label: 'Notifications',
        testId: 'settings-tab-notifications',
        icon: Bell,
        description: 'Email, push, and webhook notification settings',
        keywords: ['email', 'push', 'webhook', 'quiet hours', 'notifications'],
      },
      {
        id: 'ambient',
        path: '/settings/ambient',
        label: 'Ambient',
        testId: 'settings-tab-ambient',
        icon: Eye,
        description: 'Background noise and environmental settings',
        keywords: ['background', 'favicon', 'tint', 'ambient'],
      },
      {
        id: 'access',
        path: '/settings/access',
        label: 'Access',
        testId: 'settings-tab-access',
        icon: Users,
        description: 'Manage household members, vehicles, and zone access',
        keywords: ['household', 'zone access', 'schedule', 'access'],
      },
      {
        id: 'storage',
        path: '/settings/storage',
        label: 'Storage',
        testId: 'settings-tab-storage',
        icon: HardDrive,
        description: 'Media retention and storage management',
        keywords: ['disk', 'cleanup', 'retention', 'storage'],
      },
      {
        id: 'data',
        path: '/data',
        label: 'Data',
        testId: 'settings-tab-data',
        icon: Database,
        description: 'Backups, exports, and data management',
        keywords: ['backup', 'restore', 'export', 'data management', 'data'],
      },
      {
        id: 'webhooks',
        path: '/webhooks',
        label: 'Webhooks',
        testId: 'settings-tab-webhooks',
        icon: Webhook,
        description: 'Outbound webhook endpoints and delivery history',
        keywords: ['outbound', 'integrations', 'deliveries', 'webhooks'],
      },
      {
        id: 'audit',
        path: '/audit',
        label: 'Audit log',
        testId: 'settings-tab-audit',
        icon: Shield,
        description: 'System and user activity audit trail',
        keywords: ['history', 'changes', 'tracking', 'audit log'],
      },
      {
        id: 'notification-history',
        path: '/notifications',
        label: 'Notification history',
        testId: 'settings-tab-notification-history',
        icon: BellRing,
        description: 'Notification preferences and history',
        keywords: ['notification preferences', 'notifications'],
      },
    ],
  },

  // ── Advanced Mode (4 hubs) ────────────────────────────────────────────────
  {
    id: 'ai-workbench',
    label: 'AI Workbench',
    icon: ClipboardCheck,
    mode: 'advanced',
    tabs: [
      {
        id: 'ai-audit',
        path: '/ai-audit',
        label: 'AI Audit',
        testId: 'hub-tab-ai-audit',
        icon: ClipboardCheck,
        keywords: ['evaluation', 'critique', 'quality', 'ai audit'],
      },
      {
        id: 'prompts',
        path: '/settings/prompts',
        label: 'Prompts',
        testId: 'settings-tab-prompts',
        icon: FileText,
        description: 'Customize AI analysis prompts',
        keywords: ['templates', 'system prompt', 'prompts'],
      },
    ],
  },
  {
    id: 'gpu-models',
    label: 'GPU & Models',
    icon: Brain,
    mode: 'advanced',
    tabs: [
      {
        id: 'ai',
        path: '/ai',
        label: 'AI Performance',
        testId: 'hub-tab-ai',
        icon: Brain,
        keywords: ['model', 'inference', 'gpu', 'nemotron', 'rtdetr', 'vlm', 'latency'],
      },
      {
        id: 'ai-models',
        path: '/settings/ai-models',
        label: 'AI Models',
        testId: 'settings-tab-ai-models',
        icon: Brain,
        description: 'View status and performance of all AI models',
        keywords: ['model zoo', 'vram', 'weights', 'ai models'],
      },
      {
        id: 'gpu',
        path: '/settings/gpu',
        label: 'GPU',
        testId: 'settings-tab-gpu',
        icon: Cpu,
        description: 'GPU device assignment and VRAM strategy',
        keywords: ['hardware', 'strategy', 'vram', 'gpu settings'],
      },
    ],
  },
  {
    id: 'entities-reid',
    label: 'Entities & Re-ID',
    icon: Fingerprint,
    mode: 'advanced',
    tabs: [
      {
        id: 'entities',
        path: '/entities',
        label: 'Entities',
        testId: 'hub-tab-entities',
        shortcut: 'g e',
        shortcutLabel: 'Go to Entities',
        icon: Users,
        keywords: ['people', 'objects', 'detection', 'entities'],
      },
      {
        id: 'reid',
        path: '/reid',
        label: 'Re-ID',
        testId: 'hub-tab-reid',
        icon: Fingerprint,
        keywords: ['re-identification', 'similarity', 'embeddings', 'reid'],
      },
      {
        id: 'heatmaps',
        path: '/heatmaps',
        label: 'Heatmaps',
        testId: 'hub-tab-heatmaps',
        icon: Grid3X3,
        keywords: ['activity', 'density', 'zones', 'heatmaps'],
      },
      {
        id: 'tracks',
        path: '/tracks',
        label: 'Object tracks',
        testId: 'hub-tab-tracks',
        icon: Route,
        keywords: ['trajectories', 'movement', 'paths', 'tracks', 'object tracks'],
      },
    ],
  },
  {
    id: 'operations-monitoring',
    label: 'Operations & Monitoring',
    icon: Workflow,
    mode: 'advanced',
    tabs: [
      {
        id: 'operations',
        path: '/operations',
        label: 'Operations',
        testId: 'hub-tab-operations',
        shortcut: 'g y',
        shortcutLabel: 'Go to System',
        icon: Workflow,
        keywords: [
          'monitoring',
          'health',
          'status',
          'performance',
          'pipeline',
          'system',
          'operations',
        ],
      },
      {
        id: 'admin',
        path: '/settings/admin',
        label: 'Admin',
        testId: 'settings-tab-admin',
        icon: Wrench,
        description: 'Feature toggles, system config, and maintenance actions',
        keywords: ['feature toggles', 'system config', 'maintenance', 'logging', 'admin'],
      },
      {
        id: 'jobs',
        path: '/jobs',
        label: 'Jobs',
        testId: 'hub-tab-jobs',
        icon: Briefcase,
        keywords: ['background', 'exports', 'tasks', 'queues', 'jobs'],
      },
      {
        id: 'performance',
        path: '/performance',
        label: 'Performance',
        testId: 'hub-tab-performance',
        icon: Activity,
        keywords: ['metrics', 'throughput', 'charts', 'performance'],
      },
      {
        id: 'logs',
        path: '/logs',
        label: 'Logs',
        testId: 'hub-tab-logs',
        shortcut: 'g o',
        shortcutLabel: 'Go to Logs',
        icon: ScrollText,
        keywords: ['system', 'debug', 'output', 'loki', 'logs'],
      },
      {
        id: 'ai-services',
        path: '/ai-services',
        label: 'AI Services',
        testId: 'hub-tab-ai-services',
        icon: Server,
        keywords: ['queues', 'health', 'pipeline', 'ai services'],
      },
      {
        id: 'video-analytics',
        path: '/video-analytics',
        label: 'Video Analytics',
        testId: 'hub-tab-video-analytics',
        icon: Video,
        keywords: ['streams', 'rtsp', 'cameras', 'video analytics'],
      },
      {
        id: 'pyroscope',
        path: '/pyroscope',
        label: 'Profiling',
        testId: 'hub-tab-pyroscope',
        icon: Flame,
        keywords: ['flamegraph', 'cpu', 'memory', 'pyroscope', 'profiling'],
      },
      {
        id: 'operations-dashboard',
        path: '/operations-dashboard',
        label: 'Operations Dashboard',
        testId: 'hub-tab-operations-dashboard',
        icon: LayoutDashboard,
        keywords: ['grafana', 'overview', 'operations dashboard'],
      },
      {
        id: 'gpu-metrics',
        path: '/gpu-metrics',
        label: 'GPU Metrics',
        testId: 'hub-tab-gpu-metrics',
        icon: Cpu,
        keywords: ['dcgm', 'temperature', 'utilization', 'gpu metrics'],
      },
      {
        id: 'request-profiling',
        path: '/request-profiling',
        label: 'Request Profiling',
        testId: 'hub-tab-request-profiling',
        icon: Gauge,
        keywords: ['latency', 'endpoints', 'traces', 'request profiling'],
      },
      {
        id: 'tracing',
        path: '/tracing',
        label: 'Tracing',
        testId: 'hub-tab-tracing',
        icon: Activity,
        keywords: ['tempo', 'spans', 'distributed', 'tracing'],
      },
    ],
  },
];

export const EASY_HUBS: readonly Hub[] = HUBS.filter((h) => h.mode === 'easy');
export const ADVANCED_HUBS: readonly Hub[] = HUBS.filter((h) => h.mode === 'advanced');

function normalizePathname(pathname: string): string {
  const withoutQuery = pathname.split(/[?#]/)[0] || '/';
  if (withoutQuery.length > 1 && withoutQuery.endsWith('/')) {
    return withoutQuery.slice(0, -1);
  }
  return withoutQuery;
}

/**
 * Find the matching `(hub, tab)` pair for `pathname`.
 *
 * `/` and `/settings` match only themselves; any other tab path matches itself
 * and the paths below it by segment (`startsWith(path + '/')`), and the longest
 * match wins.
 */
export function tabForPath(pathname: string): { hub: Hub; tab: HubTab } | undefined {
  const normalized = normalizePathname(pathname);

  let bestMatch: { hub: Hub; tab: HubTab; length: number } | undefined;

  for (const hub of HUBS) {
    if (hub.exactPaths?.includes(normalized) && hub.tabs.length > 0) {
      return { hub, tab: hub.tabs[0] };
    }
    for (const tab of hub.tabs) {
      const isExactOnly = Boolean(tab.exact || tab.path === '/' || tab.path === '/settings');
      const matches = isExactOnly
        ? normalized === tab.path
        : normalized === tab.path || normalized.startsWith(`${tab.path}/`);
      if (matches && (!bestMatch || tab.path.length > bestMatch.length)) {
        bestMatch = { hub, tab, length: tab.path.length };
      }
    }
  }

  return bestMatch ? { hub: bestMatch.hub, tab: bestMatch.tab } : undefined;
}

/**
 * Return the Hub that owns `pathname`, or `undefined` for unrouted / auth paths.
 */
export function hubForPath(pathname: string): Hub | undefined {
  return tabForPath(pathname)?.hub;
}

/**
 * Return the ViewMode (`'easy'` or `'advanced'`) for `pathname`, or `undefined`
 * if `pathname` belongs to no hub.
 */
export function modeOfPath(pathname: string): ViewMode | undefined {
  return hubForPath(pathname)?.mode;
}

/**
 * Derive `g <key>` chord routes from the registry.
 */
export const CHORD_ROUTES: Readonly<Record<string, string>> = (() => {
  const routes: Record<string, string> = {};
  for (const hub of HUBS) {
    for (const tab of hub.tabs) {
      if (tab.shortcut?.startsWith('g ')) {
        const secondKey = tab.shortcut.slice(2).trim();
        if (secondKey) {
          routes[secondKey] = tab.shortcutPath ?? tab.path;
        }
      }
    }
  }
  return routes;
})();

export interface ChordDescriptor {
  keys: [string, string];
  description: string;
  path: string;
  mode: ViewMode;
}

/**
 * Ordered list of navigation chord shortcuts derived from the registry for `ShortcutsHelpModal`.
 */
export const NAVIGATION_CHORDS: readonly ChordDescriptor[] = (() => {
  const chords: ChordDescriptor[] = [];
  for (const hub of HUBS) {
    for (const tab of hub.tabs) {
      if (tab.shortcut?.startsWith('g ')) {
        const secondKey = tab.shortcut.slice(2).trim();
        if (secondKey) {
          chords.push({
            keys: ['g', secondKey],
            description: tab.shortcutLabel ?? `Go to ${tab.label}`,
            path: tab.shortcutPath ?? tab.path,
            mode: hub.mode,
          });
        }
      }
    }
  }
  return chords;
})();
