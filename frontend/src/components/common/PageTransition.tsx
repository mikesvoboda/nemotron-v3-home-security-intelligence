import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { useLocation } from 'react-router-dom';

import {
  defaultTransition,
  pageTransitionVariants,
  reducedMotionTransition,
  type PageTransitionVariant,
} from './animations';

import type { ReactNode } from 'react';

export interface PageTransitionProps {
  /** Content to animate */
  children: ReactNode;
  /** Animation variant to use */
  variant?: PageTransitionVariant;
  /** Animation duration in seconds */
  duration?: number;
  /** Additional CSS classes */
  className?: string;
}

/**
 * PageTransition wraps page content with smooth fade and slide animations.
 * Respects user's prefers-reduced-motion preference for accessibility.
 *
 * @example
 * ```tsx
 * <PageTransition>
 *   <DashboardPage />
 * </PageTransition>
 * ```
 */
export default function PageTransition({
  children,
  variant = 'slideUp',
  duration = 0.2,
  className = '',
}: PageTransitionProps) {
  const location = useLocation();
  const prefersReducedMotion = useReducedMotion();

  const variants = pageTransitionVariants[variant];
  const transition = prefersReducedMotion
    ? reducedMotionTransition
    : { ...defaultTransition, duration };

  const classes = [
    'page-transition-wrapper',
    className,
    prefersReducedMotion ? 'motion-reduce' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        data-testid="page-transition"
        className={classes}
        variants={variants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={transition}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
