/**
 * EventSearch - Search input with React 19 useTransition for non-blocking updates.
 *
 * The input updates immediately (high priority) while the search/filter
 * operation is wrapped in startTransition (low priority), keeping the
 * UI responsive during expensive operations.
 *
 * @module components/events/EventSearch
 * @see NEM-3749 - React 19 useTransition for non-blocking search/filter
 */

import { clsx } from 'clsx';
import { Loader2, Search, X } from 'lucide-react';
import { memo, useCallback, useTransition } from 'react';

export interface EventSearchProps {
  /** Current search query value */
  value: string;
  /** Callback when search query changes (wrapped in startTransition) */
  onChange: (value: string) => void;
  /** Placeholder text */
  placeholder?: string;
  /** Additional CSS classes */
  className?: string;
  /** Whether to show the search icon */
  showIcon?: boolean;
}

/**
 * EventSearch component with React 19 useTransition for non-blocking updates.
 *
 * Uses useTransition to mark search/filter operations as low priority,
 * keeping the UI responsive during expensive re-renders.
 *
 * @example
 * ```tsx
 * const [searchQuery, setSearchQuery] = useState('');
 *
 * <EventSearch
 *   value={searchQuery}
 *   onChange={setSearchQuery}
 *   placeholder="Search events..."
 * />
 * ```
 */
const EventSearch = memo(function EventSearch({
  value,
  onChange,
  placeholder = 'Search events...',
  className,
  showIcon = true,
}: EventSearchProps) {
  // React 19 useTransition for non-blocking filter updates
  const [isPending, startTransition] = useTransition();

  /**
   * Handle input changes.
   * Wrapped in startTransition to keep UI responsive during expensive filtering.
   */
  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = e.target.value;
      startTransition(() => {
        onChange(newValue);
      });
    },
    [onChange]
  );

  /**
   * Clear the search input.
   * Also wrapped in startTransition for consistency.
   */
  const handleClear = useCallback(() => {
    startTransition(() => {
      onChange('');
    });
  }, [onChange]);

  /**
   * Handle keyboard events.
   * - Escape: Clear the search
   */
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Escape') {
        handleClear();
      }
    },
    [handleClear]
  );

  return (
    <div className={clsx('relative', className)}>
      {/* Search icon */}
      {showIcon && (
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
      )}

      {/* Search input */}
      <input
        type="text"
        value={value}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        aria-label="Search events"
        className={clsx(
          'w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2.5 text-sm text-white placeholder-gray-500',
          'focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]',
          showIcon ? 'pl-10 pr-10' : 'px-4 pr-10'
        )}
      />

      {/* Loading indicator and clear button */}
      <div className="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-1">
        {/* Loading spinner when transition is pending */}
        {isPending && (
          <Loader2
            className="h-4 w-4 animate-spin text-[#76B900]"
            data-testid="search-loading-indicator"
            aria-label="Searching"
          />
        )}

        {/* Clear button when there's content */}
        {value && !isPending && (
          <button
            type="button"
            onClick={handleClear}
            className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
});

export default EventSearch;
