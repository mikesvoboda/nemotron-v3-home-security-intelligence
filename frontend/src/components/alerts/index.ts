/**
 * Alerts components for high-priority security events
 *
 * @see ./AlertsPage.tsx - Main alerts page with high/critical events
 * @see ./AlertStatsBar.tsx - Statistics bar showing alert metrics
 * @see ./AlertRulesManager.tsx - Alert rules CRUD management UI
 */

export { default as AlertsPage } from './AlertsPage';
export { default as AlertRulesManager } from './AlertRulesManager';
export { default as AlertStatsBar } from './AlertStatsBar';

export type { AlertsPageProps } from './AlertsPage';
export type { AlertRulesManagerProps } from './AlertRulesManager';
export type { AlertStatsBarProps } from './AlertStatsBar';
