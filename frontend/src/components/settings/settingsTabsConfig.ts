/**
 * Settings tabs configuration
 *
 * This file contains the configuration for all settings tabs.
 * Separated from SettingsPage.tsx for fast-refresh compatibility.
 *
 * @see NEM-4938 - Convert Settings page to nested sub-routes
 */

import {
  Bell,
  Brain,
  Camera,
  Eye,
  FileText,
  HardDrive,
  Settings as SettingsIcon,
  Shield,
  Sliders,
  Users,
  Wrench,
} from 'lucide-react';

/**
 * Settings tab configuration for navigation
 */
export interface SettingsTabConfig {
  id: string;
  name: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
}

/**
 * Settings tabs configuration
 * Each tab maps to a nested route under /settings
 */
export const settingsTabs: SettingsTabConfig[] = [
  {
    id: 'cameras',
    name: 'CAMERAS',
    path: '/settings/cameras',
    icon: Camera,
    description: 'Add, remove, and configure security cameras',
  },
  {
    id: 'rules',
    name: 'RULES',
    path: '/settings/rules',
    icon: Shield,
    description: 'Set up automated alert rules and triggers',
  },
  {
    id: 'processing',
    name: 'PROCESSING',
    path: '/settings/processing',
    icon: SettingsIcon,
    description: 'Configure detection sensitivity and AI models',
  },
  {
    id: 'notifications',
    name: 'NOTIFICATIONS',
    path: '/settings/notifications',
    icon: Bell,
    description: 'Email, push, and webhook notification settings',
  },
  {
    id: 'ambient',
    name: 'AMBIENT',
    path: '/settings/ambient',
    icon: Eye,
    description: 'Background noise and environmental settings',
  },
  {
    id: 'calibration',
    name: 'CALIBRATION',
    path: '/settings/calibration',
    icon: Sliders,
    description: 'Camera calibration and zone configuration',
  },
  {
    id: 'access',
    name: 'ACCESS',
    path: '/settings/access',
    icon: Users,
    description: 'Manage household members, vehicles, and zone access',
  },
  {
    id: 'prompts',
    name: 'PROMPTS',
    path: '/settings/prompts',
    icon: FileText,
    description: 'Customize AI analysis prompts',
  },
  {
    id: 'storage',
    name: 'STORAGE',
    path: '/settings/storage',
    icon: HardDrive,
    description: 'Media retention and storage management',
  },
  {
    id: 'ai-models',
    name: 'AI MODELS',
    path: '/settings/ai-models',
    icon: Brain,
    description: 'View status and performance of all AI models',
  },
  {
    id: 'admin',
    name: 'ADMIN',
    path: '/settings/admin',
    icon: Wrench,
    description: 'Feature toggles, system config, and maintenance actions',
  },
];
