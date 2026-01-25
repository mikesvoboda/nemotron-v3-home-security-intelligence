/**
 * ShortcutsHelpModal - Displays keyboard shortcuts reference
 *
 * Shows all available keyboard shortcuts when ? is pressed.
 * Organized by category: Global, Navigation, and List Navigation.
 * Uses focus trap for accessibility.
 */

import { X } from 'lucide-react';

import { useFocusTrap } from '../../hooks/useFocusTrap';

/**
 * Shortcut item definition
 */
interface ShortcutItem {
  /** Keyboard key(s) to display */
  keys: string[];
  /** Description of what the shortcut does */
  description: string;
}

/**
 * Shortcut group definition
 */
interface ShortcutGroup {
  /** Group title */
  title: string;
  /** Shortcuts in this group */
  items: ShortcutItem[];
}

/**
 * All available keyboard shortcuts organized by category
 */
const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    title: 'Global',
    items: [
      { keys: ['\u2318/Ctrl', 'K'], description: 'Open command palette' },
      { keys: ['?'], description: 'Show keyboard shortcuts' },
      { keys: ['Esc'], description: 'Close modal / Cancel' },
    ],
  },
  {
    title: 'Navigation',
    items: [
      { keys: ['g', 'd'], description: 'Go to Dashboard' },
      { keys: ['g', 't'], description: 'Go to Timeline' },
      { keys: ['g', 'e'], description: 'Go to Entities' },
      { keys: ['g', 'a'], description: 'Go to Alerts' },
      { keys: ['g', 's'], description: 'Go to Settings' },
      { keys: ['g', 'n'], description: 'Go to Analytics' },
      { keys: ['g', 'o'], description: 'Go to Logs' },
      { keys: ['g', 'y'], description: 'Go to System' },
    ],
  },
  {
    title: 'List Navigation',
    items: [
      { keys: ['j'], description: 'Move down / Next item' },
      { keys: ['k'], description: 'Move up / Previous item' },
      { keys: ['\u2191'], description: 'Move up (arrow)' },
      { keys: ['\u2193'], description: 'Move down (arrow)' },
      { keys: ['Home'], description: 'Jump to first item' },
      { keys: ['End'], description: 'Jump to last item' },
      { keys: ['Enter'], description: 'Select item' },
    ],
  },
];

/**
 * Props for ShortcutsHelpModal component
 */
export interface ShortcutsHelpModalProps {
  /** Whether the modal is open */
  open: boolean;
  /** Callback when modal should close */
  onClose: () => void;
}

/**
 * Renders a keyboard key
 */
function KeyBadge({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex min-w-[24px] items-center justify-center rounded bg-[#333] px-2 py-1 text-xs font-medium text-[#ccc]">
      {children}
    </kbd>
  );
}

/**
 * ShortcutsHelpModal component
 *
 * Displays a reference of all available keyboard shortcuts.
 * Uses focus trap for accessibility - focus is trapped within the modal
 * and returns to the trigger element when closed.
 */
export default function ShortcutsHelpModal({ open, onClose }: ShortcutsHelpModalProps) {
  // Use focus trap for accessibility
  const { containerRef } = useFocusTrap<HTMLDivElement>({
    isActive: open,
    onEscape: onClose,
    returnFocusOnDeactivate: true,
  });

  if (!open) {
    return null;
  }

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
        data-testid="modal-backdrop"
        aria-hidden="true"
      />

      {/* Modal content */}
      <div className="relative z-10 w-full max-w-2xl rounded-xl border border-[#2a2a2a] bg-[#1a1a1a] p-6 shadow-2xl">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-white">Keyboard Shortcuts</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-[#666] transition-colors hover:bg-[#2a2a2a] hover:text-white"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Shortcut groups */}
        <div className="grid gap-6 md:grid-cols-2">
          {SHORTCUT_GROUPS.map((group) => (
            <div key={group.title}>
              <h3 className="mb-3 text-sm font-medium uppercase tracking-wide text-[#76B900]">
                {group.title}
              </h3>
              <div className="space-y-2">
                {group.items.map((item, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between rounded-lg bg-[#222] px-3 py-2"
                  >
                    <span className="text-sm text-[#999]">{item.description}</span>
                    <div className="flex items-center gap-1">
                      {item.keys.map((key, keyIndex) => (
                        <span key={keyIndex} className="flex items-center">
                          {keyIndex > 0 && <span className="mx-1 text-xs text-[#666]">+</span>}
                          <KeyBadge>{key}</KeyBadge>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer hint */}
        <div className="mt-6 text-center text-xs text-[#666]">
          Press <KeyBadge>?</KeyBadge> anywhere to show this dialog
        </div>
      </div>
    </div>
  );
}
