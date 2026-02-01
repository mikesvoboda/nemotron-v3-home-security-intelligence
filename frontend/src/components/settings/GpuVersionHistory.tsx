/**
 * GpuVersionHistory - Configuration version history panel with diff view and export/import
 *
 * Provides a panel for viewing and managing GPU configuration versions:
 * - List of configuration versions with timestamps
 * - Diff view between versions
 * - Rollback to previous configurations
 * - Export/Import functionality
 *
 * @see NEM-4945 - GPU Configuration Version History
 */

import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  ChevronDown,
  ChevronUp,
  Clock,
  Download,
  GitCompare,
  History,
  RotateCcw,
  Upload,
  User,
} from 'lucide-react';
import { useCallback, useRef, useState } from 'react';

import {
  useConfigVersions,
  useConfigVersionDiff,
  useExportConfig,
  useImportConfig,
  useRollbackConfig,
} from '../../hooks/useGpuConfig';
import Button from '../common/Button';

import type {
  GpuConfigVersionSummary,
  GpuConfigAssignmentChange,
  GpuConfigExportData,
} from '../../services/gpuConfigApi';

/**
 * Props for GpuVersionHistory component
 */
export interface GpuVersionHistoryProps {
  /** Whether the component is in a loading/disabled state */
  disabled?: boolean;
  /** Callback after successful rollback */
  onRollback?: () => void;
  /** Callback after successful import */
  onImport?: () => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Format date for display
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Version list item component
 */
function VersionItem({
  version,
  isSelected,
  isCompareSource,
  isCompareTarget,
  onSelect,
  onCompareSelect,
}: {
  version: GpuConfigVersionSummary;
  isSelected: boolean;
  isCompareSource: boolean;
  isCompareTarget: boolean;
  onSelect: (version: GpuConfigVersionSummary) => void;
  onCompareSelect: (version: GpuConfigVersionSummary, type: 'from' | 'to') => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      className={clsx(
        'cursor-pointer rounded-lg border p-3 transition-colors',
        isSelected
          ? 'border-[#76B900] bg-[#76B900]/10'
          : 'border-gray-700 bg-gray-800/50 hover:bg-gray-800'
      )}
      onClick={() => onSelect(version)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(version);
        }
      }}
      data-testid={`version-item-${version.version_number}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge
            className={clsx(
              'text-xs font-medium',
              isCompareSource
                ? 'bg-blue-500/20 text-blue-400'
                : isCompareTarget
                  ? 'bg-green-500/20 text-green-400'
                  : 'bg-gray-700 text-gray-300'
            )}
          >
            v{version.version_number}
          </Badge>
          <span className="text-sm font-medium text-white">{version.strategy}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            className={clsx(
              'rounded p-1 text-xs transition-colors',
              isCompareSource
                ? 'bg-blue-500/20 text-blue-400'
                : 'text-gray-400 hover:bg-gray-700 hover:text-white'
            )}
            onClick={(e) => {
              e.stopPropagation();
              onCompareSelect(version, 'from');
            }}
            title="Set as compare source"
          >
            <ChevronUp className="h-3 w-3" />
          </button>
          <button
            className={clsx(
              'rounded p-1 text-xs transition-colors',
              isCompareTarget
                ? 'bg-green-500/20 text-green-400'
                : 'text-gray-400 hover:bg-gray-700 hover:text-white'
            )}
            onClick={(e) => {
              e.stopPropagation();
              onCompareSelect(version, 'to');
            }}
            title="Set as compare target"
          >
            <ChevronDown className="h-3 w-3" />
          </button>
        </div>
      </div>

      <div className="mt-2 flex items-center gap-4 text-xs text-gray-400">
        <span className="flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {formatDate(version.created_at)}
        </span>
        {version.created_by && (
          <span className="flex items-center gap-1">
            <User className="h-3 w-3" />
            {version.created_by}
          </span>
        )}
        <span>{version.assignment_count} assignments</span>
      </div>

      {version.description && (
        <p className="mt-2 text-xs text-gray-500">{version.description}</p>
      )}
    </div>
  );
}

/**
 * Diff view component
 */
function DiffView({
  fromVersion,
  toVersion,
  isLoading,
  diff,
}: {
  fromVersion: number | null;
  toVersion: number | null;
  isLoading: boolean;
  diff: {
    strategy_changed: boolean;
    old_strategy: string | null;
    new_strategy: string | null;
    assignment_changes: GpuConfigAssignmentChange[];
  } | null;
}) {
  if (fromVersion === null || toVersion === null) {
    return (
      <div className="flex h-32 items-center justify-center rounded-lg border border-dashed border-gray-700 bg-gray-800/30">
        <div className="text-center text-sm text-gray-500">
          <GitCompare className="mx-auto mb-2 h-6 w-6" />
          <p>Select two versions to compare</p>
          <p className="text-xs text-gray-600">
            Use the arrows next to version numbers
          </p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-32 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#76B900] border-t-transparent" />
      </div>
    );
  }

  if (!diff) {
    return null;
  }

  const hasChanges = diff.strategy_changed || diff.assignment_changes.length > 0;

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="flex items-center gap-2 text-sm font-medium text-white">
          <GitCompare className="h-4 w-4 text-[#76B900]" />
          Changes: v{fromVersion} → v{toVersion}
        </h4>
      </div>

      {!hasChanges ? (
        <p className="text-sm text-gray-400">No changes between these versions</p>
      ) : (
        <div className="space-y-3">
          {diff.strategy_changed && (
            <div className="rounded bg-gray-900 p-2 text-sm">
              <span className="text-gray-400">Strategy:</span>{' '}
              <span className="text-red-400 line-through">{diff.old_strategy}</span>
              {' → '}
              <span className="text-green-400">{diff.new_strategy}</span>
            </div>
          )}

          {diff.assignment_changes.length > 0 && (
            <div className="space-y-1">
              {diff.assignment_changes.map((change) => (
                <div
                  key={change.service}
                  className={clsx(
                    'rounded px-2 py-1 text-sm',
                    change.change_type === 'added' && 'bg-green-900/30 text-green-400',
                    change.change_type === 'removed' && 'bg-red-900/30 text-red-400',
                    change.change_type === 'modified' && 'bg-yellow-900/30 text-yellow-400'
                  )}
                >
                  <span className="font-medium">{change.service}:</span>{' '}
                  {change.change_type === 'added' && (
                    <>Added (GPU {change.new_gpu_index})</>
                  )}
                  {change.change_type === 'removed' && (
                    <>Removed (was GPU {change.old_gpu_index})</>
                  )}
                  {change.change_type === 'modified' && (
                    <>
                      GPU {change.old_gpu_index} → GPU {change.new_gpu_index}
                      {change.old_vram_override !== change.new_vram_override && (
                        <span className="ml-2 text-xs">
                          VRAM: {change.old_vram_override ?? 'default'} → {change.new_vram_override ?? 'default'}
                        </span>
                      )}
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Import dialog component
 */
function ImportDialog({
  isOpen,
  onClose,
  onImport,
  isLoading,
}: {
  isOpen: boolean;
  onClose: () => void;
  onImport: (data: GpuConfigExportData, applyImmediately: boolean) => void;
  isLoading: boolean;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [importData, setImportData] = useState<GpuConfigExportData | null>(null);
  const [applyImmediately, setApplyImmediately] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const text = event.target?.result as string;
        const data = JSON.parse(text) as GpuConfigExportData;

        // Basic validation
        if (!data.strategy || !data.assignments) {
          setError('Invalid configuration file format');
          return;
        }

        setImportData(data);
        setError(null);
      } catch {
        setError('Failed to parse configuration file');
      }
    };
    reader.readAsText(file);
  }, []);

  const handleImport = useCallback(() => {
    if (importData) {
      onImport(importData, applyImmediately);
    }
  }, [importData, applyImmediately, onImport]);

  const handleClose = useCallback(() => {
    setImportData(null);
    setError(null);
    setApplyImmediately(false);
    onClose();
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      data-testid="import-dialog"
    >
      <div className="mx-4 max-w-lg rounded-lg border border-gray-700 bg-[#1A1A1A] p-6 shadow-xl">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#76B900]/20">
            <Upload className="h-5 w-5 text-[#76B900]" />
          </div>
          <div>
            <h3 className="font-semibold text-white">Import Configuration</h3>
            <Text className="text-sm text-gray-400">Load a previously exported configuration</Text>
          </div>
        </div>

        {!importData ? (
          <div className="mb-6">
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,.yaml,.yml"
              onChange={handleFileSelect}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className={clsx(
                'flex w-full cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors',
                'border-gray-600 bg-gray-800/50 hover:border-[#76B900] hover:bg-gray-800'
              )}
            >
              <ArrowUpFromLine className="mb-2 h-8 w-8 text-gray-400" />
              <span className="text-sm text-gray-300">Click to select a file</span>
              <span className="mt-1 text-xs text-gray-500">JSON or YAML format</span>
            </button>
            {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
          </div>
        ) : (
          <div className="mb-6 space-y-4">
            <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-3">
              <h4 className="mb-2 text-sm font-medium text-white">Configuration Preview</h4>
              <div className="space-y-1 text-sm text-gray-400">
                <p>Strategy: <span className="text-white">{importData.strategy}</span></p>
                <p>Assignments: <span className="text-white">{importData.assignments.length}</span></p>
                {importData.source_version && (
                  <p>Source Version: <span className="text-white">v{importData.source_version}</span></p>
                )}
                {importData.description && (
                  <p>Description: <span className="text-white">{importData.description}</span></p>
                )}
              </div>
            </div>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={applyImmediately}
                onChange={(e) => setApplyImmediately(e.target.checked)}
                className="rounded border-gray-600 bg-gray-800 text-[#76B900] focus:ring-[#76B900]"
              />
              <span className="text-sm text-gray-300">Apply immediately (restart services)</span>
            </label>
          </div>
        )}

        <div className="flex justify-end gap-3">
          <Button variant="ghost" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            leftIcon={<Upload className="h-4 w-4" />}
            onClick={handleImport}
            disabled={!importData}
            isLoading={isLoading}
          >
            Import
          </Button>
        </div>
      </div>
    </div>
  );
}

/**
 * GpuVersionHistory component
 */
export default function GpuVersionHistory({
  disabled = false,
  onRollback,
  onImport,
  className,
}: GpuVersionHistoryProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<GpuConfigVersionSummary | null>(null);
  const [compareFrom, setCompareFrom] = useState<number | null>(null);
  const [compareTo, setCompareTo] = useState<number | null>(null);
  const [showImportDialog, setShowImportDialog] = useState(false);

  const { versions, totalCount, isLoading: isLoadingVersions } = useConfigVersions({
    enabled: isExpanded,
    limit: 10,
  });

  const { data: diff, isLoading: isLoadingDiff } = useConfigVersionDiff(
    compareFrom,
    compareTo
  );

  const { downloadConfig, isLoading: isExporting } = useExportConfig();
  const { importConfig, isLoading: isImporting } = useImportConfig();
  const { rollback, isLoading: isRollingBack } = useRollbackConfig();

  const handleVersionSelect = useCallback((version: GpuConfigVersionSummary) => {
    setSelectedVersion(version);
  }, []);

  const handleCompareSelect = useCallback(
    (version: GpuConfigVersionSummary, type: 'from' | 'to') => {
      if (type === 'from') {
        setCompareFrom(version.version_number);
      } else {
        setCompareTo(version.version_number);
      }
    },
    []
  );

  const handleExport = useCallback(
    async (format: 'json' | 'yaml') => {
      await downloadConfig(selectedVersion?.id, format);
    },
    [downloadConfig, selectedVersion]
  );

  const handleImport = useCallback(
    async (data: GpuConfigExportData, applyImmediately: boolean) => {
      await importConfig({
        config: data,
        apply_immediately: applyImmediately,
      });
      setShowImportDialog(false);
      onImport?.();
    },
    [importConfig, onImport]
  );

  const handleRollback = useCallback(async () => {
    if (!selectedVersion) return;

    await rollback({
      version_id: selectedVersion.id,
      apply_immediately: true,
      description: `Rollback to version ${selectedVersion.version_number}`,
    });
    setSelectedVersion(null);
    onRollback?.();
  }, [rollback, selectedVersion, onRollback]);

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="gpu-version-history"
    >
      {/* Header */}
      <button
        className="flex w-full items-center justify-between"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/20">
            <History className="h-5 w-5 text-blue-400" />
          </div>
          <div className="text-left">
            <Title className="text-white">Version History</Title>
            <Text className="mt-1 text-sm text-gray-400">
              {totalCount} versions saved
            </Text>
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-5 w-5 text-gray-400" />
        ) : (
          <ChevronDown className="h-5 w-5 text-gray-400" />
        )}
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="mt-4 space-y-4">
          {/* Action Buttons */}
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              leftIcon={<Download className="h-4 w-4" />}
              onClick={() => void handleExport('json')}
              disabled={disabled || isExporting}
              isLoading={isExporting}
            >
              Export JSON
            </Button>
            <Button
              variant="outline"
              size="sm"
              leftIcon={<ArrowDownToLine className="h-4 w-4" />}
              onClick={() => void handleExport('yaml')}
              disabled={disabled || isExporting}
            >
              Export YAML
            </Button>
            <Button
              variant="outline"
              size="sm"
              leftIcon={<Upload className="h-4 w-4" />}
              onClick={() => setShowImportDialog(true)}
              disabled={disabled}
            >
              Import
            </Button>
            {selectedVersion && (
              <Button
                variant="primary"
                size="sm"
                leftIcon={<RotateCcw className="h-4 w-4" />}
                onClick={() => void handleRollback()}
                disabled={disabled || isRollingBack}
                isLoading={isRollingBack}
              >
                Rollback to v{selectedVersion.version_number}
              </Button>
            )}
          </div>

          {/* Version List */}
          <div className="space-y-2">
            {isLoadingVersions ? (
              <div className="flex h-32 items-center justify-center">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#76B900] border-t-transparent" />
              </div>
            ) : versions.length === 0 ? (
              <div className="flex h-32 items-center justify-center rounded-lg border border-dashed border-gray-700">
                <p className="text-sm text-gray-500">No version history yet</p>
              </div>
            ) : (
              versions.map((version) => (
                <VersionItem
                  key={version.id}
                  version={version}
                  isSelected={selectedVersion?.id === version.id}
                  isCompareSource={compareFrom === version.version_number}
                  isCompareTarget={compareTo === version.version_number}
                  onSelect={handleVersionSelect}
                  onCompareSelect={handleCompareSelect}
                />
              ))
            )}
          </div>

          {/* Diff View */}
          <DiffView
            fromVersion={compareFrom}
            toVersion={compareTo}
            isLoading={isLoadingDiff}
            diff={diff ?? null}
          />
        </div>
      )}

      {/* Import Dialog */}
      <ImportDialog
        isOpen={showImportDialog}
        onClose={() => setShowImportDialog(false)}
        onImport={(data, applyImmediately) => void handleImport(data, applyImmediately)}
        isLoading={isImporting}
      />
    </Card>
  );
}
