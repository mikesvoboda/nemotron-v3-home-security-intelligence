export interface PageDocConfig {
  /** Display name shown in link (e.g., "Alerts", "Jobs") */
  label: string;
  /** Path to documentation file relative to repo root */
  docPath: string;
  /** Optional tooltip description */
  description?: string;
}

/**
 * Maps routes to their documentation configuration.
 * Used by PageDocsLink to render contextual help links.
 */
export const PAGE_DOCUMENTATION: Record<string, PageDocConfig> = {
  '/': {
    label: 'Dashboard',
    docPath: 'docs/ui/dashboard.md',
    description: 'Live monitoring and risk overview',
  },
  '/timeline': {
    label: 'Timeline',
    docPath: 'docs/ui/timeline.md',
    description: 'Chronological event history',
  },
  '/entities': {
    label: 'Entities',
    docPath: 'docs/ui/entities.md',
    description: 'Tracked people and objects',
  },
  '/alerts': {
    label: 'Alerts',
    docPath: 'docs/ui/alerts.md',
    description: 'Alert management and configuration',
  },
  '/audit': {
    label: 'Audit Log',
    docPath: 'docs/ui/audit-log.md',
    description: 'System audit trail',
  },
  '/analytics': {
    label: 'Analytics',
    docPath: 'docs/ui/analytics.md',
    description: 'Insights and trends',
  },
  '/jobs': {
    label: 'Jobs',
    docPath: 'docs/ui/jobs.md',
    description: 'Background job monitoring',
  },
  '/ai-audit': {
    label: 'AI Audit',
    docPath: 'docs/ui/ai-audit.md',
    description: 'AI decision explanations',
  },
  '/ai': {
    label: 'AI Performance',
    docPath: 'docs/ui/ai-performance.md',
    description: 'Model metrics and performance',
  },
  '/operations': {
    label: 'Operations',
    docPath: 'docs/ui/operations.md',
    description: 'System health and resources',
  },
  '/trash': {
    label: 'Trash',
    docPath: 'docs/ui/trash.md',
    description: 'Deleted event recovery',
  },
  '/logs': {
    label: 'Logs',
    docPath: 'docs/ui/logs.md',
    description: 'Application log viewer',
  },
  '/settings': {
    label: 'Settings',
    docPath: 'docs/ui/settings.md',
    description: 'Application configuration',
  },
};
