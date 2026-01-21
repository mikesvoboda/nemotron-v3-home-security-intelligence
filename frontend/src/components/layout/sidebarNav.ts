/**
 * Sidebar navigation configuration
 * Separated from Sidebar.tsx for fast-refresh compatibility
 */

import {
  Activity,
  BarChart3,
  Bell,
  Brain,
  Briefcase,
  ClipboardCheck,
  Clock,
  Flame,
  Home,
  ScrollText,
  Settings,
  Shield,
  Trash2,
  Users,
  Workflow,
} from 'lucide-react';

export interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  path: string;
  /** Data attribute for product tour targeting */
  dataTour?: string;
}

export interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
  defaultExpanded: boolean;
}

export const STORAGE_KEY = 'sidebar-expansion-state';

export const navGroups: NavGroup[] = [
  {
    id: 'monitoring',
    label: 'MONITORING',
    defaultExpanded: true,
    items: [
      { id: 'dashboard', label: 'Dashboard', icon: Home, path: '/' },
      { id: 'timeline', label: 'Timeline', icon: Clock, path: '/timeline', dataTour: 'timeline-link' },
      { id: 'entities', label: 'Entities', icon: Users, path: '/entities' },
      { id: 'alerts', label: 'Alerts', icon: Bell, path: '/alerts' },
    ],
  },
  {
    id: 'analytics',
    label: 'ANALYTICS',
    defaultExpanded: true,
    items: [
      { id: 'analytics', label: 'Analytics', icon: BarChart3, path: '/analytics' },
      { id: 'ai-audit', label: 'AI Audit', icon: ClipboardCheck, path: '/ai-audit' },
      { id: 'ai', label: 'AI Performance', icon: Brain, path: '/ai' },
      { id: 'pyroscope', label: 'Profiling', icon: Flame, path: '/pyroscope' },
    ],
  },
  {
    id: 'operations',
    label: 'OPERATIONS',
    defaultExpanded: false,
    items: [
      { id: 'jobs', label: 'Jobs', icon: Briefcase, path: '/jobs' },
      { id: 'operations', label: 'Pipeline', icon: Workflow, path: '/operations' },
      { id: 'tracing', label: 'Tracing', icon: Activity, path: '/tracing' },
      { id: 'logs', label: 'Logs', icon: ScrollText, path: '/logs' },
    ],
  },
  {
    id: 'admin',
    label: 'ADMIN',
    defaultExpanded: false,
    items: [
      { id: 'audit', label: 'Audit Log', icon: Shield, path: '/audit' },
      { id: 'trash', label: 'Trash', icon: Trash2, path: '/trash' },
      {
        id: 'settings',
        label: 'Settings',
        icon: Settings,
        path: '/settings',
        dataTour: 'settings-link',
      },
    ],
  },
];

// Flatten nav items for backwards compatibility with tests
export const navItems: NavItem[] = navGroups.flatMap((group) => group.items);
