/**
 * AdvancedOnly — Renders children only when the active view mode is Advanced (F4.9).
 */

import { useViewMode } from '../../contexts/ViewModeContext';

import type { ReactNode } from 'react';

export interface AdvancedOnlyProps {
  children: ReactNode;
}

export default function AdvancedOnly({ children }: AdvancedOnlyProps) {
  const { mode } = useViewMode();
  if (mode !== 'advanced') {
    return null;
  }
  return <>{children}</>;
}
