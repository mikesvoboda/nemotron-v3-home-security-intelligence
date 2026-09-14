/**
 * ImportExportButtons - Export and Import buttons with file handling
 *
 * Provides:
 * - Export button that triggers JSON download
 * - Import button with hidden file input
 * - Integration with usePromptImportExport hooks
 *
 * @see NEM-2699 - Implement prompt import/export with preview diffs
 */

import { Button } from '@tremor/react';
import { Download, Upload } from 'lucide-react';
import { useRef, useCallback, useState } from 'react';

import ImportPreviewModal from './ImportPreviewModal';
import {
  useExportPrompts,
  useImportPreview,
  useImportPrompts,
} from '../../../hooks/usePromptImportExport';

// ============================================================================
// Types
// ============================================================================

export interface ImportExportButtonsProps {
  /** Called after successful import */
  onImportSuccess?: () => void;
  /** Called when export fails */
  onExportError?: (error: Error) => void;
  /** Called when import fails */
  onImportError?: (error: Error) => void;
}

// ============================================================================
// Component
// ============================================================================

/**
 * Export and Import buttons with integrated file handling and preview modal.
 *
 * @example
 * ```tsx
 * <ImportExportButtons
 *   onImportSuccess={() => toast.success('Import complete')}
 *   onExportError={(e) => toast.error(`Export failed: ${e.message}`)}
 * />
 * ```
 */
export default function ImportExportButtons({
  onImportSuccess,
  onExportError,
  onImportError,
}: ImportExportButtonsProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFileName, setSelectedFileName] = useState('');
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  // Hooks
  const { exportAndDownload, isExporting } = useExportPrompts();
  const {
    previewData,
    previewFromFile,
    isPending: isPreviewPending,
    clearPreview,
  } = useImportPreview();
  const { importFromPreview, isPending: isImportPending } = useImportPrompts();

  // Handle export click
  const handleExport = useCallback(async () => {
    try {
      await exportAndDownload();
    } catch (error) {
      onExportError?.(error instanceof Error ? error : new Error('Export failed'));
    }
  }, [exportAndDownload, onExportError]);

  // Handle import button click - trigger file input
  const handleImportClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  // Handle file selection
  const handleFileChange = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;

      setSelectedFileName(file.name);

      try {
        await previewFromFile(file);
        setIsPreviewOpen(true);
      } catch (error) {
        onImportError?.(error instanceof Error ? error : new Error('Failed to parse import file'));
      }

      // Reset file input so the same file can be selected again
      event.target.value = '';
    },
    [previewFromFile, onImportError]
  );

  // Handle apply import
  const handleApplyImport = useCallback(async () => {
    if (!previewData) return;

    try {
      await importFromPreview(previewData);
      setIsPreviewOpen(false);
      clearPreview();
      onImportSuccess?.();
    } catch (error) {
      onImportError?.(error instanceof Error ? error : new Error('Failed to apply import'));
    }
  }, [previewData, importFromPreview, clearPreview, onImportSuccess, onImportError]);

  // Handle modal close
  const handleClosePreview = useCallback(() => {
    setIsPreviewOpen(false);
    clearPreview();
  }, [clearPreview]);

  return (
    <>
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".json,application/json"
        onChange={(e) => void handleFileChange(e)}
        className="hidden"
        aria-label="Import prompts file"
        data-testid="import-file-input"
      />

      {/* Button group */}
      <div className="flex gap-2" data-testid="import-export-buttons">
        <Button
          variant="secondary"
          icon={Download}
          onClick={() => void handleExport()}
          loading={isExporting}
          disabled={isExporting}
        >
          Export
        </Button>
        <Button
          variant="secondary"
          icon={Upload}
          onClick={handleImportClick}
          loading={isPreviewPending}
          disabled={isPreviewPending}
        >
          Import
        </Button>
      </div>

      {/* Import preview modal */}
      <ImportPreviewModal
        isOpen={isPreviewOpen}
        onClose={handleClosePreview}
        previewData={previewData}
        fileName={selectedFileName}
        onApplyImport={() => void handleApplyImport()}
        isImporting={isImportPending}
      />
    </>
  );
}
