import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

import {
  createListContainerVariants,
  defaultTransition,
  listItemVariants,
  reducedMotionTransition,
  type ListItemVariant,
} from './animations';

import type { ReactNode } from 'react';

export interface AnimatedListProps<T> {
  /** Array of items to render */
  items: T[];
  /** Function to render each item */
  renderItem: (item: T, index: number) => ReactNode;
  /** Function to extract unique key from each item */
  keyExtractor: (item: T, index: number) => string;
  /** Animation variant for list items */
  variant?: ListItemVariant;
  /** Delay between each item animation */
  staggerDelay?: number;
  /** Content to show when list is empty */
  emptyState?: ReactNode;
  /** Additional CSS classes for list container */
  className?: string;
  /** Additional CSS classes for list items */
  itemClassName?: string;
  /** ARIA role for the list */
  role?: string;
  /** Element type to render as ('ul' or 'div') */
  as?: 'ul' | 'div';
}

/**
 * AnimatedList renders a list with staggered entrance animations.
 * Each item animates in sequence for a smooth visual effect.
 * Respects user's prefers-reduced-motion preference.
 *
 * @example
 * ```tsx
 * <AnimatedList
 *   items={events}
 *   renderItem={(event) => <EventCard event={event} />}
 *   keyExtractor={(event) => event.id}
 *   staggerDelay={0.1}
 * />
 * ```
 */
export default function AnimatedList<T>({
  items,
  renderItem,
  keyExtractor,
  variant = 'fadeIn',
  staggerDelay = 0.05,
  emptyState,
  className = '',
  itemClassName = '',
  role,
  as = 'ul',
}: AnimatedListProps<T>) {
  const prefersReducedMotion = useReducedMotion();

  const containerVariants = createListContainerVariants(prefersReducedMotion ? 0 : staggerDelay);
  const itemVariant = listItemVariants[variant];
  const transition = prefersReducedMotion ? reducedMotionTransition : defaultTransition;

  const classes = [className, prefersReducedMotion ? 'motion-reduce' : '']
    .filter(Boolean)
    .join(' ');

  const itemClasses = [itemClassName].filter(Boolean).join(' ');

  // Render empty state if no items
  if (items.length === 0 && emptyState) {
    return <>{emptyState}</>;
  }

  const ListContainer = as === 'ul' ? motion.ul : motion.div;
  const ListItem = as === 'ul' ? motion.li : motion.div;

  return (
    <AnimatePresence>
      <ListContainer
        data-testid="animated-list"
        className={classes}
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        role={role}
      >
        {items.map((item, index) => (
          <ListItem
            key={keyExtractor(item, index)}
            data-testid="animated-list-item"
            className={itemClasses}
            variants={itemVariant}
            custom={index}
            transition={transition}
          >
            {renderItem(item, index)}
          </ListItem>
        ))}
      </ListContainer>
    </AnimatePresence>
  );
}
