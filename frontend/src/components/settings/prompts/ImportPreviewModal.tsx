/**
 * ImportPreviewModal - Preview import changes before applying
 *
 * Shows a modal with:
 * - File name being imported
 * - Summary of models affected
 * - Per-model diff views
 * - Cancel and Apply Import buttons
 *
 * @see NEM-2699 - Implement prompt import/export with preview diffs
 */

import { Dialog, DialogPanel, Title, Text, Button, Callout } from '@tremor/react';
import { X, AlertTriangle, FileJson, CheckCircle } from 'lucide-react';

import ConfigDiffView from './ConfigDiffView';

import type { PromptsImportPreviewResponse } from '../../../types/promptManagement';

// ============================================================================
// Types
// ============================================================================

export interface ImportPreviewModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** Preview data from the import preview API */
  previewData: PromptsImportPreviewResponse | null;
  /** Name of the file being imported */
  fileName: string;
  /** Callback when Apply Import is clicked */
  onApplyImport: () => void;
  /** Whether import is in progress */
  isImporting?: boolean;
}

// ============================================================================
// Component
// ============================================================================

/**
 * Modal component for previewing import changes before applying them.
 *
 * Displays:
 * - File name being imported
 * - Count of models affected
 * - Validation errors (if any)
 * - Unknown models warning (if any)
 * - Per-model configuration diffs
 *
 * @example
 * ```tsx
 * <ImportPreviewModal
 *   isOpen={isPreviewOpen}
 *   onClose={() => setIsPreviewOpen(false)}
 *   previewData={previewData}
 *   fileName="prompts-backup-2026-01-15.json"
 *   onApplyImport={handleApplyImport}
 *   isImporting={isImporting}
 * />
 * ```
 */
export default function ImportPreviewModal({
  isOpen,
  onClose,
  previewData,
  fileName,
  onApplyImport,
  isImporting = false,
}: ImportPreviewModalProps) {
  if (!previewData) {
    return null;
  }

  const totalModels = previewData.diffs.length;
  const modelsWithChanges = previewData.total_changes;
  const hasValidationErrors = previewData.validation_errors.length > 0;
  const hasUnknownModels = previewData.unknown_models.length > 0;
  const canApply = previewData.valid && modelsWithChanges > 0;

  return (
    <Dialog open={isOpen} onClose={onClose} static={true}>
      <DialogPanel
        className="max-w-3xl border border-gray-700 bg-[#1A1A1A]"
        data-testid="import-preview-modal"
      >
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <Title className="text-white">Import Preview</Title>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
            aria-label="Close"
            disabled={isImporting}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* File info and summary */}
        <div className="mb-6 space-y-2">
          <div className="flex items-center gap-2 text-gray-300">
            <FileJson className="h-4 w-4" />
            <Text className="text-gray-300">File: {fileName}</Text>
          </div>
          <Text className="text-gray-400">
            Models affected: {modelsWithChanges} of {totalModels}
          </Text>
        </div>

        {/* Validation errors */}
        {hasValidationErrors && (
          <Callout title="Validation Errors" icon={AlertTriangle} color="red" className="mb-4">
            <span className="block">
              {previewData.validation_errors.map((error, idx) => (
                <span key={idx} className="ml-4 block">
                  - {error}
                </span>
              ))}
            </span>
          </Callout>
        )}

        {/* Unknown models warning */}
        {hasUnknownModels && (
          <Callout title="Unknown Models" icon={AlertTriangle} color="amber" className="mb-4">
            <span className="block">
              The following models in the import file are not recognized and will be skipped:
            </span>
            <span className="mt-1 block">
              {previewData.unknown_models.map((model, idx) => (
                <span key={idx} className="ml-4 block">
                  - {model}
                </span>
              ))}
            </span>
          </Callout>
        )}

        {/* No changes notice */}
        {modelsWithChanges === 0 && !hasValidationErrors && (
          <Callout title="No Changes Detected" icon={CheckCircle} color="gray" className="mb-4">
            <span className="block">
              All configurations in the import file match the current configurations. Nothing will
              be changed if you apply this import.
            </span>
          </Callout>
        )}

        {/* Diff views */}
        <div className="mb-6 max-h-[400px] space-y-3 overflow-y-auto">
          {previewData.diffs.map((diff) => (
            <ConfigDiffView key={diff.model} diff={diff} />
          ))}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose} disabled={isImporting}>
            Cancel
          </Button>
          <Button onClick={onApplyImport} loading={isImporting} disabled={isImporting || !canApply}>
            Apply Import
          </Button>
        </div>
      </DialogPanel>
    </Dialog>
  );
}
