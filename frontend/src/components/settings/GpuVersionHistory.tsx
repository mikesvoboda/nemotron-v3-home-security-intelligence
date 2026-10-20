/**
 * GpuVersionHistory - Configuration version history panel with diff view and export (F-182).
 *
 * R2a row 36 retired F-183 (Import and Rollback).
 */

import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import {
  ArrowDownToLine,
  ChevronDown,
  ChevronUp,
  Clock,
  Download,
  GitCompare,
  History,
  User,
} from 'lucide-react';
import { useCallback, useState } from 'react';

import { useConfigVersions, useConfigVersionDiff, useExportConfig } from '../../hooks/useGpuConfig';
import Button from '../common/Button';

import type {
  GpuConfigVersionSummary,
  GpuConfigAssignmentChange,
} from '../../services/gpuConfigApi';

export interface GpuVersionHistoryProps {
  disabled?: boolean;
  className?: string;
}

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

      {version.description && <p className="mt-2 text-xs text-gray-500">{version.description}</p>}
    </div>
  );
}

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
          <p className="text-xs text-gray-600">Use the arrows next to version numbers</p>
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
                  {change.change_type === 'added' && <>Added (GPU {change.new_gpu_index})</>}
                  {change.change_type === 'removed' && (
                    <>Removed (was GPU {change.old_gpu_index})</>
                  )}
                  {change.change_type === 'modified' && (
                    <>
                      GPU {change.old_gpu_index} → GPU {change.new_gpu_index}
                      {change.old_vram_override !== change.new_vram_override && (
                        <span className="ml-2 text-xs">
                          VRAM: {change.old_vram_override ?? 'default'} →{' '}
                          {change.new_vram_override ?? 'default'}
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

export default function GpuVersionHistory({ disabled = false, className }: GpuVersionHistoryProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<GpuConfigVersionSummary | null>(null);
  const [compareFrom, setCompareFrom] = useState<number | null>(null);
  const [compareTo, setCompareTo] = useState<number | null>(null);

  const {
    versions,
    totalCount,
    isLoading: isLoadingVersions,
  } = useConfigVersions({
    enabled: isExpanded,
    limit: 10,
  });

  const { data: diff, isLoading: isLoadingDiff } = useConfigVersionDiff(compareFrom, compareTo);

  const { downloadConfig, isLoading: isExporting } = useExportConfig();

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

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="gpu-version-history"
    >
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
            <Text className="mt-1 text-sm text-gray-400">{totalCount} versions saved</Text>
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-5 w-5 text-gray-400" />
        ) : (
          <ChevronDown className="h-5 w-5 text-gray-400" />
        )}
      </button>

      {isExpanded && (
        <div className="mt-4 space-y-4">
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
          </div>

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

          <DiffView
            fromVersion={compareFrom}
            toVersion={compareTo}
            isLoading={isLoadingDiff}
            diff={diff ?? null}
          />
        </div>
      )}
    </Card>
  );
}
