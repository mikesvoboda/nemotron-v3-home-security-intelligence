import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import { Gauge, AlertCircle, Lock } from 'lucide-react';

import type { SeverityDefinitionResponse, SeverityMetadataResponse } from '../../types/generated';

/**
 * Props for SeverityConfigPanel component
 */
export interface SeverityConfigPanelProps {
  /** Severity metadata from API */
  data: SeverityMetadataResponse | null;
  /** Loading state */
  loading: boolean;
  /** Error message if fetch failed */
  error: string | null;
  /** Additional CSS classes */
  className?: string;
}

/**
 * SeverityConfigPanel - Displays severity level configuration (read-only)
 *
 * Shows:
 * - All 4 severity levels (LOW, MEDIUM, HIGH, CRITICAL)
 * - Risk score ranges, color codes, and descriptions
 * - Current thresholds configuration
 * - Read-only indicator (editing is a future enhancement)
 */
export default function SeverityConfigPanel({
  data,
  loading,
  error,
  className,
}: SeverityConfigPanelProps) {
  // Loading state
  if (loading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="severity-config-panel-loading"
      >
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-5 w-5 animate-pulse rounded bg-gray-700" />
            <div className="h-6 w-48 animate-pulse rounded bg-gray-700" />
          </div>
          <div className="h-5 w-20 animate-pulse rounded bg-gray-700" />
        </div>
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-gray-800/50" />
          ))}
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="severity-config-panel-error"
      >
        <div className="mb-4 flex items-center gap-2">
          <Gauge className="h-5 w-5 text-[#76B900]" />
          <Title className="text-white">Severity Configuration</Title>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <Text className="text-red-400">{error}</Text>
        </div>
      </Card>
    );
  }

  // Sort definitions by priority (0 = critical = first)
  const sortedDefinitions = data?.definitions
    ? [...data.definitions].sort((a, b) => a.priority - b.priority)
    : [];

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="severity-config-panel"
    >
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Gauge className="h-5 w-5 text-[#76B900]" />
          Severity Configuration
        </Title>
        <Badge color="gray" size="sm" icon={Lock}>
          Read-only
        </Badge>
      </div>

      {sortedDefinitions.length === 0 ? (
        <div className="flex h-32 items-center justify-center">
          <Text className="text-sm text-gray-500">No severity levels configured</Text>
        </div>
      ) : (
        <>
          {/* Severity Levels */}
          <div className="space-y-2">
            {sortedDefinitions.map((definition) => (
              <SeverityLevelRow key={definition.severity} definition={definition} />
            ))}
          </div>

          {/* Thresholds Section */}
          {data?.thresholds && (
            <div
              className="mt-4 rounded-lg border border-gray-700 bg-gray-800/30 p-3"
              data-testid="thresholds-section"
            >
              <Text className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">
                Threshold Configuration
              </Text>
              <div className="grid grid-cols-3 gap-3 text-center text-xs">
                <div>
                  <Text className="text-gray-500">Low Max</Text>
                  <p className="font-mono text-gray-200" data-testid="threshold-low-max">
                    {data.thresholds.low_max}
                  </p>
                </div>
                <div>
                  <Text className="text-gray-500">Medium Max</Text>
                  <p className="font-mono text-gray-200" data-testid="threshold-medium-max">
                    {data.thresholds.medium_max}
                  </p>
                </div>
                <div>
                  <Text className="text-gray-500">High Max</Text>
                  <p className="font-mono text-gray-200" data-testid="threshold-high-max">
                    {data.thresholds.high_max}
                  </p>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </Card>
  );
}

/**
 * SeverityLevelRow - Displays a single severity level's configuration
 */
interface SeverityLevelRowProps {
  definition: SeverityDefinitionResponse;
}

function SeverityLevelRow({ definition }: SeverityLevelRowProps) {
  // Get lighter text color for better contrast (WCAG AA compliance)
  const getBadgeTextColor = (color: string): string => {
    // Map base colors to lighter variants for better contrast on dark backgrounds
    const colorMap: Record<string, string> = {
      '#ef4444': '#fca5a5', // red-500 -> red-300 (4.5:1 contrast)
      '#f97316': '#fdba74', // orange-500 -> orange-300
      '#eab308': '#fde047', // yellow-500 -> yellow-300
      '#22c55e': '#86efac', // green-500 -> green-300
    };
    return colorMap[color.toLowerCase()] || color;
  };

  return (
    <div
      className="flex items-center gap-3 rounded-lg border border-gray-700 bg-gray-800/50 p-3"
      data-testid={`severity-level-${definition.severity}`}
    >
      {/* Color Indicator */}
      <div
        className="h-8 w-2 rounded-full"
        style={{ backgroundColor: definition.color }}
        data-testid={`color-indicator-${definition.severity}`}
      />

      {/* Label and Description */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Text className="font-medium text-gray-200">{definition.label}</Text>
          <Badge
            size="xs"
            style={{
              backgroundColor: `${definition.color}20`,
              color: getBadgeTextColor(definition.color),
              borderColor: definition.color,
            }}
          >
            {definition.severity.toUpperCase()}
          </Badge>
        </div>
        <Text className="truncate text-xs text-gray-400">{definition.description}</Text>
      </div>

      {/* Score Range */}
      <div className="text-right">
        <Text className="text-xs text-gray-500">Score Range</Text>
        <p
          className="text-tremor-default dark:text-dark-tremor-content font-mono text-sm text-gray-200"
          data-testid={`score-range-${definition.severity}`}
        >
          {definition.min_score}-{definition.max_score}
        </p>
      </div>
    </div>
  );
}
