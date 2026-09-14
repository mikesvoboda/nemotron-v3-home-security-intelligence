/**
 * AmbientStatusProvider component
 *
 * A provider component that wraps the app and manages all ambient
 * status awareness features including:
 * - Ambient background effects
 * - Favicon badge
 * - Integration with settings
 *
 * This component uses the useSystemStatus hook to get the current
 * threat level and applies ambient effects accordingly.
 */

import { useMemo, type ReactNode } from 'react';

import AmbientBackground from './AmbientBackground';
import FaviconBadge from './FaviconBadge';
import { useSettings } from '../../hooks/useSettings';
import { useSystemStatus, type SystemStatus } from '../../hooks/useSystemStatus';

export interface AmbientStatusProviderProps {
  /**
   * Children to render
   */
  children: ReactNode;
  /**
   * Override threat level (for testing)
   */
  threatLevelOverride?: number;
  /**
   * Override alert count (for testing)
   */
  alertCountOverride?: number;
}

/**
 * Calculate a threat level from system status metrics
 * Uses health status to determine threat level:
 * - healthy: 0 (normal)
 * - degraded: 50 (elevated)
 * - unhealthy: 90 (critical)
 */
function calculateThreatLevel(status: SystemStatus | null): number {
  if (!status) return 0;

  // Map health status to threat level
  switch (status.health) {
    case 'unhealthy':
      return 90; // Critical
    case 'degraded':
      return 50; // Elevated
    case 'healthy':
    default:
      return 0; // Normal
  }
}

/**
 * Provider component that manages ambient status awareness features.
 *
 * @example
 * ```tsx
 * // In App.tsx
 * export default function App() {
 *   return (
 *     <QueryClientProvider client={queryClient}>
 *       <AmbientStatusProvider>
 *         <Layout>
 *           <Routes>...</Routes>
 *         </Layout>
 *       </AmbientStatusProvider>
 *     </QueryClientProvider>
 *   );
 * }
 * ```
 */
export default function AmbientStatusProvider({
  children,
  threatLevelOverride,
  alertCountOverride,
}: AmbientStatusProviderProps) {
  const { ambientEnabled, faviconBadgeEnabled } = useSettings();
  const { status } = useSystemStatus();

  // Calculate threat level from system status or use override
  const threatLevel = useMemo(() => {
    if (threatLevelOverride !== undefined) {
      return threatLevelOverride;
    }
    return calculateThreatLevel(status);
  }, [status, threatLevelOverride]);

  // Get alert count or use override
  // Note: SystemStatus doesn't have event counts, so we derive from health
  const alertCount = useMemo(() => {
    if (alertCountOverride !== undefined) {
      return alertCountOverride;
    }
    // Map health status to a representative alert count for favicon badge
    if (!status) return 0;
    switch (status.health) {
      case 'unhealthy':
        return 3; // Show urgent badge
      case 'degraded':
        return 1; // Show warning badge
      default:
        return 0;
    }
  }, [status, alertCountOverride]);

  return (
    <>
      {/* Favicon badge (renders nothing visible) */}
      <FaviconBadge
        alertCount={alertCount}
        enabled={faviconBadgeEnabled}
        baseTitle="Security Dashboard"
      />

      {/* Ambient background wrapper */}
      <AmbientBackground threatLevel={threatLevel} enabled={ambientEnabled}>
        {children}
      </AmbientBackground>
    </>
  );
}

export type { AmbientStatusProviderProps as AmbientStatusProviderPropsType };
