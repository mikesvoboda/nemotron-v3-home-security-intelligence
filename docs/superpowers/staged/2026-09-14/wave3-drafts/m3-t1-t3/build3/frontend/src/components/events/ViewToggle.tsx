import { Calendar, Grid2x2, List } from 'lucide-react';
import { useCallback } from 'react';

/** View mode options for the timeline display */
export type ViewMode = 'grid' | 'list' | 'grouped';

export interface ViewToggleProps {
  /** Current active view mode */
  viewMode: ViewMode;
  /** Callback when view mode changes */
  onChange: (mode: ViewMode) => void;
  /** Optional localStorage key to persist preference */
  persistKey?: string;
  /** Optional className for additional styling */
  className?: string;
}

/**
 * ViewToggle component provides a toggle between grid and list view modes.
 * Used on the timeline page to switch between card grid and compact list views.
 */
export default function ViewToggle({
  viewMode,
  onChange,
  persistKey,
  className = '',
}: ViewToggleProps) {
  const handleClick = useCallback(
    (mode: ViewMode) => {
      if (mode === viewMode) return; // Don't trigger change for already active mode

      onChange(mode);

      // Persist to localStorage if key is provided
      if (persistKey && typeof window !== 'undefined') {
        try {
          window.localStorage.setItem(persistKey, JSON.stringify(mode));
        } catch (error) {
          console.warn(`Error saving view preference to localStorage:`, error);
        }
      }
    },
    [viewMode, onChange, persistKey]
  );

  const baseButtonClass =
    'flex items-center justify-center p-2 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-1 focus:ring-offset-[#1F1F1F]';
  const activeClass = 'bg-[#76B900] text-black';
  const inactiveClass = 'bg-[#1A1A1A] text-gray-400 hover:text-white hover:bg-[#252525]';

  return (
    <div
      role="group"
      aria-label="View toggle"
      className={`flex items-center gap-1 rounded-lg border border-gray-700 bg-[#1A1A1A] p-1 ${className}`}
    >
      <button
        type="button"
        onClick={() => handleClick('grid')}
        className={`${baseButtonClass} ${viewMode === 'grid' ? activeClass : inactiveClass}`}
        aria-label="Switch to grid view"
        aria-pressed={viewMode === 'grid'}
      >
        <Grid2x2 className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={() => handleClick('list')}
        className={`${baseButtonClass} ${viewMode === 'list' ? activeClass : inactiveClass}`}
        aria-label="Switch to list view"
        aria-pressed={viewMode === 'list'}
      >
        <List className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={() => handleClick('grouped')}
        className={`${baseButtonClass} ${viewMode === 'grouped' ? activeClass : inactiveClass}`}
        aria-label="Switch to grouped view"
        aria-pressed={viewMode === 'grouped'}
      >
        <Calendar className="h-4 w-4" />
      </button>
    </div>
  );
}
