import { Card, Title, Text } from '@tremor/react';
import { AlertTriangle, Gauge } from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import { fetchSeverityMetadata } from '../../services/api';

import type {
  SeverityMetadataResponse,
  SeverityDefinitionResponse,
  SeverityThresholds,
} from '../../services/api';

/**
 * Props for SeverityConfigPanel component
 */
export interface SeverityConfigPanelProps {
  /** Optional class name for styling */
  className?: string;
}

/**
 * Gets icon for severity level
 */
function getSeverityIcon(severity: string) {
  switch (severity) {
    case 'critical':
      return '!!';
    case 'high':
      return '!';
    case 'medium':
      return '-';
    case 'low':
      return '';
    default:
      return '';
  }
}

/**
 * SeverityRow - Displays a single severity level's definition
 */
interface SeverityRowProps {
  definition: SeverityDefinitionResponse;
}

function SeverityRow({ definition }: SeverityRowProps) {
  return (
    <div
      className="flex items-center justify-between rounded-lg bg-gray-800/50 p-3"
      data-testid={`severity-row-${definition.severity}`}
    >
      <div className="flex items-center gap-3">
        {/* Color Indicator */}
        <div
          className="h-4 w-4 rounded-full"
          style={{ backgroundColor: definition.color }}
          data-testid={`severity-color-${definition.severity}`}
          aria-label={`${definition.label} color indicator`}
        />

        {/* Severity Info */}
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span
              className="text-sm font-medium text-gray-300"
              data-testid={`severity-label-${definition.severity}`}
            >
              {definition.label}
            </span>
            {getSeverityIcon(definition.severity) && (
              <span
                className="text-xs font-bold"
                style={{ color: definition.color }}
              >
                {getSeverityIcon(definition.severity)}
              </span>
            )}
          </div>
          <span
            className="text-xs text-gray-500"
            data-testid={`severity-description-${definition.severity}`}
          >
            {definition.description}
          </span>
        </div>
      </div>

      {/* Score Range */}
      <div className="text-right">
        <span
          className="text-sm font-mono font-medium"
          style={{ color: definition.color }}
          data-testid={`severity-range-${definition.severity}`}
        >
          {definition.min_score} - {definition.max_score}
        </span>
        <Text className="text-xs text-gray-500">Risk Score</Text>
      </div>
    </div>
  );
}

/**
 * SeverityScale - Visual representation of severity thresholds
 */
interface SeverityScaleProps {
  definitions: SeverityDefinitionResponse[];
}

function SeverityScale({ definitions }: SeverityScaleProps) {
  // Sort definitions by min_score for proper scale display
  const sortedDefs = [...definitions].sort((a, b) => a.min_score - b.min_score);

  return (
    <div className="mt-4" data-testid="severity-scale">
      <Text className="mb-2 text-xs text-gray-500">Risk Score Scale</Text>
      <div className="flex h-4 w-full overflow-hidden rounded-full">
        {sortedDefs.map((def) => {
          const width = ((def.max_score - def.min_score + 1) / 101) * 100;
          return (
            <div
              key={def.severity}
              className="h-full"
              style={{
                backgroundColor: def.color,
                width: `${width}%`,
              }}
              title={`${def.label}: ${def.min_score}-${def.max_score}`}
            />
          );
        })}
      </div>
      <div className="mt-1 flex justify-between text-xs text-gray-500">
        <span>0</span>
        <span>25</span>
        <span>50</span>
        <span>75</span>
        <span>100</span>
      </div>
    </div>
  );
}

/**
 * ThresholdsSection - Displays threshold configuration
 */
interface ThresholdsSectionProps {
  thresholds: SeverityThresholds;
}

function ThresholdsSection({ thresholds }: ThresholdsSectionProps) {
  return (
    <div className="mt-4 rounded-lg bg-gray-800/30 p-3">
      <Text className="mb-2 text-xs font-medium text-gray-400">Threshold Configuration</Text>
      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div>
          <Text className="text-gray-500">Low Max</Text>
          <span
            className="font-mono font-medium text-green-400"
            data-testid="threshold-low-max"
          >
            {thresholds.low_max}
          </span>
        </div>
        <div>
          <Text className="text-gray-500">Medium Max</Text>
          <span
            className="font-mono font-medium text-yellow-400"
            data-testid="threshold-medium-max"
          >
            {thresholds.medium_max}
          </span>
        </div>
        <div>
          <Text className="text-gray-500">High Max</Text>
          <span
            className="font-mono font-medium text-orange-400"
            data-testid="threshold-high-max"
          >
            {thresholds.high_max}
          </span>
        </div>
      </div>
    </div>
  );
}

/**
 * SeverityConfigPanel - Displays severity level definitions and thresholds
 *
 * Shows:
 * - All severity levels with their colors, labels, and descriptions
 * - Risk score ranges for each severity level
 * - Visual scale showing threshold boundaries
 * - Current threshold configuration
 *
 * Fetches data from GET /api/system/severity endpoint.
 */
export default function SeverityConfigPanel({ className }: SeverityConfigPanelProps) {
  const [data, setData] = useState<SeverityMetadataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const response = await fetchSeverityMetadata();
      setData(response);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch severity metadata:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch severity configuration');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch - severity config is static, so no polling needed
  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  // Loading state
  if (loading) {
    return (
      <Card
        className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className ?? ''}`}
        data-testid="severity-config-panel-loading"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Gauge className="h-5 w-5 text-[#76B900]" />
          Severity Levels
        </Title>
        <div className="space-y-3">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-gray-800"></div>
          ))}
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card
        className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className ?? ''}`}
        data-testid="severity-config-panel-error"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Gauge className="h-5 w-5 text-[#76B900]" />
          Severity Levels
        </Title>
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertTriangle className="h-5 w-5 text-red-500" />
          <div>
            <Text className="text-sm font-medium text-red-400">
              Failed to load severity configuration
            </Text>
            <Text className="text-xs text-gray-400">{error}</Text>
          </div>
        </div>
      </Card>
    );
  }

  const definitions = data?.definitions ?? [];
  const thresholds = data?.thresholds;

  // Sort definitions by priority (0 = highest priority, displayed first)
  const sortedDefinitions = [...definitions].sort((a, b) => a.priority - b.priority);

  return (
    <Card
      className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className ?? ''}`}
      data-testid="severity-config-panel"
    >
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Gauge className="h-5 w-5 text-[#76B900]" />
        Severity Levels
      </Title>

      {/* Severity Definitions List */}
      <div className="space-y-2" data-testid="severity-definitions-list">
        {sortedDefinitions.length > 0 ? (
          sortedDefinitions.map((definition) => (
            <SeverityRow key={definition.severity} definition={definition} />
          ))
        ) : (
          <Text className="py-4 text-center text-gray-500">
            No severity definitions configured
          </Text>
        )}
      </div>

      {/* Visual Scale */}
      {definitions.length > 0 && <SeverityScale definitions={definitions} />}

      {/* Threshold Configuration */}
      {thresholds && <ThresholdsSection thresholds={thresholds} />}
    </Card>
  );
}
