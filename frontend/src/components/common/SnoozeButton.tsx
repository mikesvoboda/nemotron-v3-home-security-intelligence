/**
 * SnoozeButton - Dropdown button for snoozing events
 *
 * Provides quick snooze options (15 min, 1 hour, 4 hours, 24 hours)
 * and an unsnooze option when the event is currently snoozed.
 *
 * NEM-3640: Event Snooze Feature
 *
 * @example
 * ```tsx
 * <SnoozeButton
 *   snoozeUntil={event.snooze_until}
 *   onSnooze={(seconds) => handleSnooze(eventId, seconds)}
 *   onUnsnooze={() => handleUnsnooze(eventId)}
 * />
 * ```
 */

import { clsx } from 'clsx';
import { BellOff, ChevronDown, Moon } from 'lucide-react';
import { memo, useState, useRef, useEffect } from 'react';

import { isSnoozed, SNOOZE_OPTIONS, getSnoozeStatusMessage } from '../../utils/snooze';

// ============================================================================
// Types
// ============================================================================

export interface SnoozeButtonProps {
  /** ISO timestamp until which the event is snoozed (null if not snoozed) */
  snoozeUntil?: string | null;

  /** Callback when a snooze duration is selected (seconds) */
  onSnooze: (seconds: number) => void;

  /** Callback when unsnooze is clicked */
  onUnsnooze: () => void;

  /** Whether the snooze operation is in progress */
  isLoading?: boolean;

  /** Size variant */
  size?: 'sm' | 'md' | 'lg';

  /** Additional CSS classes */
  className?: string;

  /** Whether the button is disabled */
  disabled?: boolean;
}

// ============================================================================
// Component
// ============================================================================

/**
 * SnoozeButton displays a dropdown with snooze duration options.
 *
 * When the event is already snoozed, shows the current snooze status
 * and provides an option to unsnooze.
 */
const SnoozeButton = memo(function SnoozeButton({
  snoozeUntil,
  onSnooze,
  onUnsnooze,
  isLoading = false,
  size = 'md',
  className,
  disabled = false,
}: SnoozeButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const currentlySnoozed = isSnoozed(snoozeUntil);
  const snoozeStatus = currentlySnoozed ? getSnoozeStatusMessage(snoozeUntil) : '';

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Close dropdown on Escape key
  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false);
        buttonRef.current?.focus();
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen]);

  // Handle snooze selection
  const handleSnooze = (seconds: number) => {
    onSnooze(seconds);
    setIsOpen(false);
  };

  // Handle unsnooze
  const handleUnsnooze = () => {
    onUnsnooze();
    setIsOpen(false);
  };

  // Size-based styling
  const sizeClasses = {
    sm: {
      button: 'px-2 py-1 text-xs gap-1',
      icon: 'w-3.5 h-3.5',
      dropdown: 'w-36',
      option: 'px-3 py-1.5 text-xs',
    },
    md: {
      button: 'px-3 py-2 text-sm gap-1.5',
      icon: 'w-4 h-4',
      dropdown: 'w-40',
      option: 'px-3 py-2 text-sm',
    },
    lg: {
      button: 'px-4 py-2.5 text-base gap-2',
      icon: 'w-5 h-5',
      dropdown: 'w-48',
      option: 'px-4 py-2.5 text-base',
    },
  }[size];

  return (
    <div ref={dropdownRef} className={clsx('relative inline-block', className)}>
      {/* Dropdown Trigger Button */}
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled || isLoading}
        aria-expanded={isOpen}
        aria-haspopup="menu"
        aria-label={currentlySnoozed ? `${snoozeStatus}. Click to change.` : 'Snooze event'}
        className={clsx(
          // Base styles
          'inline-flex items-center justify-center rounded-lg font-medium',
          'transition-all duration-200',
          // Color scheme based on snooze state
          currentlySnoozed
            ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 hover:bg-indigo-500/30'
            : 'bg-gray-700/50 text-gray-300 border border-gray-700 hover:bg-gray-700 hover:border-gray-600',
          // Focus states
          'focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
          // Disabled/loading states
          (disabled || isLoading) && 'opacity-50 cursor-not-allowed',
          // Size classes
          sizeClasses.button
        )}
        data-testid="snooze-button"
      >
        <Moon className={sizeClasses.icon} aria-hidden="true" />
        <span>{currentlySnoozed ? 'Snoozed' : 'Snooze'}</span>
        <ChevronDown
          className={clsx(sizeClasses.icon, 'transition-transform', isOpen && 'rotate-180')}
          aria-hidden="true"
        />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          className={clsx(
            'absolute right-0 z-20 mt-1 rounded-lg',
            'bg-[#1F1F1F] border border-gray-700 shadow-lg',
            'py-1',
            sizeClasses.dropdown
          )}
          role="menu"
          aria-orientation="vertical"
          data-testid="snooze-dropdown"
        >
          {/* Snooze Status (if currently snoozed) */}
          {currentlySnoozed && snoozeStatus && (
            <div className="px-3 py-2 text-xs text-indigo-400/80 border-b border-gray-700">
              {snoozeStatus}
            </div>
          )}

          {/* Unsnooze option (if currently snoozed) */}
          {currentlySnoozed && (
            <button
              type="button"
              onClick={handleUnsnooze}
              disabled={isLoading}
              className={clsx(
                'w-full flex items-center gap-2 text-left',
                'text-red-400 hover:bg-red-500/10',
                'transition-colors',
                sizeClasses.option
              )}
              role="menuitem"
              data-testid="unsnooze-option"
            >
              <BellOff className={sizeClasses.icon} aria-hidden="true" />
              <span>Unsnooze</span>
            </button>
          )}

          {/* Divider between unsnooze and duration options */}
          {currentlySnoozed && (
            <div className="my-1 border-t border-gray-700" role="separator" />
          )}

          {/* Snooze duration label */}
          <div className="px-3 py-1 text-xs font-medium text-gray-500 uppercase tracking-wider">
            {currentlySnoozed ? 'Change duration' : 'Snooze for'}
          </div>

          {/* Snooze duration options */}
          {SNOOZE_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => handleSnooze(option.value)}
              disabled={isLoading}
              className={clsx(
                'w-full flex items-center gap-2 text-left',
                'text-gray-300 hover:bg-gray-700/50 hover:text-white',
                'transition-colors',
                sizeClasses.option
              )}
              role="menuitem"
              data-testid={`snooze-option-${option.value}`}
            >
              <Moon className={clsx(sizeClasses.icon, 'text-gray-500')} aria-hidden="true" />
              <span>{option.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
});

export default SnoozeButton;
