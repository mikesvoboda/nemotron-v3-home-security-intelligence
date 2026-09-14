/**
 * CommandPalette - cmd+k style command palette
 *
 * Provides quick navigation and actions using the cmdk library.
 * Supports:
 * - Fuzzy search for navigation items
 * - Keyboard navigation with arrow keys
 * - Displays keyboard shortcuts for each action
 */

import { Command } from 'cmdk';
import {
  LayoutDashboard,
  Clock,
  BarChart3,
  Bell,
  Users,
  FileText,
  Activity,
  Settings,
  Brain,
  ClipboardList,
} from 'lucide-react';
import { useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

import type { LucideIcon } from 'lucide-react';

/**
 * Navigation item definition
 */
interface NavigationItem {
  /** Display name */
  name: string;
  /** Route path */
  path: string;
  /** Keyboard shortcut (chord) */
  shortcut: string;
  /** Icon component */
  icon: LucideIcon;
  /** Optional keywords for search */
  keywords?: string[];
}

/**
 * Navigation items available in the command palette
 */
const NAVIGATION_ITEMS: NavigationItem[] = [
  {
    name: 'Dashboard',
    path: '/',
    shortcut: 'g d',
    icon: LayoutDashboard,
    keywords: ['home', 'main', 'overview', 'cameras'],
  },
  {
    name: 'Timeline',
    path: '/timeline',
    shortcut: 'g t',
    icon: Clock,
    keywords: ['events', 'history', 'time'],
  },
  {
    name: 'Analytics',
    path: '/analytics',
    shortcut: 'g n',
    icon: BarChart3,
    keywords: ['charts', 'graphs', 'statistics', 'stats'],
  },
  {
    name: 'Alerts',
    path: '/alerts',
    shortcut: 'g a',
    icon: Bell,
    keywords: ['notifications', 'warnings'],
  },
  {
    name: 'Entities',
    path: '/entities',
    shortcut: 'g e',
    icon: Users,
    keywords: ['people', 'objects', 'detection'],
  },
  {
    name: 'Logs',
    path: '/logs',
    shortcut: 'g o',
    icon: FileText,
    keywords: ['system', 'debug', 'output'],
  },
  {
    name: 'System',
    path: '/system',
    shortcut: 'g y',
    icon: Activity,
    keywords: ['monitoring', 'health', 'status', 'performance'],
  },
  {
    name: 'AI Performance',
    path: '/ai',
    shortcut: '',
    icon: Brain,
    keywords: ['model', 'inference', 'gpu', 'nemotron', 'rtdetr'],
  },
  {
    name: 'Audit Log',
    path: '/audit',
    shortcut: '',
    icon: ClipboardList,
    keywords: ['history', 'changes', 'tracking'],
  },
  {
    name: 'Settings',
    path: '/settings',
    shortcut: 'g s',
    icon: Settings,
    keywords: ['preferences', 'configuration', 'options'],
  },
];

/**
 * Props for CommandPalette component
 */
export interface CommandPaletteProps {
  /** Whether the palette is open */
  open: boolean;
  /** Callback when open state changes */
  onOpenChange: (open: boolean) => void;
}

/**
 * CommandPalette component
 *
 * Provides a searchable command palette for quick navigation.
 */
export default function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input when opened
  useEffect(() => {
    if (open && inputRef.current) {
      // Small delay to ensure the dialog is rendered
      setTimeout(() => {
        inputRef.current?.focus();
      }, 0);
    }
  }, [open]);

  const handleSelect = useCallback(
    (path: string) => {
      void navigate(path);
      onOpenChange(false);
    },
    [navigate, onOpenChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        onOpenChange(false);
      }
    },
    [onOpenChange]
  );

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
        aria-hidden="true"
      />

      {/* Command palette container */}
      <Command
        className="relative w-full max-w-lg overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1a1a1a] shadow-2xl"
        onKeyDown={handleKeyDown}
        loop
        filter={(value, search, keywords) => {
          // Custom filter for case-insensitive fuzzy matching
          // Combine value with keywords for search (similar to cmdk's default behavior)
          const combinedValue =
            keywords && keywords.length > 0 ? `${value} ${keywords.join(' ')}` : value;
          const normalizedValue = combinedValue.toLowerCase();
          const normalizedSearch = search.toLowerCase();

          // Check if any word in the value starts with the search term
          const words = normalizedValue.split(' ');
          if (words.some((word) => word.startsWith(normalizedSearch))) {
            return 1;
          }

          // Check if the value contains the search term
          if (normalizedValue.includes(normalizedSearch)) {
            return 0.5;
          }

          return 0;
        }}
      >
        {/* Search input */}
        <div className="flex items-center border-b border-[#2a2a2a] px-4">
          <svg
            className="mr-3 h-5 w-5 text-[#666]"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <Command.Input
            ref={inputRef}
            placeholder="Type to search..."
            className="h-14 flex-1 bg-transparent text-white placeholder-[#666] outline-none"
          />
          <kbd className="rounded bg-[#2a2a2a] px-2 py-1 text-xs text-[#ccc]">ESC</kbd>
        </div>

        {/* Results list */}
        <Command.List className="max-h-[300px] overflow-y-auto p-2">
          <Command.Empty className="py-6 text-center text-sm text-[#666]">
            No results found.
          </Command.Empty>

          <Command.Group
            heading="Navigation"
            className="px-2 [&_[cmdk-group-heading]]:mb-2 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-[#666]"
          >
            {NAVIGATION_ITEMS.map((item) => (
              <Command.Item
                key={item.path}
                value={item.name}
                keywords={item.keywords}
                onSelect={() => handleSelect(item.path)}
                className="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm text-[#999] transition-colors hover:bg-[#2a2a2a] hover:text-white aria-selected:bg-[#2a2a2a] aria-selected:text-white"
              >
                <div className="flex items-center gap-3">
                  <item.icon className="h-4 w-4" aria-hidden="true" />
                  <span>{item.name}</span>
                </div>
                {item.shortcut && (
                  <kbd className="rounded bg-[#333] px-2 py-0.5 text-xs text-[#ccc]">
                    {item.shortcut}
                  </kbd>
                )}
              </Command.Item>
            ))}
          </Command.Group>
        </Command.List>

        {/* Footer hint */}
        <div className="flex items-center justify-between border-t border-[#2a2a2a] px-4 py-2 text-xs text-[#999]">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              <kbd className="rounded bg-[#2a2a2a] px-1.5 py-0.5 text-[#ccc]">↑</kbd>
              <kbd className="rounded bg-[#2a2a2a] px-1.5 py-0.5 text-[#ccc]">↓</kbd>
              <span>Navigate</span>
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded bg-[#2a2a2a] px-1.5 py-0.5 text-[#ccc]">↵</kbd>
              <span>Select</span>
            </span>
          </div>
          <span className="flex items-center gap-1">
            <kbd className="rounded bg-[#2a2a2a] px-1.5 py-0.5 text-[#ccc]">?</kbd>
            <span>Shortcuts help</span>
          </span>
        </div>
      </Command>
    </div>
  );
}
