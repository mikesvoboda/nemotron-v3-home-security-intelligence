/**
 * DetectorSettings Component
 *
 * Provides UI for viewing and switching between object detectors at runtime.
 * Shows available detectors, their status, and allows selection of the active detector.
 *
 * @see frontend/src/hooks/useDetectorConfig.ts - State management hook
 * @see backend/api/routes/detector.py - Backend implementation
 */

import { Badge, Button, Card, Select, SelectItem, Text, Title } from '@tremor/react';
import { clsx } from 'clsx';
import { AlertCircle, Check, Cpu, Loader2, RefreshCw } from 'lucide-react';
import { useCallback, useState } from 'react';

import { useDetectorConfig } from '../../hooks/useDetectorConfig';

import type { DetectorInfo } from '../../services/detectorApi';

// ============================================================================
// Types
// ============================================================================

export interface DetectorSettingsProps {
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Badge showing detector status (enabled/disabled/active).
 */
function DetectorStatusBadge({ detector }: { detector: DetectorInfo }) {
  if (detector.is_active) {
    return (
      <Badge color="green" size="sm">
        Active
      </Badge>
    );
  }
  if (!detector.enabled) {
    return (
      <Badge color="gray" size="sm">
        Disabled
      </Badge>
    );
  }
  return (
    <Badge color="blue" size="sm">
      Available
    </Badge>
  );
}

/**
 * Card displaying detector information.
 */
function DetectorCard({
  detector,
  isActive,
  onSelect,
  isSelecting,
}: {
  detector: DetectorInfo;
  isActive: boolean;
  onSelect: () => void;
  isSelecting: boolean;
}) {
  return (
    <Card
      className={clsx(
        'border-gray-800 bg-[#1E1E1E] transition-colors',
        isActive && 'border-[#76B900] ring-1 ring-[#76B900]',
        !isActive && detector.enabled && 'hover:border-gray-700 cursor-pointer'
      )}
      onClick={!isActive && detector.enabled && !isSelecting ? onSelect : undefined}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Cpu className={clsx('h-5 w-5', isActive ? 'text-[#76B900]' : 'text-gray-400')} />
          <div>
            <Title className="text-white">{detector.display_name}</Title>
            {detector.model_version && (
              <Text className="text-sm text-gray-500">{detector.model_version}</Text>
            )}
          </div>
        </div>
        <DetectorStatusBadge detector={detector} />
      </div>

      <Text className="mt-3 text-sm text-gray-400">{detector.description}</Text>

      <div className="mt-4 flex items-center justify-between">
        <Text className="text-xs text-gray-500">{detector.url}</Text>
        {!isActive && detector.enabled && (
          <Button
            size="xs"
            variant="secondary"
            disabled={isSelecting}
            onClick={(e) => {
              e.stopPropagation();
              onSelect();
            }}
          >
            {isSelecting ? (
              <>
                <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                Switching...
              </>
            ) : (
              'Select'
            )}
          </Button>
        )}
        {isActive && (
          <div className="flex items-center gap-1 text-[#76B900]">
            <Check className="h-4 w-4" />
            <Text className="text-sm font-medium text-[#76B900]">In Use</Text>
          </div>
        )}
      </div>
    </Card>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * Settings component for managing object detectors.
 *
 * Displays available detectors in a grid layout and allows switching
 * between them at runtime. Shows health status and provides feedback
 * during switch operations.
 */
export default function DetectorSettings({ className }: DetectorSettingsProps) {
  const {
    detectors,
    activeDetector,
    isLoading,
    isSwitching,
    error,
    refresh,
    switchTo,
  } = useDetectorConfig({ pollingInterval: 30000 });

  const [switchError, setSwitchError] = useState<string | null>(null);
  const [switchingTo, setSwitchingTo] = useState<string | null>(null);

  /**
   * Handle detector selection.
   */
  const handleSelect = useCallback(
    (detectorType: string) => {
      setSwitchError(null);
      setSwitchingTo(detectorType);

      switchTo(detectorType)
        .catch((e: unknown) => {
          const message = e instanceof Error ? e.message : 'Failed to switch detector';
          setSwitchError(message);
        })
        .finally(() => {
          setSwitchingTo(null);
        });
    },
    [switchTo]
  );

  /**
   * Handle dropdown selection change.
   */
  const handleDropdownChange = useCallback(
    (value: string) => {
      if (value && value !== activeDetector) {
        handleSelect(value);
      }
    },
    [activeDetector, handleSelect]
  );

  /**
   * Handle refresh button click.
   */
  const handleRefresh = useCallback(() => {
    void refresh();
  }, [refresh]);

  // Filter enabled detectors for the dropdown
  const enabledDetectors = detectors.filter((d) => d.enabled);

  return (
    <div className={clsx('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Title className="text-white">Object Detector</Title>
          <Text className="text-gray-400">
            Select which object detection model to use for processing camera feeds.
          </Text>
        </div>
        <Button
          size="sm"
          variant="secondary"
          onClick={handleRefresh}
          disabled={isLoading}
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* Error Display */}
      {(error || switchError) && (
        <Card className="border-red-800 bg-red-900/20">
          <div className="flex items-center gap-2 text-red-400">
            <AlertCircle className="h-5 w-5" />
            <Text className="text-red-400">{switchError || error}</Text>
          </div>
        </Card>
      )}

      {/* Quick Selection Dropdown */}
      <Card className="border-gray-800 bg-[#1A1A1A]">
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <Text className="mb-1 text-sm font-medium text-gray-300">Active Detector</Text>
            <Select
              value={activeDetector || ''}
              onValueChange={handleDropdownChange}
              disabled={isLoading || isSwitching}
              placeholder="Select a detector..."
            >
              {enabledDetectors.map((detector) => (
                <SelectItem key={detector.detector_type} value={detector.detector_type}>
                  {detector.display_name}
                  {detector.model_version && ` (${detector.model_version})`}
                </SelectItem>
              ))}
            </Select>
          </div>
          {isSwitching && (
            <div className="flex items-center gap-2 text-yellow-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              <Text className="text-sm text-yellow-400">Switching...</Text>
            </div>
          )}
        </div>
      </Card>

      {/* Detector Cards Grid */}
      {isLoading && detectors.length === 0 ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {detectors.map((detector) => (
            <DetectorCard
              key={detector.detector_type}
              detector={detector}
              isActive={detector.detector_type === activeDetector}
              onSelect={() => handleSelect(detector.detector_type)}
              isSelecting={switchingTo === detector.detector_type}
            />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && detectors.length === 0 && (
        <Card className="border-gray-800 bg-[#1E1E1E]">
          <div className="py-8 text-center">
            <Cpu className="mx-auto h-12 w-12 text-gray-600" />
            <Title className="mt-4 text-gray-400">No Detectors Available</Title>
            <Text className="mt-2 text-gray-500">
              No object detectors have been configured. Check your system configuration.
            </Text>
          </div>
        </Card>
      )}

      {/* Info Card */}
      <Card className="border-gray-800 bg-[#1A1A1A]">
        <Text className="text-sm text-gray-400">
          <strong className="text-gray-300">Note:</strong> Switching detectors will apply
          immediately to new camera frame processing. Existing batches in progress will
          complete with the previous detector. Health checks are performed before switching
          to ensure the target detector is operational.
        </Text>
      </Card>
    </div>
  );
}
