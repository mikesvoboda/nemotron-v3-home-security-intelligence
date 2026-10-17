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

  // A count only comes from a counted source; the provider's sole one is
  // `alertCountOverride` (the seam a real `useAlerts` total would replace).
  const alertCount = useMemo(() => {
    if (alertCountOverride !== undefined) {
      return alertCountOverride;
    }
    // [r205] This used to fabricate a number from health (`unhealthy` → 3,
    // `degraded` → 1), so a degraded service with nothing counted still printed
    // "(1)" in the tab title and a red dot on the favicon — an invented figure
    // wearing a real feature's badge. Health is still shown as health, by the
    // tint below: `threatLevel` reads the same status through
    // `calculateThreatLevel`, which [r205] leaves byte-identical
    // (AmbientBackground.tsx:174 publishes it as data-threat-category). 0 is
    // what FaviconBadge renders as "no number": bare baseTitle, unbadged icon
    // (FaviconBadge.tsx:216-220, pinned by FaviconBadge.test.tsx).
    return 0;
  }, [alertCountOverride]);

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
