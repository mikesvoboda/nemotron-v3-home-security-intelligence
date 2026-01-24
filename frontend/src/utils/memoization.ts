/**
 * React.memo custom equality utilities for standardized memoization patterns
 *
 * This module provides reusable equality functions for React.memo that go beyond
 * shallow comparison. Use these when components receive complex props that would
 * cause unnecessary re-renders with default shallow comparison.
 *
 * Performance Guidelines:
 * - Only use custom equality when you've measured a performance issue
 * - Shallow comparison (default React.memo) is often sufficient
 * - Deep equality checks have their own cost - use judiciously
 * - Prefer restructuring props to avoid deep comparisons when possible
 *
 * @module utils/memoization
 */

/**
 * Performs a shallow equality check between two values.
 * Useful as a building block for custom equality functions.
 *
 * @param a - First value
 * @param b - Second value
 * @returns true if values are shallowly equal
 */
export function shallowEqual<T extends object>(
  a: T | null | undefined,
  b: T | null | undefined
): boolean {
  if (a === b) return true;
  if (a === null || b === null) return false;
  if (a === undefined || b === undefined) return false;

  const keysA = Object.keys(a);
  const keysB = Object.keys(b);

  if (keysA.length !== keysB.length) return false;

  const objA = a as Record<string, unknown>;
  const objB = b as Record<string, unknown>;

  for (const key of keysA) {
    if (objA[key] !== objB[key]) return false;
  }

  return true;
}

/**
 * Creates a custom equality function that compares only specific props.
 *
 * Use when you know certain props don't affect rendering and can be ignored,
 * or when some props are always new references but have stable values.
 *
 * @example
 * ```tsx
 * interface CardProps {
 *   id: string;
 *   title: string;
 *   onClick: () => void;  // New reference every render, but behavior is stable
 *   data: ComplexObject;  // Always same reference from parent's useMemo
 * }
 *
 * // Only re-render when id or title changes, ignore onClick and data
 * const MemoizedCard = memo(Card, createPropsComparator(['id', 'title']));
 * ```
 *
 * @param propsToCompare - Array of prop keys to compare
 * @returns Equality function for React.memo
 */
export function createPropsComparator<T extends object>(
  propsToCompare: (keyof T)[]
): (prevProps: T, nextProps: T) => boolean {
  return (prevProps: T, nextProps: T): boolean => {
    for (const prop of propsToCompare) {
      if (prevProps[prop] !== nextProps[prop]) {
        return false;
      }
    }
    return true;
  };
}

/**
 * Creates a custom equality function that ignores specific props.
 *
 * Use when most props matter for rendering but certain ones (like callbacks
 * or refs) don't affect the visual output.
 *
 * @example
 * ```tsx
 * interface ListItemProps {
 *   id: string;
 *   name: string;
 *   selected: boolean;
 *   onSelect: (id: string) => void;  // Ignore - always new reference
 *   onDelete: (id: string) => void;  // Ignore - always new reference
 * }
 *
 * const MemoizedListItem = memo(ListItem, createPropsExcluder(['onSelect', 'onDelete']));
 * ```
 *
 * @param propsToIgnore - Array of prop keys to ignore in comparison
 * @returns Equality function for React.memo
 */
export function createPropsExcluder<T extends object>(
  propsToIgnore: (keyof T)[]
): (prevProps: T, nextProps: T) => boolean {
  const ignoreSet = new Set(propsToIgnore);

  return (prevProps: T, nextProps: T): boolean => {
    const prevKeys = Object.keys(prevProps) as (keyof T)[];
    const nextKeys = Object.keys(nextProps) as (keyof T)[];

    // Filter out ignored keys
    const prevFiltered = prevKeys.filter((k) => !ignoreSet.has(k));
    const nextFiltered = nextKeys.filter((k) => !ignoreSet.has(k));

    if (prevFiltered.length !== nextFiltered.length) return false;

    for (const key of prevFiltered) {
      if (prevProps[key] !== nextProps[key]) {
        return false;
      }
    }

    return true;
  };
}

/**
 * Deep equality check for arrays. Only goes one level deep into the array.
 *
 * @param a - First array
 * @param b - Second array
 * @returns true if arrays have same length and elements are strictly equal
 */
export function arrayShallowEqual<T>(a: T[] | null | undefined, b: T[] | null | undefined): boolean {
  if (a === b) return true;
  if (a === null || b === null) return false;
  if (a === undefined || b === undefined) return false;
  if (a.length !== b.length) return false;

  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }

  return true;
}

/**
 * Creates a comparator for props that include an array field.
 *
 * @example
 * ```tsx
 * interface GridProps {
 *   items: Item[];
 *   selectedIds: string[];
 *   onItemClick: (id: string) => void;
 * }
 *
 * // Compare arrays by value, not reference
 * const MemoizedGrid = memo(Grid, createArrayPropsComparator({
 *   arrayProps: ['items', 'selectedIds'],
 *   ignoreProps: ['onItemClick'],
 * }));
 * ```
 */
export interface ArrayPropsComparatorOptions<T extends object> {
  /**
   * Props that are arrays and should be compared by shallow array equality
   */
  arrayProps: (keyof T)[];

  /**
   * Props to completely ignore in comparison
   */
  ignoreProps?: (keyof T)[];
}

/**
 * Creates a comparator that handles array props with shallow array comparison.
 *
 * @param options - Configuration for array comparison
 * @returns Equality function for React.memo
 */
export function createArrayPropsComparator<T extends object>(
  options: ArrayPropsComparatorOptions<T>
): (prevProps: T, nextProps: T) => boolean {
  const { arrayProps, ignoreProps = [] } = options;
  const arraySet = new Set(arrayProps);
  const ignoreSet = new Set(ignoreProps);

  return (prevProps: T, nextProps: T): boolean => {
    const keys = new Set([...Object.keys(prevProps), ...Object.keys(nextProps)]) as Set<keyof T>;

    for (const key of keys) {
      // Skip ignored props
      if (ignoreSet.has(key)) continue;

      const prevVal = prevProps[key];
      const nextVal = nextProps[key];

      // Handle array props with shallow array comparison
      if (arraySet.has(key)) {
        if (!arrayShallowEqual(prevVal as unknown[], nextVal as unknown[])) {
          return false;
        }
        continue;
      }

      // Standard equality for non-array props
      if (prevVal !== nextVal) {
        return false;
      }
    }

    return true;
  };
}

/**
 * Standard equality comparator for list item components.
 *
 * List items typically receive:
 * - Data props (id, name, etc.) - compare by value
 * - Callback props (onClick, onSelect) - ignore (stable via useCallback in parent)
 * - Selection state (selected, checked) - compare by value
 *
 * This comparator ignores common callback prop names and compares everything else.
 *
 * @example
 * ```tsx
 * const MemoizedJobsListItem = memo(JobsListItem, listItemPropsComparator);
 * ```
 */
export const listItemPropsComparator = createPropsExcluder([
  'onClick',
  'onSelect',
  'onDelete',
  'onEdit',
  'onToggle',
  'onChange',
  'onDoubleClick',
  'onContextMenu',
  'onDragStart',
  'onDragEnd',
  'onDrop',
] as never[]);

/**
 * Standard equality comparator for card components.
 *
 * Cards typically have:
 * - Content props (title, description, data) - compare by value
 * - Action callbacks - ignore
 * - Optional thumbnail/image URLs - compare by value
 *
 * @example
 * ```tsx
 * const MemoizedEventCard = memo(EventCard, cardPropsComparator);
 * ```
 */
export const cardPropsComparator = createPropsExcluder([
  'onClick',
  'onViewDetails',
  'onDismiss',
  'onSnooze',
  'onAcknowledge',
  'onSelect',
  'onSelectChange',
  'onMarkReviewed',
  'onEdit',
  'onDelete',
] as never[]);

/**
 * Type guard to check if a value is a plain object (not null, array, or other object types).
 */
function isPlainObject(value: unknown): value is Record<string, unknown> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    Object.prototype.toString.call(value) === '[object Object]'
  );
}

/**
 * Deep equality check for nested objects. Use sparingly as it's expensive.
 *
 * @param a - First value
 * @param b - Second value
 * @param maxDepth - Maximum recursion depth (default 3)
 * @returns true if values are deeply equal
 */
export function deepEqual(a: unknown, b: unknown, maxDepth = 3): boolean {
  if (a === b) return true;
  if (maxDepth <= 0) return a === b;

  // Handle null/undefined
  if (a === null || b === null) return a === b;
  if (a === undefined || b === undefined) return a === b;

  // Handle arrays
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    return a.every((item, index) => deepEqual(item, b[index], maxDepth - 1));
  }

  // Handle plain objects
  if (isPlainObject(a) && isPlainObject(b)) {
    const keysA = Object.keys(a);
    const keysB = Object.keys(b);

    if (keysA.length !== keysB.length) return false;

    return keysA.every((key) => deepEqual(a[key], b[key], maxDepth - 1));
  }

  // Primitives or mismatched types
  return a === b;
}

/**
 * Creates a comparator with deep equality for specific props.
 *
 * WARNING: Deep equality is expensive. Only use when you have complex nested
 * data structures that are recreated on each render but have the same values.
 *
 * @example
 * ```tsx
 * interface ChartProps {
 *   data: { x: number; y: number }[];
 *   config: { colors: string[]; options: ChartOptions };
 *   onPointClick: (point: Point) => void;
 * }
 *
 * // Deep compare data and config, ignore callback
 * const MemoizedChart = memo(Chart, createDeepPropsComparator({
 *   deepProps: ['data', 'config'],
 *   ignoreProps: ['onPointClick'],
 * }));
 * ```
 */
export interface DeepPropsComparatorOptions<T extends object> {
  /**
   * Props that should be compared with deep equality
   */
  deepProps: (keyof T)[];

  /**
   * Props to completely ignore in comparison
   */
  ignoreProps?: (keyof T)[];

  /**
   * Maximum depth for deep comparison (default 3)
   */
  maxDepth?: number;
}

/**
 * Creates a comparator that uses deep equality for specific props.
 *
 * @param options - Configuration for deep comparison
 * @returns Equality function for React.memo
 */
export function createDeepPropsComparator<T extends object>(
  options: DeepPropsComparatorOptions<T>
): (prevProps: T, nextProps: T) => boolean {
  const { deepProps, ignoreProps = [], maxDepth = 3 } = options;
  const deepSet = new Set(deepProps);
  const ignoreSet = new Set(ignoreProps);

  return (prevProps: T, nextProps: T): boolean => {
    const keys = new Set([...Object.keys(prevProps), ...Object.keys(nextProps)]) as Set<keyof T>;

    for (const key of keys) {
      // Skip ignored props
      if (ignoreSet.has(key)) continue;

      const prevVal = prevProps[key];
      const nextVal = nextProps[key];

      // Handle deep props with deep equality
      if (deepSet.has(key)) {
        if (!deepEqual(prevVal, nextVal, maxDepth)) {
          return false;
        }
        continue;
      }

      // Standard equality for other props
      if (prevVal !== nextVal) {
        return false;
      }
    }

    return true;
  };
}
