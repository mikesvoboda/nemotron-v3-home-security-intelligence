/**
 * BulkActionBar utility functions and pre-built action factories
 *
 * Separated from BulkActionBar.tsx to avoid react-refresh warnings
 * about exporting non-component values from component files.
 *
 * @module components/common/BulkActionBar.utils
 */

import { Download, Eye, EyeOff, Trash2 } from 'lucide-react';
import { createElement } from 'react';

import type { BulkAction } from './BulkActionBar';

/**
 * Create a "Mark Reviewed" action configuration
 */
export function createMarkReviewedAction(
  onClick: () => void,
  options: { loading?: boolean; disabled?: boolean } = {}
): BulkAction {
  return {
    id: 'mark-reviewed',
    label: 'Mark Reviewed',
    icon: createElement(Eye, { className: 'h-4 w-4' }),
    onClick,
    ...options,
  };
}

/**
 * Create a "Mark Not Reviewed" action configuration
 */
export function createMarkNotReviewedAction(
  onClick: () => void,
  options: { loading?: boolean; disabled?: boolean } = {}
): BulkAction {
  return {
    id: 'mark-not-reviewed',
    label: 'Mark Not Reviewed',
    icon: createElement(EyeOff, { className: 'h-4 w-4' }),
    onClick,
    ...options,
  };
}

/**
 * Create an "Export" action configuration
 */
export function createExportAction(
  onClick: () => void,
  options: { loading?: boolean; disabled?: boolean } = {}
): BulkAction {
  return {
    id: 'export',
    label: 'Export',
    icon: createElement(Download, { className: 'h-4 w-4' }),
    onClick,
    ...options,
  };
}

/**
 * Create a "Delete" action configuration
 */
export function createDeleteAction(
  onClick: () => void,
  options: { loading?: boolean; disabled?: boolean } = {}
): BulkAction {
  return {
    id: 'delete',
    label: 'Delete',
    icon: createElement(Trash2, { className: 'h-4 w-4' }),
    onClick,
    destructive: true,
    ...options,
  };
}
