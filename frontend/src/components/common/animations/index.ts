import type { Variants } from 'framer-motion';

/**
 * Animation variants for page transitions
 * Supports fade, slideUp, slideRight, and scale effects
 */
export const pageTransitionVariants: Record<string, Variants> = {
  fade: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
  },
  slideUp: {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -20 },
  },
  slideRight: {
    initial: { opacity: 0, x: -20 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: 20 },
  },
  scale: {
    initial: { opacity: 0, scale: 0.95 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.95 },
  },
};

/**
 * Animation variants for modal transitions
 * Supports scale, slideUp, slideDown, and fade effects
 */
export const modalTransitionVariants: Record<string, Variants> = {
  scale: {
    initial: { opacity: 0, scale: 0.9 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.9 },
  },
  slideUp: {
    initial: { opacity: 0, y: 50 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: 50 },
  },
  slideDown: {
    initial: { opacity: 0, y: -50 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -50 },
  },
  fade: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
  },
};

/**
 * Animation variants for list items with stagger support
 * The stagger effect is controlled by the parent container
 */
export const listItemVariants: Record<string, Variants> = {
  fadeIn: {
    hidden: { opacity: 0 },
    visible: { opacity: 1 },
    exit: { opacity: 0 },
  },
  slideIn: {
    hidden: { opacity: 0, x: -20 },
    visible: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: 20 },
  },
  scaleIn: {
    hidden: { opacity: 0, scale: 0.8 },
    visible: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.8 },
  },
};

/**
 * Container variants for staggered list animations
 * @param staggerDelay - Delay between each child animation
 */
export const createListContainerVariants = (staggerDelay: number = 0.05): Variants => ({
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: staggerDelay,
      delayChildren: 0.1,
    },
  },
});

/**
 * Backdrop animation variants for modals and overlays
 */
export const backdropVariants: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
};

/**
 * Default transition configuration for smooth animations
 */
export const defaultTransition = {
  duration: 0.2,
  ease: [0.4, 0, 0.2, 1], // cubic-bezier for smooth feel
};

/**
 * Reduced motion transition - instant for accessibility
 */
export const reducedMotionTransition = {
  duration: 0,
};

/**
 * Spring transition for bouncy effects
 */
export const springTransition = {
  type: 'spring',
  stiffness: 300,
  damping: 30,
};

export type PageTransitionVariant = keyof typeof pageTransitionVariants;
export type ModalTransitionVariant = keyof typeof modalTransitionVariants;
export type ListItemVariant = keyof typeof listItemVariants;
