/**
 * CollapsibleSection - Collapsible section container with localStorage persistence
 *
 * Provides a collapsible container with title and toggle button.
 * Persists collapsed/expanded state to localStorage for consistency across sessions.
 */

import { ChevronDown, ChevronRight } from 'lucide-react';
import { ReactNode } from 'react';

import { useLocalStorage } from '../../hooks/useLocalStorage';

export interface CollapsibleSectionProps {
  /** Section title displayed in header */
  title: string;
  /** Unique key for localStorage persistence */
  storageKey: string;
  /** Content to display when expanded */
  children: ReactNode;
  /** Default expanded state (default: true) */
  defaultExpanded?: boolean;
  /** Additional CSS classes for container */
  className?: string;
}

export default function CollapsibleSection({
  title,
  storageKey,
  children,
  defaultExpanded = true,
  className = '',
}: CollapsibleSectionProps) {
  const [isExpanded, setIsExpanded] = useLocalStorage<boolean>(
    `collapsible-${storageKey}`,
    defaultExpanded
  );

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  return (
    <div className={className}>
      {/* Header with toggle button */}
      <button
        onClick={toggleExpanded}
        className="mb-3 flex w-full items-center justify-between rounded-lg bg-[#1A1A1A] px-4 py-3 text-left transition-colors hover:bg-[#252525]"
        aria-expanded={isExpanded}
        aria-controls={`collapsible-content-${storageKey}`}
        type="button"
      >
        <span className="text-base font-semibold text-white">{title}</span>
        {isExpanded ? (
          <ChevronDown className="lucide-chevron-down h-5 w-5 text-gray-400" aria-hidden="true" />
        ) : (
          <ChevronRight
            className="lucide-chevron-right h-5 w-5 text-gray-400"
            aria-hidden="true"
          />
        )}
      </button>

      {/* Content */}
      {isExpanded && (
        <div id={`collapsible-content-${storageKey}`} role="region" aria-labelledby={storageKey}>
          {children}
        </div>
      )}
    </div>
  );
}
