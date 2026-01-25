/**
 * GpuStrategySelector - Radio group for GPU assignment strategies
 *
 * Provides a radio group interface for selecting between 5 GPU assignment strategies:
 * - Manual: User manually assigns GPUs to services
 * - VRAM-based: Assigns based on VRAM requirements
 * - Latency-optimized: Optimizes for lowest latency
 * - Isolation-first: Maximizes isolation between services
 * - Balanced: Balances load across available GPUs
 *
 * Includes a preview button to show proposed assignments before applying.
 *
 * @see NEM-3320 - Create GPU Settings UI component
 */

import { Card, Title, Text } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Settings2,
  HardDrive,
  Zap,
  Shield,
  Scale,
  Eye,
  Loader2,
  AlertCircle,
  AlertTriangle,
} from 'lucide-react';

import Button from '../common/Button';

import type { GpuAssignment, StrategyPreviewResponse } from '../../hooks/useGpuConfig';
import type { LucideIcon } from 'lucide-react';

/**
 * Strategy configuration with display information
 */
interface StrategyConfig {
  id: string;
  label: string;
  description: string;
  icon: LucideIcon;
}

/**
 * Available GPU assignment strategies
 */
const STRATEGIES: StrategyConfig[] = [
  {
    id: 'manual',
    label: 'Manual',
    description: 'Manually assign GPUs to each AI service',
    icon: Settings2,
  },
  {
    id: 'vram_based',
    label: 'VRAM-based',
    description: 'Assign GPUs based on VRAM requirements',
    icon: HardDrive,
  },
  {
    id: 'latency_optimized',
    label: 'Latency-optimized',
    description: 'Optimize for lowest inference latency',
    icon: Zap,
  },
  {
    id: 'isolation_first',
    label: 'Isolation-first',
    description: 'Maximize isolation between services',
    icon: Shield,
  },
  {
    id: 'balanced',
    label: 'Balanced',
    description: 'Balance load across all available GPUs',
    icon: Scale,
  },
];

/**
 * Props for GpuStrategySelector component
 */
export interface GpuStrategySelectorProps {
  /** Currently selected strategy */
  selectedStrategy: string;
  /** Available strategies from the backend */
  availableStrategies: string[];
  /** Callback when strategy is selected */
  onStrategyChange: (strategy: string) => void;
  /** Callback to preview strategy assignments */
  onPreview: (strategy: string) => Promise<StrategyPreviewResponse>;
  /** Whether a preview is loading */
  isPreviewLoading?: boolean;
  /** Preview error message */
  previewError?: string | null;
  /** Preview data from last preview request */
  previewData?: StrategyPreviewResponse | null;
  /** Whether the selector is disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Strategy option radio button component
 */
function StrategyOption({
  strategy,
  isSelected,
  isAvailable,
  disabled,
  onChange,
}: {
  strategy: StrategyConfig;
  isSelected: boolean;
  isAvailable: boolean;
  disabled?: boolean;
  onChange: () => void;
}) {
  const Icon = strategy.icon;
  const isDisabled = disabled || !isAvailable;

  return (
    <label
      className={clsx(
        'relative flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-all',
        {
          'border-[#76B900] bg-[#76B900]/10': isSelected && !isDisabled,
          'border-gray-700 bg-gray-800/50 hover:border-gray-600 hover:bg-gray-800':
            !isSelected && !isDisabled,
          'cursor-not-allowed border-gray-800 bg-gray-900 opacity-50': isDisabled,
        }
      )}
      data-testid={`strategy-option-${strategy.id}`}
    >
      <input
        type="radio"
        name="gpu-strategy"
        value={strategy.id}
        checked={isSelected}
        onChange={onChange}
        disabled={isDisabled}
        className="sr-only"
        aria-describedby={`strategy-desc-${strategy.id}`}
      />
      <div
        className={clsx(
          'mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border-2',
          {
            'border-[#76B900] bg-[#76B900]': isSelected && !isDisabled,
            'border-gray-600': !isSelected || isDisabled,
          }
        )}
      >
        {isSelected && !isDisabled && <div className="h-2 w-2 rounded-full bg-black" />}
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <Icon
            className={clsx('h-4 w-4', {
              'text-[#76B900]': isSelected && !isDisabled,
              'text-gray-400': !isSelected || isDisabled,
            })}
          />
          <span
            className={clsx('font-medium', {
              'text-white': !isDisabled,
              'text-gray-500': isDisabled,
            })}
          >
            {strategy.label}
          </span>
          {!isAvailable && (
            <span className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-400">
              Unavailable
            </span>
          )}
        </div>
        <p
          id={`strategy-desc-${strategy.id}`}
          className={clsx('mt-1 text-sm', {
            'text-gray-400': !isDisabled,
            'text-gray-600': isDisabled,
          })}
        >
          {strategy.description}
        </p>
      </div>
    </label>
  );
}

/**
 * Preview results display component
 */
function PreviewResults({
  previewData,
  isLoading,
  error,
}: {
  previewData: StrategyPreviewResponse | null;
  isLoading: boolean;
  error: string | null;
}) {
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-gray-400">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm">Loading preview...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 text-red-400">
        <AlertCircle className="h-4 w-4" />
        <span className="text-sm">{error}</span>
      </div>
    );
  }

  if (!previewData) {
    return null;
  }

  const hasWarnings = previewData.warnings && previewData.warnings.length > 0;

  return (
    <div className="mt-4 rounded-lg border border-gray-700 bg-gray-800/50 p-4">
      <div className="mb-2 flex items-center gap-2">
        <Eye className="h-4 w-4 text-[#76B900]" />
        <Text className="font-medium text-white">Proposed Assignments</Text>
        <Text className="text-xs text-gray-500">({previewData.strategy})</Text>
      </div>
      <div className="space-y-2">
        {previewData.proposed_assignments.map((assignment: GpuAssignment) => (
          <div
            key={assignment.service}
            className="flex items-center justify-between rounded bg-gray-800 px-3 py-2 text-sm"
          >
            <span className="text-gray-300">{assignment.service}</span>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[#76B900]">
                {assignment.gpu_index !== null ? `GPU ${assignment.gpu_index}` : 'Auto'}
              </span>
              {assignment.vram_budget_override !== null &&
                assignment.vram_budget_override !== undefined && (
                  <span className="text-xs text-gray-400">
                    ({assignment.vram_budget_override} GB)
                  </span>
                )}
            </div>
          </div>
        ))}
      </div>

      {/* Warnings section */}
      {hasWarnings && (
        <div
          className="mt-4 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3"
          data-testid="preview-warnings"
        >
          <div className="mb-2 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-yellow-500" />
            <Text className="text-sm font-medium text-yellow-400">Warnings</Text>
          </div>
          <div className="space-y-1">
            {previewData.warnings.map((warning, idx) => (
              <p key={idx} className="text-sm text-yellow-300">
                {warning}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * GpuStrategySelector component for selecting GPU assignment strategies
 */
export default function GpuStrategySelector({
  selectedStrategy,
  availableStrategies,
  onStrategyChange,
  onPreview,
  isPreviewLoading = false,
  previewError = null,
  previewData = null,
  disabled = false,
  className,
}: GpuStrategySelectorProps) {
  const handlePreview = async () => {
    await onPreview(selectedStrategy);
  };

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="gpu-strategy-selector"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <Title className="text-white">Assignment Strategy</Title>
          <Text className="mt-1 text-sm text-gray-400">
            Choose how GPUs are assigned to AI services
          </Text>
        </div>
        <Button
          variant="outline"
          size="sm"
          leftIcon={<Eye className="h-4 w-4" />}
          onClick={() => void handlePreview()}
          isLoading={isPreviewLoading}
          disabled={disabled || selectedStrategy === 'manual'}
          data-testid="preview-strategy-button"
        >
          Preview
        </Button>
      </div>

      {/* Strategy Options */}
      <div className="space-y-3" role="radiogroup" aria-label="GPU Assignment Strategy">
        {STRATEGIES.map((strategy) => (
          <StrategyOption
            key={strategy.id}
            strategy={strategy}
            isSelected={selectedStrategy === strategy.id}
            isAvailable={availableStrategies.includes(strategy.id)}
            disabled={disabled}
            onChange={() => onStrategyChange(strategy.id)}
          />
        ))}
      </div>

      {/* Preview Results */}
      {(isPreviewLoading || previewError || previewData) && selectedStrategy !== 'manual' && (
        <PreviewResults
          previewData={previewData}
          isLoading={isPreviewLoading}
          error={previewError}
        />
      )}
    </Card>
  );
}
