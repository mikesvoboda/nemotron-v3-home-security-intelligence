/**
 * CommandPalette - cmd+k style command palette (F4.9 — docs/uplevel/4n-modes.md).
 *
 * Lists the current mode's hubs and tabs from `config/surfaces.ts` with their
 * keywords and shortcuts, and offers "Switch to Advanced" or "Switch to Easy".
 */

import { Command } from 'cmdk';
import { SlidersHorizontal } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, type ComponentType } from 'react';
import { useNavigate } from 'react-router-dom';

import { EASY_HUBS, HUBS, type Hub } from '../../config/surfaces';
import { useViewMode } from '../../contexts/ViewModeContext';

interface PaletteNavigationItem {
  name: string;
  path: string;
  shortcut: string;
  icon: ComponentType<{ className?: string }>;
  keywords?: string[];
}

function buildPaletteItems(hubs: readonly Hub[]): PaletteNavigationItem[] {
  const items: PaletteNavigationItem[] = [];
  const seenPaths = new Set<string>();

  for (const hub of hubs) {
    // Include a hub-level entry only when the hub has its own exact path (e.g.
    // "Settings" -> "/settings") or when its first tab is "/" ("Dashboard" -> "/").
    if (hub.id === 'dashboard' && hub.tabs.length > 0) {
      const firstTab = hub.tabs[0];
      items.push({
        name: 'Dashboard',
        path: '/',
        shortcut: firstTab.shortcut ?? '',
        icon: hub.icon,
        keywords: firstTab.keywords,
      });
      seenPaths.add('/');
    } else if (hub.exactPaths && hub.exactPaths.length > 0 && hub.tabs.length > 0) {
      const firstTab = hub.tabs[0];
      const hubPath = hub.exactPaths[0];
      items.push({
        name: hub.label,
        path: hubPath,
        shortcut: firstTab.shortcut ?? '',
        icon: hub.icon,
        keywords: firstTab.keywords,
      });
      seenPaths.add(hubPath);
    }

    for (const tab of hub.tabs) {
      if (seenPaths.has(tab.path)) {
        continue;
      }
      seenPaths.add(tab.path);
      items.push({
        name: tab.label,
        path: tab.path,
        shortcut: tab.shortcutPath ? '' : (tab.shortcut ?? ''),
        icon: tab.icon ?? hub.icon,
        keywords: Array.from(new Set([...(tab.keywords ?? []), hub.label.toLowerCase()])),
      });
    }
  }

  return items;
}

export interface CommandPaletteProps {
  /** Whether the palette is open */
  open: boolean;
  /** Callback when open state changes */
  onOpenChange: (open: boolean) => void;
}

export default function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { mode, setMode } = useViewMode();
  const inputRef = useRef<HTMLInputElement>(null);

  const navigationItems = useMemo(
    () => buildPaletteItems(mode === 'advanced' ? HUBS : EASY_HUBS),
    [mode]
  );

  const switchLabel = mode === 'easy' ? 'Switch to Advanced' : 'Switch to Easy';
  const nextMode = mode === 'easy' ? 'advanced' : 'easy';

  useEffect(() => {
    if (open && inputRef.current) {
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

  const handleToggleMode = useCallback(() => {
    setMode(nextMode);
    onOpenChange(false);
  }, [setMode, nextMode, onOpenChange]);

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
          const combinedValue =
            keywords && keywords.length > 0 ? `${value} ${keywords.join(' ')}` : value;
          const normalizedValue = combinedValue.toLowerCase();
          const normalizedSearch = search.toLowerCase();

          const words = normalizedValue.split(' ');
          if (words.some((word) => word.startsWith(normalizedSearch))) {
            return 1;
          }

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
            {navigationItems.map((item) => (
              <Command.Item
                key={`${item.name}-${item.path}`}
                value={item.name}
                keywords={item.keywords}
                onSelect={() => handleSelect(item.path)}
                className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-white transition-colors aria-selected:bg-[#76B900]/20 aria-selected:text-[#76B900]"
              >
                <item.icon className="h-4 w-4 text-[#888]" />
                <span className="flex-1">{item.name}</span>
                {item.shortcut && (
                  <kbd className="rounded bg-[#2a2a2a] px-2 py-0.5 text-xs text-[#888]">
                    {item.shortcut}
                  </kbd>
                )}
              </Command.Item>
            ))}

            <Command.Item
              key={switchLabel}
              value={switchLabel}
              keywords={['mode', 'view', 'easy', 'advanced', 'blueprint']}
              onSelect={handleToggleMode}
              className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-white transition-colors aria-selected:bg-[#76B900]/20 aria-selected:text-[#76B900]"
            >
              <SlidersHorizontal className="h-4 w-4 text-[#888]" />
              <span className="flex-1">{switchLabel}</span>
            </Command.Item>
          </Command.Group>
        </Command.List>
      </Command>
    </div>
  );
}
