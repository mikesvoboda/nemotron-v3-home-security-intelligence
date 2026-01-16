/**
 * AIServiceStatus component displays the health status of AI services.
 *
 * Shows the overall degradation mode and per-service status for all AI services
 * (RT-DETRv2, Nemotron, Florence-2, CLIP). Used in the system monitoring page
 * and optionally as a header badge.
 *
 * Degradation modes:
 * - normal: All services healthy (green)
 * - degraded: Non-critical services down (yellow)
 * - minimal: Critical services partially available (orange)
 * - offline: All AI services down (red)
 */
import { clsx } from 'clsx';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  RefreshCw,
  XCircle,
  Zap,
} from 'lucide-react';
import { useState } from 'react';

import {
  useAIServiceStatus,
  type AIServiceName,
  type AIServiceState,
  type CircuitState,
  type DegradationLevel,
} from '../../hooks/useAIServiceStatus';

/**
 * Props for the AIServiceStatus component
 */
export interface AIServiceStatusProps {
  /** Whether to show detailed per-service status (default: true) */
  showDetails?: boolean;
  /** Whether to start expanded (default: false) */
  defaultExpanded?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Compact mode for header badge (default: false) */
  compact?: boolean;
}

/**
 * Configuration for degradation level styling
 */
interface DegradationConfig {
  bgColor: string;
  textColor: string;
  borderColor: string;
  icon: typeof CheckCircle;
  iconClassName: string;
  label: string;
  description: string;
}

const DEGRADATION_CONFIG: Record<DegradationLevel, DegradationConfig> = {
  normal: {
    bgColor: 'bg-green-50',
    textColor: 'text-green-800',
    borderColor: 'border-green-200',
    icon: CheckCircle,
    iconClassName: 'h-5 w-5 text-emerald-500',
    label: 'All Systems Operational',
    description: 'All AI services are healthy and functioning normally.',
  },
  degraded: {
    bgColor: 'bg-yellow-50',
    textColor: 'text-yellow-800',
    borderColor: 'border-yellow-200',
    icon: AlertTriangle,
    iconClassName: 'h-5 w-5 text-yellow-600',
    label: 'Degraded Mode',
    description: 'Some non-critical AI services are unavailable. Core detection continues.',
  },
  minimal: {
    bgColor: 'bg-orange-50',
    textColor: 'text-orange-800',
    borderColor: 'border-orange-200',
    icon: AlertCircle,
    iconClassName: 'h-5 w-5 text-orange-600',
    label: 'Minimal Mode',
    description: 'Critical AI services are partially available. Reduced functionality.',
  },
  offline: {
    bgColor: 'bg-red-50',
    textColor: 'text-red-800',
    borderColor: 'border-red-200',
    icon: XCircle,
    iconClassName: 'h-5 w-5 text-red-600',
    label: 'AI Services Offline',
    description: 'All AI services are unavailable. Historical data viewable.',
  },
};

/**
 * Human-readable names for AI services
 */
const SERVICE_DISPLAY_NAMES: Record<AIServiceName, string> = {
  rtdetr: 'RT-DETRv2',
  nemotron: 'Nemotron',
  florence: 'Florence-2',
  clip: 'CLIP',
};

/**
 * Service descriptions
 */
const SERVICE_DESCRIPTIONS: Record<AIServiceName, string> = {
  rtdetr: 'Object detection (persons, vehicles, animals)',
  nemotron: 'Risk analysis and LLM reasoning',
  florence: 'Image captioning and OCR',
  clip: 'Entity re-identification',
};

/**
 * Circuit breaker state styling
 */
interface CircuitStateConfig {
  bgColor: string;
  textColor: string;
  label: string;
}

const CIRCUIT_STATE_CONFIG: Record<CircuitState, CircuitStateConfig> = {
  closed: {
    bgColor: 'bg-green-100',
    textColor: 'text-green-700',
    label: 'Closed',
  },
  half_open: {
    bgColor: 'bg-yellow-100',
    textColor: 'text-yellow-700',
    label: 'Half-Open',
  },
  open: {
    bgColor: 'bg-red-100',
    textColor: 'text-red-700',
    label: 'Open',
  },
};

/**
 * Formats a timestamp for display
 */
function formatTimestamp(timestamp: string | null): string {
  if (!timestamp) {
    return 'Never';
  }

  try {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);

    if (diffSeconds < 60) {
      return `${diffSeconds}s ago`;
    } else if (diffSeconds < 3600) {
      return `${Math.floor(diffSeconds / 60)}m ago`;
    } else if (diffSeconds < 86400) {
      return `${Math.floor(diffSeconds / 3600)}h ago`;
    }

    return date.toLocaleString();
  } catch {
    return 'Unknown';
  }
}

/**
 * Service status row component
 */
function ServiceStatusRow({
  service,
  state,
}: {
  service: AIServiceName;
  state: AIServiceState | null;
}) {
  if (!state) {
    return (
      <div className="flex items-center justify-between rounded-md bg-gray-50 px-3 py-2">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-gray-400" />
          <span className="font-medium text-gray-700">{SERVICE_DISPLAY_NAMES[service]}</span>
        </div>
        <span className="text-sm text-gray-500">Loading...</span>
      </div>
    );
  }

  const circuitConfig = CIRCUIT_STATE_CONFIG[state.circuit_state];

  const statusIcon =
    state.status === 'healthy' ? (
      <CheckCircle className="h-4 w-4 text-emerald-500" />
    ) : state.status === 'degraded' ? (
      <AlertTriangle className="h-4 w-4 text-yellow-600" />
    ) : (
      <XCircle className="h-4 w-4 text-red-600" />
    );

  return (
    <div
      className={clsx(
        'flex flex-col rounded-md px-3 py-2',
        state.status === 'healthy' && 'bg-green-50',
        state.status === 'degraded' && 'bg-yellow-50',
        state.status === 'unavailable' && 'bg-red-50'
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {statusIcon}
          <span className="font-medium text-gray-700">{SERVICE_DISPLAY_NAMES[service]}</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              'rounded px-2 py-0.5 text-xs font-medium',
              circuitConfig.bgColor,
              circuitConfig.textColor
            )}
          >
            {circuitConfig.label}
          </span>
        </div>
      </div>

      <div className="mt-1 flex items-center justify-between text-xs text-gray-500">
        <span>{SERVICE_DESCRIPTIONS[service]}</span>
        <div className="flex items-center gap-3">
          {state.failure_count > 0 && (
            <span className="flex items-center gap-1 text-red-600">
              <AlertCircle className="h-3 w-3" />
              {state.failure_count} failures
            </span>
          )}
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatTimestamp(state.last_success)}
          </span>
        </div>
      </div>

      {state.error_message && (
        <div className="mt-1 rounded bg-red-100 px-2 py-1 text-xs text-red-600">
          {state.error_message}
        </div>
      )}
    </div>
  );
}

/**
 * Available features list component
 */
function FeaturesList({ features }: { features: string[] }) {
  if (features.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 border-t border-gray-200 pt-3">
      <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-gray-500">
        Available Features
      </h4>
      <div className="flex flex-wrap gap-2">
        {features.map((feature) => (
          <span
            key={feature}
            className="flex items-center gap-1 rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-700"
          >
            <Zap className="h-3 w-3" />
            {feature.replace(/_/g, ' ')}
          </span>
        ))}
      </div>
    </div>
  );
}

/**
 * Compact badge for header display
 */
function CompactBadge({ degradationMode }: { degradationMode: DegradationLevel }) {
  const config = DEGRADATION_CONFIG[degradationMode];
  const Icon = config.icon;

  return (
    <div
      className={clsx(
        'flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium',
        config.bgColor,
        config.textColor
      )}
      title={config.description}
    >
      <Icon className="h-3.5 w-3.5" />
      <span className="hidden sm:inline">{config.label}</span>
    </div>
  );
}

/**
 * Display the health status of AI services with optional detailed breakdown.
 *
 * @param showDetails - Whether to show per-service status (default: true)
 * @param defaultExpanded - Whether details start expanded (default: false)
 * @param className - Additional CSS classes
 * @param compact - Compact mode for header badge (default: false)
 */
export function AIServiceStatus({
  showDetails = true,
  defaultExpanded = false,
  className,
  compact = false,
}: AIServiceStatusProps): React.ReactNode {
  const { degradationMode, services, availableFeatures, lastUpdate } = useAIServiceStatus();

  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  // Compact mode - just show badge
  if (compact) {
    return <CompactBadge degradationMode={degradationMode} />;
  }

  const config = DEGRADATION_CONFIG[degradationMode];
  const Icon = config.icon;

  return (
    <div className={clsx('rounded-lg border', config.borderColor, config.bgColor, className)}>
      {/* Header */}
      {showDetails ? (
        <button
          type="button"
          className={clsx(
            'flex w-full items-center justify-between p-4 text-left',
            'cursor-pointer rounded-t-lg hover:bg-opacity-80 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2'
          )}
          onClick={() => setIsExpanded(!isExpanded)}
          aria-expanded={isExpanded}
        >
          <div className="flex items-center gap-3">
            <Icon className={config.iconClassName} aria-hidden="true" />
            <div>
              <h3 className={clsx('font-medium', config.textColor)}>{config.label}</h3>
              <p className="text-sm text-gray-600">{config.description}</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {lastUpdate && (
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <RefreshCw className="h-3 w-3" />
                {formatTimestamp(lastUpdate)}
              </span>
            )}
            {isExpanded ? (
              <ChevronUp className="h-5 w-5 text-gray-400" />
            ) : (
              <ChevronDown className="h-5 w-5 text-gray-400" />
            )}
          </div>
        </button>
      ) : (
        <div className="flex items-center justify-between p-4">
          <div className="flex items-center gap-3">
            <Icon className={config.iconClassName} aria-hidden="true" />
            <div>
              <h3 className={clsx('font-medium', config.textColor)}>{config.label}</h3>
              <p className="text-sm text-gray-600">{config.description}</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {lastUpdate && (
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <RefreshCw className="h-3 w-3" />
                {formatTimestamp(lastUpdate)}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Details (expandable) */}
      {showDetails && isExpanded && (
        <div className="space-y-2 px-4 pb-4">
          <div className="space-y-2 border-t border-gray-200 pt-3">
            <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-gray-500">
              Service Status
            </h4>
            <ServiceStatusRow service="rtdetr" state={services.rtdetr} />
            <ServiceStatusRow service="nemotron" state={services.nemotron} />
            <ServiceStatusRow service="florence" state={services.florence} />
            <ServiceStatusRow service="clip" state={services.clip} />
          </div>

          <FeaturesList features={availableFeatures} />
        </div>
      )}
    </div>
  );
}

export default AIServiceStatus;
