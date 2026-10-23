/**
 * ModeSwitch — Easy / Advanced view mode switch (F4.9 — docs/uplevel/4n-modes.md).
 *
 * Mounted in Header (desktop & tablet), Sidebar drawer, and MobileBottomNav's
 * More sheet (phones).
 */

import { clsx } from 'clsx';

import { useViewMode } from '../../contexts/ViewModeContext';

export interface ModeSwitchProps {
  className?: string;
}

export default function ModeSwitch({ className }: ModeSwitchProps) {
  const { mode, setMode } = useViewMode();

  return (
    <div
      role="group"
      aria-label="View mode"
      data-testid="mode-switch"
      className={clsx(
        'inline-flex items-center rounded-lg border border-gray-800 bg-[#141414] p-0.5',
        className
      )}
    >
      <button
        type="button"
        onClick={() => setMode('easy')}
        aria-pressed={mode === 'easy'}
        data-testid="mode-switch-easy"
        className={clsx(
          'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
          mode === 'easy'
            ? 'bg-[#76B900] text-black'
            : 'text-gray-400 hover:bg-gray-800 hover:text-white'
        )}
      >
        Easy
      </button>
      <button
        type="button"
        onClick={() => setMode('advanced')}
        aria-pressed={mode === 'advanced'}
        data-testid="mode-switch-advanced"
        className={clsx(
          'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
          mode === 'advanced'
            ? 'bg-[#76B900] text-black'
            : 'text-gray-400 hover:bg-gray-800 hover:text-white'
        )}
      >
        Advanced
      </button>
    </div>
  );
}
