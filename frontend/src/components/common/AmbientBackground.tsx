/**
 * AmbientBackground component
 *
 * Provides subtle visual cues about system threat level through
 * background color shifts and ambient effects. Designed to be
 * unobtrusive during normal operation but clearly visible when
 * threat levels are elevated.
 *
 * Respects user's reduced motion preferences.
 */

import { clsx } from 'clsx';
import { useEffect, useState, useMemo } from 'react';

import { type RiskLevel } from '../../utils/risk';

export interface AmbientBackgroundProps {
  /**
   * Current threat level score (0-100)
   * - 0-30: Normal (neutral dark background)
   * - 31-60: Elevated (subtle warm tint)
   * - 61-80: High (noticeable amber glow at edges)
   * - 81-100: Critical (pulsing red ambient glow)
   */
  threatLevel: number;
  /**
   * Whether ambient effects are enabled
   * When false, no ambient effects are rendered
   */
  enabled?: boolean;
  /**
   * Additional CSS classes
   */
  className?: string;
  /**
   * Children to render (the main app content)
   */
  children?: React.ReactNode;
}

export type ThreatCategory = 'normal' | 'elevated' | 'high' | 'critical';

/**
 * Converts a threat level score (0-100) to a category
 */
// eslint-disable-next-line react-refresh/only-export-components
export function getThreatCategory(score: number): ThreatCategory {
  if (score <= 30) return 'normal';
  if (score <= 60) return 'elevated';
  if (score <= 80) return 'high';
  return 'critical';
}

/**
 * Converts a threat level score (0-100) to a RiskLevel
 */
// eslint-disable-next-line react-refresh/only-export-components
export function threatLevelToRiskLevel(score: number): RiskLevel {
  if (score <= 30) return 'low';
  if (score <= 60) return 'medium';
  if (score <= 80) return 'high';
  return 'critical';
}

/**
 * Hook to detect user's reduced motion preference
 */
function useReducedMotion(): boolean {
  const [reducedMotion, setReducedMotion] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (event: MediaQueryListEvent) => {
      setReducedMotion(event.matches);
    };

    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  return reducedMotion;
}

/**
 * AmbientBackground provides a fullscreen ambient visual layer
 * that subtly communicates system threat status.
 */
export default function AmbientBackground({
  threatLevel,
  enabled = true,
  className,
  children,
}: AmbientBackgroundProps) {
  const reducedMotion = useReducedMotion();
  const category = useMemo(() => getThreatCategory(threatLevel), [threatLevel]);

  // Clamp threat level to valid range
  const clampedLevel = Math.max(0, Math.min(100, threatLevel));

  if (!enabled) {
    return <>{children}</>;
  }

  // Base styles for the ambient container
  const containerClasses = clsx('relative min-h-screen w-full', className);

  // Ambient overlay styles based on threat category
  const overlayClasses = clsx(
    'pointer-events-none fixed inset-0 z-0 transition-all duration-1000',
    {
      // Normal: No effect
      'opacity-0': category === 'normal',
      // Elevated: Very subtle warm tint
      'opacity-100': category !== 'normal',
    }
  );

  // Get the gradient style based on category
  const getGradientStyle = (): React.CSSProperties => {
    switch (category) {
      case 'normal':
        return {};

      case 'elevated':
        // Very subtle warm tint - barely noticeable
        return {
          background: `radial-gradient(ellipse at center, transparent 60%, rgba(234, 179, 8, 0.03) 100%)`,
        };

      case 'high':
        // Noticeable amber glow at edges
        return {
          background: `
            radial-gradient(ellipse at top, transparent 50%, rgba(249, 115, 22, 0.08) 100%),
            radial-gradient(ellipse at bottom, transparent 50%, rgba(249, 115, 22, 0.08) 100%),
            radial-gradient(ellipse at left, transparent 50%, rgba(249, 115, 22, 0.06) 100%),
            radial-gradient(ellipse at right, transparent 50%, rgba(249, 115, 22, 0.06) 100%)
          `,
        };

      case 'critical':
        // Stronger red glow for critical - will be animated
        return {
          background: `
            radial-gradient(ellipse at top, transparent 40%, rgba(239, 68, 68, 0.12) 100%),
            radial-gradient(ellipse at bottom, transparent 40%, rgba(239, 68, 68, 0.12) 100%),
            radial-gradient(ellipse at left, transparent 40%, rgba(239, 68, 68, 0.10) 100%),
            radial-gradient(ellipse at right, transparent 40%, rgba(239, 68, 68, 0.10) 100%)
          `,
        };

      default:
        return {};
    }
  };

  // Animation class for critical state
  const animationClass = clsx({
    'animate-ambient-pulse': category === 'critical' && !reducedMotion,
  });

  return (
    <div className={containerClasses} data-testid="ambient-background">
      {/* Ambient overlay layer */}
      <div
        className={clsx(overlayClasses, animationClass)}
        style={getGradientStyle()}
        data-testid="ambient-overlay"
        data-threat-category={category}
        data-threat-level={clampedLevel}
        aria-hidden="true"
      />
      {/* Main content */}
      <div className="relative z-10">{children}</div>
    </div>
  );
}

export type { RiskLevel };
