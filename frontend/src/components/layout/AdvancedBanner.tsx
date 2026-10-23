/**
 * AdvancedBanner — Displayed when an Advanced page is opened by URL in Easy mode
 * (F4.9 — docs/uplevel/4n-modes.md).
 */

import { Link, useLocation } from 'react-router-dom';

import { modeOfPath } from '../../config/surfaces';
import { useViewMode } from '../../contexts/ViewModeContext';

export default function AdvancedBanner() {
  const { mode, setMode } = useViewMode();
  const location = useLocation();
  const pathMode = modeOfPath(location.pathname);

  if (mode !== 'easy' || pathMode !== 'advanced') {
    return null;
  }

  return (
    <div
      role="region"
      aria-label="Advanced page notice"
      data-testid="advanced-page-banner"
      className="mx-4 mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-500/40 bg-amber-950/30 px-4 py-2.5 text-sm text-amber-200"
    >
      <span className="font-medium">This is an Advanced page</span>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => setMode('advanced')}
          data-testid="banner-switch-to-advanced"
          className="rounded-md bg-[#76B900] px-3 py-1 text-xs font-semibold text-black transition-colors hover:bg-[#8AD000]"
        >
          Switch to Advanced
        </button>
        <Link
          to="/"
          data-testid="banner-back-to-home"
          className="rounded-md border border-gray-700 bg-gray-800 px-3 py-1 text-xs font-medium text-gray-200 transition-colors hover:bg-gray-700 hover:text-white"
        >
          Back to Home
        </Link>
      </div>
    </div>
  );
}
