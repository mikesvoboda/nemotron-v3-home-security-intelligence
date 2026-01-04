import clsx from 'clsx';
import {
  Activity,
  AlertTriangle,
  Brain,
  CheckCircle,
  Cpu,
  Server,
  Workflow,
  XCircle,
} from 'lucide-react';
import { useCallback, useMemo } from 'react';

import { useHealthStatus } from '../../hooks/useHealthStatus';
import { useModelZooStatus } from '../../hooks/useModelZooStatus';
import { usePerformanceMetrics } from '../../hooks/usePerformanceMetrics';

// ============================================================================
// Types
// ============================================================================

/**
 * Health state for a system indicator.
 */
export type IndicatorState = 'healthy' | 'degraded' | 'critical';

/**
 * Indicator identifiers for the summary row.
 */
export type IndicatorType = 'overall' | 'gpu' | 'pipeline' | 'ai-models' | 'infra';

/**
 * Data structure for each indicator in the summary row.
 */
export interface IndicatorData {
  type: IndicatorType;
  label: string;
  state: IndicatorState;
  primaryMetric: string;
  secondaryMetric?: string;
  tooltipContent: string[];
  sectionId: string;
}

/**
 * Props for a single summary indicator card.
 */
interface SummaryIndicatorProps {
  data: IndicatorData;
  onClick: (sectionId: string) => void;
}

/**
 * Props for the SystemSummaryRow component.
 */
export interface SystemSummaryRowProps {
  /** Optional CSS class names */
  className?: string;
  /** Optional callback when an indicator is clicked */
  onIndicatorClick?: (sectionId: string) => void;
}

// ============================================================================
// State Styling
// ============================================================================

/**
 * Get the color class for an indicator state.
 */
function getStateColor(state: IndicatorState): {
  bg: string;
  text: string;
  border: string;
  icon: string;
} {
  switch (state) {
    case 'healthy':
      return {
        bg: 'bg-green-500/10',
        text: 'text-green-400',
        border: 'border-green-500/30',
        icon: 'text-green-500',
      };
    case 'degraded':
      return {
        bg: 'bg-yellow-500/10',
        text: 'text-yellow-400',
        border: 'border-yellow-500/30',
        icon: 'text-yellow-500',
      };
    case 'critical':
      return {
        bg: 'bg-red-500/10',
        text: 'text-red-400',
        border: 'border-red-500/30',
        icon: 'text-red-500',
      };
  }
}

/**
 * Get the status icon for an indicator state.
 */
function getStateIcon(state: IndicatorState): React.ReactNode {
  const colors = getStateColor(state);
  switch (state) {
    case 'healthy':
      return <CheckCircle className={clsx('h-5 w-5', colors.icon)} aria-hidden="true" />;
    case 'degraded':
      return <AlertTriangle className={clsx('h-5 w-5', colors.icon)} aria-hidden="true" />;
    case 'critical':
      return <XCircle className={clsx('h-5 w-5', colors.icon)} aria-hidden="true" />;
  }
}

/**
 * Get the indicator type icon.
 */
function getIndicatorIcon(type: IndicatorType): React.ReactNode {
  switch (type) {
    case 'overall':
      return <Activity className="h-4 w-4 text-gray-400" aria-hidden="true" />;
    case 'gpu':
      return <Cpu className="h-4 w-4 text-gray-400" aria-hidden="true" />;
    case 'pipeline':
      return <Workflow className="h-4 w-4 text-gray-400" aria-hidden="true" />;
    case 'ai-models':
      return <Brain className="h-4 w-4 text-gray-400" aria-hidden="true" />;
    case 'infra':
      return <Server className="h-4 w-4 text-gray-400" aria-hidden="true" />;
  }
}

// ============================================================================
// Summary Indicator Component
// ============================================================================

/**
 * A single indicator card in the summary row.
 */
function SummaryIndicator({ data, onClick }: SummaryIndicatorProps) {
  const colors = getStateColor(data.state);
  const statusIcon = getStateIcon(data.state);
  const typeIcon = getIndicatorIcon(data.type);

  const handleClick = useCallback(() => {
    onClick(data.sectionId);
  }, [onClick, data.sectionId]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onClick(data.sectionId);
      }
    },
    [onClick, data.sectionId]
  );

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={clsx(
        'group relative flex flex-col items-center justify-center',
        'rounded-lg border p-3',
        'cursor-pointer transition-all duration-200',
        'hover:scale-105 hover:shadow-lg',
        'focus:outline-none focus:ring-2 focus:ring-[#76B900]/50',
        colors.bg,
        colors.border
      )}
      data-testid={`summary-indicator-${data.type}`}
      aria-label={`${data.label}: ${data.state}. ${data.primaryMetric}. Click to scroll to ${data.label} section.`}
    >
      {/* Header with type icon and label */}
      <div className="flex items-center gap-1.5 mb-1">
        {typeIcon}
        <span className="text-xs font-medium text-gray-400 uppercase tracking-wide">
          {data.label}
        </span>
      </div>

      {/* Status icon */}
      <div className="mb-1" data-testid={`indicator-status-${data.type}`}>
        {statusIcon}
      </div>

      {/* Primary metric */}
      <div className={clsx('text-sm font-semibold', colors.text)} data-testid={`indicator-primary-${data.type}`}>
        {data.primaryMetric}
      </div>

      {/* Secondary metric (optional) */}
      {data.secondaryMetric && (
        <div className="text-xs text-gray-500" data-testid={`indicator-secondary-${data.type}`}>
          {data.secondaryMetric}
        </div>
      )}

      {/* Tooltip */}
      <div
        className={clsx(
          'absolute bottom-full left-1/2 -translate-x-1/2 mb-2',
          'invisible opacity-0 group-hover:visible group-hover:opacity-100',
          'transition-all duration-200 z-10',
          'min-w-[180px] max-w-[250px]'
        )}
        role="tooltip"
        data-testid={`indicator-tooltip-${data.type}`}
      >
        <div className="bg-gray-900 border border-gray-700 rounded-lg shadow-xl p-3">
          <div className="text-xs font-medium text-gray-300 mb-2 border-b border-gray-700 pb-1">
            {data.label} Details
          </div>
          <ul className="space-y-1">
            {data.tooltipContent.map((item, index) => (
              <li key={index} className="text-xs text-gray-400">
                {item}
              </li>
            ))}
          </ul>
          {/* Tooltip arrow */}
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px">
            <div className="border-8 border-transparent border-t-gray-700" />
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Determine the worst state from a list of states.
 */
function getWorstState(states: IndicatorState[]): IndicatorState {
  if (states.includes('critical')) return 'critical';
  if (states.includes('degraded')) return 'degraded';
  return 'healthy';
}

/**
 * Format bytes to human-readable string.
 */
function formatGB(gb: number): string {
  if (gb < 1) {
    return `${Math.round(gb * 1024)}MB`;
  }
  return `${gb.toFixed(1)}GB`;
}

/**
 * Format a number with appropriate suffix (k, M).
 */
function formatCount(count: number): string {
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M`;
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}k`;
  }
  return count.toString();
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * SystemSummaryRow - Five clickable indicators for quick system health overview.
 *
 * Displays:
 * - Overall: Aggregate health status (worst of all components)
 * - GPU: Utilization, temperature, VRAM usage
 * - Pipeline: Queue depth, throughput
 * - AI Models: Loaded models count, total inferences
 * - Infrastructure: Database, Redis, containers, host health
 *
 * Click any indicator to smooth scroll to that section.
 * Hover shows tooltip with component breakdown.
 */
export default function SystemSummaryRow({
  className,
  onIndicatorClick,
}: SystemSummaryRowProps) {
  // Hooks for real-time data
  const { current, isConnected } = usePerformanceMetrics();
  const { services, overallStatus } = useHealthStatus({ pollingInterval: 10000 });
  const { models, vramStats } = useModelZooStatus({ pollingInterval: 10000 });

  // Scroll to section handler
  const handleIndicatorClick = useCallback(
    (sectionId: string) => {
      // Smooth scroll to section
      const element = document.getElementById(sectionId);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      // Call external handler if provided
      onIndicatorClick?.(sectionId);
    },
    [onIndicatorClick]
  );

  // Calculate GPU indicator data
  const gpuIndicator = useMemo((): IndicatorData => {
    const gpu = current?.gpu;

    if (!gpu) {
      return {
        type: 'gpu',
        label: 'GPU',
        state: 'degraded',
        primaryMetric: 'No data',
        secondaryMetric: undefined,
        tooltipContent: ['GPU metrics unavailable', 'Check WebSocket connection'],
        sectionId: 'section-gpu',
      };
    }

    // Determine state based on temperature and utilization
    let state: IndicatorState = 'healthy';
    if (gpu.temperature > 80) {
      state = 'critical';
    } else if (gpu.temperature > 70 || gpu.utilization > 95) {
      state = 'degraded';
    }

    const vramUsed = gpu.vram_used_gb;
    const vramTotal = gpu.vram_total_gb;

    return {
      type: 'gpu',
      label: 'GPU',
      state,
      primaryMetric: `${Math.round(gpu.utilization)}% ${Math.round(gpu.temperature)}C`,
      secondaryMetric: `${formatGB(vramUsed)}/${formatGB(vramTotal)}`,
      tooltipContent: [
        `Utilization: ${Math.round(gpu.utilization)}%`,
        `Temperature: ${Math.round(gpu.temperature)}C`,
        `VRAM: ${formatGB(vramUsed)} / ${formatGB(vramTotal)}`,
        `Power: ${Math.round(gpu.power_watts)}W`,
        gpu.name,
      ],
      sectionId: 'section-gpu',
    };
  }, [current?.gpu]);

  // Calculate Pipeline indicator data
  const pipelineIndicator = useMemo((): IndicatorData => {
    const inference = current?.inference;

    if (!inference) {
      return {
        type: 'pipeline',
        label: 'Pipeline',
        state: isConnected ? 'healthy' : 'degraded',
        primaryMetric: isConnected ? '0 queue' : 'No data',
        secondaryMetric: undefined,
        tooltipContent: ['Pipeline metrics initializing...'],
        sectionId: 'section-pipeline',
      };
    }

    // Calculate total queue depth
    const detectionQueue = inference.queues?.detection_queue ?? 0;
    const analysisQueue = inference.queues?.analysis_queue ?? 0;
    const totalQueue = detectionQueue + analysisQueue;

    // Determine state based on queue depth
    let state: IndicatorState = 'healthy';
    if (totalQueue > 50) {
      state = 'critical';
    } else if (totalQueue > 10) {
      state = 'degraded';
    }

    // Calculate throughput
    const throughput = inference.throughput?.detections_per_minute ?? 0;

    return {
      type: 'pipeline',
      label: 'Pipeline',
      state,
      primaryMetric: `${totalQueue} queue`,
      secondaryMetric: `${throughput.toFixed(1)}/min`,
      tooltipContent: [
        `Detection queue: ${detectionQueue}`,
        `Analysis queue: ${analysisQueue}`,
        `Throughput: ${throughput.toFixed(1)}/min`,
        inference.rtdetr_latency_ms?.avg
          ? `RT-DETR latency: ${Math.round(inference.rtdetr_latency_ms.avg)}ms`
          : 'RT-DETR latency: N/A',
        inference.nemotron_latency_ms?.avg
          ? `Nemotron latency: ${Math.round(inference.nemotron_latency_ms.avg)}ms`
          : 'Nemotron latency: N/A',
      ],
      sectionId: 'section-pipeline',
    };
  }, [current?.inference, isConnected]);

  // Calculate AI Models indicator data
  const aiModelsIndicator = useMemo((): IndicatorData => {
    const loadedModels = models.filter(
      (m) => m.status === 'loaded' || m.status === 'loading'
    );
    const totalModels = models.length;
    const loadedCount = loadedModels.length;

    // Check for model errors
    const errorModels = models.filter((m) => m.status === 'error');
    const hasErrors = errorModels.length > 0;

    // Check RT-DETR and Nemotron specifically
    const rtdetr = current?.ai_models?.rtdetr;
    const nemotron = current?.nemotron;
    const criticalModelsOk =
      (rtdetr && (rtdetr as { status?: string }).status !== 'error') &&
      (nemotron && nemotron.status !== 'error');

    let state: IndicatorState = 'healthy';
    if (hasErrors || !criticalModelsOk) {
      state = 'critical';
    } else if (loadedCount === 0) {
      state = 'degraded';
    }

    // Calculate total inferences (from performance metrics)
    const rtdetrInf = current?.inference?.throughput?.detections_total ?? 0;
    const nemotronInf = current?.inference?.throughput?.analyses_total ?? 0;
    const totalInferences = rtdetrInf + nemotronInf;

    return {
      type: 'ai-models',
      label: 'AI Models',
      state,
      primaryMetric: `${loadedCount}/${totalModels || '?'}`,
      secondaryMetric: totalInferences > 0 ? `${formatCount(totalInferences)} inf` : undefined,
      tooltipContent: [
        `Loaded models: ${loadedCount}`,
        `Total models: ${totalModels}`,
        vramStats ? `VRAM used: ${formatGB(vramStats.used_mb / 1024)}` : 'VRAM: N/A',
        vramStats ? `VRAM available: ${formatGB(vramStats.available_mb / 1024)}` : '',
        ...loadedModels.slice(0, 3).map((m) => `- ${m.display_name || m.name}`),
        loadedModels.length > 3 ? `...and ${loadedModels.length - 3} more` : '',
      ].filter(Boolean),
      sectionId: 'section-ai-models',
    };
  }, [models, vramStats, current?.ai_models, current?.nemotron, current?.inference?.throughput]);

  // Calculate Infrastructure indicator data
  const infraIndicator = useMemo((): IndicatorData => {
    const databases = current?.databases;
    const containers = current?.containers ?? [];
    const host = current?.host;

    // Count healthy components
    let healthyCount = 0;
    let totalCount = 0;
    const componentStates: IndicatorState[] = [];
    const tooltipItems: string[] = [];

    // Check PostgreSQL
    const postgres = databases?.postgres as { status?: string } | undefined;
    if (postgres) {
      totalCount++;
      const isHealthy = postgres.status === 'healthy' || postgres.status === 'connected';
      if (isHealthy) healthyCount++;
      componentStates.push(isHealthy ? 'healthy' : 'critical');
      tooltipItems.push(`PostgreSQL: ${isHealthy ? 'OK' : 'Error'}`);
    }

    // Check Redis
    const redis = databases?.redis as { status?: string } | undefined;
    if (redis) {
      totalCount++;
      const isHealthy = redis.status === 'healthy' || redis.status === 'connected';
      if (isHealthy) healthyCount++;
      componentStates.push(isHealthy ? 'healthy' : 'critical');
      tooltipItems.push(`Redis: ${isHealthy ? 'OK' : 'Error'}`);
    }

    // Check containers
    if (containers.length > 0) {
      const healthyContainers = containers.filter(
        (c) => c.status === 'running' && (c.health === 'healthy' || c.health === 'none')
      ).length;
      totalCount++;
      if (healthyContainers === containers.length) {
        healthyCount++;
        componentStates.push('healthy');
      } else if (healthyContainers > 0) {
        componentStates.push('degraded');
      } else {
        componentStates.push('critical');
      }
      tooltipItems.push(`Containers: ${healthyContainers}/${containers.length} running`);
    }

    // Check host
    if (host) {
      totalCount++;
      const cpuOk = host.cpu_percent < 90;
      const ramUsedPercent = (host.ram_used_gb / host.ram_total_gb) * 100;
      const ramOk = ramUsedPercent < 90;
      const diskUsedPercent = (host.disk_used_gb / host.disk_total_gb) * 100;
      const diskOk = diskUsedPercent < 90;

      if (cpuOk && ramOk && diskOk) {
        healthyCount++;
        componentStates.push('healthy');
      } else if (host.cpu_percent > 95 || ramUsedPercent > 95 || diskUsedPercent > 95) {
        componentStates.push('critical');
      } else {
        componentStates.push('degraded');
      }
      tooltipItems.push(`Host CPU: ${Math.round(host.cpu_percent)}%`);
      tooltipItems.push(`Host RAM: ${Math.round(ramUsedPercent)}%`);
      tooltipItems.push(`Host Disk: ${Math.round(diskUsedPercent)}%`);
    }

    // Also check services from health endpoint
    const serviceKeys = Object.keys(services);
    if (serviceKeys.length > 0 && totalCount === 0) {
      for (const [name, service] of Object.entries(services)) {
        if (['database', 'redis', 'ai'].includes(name)) continue; // Already counted
        totalCount++;
        if (service.status === 'healthy') {
          healthyCount++;
          componentStates.push('healthy');
        } else if (service.status === 'degraded') {
          componentStates.push('degraded');
        } else {
          componentStates.push('critical');
        }
        tooltipItems.push(`${name}: ${service.status}`);
      }
    }

    // Fallback if no data
    if (totalCount === 0) {
      return {
        type: 'infra',
        label: 'Infra',
        state: 'degraded',
        primaryMetric: 'No data',
        tooltipContent: ['Infrastructure metrics unavailable'],
        sectionId: 'section-infra',
      };
    }

    const state = getWorstState(componentStates);

    return {
      type: 'infra',
      label: 'Infra',
      state,
      primaryMetric: `${healthyCount}/${totalCount}`,
      tooltipContent: tooltipItems,
      sectionId: 'section-infra',
    };
  }, [current?.databases, current?.containers, current?.host, services]);

  // Calculate Overall indicator (aggregate of all others)
  const overallIndicator = useMemo((): IndicatorData => {
    const allStates: IndicatorState[] = [
      gpuIndicator.state,
      pipelineIndicator.state,
      aiModelsIndicator.state,
      infraIndicator.state,
    ];

    // Also consider the health endpoint overall status
    if (overallStatus === 'unhealthy') {
      allStates.push('critical');
    } else if (overallStatus === 'degraded') {
      allStates.push('degraded');
    }

    const state = getWorstState(allStates);

    const stateLabel =
      state === 'healthy' ? 'healthy' : state === 'degraded' ? 'degraded' : 'critical';

    return {
      type: 'overall',
      label: 'Overall',
      state,
      primaryMetric: stateLabel,
      tooltipContent: [
        `GPU: ${gpuIndicator.state}`,
        `Pipeline: ${pipelineIndicator.state}`,
        `AI Models: ${aiModelsIndicator.state}`,
        `Infrastructure: ${infraIndicator.state}`,
        overallStatus ? `Health API: ${overallStatus}` : '',
      ].filter(Boolean),
      sectionId: 'section-overall',
    };
  }, [gpuIndicator, pipelineIndicator, aiModelsIndicator, infraIndicator, overallStatus]);

  return (
    <div
      className={clsx(
        'grid gap-3',
        // Desktop: 5 columns
        'grid-cols-2 sm:grid-cols-3 lg:grid-cols-5',
        className
      )}
      role="region"
      aria-label="System health summary"
      data-testid="system-summary-row"
    >
      {/* Overall - spans full width on smallest screens */}
      <div className="col-span-2 sm:col-span-1">
        <SummaryIndicator data={overallIndicator} onClick={handleIndicatorClick} />
      </div>

      <SummaryIndicator data={gpuIndicator} onClick={handleIndicatorClick} />
      <SummaryIndicator data={pipelineIndicator} onClick={handleIndicatorClick} />
      <SummaryIndicator data={aiModelsIndicator} onClick={handleIndicatorClick} />
      <SummaryIndicator data={infraIndicator} onClick={handleIndicatorClick} />
    </div>
  );
}

// Named export for consistency
export { SystemSummaryRow };
