import { Card, Title, Text, Badge, Tracker, type Color } from '@tremor/react';
import { clsx } from 'clsx';
import { Box, CheckCircle, XCircle, AlertCircle } from 'lucide-react';

/**
 * Container metrics
 */
export interface ContainerMetrics {
  name: string;
  status: string;
  health: string;
}

/**
 * Container health history point
 */
export interface ContainerHealthPoint {
  timestamp: string;
  health: string;
}

/**
 * Container history data for Tracker component
 */
export interface ContainerHistory {
  [containerName: string]: ContainerHealthPoint[];
}

/**
 * Tracker data point format for Tremor Tracker
 */
interface TrackerDataPoint {
  color: Color;
  tooltip: string;
}

/**
 * Props for ContainersPanel component
 */
export interface ContainersPanelProps {
  /** Container metrics array */
  containers: ContainerMetrics[];
  /** Historical health data for each container */
  history: ContainerHistory;
  /** Additional CSS classes */
  className?: string;
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
}

/**
 * Get badge color based on health status
 */
function getHealthColor(health: string): 'green' | 'red' | 'gray' {
  switch (health.toLowerCase()) {
    case 'healthy':
      return 'green';
    case 'unhealthy':
      return 'red';
    default:
      return 'gray';
  }
}

/**
 * Get Tracker color based on health status
 */
function getTrackerColor(health: string): Color {
  switch (health.toLowerCase()) {
    case 'healthy':
      return 'emerald';
    case 'unhealthy':
      return 'rose';
    default:
      return 'gray';
  }
}

/**
 * Format health status for display
 */
function formatHealth(health: string): string {
  switch (health.toLowerCase()) {
    case 'healthy':
      return 'Healthy';
    case 'unhealthy':
      return 'Unhealthy';
    default:
      return 'Unknown';
  }
}

/**
 * Get health icon based on status
 */
function HealthIcon({ health }: { health: string }) {
  switch (health.toLowerCase()) {
    case 'healthy':
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case 'unhealthy':
      return <XCircle className="h-4 w-4 text-red-500" />;
    default:
      return <AlertCircle className="h-4 w-4 text-gray-500" />;
  }
}

/**
 * Transform history data to Tracker format
 */
function transformToTrackerData(historyPoints: ContainerHealthPoint[] | undefined): TrackerDataPoint[] {
  if (!historyPoints || historyPoints.length === 0) {
    // Return empty tracker data (will show empty state)
    return [];
  }

  return historyPoints.map((point) => ({
    color: getTrackerColor(point.health),
    tooltip: `${new Date(point.timestamp).toLocaleTimeString()} - ${formatHealth(point.health)}`,
  }));
}

/**
 * ContainersPanel - Displays container health status with timeline trackers
 *
 * Shows:
 * - 6 containers: backend, frontend, postgres, redis, ai-detector, ai-llm
 * - Health status badges (green=healthy, red=unhealthy)
 * - Tremor Tracker for health timeline visualization
 * - Summary count of healthy containers
 */
export default function ContainersPanel({
  containers,
  history,
  className,
  'data-testid': testId = 'containers-panel',
}: ContainersPanelProps) {
  // Calculate summary stats
  const healthyCount = containers.filter((c) => c.health.toLowerCase() === 'healthy').length;
  const totalCount = containers.length;

  return (
    <Card className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)} data-testid={testId}>
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Box className="h-5 w-5 text-[#76B900]" />
          Containers
        </Title>
        <Badge
          color={healthyCount === totalCount ? 'green' : 'red'}
          size="sm"
          data-testid="containers-summary"
        >
          {healthyCount}/{totalCount} Healthy
        </Badge>
      </div>

      {containers.length === 0 ? (
        <div className="flex h-40 items-center justify-center">
          <Text className="text-sm text-gray-500">No containers available</Text>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {containers.map((container) => {
            const trackerData = transformToTrackerData(history[container.name]);
            const isHealthy = container.health.toLowerCase() === 'healthy';

            return (
              <div
                key={container.name}
                className={clsx(
                  'rounded-lg border p-3',
                  isHealthy
                    ? 'border-gray-700 bg-gray-800/50'
                    : 'border-red-500/30 bg-red-500/10'
                )}
                data-testid={`container-${container.name}`}
              >
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <HealthIcon health={container.health} />
                    <Text className="text-sm font-medium text-gray-200">
                      {container.name}
                    </Text>
                  </div>
                  <Badge
                    color={getHealthColor(container.health)}
                    size="xs"
                    data-testid={`container-status-${container.name}`}
                  >
                    {formatHealth(container.health)}
                  </Badge>
                </div>

                {/* Health Timeline Tracker */}
                <div data-testid={`tracker-${container.name}`}>
                  {trackerData.length > 0 ? (
                    <Tracker
                      data={trackerData}
                      className="h-4"
                    />
                  ) : (
                    <div className="flex h-4 items-center justify-center rounded bg-gray-700/50">
                      <Text className="text-xs text-gray-500">No history</Text>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
